"""Optional transcript editorial guidance; no rendering or schema changes."""


def selection_quality_guidance(mode, setting):
    """Unknown settings and non-transcript stages retain the legacy prompt."""
    if str(setting or "").strip().lower() != "v1":
        return ""
    if mode == "score":
        return """
EDITORIAL QUALITY REVIEW:
Rank concrete insights, surprising supported facts, useful demonstrations and
emotional turning points above generic topic discussion. Reward an identifiable
setup and payoff that can fit inside the configured clip duration. Emotion alone
does not replace context. Score every window as requested; do not invent claims
or treat an editorial score as a probability of views.
"""
    if mode == "detail":
        return """
EDITORIAL QUALITY REVIEW:
Before selecting each clip, identify its spoken opening, necessary context and
actual payoff in the supplied transcript. Choose one continuous source interval
that contains all three. Prefer a concrete insight, supported surprise, practical
answer or emotional turning point. A catchy overlay cannot rescue an incomplete
thought. Keep the setup when the strongest line depends on it; never reorder or
invent speech, and never shorten away a qualification or change the meaning.
Start at the earliest necessary opening phrase, avoiding disposable greetings;
finish after the answer or resolution. Keep every existing duration, word-boundary,
window, diversity and count constraint. In `why`, briefly name the concrete value
and payoff. Do not manufacture urgency, statistics, promises or controversy.
"""
    return ""
