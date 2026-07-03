import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

res = db.table("audits").select("*").execute()
for audit in res.data:
    print(f"Vendor: {audit.get('vendor_name')} | Session: {audit.get('session_id')} | Chat Length: {len(audit.get('chat_history') or [])}")
