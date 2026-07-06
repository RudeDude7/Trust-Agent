import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
db = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
try:
    res = db.table("threat_alerts").select("*").limit(1).execute()
    print(res.data)
except Exception as e:
    print(e)
