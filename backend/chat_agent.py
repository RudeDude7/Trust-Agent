from langchain_google_genai import ChatGoogleGenerativeAI
from typing import List, Dict

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

class ChatAgent:
    def __init__(self):
        # We use a slightly higher temperature for conversational fluidity, but keep it low for accuracy.
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

    def invoke(self, vendor_name: str, context: str, history: List[Dict[str, str]], user_msg: str) -> str:
        """
        history is expected to be a list of dictionaries with 'role' ('user' or 'agent') and 'content'.
        """
        system_prompt_text = (
            "You are the Trust Agent, an expert AI assistant focused exclusively on Vendor Due Diligence and Security Policy Analysis. "
            f"You are currently discussing the vendor: {vendor_name}.\n\n"
            "=== CONVERSATIONAL GUARDRAILS ===\n"
            "1. GREETINGS: If the user greets you (e.g., 'hello', 'hi', 'how are you'), politely greet them back and ask how you can help them analyze the vendor context.\n"
            "2. OUT OF BOUNDS: If the user asks something completely unrelated to vendor due diligence, the provided context, or security policies (e.g., 'write a poem', 'what is the capital of France?'), politely decline to answer and remind them of your purpose.\n"
            "3. ACCURACY: Answer the user's questions using ONLY the provided context from the RAG and OSINT pipeline below. If the context does not contain the answer, state clearly that you do not know based on the current data.\n\n"
            "=== ANALYSIS CONTEXT ===\n"
            f"{context}"
        )

        messages = [SystemMessage(content=system_prompt_text)]
        
        # Inject conversational history safely using Message objects
        # This prevents LangChain from trying to parse curly braces { } inside history as variables.
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
            
        # Add the current user message
        messages.append(HumanMessage(content=user_msg))

        # Directly invoke the LLM with the message list
        response = self.llm.invoke(messages)
        
        return response.content
