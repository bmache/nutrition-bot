"""Unit tests for the pure logic. No API key, no network."""

from unittest.mock import patch

from src.tools import apply_restrictions, clean_ingredients


class TestCleanIngredients:
    def test_comma_separated(self):
        assert clean_ingredients("Tomato, Spinach, Chicken") == [
            "tomato",
            "spinach",
            "chicken",
        ]

    def test_bulleted_lines(self):
        raw = "- Tomato\n- Spinach\n* Garlic"
        assert clean_ingredients(raw) == ["tomato", "spinach", "garlic"]

    def test_numbered_lines(self):
        raw = "1. Tomato\n2) Spinach"
        assert clean_ingredients(raw) == ["tomato", "spinach"]

    def test_deduplicates(self):
        assert clean_ingredients("Tomato, tomato, TOMATO") == ["tomato"]

    def test_empty_input(self):
        assert clean_ingredients("") == []
        assert clean_ingredients("  ,  , ") == []


class TestApplyRestrictions:
    def test_no_restriction_skips_the_llm(self):
        items = ["chicken", "rice"]
        with patch("src.tools.ask_text") as mocked:
            assert apply_restrictions(items, None) == items
            assert apply_restrictions(items, "") == items
            mocked.assert_not_called()

    def test_empty_ingredients_short_circuits(self):
        with patch("src.tools.ask_text") as mocked:
            assert apply_restrictions([], "vegan") == []
            mocked.assert_not_called()

    def test_filters_via_llm(self):
        with patch("src.tools.ask_text", return_value="rice, spinach"):
            result = apply_restrictions(["chicken", "rice", "spinach"], "vegan")
        assert result == ["rice", "spinach"]
