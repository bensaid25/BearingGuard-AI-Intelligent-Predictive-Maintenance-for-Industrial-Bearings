"""Visual layer: dark HUD theme (CSS), SVG gauges, small HTML blocks and Altair charts.

Pure presentation. Nothing here reads data sources or models.
"""
from __future__ import annotations

import html as _html
import math
import re

import altair as alt
import pandas as pd

C = {
    "cyan": "#45E0FF", "blue": "#2F7BFF", "violet": "#9B8CFF", "text": "#E4F0FF",
    "muted": "#7C9CC6", "line": "rgba(72,150,255,0.28)", "green": "#35E08A",
    "amber": "#FFB547", "red": "#FF4D6D", "grey": "#7C8BA6",
}
LEVEL_COLOR = {"normal": C["green"], "warning": C["amber"], "critical": C["red"], "unknown": C["grey"]}
FONT_BODY = "Rajdhani"


def esc(x) -> str:
    return _html.escape(str(x))


def h(markup: str) -> str:
    """Collapse whitespace so Markdown never mistakes indented HTML for a code block."""
    return re.sub(r"\s*\n\s*", " ", markup).strip()


# ------------------------------------------------------------------ small HTML blocks
def section(title: str, note: str = "") -> str:
    return h(f'<div class="sec">{esc(title)}<span class="n">{esc(note)}</span></div>')


def panel_title(title: str, hint: str = "") -> str:
    hint_html = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    return h(f'<div class="ptitle">{esc(title)}{hint_html}</div>')


def pill(text: str, level: str) -> str:
    return f'<span class="pill pill-{level}">{esc(text)}</span>'


def tile(label: str, value: str, unit: str = "", sub: str = "") -> str:
    unit_html = f'<span class="u">{esc(unit)}</span>' if unit else ""
    sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ""
    return h(f'<div class="tile"><div class="l">{esc(label)}</div>'
             f'<div class="v">{esc(value)}{unit_html}</div>{sub_html}</div>')


def kv(label: str, value: str) -> str:
    return f'<div class="kv"><span>{esc(label)}</span><b>{esc(value)}</b></div>'


def empty(reason: str) -> str:
    return h(f'<div class="empty">{esc(reason)}</div>')


_OK = {"online", "connected", "result received", "live"}
_BAD = {"unreachable", "disconnected"}


def status_level(text: str) -> str:
    t = text.lower()
    return "normal" if t in _OK else "critical" if t in _BAD else "warning"


def system_row(name: str, status: str, detail: str) -> str:
    lvl = status_level(status)
    return h(f'<div class="row status-{lvl}"><span class="dot"></span>'
             f'<span class="name">{esc(name)}<span class="detail">{esc(detail)}</span></span>'
             f'{pill(status, lvl)}</div>')


# ------------------------------------------------------------------ SVG gauges
_uid = 0


def _next_id() -> str:
    global _uid
    _uid += 1
    return f"g{_uid}"


def _polar(cx: float, cy: float, r: float, frac: float) -> tuple[float, float]:
    """Point on a top semicircle; frac 0 = left end, 1 = right end."""
    a = math.pi * (1 - frac)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def semi_gauge(value: float, vmin: float, vmax: float, color: str,
               threshold: float | None = None, min_label: str = "", max_label: str = "") -> str:
    uid = _next_id()
    span = (vmax - vmin) or 1.0
    f = min(1.0, max(0.0, (value - vmin) / span))
    cx, cy, r = 110, 104, 84
    x0, y0 = _polar(cx, cy, r, 0)
    x1, y1 = _polar(cx, cy, r, 1)
    track = f"M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {x1:.1f} {y1:.1f}"
    parts = [f'<svg viewBox="0 0 220 128" xmlns="http://www.w3.org/2000/svg" role="img">',
             f'<defs><filter id="{uid}" x="-30%" y="-30%" width="160%" height="160%">'
             f'<feGaussianBlur stdDeviation="3.2" result="b"/>'
             f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
             f'<path d="{track}" fill="none" stroke="rgba(72,150,255,0.18)" stroke-width="11" stroke-linecap="round"/>']
    for i in range(11):                                   # tick marks inside the arc
        ta, tb = _polar(cx, cy, r - 17, i / 10), _polar(cx, cy, r - (12 if i % 5 else 10), i / 10)
        parts.append(f'<line x1="{ta[0]:.1f}" y1="{ta[1]:.1f}" x2="{tb[0]:.1f}" y2="{tb[1]:.1f}" '
                     f'stroke="rgba(124,156,198,0.55)" stroke-width="1.2"/>')
    if f > 0.004:
        vx, vy = _polar(cx, cy, r, f)
        parts.append(f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {vx:.1f} {vy:.1f}" fill="none" '
                     f'stroke="{color}" stroke-width="11" stroke-linecap="round" filter="url(#{uid})"/>')
        parts.append(f'<circle cx="{vx:.1f}" cy="{vy:.1f}" r="4.5" fill="#fff" filter="url(#{uid})"/>')
    if threshold is not None:
        tf = min(1.0, max(0.0, (threshold - vmin) / span))
        ta, tb = _polar(cx, cy, r - 16, tf), _polar(cx, cy, r + 10, tf)
        parts.append(f'<line x1="{ta[0]:.1f}" y1="{ta[1]:.1f}" x2="{tb[0]:.1f}" y2="{tb[1]:.1f}" '
                     f'stroke="{C["red"]}" stroke-width="2.4"/>')
    lab = 'fill="#7C9CC6" font-size="11" font-family="Rajdhani, Segoe UI, sans-serif"'
    parts.append(f'<text x="{x0:.0f}" y="124" text-anchor="middle" {lab}>{esc(min_label)}</text>')
    parts.append(f'<text x="{x1:.0f}" y="124" text-anchor="middle" {lab}>{esc(max_label)}</text>')
    parts.append("</svg>")
    return h("".join(parts))


