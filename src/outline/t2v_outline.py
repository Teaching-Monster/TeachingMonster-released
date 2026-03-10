from typing import Any, Dict
import os
from google.genai import types

from src.gemini_client import GeminiClient
from .schemas import CourseBlueprint


class T2VOutlineModule:
    """
    Outline generator.

    Input:
        requirement_prompt (str):
            Main requirements for slides (course detail or questions)
        persona_prompt (str):
            Persona or voice to adopt.

    Output:
        str: **Course** outlines, one string includes all the content description.
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

    def analyze_context(
        self, requirement_prompt: str, persona_prompt: str
    ) -> Dict[str, Any]:
        """
        Analyzes the requirement (description) and persona to create a course blueprint.

        Args:
            requirement_prompt: The user's course description or topic requirement.
            persona_prompt: Description of the student persona.

        Returns:
            Dict with keys:
                - "blueprint": CourseBlueprint object
                - "course_topic": str
        """

        prompt = f"""
        You are an expert curriculum designer.

        Student Persona:
        \"\"\"
        {persona_prompt}
        \"\"\"

        Course Design Requirement (must be followed strictly):
        \"\"\"
        {requirement_prompt}
        \"\"\"

        Analyze the persona and the provided Requirement.

        1) Extract the main **Course Topic** from the Requirement.

        2) Output a **Design Manifesto** and **Learning Objectives** that align perfectly with the user's Requirement.
        - The manifesto MUST explicitly state that the course structure must follow the provided Requirement.
        - Scope and depth MUST be decided based on the persona: what to emphasize, what to cover lightly, and what not to teach deeply (with brief rationale).

        Lecture-first / low-interaction constraint:
        - Assume this is primarily a lecture-based, information-delivery course (e.g., online learning resources).
        - Avoid relying on interactive, in-person, or high-touch assignments (e.g., group work, live facilitation, workshops).
        - If practice is necessary, prefer low-interaction formats: optional self-check questions, reflection prompts, templates, checklists, worked examples, or lightweight quizzes.

        Planning-only constraint:
        - Do NOT write detailed lesson content, step-by-step teaching scripts, or long examples.
        - Provide teaching direction and intent only.

        Required Output Format (use exact headings):

        A) Course Topic
        - (1 concise sentence)

        B) Persona Scoping Analysis
        - Baseline & prior knowledge assumptions
        - Goals & success definition (persona-specific)
        - Constraints (time/tools/language/context)
        - Depth decisions (Teach / Teach lightly / Not deep) + brief rationale

        C) Design Manifesto
        - Bullet points that define the course design principles.
        - Must include: “This course structure must follow the provided Requirement.”
        - Must reflect lecture-first, low-interaction delivery.

        D) Learning Objectives
        - Each objective: “By the end, the learner can…”
        - Include a mix of essential and optional objectives, with persona-based depth decisions (Core vs Optional vs De-emphasize).
        """
        MODEL_NAME = "gemini-3-flash-preview"
        response = self.llm.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=CourseBlueprint
            ),
        )

        blueprint = response.parsed

        self._log_to_history(
            "[T2VOutlineModule] analyze_context (Blueprint)",
            blueprint.model_dump() if hasattr(blueprint, "model_dump") else blueprint,
        )

        return {"blueprint": blueprint, "course_topic": blueprint.course_topic}

    def create_module_outline(
        self, blueprint: CourseBlueprint, course_topic: str
    ) -> str:
        """
        Generates the final Course Outline in Markdown.

        Args:
            blueprint: CourseBlueprint object.
            course_topic: The course topic string.

        Returns:
            str: The generated markdown outline.
        """
        print("\n[Wrapper: create_module_outline]")

        prompt = f"""
            Act as an expert Instructional Designer and Presentation Storyboarder. Based on the provided CourseBlueprint, produce a comprehensive **"Structured Course Storyboard"**.

            STRICT OUTPUT RULES
            - Do not output any conversational filler. Start immediately with the course title.
            - Output clean Markdown only.

            DELIVERY CONSTRAINT (Storyboard Execution)
            - Design an execution blueprint that bridges the gap between the provided conceptual inputs (Course Topic, Design Manifesto, Learning Objectives, Persona Scoping Analysis) and the final slide deck.
            - Substance over Outline: Provide concrete derivation steps, core arguments, and rigorous domain knowledge. Do not just list topics like a menu; serve the "main course."
            - Pedagogical Pacing: Deliberately dismantle large, complex concepts into logical sequences spanning 3 to 5 slides to optimize information density and learner comprehension.
            - Visual & Layout Directives: Explicitly map out the specific visual elements and spatial arrangements required for each knowledge point.

            COURSE LENGTH (Do not hardcode)
            - Decide the total number of modules/sequences based on topic complexity + persona fit implied by the blueprint inputs.
            - Keep the structure minimal-but-sufficient to achieve the Learning Objectives under the Design Manifesto.
            - Think of this as the detailed construction blueprint (wiring, plumbing) that turns the conceptual framework (your inputs) into a fully furnished home (the final slides).

            INPUTS
            **Course Topic:** {course_topic}
            **Design Manifesto:** {blueprint.design_manifesto}
            **Learning Objectives:** {blueprint.learning_objectives}
            **Persona Scoping Analysis:** {blueprint.persona_scoping_analysis}

            Follow this exact structure and headings:

            # {course_topic}: Structured Course Storyboard

            ## 1. Executive Summary
            - Storyboard purpose and audience fit (tie to persona scoping)
            - Outcomes summary (tie to learning objectives)
            - Execution strategy statement (highlighting substance, pacing, and visual translation)

            ## 2. Pedagogical & Visual Foundations
            - 3–6 concise bullets: specific pacing strategy + visual design rationale
            - Must be consistent with Design Manifesto (do not add conflicting principles)

            ## 3. Storyboard Sequence Overview (Table)
            Provide a Markdown table with columns:
            - Sequence #
            - Sequence title
            - Primary objectives (reference objective numbers)
            - Slide count estimate (e.g., 3-5 slides)
            - Primary visual theme / core layout approach

            ## 4. Detailed Sequence Breakdown (Deep dive)
            For each sequence/module, include:
            - Sequence title
            - Why it exists (maps to persona needs + requirement)
            - Substance & Core Arguments: Concrete domain knowledge, derivations, and actual teaching content (no vague summaries).
            - Pedagogical Pacing (Slide-by-Slide Arc): Explicitly outline the logic step-by-step across 3-5 distinct slides.
            - Visual & Layout Directives: Specify required spatial arrangements, diagrams, and text-to-visual ratios for these slides.
            - Included elements: Specify what content belongs in "Speaker Notes" vs. "On-Screen Visuals".
            - What we intentionally do NOT visualize or expand on (1–3 bullets) + brief reason.

            ## 5. Common Misconceptions & Visual Correction Logic
            - List likely learner misconceptions (persona-informed)
            - For each: misconception → visual/pedagogical correction principle → how the storyboard specifically addresses it (sequence reference)

            ## 6. Conclusion
            - Narrative progression recap
            - Handoff instructions for the final slide design / production phase

            Quality Guardrails
            - Ensure every sequence maps to at least one Learning Objective.
            - The output MUST contain actionable substance, not just placeholder outlines.
            - Maintain an authoritative tone; concise, high-density writing.
        """

        MODEL_NAME = "gemini-3-flash-preview"
        response = self.llm.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="text/plain",
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        self._log_to_history("[T2VOutlineModule] create_module_outline", response.text)

        return response.text

    def run(
        self,
        requirement_prompt: str,
        persona_prompt: str,
    ) -> str:
        assert self.is_loaded, "Call load() before run()"

        # 1. Analyze context to get blueprint and topic
        print("[T2VOutlineModule] Analyzing context...")
        context_data = self.analyze_context(requirement_prompt, persona_prompt)
        blueprint = context_data["blueprint"]
        course_topic = context_data["course_topic"]
        print(f"[T2VOutlineModule] Blueprint created for topic: {course_topic}")

        # 2. Generate the full module outline
        print("[T2VOutlineModule] Generating module outline...")
        outline = self.create_module_outline(blueprint, course_topic)
        print("[T2VOutlineModule] Outline generation complete.")

        return outline
