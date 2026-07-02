from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import List, Dict

class ChatAgent:
    def __init__(self):
        # We use a slightly higher temperature for conversational fluidity, but keep it low for accuracy.
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

    def invoke(self, vendor_name: str, context: str, history: List[Dict[str, str]], user_msg: str) -> str:
        """
        history is expected to be a list of dictionaries with 'role' ('user' or 'agent') and 'content'.
        """
        system_prompt = (
            "You are the Trust Agent, an expert AI assistant focused exclusively on Vendor Due Diligence and Security Policy Analysis. "
            f"You are currently discussing the vendor: {vendor_name}.\n\n"
            "=== CONVERSATIONAL GUARDRAILS ===\n"
            "1. GREETINGS: If the user greets you (e.g., 'hello', 'hi', 'how are you'), politely greet them back and ask how you can help them analyze the vendor context.\n"
            "2. OUT OF BOUNDS: If the user asks something completely unrelated to vendor due diligence, the provided context, or security policies (e.g., 'write a poem', 'what is the capital of France?'), politely decline to answer and remind them of your purpose.\n"
            "3. ACCURACY: Answer the user's questions using ONLY the provided context from the RAG and OSINT pipeline below. If the context does not contain the answer, state clearly that you do not know based on the current data.\n\n"
            "=== ANALYSIS CONTEXT ===\n"
            "{context}"
        )

        messages = [("system", system_prompt)]
        
        # Inject conversational history
        for msg in history:
            role = "human" if msg["role"] == "user" else "ai"
            messages.append((role, msg["content"]))
            
        # Add the current user message
        messages.append(("human", "{message}"))

        prompt = ChatPromptTemplate.from_messages(messages)
        
        chain = prompt | self.llm
        
        response = chain.invoke({
            "context": context,
            "message": user_msg
        })
        
        return response.content
