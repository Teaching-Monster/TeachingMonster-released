# Outline & Wrapper Module

This folder contains the core logic for generating course scripts and storyboards within the **Teaching Monster** project. 
The latest design philosophy has evolved from simple "outline generation" into **"Structured Course Storyboards,"** emphasizing substantive teaching content (Substance) and pedagogical pacing.

## 📁 File Structure

| File | Description |
| --- | --- |
| `t2v_outline.py` | **Course Storyboard Generator**. Converts initial user requirements and Personas into high-density "Structured Course Storyboards," including visual layout instructions and pedagogical logic steps. |
| `wrapper.py` | **Content Converters (Wrappers)**. Receives the Storyboard and converts it for specific mediums:<br>- `Wrapper_PPT`: Generates slide specifications (Slide Specs) and corresponding scripts.<br>- `Wrapper_3B1B`: Generates Manim animation scripts and voiceovers. |
| `demo_flow.py` | **Integration Test Script**. Demonstrates the complete pipeline: `T2VOutlineModule` -> `Wrapper_PPT` / `Wrapper_3B1B`. Supports inputting requirements via CLI arguments. |
| `direct_t2v.py` | **One-Step Generator**. Directly generates slide specifications and scripts from requirements in a single step; intended for students to clone as a template model in the future. Output format is identical to `Wrapper_PPT`. |
| `schemas.py` | Defines Pydantic Schemas for output formats (e.g., `CourseBlueprint`, `SlideSpecs`, `AnimationScript`, etc.). |