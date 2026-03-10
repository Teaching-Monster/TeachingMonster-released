from typing import List, Optional
from pydantic import BaseModel, Field


class CourseBlueprint(BaseModel):
    course_topic: str = Field(
        ...,
        description="The main topic of the course. Inherit from input or extract from description.",
    )
    design_manifesto: str = Field(
        ...,
        description="Style rules, tone, and scope for the course. Defines what to teach and what to skip.",
    )
    learning_objectives: List[str] = Field(
        ..., description="Key learning outcomes for the student."
    )
    persona_scoping_analysis: str = Field(
        ...,
        description="Analysis of the student persona, including baseline knowledge, goals, constraints, and depth decisions.",
    )


class TextItem(BaseModel):
    id: str = Field(..., description="ID of the text block, e.g. text1")
    content: str = Field(..., description="The content of the text block")


class VisualItem(BaseModel):
    id: str = Field(..., description="ID of the visual item, e.g. visual1")
    description: str = Field(..., description="Description of the visual item")


class SlideContent(BaseModel):
    text: List[TextItem] = Field(..., description="List of text blocks on the slide")
    visuals: List[VisualItem] = Field(
        ..., description="List of visual items on the slide"
    )
    layout: str = Field(..., description="Descriptive layout instructions")


class SlideItem(BaseModel):
    id: str = Field(..., description="ID of the slide, e.g. slide1")
    content: SlideContent = Field(..., description="Content of the slide")


class SlideSpecs(BaseModel):
    slides: List[SlideItem] = Field(..., description="List of slides in the deck")


class ScriptItem(BaseModel):
    slide_id: str = Field(
        ..., description="ID of the slide this script constitutes, e.g. slide1"
    )
    script: str = Field(..., description="The spoken script text")


class ScriptOutput(BaseModel):
    scripts: List[ScriptItem] = Field(..., description="List of scripts per slide")


class AnimationScene(BaseModel):
    animation_description: str = Field(
        ..., description="Detailed visual description for 3B1B style animation"
    )
    script: str = Field(..., description="Spoken word lecture for this scene")
    formula: Optional[str] = Field(
        None, description="LaTeX formula if applicable, else null"
    )


class SceneItem(BaseModel):
    id: str = Field(..., description="ID of the scene, e.g. scene1")
    scene: AnimationScene = Field(..., description="Content of the scene")


class AnimationScript(BaseModel):
    scenes: List[SceneItem] = Field(..., description="List of animation scenes")
