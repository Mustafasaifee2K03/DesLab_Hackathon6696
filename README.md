# UniSphere: Agentic Cross-Domain Recommendation Platform

UniSphere is a complete web product that unifies recommendations across:

- Videos
- Music
- Podcasts
- Movies
- News

It is implemented as an AI-agent style application using LangChain + LangGraph and now runs in dynamic live-data mode (no static seed dependency in runtime flow).

## Current Product Flow (3 Pages)

1. `GET /` (Onboarding)
- User selects interests from relevant options.
- User enters demand_text (specific requirement in natural language).

2. `GET /preferences`
- User selects languages.
- User sets domain weights.

3. `GET /feed`
- System shows dynamic recommendations.
- User can filter and provide feedback.

## Why this fits Topic 3

- Unified multi-domain recommendation experience
- Cross-domain relevance transfer
- Agentic orchestration for retrieval planning
- Dynamic source ingestion for real-world applicability
- Explainable recommendation cards

## Architecture

- Backend: FastAPI
- Agent Orchestration: LangChain tools + LangGraph state graph
- Storage: SQLite
- Frontend: Multi-page Jinja templates + vanilla JS
- Live Connectors: iTunes, TVMaze, Google News RSS, Internet Archive

### Core modules

- `app/main.py`
- `app/agentic_workflow.py`
- `app/recommender.py`
- `app/live_sources.py`
- `app/database.py`
- `app/schemas.py`
- `app/templates/onboarding.html`
- `app/templates/preferences.html`
- `app/templates/feed.html`
- `app/static/app.js`
- `app/static/styles.css`

## Recommendation Method Highlights

- Interest and demand_text driven intent parsing
- Alias-aware relevance expansion (e.g., tech -> ai/technology/engineering/startup)
- Domain-weight enforcement (0% domains excluded)
- Feedback-driven affinity updates
- Agent-triggered live refresh when inventory coverage is weak

## Run Locally

```bash
chmod +x run.sh
./run.sh
```

Open:

- `http://localhost:8000`

## API Endpoints

- `GET /api/health`
- `GET /api/meta`
- `PUT /api/users/{user_id}/profile`
- `GET /api/users/{user_id}/profile`
- `GET /api/users/{user_id}/recommendations`
- `POST /api/users/{user_id}/feedback`
- `GET /api/users/{user_id}/feedback`
- `POST /api/live/refresh` (optional manual refresh)

## Documentation

- `USER_GUIDE.md` for user instructions
- `DesLab_Hackathon6696_Design_Document.docx` for full design decisions and architecture
