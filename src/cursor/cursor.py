import os
import gc
import json
import torch

from PIL import Image
from pathlib import Path
from typing import List, Tuple
import librosa

from .v1.src.qwen import QwenVL
from .v1.src.ui_tars.ui_tars_model import UI_TARS
from .v1.src.plot_cursor import add_cursor_pointer
from .v1.src.video import merge_into_video
from .v1.src.utils import run_cmd, get_wav_duration, roundup


CURSOR_MOVE_TIME = 0.4
CURSOR_MOVE_FRAME = 10
FPS = CURSOR_MOVE_FRAME / CURSOR_MOVE_TIME 
THREADS = 16 # number of threads for video creation
# padding silence for transition between slides
LEFT_PAD_SEC = 1.0
RIGHT_PAD_SEC = 1.0
DEBUG = False


class CursorModule:
    def __init__(self, output_root = "./cursor_output", final_root = "./output", final_video_name = "merged_video.mp4"):
        self.output_root = output_root
        self.final_root = final_root
        self.final_video_name = final_video_name
        self.is_loaded = False

    def load(self):
        self.qwenvl = QwenVL(model_path="Qwen/Qwen3-VL-8B-Instruct")
        self.ui_tars = UI_TARS(model_path="ByteDance-Seed/UI-TARS-1.5-7B")
        self.is_loaded = True
    
    def grouping(self) -> List[List[str]]:
        """
        For each slide, divide all speech scripts into groups of sentences
        """
        # qwenvl = QwenVL(model_path="/home/user/model/Qwen/Qwen3-VL-8B-Instruct")
        grouped_scripts = []
        for image, script in zip(self.images, self.scripts):
            grouped_transcription = dict()

            image.save(f"{self.output_root}/tmp.png")
            
            transcription = script.replace(". ", ".\n").split("\n")

            analysis, group = self.qwenvl.grouping(img_path=f"{self.output_root}/tmp.png", transcription="\n".join([f"- {t}" for t in transcription]))
            
            if DEBUG: 
                print("-------------------")
                print(analysis)
                print(group)

            for t, gid in zip(transcription, group):
                if gid not in grouped_transcription:
                    grouped_transcription[gid] = t
                else:
                    grouped_transcription[gid] += " " + t
            
            grouped_scripts.append([grouped_t for grouped_t in grouped_transcription.values()])

        if DEBUG: 
            print("-------------------")
            print(json.dumps(grouped_scripts, ensure_ascii=False, indent=4))

        return grouped_scripts
    
    def grounding(self, grouped_scripts: List[List[str]]) -> List[List[Tuple[int, int]]]:
        """
        For each group of sentences in each slide, assign a point (x, y)
        so that the sentences in the group describe the point in the slide
        """
        # ui_tars = UI_TARS(model_path="/home/user/model/ByteDance-Seed/UI-TARS-1.5-7B")
        grouped_points = []
        for image, grouped_script in zip(self.images, grouped_scripts):
            image.save(f"{self.output_root}/tmp.png")
            grouped_points.append([self.ui_tars.inference(f"{self.output_root}/tmp.png", transcription=grouped_s) for grouped_s in grouped_script])

        if DEBUG: 
            print("-------------------")
            print(json.dumps(grouped_points, ensure_ascii=False, indent=4))

        return grouped_points
    
    def assign_period2image(self, grouped_scripts: List[List[str]], grouped_points: List[List[Tuple[int, int]]]) -> None:
        """
        Assign time period to (slide, point) pairs with cursor trajectory,
        and output image frames with cursor position and period 
        """
        word_cnt = 0
        prev_x, prev_y = -1, -1
        for page_i, (image, grouped_script, grouped_point, timestamp, audio_path) in enumerate(zip(self.images, grouped_scripts, grouped_points, self.timestamps, self.audio_paths), start=1):
            image.save(f"{self.output_root}/tmp.png")

            group_len = len(grouped_script)
            duration = roundup(get_wav_duration(audio_path), 2)

            start_time = 0.00 if word_cnt == 0 else timestamp[word_cnt][0]
            end_time = start_time
            
            for group_i, (script, (x, y)) in enumerate(zip(grouped_script, grouped_point), start=1):
                if prev_x != -1 and prev_y != -1:
                    vec_x = (x - prev_x) / CURSOR_MOVE_FRAME
                    vec_y = (y - prev_y) / CURSOR_MOVE_FRAME
                    for frame_i in range(CURSOR_MOVE_FRAME):
                        out = add_cursor_pointer(Image.open(f"{self.output_root}/tmp.png"), (round(prev_x + frame_i * vec_x), round(prev_y + frame_i * vec_y)), size=(image.size[0] // 50))
                        
                        end_time += CURSOR_MOVE_TIME / CURSOR_MOVE_FRAME
                        out.convert("RGB").save(f"{self.output_root}/slides/page{page_i}-{group_i}_{start_time:0>2.4f}-{end_time:0>2.4f}_moving.png")
                        start_time = end_time

                out = add_cursor_pointer(Image.open(f"{self.output_root}/tmp.png"), (x, y), size=(image.size[0] // 50))

                word_cnt += len(script.split(" "))
                end_time = duration if group_i == group_len else timestamp[word_cnt - 1][1]
                out.convert("RGB").save(f"{self.output_root}/slides/page{page_i}-{group_i}_{start_time:0>2.4f}-{end_time:0>2.4f}_stationary.png")
                start_time = end_time

                prev_x = x
                prev_y = y

            word_cnt = 0

    def make_video(self) -> None:
        """
        Merge all images and audio into video
        """
        # merge all frames for each page
        video_paths = []
        folder = Path(f"{self.output_root}/slides") # change this to your directory
        for page_i in range(1, len(self.images) + 1):
            prefix = f"page{page_i}"   # change this
            page_frames = [str(f) for f in folder.iterdir() if f.name.startswith(prefix)]

            frame_start_end = []
            for page_frame in page_frames:
                start, end = page_frame.split("_")[-2].split("-")
                frame_start_end.append((page_frame, float(start), float(end)))
            audio_path = self.audio_paths[page_i - 1]
            video_path = f"{self.output_root}/videos/page{page_i}.mp4"
            video_paths.append(video_path)

            merge_into_video(frame_start_end, audio_path, video_path, FPS, THREADS, LEFT_PAD_SEC, RIGHT_PAD_SEC)

        # merge all pages
        with open(f"{self.output_root}/merge.txt", "w") as fp:
             for page_i in range(1, len(self.images) + 1):
                fp.write(f"file ./videos/page{page_i}.mp4\n")
        
        run_cmd(f"ffmpeg -f concat -safe 0 -i {self.output_root}/merge.txt -c copy {self.final_root}/{self.final_video_name}")
        run_cmd(f"rm -f {self.output_root}/tmp.png {self.output_root}/merge.txt")

    def run(
        self,
        images: List[Image.Image],
        scripts: List[str],
        timestamps: List[List[Tuple[float, float]]],
        audio_paths: List[str],
    ) -> None:
        run_cmd(f"rm -rf {self.output_root}")
        run_cmd(f"rm -rf {self.final_root}")
        os.makedirs(f"{self.output_root}/slides", exist_ok=True)
        os.makedirs(f"{self.output_root}/videos", exist_ok=True)
        os.makedirs(self.final_root, exist_ok=True)

        self.images = images
        self.scripts = scripts
        self.timestamps = timestamps
        self.audio_paths = audio_paths

        grouped_scripts = self.grouping()
        grouped_points = self.grounding(grouped_scripts)
        return grouped_scripts, grouped_points
