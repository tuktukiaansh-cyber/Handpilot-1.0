from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

print("HandPilot system check")
print("OS:", platform.platform())
print("Python:", platform.python_version())
print("Machine:", platform.machine())
print("MediaPipe GPU disable env:", "1" if sys.platform == "darwin" else "not needed")

for name in ("cv2", "mediapipe", "numpy", "PySide6", "pynput"):
    try:
        module = importlib.import_module(name)
        print(f"{name}: OK {getattr(module, '__version__', '')}".rstrip())
    except Exception as exc:
        print(f"{name}: ERROR {exc}")

try:
    import mediapipe as _mp
    if sys.platform == "darwin":
        version_text = getattr(_mp, "__version__", "0.0.0")
        major = int(version_text.split(".")[0])
        if major >= 1:
            print("WARNING: MediaPipe 1.x is not accepted on macOS by this build.")
            print("         Reinstall mediapipe==0.10.35 before launching HandPilot.")
        else:
            print("MediaPipe macOS compatibility line: OK")
except Exception:
    pass

for model in ("hand_landmarker.task", "blaze_face_short_range.tflite"):
    path = ASSETS / model
    print(f"Model {model}:", "OK" if path.exists() and path.stat().st_size > 100_000 else "MISSING")
