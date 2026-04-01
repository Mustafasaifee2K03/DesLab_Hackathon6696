from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import exp
import re

from .database import (
    get_all_content,
    get_feedback,
    get_feedback_with_content,
    get_hidden_or_disliked_ids,
    get_saved_ids,
)


TERM_ALIASES: dict[str, set[str]] = {
    "tech": {"technology", "ai", "software", "engineering", "startup"},
    "technology": {"tech", "ai", "software", "engineering"},
    "ai": {"artificial", "intelligence", "technology", "startup"},
    "startup": {"founder", "business", "technology", "product"},
    "coding": {"programming", "software", "engineering", "developer"},
    "romance": {"love", "romantic", "relationship"},
    "fitness": {"workout", "training", "health", "wellness"},
}


def _expand_term(term: str) -> set[str]:
    expanded = {term}
    expanded.update(TERM_ALIASES.get(term, set()))
    return expanded


def _norm_terms(values: list[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        normalized = value.lower().replace("/", " ").replace("-", " ")
        for token in re.findall(r"[a-zA-Z0-9]+", normalized):
            token = token.strip()
            if token:
                terms.update(_expand_term(token))
    return terms


def _item_terms(item: dict) -> set[str]:
    raw = " ".join(
        [
            item.get("title", ""),
            item.get("description", ""),
            " ".join(item.get("tags", [])),
            item.get("domain", ""),
        ]
    ).lower()
    tokens = re.findall(r"[a-zA-Z0-9]+", raw)
    terms: set[str] = set()
    for token in tokens:
        if len(token) < 3:
            continue
        terms.update(_expand_term(token))
    return terms


def _soft_overlap(profile_terms: set[str], item_terms: set[str]) -> float:
    if not profile_terms:
        return 0.0
    matched = 0
    for term in profile_terms:
        if term in item_terms:
            matched += 1
            continue
        for item_term in item_terms:
            if term.startswith(item_term) or item_term.startswith(term):
                matched += 1
                break
    return matched / max(1, len(profile_terms))


def _freshness_score(published_at: str) -> float:
    dt = datetime.fromisoformat(published_at)
    days_old = max(0, (datetime.utcnow() - dt).days)
    return float(exp(-days_old / 45))


def _build_affinity(feedback_rows: list[dict]) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    global_tag_affinity: dict[str, float] = defaultdict(float)
    per_domain: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    action_weight = {
        "like": 1.0,
        "save": 0.8,
        "view": 0.3,
        "dislike": -0.9,
        "hide": -1.0,
    }

    for row in feedback_rows:
        weight = action_weight.get(row["action"], 0)
        for tag in row["tags"]:
            t = tag.lower()
            global_tag_affinity[t] += weight
            per_domain[row["domain"]][t] += weight

    return global_tag_affinity, per_domain


def _score_item(
    item: dict,
    profile: dict,
    global_affinity: dict[str, float],
    domain_affinity: dict[str, dict[str, float]],
) -> tuple[float, str, float]:
    interest_terms = _norm_terms(profile["interests"])
    mood_terms = _norm_terms(profile["moods"])
    item_terms = _item_terms(item)
    item_tags = {tag.lower() for tag in item["tags"]}

    interest_overlap = _soft_overlap(interest_terms, item_terms)
    mood_overlap = _soft_overlap(mood_terms, item_terms)
    relevance = 0.85 * interest_overlap + 0.15 * mood_overlap

    domain_pref = profile["domain_weights"].get(item["domain"], 20) / 100
    freshness = _freshness_score(item["published_at"])
    popularity = item["popularity"] / 100

    affinity_raw = sum(global_affinity.get(tag, 0.0) for tag in item_tags)
    affinity_score = max(0.0, min(1.0, (affinity_raw + 3) / 6))

    cross_domain_raw = 0.0
    for domain, tags in domain_affinity.items():
        if domain == item["domain"]:
            continue
        cross_domain_raw += sum(tags.get(tag, 0.0) for tag in item_tags)
    cross_domain = max(0.0, min(1.0, (cross_domain_raw + 2) / 5))

    score = (
        0.50 * relevance
        + 0.20 * domain_pref
        + 0.12 * freshness
        + 0.08 * popularity
        + 0.06 * cross_domain
        + 0.04 * affinity_score
    )

    if interest_terms and relevance < 0.05 and affinity_score < 0.45:
        score -= 0.22

    score = max(0.0, min(1.0, score))

    reasons: list[str] = []
    if relevance > 0.2:
        matched = [term for term in interest_terms if term in item_terms][:2]
        reasons.append(f"matches your interests in {', '.join(matched)}")
    if cross_domain > 0.5:
        reasons.append("bridges topics you liked in other formats")
    if freshness > 0.6:
        reasons.append("is fresh and recently published")
    if popularity > 0.75:
        reasons.append("is trending right now")
    if not reasons:
        reasons.append("fits your current preference blend")

    return score, "Recommended because it " + " and ".join(reasons) + ".", relevance


def _diversified_rerank(
    items: list[dict], domain_weights: dict[str, int], limit: int
) -> list[dict]:
    positive_domains = [d for d, w in domain_weights.items() if w > 0]
    if positive_domains:
        items = [item for item in items if item["domain"] in positive_domains]

    buckets: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        buckets[item["domain"]].append(item)

    domain_order = sorted(domain_weights.keys(), key=lambda d: domain_weights[d], reverse=True)
    picks: list[dict] = []

    # Weighted round-robin to avoid one domain dominating the feed.
    while len(picks) < limit:
        progressed = False
        for domain in domain_order:
            weight = domain_weights.get(domain, 0)
            if weight <= 0:
                quota = 0
            else:
                quota = max(1, weight // 20)
            for _ in range(quota):
                if buckets[domain] and len(picks) < limit:
                    picks.append(buckets[domain].pop(0))
                    progressed = True
        if not progressed:
            break

    return picks


def recommend_for_user(profile: dict, limit: int = 25, domain: str | None = None) -> list[dict]:
    all_content = get_all_content()
    hidden_or_disliked = get_hidden_or_disliked_ids(profile["user_id"])
    saved_ids = get_saved_ids(profile["user_id"])
    feedback_rows = get_feedback_with_content(profile["user_id"])
    global_affinity, domain_affinity = _build_affinity(feedback_rows)

    scored: list[dict] = []
    for item in all_content:
        if item["id"] in hidden_or_disliked:
            continue
        if domain and item["domain"] != domain:
            continue
        if profile["languages"] and item["language"] not in profile["languages"]:
            continue

        score, reason, relevance = _score_item(item, profile, global_affinity, domain_affinity)
        if profile.get("interests") and relevance < 0.08 and profile["domain_weights"].get(item["domain"], 0) < 80:
            continue

        scored.append(
            {
                **item,
                "score": round(score, 4),
                "reason": reason,
                "saved": item["id"] in saved_ids,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    if domain:
        return scored[:limit]

    return _diversified_rerank(scored, profile["domain_weights"], limit)


def feedback_summary(user_id: str) -> dict[str, int]:
    rows = get_feedback(user_id)
    summary: dict[str, int] = defaultdict(int)
    for row in rows:
        summary[row["action"]] += 1
    return dict(summary)
