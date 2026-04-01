# UniSphere User Guide

This guide explains the updated 3-page dynamic flow.

UniSphere runs an agentic recommendation workflow using LangChain + LangGraph:

- Plan: check current catalog coverage for your profile
- Refresh: fetch live content when coverage is low
- Retrieve: rank and explain recommendations

## 1. Start the app

Run:

```bash
./run.sh
```

Open:

- http://localhost:8000

## 2. Step 1: Interests + Demand

On the first page:

1. Enter User ID and Name.
2. Select relevant interests from the list.
3. Enter demand_text (specific content requirement in your own words).
4. Click Continue to Preferences.

## 3. Step 2: Preferences

On the second page:

1. Select language(s).
2. Set domain weights (videos, music, podcasts, movies, news).
3. Click Generate Live Recommendations.

## 4. Step 3: Feed

On the feed page:

- Domain: choose one domain (or All).
- Max Duration: content longer than this value is excluded.
- Result Limit: number of recommendations requested.

Click Refresh Results after changing filters.

## 5. Feedback controls

Each card has:

- Like: boosts similar items.
- Save: keeps item in your saved preference signal.
- Dislike: suppresses similar items.
- Hide: removes that item from future feed.

Feedback updates future ranking in real time.

## 6. Recommendation quality tips

For best personalized results:

1. Select focused interests that truly match your intent.
2. Write demand_text with specifics (topic + format + recency + language preference).
3. Keep domain weights aligned with your actual preference.
4. Give feedback on at least 10 items to improve personalization.

## 7. Dynamic content note

The app now uses live dynamic sources at runtime. It no longer depends on local static seed catalogs for feed generation.

## 8. Quick troubleshooting

- Cannot continue from step 1: choose at least one interest and provide detailed demand text.
- Empty feed: broaden domain, increase max duration, or include English.
- Low relevance: refine demand_text with clear keywords (for example: "latest AI engineering podcasts and startup analysis").
- Links do not open: ensure network access and disable popup blocking for localhost.
- Server not reachable: rerun `./run.sh` and check port 8000 availability.
