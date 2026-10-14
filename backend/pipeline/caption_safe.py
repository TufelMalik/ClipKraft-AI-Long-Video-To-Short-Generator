"""Face-aware caption anchors in normalized output-frame coordinates."""
from hook_placement import face_cost

BANDS = {'bottom':(.70,.88),'middle':(.42,.58),'top':(.10,.28)}


def safe_alignment(frames, preferred='bottom'):
    def cost(name):
        a,b = BANDS[name]
        return face_cost((.08,a,.92,b),frames)
    if cost(preferred) == 0:
        return preferred
    return min(BANDS,key=lambda name:(cost(name),name != preferred))


def placement_ranges(video_path, ranges, duration):
    from hook_placement import detect_faces
    windows = ranges or [{'start':0,'end':duration,'layout':'track'}]
    output = []
    for r in windows:
        start,end = r['start'],min(r['end'],duration)
        # Recheck long shots so a speaker leaning down moves the captions.
        while start < end:
            stop = min(end,start+3)
            frames = detect_faces(video_path,start,stop)
            preferred = 'middle' if r.get('layout') == 'split' else 'bottom'
            output.append((start,stop,safe_alignment(frames,preferred)))
            start = stop
    return output
