import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# 1. Open the Vault
load_dotenv()

def get_llm() -> ChatGoogleGenerativeAI:
    """Initializes and returns the Gemini model (The Brain)."""
    # LangChain automatically looks for GEMINI_API_KEY in your environment variables.
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.0, # Zero creativity. We want strict, factual analysis.
        max_tokens=500,
    )

def get_prompt_template() -> ChatPromptTemplate:
    """Defines Trust Agent's core persona and input variables."""
    # A ChatPromptTemplate separates instructions into different "Roles"
    return ChatPromptTemplate.from_messages([
        # The System prompt is the absolute law. It tells the AI WHO it is.
        ("system", "You are Trust Agent, a senior vendor risk analyst. Your job is to provide concise, factual risk assessments of third-party companies. You must be objective and brief. Do not hallucinate data."),
        
        # The Human prompt is what we inject dynamically on every run.
        ("human", "Please provide a brief, 2-sentence risk overview for the following company: {company_name}")
    ])

async def analyze_vendor(company_name: str) -> str:
    """Orchestrates the LangChain pipeline to analyze a specific vendor."""
    llm = get_llm()
    prompt = get_prompt_template()
    
    # 2. Build the Pipeline using LCEL (LangChain Expression Language)
    # The '|' symbol means "Pipe the output of the prompt directly into the LLM"
    chain = prompt | llm
    
    print(f"⏳ Trust Agent is analyzing {company_name}...")
    
    # 3. Execute the Chain Asynchronously
    # We pass in a dictionary containing our variables
    response = await chain.ainvoke({"company_name": company_name})
    
    # LangChain returns a complex AIMessage object. We just want the raw text content.
    return str(response.content)

async def main() -> None:
    print("Starting Trust Agent Sprint 1 Engine...\n")
    
    # Change the target to prove we are just auditing them
    target_company = "TikTok" 
    result = await analyze_vendor(target_company)
    
    print("\n--- Assessment Report ---")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())