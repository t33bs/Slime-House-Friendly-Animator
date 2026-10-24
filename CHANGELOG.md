## v0.47.0 — Windows GUI smoke-test hardening

The packaged GUI smoke test now checks actual minimize/maximize states, restore-to-normal, and resize behavior against available screen geometry at 800×600, 1280×720 and 1920×1080 targets (clamped to runner screen). Windows CI logs Qt and OS diagnostics. These tests require execution on a Windows runner; they have not been executed in this environment.

## v0.46.0 — Windows installer upgrade regression

Added a Windows CI install/reinstall/uninstall lifecycle test. It runs packaged GUI smoke checks after both installs and compares the exact bytes of a user-project sentinel outside the installation directory before and after each operation. This is a same-version reinstall rehearsal, not yet a true cross-version upgrade test. Windows workflow has not executed here.

## v0.45.0 — Windows installer lifecycle validation
- GitHub Actions now runs a real silent installation, starts the **installed** EXE in GUI smoke-test mode, invokes the actual uninstaller, and checks the installed EXE was removed.
- Captures installer log as a failure artifact when available.
- Adds two pipeline regression tests.
- Windows CI has not yet been executed here: this is an unverified Windows test workflow, not a passed installer run.

## v0.44.0 — Phase 5 Windows packaging smoke-test checkpoint
- Added `--smoke-test` to exercise the real PySide6 application startup, minimize/maximize/restore transitions, and offline Slime Buddy/template resources.
- Windows GitHub Actions now executes the **packaged EXE** smoke test and fails the build if it exits unsuccessfully.
- Added packaged dependency presence checks and synchronized installer/application version.
- Added four regression guardrails for Windows packaging configuration.
- **Still unverified:** Windows CI execution, installer installation/uninstallation, DPI scaling, interactive GUI and upgrade behavior. The workflow must run on GitHub Windows runners to validate these.

# v0.42.0 — Phase 5 installer and updater foundation

- Added Windows one-folder PyInstaller build and Inno Setup installer/uninstaller configuration.
- Installer preserves user data by only uninstalling program files.
- Added Ed25519-signed manifest validation, version comparison, SHA-256/size checked installer download helper, and eight updater tests.
- Added manual Check for updates button, running checks in a background thread when official signing keys/feed are configured.
- Update button opens the official release download URL after explicit approval; it does NOT silently install updates.
- Signing key/feed are deliberately blank until official release infrastructure is set up. No unsigned updates accepted.
- Windows installer and GUI have NOT been run or verified in this Linux environment.
## v0.41.0 — Phase 4 regression checkpoint

- Export regression coverage for colliding sanitized animation names, empty timelines, and single-format export.
- Avoid overwriting separate animations when names differ only in punctuation or case.
- Source-level tests only; Windows GUI verification remains pending.

## v0.38.0 — Phase 4 GIF fidelity
Shared GIF palette, binary alpha, 10ms duration quantization, transparent-frame and motion regression tests. Windows GUI validation remains pending.

# v0.36.0 — Phase 4, Task 1: Sprite sheet timing fidelity

- Override generic sprite sheet export to preserve authored per-pose durations in the JSON manifest.
- Preserve exact RGBA frame pixels and explicit atlas rectangles, including configurable spacing.
- Add regression tests for atlas crops, multiple animation order, no-frame fallback, and non-mutating export.
- Phase 4 animated-format integration and Windows GUI verification remain pending.

## v0.37.0 — Responsive window hardening
- Scrollable left, middle and comparison panels for small viewports.
- Horizontal scrolling for crowded action toolbars.
- Restore saved windows inside available monitor bounds after resolution/monitor changes.
- Pure geometry tests for small, multiple and negative-coordinate displays.
- Actual Windows maximize/minimize behavior remains unverified until Windows GUI testing.

## v0.39.0 — Phase 4 APNG fidelity
- Isolated lossless RGBA APNG encoder; validate dimensions, timing and frame counts.
- Integration and byte-exact frame round-trip tests including alpha, motion and non-destructive export.
- Windows GUI and full end-to-end verification remain pending.

## v0.40.0 — Phase 4 Task 4: project-to-export integration
- Added end-to-end project save/reopen/export tests for GIF, APNG and PNG/JSON atlas.
- Verify multiple animations, per-pose timing, transparent RGBA pixels, atlas rectangles, looping and project fingerprint stability.
- Added a second nested-path save/reopen and separate-output-directory export regression test.
- Windows GUI and actual display testing remain outstanding.

## v0.43.0 — Windows update handoff and release assets
- Asynchronous verified installer download, save-before-update confirmation and Windows installer handoff.
- Offline signing script for a GitHub release manifest (Ed25519 private key never committed).
- Resource self-check for Slime Buddy, recipes and reference animations.
- Added signed-release and bundled-resource tests.
- Update feed and public key intentionally remain unconfigured until release owner provisions them.
