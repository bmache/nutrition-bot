"""Gradio front end for NourishBot.

Run:  python app.py    ->  http://127.0.0.1:7860
"""

from __future__ import annotations

import os
import tempfile
import traceback

import gradio as gr
from dotenv import load_dotenv

from src.crew import NourishBotAnalysisCrew, NourishBotRecipeCrew
from src.formatting import format_analysis_output, format_recipe_output, to_dict
from src.llm import ProviderError, active_provider, spec

load_dotenv()

RECIPE = "recipe"
ANALYSIS = "analysis"


def analyze_food(image, dietary_restrictions, workflow_type):
    """Entry point wired to the Analyze button."""
    if image is None:
        return "Please upload an image first."
    if workflow_type not in (RECIPE, ANALYSIS):
        return "Please choose a workflow: recipe or analysis."

    # Write to a temp file: the vision tools take a path, and a temp
    # file avoids clobbering a fixed name when two people click at once.
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        image_path = tmp.name
    image.convert("RGB").save(image_path, "JPEG")

    inputs = {
        "uploaded_image": image_path,
        "dietary_restrictions": dietary_restrictions or "none",
    }

    try:
        if workflow_type == RECIPE:
            crew_instance = NourishBotRecipeCrew(
                image_data=image_path,
                dietary_restrictions=dietary_restrictions,
            )
        else:
            crew_instance = NourishBotAnalysisCrew(image_data=image_path)

        result = crew_instance.crew().kickoff(inputs=inputs)
        data = to_dict(result)

        if workflow_type == RECIPE:
            return format_recipe_output(data)
        return format_analysis_output(data)

    except ProviderError as exc:
        return f"**Configuration problem**\n\n{exc}"
    except Exception as exc:  # noqa: BLE001 - surface it in the UI
        traceback.print_exc()
        return (
            f"**Something went wrong**\n\n`{type(exc).__name__}: {exc}`\n\n"
            "Check the terminal for the full trace. A rate limit, a missing "
            "API key, or a retired model name is the usual cause."
        )
    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass


def provider_banner() -> str:
    try:
        s = spec()
        return (
            f"Provider **{active_provider()}** &nbsp;|&nbsp; "
            f"vision `{s.vision_model}` &nbsp;|&nbsp; chat `{s.chat_model}`"
        )
    except ProviderError as exc:
        return f"**Not configured:** {exc}"


CSS = """
.header { text-align: center; }
footer { display: none !important; }
"""

with gr.Blocks(title="NourishBot") as demo:
    gr.Markdown("# NourishBot", elem_classes="header")
    gr.Markdown(
        "An AI nutrition coach built on a CrewAI multi-agent system. "
        "Runs on any LLM provider — swap it in `.env`.",
        elem_classes="header",
    )
    gr.Markdown(provider_banner(), elem_classes="header")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Input")
            image_input = gr.Image(type="pil", label="Food photo")
            dietary_input = gr.Textbox(
                label="Dietary restriction (optional)",
                placeholder="vegan, gluten-free, keto...",
            )
            workflow_radio = gr.Radio(
                choices=[RECIPE, ANALYSIS],
                value=ANALYSIS,
                label="Workflow",
                info=(
                    "recipe: photo of ingredients or your fridge. "
                    "analysis: photo of a plated meal."
                ),
            )
            submit_btn = gr.Button("Analyze", variant="primary")

        with gr.Column(scale=2):
            gr.Markdown("### Result")
            result_display = gr.Markdown(
                "Upload a photo and press **Analyze**."
            )

    submit_btn.click(
        fn=analyze_food,
        inputs=[image_input, dietary_input, workflow_radio],
        outputs=result_display,
    )

if __name__ == "__main__":
    # Gradio 6 moved theme/css from Blocks() to launch().
    demo.launch(
        theme=gr.themes.Soft(),
        css=CSS,
        server_name=os.getenv("HOST", "127.0.0.1"),
        server_port=int(os.getenv("PORT", "7860")),
    )
