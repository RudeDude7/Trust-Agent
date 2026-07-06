import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

async def main():
    db = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    
    # Get a session ID that belongs to the user
    # Or just use the test_delete approach
    try:
        # Create a dummy audit
        test_session = "12345678-1234-5678-1234-567812345678"
        db.table("audits").insert({
            "session_id": test_session,
            "user_id": "12dce423-7541-4ab2-825d-997abf598b82",
            "vendor_name": "Test Delete",
            "risk_assessment": {"overall_risk_level": "LOW"}
        }).execute()
        print("Inserted dummy audit")

        # Now delete it
        res = db.table("audits").delete().eq("session_id", test_session).execute()
        print("Deleted dummy audit:", res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
