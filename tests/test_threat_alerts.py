import os
import uuid
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
db = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
try:
    fake_user = str(uuid.uuid4())
    res = db.table("threat_alerts").select("*").eq("user_id", fake_user).order("created_at", desc=True).execute()
    print("SUCCESS", res)
except Exception as e:
    print("FAILED", type(e), str(e))
    import traceback
    traceback.print_exc()
