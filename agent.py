import asyncio
import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

def get_llm() -> ChatGoogleGenerativeAI:
    """Initializes the LLM client with deterministic inference parameters."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.0,
        max_tokens=500,
    )

def get_prompt_template() -> ChatPromptTemplate:
    """Constructs the system and user prompt templates for vendor analysis."""
    return ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a senior vendor risk analyst. Your job is to provide concise, "
            "factual risk assessments of third-party companies. You must be "
            "objective and brief. Do not hallucinate data."
        ),
        (
            "human", 
            "Please provide a brief, 2-sentence risk overview for the following "
            "company: {company_name}"
        )
    ])

async def analyze_vendor(company_name: str) -> str:
    """Executes the LangChain processing pipeline for a given vendor."""
    llm = get_llm()
    prompt = get_prompt_template()
    
    # Construct LCEL pipeline
    chain = prompt | llm
    
    print(f"Executing risk assessment pipeline for: {company_name}...")
    response = await chain.ainvoke({"company_name": company_name})
    
    return str(response.content)

async def main() -> None:
    print("Initializing Trust Agent Assessment Module...\n")
    
    target_company = "TikTok" 
    result = await analyze_vendor(target_company)
    
    print("\n--- Assessment Report ---")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())