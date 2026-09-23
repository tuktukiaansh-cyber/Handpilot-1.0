from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
MODELS = {
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "blaze_face_short_range.tflite": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
}


def download_one(name: str, url: str) -> None:
    destination = ASSETS / name
    if destination.exists() and destination.stat().st_size > 100_000:
        print(f"OK: {name}")
        return
    print(f"Downloading {name}...")
    request = Request(url, headers={"User-Agent": "HandPilot/2.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as out:
        total = int(response.headers.get("Content-Length", "0"))
        received = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            received += len(chunk)
            if total:
                print(f"\r  {received / total * 100:5.1f}%", end="", flush=True)
    print(f"\nSaved: {destination}")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        download_one(name, url)


if __name__ == "__main__":
    main()
