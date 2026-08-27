"""Crew assembly.

Two workflows share one set of agents:

    Recipe   : detect ingredients -> filter by diet -> suggest recipes
    Analysis : analyse nutrition (single agent, single call)

Deliberately written WITHOUT the @CrewBase / @agent / @task
decorators. Plain classes are version-stable across CrewAI releases,
trivially unit-testable, and make the wiring visible instead of
magic. Template Method: the base class builds the parts, each
subclass only decides which parts run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from crewai import Agent, Crew, Process, Task

from src.llm import crew_llm
from src.models import NutrientAnalysisOutput, RecipeSuggestionOutput
from src.tools import (
    analyze_nutrition,
    extract_ingredients,
    filter_based_on_restrictions,
    filter_ingredients,
)

CONFIG_DIR = Path(__file__).parent / "config"


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class BaseNourishBotCrew:
    """Shared agents and tasks. Subclasses pick which ones to run."""

    def __init__(
        self,
        image_data: str,
        dietary_restrictions: Optional[str] = None,
    ) -> None:
        self.image_data = image_data
        self.dietary_restrictions = dietary_restrictions or ""
        self.agents_config = _load("agents.yaml")
        self.tasks_config = _load("tasks.yaml")
        # One LLM instance reused by every agent in this run.
        self.llm = crew_llm()

    # -- agents -------------------------------------------------
    def ingredient_detection_agent(self) -> Agent:
        return Agent(
            **self.agents_config["ingredient_detection_agent"],
            tools=[extract_ingredients, filter_ingredients],
            llm=self.llm,
            allow_delegation=False,
            max_iter=5,
            verbose=True,
        )

    def dietary_filtering_agent(self) -> Agent:
        return Agent(
            **self.agents_config["dietary_filtering_agent"],
            tools=[filter_based_on_restrictions],
            llm=self.llm,
            allow_delegation=False,   # nothing to delegate to; keeps it fast
            max_iter=4,
            verbose=True,
        )

    def nutrient_analysis_agent(self) -> Agent:
        return Agent(
            **self.agents_config["nutrient_analysis_agent"],
            tools=[analyze_nutrition],
            llm=self.llm,
            allow_delegation=False,
            max_iter=4,
            verbose=True,
        )

    def recipe_suggestion_agent(self) -> Agent:
        return Agent(
            **self.agents_config["recipe_suggestion_agent"],
            llm=self.llm,
            allow_delegation=False,
            max_iter=4,
            verbose=True,
        )

    # -- tasks --------------------------------------------------
    # Note: task chaining uses `context=[...]`, the supported CrewAI
    # API. `depends_on` / `input_data` are not real Task parameters
    # and break on current releases.
    def build_recipe_tasks(self):
        detect_agent = self.ingredient_detection_agent()
        filter_agent = self.dietary_filtering_agent()
        recipe_agent = self.recipe_suggestion_agent()

        detect = Task(
            **self.tasks_config["ingredient_detection_task"],
            agent=detect_agent,
        )
        filtered = Task(
            **self.tasks_config["dietary_filtering_task"],
            agent=filter_agent,
            context=[detect],
        )
        recipes = Task(
            **self.tasks_config["recipe_suggestion_task"],
            agent=recipe_agent,
            context=[filtered],
            output_json=RecipeSuggestionOutput,
        )
        return [detect, filtered, recipes], [
            detect_agent,
            filter_agent,
            recipe_agent,
        ]

    def build_analysis_tasks(self):
        agent = self.nutrient_analysis_agent()
        task = Task(
            **self.tasks_config["nutrient_analysis_task"],
            agent=agent,
            output_json=NutrientAnalysisOutput,
        )
        return [task], [agent]

    def crew(self) -> Crew:  # pragma: no cover - overridden
        raise NotImplementedError


class NourishBotRecipeCrew(BaseNourishBotCrew):
    """Fridge photo in, dietary-safe recipes out."""

    def crew(self) -> Crew:
        tasks, agents = self.build_recipe_tasks()
        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
        )


class NourishBotAnalysisCrew(BaseNourishBotCrew):
    """Plated meal in, nutrient breakdown out."""

    def crew(self) -> Crew:
        tasks, agents = self.build_analysis_tasks()
        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
        )
