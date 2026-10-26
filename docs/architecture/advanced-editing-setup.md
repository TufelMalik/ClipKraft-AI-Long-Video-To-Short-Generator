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
