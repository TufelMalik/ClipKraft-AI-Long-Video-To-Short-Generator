"""Four bounded Pillow templates with explicit HarfBuzz/FreeType text shaping.

Mixed Latin/Devanagari runs are shaped separately. No browser font substitution,
external font lookup, executable text, or silent unsupported-glyph replacement.
"""
import functools
import math
import re
from pathlib import Path
from PIL import Image, ImageDraw
from edit_project import EditError
from longform_render import fingerprint

ROOT = Path(__file__).resolve().parents[2] / 'fonts'
FONTS = {'latin': ROOT / 'NotoSans-Regular.ttf', 'deva': ROOT / 'NotoSansDevanagari-Regular.ttf'}
TEMPLATE_VERSION = 'static-templates-1'


def support():
    try:
        import uharfbuzz  # noqa: F401
        import freetype  # noqa: F401
        return all(p.is_file() for p in FONTS.values())
    except ImportError:
        return False


def dependencies():
    if not support():
        raise EditError('visual_shaping_unavailable_install_longform_requirements')
    import uharfbuzz as hb
    import freetype
    return [{'template': TEMPLATE_VERSION, 'harfbuzz': hb.version_string(), 'freetype': list(freetype.version())},
        *[{'font': p.name, 'checksum': fingerprint(p)} for p in FONTS.values()]]


def runs(text):
    result, current, script = [], '', 'latin'
    for ch in text:
        next_script = 'deva' if '\u0900' <= ch <= '\u097f' else script if ch.isspace() else 'latin'
        if next_script != script and current:
            result.append((script, current))
            current = ''
        current += ch
        script = next_script
    if current:
        result.append((script, current))
    return result


def shaped(text, size):
    import uharfbuzz as hb
    import freetype
    glyphs, pen = [], 0.0
    for script, value in runs(text):
        font_path = FONTS[script]
        font = hb.Font(hb.Face(font_path.read_bytes()))
        hb.ot_font_set_funcs(font)
        font.scale = (size * 64, size * 64)
        buf = hb.Buffer()
        buf.add_str(value)
        buf.guess_segment_properties()
        buf.direction = 'ltr'
        buf.script = 'deva' if script == 'deva' else 'latn'
        hb.shape(font, buf)
        face = freetype.Face(str(font_path))
        face.set_pixel_sizes(0, size)
        for info, position in zip(buf.glyph_infos, buf.glyph_positions):
            if info.codepoint == 0:
                raise EditError('unsupported_glyph_use_english_or_devanagari')
            face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
            bitmap = face.glyph.bitmap
            if bitmap.width and bitmap.rows:
                mask = Image.frombytes('L', (bitmap.width, bitmap.rows), bytes(bitmap.buffer), 'raw', 'L', bitmap.pitch)
                x = round(pen + position.x_offset / 64 + face.glyph.bitmap_left)
                y = round(-position.y_offset / 64 - face.glyph.bitmap_top)
                glyphs.append((mask, x, y))
            pen += position.x_advance / 64
    if not glyphs:
        return Image.new('L', (max(1, math.ceil(pen)), size))
    left = min(0, *(x for _, x, _ in glyphs))
    top = min(y for _, _, y in glyphs)
    right = max(math.ceil(pen), *(x + mask.width for mask, x, _ in glyphs))
    bottom = max(y + mask.height for mask, _, y in glyphs)
    result = Image.new('L', (right - left + 2, bottom - top + 2))
    # Union glyph coverage: overlapping marks must not erase earlier glyphs.
    from PIL import ImageChops
    for mask, x, y in glyphs:
        layer = Image.new('L', result.size)
        layer.paste(mask, (x - left + 1, y - top + 1))
        result = ImageChops.lighter(result, layer)
    return result


