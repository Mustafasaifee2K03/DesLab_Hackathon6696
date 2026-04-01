# UniSphere User Guide

This guide explains how to use UniSphere effectively and how to troubleshoot missing recommendations.

UniSphere now runs an agentic recommendation workflow using LangChain + LangGraph:

- Plan: checks profile + catalog coverage
- Refresh: fetches live content if coverage is weak
- Retrieve: ranks and explains recommendations

## 1. Start the app

Run:

```bash
./run.sh
```

Open:

- http://localhost:8000

## 2. Create your profile

In Personalization Setup:

1. Enter User ID and Name.
2. Add Interests as comma-separated values.
3. Add Moods as comma-separated values.
4. Select one or more Languages.
5. Set Domain Weights (videos, music, podcasts, movies, news).
6. Click Save Profile.
7. Click Load Recommendations.

## 3. Understand filters

In Feed Controls:

- Domain: choose one domain (or All).
- Max Duration: content longer than this value is excluded.
- Result Limit: number of recommendations requested.

Click Refresh Feed after changing filters.

## 3.1 Sync live content

Use the `Sync Live Sources` button in Feed Controls when you want fresh content from external platforms.

It calls live providers (music, podcasts, movies, videos, and news) and stores normalized records in your catalog.

## 4. Why music may appear empty (and what now happens)

If you choose a language with little or no content (for example Hindi/Urdu in demo data), music feed may become empty.

Current system behavior:

- UniSphere now automatically includes English fallback content when selected languages return no matches.
- A message appears above the feed telling you fallback was applied.

If you still see no results:

1. Increase Max Duration.
2. Switch Domain to All to verify profile behavior.
3. Ensure at least one language is selected.
4. Reduce very narrow filters.
5. Use `Sync Live Sources` and then `Refresh Feed`.

## 5. Feedback controls

Each card has:

- Like: boosts similar items.
- Save: keeps item in your saved preference signal.
- Dislike: suppresses similar items.
- Hide: removes that item from future feed.

Feedback updates future ranking in real time.

## 6. Recommendation quality tips

For best personalized results:

1. Use 3 to 8 relevant interests.
2. Keep domain weights balanced unless you want a specialized feed.
3. Give at least 10 to 20 feedback actions for stronger personalization.

## 7. Known demo-data limitation

The included seed dataset is mostly English. This is expected for the hackathon demo package.

Production expansion path:

- Add multilingual source adapters.
- Increase per-domain catalog size.
- Use locale-specific ranking weights.

## 8. Quick troubleshooting

- No feed loaded: save profile first.
- Empty feed after filters: broaden domain, increase duration, keep English selected.
- Unexpected recommendations: provide more likes/dislikes to refine model.
- Server not reachable: rerun `./run.sh` and ensure port 8000 is free.
