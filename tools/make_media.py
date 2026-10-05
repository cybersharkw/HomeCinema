"""Erzeugt die Grafiken für Skin und Add-on (reines Python, keine Zusatzpakete).

Ausführen: py tools/make_media.py
"""
import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIN_MEDIA = os.path.join(ROOT, "skin.homecinema", "media", "hc")
ADDON_RES = os.path.join(ROOT, "script.homecinema", "resources")
SKIN_RES = os.path.join(ROOT, "skin.homecinema", "resources")

GOLD = (229, 176, 74)
RED = (179, 18, 31)
DARK = (10, 10, 12)


class Image:
    def __init__(self, width, height, fill=(0, 0, 0, 0)):
        self.w, self.h = width, height
        self.px = [list(fill) for _ in range(width * height)]

    def blend(self, x, y, color, alpha):
        """Alpha-Compositing (Quelle über Ziel), alpha 0..1."""
        if alpha <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        dst = self.px[y * self.w + x]
        sa = alpha * (color[3] / 255.0 if len(color) > 3 else 1.0)
        da = dst[3] / 255.0
        out_a = sa + da * (1 - sa)
        if out_a <= 0:
            return
        for i in range(3):
            dst[i] = int(round((color[i] * sa + dst[i] * da * (1 - sa)) / out_a))
        dst[3] = int(round(out_a * 255))

    def set(self, x, y, rgba):
        self.px[y * self.w + x] = list(rgba)

    def paste(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                p = other.px[y * other.w + x]
                if p[3]:
                    self.blend(ox + x, oy + y, p[:3], p[3] / 255.0)

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        raw = bytearray()
        for y in range(self.h):
            raw.append(0)
            for x in range(self.w):
                raw.extend(bytes(max(0, min(255, int(v))) for v in self.px[y * self.w + x]))

        def chunk(tag, data):
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        png += chunk(b"IEND", b"")
        with open(path, "wb") as handle:
            handle.write(png)


def coverage(inside, x, y, samples=4):
    hits = 0
    for sy in range(samples):
        for sx in range(samples):
            if inside(x + (sx + 0.5) / samples, y + (sy + 0.5) / samples):
                hits += 1
    return hits / float(samples * samples)


def fill_shape(img, inside, color, box=None):
    x0, y0, x1, y1 = box or (0, 0, img.w, img.h)
    for y in range(max(0, y0), min(img.h, y1)):
        for x in range(max(0, x0), min(img.w, x1)):
            c = coverage(inside, x, y)
            if c:
                img.blend(x, y, color, c)


def polygon_test(points):
    def inside(px, py):
        result = False
        j = len(points) - 1
        for i, (xi, yi) in enumerate(points):
            xj, yj = points[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                result = not result
            j = i
        return result
    return inside


def star_points(cx, cy, outer, inner):
    pts = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        angle = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


# ---------------------------------------------------------------- Sterne
def make_stars():
    size = 80
    star = polygon_test(star_points(size / 2, size / 2 + 3, size * 0.47, size * 0.19))
    full, empty = Image(size, size), Image(size, size)
    fill_shape(full, star, GOLD + (255,))
    fill_shape(empty, star, (255, 255, 255, 60))
    half = Image(size, size)
    fill_shape(half, lambda x, y: star(x, y) and x >= size / 2, (255, 255, 255, 60))
    fill_shape(half, lambda x, y: star(x, y) and x < size / 2, GOLD + (255,))
    for value in range(11):  # Kodi-Bewertung 0..10 -> 0..5 Sterne
        row = Image(size * 5, size)
        for i in range(5):
            filled = value - i * 2
            row.paste(full if filled >= 2 else half if filled == 1 else empty, i * size, 0)
        row.save(os.path.join(SKIN_MEDIA, "stars{}.png".format(value)))


# ---------------------------------------------------------------- Vorhang
def curtain(width, height, mirror=False):
    img = Image(width, height)
    folds = 7.0
    for y in range(height):
        sag = 1.0 - 0.12 * (y / height) ** 2  # Falten laufen unten leicht zusammen
        for x in range(width):
            u = (width - 1 - x if mirror else x) / float(width)
            phase = u * folds * math.pi * sag
            light = 0.35 + 0.65 * abs(math.sin(phase)) ** 0.7
            light *= 0.75 + 0.25 * (1 - y / height)
            edge = (1 - u) if not mirror else u
            light *= 0.55 + 0.45 * min(1.0, (1 - abs(0.5 - u) * 2) * 3 + 0.2)
            color = (int(RED[0] * light + 20 * light ** 3), int(RED[1] * light), int(RED[2] * light), 255)
            img.set(x, y, color)
        # goldene Borte am inneren Rand
        border_x = range(width - 10, width) if not mirror else range(0, 10)
        for x in border_x:
            img.set(x, y, GOLD + (255,))
    return img


# ---------------------------------------------------------------- Verläufe & Licht
def gradient(width, height, horizontal, start_alpha, end_alpha, color=(0, 0, 0)):
    img = Image(width, height)
    steps = width if horizontal else height
    for i in range(steps):
        t = i / float(steps - 1)
        a = start_alpha + (end_alpha - start_alpha) * (t * t * (3 - 2 * t))
        for j in range(height if horizontal else width):
            x, y = (i, j) if horizontal else (j, i)
            img.set(x, y, color + (int(a),))
    return img


def spotlight(size):
    img = Image(size, size)
    c = size / 2.0
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - c, y - c) / c
            a = max(0.0, 1 - d) ** 2.2
            img.set(x, y, (255, 240, 210, int(255 * a)))
    return img


def light_cone(width, height):
    """Projektorlicht: Kegel von oben, nach unten breiter und schwächer."""
    img = Image(width, height)
    for y in range(height):
        t = y / float(height)
        half = width * (0.06 + 0.44 * t)
        for x in range(width):
            d = abs(x - width / 2.0) / half if half else 1
            if d < 1:
                a = (1 - d) ** 1.5 * (1 - t) ** 0.6 * 0.55
                img.set(x, y, (255, 236, 200, int(255 * a)))
    return img


def rounded_rect(width, height, radius, stroke=None, color=(255, 255, 255, 255)):
    def inside_rr(px, py, inset=0.0):
        x0, y0, x1, y1 = inset, inset, width - inset, height - inset
        r = max(0.0, radius - inset)
        if not (x0 <= px <= x1 and y0 <= py <= y1):
            return False
        cx = min(max(px, x0 + r), x1 - r)
        cy = min(max(py, y0 + r), y1 - r)
        return (px - cx) ** 2 + (py - cy) ** 2 <= r * r

    img = Image(width, height)
    if stroke:
        fill_shape(img, lambda x, y: inside_rr(x, y) and not inside_rr(x, y, stroke), color)
    else:
        fill_shape(img, inside_rr, color)
    return img


def glow_frame(size, radius, stroke, glow):
    """Fokusrahmen mit weichem Schein (wird per colordiffuse eingefärbt)."""
    img = Image(size, size)
    inner = glow
    for y in range(size):
        for x in range(size):
            # Abstand zur Rahmenlinie eines abgerundeten Rechtecks
            cx = min(max(x + 0.5, inner + radius), size - inner - radius)
            cy = min(max(y + 0.5, inner + radius), size - inner - radius)
            dist = abs(math.hypot(x + 0.5 - cx, y + 0.5 - cy) - radius)
            if dist <= stroke / 2.0:
                a = 1.0
            else:
                a = max(0.0, 1 - (dist - stroke / 2.0) / glow) ** 2 * 0.6
            if a > 0:
                img.set(x, y, (255, 255, 255, int(255 * a)))
    return img


def tab_focus(width, height):
    """Fokus eines Reiters: leuchtender Balken unten, darüber ein weicher Schein."""
    img = Image(width, height)
    bar_top = height - 6
    for y in range(height):
        for x in range(width):
            edge = min(x, width - 1 - x) / 30.0  # Enden laufen weich aus (9-Slice-Rand 30 px)
            fade = min(1.0, edge)
            if y >= bar_top:
                a = fade
            else:
                a = fade * max(0.0, 1 - (bar_top - y) / 40.0) ** 2 * 0.45
            img.set(x, y, (255, 255, 255, int(255 * a)))
    return img


# ---------------------------------------------------------------- Icon & Fanart
def make_icon(size):
    img = Image(size, size, DARK + (255,))
    c = size / 2.0
    # weicher Lichtschein
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - c, y - c) / c
            img.blend(x, y, RED, max(0.0, 1 - d) ** 2 * 0.5)
    ring_outer, ring_inner = size * 0.40, size * 0.355
    fill_shape(img, lambda x, y: ring_inner ** 2 <= (x - c) ** 2 + (y - c) ** 2 <= ring_outer ** 2, GOLD + (255,))
    fill_shape(img, lambda x, y: (x - c) ** 2 + (y - c) ** 2 < ring_inner ** 2, RED + (255,))
    tri = polygon_test([(c - size * 0.11, c - size * 0.16), (c - size * 0.11, c + size * 0.16), (c + size * 0.17, c)])
    fill_shape(img, tri, (250, 245, 235, 255))
    # Filmlöcher oben und unten
    for i in range(8):
        x = size * (0.08 + i * 0.12)
        for top in (size * 0.03, size * 0.91):
            fill_shape(img, rounded_inside(x, top, size * 0.07, size * 0.05, size * 0.012), (40, 40, 44, 255))
    return img


