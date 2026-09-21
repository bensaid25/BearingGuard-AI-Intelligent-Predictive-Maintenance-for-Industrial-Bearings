"""Predictive Maintenance Dashboard (presentation layer only).

Run from the project root:   streamlit run frontend/app.py
All data comes from utils.get_dashboard_data(); this file never calls a model.
"""
import time

import streamlit as st

import theme
import utils
from theme import C, esc

st.set_page_config(page_title="Predictive Maintenance Dashboard", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(theme.CSS, unsafe_allow_html=True)


def html(markup: str):
    st.markdown(theme.h(markup), unsafe_allow_html=True)


def show_chart(chart):
    """Compatibility wrapper: newer Streamlit uses width='stretch', older use_container_width."""
    try:
        st.altair_chart(chart, width="stretch", theme=None)
    except TypeError:
        st.altair_chart(chart, use_container_width=True, theme=None)


# --------------------------------------------------------------------------- sidebar
def render_sidebar() -> dict:
    sb = st.sidebar
    sb.header("Controls")
    machine_id = sb.text_input("Machine ID", value="BEARING-01")
    source = sb.radio("Data source", [utils.SOURCE_MOCK, utils.SOURCE_BACKEND])
    scenario, base_url = "normal", utils.DEFAULT_BASE_URL
    if source == utils.SOURCE_MOCK:
        label = sb.selectbox("Demo scenario", list(utils.SCENARIOS.values()))
        scenario = next(k for k, v in utils.SCENARIOS.items() if v == label)
        sb.markdown(theme.h('<div class="sb-box sb-mock"><b>DEMO MODE — MOCK DATA</b><br>'
                            'Every value is simulated.</div>'), unsafe_allow_html=True)
    else:
        base_url = sb.text_input("Backend URL", value=utils.DEFAULT_BASE_URL)
        sb.markdown(theme.h('<div class="sb-box sb-live"><b>LIVE MODE</b><br>'
                            'Only real backend responses are shown.</div>'), unsafe_allow_html=True)
    auto = sb.checkbox("Auto-refresh", value=False)
    interval = sb.slider("Refresh every (seconds)", 2, 30, 5, disabled=not auto)
    sb.button("Refresh now")
    return dict(machine_id=machine_id, source=source, scenario=scenario,
                base_url=base_url, auto=auto, interval=interval)


# --------------------------------------------------------------------------- header + status
def render_header(d: dict):
    if d["is_mock"]:
        chip = '<span class="chip chip-mock">MOCK DATA</span>'
    elif d["system"]["connection"][0] == "Connected":
        chip = '<span class="chip chip-live">LIVE</span>'
    else:
        chip = '<span class="chip chip-off">OFFLINE</span>'
    html(f'''<div class="hud-head">
        <div><div class="hud-title">Predictive Maintenance Dashboard</div>
        <div class="hud-sub">Intelligent Bearing Fault Detection and Remaining Health Assessment</div></div>
        <div class="hud-right"><span class="clock">{d["generated_at"]:%I:%M:%S %p}</span>
        {chip}<span class="chip chip-id">{esc(d["machine_id"])}</span></div></div>''')
    if d["is_mock"]:
        html('<div class="mock-banner"><b>DEMO MODE — MOCK DATA</b>'
             '<span>All values on this page are simulated. None comes from a model or a sensor.</span></div>')


def render_status(d: dict):
    status, reasons = utils.compute_overall_status(d)
    items = "".join(f"<li>{esc(r)}</li>" for r in reasons)
    with st.container(key="panel_status"):
        html(f'''<div class="status-hero status-{status.lower()}">
            <div><div class="who">Machine status · {esc(d["machine_id"])}</div>
            <div class="status-word">{status}</div></div>
            <div><ul>{items}</ul>
            <div class="note">Display rule that combines the three model outputs. It is not produced by any model.</div>
            </div></div>''')


# --------------------------------------------------------------------------- sensor
def render_sensors(d: dict):
    html(theme.section("Sensor monitoring", "ESP32 + MPU6050" + (" · simulated" if d["is_mock"] else "")))
    s = d["sensor"]
    with st.container(key="panel_sensor"):
        if not s["available"]:
            html(theme.empty(s["note"]))
            return
        v = s["latest"]
        gauge = theme.semi_gauge(v["rms"], 0, utils.VIB_GAUGE_MAX_G, C["cyan"],
                                 min_label="0", max_label=f"{utils.VIB_GAUGE_MAX_G:g} g")
        tiles = "".join([
            theme.tile("Ax", f"{v['ax']:+.3f}", "g"),
            theme.tile("Ay", f"{v['ay']:+.3f}", "g"),
            theme.tile("Az", f"{v['az']:+.3f}", "g"),
            theme.tile("Sampling rate", f"{v['sampling_rate_hz']}", "Hz"),
            theme.tile("Last update", utils.fmt_time(v["timestamp"]), sub=utils.fmt_age(v["timestamp"])),
        ])
        html(f'''<div class="sensor"><div class="gauge">{gauge}
            <div class="gv">{v["rms"]:.3f}<span class="u">g</span></div>
            <div class="gl">Vibration RMS</div></div>
            <div class="tiles">{tiles}</div></div>''')


# --------------------------------------------------------------------------- AI
def render_ai(d: dict):
    html(theme.section("AI results", "three independent models"))
    c1, c2, c3 = st.columns(3, gap="medium")

    with c1, st.container(key="panel_cwru"):
        html(theme.panel_title("CWRU", "bearing fault classification"))
        r = d["cwru"]
        if r["available"]:
            conf = float(r["confidence"] or 0)
            healthy = str(r["fault_class"]).lower() == "normal"
            col = C["green"] if healthy else C["red"]
            html(f'''<div class="ai" style="--c:{col}">
                {theme.ring_gauge(conf, f"{conf:.0%}", "confidence", C["cyan"])}
                <div class="cap">Predicted fault class</div>
                <div class="big">{esc(r["fault_class"])}</div></div>''')
        else:
            html(theme.empty(r.get("reason", "No result.")))

    with c2, st.container(key="panel_ims"):
        html(theme.panel_title("IMS", "anomaly detection"))
        r = d["ims"]
        if r["available"]:
            score, thr = float(r["score"]), r.get("threshold")
            vmax = max(utils.IMS_GAUGE_MIN_MAX, score * 1.1, (thr or 0) * 1.3)
            flagged = bool(r.get("is_anomaly"))
            col = C["red"] if flagged else C["cyan"]
            gauge = theme.semi_gauge(score, 0, vmax, col, threshold=thr, min_label="0", max_label=f"{vmax:.1f}")
            state = theme.pill("ANOMALY" if flagged else "NORMAL", "critical" if flagged else "normal")
            thr_txt = "n/a" if thr is None else f"{thr:.2f}"
            html(f'''<div class="ai"><div class="gauge">{gauge}
                <div class="gv">{score:.2f}</div><div class="gl">Anomaly score</div></div>
                <div style="margin:.35rem 0 .3rem">{state}</div>
                {theme.kv("Threshold (red mark)", thr_txt)}</div>''')
        else:
            html(theme.empty(r.get("reason", "No result.")))

    with c3, st.container(key="panel_cmapss"):
        html(theme.panel_title("C-MAPSS FD001", "remaining useful life"))
        r = d["cmapss"]
        if r["available"]:
            v = float(r["rul"])
            level = ("critical" if v < utils.RUL_CRITICAL_CYCLES
                     else "warning" if v < utils.RUL_WARNING_CYCLES else "normal")
            text = {"critical": f"Under {utils.RUL_CRITICAL_CYCLES} cycles",
                    "warning": f"Under {utils.RUL_WARNING_CYCLES} cycles",
                    "normal": f"{utils.RUL_WARNING_CYCLES} cycles or more"}[level]
            html(f'''<div class="ai">
                {theme.ring_gauge(v / utils.RUL_DISPLAY_MAX, f"{v:.0f}", "cycles", theme.LEVEL_COLOR[level])}
                <div class="cap">Predicted RUL</div>
                <div style="margin:.25rem 0 .3rem">{theme.pill(text, level)}</div>
                {theme.kv("Ring scale", f"0 to {utils.RUL_DISPLAY_MAX} cycles")}</div>''')
        else:
            html(theme.empty(r.get("reason", "No result.")))

    st.caption("The CWRU, IMS and C-MAPSS inputs are benchmark dataset samples. The MPU6050 stream is "
               "ingestion/diagnostic only and is not fed to the IMS model.")


# --------------------------------------------------------------------------- charts
def render_charts(d: dict):
    html(theme.section("Trends"))
    c1, c2, c3 = st.columns(3, gap="medium")
    hist = d["sensor"]["history"]

    with c1, st.container(key="panel_chart_vib"):
        html(theme.panel_title("Vibration", "RMS over time"))
        if hist.empty:
            html(theme.empty("No vibration history is available from the backend yet."))
        else:
            show_chart(theme.vibration_chart(hist))

    with c2, st.container(key="panel_chart_ims"):
        html(theme.panel_title("IMS score", "dashed = threshold"))
        r = d["ims"]
        if r["history"].empty:
            html(theme.empty("No IMS score history is available yet."))
        else:
            show_chart(theme.ims_chart(r["history"], r.get("threshold"), utils.IMS_HIGHER_IS_ANOMALOUS))

    with c3, st.container(key="panel_chart_rul"):
        html(theme.panel_title("RUL trend", "C-MAPSS FD001"))
        h = d["cmapss"]["history"]
        if h.empty:
            html(theme.empty("No RUL history is available yet."))
        else:
            show_chart(theme.rul_chart(h))

    if not hist.empty:
        with st.expander("Ax / Ay / Az over time"):
            for chart in theme.axes_charts(hist):
                show_chart(chart)


# --------------------------------------------------------------------------- system
def render_system(d: dict):
    html(theme.section("System information"))
    s = d["system"]
    left = [("FastAPI backend", *s["backend"]),
            ("CWRU model", *s["models"]["cwru"]),
            ("IMS model", *s["models"]["ims"]),
            ("C-MAPSS model", *s["models"]["cmapss"])]
    right = [("Connection", *s["connection"]),
             ("Data source", "Mock" if d["is_mock"] else ("Live" if s["connection"][0] == "Connected" else "Live (offline)"),
              s["data_source"]),
             ("MPU6050 to IMS inference", "Not available",
              "The /sensor-data path is ingestion/diagnostic only. No valid IMS-compatible path exists for it.")]
    with st.container(key="panel_system"):
        html('<div class="sys"><div>' + "".join(theme.system_row(*r) for r in left) + "</div><div>"
             + "".join(theme.system_row(*r) for r in right) + "</div></div>")
        if s.get("raw_health") is not None:
            with st.expander("Raw /health response"):
                st.json(s["raw_health"])


# --------------------------------------------------------------------------- main
cfg = render_sidebar()
data = utils.get_dashboard_data(cfg["source"], cfg["machine_id"], cfg["scenario"], cfg["base_url"])
render_header(data)
render_status(data)
render_sensors(data)
render_ai(data)
render_charts(data)
render_system(data)

if cfg["auto"]:
    time.sleep(cfg["interval"])
    st.rerun()
