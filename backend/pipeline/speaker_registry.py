"""Persistent shot-local face tracks, velocity prediction and occlusion hold.

These are observed track IDs, not verified identities across camera angles.
"""
import math


class SpeakerRegistry:
    def __init__(self, max_missing=30):
        self.tracks, self.next_id, self.max_missing = {}, 0, max_missing

    def update(self, boxes, frame):
        available, result = set(self.tracks), []
        for box in sorted(boxes, key=lambda b: b[2]*b[3], reverse=True):
            x, y, w, h = box
            cx, cy = x+w/2, y+h/2
            candidates = []
            for key in available:
                t = self.tracks[key]
                if frame-t['frame'] > self.max_missing:
                    continue
                bx, by, bw, bh = t['box']
                dt = frame-t['frame']
                distance = math.hypot(cx-bx-bw/2-t['vx']*dt,
                                      cy-by-bh/2-t['vy']*dt)
                if distance <= max(w,h,bw,bh)*1.2:
                    candidates.append((distance,key))
            if candidates:
                _, key = min(candidates)
                available.remove(key)
                previous = self.tracks[key]
                bx, by, bw, bh = previous['box']
                dt = max(1,frame-previous['frame'])
                vx, vy = (cx-bx-bw/2)/dt, (cy-by-bh/2)/dt
            else:
                key, vx, vy = self.next_id, 0, 0
                self.next_id += 1
            self.tracks[key] = {'id':key, 'box':tuple(box), 'vx':vx, 'vy':vy, 'frame':frame}
            result.append(self.tracks[key].copy())
        return result

    def predict(self, key, frame):
        t = self.tracks.get(key)
        if not t or frame-t['frame'] > self.max_missing:
            return None
        x,y,w,h = t['box']
        dt = frame-t['frame']
        return x+t['vx']*dt, y+t['vy']*dt, w,h
