"""
api.py — FastAPI wrapper for the Vendor Due Diligence LangGraph Pipeline

This module exposes our agentic pipeline as a REST API.
Run it locally with: uvicorn api:app --reload
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import build_graph
from state import VendorDueDiligenceState

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

# Initialize the FastAPI app
app = FastAPI(
    title="Trust Agent - Vendor Due Diligence API",
    description="API for running automated vendor due diligence using LangGraph.",
    version="1.0.0"
)

# Build the graph once at startup so we don't rebuild it on every request
log.info("Compiling LangGraph pipeline...")
graph_app = build_graph()
log.info("Pipeline compiled successfully.")

# Define the Pydantic schema for the incoming request body
class AnalyzeRequest(BaseModel):
    vendor_name: str
    vendor_url: Optional[str] = None

# Define the endpoint
@app.post("/analyze")
async def analyze_vendor(request: AnalyzeRequest):
    """
    Triggers the LangGraph pipeline to perform due diligence on a vendor.
    """
    log.info(f"Received analysis request for vendor: {request.vendor_name}")

    try:
        # Construct the initial state
        initial_state: VendorDueDiligenceState = { # type: ignore[typeddict-item]
            "vendor_name": request.vendor_name,
            "vendor_url": request.vendor_url or "",
        }

        # Invoke the graph synchronously (since our agents use synchronous LangChain calls right now)
        # In a high-traffic production system, we would convert the node functions to async.
        final_state = graph_app.invoke(initial_state)

        # Extract the final assessment
        assessment = final_state.get("risk_assessment")
        if not assessment:
            raise HTTPException(status_code=500, detail="Pipeline completed but no risk assessment was generated.")

        return {
            "status": "success",
            "vendor": request.vendor_name,
            "risk_assessment": assessment
        }

    except Exception as e:
        log.error(f"Error during pipeline execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Simple health check endpoint for Cloud Run / load balancers."""
    return {"status": "healthy"}
