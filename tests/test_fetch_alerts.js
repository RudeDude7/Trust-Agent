const API_BASE = "http://localhost:8000";

async function run() {
  try {
    const res = await fetch(`${API_BASE}/threat_alerts`);
    const data = await res.json();
    console.log(data);
  } catch (e) {
    console.error("Error:", e);
  }
}
run();
