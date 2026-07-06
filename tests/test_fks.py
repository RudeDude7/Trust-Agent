import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def main():
    conn = psycopg2.connect(os.environ.get("SUPABASE_DB_URL"))
    cur = conn.cursor()
    cur.execute("""
        SELECT
            tc.table_name, 
            kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY';
    """)
    for row in cur.fetchall():
        print(row)

if __name__ == "__main__":
    main()