def ring_gauge(frac: float, center: str, sub: str, color: str) -> str:
    uid = _next_id()
    f = min(1.0, max(0.0, frac))
    r = 58
    circ = 2 * math.pi * r
    parts = [f'<svg viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" role="img">',
             f'<defs><filter id="{uid}" x="-30%" y="-30%" width="160%" height="160%">'
             f'<feGaussianBlur stdDeviation="3.2" result="b"/>'
             f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
             f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="rgba(72,150,255,0.18)" stroke-width="10"/>']
    if f > 0.004:
        parts.append(f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="{color}" stroke-width="10" '
                     f'stroke-linecap="round" stroke-dasharray="{circ * f:.1f} {circ:.1f}" '
                     f'transform="rotate(-90 80 80)" filter="url(#{uid})"/>')
    parts.append(f'<text x="80" y="82" text-anchor="middle" fill="#E4F0FF" font-size="24" font-weight="600" '
                 f'font-family="Orbitron, Rajdhani, Segoe UI, sans-serif">{esc(center)}</text>')
    parts.append(f'<text x="80" y="102" text-anchor="middle" fill="#7C9CC6" font-size="12" '
                 f'font-family="Rajdhani, Segoe UI, sans-serif">{esc(sub)}</text>')
    parts.append("</svg>")
    return h("".join(parts))


# ------------------------------------------------------------------ charts
def _x():
    return alt.X("timestamp:T", title=None, axis=alt.Axis(format="%H:%M:%S", labelFlush=False, tickCount=4))


def _finish(chart):
    return (chart.configure(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor="rgba(72,150,255,0.12)", domainColor="rgba(72,150,255,0.30)",
                            tickColor="rgba(72,150,255,0.30)", labelColor=C["muted"], titleColor=C["muted"],
                            labelFont=FONT_BODY, titleFont=FONT_BODY, labelFontSize=11, titleFontSize=11)
            .configure_header(labelColor=C["text"], labelFont=FONT_BODY))


def _glow_area(color: str):
    return alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                        stops=[alt.GradientStop(color="rgba(0,0,0,0)", offset=0),
                               alt.GradientStop(color=color, offset=1)])


def vibration_chart(df: pd.DataFrame):
    base = alt.Chart(df).encode(x=_x(), y=alt.Y("rms:Q", title="RMS (g)"))
    area = base.mark_area(color=_glow_area("rgba(69,224,255,0.30)"), line={"color": C["cyan"], "strokeWidth": 2})
    tip = base.mark_point(opacity=0, size=60).encode(
        tooltip=[alt.Tooltip("timestamp:T", format="%H:%M:%S"), alt.Tooltip("rms:Q", format=".3f")])
    return _finish(alt.layer(area, tip).properties(height=210))


