"""Consistency Dashboard view: KPIs, heatmap, per-habit bars, trends, insights.

Rendered from app.py via ``render_dashboard()``. Read-only: it only uses the
existing helpers from database.py and never writes to the database.
"""
import calendar
from datetime import date, timedelta
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import get_month_matrix, get_tasks

# A day "counts" toward streaks when at least this share of habits is done.
STREAK_THRESHOLD = 0.6
HISTORY_MONTHS = 12

INK = "#293126"
MUTED = "#77766c"
SAGE = "#9da88c"
SAGE_DARK = "#667157"
PEACH = "#e9bda2"
PEACH_LIGHT = "#f7e2d5"
GREEN_LIGHT = "#e7ecdf"
LINE = "#d9d1c2"
TERRACOTTA = "#b65f37"

DASH_CSS = f"""
<style>
header[data-testid="stHeader"], footer, #MainMenu,
div[data-testid="stToolbar"], div[data-testid="stDecoration"] {{ display: none !important; }}

.d-kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 6px 0 22px; }}
.d-kpi {{
    background: rgba(255,253,248,.9); border: 1px solid {LINE}; border-radius: 18px;
    padding: 18px 22px; box-shadow: 0 10px 30px rgba(77,66,48,.07);
}}
.d-kpi .lbl {{ font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: {MUTED}; font-weight: 600; }}
.d-kpi .val {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 3rem; line-height: 1.05; font-weight: 600; color: {INK}; margin-top: 4px; }}
.d-kpi .val small {{ font-size: 1.1rem; color: {MUTED}; font-weight: 500; margin-left: 4px; }}
.d-kpi .sub {{ font-size: .8rem; color: {MUTED}; margin-top: 2px; }}
.d-kpi .up {{ color: {SAGE_DARK}; font-weight: 600; }}
.d-kpi .down {{ color: {TERRACOTTA}; font-weight: 600; }}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: {LINE} !important; border-radius: 18px !important; background: rgba(255,253,248,.9);
    box-shadow: 0 10px 30px rgba(77,66,48,.07); padding: 8px 12px;
}}
div[data-testid="stVerticalBlockBorderWrapper"] h3 {{ margin: 0 0 2px; padding: 0; font-size: 1.55rem; font-weight: 600; }}
div[data-testid="stVerticalBlockBorderWrapper"] .cap {{ font-size: .8rem; color: {MUTED}; margin-bottom: 10px; }}

.d-habit {{
    display: grid; grid-template-columns: minmax(120px, 1.4fr) 2fr 48px 112px; gap: 12px;
    align-items: center; padding: 9px 0; border-bottom: 1px dashed {LINE};
}}
.d-habit:last-child {{ border-bottom: 0; }}
.d-habit .nm {{ font-size: .9rem; font-weight: 600; color: {INK}; line-height: 1.2; }}
.d-habit .cat {{ font-size: .7rem; color: {MUTED}; letter-spacing: .04em; }}
.d-bar {{ height: 10px; background: {GREEN_LIGHT}; border-radius: 99px; overflow: hidden; }}
.d-bar > span {{ display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, {PEACH}, {SAGE} 55%, {SAGE_DARK}); }}
.d-pct {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.35rem; font-weight: 700; text-align: right; }}

.d-insights {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: 4px 0 8px; }}
.d-insight {{ background: {GREEN_LIGHT}; border-radius: 16px; padding: 14px 18px; font-size: .92rem; line-height: 1.45; color: {INK}; }}
.d-insight.peach {{ background: {PEACH_LIGHT}; }}
.d-insight b {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.15rem; }}
.d-insight .tag {{ display: block; font-size: .68rem; letter-spacing: .14em; text-transform: uppercase; color: {MUTED}; margin-bottom: 3px; font-weight: 600; }}

.d-empty {{ text-align: center; padding: 60px 20px; font-family: 'Cormorant Garamond', Georgia, serif; font-style: italic; font-size: 1.5rem; color: {MUTED}; }}

@media (max-width: 900px) {{
    .d-kpis {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
    .d-kpi {{ padding: 14px 16px; }}
    .d-kpi .val {{ font-size: 2.3rem; }}
    .d-habit {{ grid-template-columns: 1fr 44px; }}
    .d-habit .bar-col {{ grid-column: 1 / -1; grid-row: 2; }}
    .d-habit .spark {{ grid-column: 1 / -1; grid-row: 3; }}
}}
</style>
"""


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def _shift_month(year: int, month: int, delta: int):
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _load_history(year: int, month: int, tasks, today: date):
    """Return (done, last_day): a days x habits 0/1 DataFrame and its last day.

    Days that haven't happened yet are excluded; days with no record count as
    not done (same as the tracker grid).
    """
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    last_day = min(month_end, today)
    start_year, start_month = _shift_month(year, month, -(HISTORY_MONTHS - 1))
    first_day = date(start_year, start_month, 1)
    if last_day < first_day:
        return None, last_day

    index = pd.date_range(first_day, last_day, freq="D")
    done = pd.DataFrame(0, index=index, columns=[t[0] for t in tasks], dtype=int)
    for i in range(HISTORY_MONTHS):
        y, m = _shift_month(start_year, start_month, i)
        for (task_id, day), completed in get_month_matrix(y, m).items():
            ts = pd.Timestamp(y, m, day)
            if completed and task_id in done.columns and ts in done.index:
                done.loc[ts, task_id] = 1
    return done, last_day


