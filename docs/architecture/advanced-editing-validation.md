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

CI run 40313637675 passed frontend and exposed the existing missing root stdio
launcher and outdated thumbnail-font path on Linux. Compatibility repairs restore
the documented launcher, use the actual bundled font, and support Windows anonymous
stdin pipes. Targeted checks: **18 passed**. Full local suite after repairs:
**1,250 passed, 26 skipped, 3 baseline Windows failures**, no errors. CI now installs
FFmpeg so new media tests cannot silently skip for a missing executable.

Audio compatibility commit `5854d04` was pushed to the feature branch. GitHub
Actions run `40318316166` passed both backend and frontend jobs.

## Visual explanations — verified local release

Four manual templates, source occurrence timing, Hindi/Hinglish shaping,
grounded Qwen suggestions and explicit preview approval are implemented locally.
Before the final environment-signature change, focused tests passed **42 tests**;
the full suite reported **1,262 passed, 26 skipped, 3 baseline Windows failures**.
Dashboard lint and build passed. Raster tests cover all four templates in portrait
and landscape, unsupported glyphs, overflow and callout bounds. Encoded media
checks covered overlay boundaries, preview/export parity and silent source video.

Browser verification used the real editor/API with an encoded synthetic source:
Hindi/Hinglish key point over music and captions, playback, approval and export
passed. This is not a recorded-speech quality assessment. A local llama.cpp
b11898 CPU server with official Qwen3-0.6B Q8_0 GGUF returned a grounded callout
using the final bounded exact-extract schema. Earlier broader schemas produced
unusable output; the implemented assistant only selects key points and callouts.
This verifies connectivity and one grounded result, not general editorial quality.

The final font/engine/template signature pinning and expanded encoded tests for
all four templates passed in the subsequent full suite: **1,274 passed, 26 skipped,
3 unchanged baseline Windows failures**. An earlier automatic approval usage-limit
block was resolved before this run. Recorded speech, hour-scale high-resolution
capacity and tracking remain unverified; tracking is disabled. B-roll is the next
separate delivery. CI results are recorded after pushing the visual feature.

UI integration follow-up: moved the editor entry into the existing app header,
reused the app theme, grouped composition controls into Audio/Visuals/Local media,
and retained preview approval gating. Dashboard lint and production build passed.
Browser checks confirmed the entry at `/#app`, same-page dialog opening, saved
project loading, visual section selection and disabled approval before preview.
These checks do not replace the pending backend/media regression run or CI.
