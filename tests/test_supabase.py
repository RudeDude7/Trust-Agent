import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
db = create_client(supabase_url, supabase_key)
try:
    res = db.table("threat_alerts_missing").select("*").execute()
    print("Success", res)
except Exception as e:
    print("Exception:", str(e))
    import traceback
    traceback.print_exc()
