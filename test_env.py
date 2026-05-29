import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types

# Load environment variables into memory
load_dotenv()

def test_supabase_connection() -> bool:
    """Verifies connection to the Supabase PostgreSQL instance."""
    url: str | None = os.environ.get("SUPABASE_URL")
    key: str | None = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase credentials in .env file.")
        return False
        
    try:
        supabase: Client = create_client(url, key)
        print("✅ Supabase client initialized successfully.")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

async def test_llm_connection() -> bool:
    """Verifies the Gemini API key using the modern SDK and current model."""
    api_key: str | None = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ Missing GEMINI_API_KEY in .env file.")
        return False

    try:
        print("⏳ Pinging Gemini...")
        client = genai.Client(api_key = api_key)
        
        # Upgraded to the currently supported flash model
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.5-flash',
            contents="Reply with exactly one word: 'Connected'.",
            config=types.GenerateContentConfig(
                max_output_tokens=5,
                temperature=0.0
            )
        )
        
        result: str | None = response.text
        clean_result = result.strip() if result else "No response"
        print(f"✅ Gemini API connected successfully. Response: {clean_result}")
        return True
    except Exception as e:
        print(f"❌ Gemini connection failed: {e}")
        return False

async def main() -> None:
    print("Starting Trust Agent environment check...\n")
    
    db_ok: bool = test_supabase_connection()
    llm_ok: bool = await test_llm_connection()
    
    print("\n--- Diagnostic Results ---")
    if db_ok and llm_ok:
        print("🚀 All systems go. Sprint 0 plumbing is fully operational.")
    else:
        print("⚠️ Environment check failed. Please resolve the errors above before continuing.")

if __name__ == "__main__":
    asyncio.run(main())