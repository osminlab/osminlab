"""SVG cards for the activity window of README.md (stdlib only).

Each card is written twice, `<name>-light.svg` and `<name>-dark.svg`; the
README selects one with <picture> and prefers-color-scheme. The SVGs embed
their own CSS, including a short entrance animation that is disabled under
prefers-reduced-motion. GitHub renders them as images, so they are not
interactive.
"""

from html import escape
from pathlib import Path

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
WIDTH = 840

# Background, border and text colors match GitHub's light and dark themes.
# `series` holds the categorical colors used by the languages card.
THEMES = {
    "light": {
        "bg": "#ffffff",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#59636e",
        "grid": "#d8dee4",
        "accent": "#2a78d6",
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
    },
    "dark": {
        "bg": "#0d1117",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#9198a1",
        "grid": "#30363d",
        "accent": "#3987e5",
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
    },
}

STYLE = """
<style>
  text { font-family: %(font)s; fill: %(text)s; }
  .title { font-size: 16px; font-weight: 600; }
  .label { font-size: 13px; fill: %(muted)s; }
  .small { font-size: 11px; fill: %(muted)s; }
  .hero { font-size: 44px; font-weight: 600; }
  .big { font-size: 28px; font-weight: 600; }
  .value { font-size: 13px; font-weight: 600; }
  /* Elements are visible by default; without CSS animations the final
     state is shown. */
  .fade { animation: fade .6s ease-out both; }
  .grow { transform-box: fill-box; transform-origin: bottom;
          animation: grow .7s cubic-bezier(.2,.8,.2,1) both; }
  .slide { transform-box: fill-box; transform-origin: left;
           animation: slide .9s cubic-bezier(.2,.8,.2,1) both; }
  @keyframes fade { from { opacity: 0; } }
  @keyframes grow { from { transform: scaleY(0); } }
  @keyframes slide { from { transform: scaleX(0); } }
  @media (prefers-reduced-motion: reduce) {
    .fade, .grow, .slide { animation: none; }
  }
</style>
"""


