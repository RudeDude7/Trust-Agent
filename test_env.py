import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import Client, create_client

load_dotenv()

def test_supabase_connection() -> bool:
    """Verifies connectivity to the configured Supabase PostgreSQL instance."""
    url: str | None = os.environ.get("SUPABASE_URL")
    key: str | None = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("[Error] Missing Supabase credentials in environment.")
        return False
        
    try:
        supabase: Client = create_client(url, key)
        print("[Success] Supabase client initialized.")
        return True
    except Exception as e:
        print(f"[Error] Supabase connection failed: {e}")
        return False

async def test_llm_connection() -> bool:
    """Validates API authentication and inference capabilities with the LLM provider."""
    api_key: str | None = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("[Error] Missing GEMINI_API_KEY in environment.")
        return False

    try:
        print("Pinging LLM provider...")
        client = genai.Client(api_key=api_key)
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.5-flash',
            contents="Reply with exactly one word: 'Connected'.",
            config=types.GenerateContentConfig(
                max_output_tokens=5,
                temperature=0.0
            )
        )
        
        clean_result = response.text.strip() if response.text else "No response"            
        print(f"[Success] LLM API connected. Response: {clean_result}")
        return True
    except Exception as e:
        print(f"[Error] LLM connection failed: {e}")
        return False

async def main() -> None:
    print("Starting environment diagnostic check...\n")
    
    db_ok: bool = test_supabase_connection()
    llm_ok: bool = await test_llm_connection()
    
    print("\n--- Diagnostic Results ---")
    if db_ok and llm_ok:
        print("[OK] Core infrastructure operational.")
    else:
        print("[Warning] Environment check failed. Review logs above.")

if __name__ == "__main__":
    asyncio.run(main())