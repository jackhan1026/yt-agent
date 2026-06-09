#!/usr/bin/env python3
"""Shared utilities for radio generation scripts."""

import os
import time
import asyncio
import subprocess
import requests
import edge_tts


def call_claude(prompt: str, model: str = "sonnet", retries: int = 3, timeout: int = 300) -> str:
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    last_err = None
    for attempt in range(1, retries + 1):
        if attempt > 1:
            print(f"  [retry {attempt}/{retries}] waiting 15s before retry…")
            time.sleep(15)
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", model, "--output-format", "text", "--tools", "none"],
                capture_output=True, text=True, env=env, timeout=timeout, stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                last_err = RuntimeError(f"claude -p failed:\n{result.stderr}")
                print(f"  [attempt {attempt}] non-zero exit: {result.stderr[:200]}")
                continue
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            last_err = RuntimeError(f"claude -p timed out after {timeout}s (attempt {attempt}/{retries})")
            print(f"  [attempt {attempt}] timed out after {timeout}s")
    raise last_err


def fetch_weather(city: str) -> dict | None:
    try:
        r = requests.get(
            f"https://wttr.in/{city}?format=j1",
            headers={"User-Agent": "curl/8.0"}, timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        c, w = data["current_condition"][0], data["weather"][0]
        return {
            "temp_c":       c["temp_C"],
            "temp_f":       c["temp_F"],
            "feels_like_c": c["FeelsLikeC"],
            "desc":         c["weatherDesc"][0]["value"],
            "humidity":     c["humidity"],
            "wind_kmh":     c["windspeedKmph"],
            "max_c":        w["maxtempC"],
            "min_c":        w["mintempC"],
            "max_f":        w["maxtempF"],
            "min_f":        w["mintempF"],
            "sunrise":      w["astronomy"][0]["sunrise"],
            "sunset":       w["astronomy"][0]["sunset"],
        }
    except Exception as e:
        print(f"[warn] weather: {e}")
        return None


def get_audio_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def mix_with_bgm(voice_path: str, bgm_path: str, output_path: str,
                 bgm_volume: float, fade_in: int, fade_out: int):
    duration = get_audio_duration(voice_path)
    fo_start = max(0, duration - fade_out)
    fc = (
        f"[1:a]aloop=loop=-1:size=2e+09,"
        f"volume={bgm_volume},"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={fo_start}:d={fade_out}[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[out]"
    )
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", voice_path, "-i", bgm_path,
         "-filter_complex", fc, "-map", "[out]",
         "-c:a", "libmp3lame", "-b:a", "128k", output_path],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg mix failed:\n{r.stderr[-2000:]}")


def synthesize_mp3(text: str, out_path: str, voice: str, rate: str, pitch: str,
                   customspeak: bool = False):
    async def _run():
        await edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch).save(out_path)
    asyncio.run(_run())