def axes_charts(df: pd.DataFrame) -> list:
    """One small chart per axis, each with its own y scale (Az sits near 1 g, Ax and Ay near 0)."""
    charts = []
    for i, (col, color) in enumerate([("ax", C["cyan"]), ("ay", C["blue"]), ("az", C["violet"])]):
        last = i == 2
        charts.append(_finish(alt.Chart(df).mark_line(color=color, strokeWidth=1.6).encode(
            x=alt.X("timestamp:T", title=None, axis=alt.Axis(format="%H:%M:%S", tickCount=6) if last else None),
            y=alt.Y(f"{col}:Q", title=f"{col.capitalize()} (g)", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("timestamp:T", format="%H:%M:%S"), alt.Tooltip(f"{col}:Q", format=".3f")],
        ).properties(height=95 if last else 80)))
    return charts


def ims_chart(df: pd.DataFrame, threshold: float | None, higher_is_anomalous: bool = True):
    line = alt.Chart(df).mark_line(color=C["cyan"], strokeWidth=2).encode(
        x=_x(), y=alt.Y("score:Q", title="Score"),
        tooltip=[alt.Tooltip("timestamp:T", format="%H:%M:%S"), alt.Tooltip("score:Q", format=".3f")])
    layers = [line]
    if threshold is not None:
        layers.append(alt.Chart(pd.DataFrame({"threshold": [threshold]})).mark_rule(
            color=C["red"], strokeDash=[6, 4], strokeWidth=1.6).encode(y="threshold:Q"))
        flagged = df[df["score"] > threshold] if higher_is_anomalous else df[df["score"] < threshold]
        if not flagged.empty:
            layers.append(alt.Chart(flagged).mark_circle(color=C["red"], size=34).encode(x=_x(), y="score:Q"))
    return _finish(alt.layer(*layers).properties(height=210))


def rul_chart(df: pd.DataFrame):
    base = alt.Chart(df).encode(
        x=alt.X("cycle:Q", title="Cycle", axis=alt.Axis(tickMinStep=1, format="d", tickCount=5)),
        y=alt.Y("rul:Q", title="RUL (cycles)"),
        tooltip=[alt.Tooltip("cycle:Q"), alt.Tooltip("rul:Q", format=".0f")])
    area = base.mark_area(color=_glow_area("rgba(47,123,255,0.30)"), line={"color": C["blue"], "strokeWidth": 2})
    last = alt.Chart(df.tail(1)).mark_circle(color="#fff", size=80).encode(x="cycle:Q", y="rul:Q")
    return _finish(alt.layer(area, last).properties(height=210))


