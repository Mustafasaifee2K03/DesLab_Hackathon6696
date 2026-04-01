from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .data_loader import load_seed_data
from .agentic_workflow import refresh_live_catalog, run_recommendation_agent
from .database import (
    get_all_content,
    get_feedback,
    get_user_profile,
    init_db,
    insert_feedback,
    upsert_user_profile,
)
from .recommender import feedback_summary
from .schemas import DOMAINS, FEEDBACK_ACTIONS, FeedbackPayload, ProfilePayload

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="UniSphere Recommendation Platform",
    version="1.0.0",
    description="Unified cross-domain recommendation platform for videos, music, podcasts, movies, and news.",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    synced = load_seed_data()
    if synced:
        print(f"Synced {synced} seed content records")


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "domains": DOMAINS})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/meta")
def meta() -> dict:
    return {
        "domains": DOMAINS,
        "actions": FEEDBACK_ACTIONS,
        "content_count": len(get_all_content()),
        "agent_framework": "langchain-langgraph",
    }


@app.put("/api/users/{user_id}/profile")
def upsert_profile(user_id: str, payload: ProfilePayload) -> dict:
    cleaned_id = re.sub(r"[^a-zA-Z0-9_-]", "", user_id).strip()
    if len(cleaned_id) < 3:
        raise HTTPException(status_code=400, detail="user_id must be at least 3 alphanumeric characters")

    if set(payload.domain_weights.keys()) != set(DOMAINS):
        raise HTTPException(
            status_code=400,
            detail=f"domain_weights must contain exactly these keys: {DOMAINS}",
        )

    total_weights = sum(payload.domain_weights.values())
    if total_weights <= 0:
        raise HTTPException(status_code=400, detail="domain_weights total must be greater than 0")

    normalized_weights = {
        domain: int((weight / total_weights) * 100)
        for domain, weight in payload.domain_weights.items()
    }

    # Keep total around 100 after integer rounding.
    drift = 100 - sum(normalized_weights.values())
    if drift != 0:
        top_domain = max(normalized_weights.items(), key=lambda pair: pair[1])[0]
        normalized_weights[top_domain] += drift

    profile_doc = {
        "user_id": cleaned_id,
        "name": payload.name.strip(),
        "interests": [item.lower().strip() for item in payload.interests if item.strip()],
        "languages": [lang.lower().strip() for lang in payload.languages if lang.strip()],
        "moods": [mood.lower().strip() for mood in payload.moods if mood.strip()],
        "domain_weights": normalized_weights,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    upsert_user_profile(profile_doc)

    return {"status": "ok", "profile": profile_doc}


@app.get("/api/users/{user_id}/profile")
def get_profile(user_id: str) -> dict:
    profile = get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/api/users/{user_id}/recommendations")
def get_recommendations(
    user_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    domain: str | None = Query(default=None),
    max_duration: int | None = Query(default=None, ge=1, le=600),
    enable_language_fallback: bool = Query(default=True),
) -> dict:
    profile = get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Create profile first")

    if domain and domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"domain must be one of: {DOMAINS}")

    result = run_recommendation_agent(
        profile=profile,
        domain=domain,
        limit=limit,
        max_duration=max_duration,
        enable_language_fallback=enable_language_fallback,
    )

    return {"user_id": user_id, **result}


@app.post("/api/live/refresh")
def refresh_live(
    user_id: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    limit_per_domain: int = Query(default=8, ge=1, le=30),
) -> dict:
    if domain and domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"domain must be one of: {DOMAINS}")

    query_terms = ["trending", "technology"]
    languages = ["en"]
    domains = [domain] if domain else DOMAINS

    if user_id:
        profile = get_user_profile(user_id)
        if profile:
            query_terms = (profile["interests"] + profile["moods"])[:4] or query_terms
            languages = profile["languages"] or languages
            if not domain:
                domains = sorted(
                    profile["domain_weights"],
                    key=lambda d: profile["domain_weights"][d],
                    reverse=True,
                )

    added = refresh_live_catalog(
        domains=domains,
        query_terms=query_terms,
        languages=languages,
        limit_per_domain=limit_per_domain,
    )
    return {
        "status": "ok",
        "added": added,
        "domains": domains,
        "languages": languages,
        "content_count": len(get_all_content()),
    }


@app.post("/api/users/{user_id}/feedback")
def post_feedback(user_id: str, payload: FeedbackPayload) -> dict:
    if not get_user_profile(user_id):
        raise HTTPException(status_code=404, detail="Create profile first")

    all_ids = {item["id"] for item in get_all_content()}
    if payload.content_id not in all_ids:
        raise HTTPException(status_code=404, detail="content_id not found")

    insert_feedback(
        user_id=user_id,
        content_id=payload.content_id,
        action=payload.action,
        ts=datetime.now(timezone.utc).isoformat(),
    )
    return {"status": "ok", "summary": feedback_summary(user_id)}


@app.get("/api/users/{user_id}/feedback")
def list_feedback(user_id: str) -> dict:
    if not get_user_profile(user_id):
        raise HTTPException(status_code=404, detail="Create profile first")
    rows = get_feedback(user_id)
    return {"count": len(rows), "items": rows, "summary": feedback_summary(user_id)}
