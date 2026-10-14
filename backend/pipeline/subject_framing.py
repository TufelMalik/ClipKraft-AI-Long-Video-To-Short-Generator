"""Upper-body framing, independent of the heavy pipeline imports.

Pose detection is lazy and serialized; geometry and smoothing are pure Python.
Face boxes stay unchanged for mouth analysis and speaker identity matching.
"""
import math
import threading

_pose = None
_pose_lock = threading.Lock()


def upper_body_box(face, landmarks, width, height):
    """Enclose the head, visible shoulders, elbows and hands of THIS face.

    MediaPipe Pose returns one person. Reject a pose whose nose is not inside
    this face rather than accidentally framing the listener's body.
    """
    x, y, w, h = face
    fallback = (max(0, x - w), max(0, y - h * .2),
                min(width, x + w * 2), min(height, y + h * 3.5))
    points = []
    if landmarks and len(landmarks) >= 23:
        nose = landmarks[0]
        nx, ny = nose.x * width, nose.y * height
        if x - w * .3 <= nx <= x + w * 1.3 and y - h * .3 <= ny <= y + h * 1.3:
            for i in range(11, 23):
                p = landmarks[i]
                if p.visibility >= .55 and 0 <= p.x <= 1 and 0 <= p.y <= 1:
                    points.append((p.x * width, p.y * height))
    if not points:
        return fallback
    xs = [x, x + w] + [p[0] for p in points]
    ys = [y - h * .2, y + h] + [p[1] for p in points]
    return (max(0, min(xs) - w * .15), max(0, min(ys)),
            min(width, max(xs) + w * .15), min(height, max(ys) + h * .2))


def detect_upper_body(frame, face):
    """Use the pinned MediaPipe solutions API; keep a geometric fallback."""
    global _pose
    import cv2
    import mediapipe as mp
    height, width = frame.shape[:2]
    with _pose_lock:
        if _pose is None:
            # Stateless samples: the pipeline may alternate between clips.
            _pose = mp.solutions.pose.Pose(static_image_mode=True,
                model_complexity=1, min_detection_confidence=.5)
        result = _pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    landmarks = result.pose_landmarks.landmark if result.pose_landmarks else None
    return upper_body_box(face, landmarks, width, height)


def fill_crop(width, height, aspect, face=None, body=None):
    """Return even (w,h,x,y), filling the canvas without stretching/padding.

    Seek an eye line at 35% while enclosing the upper body. Source boundaries
    are authoritative when these constraints cannot all be satisfied.
    """
    max_h = min(height, width / aspect)
    if face is None:
        crop_h = max_h
        cx, cy = width / 2, height / 2
    else:
        x, y, w, h = face
        body = body or upper_body_box(face, None, width, height)
        bx0, by0, bx1, by1 = body
        eye_y = y + h * .35
        crop_h = min(max_h, max(h * 4, (bx1 - bx0) / aspect,
                               (by1 - eye_y) / .65, (eye_y - by0) / .35))
        cx = x + w / 2
        cy = eye_y + crop_h * .15
    ch = max(2, int(crop_h) // 2 * 2)
    cw = max(2, min(width // 2 * 2, int(ch * aspect) // 2 * 2))
    x = max(0, min(width - cw, int(cx - cw / 2))) // 2 * 2
    y = max(0, min(height - ch, int(cy - ch / 2))) // 2 * 2
    return cw, ch, x, y


class BodyCamera:
    """EMA over a 20-frame window; snap immediately at a real shot cut."""
    def __init__(self, width, height, aspect, window=20):
        self.width, self.height, self.aspect = width, height, aspect
        self.alpha = 2 / (max(1, window) + 1)
        self.target = fill_crop(width, height, aspect)
        self.current = self.target
        self.snap = True

    def begin_scene(self):
        self.snap = True
        self.target = fill_crop(self.width, self.height, self.aspect)

    def update(self, face, body=None):
        target = fill_crop(self.width, self.height, self.aspect, face, body)
        if all(math.isfinite(v) for v in target):
            self.target = target

    def box(self):
        if self.snap:
            self.current, self.snap = self.target, False
        else:
            self.current = tuple(a + self.alpha * (b - a)
                                 for a, b in zip(self.current, self.target))
        w, h, x, y = (int(v) // 2 * 2 for v in self.current)
        # Recompute width from smoothed height to preserve the output aspect.
        h = max(2, min(h, self.height // 2 * 2))
        w = max(2, min(int(h * self.aspect) // 2 * 2, self.width // 2 * 2))
        return w, h, max(0, min(x, self.width - w)), max(0, min(y, self.height - h))


def fill_filtergraph(out_w, out_h):
    return (f"[0:v]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},setsar=1[v]")


def lock_scene_lens(boxes, width, height, aspect):
    """Keep lens size fixed within a shot; move only x/y.

    FFmpeg reinitializes downstream filters when crop dimensions change,
    discarding buffered frames. Choose a lens that fits the widest observed
    body, then follow its eye line with the already-smoothed trajectory.
    """
    h = max(b[1] for b in boxes)
    w = min(width // 2 * 2, int(h * aspect) // 2 * 2)
    return [(w, h,
             max(0, min(width-w, int(x + bw/2 - w/2))) // 2 * 2,
             max(0, min(height-h, int(y + bh*.35 - h*.35))) // 2 * 2)
            for bw, bh, x, y in boxes]
