from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Any
from datetime import datetime
from google.cloud import spanner

# Local imports
from models import DEFAULT_ISSUE_CATEGORIES
from spanner_store import get_database

app = FastAPI(title="CivicAurAI API")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/categories")
async def get_categories():
    """Return the available categories from our local system."""
    return [c.model_dump() for c in DEFAULT_ISSUE_CATEGORIES]


@app.get("/api/reports")
async def get_reports(limit: int = 20):
    """
    Fetch mixed data from local Spanner and public SF311 API.
    Returns a unified format for the dashboard.
    """
    unified_reports: List[Dict[str, Any]] = []

    # 1. Fetch Local Spanner Data (CivicAurAI detected issues)
    try:
        db = get_database()
        with db.snapshot() as snapshot:
            # Simple query to get the most recent non-resolved issues
            results = snapshot.execute_sql(
                "SELECT IssueId, CategoryId, Latitude, Longitude, Status, CreatedAt "
                "FROM Issues "
                "ORDER BY CreatedAt DESC LIMIT @limit",
                params={"limit": limit},
                param_types={"limit": spanner.param_types.INT64}
            )
            for row in results:
                unified_reports.append({
                    "id": row[0],
                    "title": row[1], # CategoryId as Title fallback
                    "status": row[4],
                    "lat": row[2],
                    "lng": row[3],
                    "source": "CivicAurAI",
                    "agency": "Local System",
                    "created_at": row[5].isoformat() if row[5] else None,
                    "image_url": None # Placeholder
                })
    except Exception as e:
        print(f"Error fetching from Spanner: {e}")

    # 2. Fetch Public SF311 Data (via DataSF API)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://data.sfgov.org/resource/vw6y-z8j6.json",
                params={
                    "$limit": limit,
                    "$order": "requested_datetime DESC"
                }
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data:
                # Map SF311 format
                unified_reports.append({
                    "id": item.get("service_request_id"),
                    "title": item.get("service_details") or item.get("service_name"),
                    "status": item.get("status_notes") or item.get("status_description"),
                    "lat": float(item.get("lat", 0)) if item.get("lat") else 0.0,
                    "lng": float(item.get("long", 0)) if item.get("long") else 0.0,
                    "source": "SF311 Public",
                    "agency": item.get("agency_responsible"),
                    "created_at": item.get("requested_datetime"),
                    "image_url": item.get("media_url") # Some SF311 tickets have images
                })
    except Exception as e:
        print(f"Error fetching from SF311 API: {e}")

    # Combine and sort roughly by date (ignoring strict timezone issues for prototype)
    unified_reports.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return unified_reports[:limit*2]
