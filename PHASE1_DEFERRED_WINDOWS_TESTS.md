# Deferred Windows verification — Phase 1

These four checks are intentionally postponed until a usable Windows build:

1. Verify Slimer Pose 001/002/... labels in the Asset Library match timeline pose positions, including reordering.
2. Safely migrate old projects containing multiple legacy `Slimer pose` layers; preserve legitimate artwork.
3. Repeatedly highlight, drag, place frames, switch poses, and compare pixel-exact exports for loss or stale overlays.
4. Verify pose recovery in the UI, including save/reopen, reorder/delete, and recovery of the correct timeline pose.

## Source progress

- Added bounded (5-entry) per-pose recovery history in `PetSuiteModel` for `save_pose_at` and `edit_pose_at`.
- Recovery is currently in-memory only; no UI command or on-disk persistence has been added.
- Recovery keys currently use animation name and frame index; timeline insertion/deletion/reordering still require stable-ID handling before production use.
- No claim is made that the original pixel depreciation bug is fixed.
