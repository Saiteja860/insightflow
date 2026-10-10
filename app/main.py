"""InsightFlow API and dashboard."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analysis import analyze_feedback
from .db import Database
from .insights import generate_decisions, summarize
from .seed import SAMPLE_FEEDBACK

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="InsightFlow", version="0.1.0",
              description="Intelligent customer feedback and decision platform")
# On Vercel the filesystem is read-only except /tmp — store the SQLite DB there
_DEFAULT_DB = "/tmp/insightflow.db" if os.getenv("VERCEL") else str(BASE_DIR / "data" / "insightflow.db")
db = Database(os.getenv("INSIGHTFLOW_DB", _DEFAULT_DB))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class FeedbackIn(BaseModel):
    text: str = Field(min_length=3, max_length=5000)
    source: Literal["survey", "email", "chat", "review", "social", "web"] = "web"
    customer_id: Optional[str] = Field(default=None, max_length=100)
    channel: Optional[str] = Field(default="web", max_length=50)


class StatusIn(BaseModel):
    status: Literal["open", "in_progress", "done", "dismissed"]


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "feedback_count": len(db.all_feedback())}


@app.post("/api/feedback", status_code=201)
def submit_feedback(payload: FeedbackIn):
    analysis = analyze_feedback(payload.text)
    record = {
        **payload.model_dump(),
        **analysis.to_dict(),
    }
    fid = db.insert_feedback(record)
    return {"id": fid, "analysis": analysis.to_dict()}


@app.get("/api/feedback")
def list_feedback(limit: int = 50, sentiment: Optional[str] = None):
    limit = max(1, min(limit, 500))
    return db.list_feedback(limit=limit, sentiment=sentiment)


@app.get("/api/insights")
def insights():
    return summarize(db.all_feedback())


@app.post("/api/decisions/generate")
def create_decisions():
    """Generate recommendations from current feedback and store new ones."""
    existing_titles = {(d["title"], d["status"]) for d in db.list_decisions() if d["status"] == "open"}
    created = []
    for d in generate_decisions(db.all_feedback()):
        if (d["title"], "open") in existing_titles:
            continue
        d["id"] = db.insert_decision(d)
        d["status"] = "open"
        created.append(d)
    return {"created": created, "count": len(created)}


@app.get("/api/decisions")
def list_decisions():
    return db.list_decisions()


@app.patch("/api/decisions/{decision_id}")
def update_decision(decision_id: int, payload: StatusIn):
    if not db.update_decision_status(decision_id, payload.status):
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"id": decision_id, "status": payload.status}


@app.post("/api/seed")
def seed(reset: bool = False):
    """Load sample feedback so the dashboard has data to show."""
    if reset:
        db.clear()
    for item in SAMPLE_FEEDBACK:
        analysis = analyze_feedback(item["text"])
        db.insert_feedback({**item, **analysis.to_dict()})
    return {"loaded": len(SAMPLE_FEEDBACK)}
