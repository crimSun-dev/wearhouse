"""Generated product placeholders (pure, deterministic). An SVG card built ONLY from the product's published facts:
a silhouette per wardrobe slot tinted with the documented colour swatch, the name and category, and a visible
"GENERATED PLACEHOLDER" label. Never presented as a product photo; replaceable media objects (design D2).
All text is XML-escaped; nothing from a product name can become markup.
"""
from __future__ import annotations

import hashlib
from xml.sax.saxutils import escape

from .domain import colour_hex

GENERATOR = "wearhouse-placeholder@1"
WIDTH, HEIGHT = 600, 800
NEUTRAL = "#b9a9b5"

# Simple silhouettes drawn in a 600x800 box (centre region ~ 120..480 x 140..600).
SILHOUETTES = {
    "top": "M190 210 L250 180 Q300 215 350 180 L410 210 L480 300 L430 335 L405 300 L405 560 L195 560 L195 300 "
           "L170 335 L120 300 Z",
    "outer": "M185 200 L255 170 L300 230 L345 170 L415 200 L485 330 L440 360 L415 320 L415 590 L310 590 L300 250 "
             "L290 590 L185 590 L185 320 L160 360 L115 330 Z",
    "bottom": "M215 180 L385 180 L405 590 L325 590 L300 300 L275 590 L195 590 Z",
    "dress": "M245 170 L275 170 Q300 200 325 170 L355 170 L360 270 L330 300 L440 590 L160 590 L270 300 L240 270 Z",
    "footwear": "M140 450 Q150 390 220 380 L300 330 Q330 320 340 350 L360 420 Q440 430 470 470 L470 510 L140 510 Z",
    "accessory": "M210 300 Q210 220 300 220 Q390 220 390 300 L440 300 L460 560 L140 560 L160 300 Z "
                 "M240 300 Q240 250 300 250 Q360 250 360 300 Z",
    "unknown": "M300 200 Q330 200 330 228 Q330 250 305 258 L305 280 L470 420 L130 420 L295 280 L295 250 Z",
}


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(hex_colour: str) -> float:
    r, g, b = (c / 255 for c in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _mix(hex_colour: str, other: str, t: float) -> str:
    a, b = _rgb(hex_colour), _rgb(other)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _wrap(text: str, width: int = 22, lines: int = 2) -> list[str]:
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                out.append(cur)
            cur = w[:width]
        if len(out) == lines:
            break
    if cur and len(out) < lines:
        out.append(cur)
    if len(" ".join(out)) < len(" ".join(words)):
        out[-1] = out[-1][: width - 1].rstrip() + "…"
    return out or ["Unnamed product"]


def placeholder_svg(*, name: str | None, category: str | None, colour: str | None, slot: str | None) -> bytes:
    """Deterministic SVG bytes for the given published facts."""
    swatch = colour_hex(colour) or NEUTRAL
    background = _mix(swatch, "#ffffff", 0.82)
    stroke = _mix(swatch, "#000000", 0.35)
    ink = "#2b1d2a" if _luminance(background) > 0.5 else "#ffffff"
    shape = SILHOUETTES.get(slot or "unknown", SILHOUETTES["unknown"])
    title_lines = _wrap(name or "Unnamed product")
    sub = " · ".join(x for x in (category, colour if colour_hex(colour) else (f"{colour} (no swatch)" if colour else None))
                     if x)
    seed = int(hashlib.sha256(f"{name}|{category}|{colour}|{slot}".encode()).hexdigest()[:6], 16)
    tilt = (seed % 7) - 3  # small deterministic variety between products
    texts = "".join(f'<text x="300" y="{660 + i * 40}" text-anchor="middle" font-size="30" font-weight="600" '
                    f'fill="{ink}">{escape(line)}</text>' for i, line in enumerate(title_lines))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'role="img" aria-label="{escape("Generated placeholder: " + (name or "product"), {chr(34): "&quot;"})}">'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{background}"/>'
        f'<rect x="24" y="24" width="{WIDTH - 48}" height="{HEIGHT - 48}" rx="28" fill="none" stroke="{stroke}" '
        f'stroke-opacity="0.25" stroke-width="2"/>'
        f'<g transform="rotate({tilt} 300 380)"><path d="{shape}" fill="{swatch}" stroke="{stroke}" stroke-width="4" '
        f'stroke-linejoin="round" fill-rule="evenodd"/></g>'
        f'{texts}'
        f'<text x="300" y="{660 + len(title_lines) * 40 + 4}" text-anchor="middle" font-size="20" fill="{ink}" '
        f'fill-opacity="0.75">{escape(sub)}</text>'
        f'<text x="300" y="70" text-anchor="middle" font-size="16" letter-spacing="3" fill="{ink}" '
        f'fill-opacity="0.6">GENERATED PLACEHOLDER</text>'
        f'</svg>'
    )
    return svg.encode("utf-8")
