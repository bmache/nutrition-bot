"""Formatting and output-coercion tests."""

import json
from types import SimpleNamespace

from src.formatting import format_analysis_output, format_recipe_output, to_dict


class TestToDict:
    def test_passes_through_a_dict(self):
        assert to_dict({"dish": "salad"}) == {"dish": "salad"}

    def test_reads_json_dict_attribute(self):
        obj = SimpleNamespace(json_dict={"dish": "curry"})
        assert to_dict(obj) == {"dish": "curry"}

    def test_parses_raw_json_string(self):
        obj = SimpleNamespace(raw=json.dumps({"dish": "soup"}))
        assert to_dict(obj) == {"dish": "soup"}

    def test_unparseable_output_degrades_to_raw(self):
        obj = SimpleNamespace(raw="not json at all")
        assert to_dict(obj) == {"_raw": "not json at all"}


class TestFormatting:
    def test_recipe_markdown(self):
        data = {
            "recipes": [
                {
                    "title": "Spinach Rice",
                    "ingredients": ["rice", "spinach"],
                    "instructions": "Cook it.",
                    "calorie_estimate": 320,
                }
            ]
        }
        out = format_recipe_output(data)
        assert "Spinach Rice" in out
        assert "- rice" in out
        assert "320 kcal" in out

    def test_recipe_empty(self):
        assert "No recipes" in format_recipe_output({"recipes": []})

    def test_analysis_markdown(self):
        data = {
            "dish": "Grilled salmon",
            "portion_size": "1 fillet",
            "estimated_calories": 410,
            "nutrients": {
                "protein": "35g",
                "vitamins": [{"name": "Vitamin D", "percentage_dv": "60%"}],
                "minerals": [{"name": "Calcium", "amount": "20mg"}],
            },
            "health_evaluation": "Well balanced.",
        }
        out = format_analysis_output(data)
        assert "Grilled salmon" in out
        assert "| Protein | 35g |" in out
        assert "Vitamin D" in out
        assert "Well balanced." in out

    def test_raw_fallback_is_shown_not_swallowed(self):
        out = format_analysis_output({"_raw": "model said something odd"})
        assert "model said something odd" in out