# ------------------------------------------------------------------ CSS
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700&family=Rajdhani:wght@400;500;600;700&display=swap');
:root { --cyan:#45E0FF; --blue:#2F7BFF; --text:#E4F0FF; --muted:#7C9CC6; --line:rgba(72,150,255,0.28);
        --green:#35E08A; --amber:#FFB547; --red:#FF4D6D; --grey:#7C8BA6; --panel:rgba(11,27,60,0.72); }

/* page */
.stApp { color:var(--text); font-family:'Rajdhani','Segoe UI',Roboto,sans-serif; font-size:1.08rem;
  background:
    radial-gradient(1100px 520px at 50% -8%, rgba(47,123,255,0.20), transparent 70%),
    radial-gradient(900px 480px at 50% 112%, rgba(155,70,255,0.22), transparent 70%),
    linear-gradient(rgba(70,140,255,0.045) 1px, transparent 1px) 0 0/46px 46px,
    linear-gradient(90deg, rgba(70,140,255,0.045) 1px, transparent 1px) 0 0/46px 46px,
    linear-gradient(180deg,#050B1E 0%,#0A1533 100%);
  background-attachment: fixed; }
[data-testid="stHeader"] { background:transparent; }
.stAppDeployButton, footer { display:none !important; }
[data-testid="stToolbar"] * { color:var(--muted) !important; }
.block-container { padding-top:2.4rem; padding-bottom:3rem; max-width:1400px; }
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p { color:var(--text); }
[data-testid="stSidebar"] { color:var(--text); }
[data-testid="stCaptionContainer"] { color:var(--muted); }

div[class*="st-key-panel_cwru"], div[class*="st-key-panel_ims"], div[class*="st-key-panel_cmapss"] { min-height:372px; }
div[class*="st-key-panel_chart"] { min-height:292px; }

/* header */
.hud-head { display:flex; justify-content:space-between; align-items:center; gap:1rem; flex-wrap:wrap;
  padding:0 .2rem 1rem; border-bottom:1px solid var(--line); margin-bottom:1rem; }
.hud-title { font-family:'Orbitron','Segoe UI',sans-serif; font-size:1.6rem; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; line-height:1.2; text-shadow:0 0 16px rgba(69,224,255,.35); }
.hud-sub { color:var(--muted); font-size:1rem; letter-spacing:.05em; margin-top:.2rem; }
.hud-right { display:flex; align-items:center; gap:.8rem; color:var(--muted); }
.clock { font-size:1rem; letter-spacing:.06em; }
.chip { border:1px solid var(--c); color:var(--c); border-radius:999px; padding:.12rem .85rem; font-size:.8rem;
  font-weight:700; letter-spacing:.14em; background:color-mix(in srgb, var(--c) 14%, transparent); }
.chip-live { --c:var(--green); } .chip-mock { --c:var(--amber); } .chip-off { --c:var(--red); }
.chip-id { --c:var(--cyan); }
.mock-banner { border:1px solid var(--amber); border-radius:10px; padding:.5rem 1rem; margin-bottom:.4rem;
  background:rgba(255,181,71,.10); color:var(--amber); }
.mock-banner b { font-family:'Orbitron','Segoe UI',sans-serif; letter-spacing:.12em; font-size:.85rem; }
.mock-banner span { color:#FFD9A0; margin-left:.8rem; }

/* section labels + panels */
.sec { display:flex; align-items:center; gap:.8rem; margin:1.7rem 0 .7rem; color:var(--cyan);
  font-family:'Orbitron','Segoe UI',sans-serif; font-size:.82rem; letter-spacing:.2em; text-transform:uppercase; }
.sec::before { content:''; width:28px; height:2px; background:var(--cyan); box-shadow:0 0 8px var(--cyan); }
.sec .n { color:var(--muted); font-family:'Rajdhani','Segoe UI',sans-serif; letter-spacing:.04em;
  text-transform:none; font-size:.98rem; }
div[class*="st-key-panel"] { background:var(--panel); border:1px solid var(--line); border-radius:14px;
  padding:1rem 1.25rem 1.05rem; height:100%;
  box-shadow:0 0 0 1px rgba(69,224,255,.04) inset, 0 10px 34px rgba(0,0,0,.38), 0 0 26px rgba(47,123,255,.08); }
[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] { height:100%; }
.ptitle { font-family:'Orbitron','Segoe UI',sans-serif; font-size:.74rem; letter-spacing:.16em; color:var(--muted);
  text-transform:uppercase; margin-bottom:.55rem; }
.ptitle .hint { font-family:'Rajdhani','Segoe UI',sans-serif; letter-spacing:.03em; text-transform:none;
  font-size:.95rem; margin-left:.7rem; color:#5F7FA8; }
.note { color:var(--muted); font-size:.92rem; margin-top:.7rem; line-height:1.3; }
.empty { border:1px dashed var(--line); border-radius:10px; padding:.8rem 1rem; color:var(--muted); font-size:.98rem; }

/* status hero */
.status-hero { display:grid; grid-template-columns:auto 1fr; gap:3rem; align-items:center; }
.status-hero .who { color:var(--muted); letter-spacing:.14em; font-size:.85rem; text-transform:uppercase; }
.status-word { font-family:'Orbitron','Segoe UI',sans-serif; font-size:3.3rem; font-weight:700; line-height:1.1;
  color:var(--c); text-shadow:0 0 22px var(--c); }
.status-hero ul { margin:0; padding-left:1.1rem; font-size:1.08rem; }
.status-hero li { margin:.15rem 0; }
.status-normal { --c:var(--green); } .status-warning { --c:var(--amber); }
.status-critical { --c:var(--red); } .status-unknown { --c:var(--grey); }

/* sensor block */
.sensor { display:grid; grid-template-columns:250px 1fr; gap:1.6rem; align-items:center; }
.tiles { display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:.7rem; }
.tile { background:rgba(6,16,40,.55); border:1px solid var(--line); border-radius:10px; padding:.6rem .85rem; }
.tile .l { font-size:.74rem; letter-spacing:.14em; color:var(--muted); text-transform:uppercase; }
.tile .v { font-size:1.65rem; font-weight:600; line-height:1.25; white-space:nowrap;
  text-shadow:0 0 12px rgba(69,224,255,.35); }
.tile .u { font-size:.95rem; color:var(--muted); margin-left:.3rem; font-weight:500; text-shadow:none; }
.tile .s { font-size:.85rem; color:var(--muted); }
.gauge { text-align:center; }
.gauge svg { width:100%; max-width:240px; }
.gauge .gv { font-size:2rem; font-weight:600; margin-top:-.5rem; text-shadow:0 0 12px rgba(69,224,255,.35); }
.gauge .gv .u { font-size:1rem; color:var(--muted); margin-left:.3rem; text-shadow:none; }
.gauge .gl { font-size:.74rem; letter-spacing:.14em; color:var(--muted); text-transform:uppercase; }

/* AI panels */
.ai { display:flex; flex-direction:column; align-items:center; text-align:center; gap:.25rem; }
.ai svg { width:100%; max-width:200px; }
.ai .big { font-family:'Orbitron','Segoe UI',sans-serif; font-size:1.35rem; font-weight:600; color:var(--c, var(--text));
  text-shadow:0 0 14px var(--c, transparent); margin-top:.2rem; }
.ai .cap { font-size:.74rem; letter-spacing:.14em; color:var(--muted); text-transform:uppercase; }
.kv { display:flex; justify-content:space-between; width:100%; padding:.3rem 0; border-top:1px solid rgba(72,150,255,.14);
  font-size:1rem; color:var(--muted); }
.kv b { color:var(--text); font-weight:600; }
.pill { display:inline-block; padding:.08rem .85rem; border-radius:999px; font-size:.85rem; font-weight:700;
  letter-spacing:.05em; border:1px solid var(--c); color:var(--c);
  background:color-mix(in srgb, var(--c) 14%, transparent); white-space:nowrap; }
.pill-normal { --c:var(--green); } .pill-warning { --c:var(--amber); }
.pill-critical { --c:var(--red); } .pill-unknown { --c:var(--grey); }

/* system list */
.sys { display:grid; grid-template-columns:1fr 1fr; gap:0 2.6rem; }
.row { display:flex; align-items:flex-start; gap:.75rem; padding:.6rem 0; border-bottom:1px solid rgba(72,150,255,.13); }
.row .dot { width:9px; height:9px; border-radius:50%; background:var(--c); box-shadow:0 0 9px var(--c); margin-top:.5rem; flex:none; }
.row .name { flex:1; font-size:1.08rem; font-weight:600; }
.row .detail { display:block; color:var(--muted); font-size:.9rem; font-weight:400; }

/* sidebar + widgets */
[data-testid="stSidebar"] { background:rgba(7,16,40,.94); border-right:1px solid var(--line); }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-family:'Orbitron','Segoe UI',sans-serif;
  font-size:.95rem; letter-spacing:.18em; text-transform:uppercase; color:var(--cyan); }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color:var(--text); }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div { background:rgba(12,30,70,.85) !important;
  border-color:var(--line) !important; border-radius:8px !important; }
[data-baseweb="input"] input, [data-baseweb="select"] div { color:var(--text) !important; }
[data-baseweb="popover"] > div, [data-baseweb="popover"] ul { background:#0B1A3C !important; }
[data-baseweb="popover"] li { color:var(--text) !important; }
[data-baseweb="popover"] li:hover { background:rgba(69,224,255,.15) !important; }
.stButton > button { background:rgba(12,30,70,.85); color:var(--text); border:1px solid var(--cyan); border-radius:8px; }
.stButton > button:hover { background:rgba(69,224,255,.15); color:#fff; border-color:var(--cyan); }
[data-testid="stExpander"] { background:var(--panel); border:1px solid var(--line); border-radius:12px; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color:var(--text); }
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) > div:first-child { background-color:var(--cyan) !important; border-color:var(--cyan) !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"]:has(input:checked) > span:first-child { background-color:var(--cyan) !important; border-color:var(--cyan) !important; }
[data-testid="stSlider"] [role="slider"] { background-color:var(--cyan) !important; }
.sb-box { border:1px solid var(--c); border-radius:8px; padding:.55rem .75rem; margin:.3rem 0 .8rem; font-size:.98rem;
  background:color-mix(in srgb, var(--c) 12%, transparent); color:var(--text); }
.sb-box b { color:var(--c); letter-spacing:.06em; }
.sb-mock { --c:var(--amber); } .sb-live { --c:var(--cyan); }

@media (max-width:1100px) {
  .sensor, .status-hero, .sys { grid-template-columns:1fr; }
  .tiles { grid-template-columns:repeat(2, minmax(0,1fr)); }
}
</style>
"""
