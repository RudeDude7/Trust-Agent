import os, sys
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv('.env')
from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

try:
    res = db.table("documents").select("id, metadata").eq("user_id", "00000000-0000-0000-0000-000000000000").execute()
    print("Success:", res)
except Exception as e:
    print("Error:", repr(e))
