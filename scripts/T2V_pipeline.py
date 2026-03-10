"""
VideoGenerationPipeline Module

This module implements a monolithic orchestration layer for generating educational
or presentation-style videos from a simple text prompt. It follows a strictly 
sequential "waterfall" architecture:

Data Flow:
1. User Prompt -> [OutlineModule] -> Structured JSON Outline
2. Outline -> [Wrapper] -> Slide Content & Voiceover Scripts
3. Slide Content -> [SlidesModule] -> Static Images (.jpg)
4. Scripts -> [TTSModule] -> Audio files (.mp3) + Word-level Timestamps
5. Images/Scripts/Timestamps -> [CursorModule] -> X/Y Coordinate Trajectories
6. All Assets -> [MoviePy Renderer] -> Final MP4

Key Components:
- LLM Client: Handles all generative text tasks.
- AppConfig: Manages paths, slide types (PPT vs 3B1B), and model parameters.
- MoviePy: Used for the final compositing of layers (Slide + Cursor + Audio).
"""

import argparse
import os
from typing import List

import yaml
import numpy as np
from PIL import Image
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
import json

from src import *

class VideoGenerationPipeline:
    """
    End-to-end pipeline with built-in renderer.

    Attributes:
        app_config (AppConfig): Configuration object for directories and module settings.
        llm_client: The backend LLM provider (e.g., Gemini, OpenAI).
        video_output_path (str): Final destination of the rendered MP4.
        fps (int): Frames per second for the output video (default: 15).
    """

    def __init__(
        self,
        llm_client,
        app_config: AppConfig,
        output_video_name: str = "final_video.mp4",
        final_video_dir: str = "./output",
    ):
        self.app_config = app_config
        self.llm_client = llm_client

        # --- Directory Management ---
        # Prioritizes explicit arguments over config file defaults
        output_config = app_config.output
        tmp_dir = (output_config.tmp_dir if output_config else None) or "./tmp_pipeline"
        os.makedirs(tmp_dir, exist_ok=True)

        final_dir = (
            final_video_dir
            or (output_config.final_video_dir if output_config else None)
            or tmp_dir
        )

        # Define sub-directories for intermediate assets
        self.slides_output_root = os.path.join(tmp_dir, "slides")
        self.tts_output_root = os.path.join(tmp_dir, "tts")
        self.cursor_output_root = os.path.join(tmp_dir, "cursor")

        self.video_output_path = os.path.join(final_dir, output_video_name)
        os.makedirs(final_dir, exist_ok=True)

        self.fps = 15

        # --- Module Initialization ---
        self.outline_module = T2VOutlineModule(llm_client)

        # Support for different slide engines (Standard PPT vs Manim-style 3B1B)
        if app_config.pipeline.slides_type == "PPT":
            self.slides_module = SlidesModule_PPT(
                llm_client, config=self.app_config.ppt, output_root=self.slides_output_root
            )
            self.wrapper = Wrapper_PPT(llm_client)
        else:
            self.slides_module = SlidesModule_3B1B(
                llm_client, output_root=self.slides_output_root
            )
            self.wrapper = Wrapper_3B1B(llm_client)
            
        self.tts_module = TTSModule(output_root=self.tts_output_root)
        self.cursor_module = CursorModule(
            output_root=self.cursor_output_root, 
            final_root=final_dir, 
            final_video_name=output_video_name
        )

    def load(self):
        """
        Initializes heavy resources (e.g., local ML models, network connections).
        Must be called after __init__ and before run().
        """
        self.outline_module.load()
        self.wrapper.load()
        self.slides_module.load()
        self.tts_module.load()
        self.cursor_module.load()

    def run(
        self,
        requirement_prompt: str,
        persona_prompt: str,
    ) -> dict:
        """
        Orchestrates the full generation process from text to MP4.

        Args:
            requirement_prompt: The core topic or instruction.
            persona_prompt: The tone/style of the presentation (e.g., "Academic").

        Returns:
            dict: A dictionary containing paths and data for all generated assets.
        """

        # =============================
        # Step 1: Content Planning
        # Generates a high-level structure of the video.
        # =============================
        outlines: List[str] = self.outline_module.run(
            requirement_prompt=requirement_prompt,
            persona_prompt=persona_prompt,
        )
        json.dump(outlines, open("tmp/outlines.json", "w+", encoding="utf-8"), ensure_ascii=False, indent=4)

        # =============================
        # Step 2: Content Interpretation
        # Breaks outlines into slide-by-slide structure and narration scripts.
        # =============================
        slides_struct, scripts = self.wrapper.run(outlines)
        json.dump(slides_struct, open("tmp/slides_struct.json", "w+", encoding="utf-8"), ensure_ascii=False, indent=4)
        json.dump(scripts, open("tmp/scripts.json", "w+", encoding="utf-8"), ensure_ascii=False, indent=4)

        # =============================
        # Step 3: Visual Asset Generation
        # Renders the slides into image files.
        # =============================
        slides_folder = self.slides_module.run(slides_struct)

        slide_images: List[Image.Image] = []
        slide_image_paths: List[str] = []
        for idx in range(1, len(slides_struct) + 1):
            img_path = os.path.join(slides_folder, f"{idx}.jpg")
            slide_image_paths.append(img_path)
            slide_images.append(Image.open(img_path))

        # =============================
        # Step 4: Audio Synthesis
        # Generates narration and precise word-level timings for cursor syncing.
        # =============================
        audio_folder, word_timings = self.tts_module.run(scripts)
        json.dump(word_timings, open("tmp/word_timings.json", "w+", encoding="utf-8"), ensure_ascii=False, indent=4)

        audio_paths: List[str] = [
            os.path.join(audio_folder, f"{i}.mp3") for i in range(1, len(scripts) + 1)
        ]

        # =============================
        # Step 5: Animation Planning
        # Calculates where the "laser pointer" (cursor) should move based on keywords.
        # =============================
        cursor_script, cursor_data = self.cursor_module.run(
            images=slide_images,
            scripts=scripts,
            timestamps=word_timings,
            audio_paths=audio_paths,
        )

        # =============================
        # Step 6: Built-in Video Rendering (MoviePy)
        # Composites visual and audio layers into the final video file.
        # =============================
        video_clips = []

        for slide_idx in range(len(slide_image_paths)):
            img_path = slide_image_paths[slide_idx]
            audio_path = audio_paths[slide_idx]
            
            # Load audio to determine the exact duration of this slide segment
            audio_clip = AudioFileClip(audio_path).set_fps(44100)
            slide_duration = audio_clip.duration

            # Create the background slide layer
            base_clip = ImageClip(img_path).set_duration(slide_duration)

            # Create the cursor layer (a 20x20 red square/dot)
            cursor_img = np.zeros((20, 20, 3), dtype=np.uint8)
            cursor_img[:, :] = (255, 0, 0) # Red dot
            cursor_clip = ImageClip(cursor_img).set_duration(slide_duration)

            # --- Cursor Path Calculation ---
            # Handles smooth interpolation between different focus points on a slide.
            CURSOR_MOVE_TIME = 0.4
            CURSOR_MOVE_FRAME = 10
            prev_x, prev_y = None, None
            word_cnt = 0
            grouped_script = cursor_script[slide_idx]
            grouped_point = cursor_data[slide_idx]
            timestamps = word_timings[slide_idx]

            positions = [] # List of (time, (x, y)) tuples

            for group_idx, (script, (x, y)) in enumerate(zip(grouped_script, grouped_point)):
                start_time = 0.0 if word_cnt == 0 else timestamps[word_cnt][0]

                # If moving from a previous point, interpolate coordinates for smoothness
                if prev_x is not None and prev_y is not None:
                    vec_x = (x - prev_x) / CURSOR_MOVE_FRAME
                    vec_y = (y - prev_y) / CURSOR_MOVE_FRAME

                    for frame_i in range(CURSOR_MOVE_FRAME):
                        t = start_time + frame_i * (CURSOR_MOVE_TIME / CURSOR_MOVE_FRAME)
                        pos_x = int(prev_x + frame_i * vec_x)
                        pos_y = int(prev_y + frame_i * vec_y)
                        positions.append((t, (pos_x, pos_y)))

                    start_time += CURSOR_MOVE_TIME

                # Calculate end-time for this specific word group
                word_cnt += len(script.split())
                prev_x, prev_y = x, y
                end_t = timestamps[word_cnt - 1][1] if word_cnt - 1 < len(timestamps) else slide_duration
                positions.append((end_t, (x, y)))

            # Function to interpolate the cursor's position at any given timestamp 't'
            def make_position_fn(positions):
                def pos_fn(t):
                    for i in range(len(positions) - 1):
                        if positions[i][0] <= t < positions[i+1][0]:
                            return positions[i][1]
                    return positions[-1][1]
                return pos_fn

            # Overlay cursor on slide and attach audio
            cursor_clip = cursor_clip.set_position(make_position_fn(positions))
            video_clips.append(CompositeVideoClip([base_clip, cursor_clip]).set_audio(audio_clip))

        # Merge all individual slide clips and encode to MP4
        final_video = concatenate_videoclips(video_clips, method="compose")
        final_video.write_videofile(
            self.video_output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
        )

        # Cleanup memory/file handles
        final_video.close()
        for clip in video_clips:
            clip.close()
            if hasattr(clip, "audio") and clip.audio:
                clip.audio.close()

        # =============================
        # Step 7: Return bundle
        # =============================
        return {
            "outlines": outlines,
            "slides_struct": slides_struct,
            "slides_folder": slides_folder,
            "scripts": scripts,
            "audio_folder": audio_folder,
            "word_timings": word_timings,
            "cursor_data": cursor_data,
            "final_video_path": self.video_output_path,
        }