def block(canvas, text, rect, size, color):
    x, y, width, height = rect
    words = text.split()
    lines, line = [], ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if shaped(candidate, size).width > width:
            if not line or shaped(word, size).width > width:
                raise EditError('visual_text_overflow_shorten_text_or_reduce_size')
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    masks = [shaped(line, size) for line in lines]
    gap = max(3, round(size * .35))
    if sum(max(mask.height, size) + gap for mask in masks) - gap > height:
        raise EditError('visual_text_overflow_shorten_text_or_reduce_size')
    for mask in masks:
        canvas.paste(color, (x, y, x + mask.width, y + mask.height), mask)
        y += max(mask.height, size) + gap


def raster(layer, width, height, target):
    if not support():
        raise EditError('visual_shaping_unavailable_install_longform_requirements')
    if width * height > 16000000 or min(width, height) < 90:
        raise EditError('visual_frame_dimensions_unsupported')
    canvas = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(canvas)
    dark = layer['theme'] == 'dark'
    background, foreground, accent = ((18, 24, 38, 240), (255, 255, 255, 255), (255, 190, 80, 255)) if dark else ((250, 248, 240, 245), (20, 30, 45, 255), (28, 80, 135, 255))
    factor = {'small': .85, 'medium': 1, 'large': 1.2}[layer['size']]
    size = max(8, round(min(width, height) * .043 * factor))
    margin = max(6, round(width * .05))
    padding = max(5, round(min(width, height) * .035))
    card_w = width - margin * 2
    if layer['position'] in ('upper_left', 'upper_right'):
        card_w = round(card_w * .7)
    card_h = round(height * (.49 if layer['kind'] in ('comparison', 'process') else .28))
    x = width - margin - card_w if layer['position'] == 'upper_right' else margin
    y = round(height * (.22 if layer['position'] == 'center' else .06))
    if y + card_h > height * .74:
        raise EditError('visual_layout_exceeds_safe_region')
    draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=max(4, size // 2), fill=background)
    draw.rectangle((x, y + padding, x + max(3, size // 6), y + card_h - padding), fill=accent)
    title_height = round(size * 2.8)
    if layer['kind'] == 'key_point':
        block(canvas, layer['title'], (x + padding, y + padding, card_w - 2 * padding, title_height), size, accent)
        block(canvas, layer['text'], (x + padding, y + padding + title_height, card_w - 2 * padding, card_h - title_height - padding * 2), size, foreground)
    elif layer['kind'] == 'process':
        block(canvas, layer['title'], (x + padding, y + padding, card_w - 2 * padding, title_height), size, accent)
        row_h = (card_h - title_height - 2 * padding) // len(layer['steps'])
        for i, text in enumerate(layer['steps']):
            block(canvas, f'{i + 1}. {text}', (x + padding, y + padding + title_height + i * row_h, card_w - padding * 2, row_h), size, foreground)
    elif layer['kind'] == 'comparison':
        block(canvas, layer['title'], (x + padding, y + padding, card_w - 2 * padding, title_height), size, accent)
        col_w = (card_w - padding * 4) // 3
        row_h = (card_h - title_height - 2 * padding) // (len(layer['rows']) + 1)
        rows = [['', *layer['labels']], *[[r['label'], r['left'], r['right']] for r in layer['rows']]]
        for i, row in enumerate(rows):
            for j, text in enumerate(row):
                if text:
                    block(canvas, text, (x + padding + j * (col_w + padding), y + padding + title_height + i * row_h, col_w, row_h), max(8, round(size * .85)), accent if i == 0 else foreground)
    else:
        block(canvas, layer['text'], (x + padding, y + padding, card_w - padding * 2, card_h - padding * 2), size, foreground)
        b = layer['box']
        box = (round(b['x'] * width), round(b['y'] * height), round((b['x'] + b['width']) * width) - 1, round((b['y'] + b['height']) * height) - 1)
        draw.rectangle(box, outline=accent, width=max(2, size // 8))
        tip = ((box[0] + box[2]) // 2, box[1])
        draw.line(((x + card_w // 2, y + card_h), tip), fill=accent, width=max(2, size // 8))
        draw.polygon([tip, (tip[0] - size // 3, tip[1] - size // 2), (tip[0] + size // 3, tip[1] - size // 2)], fill=accent)
    canvas.save(target)
    return target
