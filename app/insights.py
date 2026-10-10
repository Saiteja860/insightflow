"""Aggregates feedback into insights and turns them into prioritized decisions."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from .analysis import THEMES

ACTION_LIBRARY = {
    "pricing": "Review pricing and billing transparency",
    "performance": "Prioritize performance optimization",
    "reliability": "Triage bugs and stability issues",
    "usability": "Improve UX and clarify the user flow",
    "customer_support": "Improve customer support response quality and speed",
    "delivery": "Investigate delivery and logistics delays",
    "features": "Evaluate requested features for the roadmap",
}


def summarize(feedback: list[dict]) -> dict:
    total = len(feedback)
    if total == 0:
        return {"total": 0, "avg_score": 0.0, "sentiment_counts": {}, "nps_like": None,
                "theme_stats": [], "high_urgency": 0}

    sentiments = Counter(f["sentiment"] for f in feedback)
    avg = round(mean(f["score"] for f in feedback), 3)
    promoters = sum(1 for f in feedback if f["score"] >= 0.5)
    detractors = sum(1 for f in feedback if f["score"] <= -0.5)
    nps_like = round(100 * (promoters - detractors) / total)

    theme_scores: dict[str, list[float]] = defaultdict(list)
    theme_urgency: dict[str, list[int]] = defaultdict(list)
    for f in feedback:
        for t in f["themes"]:
            theme_scores[t].append(f["score"])
            theme_urgency[t].append(f["urgency"])

    theme_stats = []
    for theme, scores in theme_scores.items():
        theme_stats.append({
            "theme": theme,
            "mentions": len(scores),
            "avg_score": round(mean(scores), 3),
            "avg_urgency": round(mean(theme_urgency[theme]), 2),
            "negative_share": round(sum(1 for s in scores if s < -0.15) / len(scores), 2),
        })
    theme_stats.sort(key=lambda x: (x["negative_share"] * x["mentions"], x["mentions"]), reverse=True)

    return {
        "total": total,
        "avg_score": avg,
        "sentiment_counts": dict(sentiments),
        "nps_like": nps_like,
        "theme_stats": theme_stats,
        "high_urgency": sum(1 for f in feedback if f["urgency"] >= 4),
    }


def generate_decisions(feedback: list[dict], min_mentions: int = 2) -> list[dict]:
    """Rule-based recommendations: flags themes with enough negative signal."""
    summary = summarize(feedback)
    decisions = []
    for stat in summary["theme_stats"]:
        if stat["mentions"] < min_mentions:
            continue
        if stat["avg_score"] >= -0.1 and stat["negative_share"] < 0.4:
            continue  # healthy theme, no action needed

        if stat["negative_share"] >= 0.6 or stat["avg_urgency"] >= 4:
            priority = "critical" if stat["avg_urgency"] >= 4 else "high"
        elif stat["negative_share"] >= 0.4:
            priority = "medium"
        else:
            priority = "low"

        decisions.append({
            "title": ACTION_LIBRARY.get(stat["theme"], f"Investigate issues related to {stat['theme']}"),
            "theme": stat["theme"],
            "priority": priority,
            "rationale": (
                f"{stat['mentions']} mentions, {int(stat['negative_share'] * 100)}% negative, "
                f"average urgency {stat['avg_urgency']}/5, average sentiment {stat['avg_score']:+.2f}."
            ),
        })

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    decisions.sort(key=lambda d: order[d["priority"]])
    return decisions


KNOWN_THEMES = list(THEMES.keys())
