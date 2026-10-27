import asyncio
import copy
import subprocess
from pathlib import Path

import pytest
from edit_project import EditError, new_project
import composition as c
import edit_llm
import longform_render
import visual_templates as templates
from test_composition import media, project  # shared encoded-media fixture


def visual(p, kind='key_point'):
    layer = {'id': 'visual', 'kind': kind, 'anchor': {'type': 'occurrence', 'segment_id': p['segments'][0]['id'],
        'source_start_ms': 1000, 'source_end_ms': 5000}}
    fields = {'key_point': {'title': 'ध्यान दें', 'text': 'Plan पहले, फिर काम करें।'},
        'comparison': {'title': 'Cost', 'labels': ['Before', 'After'], 'rows': [{'label': 'Time', 'left': '10 min', 'right': '5 min'}]},
        'process': {'title': 'Steps', 'steps': ['Plan', 'Build', 'Review']},
        'callout': {'text': 'Review this region', 'box': {'x': .5, 'y': .4, 'width': .2, 'height': .2}}}
    return {**layer, **fields[kind]}


@pytest.mark.parametrize('kind', ['key_point', 'comparison', 'process', 'callout'])
@pytest.mark.parametrize('dimensions', [(1280, 720), (720, 1280)])
def test_four_templates_multilingual_and_aspect(tmp_path, kind, dimensions):
    p = project()
    layer = c.draft(p, {**c.empty(), 'visual_layers': [visual(p, kind)]})['composition']['visual_layers'][0]
    target = tmp_path / f'{kind}.png'
    templates.raster(layer, *dimensions, target)
    from PIL import Image
    im = Image.open(target)
    assert im.size == dimensions and im.getbbox()
    assert im.getpixel((dimensions[0] // 2, dimensions[1] - 10))[3] == 0


def test_shaping_missing_glyph_and_overflow(tmp_path):
    assert templates.shaped('किरण क्षत्रिय हिन्दी', 32).getbbox()
    with pytest.raises(EditError, match='unsupported_glyph'):
        templates.shaped('🛸', 24)
    p = project()
    layer = c.draft(p, {**c.empty(), 'visual_layers': [dict(visual(p), title='W' * 150)]})['composition']['visual_layers'][0]
    with pytest.raises(EditError, match='overflow'):
        templates.raster(layer, 640, 360, tmp_path / 'bad.png')
    layer = visual(p, 'callout')
    layer['box']['x'] = .95
    with pytest.raises(EditError, match='outside_frame'):
        c.draft(p, {**c.empty(), 'visual_layers': [layer]})


def test_visual_hash_font_and_template_identity(monkeypatch):
    p = project()
    p = c.draft(p, {**c.empty(), 'visual_layers': [visual(p)]})
    before = c.identity(p)
    monkeypatch.setattr(templates, 'TEMPLATE_VERSION', 'different')
    assert before != c.identity(p)


@pytest.mark.parametrize('kind', ['key_point', 'comparison', 'process', 'callout'])
def test_real_visual_boundary_parity_and_silent_source(media, tmp_path, kind):
    source, store, asset = media
    p = project()
    p = c.draft(p, {**c.empty(), 'visual_layers': [visual(p, kind)]})
    first = asyncio.run(longform_render.render(p, source, {}, tmp_path, 'visual-preview', asset_store=store))
    second = asyncio.run(longform_render.render(p, source, {}, tmp_path, 'visual-export', asset_store=store))
    assert first['composition_hash'] == second['composition_hash']
    def pixel(file, at):
        return subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(at), '-i', str(tmp_path / file),
            '-frames:v', '1', '-vf', 'crop=2:2:20:20', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
    assert pixel(first['filename'], .5) != pixel(first['filename'], 2)
    assert pixel(first['filename'], 2) == pixel(second['filename'], 2)
    assert pixel(first['filename'], .5) == pixel(first['filename'], 5.5)
    silent = tmp_path / 'silent.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-an', '-c:v', 'copy', str(silent)], check=True)
    result = asyncio.run(longform_render.render(p, silent, {}, tmp_path, 'visual-silent', asset_store=store))
    info = asyncio.run(longform_render.probe(tmp_path / result['filename']))
    assert not any(s['codec_type'] == 'audio' for s in info['streams'])
    assert result['template_dependencies'] and result['duration_ms'] == 6000


def test_visual_model_grounding_and_manual_fallback(monkeypatch):
    t = {'segments': [{'words': [{'word': 'Plan carefully.', 'start': 0, 'end': 3}, {'word': 'Review results.', 'start': 3, 'end': 6}]}]}
    p = new_project('job', 6000, 'source', t)
    choice = {'kind': 'key_point', 'sentence_ids': ['s0'], 'title': 'Plan', 'text': 'Plan carefully.', 'steps': [], 'labels': [], 'rows': [], 'reason': 'Clarify this point'}
    async def generate(*_):
        return {'suggestions': [choice]}
    monkeypatch.setattr(edit_llm, 'generate', generate)
    result = asyncio.run(edit_llm.visual_suggestions(p, t, p['segments'][0]['id'], ['s0']))
    assert result[0]['layer']['text'] == 'Plan carefully.'
    choice['text'] = 'Save 90% with this strategy'
    assert asyncio.run(edit_llm.visual_suggestions(p, t, p['segments'][0]['id'], ['s0'])) == []
    choice['sentence_ids'] = ['invented']
    with pytest.raises(EditError, match='invalid_model_output'):
        asyncio.run(edit_llm.visual_suggestions(p, t, p['segments'][0]['id'], ['s0']))
    assert c.draft(p, {**c.empty(), 'visual_layers': [visual(p)]})
