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

Visual delivery commit `71e5885` passed backend and frontend CI in run
`40536591499`. Final focused visual/audio/long-form/recut/LLM checks:
**83 passed, 2 skipped**. The main-page UI and visual feature are committed and pushed.

## Context-aware B-roll — 27 October 2026

Implemented local metadata search, explicit Hindi/Hinglish aliases, optional
bounded Qwen ranking, private media inspection/tagging, occurrence-linked manual
and suggested placement, cover/inset, contain/crop focus, in-points, explicit
tail-loop/final-frame hold, and immutable preview approval. Asset audio is never
mapped into B-roll outputs. Explanation layers render above B-roll.

`tests/test_broll.py` verifies bilingual/no-match retrieval, model fallback and
invalid IDs, wrong media type, short files, cover conflicts, stale metadata,
changed-source anchors, tampered approval and independent flags. Actual FFmpeg
fixtures cover images, 25-fps portrait video over a 20-fps landscape source,
crop focus, inset geometry, in-point loops and freeze, source audio absence and
combined audio/explanations/B-roll. Decoded narration hashes match the original
render over the approved six-second interval; B-roll audio is excluded. Full
decoded video hashes match preview/export. An intermediate-container AAC priming
shift discovered by this test was fixed by retaining the legacy MP4 intermediate
for visual-only compositions; raw PCM/MKV remains specific to audio mixing.

Focused combined regressions: **92 passed, 2 skipped**. Dashboard lint/build passed
with the pre-existing environment/Browserslist/bundle notices. Live llama.cpp
b11898/Qwen3-0.6B Q8_0 ranked a tagged synthetic local asset for an actual selected
transcript passage in the main OpenShorts page. Browser checks passed tagging,
media inspection, suggestion, editable inset placement, full preview/playback,
approval, undo and redo. Final full-suite/export/CI results follow below.

All encoded fixtures are synthetic. Recorded English/Hindi speech quality,
hour-scale high-resolution resource capacity and tracked callouts are not
verified by these tests. Feature flags remain off by default; tracked callouts
remain disabled. These are explicit verification limits, not evidence of those
workloads completing successfully.

Final local suite: **1,291 passed, 26 skipped, 3 baseline Windows failures**
(`test_restoring_static` and the two POSIX ASR lock assertions). No new failures.
Browser final export `6c26b59cdcc34a489ddc80316a604fce` at synthetic project
revision 7 played successfully with music, Hindi/Hinglish explanation, B-roll
inset and selectable captions. Composition renderer identity advances to
`composition-2` for the new B-roll graph and visual-only timestamp correction.

After advancing the renderer identity, final composition media checks passed
**31 tests**. The temporary standalone verification HTML was removed; browser
verification and the retained result use the actual `/#app` page. CI runs on
every feature-branch push; final run status is linked in the delivery response
and available in the repository's GitHub Actions history for
`codex/advanced-editing-plan`.

## UI clarity follow-up

Simplified tool labels to Audio, Text & graphics, B-roll and My media. The editor
opens its tools immediately, groups optional controls under advanced settings,
and keeps Preview/Save/Reset controls visible. Preview scrolls into view when
ready; saving remains disabled until that exact preview plays. Saved-video
preview/export actions are explicitly distinguished from unsaved draft changes.
The Shams Group header logo change was subsequently rolled back at the user's
request; the original OpenShorts branding is restored. UI simplification remains.

Browser verification covered 390px and 1280px layouts, loaded header image,
advanced-setting visibility, draft editing, preview playback unlocking Save,
and successful save to synthetic project revision 8. Lint/build passed. Full
suite: **1,291 passed, 26 skipped, 3 unchanged baseline Windows failures**.

## Full-video upload and error-response correction

The local browser had remained connected to an isolated verification router host,
which did not provide the normal application's upload directory. Full-video
upload therefore returned a plain-text HTTP 500, and unconditional frontend JSON
parsing hid it behind `Unexpected token`. The local preview now uses the actual
`app:app` backend. Existing private library assets were preserved. Synthetic
verification projects remain separate from the normal application's projects.

An actual upload then exposed a Windows subprocess issue: redirected ASR progress
logs used cp1252 and failed on Unicode. The transcription worker explicitly sets
UTF-8 on stdout/stderr. A subprocess regression forces cp1252 and verifies Unicode
progress plus an atomic multilingual transcript write. An HTTP ingest regression
uses the real application host contract and verifies source discovery, project
creation, transcript availability and a playable encoded preview (inference only
is stubbed in this automated test).

The editor now reads non-JSON server/proxy failures as readable HTTP errors while
preserving structured server details. Four Node response-handler checks pass and
run in frontend CI. Focused Python upload/worker/long-form checks: **25 passed**.
Manual verification uploaded a locally generated speech video through the browser
to the actual app and completed real faster-whisper transcription into an editable
project. This is generated speech, not representative recorded-speech quality
or hour-scale capacity verification.

The same uploaded speech project subsequently rendered a playable preview and
final export through the normal application. Full regression suite:
**1,293 passed, 26 skipped, 3 unchanged baseline Windows failures**. Dashboard
lint/build and all four response-handler checks passed.