def _streaks(daily: pd.Series):
    """Current and longest run of days at or above STREAK_THRESHOLD."""
    hit = (daily >= STREAK_THRESHOLD).tolist()
    longest = run = 0
    for h in hit:
        run = run + 1 if h else 0
        longest = max(longest, run)
    current = 0
    for h in reversed(hit):
        if not h:
            break
        current += 1
    return current, longest


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------
_FONT = dict(family="DM Sans, sans-serif", color=INK, size=12)
_HOVER = dict(bgcolor="#fffdf8", bordercolor=LINE, font=dict(family="DM Sans", color=INK, size=12))


def _base_layout(height: int, **kw):
    return dict(
        height=height, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=_FONT, hoverlabel=_HOVER, **kw,
    )


def _heatmap(daily: pd.Series, year: int, month: int):
    first_weekday, n_days = calendar.monthrange(year, month)
    n_weeks = (first_weekday + n_days + 6) // 7
    z = [[None] * 7 for _ in range(n_weeks)]
    text = [[""] * 7 for _ in range(n_weeks)]
    hover = [[""] * 7 for _ in range(n_weeks)]
    for day in range(1, n_days + 1):
        w, d = divmod(first_weekday + day - 1, 7)
        text[w][d] = str(day)
        ts = pd.Timestamp(year, month, day)
        if ts in daily.index:
            z[w][d] = float(daily[ts]) * 100
            hover[w][d] = f"{calendar.month_abbr[month]} {day}: {daily[ts]:.0%}"
        else:
            hover[w][d] = f"{calendar.month_abbr[month]} {day}: upcoming"
    fig = go.Figure(go.Heatmap(
        z=z, text=text, texttemplate="%{text}", textfont=dict(size=12, color=INK),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>",
        x=list(calendar.day_abbr), y=list(range(n_weeks)), zmin=0, zmax=100,
        xgap=5, ygap=5, showscale=False, hoverongaps=False,
        colorscale=[[0, PEACH_LIGHT], [0.45, "#eadfc9"], [0.7, SAGE], [1, SAGE_DARK]],
    ))
    fig.update_layout(**_base_layout(72 + 52 * n_weeks))
    fig.update_layout(margin=dict(l=8, r=8, t=36, b=8))  # room for weekday labels above the grid
    fig.update_xaxes(side="top", showgrid=False, zeroline=False, fixedrange=True,
                     tickfont=dict(size=11, color=INK), ticks="", automargin=True)
    fig.update_yaxes(autorange="reversed", showgrid=False, zeroline=False, visible=False,
                     fixedrange=True)
    return fig


