# Shorts quality implementation plan

## Goal and boundaries

Improve standalone moment selection, spoken openings and complete-story pacing.
Editorial scores are estimates, never guarantees of views. Preserve the default
pipeline, API response schemas, stored projects, source files, caption styles,
hook replacement, manual recut/reframe, layouts, watermarking and export.

Base: main at 89cb754. Work branch: codex/shorts-quality. No bulk merge from
release/v2: its editorial and moment-signal work is useful reference, but includes
unrelated rendering, UI, speaker and channel changes requiring separate review.

## Current architecture

Transcript windows are scored by gemini_worker, shortlisted globally by main,
then detailed into clips. clip_selection snaps to words, enforces durations and
deduplicates. Existing prompts already request context, a strong opening and a
payoff. Strengthen these stages before introducing another model request.

## Ordered milestones and release gates

1. Baseline: capture focused tests, then broader compatibility checks. Before
   enabling improved mode, render the same representative source in both modes.
   Cover talking head, interview, tutorial, Hindi/English, weak transcript and
   silent visual footage. Save inputs/settings and compare continuity and sync.
2. Selection pilot: explicit SHORTS_SELECTION_QUALITY=v1 adds grounded quality
   guidance to transcript score/detail prompts only. Default and unknown values
   leave prompt text unchanged. No additional calls, schema or renderer changes.
   Existing parsing/retry/error handling remains; this phase does not claim an
   automatic second request with the legacy prompt on model failure.
3. Validated review: add optional source-grounded review records (opening,
   context, payoff, reason and original timings). Validate finite timestamps,
   source/window/duration bounds and actual transcript evidence. Reject invalid
   proposals and preserve the original candidate; never drop all usable clips.
   Keep optional fields backward compatible and exclude unvalidated AI edits.
4. Opening/story boundaries: bounded continuous trims before rendering, using
   word timestamps and sentence context. Preserve qualifications, speakers and
   payoff. Missing/uncertain word data means keep original timings. Store original
   and accepted timing provenance. Do not reorder speech or extend beyond source.
5. Pacing: separately gated internal pause/repetition edits. First establish a
   shared source-to-output timeline mapping for subtitles, layout ranges, hooks,
   recut and reframe. Reuse reviewed v2 code only where its contracts fit. On
   assembly failure, preserve clean original clip; publish only complete files.
6. Rollout: review old/new videos, latency, token usage and rejection reasons.
   Require relevant tests, compatibility checks and actual playback before merge
   and default changes. Disable the flag and restart for initial pilot rollback.

## Verification criteria

- Legacy mode follows the same selection prompts and render path.
- Selected words remain complete; captions align with audible speech after edits.
- Meaning, necessary setup and promised payoff survive; manual review required.
- Existing caption presets, hook add/remove, source recut, framing, exports and
  legacy metadata work. Visual-only selection bypasses transcript improvements.
- Malformed model output, timeouts and unavailable transcript data do not gain
  new failure modes. Test validation/fallback explicitly in later milestones.
- Track channel results only after publication; offline scores cannot establish
  growth. Compare relative channel performance without universal viral thresholds.

## Initial evidence

108 existing focused tests passed on the unmodified feature branch (selection,
generation controls, recut, hook grounding, edit builder). Windows sandbox temp
creation initially caused seven fixture errors; using a workspace basetemp fixed
them. Full suite and real AI/video export verification remain outstanding.

After the pilot change, 127 focused tests passed, including 19 new opt-in/default
checks. git diff --check passed. A broader selection including Gemini retry and
render helpers stalled after initial progress and was interrupted; it is not a
passing result and needs isolated investigation before release.

## Immediate implementation

Milestone 2 is an opt-in prompt pilot with no new render behavior. Next inspect
broader tests/import compatibility, then implement validated review and boundary
proposals with meaningful regression tests. Never enable v1 by editing the user's
private .env automatically. No commit/push or release-v2 merge is implied.
