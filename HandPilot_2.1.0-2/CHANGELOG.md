## 2.1.1 — macOS 27 input-thread fix

- Moved `ActionRouter` / `pynput` desktop-input ownership from `CameraThread` to the Qt main thread.
- Fixes macOS 27 `EXC_BREAKPOINT` / `dispatch_assert_queue` crashes through HIToolbox/TIS keyboard-input APIs.
- CameraThread is now strictly vision-only; mouse/keyboard actions are executed from the GUI event thread.
- Added ActionRouter state reset when the camera stops/restarts.

# Changelog

## 2.1.0 — Independent two-hand control

- Added independent per-hand gesture state machines.
- Added simultaneous actions: one hand can move the cursor while the other scrolls or clicks.
- Added per-hand mouse and scroll motion state so gesture changes on one hand do not reset the other.
- Added optional per-mapping LEFT/RIGHT hand filters.
- Added `runtime.multi_hand_enabled` setting (enabled by default).
- Updated the Live UI and video overlay to show each hand's active gesture/action role.


## 2.0.1 — macOS crash fix

- Pin MediaPipe to `0.10.35` on the desktop vision stack.
- Explicitly select MediaPipe CPU delegates for hand and face models.
- Set `MEDIAPIPE_DISABLE_GPU=1` before MediaPipe can be imported on macOS.
- Add a startup guard that rejects MediaPipe 1.x on macOS with a clear repair command instead of entering the known native-abort path.
- Remove Qt's missing `-apple-system` font alias warning.
- Extend `doctor.py` with the MediaPipe compatibility check.

## 2.0.0



- Added local face detection and face-aware hand-control suppression.

- Fixed pinch detection ordering so pinch/OK are checked before fist/counting.

- Replaced relative hand-center mouse movement with absolute joint-to-screen mapping.

- Default cursor joint is MediaPipe landmark 8 (index fingertip).

- Added cursor smoothing, screen-edge mapping margins, precision and pixel deadzone.

- Made PINCH → LEFT_CLICK and OK → RIGHT_CLICK default mappings.

- Added payload JSON editing in the Mappings UI.

- Added safe action error isolation and action-state resets on gesture transitions.

- Added preferred hand selection and spatial hand continuity.

- Added platform-aware next/previous window and desktop actions.

- Added JSON config migration so older `user_config.json` files inherit new defaults.

- Added dependency-free unit tests for cursor mapping and pinch classification.

## 2.0.2 — Real application restart

- Fixed Settings → Save & restart: it now relaunches the entire HandPilot process instead of only restarting the camera thread.
- Added a detached restart helper that waits for the old Qt/camera process to exit before launching `main.py` again.
- Added visible "Restarting…" UI state and safe failure handling.
- Preserves command-line arguments across restart.

## 2.0.3 — Fingertip gesture controls

- ONE finger uses index fingertip landmark #8 as the air-mouse control point.
- TWO fingers use index fingertip motion for directional scrolling. Move the fingertip down to scroll down; move it up to scroll up.
- Scroll uses filtered trajectory motion, vertical-axis locking, minimum-motion filtering, and fractional accumulation so slow/fast waves both work.
- Added scroll tuning controls to Settings.
