"""Agent tools.

Each tool is split in two:

    pure function   -> the actual logic, unit-testable, no framework
    @tool wrapper   -> the thin CrewAI-facing adapter

That separation is why `tests/` can run with no API key and no
network at all.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from crewai.tools import tool

from src import prompts
from src.llm import ask_text, ask_vision

log = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------
def clean_ingredients(raw_ingredients: str) -> List[str]:
    """Normalise a messy model reply into a clean ingredient list.

    Handles comma lists, bulleted lines and numbered lines, which
    is what models actually return in practice.
    """
    if not raw_ingredients:
        return []

    # Split on commas AND newlines, then strip list markers.
    parts = re.split(r"[,\n]", raw_ingredients)
    cleaned: List[str] = []
    for part in parts:
        item = part.strip().lower()
        item = re.sub(r"^[-*•]\s*", "", item)        # bullet markers
        item = re.sub(r"^\d+[.)]\s*", "", item)      # 1. or 1)
        item = item.strip(" .:;")
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def apply_restrictions(
    ingredients: List[str],
    dietary_restrictions: Optional[str] = None,
) -> List[str]:
    """Drop ingredients that violate the restriction.

    No restriction means no LLM call -- the cheapest request is the
    one you never send.
    """
    if not dietary_restrictions or not str(dietary_restrictions).strip():
        return ingredients
    if not ingredients:
        return []

    prompt = prompts.DIETARY_FILTER.format(
        ingredients=", ".join(ingredients),
        restriction=dietary_restrictions,
    )
    reply = ask_text(prompt, max_tokens=200)
    return clean_ingredients(reply)


# ---------------------------------------------------------------
# CrewAI-facing wrappers
# ---------------------------------------------------------------
@tool("Extract ingredients")
def extract_ingredients(image_input: str) -> str:
    """Extract the food ingredients visible in an image.

    :param image_input: local file path or http(s) URL of the image.
    :return: comma-separated ingredient string.
    """
    log.info("Extracting ingredients from %s", image_input)
    return ask_vision(prompts.EXTRACT_INGREDIENTS, image_input, max_tokens=300)


@tool("Clean ingredient list")
def filter_ingredients(raw_ingredients: str) -> List[str]:
    """Normalise a raw ingredient string into a clean list.

    :param raw_ingredients: model output, comma or newline separated.
    :return: de-duplicated lowercase ingredient list.
    """
    return clean_ingredients(raw_ingredients)


@tool("Apply dietary restrictions")
def filter_based_on_restrictions(
    ingredients: List[str],
    dietary_restrictions: Optional[str] = None,
) -> List[str]:
    """Remove ingredients that break a dietary restriction.

    :param ingredients: candidate ingredients.
    :param dietary_restrictions: e.g. "vegan", "gluten-free", "keto".
    :return: only the compliant ingredients.
    """
    return apply_restrictions(ingredients, dietary_restrictions)


@tool("Analyze nutrition")
def analyze_nutrition(image_input: str) -> str:
    """Estimate calories and nutrients for the food in an image.

    :param image_input: local file path or http(s) URL of the image.
    :return: structured nutritional assessment as text.
    """
    log.info("Analysing nutrition for %s", image_input)
    return ask_vision(prompts.NUTRITION_ANALYSIS, image_input, max_tokens=900)
