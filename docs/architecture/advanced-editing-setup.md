# Optional local composition editing

The existing local long-form setup and loopback/token guard still apply. Enable
`LONGFORM_EDITING_ENABLED`, `LONGFORM_EXPORT_ENABLED`, and `LONGFORM_AUDIO_ENABLED`
to use Audio in **Edit full video → Audio, visuals and local assets**. Flags default
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
local assets** and select Audio storytelling, Visual explanations or Local media.
Only enabled capabilities are shown; the existing feature defaults are unchanged.
There is no separate production site or new route for these controls.

Install `requirements-longform.txt` and enable `EDIT_VISUALS_ENABLED` for visual
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
