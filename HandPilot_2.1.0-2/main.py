from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# macOS / Apple Silicon safety: keep MediaPipe on its CPU path. This environment
# variable is set before importing any local module that may import MediaPipe.
if sys.platform == "darwin":
    os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.core.config import ConfigStore
from src.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
USER_CONFIG = CONFIG_DIR / "user_config.json"
DEFAULT_CONFIG = CONFIG_DIR / "default_config.json"
HAND_MODEL_PATH = ROOT / "assets" / "hand_landmarker.task"
FACE_MODEL_PATH = ROOT / "assets" / "blaze_face_short_range.tflite"


def _version_tuple(version: str) -> tuple[int, int, int]:
    parts = [int(x) for x in re.findall(r"\d+", version)[:3]]
    parts += [0] * (3 - len(parts))
    return tuple(parts[:3])


def _check_vision_runtime(app: QApplication) -> bool:
    try:
        import mediapipe as mp
    except Exception as exc:
        QMessageBox.critical(
            None,
            "HandPilot — MediaPipe missing",
            f"Could not import MediaPipe.\n\n{exc}\n\n"
            "Install the pinned dependencies with:\n"
            "python -m pip install --force-reinstall -r requirements.txt",
        )
        return False

    # MediaPipe 1.0.x has a known native macOS failure mode in the vision graph
    # used here. Do not let a later accidental upgrade put the app back into a
    # hard-abort state. 0.10.35 is the pinned compatibility line for HandPilot.
    if sys.platform == "darwin" and _version_tuple(getattr(mp, "__version__", "0.0.0")) >= (1, 0, 0):
        QMessageBox.critical(
            None,
            "HandPilot — incompatible MediaPipe version",
            f"Installed MediaPipe: {getattr(mp, '__version__', 'unknown')}\n\n"
            "HandPilot currently pins MediaPipe 0.10.35 on macOS because the 1.0.x "
            "line can abort natively in the Metal/Drishti vision graph.\n\n"
            "Fix it with:\n"
            "python -m pip install --force-reinstall --no-cache-dir mediapipe==0.10.35",
        )
        return False

    return True


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HandPilot")
    app.setApplicationDisplayName("HandPilot")
    app.setOrganizationName("HandPilot")

    if not _check_vision_runtime(app):
        return 2

    config = ConfigStore(USER_CONFIG, DEFAULT_CONFIG)
    window = MainWindow(config, HAND_MODEL_PATH, FACE_MODEL_PATH)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
