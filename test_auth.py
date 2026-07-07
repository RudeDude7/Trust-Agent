import os, sys
from dotenv import load_dotenv
load_dotenv('.env')
from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

try:
    res = db.auth.sign_up({"email": "testagent123@example.com", "password": "TestPassword123!"})
    token = res.session.access_token if res.session else "NO_SESSION"
    print("TOKEN:", token)
except Exception as e:
    try:
        res = db.auth.sign_in_with_password({"email": "testagent123@example.com", "password": "TestPassword123!"})
        print("TOKEN:", res.session.access_token)
    except Exception as e2:
        print("Error:", repr(e2))
