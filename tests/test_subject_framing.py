from types import SimpleNamespace

from subject_framing import BodyCamera, fill_crop, fill_filtergraph, upper_body_box


def test_crop_fills_without_padding_and_keeps_eye_line():
    face = (870, 260, 180, 180)
    box = fill_crop(1920, 1080, 9/16, face, (760, 224, 1160, 750))
    w, h, x, y = box
    assert abs(w/h - 9/16) < .005
    assert abs((260 + 180*.35 - y)/h - .35) < .01
    assert all(v % 2 == 0 for v in box)
    assert x <= face[0] and x+w >= face[0]+face[2]


def test_portrait_and_edge_crops_stay_inside_source():
    for width, height in [(1920, 1080), (720, 1280), (1080, 2400)]:
        for face in [None, (0, 0, 100, 100), (width-100, height-100, 100, 100)]:
            w, h, x, y = fill_crop(width, height, 9/16, face)
            assert 0 <= x <= width-w and 0 <= y <= height-h
            assert w > 0 and h > 0


def test_pose_of_listener_is_not_attached_to_speaker():
    face = (100, 100, 100, 100)
    points = [SimpleNamespace(x=.9, y=.9, visibility=1)]*33
    assert upper_body_box(face, points, 1920, 1080) == upper_body_box(face, None, 1920, 1080)


def test_camera_smooths_motion_but_snaps_at_cut():
    camera = BodyCamera(1920, 1080, 9/16)
    camera.update((400, 100, 120, 120))
    first = camera.box()
    camera.update((900, 100, 120, 120))
    moved = camera.box()
    assert first[2] < moved[2] < camera.target[2]
    camera.begin_scene()
    camera.update((1100, 100, 120, 120))
    assert camera.box() == camera.target


def test_fill_graph_has_no_blur_or_padding():
    graph = fill_filtergraph(1080, 1920)
    assert 'force_original_aspect_ratio=increase' in graph
    assert 'crop=1080:1920' in graph
    assert 'blur' not in graph and 'pad=' not in graph
