from __future__ import annotations

import hashlib
import html
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx

DEFAULT_TIMEOUT = 12.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _normalize_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _to_iso(value: str | None) -> str:
    if not value:
        return _now_iso()

    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).replace(tzinfo=None).isoformat(timespec="seconds")
    except ValueError:
        return _now_iso()


def _tokenize(*chunks: str) -> list[str]:
    text = " ".join(chunks).lower()
    words = re.findall(r"[a-zA-Z0-9]+", text)
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "about",
        "your",
        "you",
        "are",
        "new",
        "how",
        "why",
    }
    tags: list[str] = []
    for word in words:
        if len(word) < 3 or word in stop:
            continue
        if word not in tags:
            tags.append(word)
        if len(tags) == 6:
            break
    return tags or ["trending"]


def _build_item(
    domain: str,
    title: str,
    description: str,
    language: str,
    duration_minutes: int,
    source: str,
    url: str,
    creator: str,
    published_at: str,
    popularity: float,
    tags: list[str],
) -> dict[str, Any]:
    stable_id = hashlib.md5(f"{domain}|{url}".encode("utf-8")).hexdigest()[:14]
    return {
        "id": f"live_{domain}_{stable_id}",
        "domain": domain,
        "title": _normalize_text(title)[:180] or "Untitled",
        "description": _normalize_text(description)[:800] or "No description available.",
        "tags": tags,
        "language": language,
        "duration_minutes": max(1, min(300, int(duration_minutes))),
        "source": source,
        "url": url,
        "creator": _normalize_text(creator)[:120] or source,
        "published_at": _to_iso(published_at),
        "popularity": max(1.0, min(99.0, float(popularity))),
    }


def _language_query_hint(language: str, base_query: str) -> str:
    query = base_query.strip() or "trending"
    if language == "hi":
        return f"{query} hindi"
    if language == "ur":
        return f"{query} urdu"
    return query


def fetch_music_items(query: str, language: str, limit: int) -> list[dict[str, Any]]:
    term = _language_query_hint(language, query)
    url = "https://itunes.apple.com/search"
    params = {
        "term": term,
        "media": "music",
        "entity": "song",
        "limit": str(limit),
    }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for row in payload.get("results", []):
        track_name = row.get("trackName", "")
        artist = row.get("artistName", "")
        preview_url = row.get("trackViewUrl") or row.get("collectionViewUrl")
        if not preview_url or not track_name:
            continue

        millis = row.get("trackTimeMillis") or 180000
        duration_minutes = max(1, int(round(millis / 60000)))
        lang = language if language in {"hi", "ur"} else "en"

        items.append(
            _build_item(
                domain="music",
                title=track_name,
                description=row.get("primaryGenreName", "") + " track discovered from iTunes Search.",
                language=lang,
                duration_minutes=duration_minutes,
                source="iTunes Music",
                url=preview_url,
                creator=artist,
                published_at=row.get("releaseDate", ""),
                popularity=70 + (len(items) % 20),
                tags=_tokenize(track_name, artist, row.get("primaryGenreName", ""), term),
            )
        )

    return items


def fetch_podcast_items(query: str, language: str, limit: int) -> list[dict[str, Any]]:
    term = _language_query_hint(language, query)
    url = "https://itunes.apple.com/search"
    params = {
        "term": term,
        "media": "podcast",
        "limit": str(limit),
    }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for row in payload.get("results", []):
        collection_name = row.get("collectionName", "")
        creator = row.get("artistName", "")
        item_url = row.get("collectionViewUrl")
        if not item_url or not collection_name:
            continue

        feed_url = row.get("feedUrl", "")
        description = row.get("genres", ["podcast"])
        lang = language if language in {"hi", "ur"} else "en"

        items.append(
            _build_item(
                domain="podcasts",
                title=collection_name,
                description=f"Podcast discovered from iTunes. Feed: {feed_url}" if feed_url else "Podcast discovered from iTunes.",
                language=lang,
                duration_minutes=35,
                source="iTunes Podcasts",
                url=item_url,
                creator=creator,
                published_at=row.get("releaseDate", ""),
                popularity=68 + (len(items) % 22),
                tags=_tokenize(collection_name, creator, " ".join(description), term),
            )
        )

    return items


