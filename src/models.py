"""Pydantic schemas for task output.

Agents return prose by default. Binding each task to a schema turns
that prose into validated JSON, which is what lets the UI render
tables instead of dumping raw model text.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class Recipe(BaseModel):
    title: str = Field(..., description="Recipe title")
    ingredients: List[str] = Field(..., description="Ingredients used")
    instructions: str = Field(..., description="Step-by-step method")
    calorie_estimate: int = Field(..., description="Calories per serving")


class RecipeSuggestionOutput(BaseModel):
    recipes: List[Recipe] = Field(default_factory=list)


class VitaminInfo(BaseModel):
    name: str = Field(..., description="Vitamin name, e.g. Vitamin C")
    percentage_dv: str = Field(..., description="Percent of daily value")


class MineralInfo(BaseModel):
    name: str = Field(..., description="Mineral name, e.g. Calcium")
    amount: str = Field(..., description="Amount with unit, e.g. 100mg")


class NutrientBreakdown(BaseModel):
    protein: Optional[str] = None
    carbohydrates: Optional[str] = None
    fats: Optional[str] = None
    vitamins: List[VitaminInfo] = Field(default_factory=list)
    minerals: List[MineralInfo] = Field(default_factory=list)


class NutrientAnalysisOutput(BaseModel):
    dish: Optional[str] = None
    portion_size: Optional[str] = None
    estimated_calories: Optional[int] = None
    nutrients: NutrientBreakdown = Field(default_factory=NutrientBreakdown)
    health_evaluation: Optional[str] = None