# -----------------------------
# Example Usage
# -----------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run pipeline with prompts and video path"
    )

    parser.add_argument(
        "-r",
        "--requirement-prompt",
        type=str,
        default="Explain machine learning basics",
        help="Main requirement prompt (e.g., 'Explain machine learning basics')",
    )

    parser.add_argument(
        "-p",
        "--persona-prompt",
        type=str,
        default="Friendly instructor",
        help="Persona prompt (e.g., 'Friendly instructor')",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config/default.yaml",
        help="Generation config (e.g., config/default.yaml)",
    )

    parser.add_argument(
        "-o",
        "--output-video-name",
        type=str,
        default="final_video.mp4",
        help="Output video file name (e.g., final_video.mp4)",
    )

    parser.add_argument(
        "-d",
        "--final-video-dir",
        type=str,
        default=None,
        help="Directory for final video output (overrides config if provided)",
    )

    args = parser.parse_args()

    print("\n=== Input ===")
    print(f"Requirement prompt: {args.requirement_prompt}")
    print(f"Persona prompt: {args.persona_prompt}")
    print(f"Config path: {args.config}")

    print("\n=== Loading ===")
    with open(args.config, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        config = AppConfig(**data)

    client = GeminiClient(config.llm)

    pipeline = VideoGenerationPipeline(
        llm_client=client,
        app_config=config,
        output_video_name=args.output_video_name,
        final_video_dir=args.final_video_dir,
    )

    pipeline.load()

    print("\n=== Run ===")
    assets = pipeline.run(
        requirement_prompt=args.requirement_prompt,
        persona_prompt=args.persona_prompt,
    )

    print("\n=== Final Output ===")
    print("Final video:", assets["final_video_path"])
