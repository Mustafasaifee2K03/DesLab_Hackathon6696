from __future__ import annotations

import re
from typing import Any, TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from .database import (
    content_language_breakdown,
    count_content_for_filters,
    get_all_content,
    insert_content_items,
)
from .live_sources import fetch_live_content
from .recommender import recommend_for_user


class AgentState(TypedDict, total=False):
    profile: dict[str, Any]
    domain: str | None
    limit: int
    max_duration: int | None
    enable_language_fallback: bool
    should_refresh_live: bool
    planning_note: str
    live_items_added: int
    items: list[dict[str, Any]]
    message: str
    diagnostics: dict[str, Any]


@tool
def inspect_inventory_tool(languages: list[str], domain: str | None = None) -> dict[str, Any]:
    """Inspect catalog coverage for selected languages and domain."""
    return {
        "matched_count": count_content_for_filters(languages=languages, domain=domain),
        "language_breakdown": content_language_breakdown(domain=domain),
        "domain": domain,
        "languages": languages,
    }


@tool
def refresh_live_sources_tool(
    domains: list[str],
    query_terms: list[str],
    languages: list[str],
    limit_per_domain: int = 8,
) -> dict[str, Any]:
    """Fetch live content from external providers and upsert into the catalog."""
    items = fetch_live_content(
        domains=domains,
        query_terms=query_terms,
        languages=languages,
        limit_per_domain=limit_per_domain,
    )
    if items:
        insert_content_items(items)
    return {"added": len(items)}


def _plan_node(state: AgentState) -> AgentState:
    profile = state.get("profile", {})
    domain = state.get("domain")
    limit = state.get("limit", 25)
    languages = profile.get("languages", [])

    inventory = inspect_inventory_tool.invoke({"languages": languages, "domain": domain})
    minimum_required = max(5, limit // 2)
    should_refresh_live = inventory["matched_count"] < minimum_required

    if should_refresh_live:
        note = (
            "Catalog coverage is thin for selected filters, so the agent will fetch live "
            "content before ranking recommendations."
        )
    else:
        note = "Catalog coverage is healthy; the agent will rank from local + previously synced content."

    return {
        "should_refresh_live": should_refresh_live,
        "planning_note": note,
        "diagnostics": {"inventory": inventory},
    }


def _refresh_live_node(state: AgentState) -> AgentState:
    profile = state.get("profile", {})
    domain = state.get("domain")

    domains = [domain] if domain else list(profile.get("domain_weights", {}).keys())
    demand_tokens = [
        token
        for token in re.split(r"\W+", profile.get("demand_text", "").lower())
        if len(token) > 2
    ]
    query_terms = (profile.get("interests", []) + demand_tokens)[:6] or ["trending"]
    languages = profile.get("languages", []) or ["en"]

    refresh_result = refresh_live_sources_tool.invoke(
        {
            "domains": domains,
            "query_terms": query_terms,
            "languages": languages,
            "limit_per_domain": 8,
        }
    )
    return {"live_items_added": int(refresh_result["added"])}


def _retrieve_node(state: AgentState) -> AgentState:
    profile = state.get("profile", {})
    domain = state.get("domain")
    limit = state.get("limit", 25)
    max_duration = state.get("max_duration")
    enable_language_fallback = state.get("enable_language_fallback", True)

    recs = recommend_for_user(profile, limit=limit, domain=domain)
    if max_duration is not None:
        recs = [item for item in recs if item["duration_minutes"] <= max_duration]

    message = ""
    fallback_applied = False

    if (
        enable_language_fallback
        and not recs
        and profile.get("languages")
        and "en" not in profile["languages"]
    ):
        fallback_profile = {
            **profile,
            "languages": list(dict.fromkeys(profile["languages"] + ["en"])),
        }
        fallback_recs = recommend_for_user(fallback_profile, limit=limit, domain=domain)
        if max_duration is not None:
            fallback_recs = [
                item for item in fallback_recs if item["duration_minutes"] <= max_duration
            ]
        if fallback_recs:
            recs = fallback_recs
            fallback_applied = True
            message = (
                "No recommendations matched your selected languages exactly. "
                "English content was included automatically."
            )

    if not recs and not message:
        message = (
            "No recommendations match the current filters. "
            "Try including English, increasing max duration, or refreshing live sources."
        )

    available_languages = sorted({item["language"] for item in get_all_content()})
    diagnostics = {
        "selected_languages": profile.get("languages", []),
        "available_languages": available_languages,
        "domain": domain,
        "max_duration": max_duration,
        "fallback_applied": fallback_applied,
        "agent_planning_note": state.get("planning_note", ""),
        "live_refresh_attempted": state.get("should_refresh_live", False),
        "live_items_added": state.get("live_items_added", 0),
        "agent_framework": "langchain-langgraph",
    }

    return {"items": recs, "message": message, "diagnostics": diagnostics}


def _route_after_plan(state: AgentState) -> str:
    return "refresh_live" if state.get("should_refresh_live") else "retrieve"


_builder = StateGraph(AgentState)
_builder.add_node("plan", _plan_node)
_builder.add_node("refresh_live", _refresh_live_node)
_builder.add_node("retrieve", _retrieve_node)
_builder.add_edge(START, "plan")
_builder.add_conditional_edges(
    "plan",
    _route_after_plan,
    {
        "refresh_live": "refresh_live",
        "retrieve": "retrieve",
    },
)
_builder.add_edge("refresh_live", "retrieve")
_builder.add_edge("retrieve", END)
AGENT_GRAPH = _builder.compile()


def run_recommendation_agent(
    profile: dict[str, Any],
    domain: str | None,
    limit: int,
    max_duration: int | None,
    enable_language_fallback: bool,
) -> dict[str, Any]:
    state: AgentState = {
        "profile": profile,
        "domain": domain,
        "limit": limit,
        "max_duration": max_duration,
        "enable_language_fallback": enable_language_fallback,
    }
    result = AGENT_GRAPH.invoke(state)

    items = result.get("items", [])
    return {
        "count": len(items),
        "items": items,
        "message": result.get("message", ""),
        "diagnostics": result.get("diagnostics", {}),
    }


def refresh_live_catalog(
    domains: list[str],
    query_terms: list[str],
    languages: list[str],
    limit_per_domain: int,
) -> int:
    result = refresh_live_sources_tool.invoke(
        {
            "domains": domains,
            "query_terms": query_terms,
            "languages": languages,
            "limit_per_domain": limit_per_domain,
        }
    )
    return int(result["added"])