def rounded_inside(x0, y0, w, h, r):
    def inside(px, py):
        if not (x0 <= px <= x0 + w and y0 <= py <= y0 + h):
            return False
        cx = min(max(px, x0 + r), x0 + w - r)
        cy = min(max(py, y0 + r), y0 + h - r)
        return (px - cx) ** 2 + (py - cy) ** 2 <= r * r
    return inside


def make_fanart(width, height):
    img = Image(width, height, DARK + (255,))
    img.paste(light_cone(width // 2, height), width // 4, 0)
    left = curtain(width // 4, height)
    right = curtain(width // 4, height, mirror=True)
    img.paste(left, 0, 0)
    img.paste(right, width - width // 4, 0)
    img.paste(gradient(width, height // 3, False, 0, 230), 0, height - height // 3)
    return img


def main():
    make_stars()
    curtain(480, 540).save(os.path.join(SKIN_MEDIA, "curtain_left.png"))
    curtain(480, 540, mirror=True).save(os.path.join(SKIN_MEDIA, "curtain_right.png"))
    light_cone(480, 540).save(os.path.join(SKIN_MEDIA, "light_cone.png"))
    spotlight(256).save(os.path.join(SKIN_MEDIA, "spotlight.png"))
    gradient(512, 4, True, 250, 0).save(os.path.join(SKIN_MEDIA, "gradient_left.png"))
    gradient(4, 512, False, 0, 255).save(os.path.join(SKIN_MEDIA, "gradient_bottom.png"))
    gradient(4, 256, False, 220, 0).save(os.path.join(SKIN_MEDIA, "gradient_top.png"))
    rounded_rect(200, 300, 14).save(os.path.join(SKIN_MEDIA, "poster_mask.png"))
    rounded_rect(320, 180, 14).save(os.path.join(SKIN_MEDIA, "landscape_mask.png"))
    tab_focus(120, 76).save(os.path.join(SKIN_MEDIA, "tab_focus.png"))
    rounded_rect(64, 64, 14).save(os.path.join(SKIN_MEDIA, "rounded.png"))
    glow_frame(96, 14, 4, 18).save(os.path.join(SKIN_MEDIA, "focus_glow.png"))
    icon = make_icon(256)
    icon.save(os.path.join(ADDON_RES, "icon.png"))
    icon.save(os.path.join(SKIN_RES, "icon.png"))
    fanart = make_fanart(960, 540)
    fanart.save(os.path.join(ADDON_RES, "fanart.png"))
    fanart.save(os.path.join(SKIN_RES, "fanart.png"))
    fanart.save(os.path.join(SKIN_MEDIA, "background.png"))
    print("Grafiken erzeugt.")


if __name__ == "__main__":
    main()