def card(t: dict, height: int, title: str, body: list[str]) -> str:
    """The frame shared by every card: border, background and title."""
    return "\n".join([
        (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="{escape(title)}">'),
        f"<title>{escape(title)}</title>",
        STYLE % {"font": FONT, **t},
        (f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" '
        f'rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>'),
        f'<text class="title" x="24" y="36">{escape(title)}</text>',
        *body,
        "</svg>",
    ])


def delay(ms: int) -> str:
    return f'style="animation-delay:{ms}ms"'


def bar_path(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """A bar standing on y + h, with only its top corners rounded."""
    r = min(r, w / 2, h)
    return (
        f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"V{y + h:.1f} Z"
    )


def bars(
    t: dict,
    data: list[tuple[str, float]],
    x0: float,
    width: float,
    top: float,
    bottom: float,
    bar_w: float,
) -> list[str]:
    """A small bar chart: one hue, a baseline, the value above every bar.

    Every bar is labelled since the image has no tooltips; the highest
    value is shown in bold.
    """
    peak = max((v for _, v in data), default=0) or 1
    slot = width / len(data)
    out = [
        (f'<line x1="{x0}" y1="{bottom}" x2="{x0 + width}" y2="{bottom}" '
        f'stroke="{t["grid"]}"/>')
    ]
    for i, (label, value) in enumerate(data):
        cx = x0 + slot * (i + 0.5)
        h = (bottom - top) * value / peak
        if h >= 1:
            out.append(
                f'<path class="grow" {delay(i * 50)} '
                f'd="{bar_path(cx - bar_w / 2, bottom - h, bar_w, h)}" '
                f'fill="{t["accent"]}"/>'
            )
        cls = "value" if value == peak else "small"
        out.append(
            f'<text class="{cls} fade" {delay(300 + i * 50)} x="{cx:.1f}" '
            f'y="{bottom - h - 6:.1f}" text-anchor="middle">{value:.1f}</text>'
        )
        out.append(
            f'<text class="small" x="{cx:.1f}" y="{bottom + 18}" '
            f'text-anchor="middle">{escape(label)}</text>'
        )
    return out


def overview(t: dict, s: dict) -> str:
    """The all-time total as the hero figure, three supporting numbers."""
    hero_x, split = 160, 320
    since = f"{s['since']} – present" if "since" in s else ""
    body = [
        (f'<g class="fade"><text class="hero" x="{hero_x}" y="104" '
        f'text-anchor="middle">{s["all_time"]:,}</text>'),
        (f'<text class="value" x="{hero_x}" y="132" text-anchor="middle">'
        "All-time contributions</text>"),
        (f'<text class="small" x="{hero_x}" y="150" text-anchor="middle">'
        f"{since}</text></g>"),
        f'<line x1="{split}" y1="66" x2="{split}" y2="150" stroke="{t["grid"]}"/>',
    ]
    tiles = [
        (s.get("year_total"), "contributions", "in the last year"),
        (s.get("merged"), "pull requests", "merged"),
        (s.get("years"), "years", f"on GitHub since {s.get('since')}"),
    ]
    tiles = [tile for tile in tiles if tile[0] is not None]
    slot = (WIDTH - split - 24) / max(len(tiles), 1)
    for i, (value, label, note) in enumerate(tiles):
        cx = split + slot * (i + 0.5)
        body += [
            f'<g class="fade" {delay(150 + i * 120)}>',
            f'<text class="big" x="{cx:.0f}" y="100" text-anchor="middle">{value:,}</text>',
            f'<text class="value" x="{cx:.0f}" y="128" text-anchor="middle">{label}</text>',
            (f'<text class="small" x="{cx:.0f}" y="146" text-anchor="middle">'
            f"{escape(note)}</text></g>"),
        ]
    return card(t, 176, "GitHub activity", body)


def activity(t: dict, s: dict) -> str:
    """Average contributions per calendar month and per weekday."""
    body = [
        f'<text class="label" x="24" y="62">Per month · {s["span"]}</text>',
        f'<text class="label" x="{WIDTH - 240}" y="62">Per day, by weekday</text>',
        *bars(t, s["month_avg"], 24, WIDTH - 300, 90, 200, 24),
        *bars(t, s["weekday_avg"], WIDTH - 240, 216, 90, 200, 18),
    ]
    return card(t, 236, "Average contributions", body)


def icon(path: str | None, x: float, y: float, color: str) -> str:
    """A 16px Simple Icons logo in the series colour, or a dot without one."""
    if not path:
        return f'<circle cx="{x + 8}" cy="{y + 8}" r="5" fill="{color}"/>'
    return (
        f'<svg x="{x}" y="{y}" width="16" height="16" viewBox="0 0 24 24">'
        f'<path d="{escape(path)}" fill="{color}"/></svg>'
    )


def languages(t: dict, s: dict) -> str:
    """One proportional bar, then a legend row with each language's logo."""
    langs = s["languages"][: len(t["series"])]
    x, width, gap = 24, WIDTH - 48, 2
    usable = width - gap * (len(langs) - 1)
    # Small shares get a minimum width; the difference is taken from the largest.
    widths = [max(6.0, usable * pct / 100) for _, pct, _ in langs]
    widths[0] -= sum(widths) - usable
    body = [
        (f'<clipPath id="track"><rect x="{x}" y="58" width="{width}" '
        'height="10" rx="5"/></clipPath>'),
        '<g clip-path="url(#track)">',
    ]
    for i, w in enumerate(widths):
        body.append(
            f'<rect class="slide" {delay(i * 120)} x="{x:.1f}" y="58" '
            f'width="{w:.1f}" height="10" fill="{t["series"][i]}"/>'
        )
        x += w + gap
    body.append("</g>")
    slot = width / len(langs)
    for i, (name, pct, logo) in enumerate(langs):
        lx = 24 + slot * i
        body += [
            f'<g class="fade" {delay(300 + i * 100)}>',
            icon(logo, lx, 92, t["series"][i]),
            (f'<text x="{lx + 24:.0f}" y="105"><tspan class="value">'
            f'{escape(name)}</tspan><tspan class="label" dx="6">{pct:.1f}%'
            "</tspan></text></g>"),
        ]
    return card(t, 132, "Top languages", body)


CARDS = {
    "overview": (overview, ("all_time",)),
    "activity": (activity, ("month_avg", "weekday_avg")),
    "languages": (languages, ("languages",)),
}


def write_cards(stats: dict, outdir: Path) -> list[str]:
    """Write every card whose data is present; return their names.

    SVG files in `outdir` that were not written in this run are deleted, so
    the folder only contains the cards referenced by the README.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (render, needs) in CARDS.items():
        if all(stats.get(k) for k in needs):
            for theme, t in THEMES.items():
                (outdir / f"{name}-{theme}.svg").write_text(
                    render(t, stats) + "\n", encoding="utf-8"
                )
            written.append(name)
    for old in outdir.glob("*.svg"):
        if old.stem.rsplit("-", 1)[0] not in written:
            old.unlink()
    return written
