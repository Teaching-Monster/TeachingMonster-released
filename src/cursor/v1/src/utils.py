import math
import wave
import contextlib
import subprocess


def run_cmd(cmd: str):
    print(f"Terminal: '{cmd}'")
    subprocess.run(cmd, shell=True, check=True)


def get_wav_duration(file_path: str) -> float:
    with contextlib.closing(wave.open(file_path,'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration = frames / float(rate)
        return duration


def roundup(value: float, decimals: int=0) -> float:
    multiplier = 10 ** decimals
    return math.ceil(value * multiplier) / multiplier
