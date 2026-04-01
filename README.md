# UniSphere: Cross-Domain Recommendation Platform

UniSphere is a complete web product that aggregates and recommends content across five domains in one interface:

- Videos
- Music
- Podcasts
- Movies
- News

It solves disconnected discovery workflows by combining multi-domain content into one personalized feed with explainable recommendations.
It now uses an agentic pipeline built with LangChain + LangGraph to plan, fetch, and rank recommendations.

## Why this fits Topic 3

- Unified recommendation feed across formats
- Personalized ranking based on explicit profile + behavioral feedback
- Cross-domain transfer learning (likes in one domain influence others)
- Scalable architecture with clear domain adapters and normalized schema
- AI-agent orchestration using LangChain/LangGraph

## Product Capabilities

- Profile onboarding: interests, mood, languages, and domain weights
- Hybrid recommendation model:
  - Interest-tag overlap
  - Domain preference weighting
  - Recency/freshness
  - Popularity
  - Behavioral affinity from feedback
  - Cross-domain affinity boost
- Explainable cards: every recommendation includes a reason
- Real-time feedback loop: like, dislike, save, hide, view
- Filter controls: domain, max duration, result count
- Smart language fallback: if selected languages return no matches, English fallback is applied with an explanatory message
- Live source sync: fetches fresh content from external providers on-demand and during agent planning

## Architecture

- Backend: FastAPI
- Storage: SQLite
- Frontend: Jinja template + modern vanilla JS/CSS
- Data: seed adapters + live connectors (iTunes, TVMaze, Google News RSS, Internet Archive)
- Agent runtime: LangChain tools + LangGraph state graph

### Core modules

- `app/main.py`: API + web routes
- `app/agentic_workflow.py`: LangGraph recommendation agent (plan -> refresh -> retrieve)
- `app/live_sources.py`: live provider connectors and normalization
- `app/database.py`: SQLite schema and queries
- `app/data_loader.py`: seed ingestion from source files
- `app/recommender.py`: hybrid scoring and diversity reranking
- `app/data/sources/*.json`: multi-domain normalized content records
- `app/templates/index.html`: complete UI
- `app/static/app.js`: feed, controls, profile handling, feedback actions
- `app/static/styles.css`: polished responsive UI styling

## Normalized Content Schema

Every item follows one generalized schema:

- `id`
- `domain`
- `title`
- `description`
- `tags[]`
- `language`
- `duration_minutes`
- `source`
- `url`
- `creator`
- `published_at`
- `popularity`

## Run Locally

```bash
chmod +x run.sh
./run.sh
```

Then open:

- `http://localhost:8000`

## User Guide

- See `USER_GUIDE.md` for step-by-step usage and troubleshooting.

## API Endpoints

- `GET /api/health`
- `GET /api/meta`
- `PUT /api/users/{user_id}/profile`
- `GET /api/users/{user_id}/profile`
- `GET /api/users/{user_id}/recommendations`
- `POST /api/users/{user_id}/feedback`
- `GET /api/users/{user_id}/feedback`
- `POST /api/live/refresh`

## Submission Checklist Mapping

- Complete product: yes (full-stack web app)
- Usability: onboarding + feed + filters + explanation + responsive UI
- Effectiveness: personalized hybrid recommendation engine + feedback loop
- Real-world applicability: unified schema, extensible source adapters, scalable API design
- Uniqueness: cross-domain transfer scoring and mixed-domain ranking

## Demo Walkthrough

1. Open app and keep default `demo_user`.
2. Save profile with interests and custom domain weights.
3. Observe mixed-domain feed and explanation on each card.
4. Click like/save/dislike/hide on multiple cards.
5. Refresh feed and observe ranking changes.
6. Filter by domain and duration.

## Notes

- Data sources are seeded locally for deterministic demo behavior.
- The adapter pattern allows replacing JSON with live APIs later.
