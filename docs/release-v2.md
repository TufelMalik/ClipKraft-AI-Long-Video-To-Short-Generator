# Release v2 implementation

Branch: `release/v2`, based on `feat/structured`.

The two supplied planning documents define the feature backlog. Business
forecasts and statements about monetization or creator permissions are not
acceptance criteria or guarantees. No creator is assumed to have granted rights.

Implement and validate these phases sequentially:

1. Upper-body detection, aspect-correct fill crop, eye-line positioning,
   removal of default blurred padding, and temporal crop smoothing.
2. Audio-visual active speaker attribution, persistent speaker identities,
   tracked positions, and hard cuts with a minimum hold.
3. Commentary tracks, context lower-thirds, channel intro/outro templates,
   safe captions/hooks, word synchronization, loudness, silence trimming,
   and delivery quality.
4. Optional channel profiles and niches, duplicate
   fingerprints, source diversity warnings, and scored hooks.
5. Reaction cutaways, caption styles/colors, hook animation/dismissal,
   word-driven zooms, sound hits, grade, and editable B-roll markers.
6. Transcript/audio moment ranking and complete-thought length optimization.

Video speed slider: deferred by user request. No playback or export speed change.

## Implemented phases

| Phase | Implementation | Practical limits |
| --- | --- | --- |
| 1 | MediaPipe upper-body landmarks with geometric fallback; eye-line crop; fill framing; 20-frame EMA; fixed lens per shot to avoid FFmpeg frame loss | Subject/source boundaries can prevent the ideal eye line. Explicit full-width/screen layouts retain readable content. |
| 2 | Audio-gated mouth activity; shot-local velocity tracks; 2.4-second minimum camera hold; aligned SFace embeddings for anonymous identities across shots | An uncertain embedding creates a new ID. Accuracy requires review on real two-person footage. |
| 3 | Uploaded intro/outro commentary; context cards; niche-colored branding cards; face-aware caption anchors; synchronized words; pause trimming; normalized audio; 1080×1920 vertical output at ≥30 fps | Commentary is 0.5–15 seconds and ≤20 MB per upload. Context placement minimizes overlap; no overlay can avoid every face in every shot. |
| 4 | Optional channel profiles and niches; automatic uploader attribution for URL sources; atomic audio/visual duplicate ledger; weekly diversity warnings; publishing-profile binding | Self-host mode. Creator IDs are optional source-tracking metadata for uploads. Hooks keep their existing behavior until the original scorer is supplied. |
| 5 | Hormozi/Neon/Minimalist/Karaoke captions; speaker colors; hook fades and 3.5-second dismissal; word-triggered 12% zooms; generated sound accents; subtle grade; editable B-roll notes | Reaction cutaways are an opt-in facial-motion heuristic, not an emotion classifier. B-roll notes mark insertion points; they do not insert footage. |
| Selection | Transcript signals plus audio peaks augment model ranking; complete-thought preference around 30–50 seconds; conservative sentence-tail trimming | English phrase signals and numeric/reaction markers supplement the existing multilingual model. Scores are editorial estimates, not predicted view counts. |

## Using the new controls

Open the generator's **Advanced options** for editorial settings and channel
safety. Commentary files attach to the process request. Each generated clip
keeps its clean reframe; caption timing is remapped through silence cuts and
intro/outro additions. Trims and manual reframing reassemble the saved editorial
settings. The clip editor exposes B-roll notes in exported-video seconds.

Local channel profiles start with Finance, Tech/AI and Motivation and empty
creator lists. The versioned template is `examples/channel-profiles.json`;
personal configuration lives in ignored `.config/channels.json`. Configure
profiles in the dashboard or through `PUT /api/channel-profiles`.

Creator IDs are optional for source tracking. No permission references, expiry
dates or creator whitelists are required. URL processing records the uploader
automatically. Channel assignment is optional. For
publishing, set the channel's `publish_profile` to the intended Upload-Post
profile. The tool refuses a mismatched profile.

Environment options:

- `CHANNEL_PROFILES_PATH`: override the personal profile file path.
- `CLIP_LEDGER_PATH`: override the ignored SQLite fingerprint ledger path.
- `SPEAKER_MODELS_DIR`: override the speaker embedding model directory.
- `UPPER_BODY_CROP=0` / `REFRAME_FILL=0`: restore legacy crop behavior.
- `EDITORIAL_CONFIG_PATH`: CLI/job editorial JSON, including local commentary paths.

Docker builds install checksum-pinned SFace weights and their license. A bind
mount can hide image-bundled models; run `python scripts/setup_speaker_models.py`
in the checkout to populate `.cache/speaker-models`. Missing weights retain
shot-local tracking with a visible log message. Embeddings are held in memory
for one clip and are never saved as personal identity data.

Model references: [OpenCV SFace API example](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/sface.py),
[model license](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/LICENSE),
[MediaPipe Pose](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md).

## Deferred by user request

- Video speed control.
- 7/10 hook-score gate and the original 21-formula `hookscore.py` integration.

## Validation record

- Branch created from `feat/structured`; implementation is local and uncommitted.
- Full Linux/ML suite: 1,304 tests passed before the final export-index/API checks.
- Final targeted API/export checks: 65 tests passed. The final full-suite rerun
  is pending because the local Docker engine is unavailable; restart was attempted.
- Real FFmpeg smoke tests cover crop frame retention, keyword zoom frame retention,
  editorial/caption offsets, branding, sound accents, and hook fading/duration.
- Pose model initialization/inference checked in the existing local backend image.
- Frontend production build and lint of changed frontend files pass.
- Full frontend lint reports pre-existing issues in the bundled analytics script,
  `Legal.jsx`, `PricingPage.jsx`, and `consent.js`; these are outside this release.
- Windows-only full-suite failures were compared with the starting branch; the
  Linux image provides the authoritative backend validation.
- No paid model calls, publishing, or deployment performed during validation.
- Real single-/two-speaker podcast quality review remains a release acceptance step.