def fetch_movie_items(query: str, language: str, limit: int) -> list[dict[str, Any]]:
    term = quote_plus(_language_query_hint(language, query))
    url = f"https://api.tvmaze.com/search/shows?q={term}"

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url)
            response.raise_for_status()
            rows = response.json()
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        show = row.get("show", {})
        title = show.get("name", "")
        show_url = show.get("officialSite") or show.get("url")
        if not title or not show_url:
            continue

        summary = re.sub(r"<[^>]+>", "", show.get("summary", ""))
        runtime = show.get("runtime") or 45
        lang = (show.get("language") or "en").lower()
        lang = "hi" if lang.startswith("hindi") else ("ur" if lang.startswith("urdu") else "en")

        items.append(
            _build_item(
                domain="movies",
                title=title,
                description=summary or "Show discovered from TVMaze.",
                language=lang,
                duration_minutes=runtime,
                source="TVMaze",
                url=show_url,
                creator=(show.get("network") or {}).get("name", "TVMaze"),
                published_at=show.get("premiered", ""),
                popularity=65 + (len(items) % 24),
                tags=_tokenize(title, summary, " ".join(show.get("genres", [])), query),
            )
        )

    return items


def fetch_video_items(query: str, language: str, limit: int) -> list[dict[str, Any]]:
    search_query = _language_query_hint(language, query)
    params: dict[str, Any] = {
        "q": f"title:({search_query}) AND mediatype:(movies)",
        "fl[]": ["identifier", "title", "description", "creator", "publicdate", "downloads"],
        "rows": str(limit),
        "page": "1",
        "output": "json",
    }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get("https://archive.org/advancedsearch.php", params=params)
            response.raise_for_status()
            docs = response.json().get("response", {}).get("docs", [])
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for row in docs:
        identifier = row.get("identifier")
        title = row.get("title")
        if not identifier or not title:
            continue

        url = f"https://archive.org/details/{identifier}"
        description = row.get("description", "")
        creator = row.get("creator", "Internet Archive")
        downloads = row.get("downloads", 0) or 0
        popularity = 50 + min(45, int(downloads) // 500)

        items.append(
            _build_item(
                domain="videos",
                title=title,
                description=description,
                language=language if language in {"hi", "ur"} else "en",
                duration_minutes=20,
                source="Internet Archive",
                url=url,
                creator=str(creator),
                published_at=row.get("publicdate", ""),
                popularity=popularity,
                tags=_tokenize(title, description, str(creator), search_query),
            )
        )

    return items


def fetch_news_items(query: str, language: str, limit: int) -> list[dict[str, Any]]:
    q = _language_query_hint(language, query)
    feed_url = f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        feed = feedparser.parse(feed_url)
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for entry in feed.entries[:limit]:
        title = str(entry.get("title", ""))
        link = str(entry.get("link", ""))
        if not title or not link:
            continue

        published = str(entry.get("published", ""))
        published_iso = _now_iso()
        parsed_struct = entry.get("published_parsed")
        if published and isinstance(parsed_struct, time.struct_time):
            try:
                parsed_dt = datetime(*parsed_struct[:6])
                published_iso = parsed_dt.isoformat(timespec="seconds")
            except Exception:
                published_iso = _now_iso()

        source = "Google News"
        if "source" in entry and isinstance(entry.source, dict):
            source = entry.source.get("title", "Google News")

        summary = str(entry.get("summary", "News article discovered from Google News RSS."))

        items.append(
            _build_item(
                domain="news",
                title=title,
                description=summary,
                language=language if language in {"hi", "ur"} else "en",
                duration_minutes=6,
                source=source,
                url=link,
                creator=source,
                published_at=published_iso,
                popularity=72 + (len(items) % 20),
                tags=_tokenize(title, summary, q),
            )
        )

    return items


LIVE_FETCHERS = {
    "videos": fetch_video_items,
    "music": fetch_music_items,
    "podcasts": fetch_podcast_items,
    "movies": fetch_movie_items,
    "news": fetch_news_items,
}


def fetch_live_content(
    domains: list[str],
    query_terms: list[str],
    languages: list[str],
    limit_per_domain: int = 8,
) -> list[dict[str, Any]]:
    dedupe: dict[str, dict[str, Any]] = {}
    effective_queries = query_terms[:3] or ["trending"]
    effective_languages = languages or ["en"]

    for domain in domains:
        fetcher = LIVE_FETCHERS.get(domain)
        if not fetcher:
            continue

        for language in effective_languages:
            for term in effective_queries:
                for item in fetcher(term, language, max(3, limit_per_domain // len(effective_queries))):
                    dedupe[item["id"]] = item

    return list(dedupe.values())
