"""
chat_agent.py — Conversational RAG Agent for Vendor Due Diligence

This agent uses LangGraph with MemorySaver for maintaining conversation state.
It answers user follow-ups based on the initial compliance analysis context and 
has access to a similarity search tool to query Supabase for fresh policy chunks.
"""

from typing import Annotated, List, Dict
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from typing_extensions import TypedDict

# Import the retrieve function from comparator_agent
from comparator_agent import _retrieve_chunks

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chat_agent")

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: str
    vendor_name: str
    user_id: str

@tool
def search_policy_documents(query: str, user_id: str) -> str:
    """
    Search the vendor and internal policy documents for specific terms or clauses.
    Use this tool when the user asks a specific question about policies that is not 
    covered by the initial context.
    """
    log.info(f"Targeted similarity search for: '{query}'")
    results = _retrieve_chunks(query, user_id)
    if not results:
        return "No matching policy documents found."
    
    formatted_results = []
    for doc, score in results[:5]:  # Top 5 most relevant
        role = doc.metadata.get("role", "unknown")
        formatted_results.append(f"[{role.upper()} POLICY - Score {score:.2f}]:\n{doc.page_content}")
    
    return "\n\n---\n\n".join(formatted_results)

class ChatAgent:
    def __init__(self):
        # Tools available to the agent
        self.tools = [search_policy_documents]
        
        # LLM setup
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Build the LangGraph State Machine
        workflow = StateGraph(ChatState)
        
        # Define the nodes
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        
        # Define edges
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            tools_condition,
        )
        workflow.add_edge("tools", "agent")
        
        # Compile with checkpointer
        self.memory = MemorySaver()
        self.app = workflow.compile(checkpointer=self.memory)

    def _call_model(self, state: ChatState):
        messages = state["messages"]
        vendor_name = state["vendor_name"]
        context = state["context"]
        
        system_prompt = (
            "You are the Trust Agent, an expert AI assistant focused exclusively on Vendor Due Diligence and Security Policy Analysis. "
            f"You are currently discussing the vendor: {vendor_name}.\n\n"
            "=== CONVERSATIONAL GUARDRAILS ===\n"
            "1. GREETINGS: If the user greets you, politely greet them back and ask how you can help them analyze the vendor context.\n"
            "2. OUT OF BOUNDS: If the user asks something completely unrelated to vendor due diligence, the provided context, or security policies, politely decline to answer and remind them of your purpose.\n"
            "3. ACCURACY: Answer questions using the INITIAL CONTEXT below. If you need more specific details from the policies, use your search_policy_documents tool. If you still cannot find the answer, state clearly that you do not know based on the current data.\n"
            "4. TOOL USAGE: When calling search_policy_documents, make sure to pass the 'user_id' parameter exactly as provided in the state if necessary, or just rely on the tool signature.\n\n"
            "=== INITIAL CONTEXT (Findings & OSINT) ===\n"
            f"{context}"
        )
        
        # Prepend system message if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        else:
            # Update system message with latest context
            messages[0] = SystemMessage(content=system_prompt)
            
        # The tool requires user_id. We can wrap the tool or just bind it, 
        # but since LangChain passes kwargs, we can use an injected dependency 
        # or bind the user_id dynamically. For simplicity, we'll let the LLM pass user_id,
        # but to guarantee security, we should ideally inject it.
        # However, passing it as a system prompt instruction works for this internal tool.
        # We will append an instruction to always use this user_id:
        user_id = state.get("user_id", "")
        messages[0].content += f"\n\nCRITICAL: When using the search_policy_documents tool, ALWAYS pass '{user_id}' as the user_id argument."

        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def invoke(self, vendor_name: str, context: str, history: List[Dict[str, str]], user_msg: str, session_id: str, user_id: str) -> str:
        """
        Invokes the stateful agent. 
        Note: history parameter is kept for backward compatibility if api.py still manages it, 
        but LangGraph's checkpointer will naturally maintain state across invokes with the same session_id.
        """
        config = {"configurable": {"thread_id": session_id}}
        
        # If this is the first turn for this thread, we need to initialize the state
        # with the history loaded from Supabase to seamlessly bridge the stateless/stateful gap.
        current_state = self.app.get_state(config)
        if not current_state.values:
            log.info(f"Initializing LangGraph memory for session {session_id} from Supabase history")
            initial_messages = []
            for msg in history:
                if msg["role"] == "user":
                    initial_messages.append(HumanMessage(content=msg["content"]))
                else:
                    initial_messages.append(AIMessage(content=msg["content"]))
            
            # Update the state directly before invoking
            if initial_messages:
                self.app.update_state(config, {"messages": initial_messages, "vendor_name": vendor_name, "context": context, "user_id": user_id})
                
        # Invoke the agent with the new user message
        input_state = {
            "messages": [HumanMessage(content=user_msg)],
            "vendor_name": vendor_name,
            "context": context,
            "user_id": user_id
        }
        
        result = self.app.invoke(input_state, config)
        
        # The final message is the agent's response
        final_message = result["messages"][-1].content
        return final_message
