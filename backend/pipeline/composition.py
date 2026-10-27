"""Opt-in composition schema and identity. No defaults are written to v1 projects."""
import copy
from typing import Literal, Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from edit_project import EditError, digest
from timeline_map import timeline

RENDERER_VERSION = 'composition-2'


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class OutputAnchor(Model):
    type: Literal['output']
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    base_revision: int = Field(ge=0)


class OccurrenceAnchor(Model):
    type: Literal['occurrence']
    segment_id: str = Field(min_length=1, max_length=100)
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(gt=0)


Anchor = Annotated[OutputAnchor | OccurrenceAnchor, Field(discriminator='type')]


class Voice(Model):
    cleanup: Literal['off', 'gentle'] = 'off'
    gain_db: float = Field(default=0, ge=-60, le=12, allow_inf_nan=False)


class AudioTrack(Model):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal['music', 'sfx']
    asset_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    asset_version: int = Field(ge=1)
    asset_in_ms: int = Field(default=0, ge=0)
    anchor: Anchor
    gain_db: float = Field(default=-18, ge=-60, le=6, allow_inf_nan=False)
    fade_in_ms: int = Field(default=0, ge=0, le=10000)
    fade_out_ms: int = Field(default=0, ge=0, le=10000)
    loop: bool = False
    duck_under_voice: bool = False
    enabled: bool = True
    needs_review: bool = False


Text = Annotated[str, Field(min_length=1, max_length=160)]


class VisualBase(Model):
    id: str = Field(min_length=1, max_length=100)
    template_version: Literal[1] = 1
    anchor: OccurrenceAnchor
    position: Literal['upper_third', 'center', 'upper_left', 'upper_right'] = 'upper_third'
    size: Literal['small', 'medium', 'large'] = 'medium'
    theme: Literal['dark', 'light'] = 'dark'
    transition_ms: int = Field(default=200, ge=0, le=500)
    enabled: bool = True
    needs_review: bool = False
    sentence_ids: list[str] = Field(default_factory=list, max_length=4)
    proposal_id: str | None = None


class KeyPoint(VisualBase):
    kind: Literal['key_point']
    title: Text
    text: Text


class ComparisonRow(Model):
    label: Text
    left: Text
    right: Text


class Comparison(VisualBase):
    kind: Literal['comparison']
    title: Text
    labels: list[Text] = Field(min_length=2, max_length=2)
    rows: list[ComparisonRow] = Field(min_length=1, max_length=3)


class Process(VisualBase):
    kind: Literal['process']
    title: Text
    steps: list[Text] = Field(min_length=2, max_length=4)


class Box(Model):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    width: float = Field(gt=0, le=1, allow_inf_nan=False)
    height: float = Field(gt=0, le=1, allow_inf_nan=False)


class Callout(VisualBase):
    kind: Literal['callout']
    text: Text
    box: Box


class Broll(Model):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal['broll']
    anchor: OccurrenceAnchor
    asset_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    asset_version: int = Field(ge=1)
    asset_in_ms: int = Field(default=0, ge=0)
    mode: Literal['cover', 'inset'] = 'cover'
    fit: Literal['contain', 'crop'] = 'contain'
    position: Literal['upper_left', 'upper_right'] = 'upper_right'
    crop_x: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    crop_y: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    loop: bool = False
    freeze: bool = False
    enabled: bool = True
    needs_review: bool = False
    sentence_ids: list[str] = Field(default_factory=list, max_length=4)
    proposal_id: str | None = None


Visual = Annotated[KeyPoint | Comparison | Process | Callout | Broll, Field(discriminator='kind')]


class Composition(Model):
    version: Literal[1] = 1
    voice: Voice = Field(default_factory=Voice)
    audio_tracks: list[AudioTrack] = Field(default_factory=list, max_length=8)
    visual_layers: list[Visual] = Field(default_factory=list, max_length=16)
    loudness_lufs: float = Field(default=-16, ge=-24, le=-14, allow_inf_nan=False)
    visual_signature: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


def empty():
    return Composition().model_dump()


def layers(project):
    c = project.get('composition', {})
    return c.get('audio_tracks', []) + c.get('visual_layers', [])


