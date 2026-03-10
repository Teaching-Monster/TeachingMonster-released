from typing import List, Tuple
from moviepy.video.VideoClip import ImageClip
from moviepy.audio.AudioClip import concatenate_audioclips
from moviepy.audio.io.AudioFileClip import AudioFileClip, AudioClip
from moviepy.video.compositing.concatenate import concatenate_videoclips


def merge_into_video(
    frame_start_end: List[Tuple[str, float, float]], 
    audio_path: str, output_path: str, fps: float, threads: int=4,
    left_pad_sec :float=1.0, right_pad_sec :float=1.0, 
) -> None:
    n_frame = len(frame_start_end)
    frame_start_end.sort(key=lambda x: x[1])
    
    # 1️⃣ Create Video Clips from Images
    clips = []
    for frame_i, (img_file, start, end) in enumerate(frame_start_end):
        duration = end - start
        if frame_i == 0:
            clip = (
                ImageClip(img_file)
                .set_duration(duration + left_pad_sec)
                .set_start(start)
            )
        elif frame_i == n_frame:
            clip = (
                ImageClip(img_file)
                .set_duration(duration + right_pad_sec)
                .set_start(start + left_pad_sec)
            )
        else:
            clip = (
                ImageClip(img_file)                # load the image
                .set_duration(duration)           # set how long it stays
                .set_start(start + left_pad_sec)  # set its timestamp in final timeline
            )
        clips.append(clip)

    # 2️⃣ Combine (concatenate) clips into one video
    # Note: In MoviePy, concatenation assumes clips are in order and follow one another.
    # If you want exact timing from start times, CompositeVideoClip may be used instead.
    video_clip = concatenate_videoclips(clips, method="chain")

    # 3️⃣ Load audio and attach it
    audio_clip = AudioFileClip(audio_path)
    # 產生 silence clip
    left_silence = AudioClip(lambda t: 0, duration=left_pad_sec, fps=audio_clip.fps)
    right_silence = AudioClip(lambda t: 0, duration=right_pad_sec, fps=audio_clip.fps)
    # 拼接：silence + audio + silence
    audio_clip = concatenate_audioclips([left_silence, audio_clip, right_silence])
    video_set_audio = video_clip.set_audio(audio_clip)

    # 4️⃣ Write out the final video file
    video_set_audio.write_videofile(
        output_path,
        fps=fps,
        threads=threads,
        preset='medium',
        codec="libx264", # standard MP4 codec
    )
