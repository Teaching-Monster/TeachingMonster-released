from typing import Any, Dict, List, Tuple
from src.gemini_client import GeminiClient
from google.genai import types
import json


class DirectT2VModule:
    """
    Directly generates Slide Specs and Scripts from raw requirements in a single step.
    Mimics Wrapper_PPT behavior but skips the intermediate outline step.

    Input:
        requirement_prompt (str): Main requirements for the course.
        persona_prompt (str): Persona or voice to adopt.

    Output:
        Tuple[List[Dict[str, Any]], List[str]]:
            - List[Dict]: Slide specs (content, visuals, layout).
            - List[str]: Spoken scripts for each slide.
    """

    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
        self.is_loaded = False

    def load(self):
        """Load underlying LLM client."""
        self.llm.load()
        self.is_loaded = True

    def run(
        self,
        requirement_prompt: str,
        persona_prompt: str,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:

        assert self.is_loaded, "Call load() before run()"
        print("\n[DirectT2VModule] Generating Slide Specs & Scripts (One-Step)...")

        # Define Schema locally for this specific One-Step requirement
        from pydantic import BaseModel, Field

        class TextItem(BaseModel):
            id: str = Field(..., description="ID of the text block")
            content: str = Field(..., description="The content of the text block")

        class VisualItem(BaseModel):
            id: str = Field(..., description="ID of the visual item")
            description: str = Field(..., description="Description of the visual item")

        class CombinedSlideItem(BaseModel):
            id: str = Field(..., description="ID of the slide, e.g. slide1")
            text: List[TextItem] = Field(..., description="List of text items")
            visuals: List[VisualItem] = Field(..., description="List of visual items")
            layout: str = Field(..., description="Layout description")
            script: str = Field(
                ..., description="Spoken narration script for this slide"
            )

        class CombinedOutput(BaseModel):
            slides: List[CombinedSlideItem] = Field(..., description="List of slides")

        prompt = f"""
        Act as an Expert Instructional Designer and Slide Deck Creator.

        Your Goal: Create a complete slide deck presentation based on the User's Requirement.

        Student Persona:
        \"\"\"
        {persona_prompt}
        \"\"\"

        Course Requirement:
        \"\"\"
        {requirement_prompt}
        \"\"\"

        ### Instructions
        1. **Curriculum Design**: Plan a logical sequence of slides.
           - Start with a Title Slide.
           - structured body slides.
           - Summary slide.

        2. **Slide Design**: For EACH slide, design:
           - **Text**: Key bullet points (concise).
           - **Visuals**: Descriptions of images/diagrams.
           - **Layout**: How to arrange elements.
           - **Script**: Natural, engaging spoken narration.

        ### Output Format (Strict JSON)
        Return a single JSON object with a key `"slides"` containing a LIST of slide objects.
        """

        MODEL_NAME = "gemini-2.5-pro"

        response = self.llm.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=CombinedOutput
            ),
        )

        try:
            # Pydantic parsing
            output_obj = response.parsed

            specs_list = []
            scripts_list = []

            if output_obj and output_obj.slides:
                for item in output_obj.slides:
                    # Construct Spec part (matching Wrapper_PPT output structure)
                    # Wrapper_PPT specs are typically just the 'content' dict of the slide
                    spec_entry = {
                        "text": [t.model_dump() for t in item.text],
                        "visuals": [v.model_dump() for v in item.visuals],
                        "layout": item.layout,
                    }
                    specs_list.append(spec_entry)

                    # Construct Script part
                    scripts_list.append(item.script)

            return specs_list, scripts_list

        except Exception as e:
            print(f"[DirectT2VModule] Error parsing: {e}")
            return [], []


if __name__ == "__main__":
    # Test Block
    import os
    import sys
    import yaml
    from dotenv import load_dotenv

    # Path setup to import siblings
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    from src.config_schema import AppConfig

    load_dotenv()

    # Load config
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
            app_config = AppConfig(**config_data)

        client = GeminiClient(app_config.llm)
        module = DirectT2VModule(client)
        module.load()

        req = "Explain the concept of 'Eigenvectors' efficiently."
        persona = "A friendly math tutor for college freshmen."

        visuals, scripts = module.run(req, persona)

        print("\n=== Result ===")
        print(f"Generated {len(visuals)} slides.")

        import json

        print("\n--- Visual Specs (Full) ---")
        print(json.dumps(visuals, indent=2, ensure_ascii=False))

        print("\n--- Scripts (Full) ---")
        print(json.dumps(scripts, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Test failed: {e}")