def resolve(project, anchor):
    if anchor['type'] == 'output':
        a, b = anchor['start_ms'], anchor['end_ms']
    else:
        seg = next((s for s in timeline(project['segments']) if s['id'] == anchor['segment_id']), None)
        a, b = anchor['source_start_ms'], anchor['source_end_ms']
        if not seg or not seg['source_start_ms'] <= a < b <= seg['source_end_ms']:
            raise EditError('anchor_needs_review')
        a, b = a + seg['output_start_ms'] - seg['source_start_ms'], b + seg['output_start_ms'] - seg['source_start_ms']
    if not 0 <= a < b <= project['duration_ms']:
        raise EditError('anchor_needs_review')
    return a, b


def validate(project):
    version = project.get('schema_version', 1)
    if version not in (1, 2) or version == 1 and 'composition' in project:
        raise EditError('unsupported_project_schema')
    if version == 1:
        return project
    try:
        project['composition'] = Composition.model_validate(project['composition']).model_dump()
    except (ValidationError, KeyError) as e:
        raise EditError('invalid_composition') from e
    seen, covers = set(), []
    if sum(x['kind'] == 'broll' and x['enabled'] for x in layers(project)) > 4:
        raise EditError('maximum_four_enabled_broll_layers')
    for layer in layers(project):
        if layer['id'] in seen:
            raise EditError('duplicate_layer_id')
        seen.add(layer['id'])
        if layer['kind'] == 'callout':
            box = layer['box']
            if box['x'] + box['width'] > 1 or box['y'] + box['height'] > 1:
                raise EditError('callout_outside_frame')
        if layer['needs_review']:
            continue
        a, b = resolve(project, layer['anchor'])
        if layer['kind'] == 'broll':
            if layer['loop'] and layer['freeze']:
                raise EditError('choose_loop_or_freeze')
            if layer['enabled'] and layer['mode'] == 'cover':
                if any(a < y and b > x for x, y in covers):
                    raise EditError(f'overlapping_broll_covers:{a}-{b}')
                covers.append((a, b))
        if layer.get('fade_in_ms', 0) + layer.get('fade_out_ms', 0) > b - a:
            raise EditError('fades_exceed_track')
        if layer.get('transition_ms', 0) * 2 > b - a:
            raise EditError('transition_exceeds_layer')
    return project


def audio_active(project):
    c = project.get('composition', empty())
    return c['voice'] != empty()['voice'] or c['loudness_lufs'] != empty()['loudness_lufs'] or any(x['enabled'] for x in c['audio_tracks'])


def active(project):
    return audio_active(project) or any(x['enabled'] for x in layers(project))


def reconcile(before, after):
    """Only explicit split lineage may move content-linked layers to new occurrences."""
    if before['segments'] == after['segments'] or 'composition' not in after:
        return after
    old = {s['id']: s for s in before['segments']}
    previous_layers = {layer['id']: layer for layer in layers(before)}
    for layer in layers(after):
        anchor = layer['anchor']
        if anchor['type'] == 'output':
            # Even equal-duration reorders change what a soundtrack accompanies.
            layer['needs_review'] = True
            continue
        prior = previous_layers.get(layer['id'], layer)['anchor']
        candidates = [s for s in after['segments'] if (s['id'] == prior['segment_id'] or
            prior['segment_id'] in s.get('lineage', [])) and prior['segment_id'] in old and
            s['source_start_ms'] <= anchor['source_start_ms'] < anchor['source_end_ms'] <= s['source_end_ms']]
        if len(candidates) == 1:
            anchor['segment_id'] = candidates[0]['id']
        else:
            layer['needs_review'] = True
    return after


def identity(project, dependencies=()):
    visual_dependencies = []
    if any(x['enabled'] and x['kind'] not in ('music', 'sfx', 'broll') for x in layers(project)):
        from visual_templates import dependencies as template_dependencies
        visual_dependencies = template_dependencies()
    return digest({'segments': project['segments'], 'source': project['source'],
        'transcript_version': project['transcript_version'], 'composition': project.get('composition', empty()),
        'dependencies': list(dependencies) + visual_dependencies, 'renderer': RENDERER_VERSION})


def draft(project, value):
    p = copy.deepcopy(project)
    p.update(schema_version=2, composition=value)
    validate(p)
    if any(x['enabled'] and x['kind'] != 'broll' for x in p['composition']['visual_layers']):
        from visual_templates import dependencies
        p['composition']['visual_signature'] = digest(dependencies())
    else:
        p['composition']['visual_signature'] = None
    return p
