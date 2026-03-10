from typing import Any, Dict, List, Tuple
import json
import os
from src.gemini_client import GeminiClient
from google.genai import types
from .schemas import SlideSpecs, ScriptOutput, AnimationScript


class Wrapper_PPT:
    """
    Wrapper for ppt slides

    Input:
        str: Course outline
    output:
        tuple: (list of specs, list of scripts, overall_tone) with strictly structured data.
    """

    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
        self.is_loaded = False
        self.save_history = os.getenv("SAVE_HISTORY", "False").lower() in (
            "true",
            "1",
            "yes",
        )

    def _log_to_history(self, event: str, content: Any):
        """Helper to log intermediate steps to history.txt if enabled."""
        if not self.save_history:
            return

        import datetime
        import os
        import json

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Format content for readability
        if isinstance(content, (dict, list)):
            try:
                formatted_content = json.dumps(content, indent=2, ensure_ascii=False)
            except Exception:
                formatted_content = str(content)
        else:
            formatted_content = str(content)

        log_entry = (
            f"\\n[{timestamp}] === {event} ===\\n{formatted_content}\\n{'-' * 40}\\n"
        )
        log_path = os.path.join(os.path.dirname(__file__), "history.txt")

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Failed to write history: {e}")

    def load(self):
        """Load underlying LLM client."""
        self.llm.load()
        self.is_loaded = True

    def generate_slide_specs(self, outline: str) -> Dict[str, Any]:
        """Generates Slide Specs from outline using structured output."""
        print("\n[Wrapper_PPT] Generating Slide Specs...")
        prompt_specs = f"""
            You are an expert Presentation Designer, JSON Data Architect, and educator. Your mission is to craft professional yet highly engaging and subtly humorous course presentations that keep learners wide awake. You will receive a comprehensive "Structured Course Storyboard" as input. Your task is to execute this blueprint by converting it into a single JSON output that represents the final, fully-furnished slide deck.

            Output requirements:

            * Output **only valid JSON** (no markdown formatting blocks like ```json, no extra text).
            * The JSON must be a single object with a key `"slides"` containing a list of slide objects.
            * Each slide object must include:
                * `"id"`: e.g. "slide1", "slide2"...
                * `"content"`: Object containing:
                    * `"text"`: List of text items, each with `"id"` (e.g. "text1") and `"content"`. (Extract from "Substance & Core Arguments"; keep text concise, high-density, presentation-ready, and occasionally witty).
                    * `"visuals"`: List of visual items, each with `"id"` (e.g. "visual1") and `"description"`. (Translate directly from "Visual & Layout Directives").
                    * `"layout"`: Descriptive natural-language explanation. (Map to the spatial arrangements defined in the storyboard).

            Content constraints:

            * **Slide Deck Structure MUST include:**
                * **Opening Slide (Slide 1):** A catchy, welcoming, and slightly humorous introduction to grab the audience's attention instantly.
                * **Course Overview Slide (Slide 2):** A clear, engaging agenda outlining the course architecture, what will be discussed, and the expected learning outcomes.
                * **Conclusion Slide (Final Slide):** A strong, memorable, and witty wrap-up to elegantly conclude the session.
            * Do **not** include any role labels such as “Author”, “Lead Researcher”, or similar credits anywhere, unless explicitly required by the provided input.
            * Strictly follow the "Pedagogical Pacing" mapped out in the storyboard while injecting your professional yet humorous teaching persona. Ensure complex concepts are properly distributed across the specified number of slides (e.g., following the 3-5 slides per sequence logic).
            * Convert the "On-Screen Visuals" into actual slide content.
            * Do not include speaker notes, overarching explanations, or any content outside the strict JSON structure.

            Structured Course Storyboard:
            {outline}
        """
        MODEL_NAME = "gemini-3-flash-preview"
        response_specs = self.llm.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt_specs,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=SlideSpecs
            ),
        )
        try:
            # Pydantic model response
            specs_obj = response_specs.parsed

            # Convert QuerySet-like structure back to Dict for ease of use in generate_scripts and returning
            specs = {}
            if specs_obj and specs_obj.slides:
                for item in specs_obj.slides:
                    specs[item.id] = item.content

            self._log_to_history("[Wrapper_PPT] generate_slide_specs", specs)

        except Exception as e:
            print(f"Error parsing specs: {e}")
            self._log_to_history("Error Parsing Specs", str(e))
            specs = {}
        return specs

    def generate_slide_scripts(self, specs: Dict[str, Any]) -> Dict[str, str]:
        """Generates Slide Scripts from specs using structured output."""
        print("\n[Wrapper_PPT] Generating Slide Scripts...")

        try:
            # Serialize specs for prompt
            specs_dict = {
                k: v.model_dump() if hasattr(v, "model_dump") else v
                for k, v in specs.items()
            }
        except:
            specs_dict = specs

        prompt_script = f"""
        You are a highly engaging, dynamic speaker giving a live lecture.
        Your task is to generate a spoken script for a presentation based on the provided slide specifications.

        ### INPUT DATA (Slide Specs):
        {json.dumps(specs_dict, indent=2, ensure_ascii=False)}

        ### INSTRUCTIONS:
        1. **Analyze the Input**: Review the visuals and content for each slide.
        2. **Draft the Live Script**: Create a highly conversational, natural spoken script for each slide, exactly as you would speak it on a live stage or in a dynamic classroom.
        - **Audience Engagement**: Use non-interactive rhetorical questions (questions that make the audience think without expecting a verbal answer), inclusive language ("we", "let's look at"), and conversational hooks (e.g., "Imagine...", "Have you ever noticed..."). Strictly avoid interactive prompts that wait for audience participation (e.g., do not ask for a show of hands).
        - **Visual Direction**: Explicitly and naturally direct the audience's attention to visual elements as if you are pointing at a screen (e.g., "Take a look at this chart right here...", "Notice this upward trend...", "If you focus on the left side...").
        - **Flow and Transitions**: Ensure smooth, logical transitions from one slide to the next. The script must read like a continuous, compelling narrative, not disconnected bullet points.
        - **Spoken Dynamics**: Emulate real human speech patterns. Use short sentences, natural filler words at the start of thoughts (e.g., "Now,", "So,", "But here's the catch..."), and create rhythm.

        ### OUTPUT FORMAT:
        * Output **only valid JSON** (no markdown formatting blocks like ```json, no extra text).
        * The JSON must be a single object containing:
            * `"scripts"`: List of objects, each having `"slide_id"` (e.g. "slide1") and `"script"` (string).
        """
        MODEL_NAME = "gemini-3-flash-preview"
        response_script = self.llm.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt_script,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=ScriptOutput
            ),
        )
        try:
            script_obj = response_script.parsed

            scripts_map = {}
            if script_obj and script_obj.scripts:
                for item in script_obj.scripts:
                    scripts_map[item.slide_id] = item.script

            self._log_to_history("[Wrapper_PPT] generate_slide_scripts", {"scripts_map": scripts_map})

        except Exception as e:
            print(f"Error parsing scripts: {e}")
            self._log_to_history("Error Parsing Scripts", str(e))
            scripts_map = {}

        return scripts_map

    def run(self, outline: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Generates Slide Specs and Slide Scripts using LLM (Structured Output).
        Returns: (specs_list, scripts_list)
        """
        assert self.is_loaded, "Call load() before run()"

        # Input validation
        if not isinstance(outline, str):
            raise TypeError(f"Expected outline to be a str, got {type(outline)}")

        if len(outline) == 0:
            raise ValueError("outline str cannot be empty")

        # 1. Generate Slide Specs
        # specs is Dict[str, SlideContent] (Pydantic objects)
        specs = self.generate_slide_specs(outline)

        # 2. Generate Slide Script
        scripts_map = self.generate_slide_scripts(specs)

        # 3. Combine into requested Tuple output
        specs_list = []
        scripts_list = []

        # Sort keys
        def sort_key(k):
            try:
                return int(k.replace("slide", ""))
            except:
                return 999

        sorted_keys = sorted(specs.keys(), key=sort_key)

        for key in sorted_keys:
            # Append spec
            # Convert Pydantic object to dict for final output
            content_obj = specs[key]
            content_dict = (
                content_obj.model_dump()
                if hasattr(content_obj, "model_dump")
                else content_obj
            )
            specs_list.append(content_dict)

            # Append corresponding script (or empty if missing)
            scripts_list.append(scripts_map.get(key, ""))

        return specs_list, scripts_list


class Wrapper_3B1B:
    """
    Wrapper for 3B1B slides

    Input:
        str: course outline
    output:
        list[dict[str, Any]]: slides structure
        list[str]: Scripts for each slide (one string per slide)
    """

    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
        self.is_loaded = False
        self.save_history = os.getenv("SAVE_HISTORY", "False").lower() in (
            "true",
            "1",
            "yes",
        )

    def _log_to_history(self, event: str, content: Any):
        """Helper to log intermediate steps to history.txt if enabled."""
        if not self.save_history:
            return

        import datetime
        import os
        import json

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Format content for readability
        if isinstance(content, (dict, list)):
            try:
                formatted_content = json.dumps(content, indent=2, ensure_ascii=False)
            except Exception:
                formatted_content = str(content)
        else:
            formatted_content = str(content)

        log_entry = (
            f"\\n[{timestamp}] === {event} ===\\n{formatted_content}\\n{'-' * 40}\\n"
        )
        log_path = os.path.join(os.path.dirname(__file__), "history.txt")

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Failed to write history: {e}")

    def load(self):
        """Load underlying LLM client."""
        self.llm.load()
        self.is_loaded = True

    def generate_animation_script(self, outline: str) -> Dict[str, Any]:
        """
        Generates the raw animation script scenes from the outline using LLM.
        """
        print("\n[Wrapper_3B1B] Generating Animation Script...")

        prompt = f"""
        You are an expert instructional designer and animation director, specializing in explaining complex concepts using "3Blue1Brown" style dynamic visualizations.

        Your task is to convert the provided **course outline** into a structured JSON animation script.

        ### Output Requirements
        * Output **only valid JSON** (no markdown, no extra text).
        * The JSON must contain a root key `"scenes"` which is a LIST of scene objects.
        * Each scene object must contain:
            * `"id"`: e.g. "scene1", "scene2"...
            * `"scene"`: Object containing exactly these three fields:
                1.  `"animation_description"`:
                    * **Goal:** Provide a highly detailed description of visual elements and their movements.
                    * **Dynamic Adaptation Rule:** Choose the visual style based on the content type:
                        * **Type A: Math/Geometry/Architecture (The "Hard" Stuff):**
                            * Define geometry explicitly. Use specific shapes (cubes, planes, grids).
                            * *Example:* "A 10x10 matrix grid [Q] slides over another grid [K]. Intersecting cells glow yellow to show dot-product calculation."
                        * **Type B: Concepts/History/Intro (The "Soft" Stuff):**
                            * Use **Visual Metaphors**, **Kinetic Typography**, or **Flowcharts**. Do NOT use static bullet points.
                            * *Example (Concept):* "The word 'Overfitting' appears in the center. It grows aggressively large and spiky, crowding out the surrounding data points, visualizing the concept of 'memorizing noise'."
                        * **Type C (Flow):** "A simple icon representing 'Raw Data' travels along a pipeline..."
                    * **General Visual Style:** Minimalist, high contrast, smooth motion (Manim engine style). Focus on *verbs*.

                2.  `"script"`:
                    * The exact **spoken word** lecture for this specific scene.
                    * **Tone:** Natural, conversational, enthusiastic.
                * **Synchronization:** The script must match the visual intensity. If the visual is complex, the script should slow down to explain. If the visual is a quick metaphor, the script can be punchy.

                3.  `"formula"`:
                    * The core mathematical content in **LaTeX format**.
                    * Return `null` if the scene is conceptual or historical.

        ### Constraints
        * Follow the logical flow of the course outline.
        * Ensure `"formula"` is valid LaTeX syntax.
        * Keep the JSON structure strict.

        ### Course Outline:
        {outline}
        """
        MODEL_NAME = "gemini-3-flash-preview"
        response = self.llm.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=AnimationScript
            ),
        )

        try:
            # Pydantic parsing
            script_obj = response.parsed

            # Convert list back to Dict map
            script_data = {}
            if script_obj and script_obj.scenes:
                for item in script_obj.scenes:
                    script_data[item.id] = item.scene

            self._log_to_history(
                "[Wrapper_3B1B] generate_animation_script", script_data
            )

        except Exception as e:
            print(f"Error parsing JSON: {e}")
            self._log_to_history("Error Parsing 3B1B Script", str(e))
            script_data = {}

        return script_data

    def run(self, outline: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Generates 3b1b-style animation script and splits it into visual specs and spoken scripts.

        Args:
            outline: The course outline markdown string.

        Returns:
            Tuple[List[Dict[str, Any]], List[str]]:
                - List[Dict]: List of dicts containing {"animation_description": ..., "formula": ...}
                - List[str]: List of spoken scripts corresponding to the scenes.
        """
        assert self.is_loaded, "Call load() before run()"

        # Input validation
        if not isinstance(outline, str):
            raise TypeError(f"Expected outline to be a str, got {type(outline)}")

        if len(outline) == 0:
            raise ValueError("outline str cannot be empty")

        # 1. Generate Raw Script Data (Dict of Scenes)
        script_data = self.generate_animation_script(outline)

        # 2. Process into requested Tuple format
        visuals_list = []
        scripts_list = []

        # Sort keys to ensure order (scene1, scene2...)
        def sort_key(k):
            try:
                return int(k.replace("scene", ""))
            except:
                return 999

        sorted_keys = sorted(script_data.keys(), key=sort_key)

        for key in sorted_keys:
            scene = script_data[key]  # AnimationScene object

            # Extract visual parts
            visual_entry = {
                "animation_description": scene.animation_description,
                "formula": scene.formula,
            }
            visuals_list.append(visual_entry)

            # Extract script part
            scripts_list.append(scene.script)

        return visuals_list, scripts_list
