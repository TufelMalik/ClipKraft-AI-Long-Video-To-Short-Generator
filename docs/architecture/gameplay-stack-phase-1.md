# Gameplay Stack — Phase 1 Plan

Status: plan only. No feature code is part of this document.

Phase 1 builds the preview. Two local videos play together in a 9:16 stack. Nothing is uploaded, transcribed, or exported.

## 1. What this phase delivers

A new **Gameplay** tab in the existing ClipKraft dashboard.

The user loads a facecam file and a gameplay file from disk. The preview shows:

- A 9:16 frame.
- The facecam in the top band. Default split is 30% facecam, 70% gameplay. The facecam share can move from 10% to 50%.
- The gameplay in the bottom band, taken from a 9:16 window on the 16:9 source.
- That window slides left and right. The position is one number for the whole preview, from 0 (left) to 1 (right). Default is centered.
- A divider on the boundary: none, solid, gradient, or glow, with a color and a thickness.
- One play button, one scrubber. Both videos share one clock.

The existing Clip Generator, manual clip tab, reframing, and Remotion short player stay as they are.

## 2. Geometry

The attached frame drawing is the rule. The red 9:16 rectangle is the short. It slides across the 16:9 gameplay. The facecam replaces the top of that rectangle. The gameplay the viewer sees is the rest of the same rectangle.

For a gameplay frame of width `W` and height `H`:

- Window height is `H` (the full frame).
- Window width is `H * 9 / 16`.
- If `W` is already less than or equal to that width, the window is the whole frame and the drag has no travel.
- Otherwise the left edge is `frameCropX * (W - windowWidth)`.
- `frameCropX` is 0 at the left edge, 0.5 at the center, and 1 at the right edge.

On a 1920×1080 gameplay frame the window is 607.5×1080. At the center its left edge is 656.25.

The preview is a fixed 9:16 stage (360×640 CSS pixels). `splitRatio` is the facecam share, default 0.30.

- Facecam band: full stage width, height `stageHeight * splitRatio`. The facecam image is cover-cropped and centered. Phase 1 does not follow the face.
- Gameplay band: the remainder of the stage. It shows only the bottom `(1 - splitRatio)` of the 9:16 window, scaled to fill the band. The top of the window is hidden behind the facecam. The picture is not stretched.
- Divider: drawn on the boundary, centered on it. Thickness is specified in reference pixels at a 1080-wide stage and scaled to the preview.

The frame selector shows the full gameplay picture, darkens everything outside the 9:16 window, and draws a line inside the window at `splitRatio` so the covered strip is visible. Dragging moves X only.

## 3. Files

New:

| File | Role |
|---|---|
| `dashboard/src/components/gameplay/stackMath.js` | Pure functions: window size, crop X, band heights, source rectangle for the gameplay band. No React. |
| `dashboard/src/components/gameplay/stackMath.test.mjs` | Node tests for those functions, including a 1920×1080 center crop and a source that is already too narrow to slide. |
| `dashboard/src/components/gameplay/GameplayStackTab.jsx` | Tab shell: file pickers, controls, playback state. |
| `dashboard/src/components/gameplay/StackPreview.jsx` | The 9:16 stage. Two hidden `<video>` elements. One canvas draws the stack. |
| `dashboard/src/components/gameplay/FrameSelector.jsx` | The 16:9 strip with the draggable 9:16 window. |

Edited:

| File | Change |
|---|---|
| `dashboard/src/App.jsx` | Add a **Gameplay** nav item and render `GameplayStackTab` when that tab is active. No other tab changes. |

No Python, FFmpeg, Remotion, or job-queue changes in this phase. The Remotion `ShortVideo` composition stays a single-video preview. Captions land on this stack in a later phase.

## 4. Behaviour I will implement

**Loading.** Each picker accepts `mp4`, `webm`, `mov`, and `mkv`. The browser reads the file through an object URL. Duration, width, and height come from the `<video>` element. The file is not sent to the API.

**Playback.** Gameplay time is the clock. Play and pause set both elements. On each frame the facecam is seeked only when it has drifted by more than 0.15 seconds. A scrub of the shared bar seeks both. Playback stops at the shorter duration. The UI shows both durations and, when they differ, which file ends first.

**Split.** A slider from 10 to 50, labeled as facecam/gameplay (for example `30 / 70`). The preview and the line inside the frame selector update while the slider moves.

**Divider.** Four choices: none, solid, gradient, glow. Solid and glow use the chosen color. Thickness runs from 0 to 16 reference pixels. Gradient fades the facecam band into the gameplay band across that thickness. Glow is a soft line of the chosen color. None draws a hard cut.

**Frame position.** Dragging the window, or a matching 0–100% slider, sets `frameCropX`. The preview uses the new crop on the next drawn frame.

**Empty state.** Before both files are chosen, the stage shows two labeled slots. Controls that need a file stay disabled.

## 5. What I will verify

- `node --test dashboard/src/components/gameplay/stackMath.test.mjs` passes.
- `npm run lint` in `dashboard/` passes.
- In the browser: load two files, press play, and confirm both pictures move together.
- Drag the window to the left edge, the center, and the right edge, and confirm the gameplay band matches.
- Move the split slider and confirm the bands and the selector line move together.
- Switch divider style, color, and thickness, and confirm the preview updates without a reload.
- Scrub, pause, and play again, and confirm the two videos stay on the same timestamp.
- Open Clip Generator and confirm that tab is unchanged.

## 6. Out of this phase

These stay in later phases and will not be stubbed into the Phase 1 UI:

- Caption transcription, Hormozi rendering, and the caption Y slider.
- Green screen, background image, solid-color replacement, face centering, and shape masks.
- Export, FFmpeg, audio mixing, watermark, presets, and GTA labels.
- Manual timestamps, audio-peak detection, batch export, montage, and YouTube live-chat peaks.
- Upload of either file to the backend.
