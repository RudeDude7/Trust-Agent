import os
import time
import uuid
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from exa_py import Exa

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    log.error("Missing SUPABASE_URL or SUPABASE_KEY. Exiting worker.")
    exit(1)

db: Client = create_client(supabase_url, supabase_key)

# Initialize Exa
exa_api_key = os.environ.get("EXA_API_KEY")
if not exa_api_key:
    log.warning("Missing EXA_API_KEY. OSINT lookups will fail if triggered.")
    
try:
    exa = Exa(exa_api_key)
except Exception as e:
    log.error(f"Failed to initialize Exa: {e}")
    exa = None

def get_watched_vendors() -> list[str]:
    """Fetches unique vendor names being watched across all users."""
    # Note: If there are many users, a standard select might return duplicates.
    # For a simple demo, we fetch all and deduplicate in Python.
    res = db.table("watched_vendors").select("vendor_name").execute()
    vendors = {row["vendor_name"] for row in res.data} if res.data else set()
    return list(vendors)

def scan_vendor_threats(vendor_name: str) -> list[dict]:
    """Uses Exa to search for recent security breaches for a specific vendor."""
    if not exa:
        log.error("Exa client not initialized. Cannot scan threats.")
        return []

    log.info(f"Scanning for live threats regarding: {vendor_name}")
    
    query = f"{vendor_name} (data breach OR ransomware OR cyber attack OR security incident OR FTC fine OR compliance violation)"
    
    # Search for news from the last 7 days
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    try:
        response = exa.search_and_contents(
            query,
            type="neural",
            use_autoprompt=True,
            num_results=3,
            text=True,
            start_published_date=one_week_ago
        )
        
        alerts = []
        for res in response.results:
            # Simple heuristic: if it mentions 'breach' or 'ransomware' in title or snippet
            text = f"{res.title} {res.text}".lower()
            if any(keyword in text for keyword in ["breach", "ransomware", "hack", "leaked", "stolen", "vulnerability", "lawsuit", "fine"]):
                alerts.append({
                    "alert_title": res.title,
                    "alert_summary": res.text[:300] + "..." if res.text and len(res.text) > 300 else (res.text or "No summary available."),
                    "source_url": res.url,
                    "severity": "HIGH" if "ransomware" in text or "breach" in text else "MEDIUM"
                })
        
        return alerts
    
    except Exception as e:
        log.error(f"Exa search failed for {vendor_name}: {e}")
        return []

def distribute_alerts(vendor_name: str, alerts: list[dict]):
    """Distributes alerts to all users watching the vendor."""
    if not alerts:
        return

    # Find all users watching this vendor
    res = db.table("watched_vendors").select("user_id").eq("vendor_name", vendor_name).execute()
    if not res.data:
        return
        
    user_ids = [row["user_id"] for row in res.data]
    
    # We need to deduplicate alerts. A simple way is to check if the URL already exists in threat_alerts
    # for the last 7 days.
    existing_res = db.table("threat_alerts").select("source_url").eq("vendor_name", vendor_name).execute()
    existing_urls = {row["source_url"] for row in existing_res.data} if existing_res.data else set()
    
    new_alerts = [a for a in alerts if a["source_url"] not in existing_urls]
    
    if not new_alerts:
        log.info(f"No *new* alerts for {vendor_name}.")
        return
        
    log.info(f"Distributing {len(new_alerts)} new alerts for {vendor_name} to {len(user_ids)} users.")
    
    inserts = []
    for user_id in user_ids:
        for alert in new_alerts:
            inserts.append({
                "user_id": user_id,
                "vendor_name": vendor_name,
                "alert_title": alert["alert_title"],
                "alert_summary": alert["alert_summary"],
                "source_url": alert["source_url"],
                "severity": alert["severity"],
                "is_read": False
            })
            
    if inserts:
        db.table("threat_alerts").insert(inserts).execute()

def main_loop():
    log.info("Starting Live Threat & Breach Monitor Worker...")
    
    # Run every 4 hours. For testing, we can just run once, but in prod it loops.
    INTERVAL_SECONDS = 60 * 60 * 4 
    
    while True:
        try:
            vendors = get_watched_vendors()
            log.info(f"Found {len(vendors)} watched vendors to scan.")
            
            for vendor in vendors:
                alerts = scan_vendor_threats(vendor)
                if alerts:
                    distribute_alerts(vendor, alerts)
                time.sleep(2)  # Rate limiting
                
            log.info(f"Scan cycle complete. Sleeping for {INTERVAL_SECONDS / 3600} hours.")
            
        except Exception as e:
            log.error(f"Error in monitor loop: {e}")
            
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    # If run with --run-once, only do one pass and exit (useful for cron)
    import sys
    if "--run-once" in sys.argv:
        vendors = get_watched_vendors()
        for vendor in vendors:
            alerts = scan_vendor_threats(vendor)
            if alerts:
                distribute_alerts(vendor, alerts)
            time.sleep(2)
        log.info("One-off scan complete. Exiting.")
    else:
        main_loop()
