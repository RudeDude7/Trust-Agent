from ingest import get_supabase_client
db = get_supabase_client()
print(dir(db.auth))
