"""
chat_agent.py — Conversational RAG Agent for Vendor Due Diligence

This agent uses LangGraph with MemorySaver for maintaining conversation state.
It answers user follow-ups based on the initial compliance analysis context and
has access to a similarity search tool to query Supabase for fresh policy chunks.
"""

from typing import Annotated, List, Dict
import logging
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from typing_extensions import TypedDict
from typing import Any

from comparator_agent import _retrieve_chunks

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chat_agent")


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: str
    vendor_name: str
    user_id: str


def _build_search_tool(user_id: str):
    """
    Creates a search tool with user_id baked into the closure.
    The LLM only sees and controls the 'query' parameter —
    user_id is injected server-side and invisible to the model.
    """
    @tool
    def search_policy_documents(query: str) -> str:
        """
        Search the vendor and internal policy documents for specific terms or clauses.
        Use this tool when the user asks a specific question about policies that is not
        covered by the initial context.
        """
        log.info("Targeted similarity search for: '%s' (user: %s)", query, user_id)
        results = _retrieve_chunks(query, user_id)
        if not results:
            return "No matching policy documents found."

        formatted_results = []
        for doc, score in results[:5]:
            role = doc.metadata.get("role", "unknown")
            formatted_results.append(f"[{role.upper()} POLICY - Score {score:.2f}]:\n{doc.page_content}")

        return "\n\n---\n\n".join(formatted_results)

    return search_policy_documents


class ChatAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
        self.memory = MemorySaver()
        # Graph and tools are now built per-session in invoke(),
        # since each session needs a tool scoped to that user's ID.
        self._compiled_graphs: dict[str, Any] = {}

    def _get_or_build_graph(self, user_id: str):
        """
        Returns a compiled graph with the search tool scoped to this user_id.
        Cached per user_id so repeated calls don't rebuild.
        """
        if user_id in self._compiled_graphs:
            return self._compiled_graphs[user_id]

        # Build a tool with user_id baked in — LLM cannot see or alter it
        search_tool = _build_search_tool(user_id)
        tools = [search_tool]

        llm_with_tools = self.llm.bind_tools(tools)

        def call_model(state: ChatState):
            messages = state["messages"]
            vendor_name = state["vendor_name"]
            context = state["context"]

            system_prompt = (
                "You are the Trust Agent, an expert AI assistant focused exclusively on Vendor Due Diligence and Security Policy Analysis. "
                f"You are currently discussing the vendor: {vendor_name}.\n\n"
                "=== CONVERSATIONAL GUARDRAILS ===\n"
                "1. GREETINGS: If the user greets you, politely greet them back and ask how you can help them analyze the vendor context.\n"
                "2. OUT OF BOUNDS: If the user asks something completely unrelated to vendor due diligence, the provided context, or security policies, politely decline to answer and remind them of your purpose.\n"
                "3. ACCURACY: Answer questions using the INITIAL CONTEXT below. If you need more specific details from the policies, use your search_policy_documents tool. If you still cannot find the answer, state clearly that you do not know based on the current data.\n\n"
                "=== INITIAL CONTEXT (Findings & OSINT) ===\n"
                f"{context}"
            )

            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_prompt)] + messages
            else:
                messages[0] = SystemMessage(content=system_prompt)

            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}

        workflow = StateGraph(ChatState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(tools))
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")

        compiled = workflow.compile(checkpointer=self.memory)
        self._compiled_graphs[user_id] = compiled
        return compiled

    def invoke(self, vendor_name: str, context: str, history: List[Dict[str, str]], user_msg: str, session_id: str, user_id: str) -> str:
        """
        Invokes the stateful agent with user_id securely scoped via closure.
        """
        app = self._get_or_build_graph(user_id)
        config = {"configurable": {"thread_id": session_id}}

        # Initialize memory from Supabase history if this is the first turn
        current_state = app.get_state(config)
        if not current_state.values:
            log.info("Initializing LangGraph memory for session %s from Supabase history", session_id)
            initial_messages = []
            for msg in history:
                if msg["role"] == "user":
                    initial_messages.append(HumanMessage(content=msg["content"]))
                else:
                    initial_messages.append(AIMessage(content=msg["content"]))

            if initial_messages:
                app.update_state(config, {
                    "messages": initial_messages,
                    "vendor_name": vendor_name,
                    "context": context,
                    "user_id": user_id
                })

        input_state = {
            "messages": [HumanMessage(content=user_msg)],
            "vendor_name": vendor_name,
            "context": context,
            "user_id": user_id
        }

        result = app.invoke(input_state, config)
        return result["messages"][-1].content