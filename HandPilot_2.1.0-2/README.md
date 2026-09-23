# HandPilot 2.x

## macOS 27 threading fix

HandPilot 2.1.1 creates the `pynput` desktop-input controller on the Qt main thread and executes keyboard/mouse actions from that same thread. This is intentional: macOS 27 can trap background-thread calls into HIToolbox/TIS input-source APIs.

A local real-time desktop vision controller for macOS, Windows and Linux. HandPilot combines a MediaPipe Hand Landmarker, a lightweight BlazeFace detector, OpenCV camera capture, a PySide6 UI, and pynput desktop input.

## Two-hand control

HandPilot 2.1 supports independent control for both detected hands. Each hand keeps its own gesture stabilizer, landmark smoother, cursor state, and scroll trajectory. This enables combinations such as:

- LEFT/RIGHT hand `ONE` → cursor movement while the other hand uses `TWO` → scroll.
- One hand uses `ONE` → cursor movement while the other performs `PINCH` → left click.
- One hand performs `OK` → right click while the other continues moving the cursor.

Mappings can optionally be filtered to `ANY`, `LEFT`, or `RIGHT` in the Mappings tab. `runtime.multi_hand_enabled` controls whether actions are evaluated independently for both hands.

## What changed in 2.x

- **Absolute air-mouse mapping:** the configurable cursor joint (default: index fingertip, landmark 8) is mapped from normalized camera coordinates to real screen pixels.
- **Independent cursor smoothing:** cursor filtering is separate from gesture filtering, with active-area margins, precision and pixel deadzone controls.
- **Fixed pinch classification:** pinch/OK are evaluated before fist/finger counting, so a pinched hand cannot be swallowed by the fist rule.
- **Click state machine:** clicks fire on stable gesture entry, not every frame; cooldown is tracked independently per hand and gesture.
- **Face-aware interaction guard:** a BlazeFace detector watches for faces. When the control hand overlaps the expanded face region, gestures and computer-control actions are paused.
- **Face hold:** the last face box is held briefly between detector passes so the interaction guard does not blink on/off.
- **Multiple hands:** both hands can control the computer simultaneously. Each hand has independent gesture, cursor, scroll, and cooldown state. Preferred hand selects the primary UI hand; `multi_hand_enabled` controls whether both hands can execute mappings.
- **Action error isolation:** a desktop-control permission/error no longer kills the camera thread.
- **Configurable UI:** camera, face guard, smoothing, gesture thresholds, cursor joint and cursor mapping can be edited without changing recognition code.

## Default controls

| Gesture | Action | Mode | Enabled |
|---|---|---|---|
| ONE | MOUSE_MOVE | WHILE_ACTIVE | Yes |
| PINCH | LEFT_CLICK | ON_ENTER | Yes |
| OK | RIGHT_CLICK | ON_ENTER | Yes |
| TWO | SCROLL | WHILE_ACTIVE | Yes |
| FIST | MEDIA_PLAY_PAUSE | ON_ENTER | Yes |
| THUMBS_UP | VOLUME_UP | ON_ENTER | Yes |
| THUMBS_DOWN | VOLUME_DOWN | ON_ENTER | Yes |

Automation is OFF on first launch. Turn it on after verifying the live gesture labels.

## macOS MediaPipe compatibility

For Apple Silicon Macs, HandPilot intentionally pins `mediapipe==0.10.35`. A MediaPipe 1.0.x installation can abort natively inside the macOS Metal/Drishti vision graph before Python gets a chance to catch the error. The application also requests the CPU delegate explicitly and sets `MEDIAPIPE_DISABLE_GPU=1` on macOS.

If you previously installed HandPilot 2.0.0, repair the environment with:

```bash
./fix_macos.sh

# Or manually:
python -m pip uninstall -y mediapipe
python -m pip install --no-cache-dir mediapipe==0.10.35
python tools/doctor.py
python main.py
```

The doctor should report the MediaPipe version as `0.10.35` and `MediaPipe macOS compatibility line: OK`.

## Installation

Recommended: Python 3.12+ on Apple Silicon. The bundled macOS arm64 MediaPipe 0.10.35 wheel is Python-3 compatible; if another dependency resolver rejects Python 3.13, use Python 3.12 for the cleanest setup.

### macOS / Linux

```bash
cd HandPilot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python tools/download_model.py
python tools/doctor.py
python main.py
```

### Windows PowerShell

```powershell
cd HandPilot
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python tools\download_model.py
python tools\doctor.py
python main.py
```

## Models

`tools/download_model.py` downloads two local models:

- `hand_landmarker.task`
- `blaze_face_short_range.tflite`

The Hand Landmarker is used for the 21 hand joints and handedness. The face detector supplies a lightweight face bounding box used to pause hand control when the hand is on the face.

## macOS permissions

Camera:

**System Settings → Privacy & Security → Camera**

Desktop control:

**System Settings → Privacy & Security → Accessibility**

Grant permission to the terminal/Python host that actually launches HandPilot.

## Per-hand mapping

Each mapping can target `ANY`, `LEFT`, or `RIGHT`. Use `ANY` for ordinary two-hand behavior. For example, assign `ONE` → `MOUSE_MOVE` to `LEFT` and `PINCH` → `LEFT_CLICK` to `RIGHT` when you want deterministic role separation.

`multi_hand_enabled` defaults to `true`, so a `ONE` hand can move the pointer while the other hand independently scrolls with `TWO` or clicks with `PINCH`/`OK`.

## Cursor mapping

HandPilot uses the selected landmark (default index fingertip) as a normalized `(x, y)` point.

1. Camera point is cropped to the configurable active area.
2. The point is optionally precision-scaled around the center.
3. Exponential smoothing reduces jitter.
4. The final normalized point becomes absolute screen pixels.
5. A small deadzone prevents tiny movements from generating desktop input.

This is why the cursor can reach the whole screen instead of only moving relative to the previous hand position.

## Face guard behavior

When a face is detected, HandPilot expands the face box slightly. If the control hand's wrist, thumb tip, index tip, middle tip or pinky tip enters that region—or enough hand landmarks overlap it—the hand is marked `face_blocked`.

Blocked hands remain visible in red, but the gesture engine reports `NONE`, the cursor mapper resets, and continuous actions stop. This prevents the exact problem where putting a hand in front of your face continues to drive the mouse.

## Adding a new gesture

Implement the recognition feature in `src/gestures/rules.py` or replace `RuleBasedClassifier` with a learned classifier in `src/gestures/classifier.py`. The rest of the pipeline consumes `GesturePrediction`, so actions and UI do not need to know how the gesture was recognized.

## Adding a new action

Create an `Action` implementation under `src/actions/`, register it in `ActionRouter.actions`, then select it from the Mappings tab.

## Project layout

```text
HandPilot/
├── main.py
├── requirements.txt
├── README.md
├── assets/
├── config/
├── tools/
├── tests/
└── src/
    ├── core/
    ├── gestures/
    ├── vision/
    ├── actions/
    └── ui/
```


### Settings restart

Settings that affect the process-wide vision stack use **Save & restart**. This now launches a detached relaunch helper, waits for the existing HandPilot process to fully exit, and then starts `main.py` again using the same Python interpreter and command-line arguments.

### Gesture control model

- **ONE:** the index fingertip (#8) is the air-mouse point. Move that fingertip around the camera view to move the cursor.
- **TWO:** keep two fingers raised and wave the **index fingertip (#8)** vertically. Move down to scroll down; move up to scroll up. Diagonal/horizontal movement is filtered.
- Scrolling uses a continuous fingertip trajectory with smoothing and fractional accumulation rather than one wheel event per frame.
