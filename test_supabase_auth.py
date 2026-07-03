from ingest import get_supabase_client
import sys
db = get_supabase_client()
print(dir(db.auth))
