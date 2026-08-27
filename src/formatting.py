"""Turn crew output into Markdown for the UI.

Kept separate from app.py so it can be tested without importing
Gradio or touching the network.
"""

from __future__ import annotations

import json
from typing import Any

DISCLAIMER = (
    "\n\n---\n\n*Estimates generated from a photograph by an AI model. "
    "They are not medical or dietary advice. Check ingredients yourself "
    "for allergens, and consult a qualified professional for anything "
    "that matters.*"
)


def to_dict(crew_output: Any) -> dict:
    """Coerce a CrewOutput into a plain dict, defensively.

    CrewAI has moved this around between releases, so try every known
    shape before giving up. Never raises -- a failed parse degrades
    to raw text rather than a stack trace in the UI.
    """
    if isinstance(crew_output, dict):
        return crew_output

    for attr in ("json_dict", "to_dict"):
        value = getattr(crew_output, attr, None)
        if callable(value):
            try:
                result = value()
                if isinstance(result, dict):
                    return result
            except Exception:  # noqa: BLE001 - best effort by design
                pass
        elif isinstance(value, dict):
            return value

    pydantic_obj = getattr(crew_output, "pydantic", None)
    if pydantic_obj is not None and hasattr(pydantic_obj, "model_dump"):
        return pydantic_obj.model_dump()

    raw = getattr(crew_output, "raw", None) or str(crew_output)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (TypeError, ValueError):
        pass

    return {"_raw": raw}


def _raw_fallback(data: dict, heading: str):
    """If parsing failed, show the model text instead of an error."""
    if "_raw" in data:
        return f"{heading}\n\n{data['_raw']}{DISCLAIMER}"
    return None


def format_recipe_output(data: dict) -> str:
    heading = "## Recipe ideas"
    if (fallback := _raw_fallback(data, heading)) is not None:
        return fallback

    recipes = data.get("recipes") or []
    if not recipes:
        return f"{heading}\n\nNo recipes could be generated. Try a clearer photo."

    out = [heading, ""]
    for idx, recipe in enumerate(recipes, 1):
        out.append(f"### {idx}. {recipe.get('title', 'Untitled')}")
        out.append("")
        out.append("**Ingredients**")
        out.append("")
        for item in recipe.get("ingredients", []):
            out.append(f"- {item}")
        out.append("")
        out.append("**Method**")
        out.append("")
        out.append(str(recipe.get("instructions", "")))
        out.append("")
        if (cal := recipe.get("calorie_estimate")) is not None:
            out.append(f"**Approx. calories per serving:** {cal} kcal")
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out) + DISCLAIMER


def format_analysis_output(data: dict) -> str:
    heading = "## Nutritional analysis"
    if (fallback := _raw_fallback(data, heading)) is not None:
        return fallback

    out = [heading, ""]

    if dish := data.get("dish"):
        out.append(f"**Dish:** {dish}")
        out.append("")
    if portion := data.get("portion_size"):
        out.append(f"**Assumed portion:** {portion}")
        out.append("")
    if calories := data.get("estimated_calories"):
        out.append(f"**Estimated calories:** {calories} kcal")
        out.append("")

    nutrients = data.get("nutrients") or {}
    macros = [
        (name.capitalize(), nutrients.get(name))
        for name in ("protein", "carbohydrates", "fats")
    ]
    macros = [(k, v) for k, v in macros if v]
    if macros:
        out.append("**Macronutrients**")
        out.append("")
        out.append("| Nutrient | Amount |")
        out.append("|---|---|")
        for name, value in macros:
            out.append(f"| {name} | {value} |")
        out.append("")

    if vitamins := nutrients.get("vitamins"):
        out.append("**Vitamins**")
        out.append("")
        out.append("| Vitamin | %DV |")
        out.append("|---|---|")
        for v in vitamins:
            out.append(f"| {v.get('name', 'n/a')} | {v.get('percentage_dv', 'n/a')} |")
        out.append("")

    if minerals := nutrients.get("minerals"):
        out.append("**Minerals**")
        out.append("")
        out.append("| Mineral | Amount |")
        out.append("|---|---|")
        for m in minerals:
            out.append(f"| {m.get('name', 'n/a')} | {m.get('amount', 'n/a')} |")
        out.append("")

    if verdict := data.get("health_evaluation"):
        out.append("**Health evaluation**")
        out.append("")
        out.append(verdict)

    return "\n".join(out) + DISCLAIMER
