import os
import sys
import yaml
import argparse
from dotenv import load_dotenv

# Ensure the project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.gemini_client import GeminiClient
from src.config_schema import AppConfig
from src.outline.t2v_outline import T2VOutlineModule
from src.outline.wrapper import Wrapper_PPT, Wrapper_3B1B

FLOWCHART = """
[輸入]
  ├─ 需求設定 (Requirement Prompt)
  └─ 角色設定 (Persona Prompt)
       │
       ▼
[階段一：生成大綱模型] (T2VOutlineModule)
  ├─ (1) 分析情境 ➔ 產生「結構化課程藍圖」(Course Blueprint)
  └─ (2) 擴充藍圖 ➔ 產生「Markdown 課程大綱」(Markdown Outline)
       │
       ▼
[階段二：腳本包裝與分流] (Wrappers)
       ├─────────────────────────────────┐
       ▼                                 ▼
[簡報包裝器] (Wrapper_PPT)         [動畫包裝器] (Wrapper_3B1B)
  │                                 │
  ├─ 提取標題與列點                   ├─ 設計連續的視覺場景
  ├─ 提取視覺要求                     ├─ 套用數學公式
  └─ 產生對應講稿                     └─ 產生串場口白腳本
       │                                 │
       ▼                                 ▼
[輸出結構化資料]                   [輸出結構化資料]
  (Slide Specs + Scripts)           (Animation Scenes + Scripts)
"""

def main():
    parser = argparse.ArgumentParser(
        description="Teaching Monster Outline Demo Flow\n\n流程圖:\n" + FLOWCHART,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--requirement", "-r", type=str, default=None,
        help="Main requirements for the course (e.g. topic to cover)."
    )
    parser.add_argument(
        "--persona", "-p", type=str, default=None,
        help="Persona or voice to adopt for the generated content."
    )
    args = parser.parse_args()

    # 1. Load Environment Variables (API Key, SAVE_HISTORY)
    load_dotenv()

    print("=== Teaching Monster Outline Demo Flow ===")

    # 2. Initialize Client and Modules
    try:
        # Load config
        config_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
        )
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
            app_config = AppConfig(**config_data)

        # Initialize client with config
        client = GeminiClient(app_config.llm)

        # Note: wrappers now check os.getenv("SAVE_HISTORY") automatically
        t2v_module = T2VOutlineModule(client)
        ppt_wrapper = Wrapper_PPT(client)
        anim_wrapper = Wrapper_3B1B(client)

        # Load models (actually just sets flag currently)
        t2v_module.load()
        ppt_wrapper.load()
        anim_wrapper.load()
        print("[System] Modules loaded successfully.")

    except Exception as e:
        print(f"[Error] Failed to initialize modules: {e}")
        return

    # 3. Define Input Data
    # Use command line arguments if provided, otherwise default to sample prompts
    requirement_prompt = args.requirement or """
    Create a short course about "The Physics of Black Holes".
    Focus on Event Horizon, Singularity, and Spaghettification.
    """

    persona_prompt = args.persona or """
    You are an enthusiastic science communicator explaining complex topics to high school students.
    Use analogies, keep it engaging, and avoid overly dense jargon.
    """

    print(f"\n[Input] Requirement: {requirement_prompt.strip()}")
    print(f"[Input] Persona: {persona_prompt.strip()}")

    # 4. Generate Course Outline using T2VOutlineModule
    print("\n--- Step 1: Generating Course Outline ---")
    try:
        outline_markdown = t2v_module.run(
            requirement_prompt=requirement_prompt, persona_prompt=persona_prompt
        )
        print("[Success] Outline generated.")
        # print(outline_markdown[:500] + "...") # Print snippet
    except Exception as e:
        print(f"[Error] Outline generation failed: {e}")
        return

    # 5. Generate PPT Specs and Scripts using Wrapper_PPT
    print("\n--- Step 2: Generating PPT Slides & Scripts ---")
    try:
        ppt_specs, ppt_scripts = ppt_wrapper.run(outline_markdown)
        print(f"[Success] Generated {len(ppt_specs)} slides.")
        print(
            f"Sample Slide 1 Title: {ppt_specs[0].get('title', 'No Title Found') if ppt_specs else 'N/A'}"
        )
    except Exception as e:
        print(f"[Error] PPT generation failed: {e}")

    # 6. Generate 3B1B Animation Script using Wrapper_3B1B
    print("\n--- Step 3: Generating 3B1B Animation Script ---")
    try:
        visuals, scripts = anim_wrapper.run(outline_markdown)
        print(f"[Success] Generated {len(visuals)} animation scenes.")
        print(
            f"Sample Scene 1 Description snippet: {visuals[0].get('animation_description', '')[:50] if visuals else 'N/A'}..."
        )
    except Exception as e:
        print(f"[Error] Animation generation failed: {e}")

    print("\n=== Demo Complete ===")
    if os.getenv("SAVE_HISTORY", "False").lower() in ("true", "1", "yes"):
        print("Check src/outline/history.txt for detailed logs.")
    else:
        print("History logging was disabled. Set SAVE_HISTORY=true to see details.")


if __name__ == "__main__":
    main()