def _weekly_trend(daily: pd.Series):
    weekly = daily.resample("W-SUN").mean().tail(12) * 100
    labels = [f"{(d - timedelta(days=6)).strftime('%b')} {(d - timedelta(days=6)).day}" for d in weekly.index]
    shown = labels[::-1][::2][::-1]  # every other week, always including the latest
    fig = go.Figure(go.Scatter(
        x=labels, y=weekly.values, mode="lines+markers", line=dict(color=SAGE_DARK, width=3, shape="spline"),
        marker=dict(size=9, color=PEACH, line=dict(color="#fffdf8", width=2)),
        fill="tozeroy", fillcolor="rgba(157,168,140,.18)",
        hovertemplate="Week of %{x}<br>%{y:.0f}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout(260))
    fig.update_xaxes(showgrid=False, zeroline=False, fixedrange=True, tickfont=dict(size=10, color=MUTED),
                     tickmode="array", tickvals=shown, ticktext=shown, tickangle=0, automargin=True)
    fig.update_yaxes(range=[0, 105], gridcolor="#eee7d8", zeroline=False, fixedrange=True,
                     tickvals=[0, 20, 40, 60, 80, 100],
                     ticktext=["0%", "20%", "40%", "60%", "80%", "100%"],
                     automargin=True, tickfont=dict(size=10, color=MUTED))
    return fig


def _category_chart(cat_rates: pd.Series):
    cat_rates = cat_rates.sort_values()
    fig = go.Figure(go.Bar(
        x=cat_rates.values * 100, y=list(cat_rates.index), orientation="h",
        marker=dict(color=cat_rates.values * 100, colorscale=[[0, PEACH], [0.6, SAGE], [1, SAGE_DARK]],
                    cmin=0, cmax=100, line=dict(width=0)),
        text=[f"{v:.0%}" for v in cat_rates.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:.0f}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout(60 + 40 * len(cat_rates), bargap=0.45))
    fig.update_layout(margin=dict(l=8, r=36, t=8, b=8))
    fig.update_xaxes(range=[0, 100], visible=False, fixedrange=True)
    fig.update_yaxes(showgrid=False, fixedrange=True, automargin=True, tickfont=dict(size=12, color=INK))
    return fig


def _sparkline(values, width=108, height=28):
    if len(values) < 2:
        return ""
    pts = [(i * (width - 4) / (len(values) - 1) + 2, height - 3 - v * (height - 6)) for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"2,{height} {line} {width - 2},{height}"
    lx, ly = pts[-1]
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polygon points="{area}" fill="{SAGE}" fill-opacity=".2"/>'
        f'<polyline points="{line}" fill="none" stroke="{SAGE_DARK}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{PEACH}" stroke="#fffdf8" stroke-width="1.5"/></svg>'
    )


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
def _kpi(label, value, sub="", unit=""):
    unit_html = f"<small>{unit}</small>" if unit else ""
    return (f'<div class="d-kpi"><div class="lbl">{label}</div>'
            f'<div class="val">{value}{unit_html}</div><div class="sub">{sub}</div></div>')


def render_dashboard():
    st.markdown(DASH_CSS, unsafe_allow_html=True)
    today = date.today()
    tasks = get_tasks()

    c1, c2, c3, c4 = st.columns([1, 0.7, 1.2, 1.5])
    with c1:
        month = st.selectbox("MONTH", list(range(1, 13)), index=today.month - 1,
                             format_func=lambda m: calendar.month_name[m], key="dash_month")
    with c2:
        years = list(range(today.year - 2, today.year + 3))
        year = st.selectbox("YEAR", years, index=years.index(today.year), key="dash_year")
    categories = sorted({t[2] for t in tasks})
    with c3:
        sel_cats = st.multiselect("CATEGORY", categories, placeholder="All categories", key="dash_cats")
    pool = [t for t in tasks if not sel_cats or t[2] in sel_cats]
    with c4:
        sel_habits = st.multiselect("HABIT", [t[1] for t in pool], placeholder="All habits", key="dash_habits")
    chosen = [t for t in pool if not sel_habits or t[1] in sel_habits]

    month_label = f"{calendar.month_name[month]} {year}"
    if not chosen:
        st.markdown('<div class="d-empty">No habits match this filter.</div>', unsafe_allow_html=True)
        return

    done, last_day = _load_history(year, month, chosen, today)
    month_start = date(year, month, 1)
    if done is None or last_day < month_start:
        st.markdown(f'<div class="d-empty">{month_label} hasn\'t started yet. ♡</div>', unsafe_allow_html=True)
        return

    names = {t[0]: t[1] for t in chosen}
    cats = {t[0]: t[2] for t in chosen}
    daily = done.mean(axis=1)                       # share of habits done per day
    in_month = done.loc[pd.Timestamp(month_start):pd.Timestamp(last_day)]
    month_daily = daily.loc[in_month.index]

    if int(in_month.to_numpy().sum()) == 0:
        st.markdown(f'<div class="d-empty">Nothing logged for {month_label} yet.<br>'
                    'Tick a few habits in the Tracker and they\'ll show up here.</div>',
                    unsafe_allow_html=True)
        return

    rate = float(in_month.to_numpy().mean())
    py, pm = _shift_month(year, month, -1)
    prev_start, prev_end = pd.Timestamp(py, pm, 1), pd.Timestamp(py, pm, calendar.monthrange(py, pm)[1])
    prev = done.loc[prev_start:prev_end]
    if len(prev) and prev.to_numpy().sum() > 0:
        delta = rate - float(prev.to_numpy().mean())
        cls, arrow = ("up", "▲") if delta >= 0 else ("down", "▼")
        sub = f'<span class="{cls}">{arrow} {abs(delta) * 100:.0f} pts</span> vs {calendar.month_abbr[pm]}'
    else:
        sub = f"{len(in_month)} days tracked"

    # Streaks are measured on the full history up to the selected month's last tracked day.
    current, longest = _streaks(daily)
    perfect = int((month_daily >= 0.999).sum())

    st.markdown('<div class="d-kpis">' + "".join([
        _kpi("Consistency", f"{rate:.0%}", sub),
        _kpi("Current streak", current, f"days ≥ {STREAK_THRESHOLD:.0%} done", "days"),
        _kpi("Longest streak", longest, f"last {HISTORY_MONTHS} months", "days"),
        _kpi("Perfect days", perfect, f"of {len(in_month)} tracked"),
    ]) + "</div>", unsafe_allow_html=True)

    # ---- Insights --------------------------------------------------------
    habit_rates = in_month.mean().rename(index=names).sort_values(ascending=False)
    best_h, worst_h = habit_rates.index[0], habit_rates.index[-1]
    wd = month_daily.groupby(month_daily.index.dayofweek).mean()
    best_wd, worst_wd = int(wd.idxmax()), int(wd.idxmin())
    insights = [
        ("Strongest habit", f"<b>{escape(best_h)}</b> at {habit_rates.iloc[0]:.0%}. Keep it up.", ""),
        ("Needs love", f"<b>{escape(worst_h)}</b> is at {habit_rates.iloc[-1]:.0%}. Try anchoring it to an existing routine.", "peach"),
        ("Best weekday", f"<b>{calendar.day_name[best_wd]}</b> averages {wd.max():.0%}"
                         + (f"; {calendar.day_name[worst_wd]} is the softest at {wd.min():.0%}." if worst_wd != best_wd else "."), ""),
    ]
    st.markdown('<div class="d-insights">' + "".join(
        f'<div class="d-insight {cls}"><span class="tag">{tag}</span>{body}</div>' for tag, body, cls in insights
    ) + "</div>", unsafe_allow_html=True)

    # ---- Heatmap + weekly trend -----------------------------------------
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        with st.container(border=True):
            st.markdown(f'<h3>Daily heatmap</h3><div class="cap">{month_label} · share of habits done each day</div>', unsafe_allow_html=True)
            st.plotly_chart(_heatmap(daily, year, month), use_container_width=True, theme=None, config={"displayModeBar": False})
    with right:
        with st.container(border=True):
            st.markdown('<h3>Weekly trend</h3><div class="cap">Average completion, last 12 weeks</div>', unsafe_allow_html=True)
            st.plotly_chart(_weekly_trend(daily), use_container_width=True, theme=None, config={"displayModeBar": False})

    # ---- Habit bars + categories ----------------------------------------
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        rates = in_month.mean().sort_values(ascending=False)
        recent = done.tail(14)
        rolling = done.rolling(7, min_periods=1).mean().tail(14)
        rows = []
        for task_id, r in rates.items():
            rows.append(
                '<div class="d-habit">'
                f'<div><div class="nm">{escape(names[task_id])}</div><div class="cat">{escape(cats[task_id])}</div></div>'
                f'<div class="bar-col"><div class="d-bar"><span style="width:{r * 100:.0f}%"></span></div></div>'
                f'<div class="d-pct">{r:.0%}</div>'
                f'<div class="spark" title="7-day rolling rate, last {len(recent)} days">{_sparkline(rolling[task_id].tolist())}</div>'
                '</div>'
            )
        with st.container(border=True):
            st.markdown('<h3>Habit consistency</h3><div class="cap">Selected month · sparkline shows 7-day rolling rate over the last 14 days</div>'
                        + "".join(rows), unsafe_allow_html=True)
    with right:
        cat_rates = in_month.mean().groupby(pd.Series(cats)).mean()
        with st.container(border=True):
            st.markdown('<h3>By category</h3><div class="cap">Average completion per category</div>', unsafe_allow_html=True)
            st.plotly_chart(_category_chart(cat_rates), use_container_width=True, theme=None, config={"displayModeBar": False})
