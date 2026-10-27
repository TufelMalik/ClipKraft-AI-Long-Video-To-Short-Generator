# Optional local composition editing

The existing local long-form setup and loopback/token guard still apply. Enable
`LONGFORM_EDITING_ENABLED`, `LONGFORM_EXPORT_ENABLED`, and `LONGFORM_AUDIO_ENABLED`
to use Audio in **Edit full video → Edit your video**. Flags default
off. Restart the backend after changing configuration. No cloud support is added.

FFmpeg/ffprobe must provide `afftdn`, `sidechaincompress`, `amix`, `afade`, `aloop`,
and `loudnorm`; the capabilities response reports installed audio filters. Pillow
is needed to validate image uploads. No paid service or model is used for audio.

Upload audio, add a music or SFX track, then edit start/end, source in-point, gain,
fades, looping and ducking. Short files require a shorter placement or explicit
looping; loops repeat the selected tail, limited to 60 seconds of decoded audio.
Check loop joins in playback. Use gentle cleanup only when useful; it does not
separate embedded music. Ducking is unavailable without source audio. The source's
first audio stream is used consistently across cuts. Output mixes are stereo/48 kHz.

Mute/solo-background and voice bypass affect **Audition only**. Audition previews
cannot be applied by the API. **Preview composition to save** renders all export
settings; play it and explicitly approve to save. Every setting change invalidates
the pending approval. Previews cover the full timeline, preserving phase, fades and
detector history. Final encoded AAC loudness/true peak are recorded in the manifest;
encoded peaks over 0 dBTP fail rather than silently accept clipping.

The library accepts a bounded raster/video/audio allowlist, at most 256 MB per file
and 2 GB total, eight audio tracks, 16 million image pixels, and two-hour media.
Uploads are private beside the existing SQLite database, outside public media
roots. Media is served through scoped 15-minute tickets. Content is immutable:
upload replacements as new asset IDs; existing drafts/exports keep their original
checksums. Metadata has separate revision checks. Referenced assets cannot be
deleted, including history and preview dependencies. No automatic asset expiry is
imposed; the hard quota is explicit, and missing files are reported. Existing job
retention still governs source videos and exports.

Version 1 projects stay version 1 until a composition is saved. Empty compositions
use the existing render path. Active compositions use raw PCM intermediates and
one final audio finish; shorts normalization defaults are unchanged. Timeline
changes mark output-anchored tracks for review. Reconfirm their times or disable
them before preview/export. Occurrence anchors follow only explicit split lineage;
removed/cross-cut ranges need review. Disable affected tracks before previewing AI
story cuts, then re-place them on the approved timeline. Undo/redo restores complete
saved snapshots. Historical manifests remain immutable.

Back up the private database and asset directory before deployment. Do not run an
older binary against a schema-v2 database: old releases cannot safely understand
its tracks. To downgrade, restore a matching pre-v2 database backup and preserve
immutable exports separately. Disabling feature flags stops new changes; it does
not erase compositions or silently omit saved layers during rendering.

## Visual explanations

Open the existing OpenShorts app and choose **Edit full video** in its header.
The editor opens in the same page. Inside a project, expand **Audio, visuals and
local assets** and select Audio, Text & graphics, B-roll or My media.
Only enabled capabilities are shown; the existing feature defaults are unchanged.
There is no separate production site or new route for these controls.

Install `requirements-longform.txt` and enable `LONGFORM_VISUALS_ENABLED` for visual
controls. The capability check requires FFmpeg overlay support, HarfBuzz,
FreeType, and the bundled Noto Sans and Noto Sans Devanagari fonts. Their SIL OFL
license is included in `fonts/Noto-OFL.txt`. Text is shaped explicitly with
HarfBuzz and rasterized with FreeType; Pillow RAQM is not required. English,
Hindi and Hinglish are supported; other scripts are not verified.

The editor provides key points, comparisons, ordered processes and callouts.
Set the source occurrence and interval, position, size, theme and transition;
callout boxes use normalized coordinates. Overflow and unsupported glyphs fail
with an error instead of silently clipping or substituting text. Template
placements reserve the lower caption area; manually placed callouts need review.
Preview, play and explicitly approve the complete composition before saving.
Font, shaping engine and template versions are pinned; changes require a new
preview and approval. Visual overlays require an additional video encoding pass.
Visual-only edits preserve the existing audio treatment.

Optional Qwen3-0.6B suggestions select short, exact transcript extracts for key
points or callouts. Select up to four sentences from one source occurrence.
Comparisons and processes are manually authored. Suggestions are editable and
never apply automatically; missing or unsuitable model output leaves manual
editing available. Configure the existing OpenAI-compatible local endpoint with
model alias `qwen3-0.6b`. No paid model is required.

Upstream components: [Noto fonts](https://github.com/notofonts/noto-fonts),
[uharfbuzz](https://github.com/harfbuzz/uharfbuzz), and
[freetype-py](https://freetype-py.readthedocs.io/en/latest/).

## Context-aware B-roll

Enable `LONGFORM_BROLL_ENABLED=true` alongside `LONGFORM_EDITING_ENABLED=true`.
The feature uses the existing **Edit full video** option in the OpenShorts page.
Audio and explanation features are independently gated. FFmpeg must provide
overlay, scale, pad, crop, fps and tpad; capabilities report actual support.

In **My media**, upload an image/video and add tags, a description of its
visible content, language, source label and usage notes. Inspect the ticketed
media before using it. Unknown usage rights remain unspecified. Assets stay in
the existing private library; referenced drafts/history/exports prevent deletion.
Metadata edits use optimistic revision checks. Updating media content requires
a new upload, preserving existing immutable asset IDs and export dependencies.

In **B-roll**, choose the source occurrence and one to four transcript
sentences, then suggest matches. Search uses deterministic token overlap over
tags/descriptions/source labels, with a small explicit Hindi/Hinglish alias list
in `broll_search.py`; additional domain vocabulary belongs in user tags. No model
or external search service is needed. Optional local Qwen3-0.6B ranks only those
metadata candidates. Reasons displayed in the UI are verified matched terms;
neither retrieval nor Qwen inspects pixels. No match is a valid result. Manual
metadata search and placement remain available without Qwen.

Select a candidate or manually choose an image/video, then set source occurrence,
start/end, cover/inset, contain/crop and normalized crop focus. Insets occupy 40%
of frame dimensions at upper left/right, leaving lower caption space. Images
hold for the selected interval. Video in-points select the start of footage; short
clips fail unless explicitly set to loop the selected tail or hold its final
frame. Loop tails are capped at 60 seconds and normalized to a temporary video
before streaming repetition, avoiding a decoded-frame loop cache. This adds an
encoding pass for loops and uses the existing deadline/disk/cancellation guards.

At most four B-roll layers can be enabled; full-frame covers cannot overlap.
Insets may overlap, and explanations render above all B-roll, in saved layer
order. Review region/caption overlap in preview. B-roll never inserts time or
uses asset audio: main narration and chosen music/SFX continue. To use another
audio source, add an explicit audio track through the Audio panel.

Every change requires a complete preview, playback and explicit approval. New
AI proposals pin source/transcript revision and asset metadata revision; changed
metadata or assets invalidate pending approval. Saved layers are frozen placements
and remain manually editable. EDL cuts reuse the common occurrence reconciliation;
resolve or disable layers marked for review. Undo/redo restores all composition
settings together. Preview/export use the same path and dependency hashes.
