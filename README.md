#  HANDPILOT

###  Launch HandPilot

 run:
 
```bash
git clone https://github.com/tuktukiaansh-cyber/HandPilot-1.0.git
cd HandPilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
in terminal!!

```text
╭──────────────────────────────────────────╮
│          🖐️  HANDPILOT STARTING         │
│                                          │
│   Hand Tracking     ✓                    │
│   Face Tracking     ✓                    │
│   Gesture Engine    ✓                    │
│   Two-Hand Control  ✓                    │
│   Air Mouse         ✓                    │
│   Gesture Actions   ✓                    │
│                                          │
│              READY 🚀                    │
╰──────────────────────────────────────────╯
```
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
