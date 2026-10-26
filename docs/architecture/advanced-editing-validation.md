# Advanced editing validation

## Audio and shared foundation — 26 October 2026

Implemented strict opt-in schema v2, occurrence lineage, stale-layer review,
private content-checked assets, transactional snapshots, complete composition
identity, immutable preview approval, and manual music/SFX/voice controls.

Commands run with the repository virtual environment and Windows local socket/
subprocess access:

- Baseline focused long-form/recut/LLM tests: **61 passed, 2 skipped**.
- Full suite before new tests: **1,239 passed, 26 skipped, 4 failed, 3 errors**.
- Full suite with audio tests: **1,246 passed, 26 skipped, 4 failed, 3 errors**.
- The unchanged failures are static-file restoration, unavailable platform font,
  two POSIX ASR-lock assertions, and three stdio tests using the former module path.
- Dashboard `npm run lint` and `npm run build` passed. Existing OpenPanel variable,
  Browserslist and bundle-size notices remain.

`tests/test_composition.py` exercises actual FFmpeg/AAC outputs, source-audio absence,
looping/short asset rejection, fades, checksum replacement, private tickets,
cross-cut anchors, history, stale revisions and approval tampering. A 440 Hz
dialogue detector with a silent interval and 1,200 Hz music measures stronger music
during the gap. Decoded video/audio preview/export hashes match with fixed sample
blocks, fixed graph scheduling and bit-exact AAC settings. Encoded true peak stays
below 0 dBTP; full decode and duration checks pass. This establishes signal behavior,
not perceived speech intelligibility or editorial quality.

No representative user-owned speech footage is available in the workspace. Actual
English/Hindi speech listening, existing-music cleanup assessment, hour-scale
high-resolution memory/disk capacity, and live Qwen remain external verification
gates. Synthetic fixtures are not evidence for those claims. Flags remain off by
default. Browser checks passed against the real API: add a track, set fades/ducking, render,
play, approve/save, undo, redo and export with selectable captions. The standalone
test server must run with Python UTF-8 mode on Windows, as the existing encoder
logs contain Unicode. Final focused regressions: **87 passed, 2 skipped**. CI status
is recorded after the feature-branch push.
