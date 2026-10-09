import calendar
from copy import deepcopy
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from database import (
    initialize_database,
    seed_tasks,
    get_tasks,
    get_month_matrix,
    save_month_matrix,
    get_month_metadata,
    save_month_metadata,
)

st.set_page_config(
    page_title="Habit Tracker",
    page_icon="♡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

initialize_database()
seed_tasks()

# -----------------------------
# Theme / styling
# -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=DM+Sans:wght@400;500;600&display=swap');

:root {
    --ink: #293126;
    --muted: #77766c;
    --sage: #9da88c;
    --sage-dark: #667157;
    --cream: #fbf8f1;
    --paper: #fffdf8;
    --line: #d9d1c2;
    --peach: #e9bda2;
    --peach-light: #f7e2d5;
    --green-light: #e7ecdf;
}

.stApp {
    background:
        radial-gradient(circle at 7% 7%, rgba(233,189,162,.20) 0 55px, transparent 56px),
        radial-gradient(circle at 94% 11%, rgba(157,168,140,.16) 0 75px, transparent 76px),
        linear-gradient(180deg, #fbf8f1 0%, #fffdf8 100%);
    color: var(--ink);
}

.block-container {
    max-width: 1450px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3, .serif {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    color: var(--ink) !important;
}

p, label, .stMarkdown, .stCaption, .stTextInput, .stTextArea {
    font-family: 'DM Sans', sans-serif;
}

.hero {
    text-align: center;
    padding: 12px 0 18px;
}
.hero .small-title {
    font-family: 'DM Sans', sans-serif;
    letter-spacing: .25em;
    font-size: .78rem;
    color: var(--sage-dark);
    text-transform: uppercase;
    margin-bottom: -3px;
}
.hero h1 {
    font-size: clamp(3.5rem, 8vw, 6.5rem) !important;
    line-height: .85;
    margin: 0;
    font-weight: 600;
    letter-spacing: -.045em;
}
.hero .tracker {
    color: #b65f37;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-style: italic;
    font-size: clamp(2.4rem, 5vw, 4.4rem);
    margin-left: .15em;
}
.tagline {
    display: inline-block;
    margin-top: 18px;
    padding: 8px 24px;
    border-radius: 6px;
    background: #dfe3d2;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-style: italic;
    font-size: 1.15rem;
    transform: rotate(-.5deg);
}

.paper-card {
    background: rgba(255,253,248,.82);
    border: 1px solid var(--line);
    border-radius: 14px;
    box-shadow: 0 8px 28px rgba(77,66,48,.06);
    padding: 18px 20px;
}

.field-label {
    font-size: .78rem;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: #4c5047;
    font-weight: 600;
}

.month-title {
    text-align: center;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2.25rem;
    font-weight: 600;
    margin: 6px 0 16px;
}

.section-ribbon {
    display: inline-block;
    background: #9da88c;
    color: white;
    padding: 6px 28px;
    border-radius: 3px 18px 3px 18px;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.25rem;
    letter-spacing: .08em;
    margin: 8px 0 10px;
}

.week-card {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: rgba(255,253,248,.85);
    padding: 14px 16px;
    height: 100%;
}
.week-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 11px 0;
}
.week-label { width: 74px; font-size: .78rem; font-weight: 600; }
.dot {
    width: 16px; height: 16px; border-radius: 50%;
    border: 1px solid #aaa28f; display: inline-block;
}
.dot.on { background: #9da88c; border-color: #9da88c; }

.reflection-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.15rem;
    font-weight: 600;
    margin-top: 12px;
    color: #4a493f;
}

div[data-testid="stDataEditor"] {
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
    background: var(--paper);
}

.stButton > button {
    border-radius: 20px;
    border: 1px solid #bdb5a6;
    background: #fffdf8;
    color: var(--ink);
    font-family: 'DM Sans', sans-serif;
}
.stButton > button:hover {
    border-color: var(--sage-dark);
    color: var(--sage-dark);
}

.save-btn button {
    background: #6f795f !important;
    color: white !important;
    border-color: #6f795f !important;
}

div[data-testid="stMetric"] {
    background: rgba(255,253,248,.75);
    border: 1px solid var(--line);
    padding: 12px;
    border-radius: 12px;
}

.footer-note {
    text-align: center;
    color: #77766c;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-style: italic;
    font-size: 1.25rem;
    padding: 20px;
}

@media (max-width: 900px) {
    .block-container { padding: 1rem .65rem 2rem; }
    .hero h1 { font-size: 4rem !important; }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Helpers
# -----------------------------

def month_key(year, month):
    return f"{year:04d}-{month:02d}"


def build_editor_dataframe(tasks, saved, days_in_month):
    rows = []
    for task_id, name, category in tasks:
        row = {"Habit": name}
        for day in range(1, days_in_month + 1):
            row[str(day)] = bool(saved.get((task_id, day), False))
        rows.append(row)
    return pd.DataFrame(rows)


def dataframe_to_matrix(editor_df, tasks):
    matrix = {}
    for row_index, (task_id, _, _) in enumerate(tasks):
        matrix[task_id] = {}
        for day in editor_df.columns:
            if day == "Habit":
                continue
            matrix[task_id][int(day)] = bool(editor_df.iloc[row_index][day])
    return matrix


def weekly_stats(editor_df, days_in_month):
    stats = []

    # Build a mapping that works whether Streamlit/Pandas
    # represents the day columns as integers or strings.
    day_column_map = {}

    for column in editor_df.columns:
        try:
            day_number = int(column)

            if 1 <= day_number <= days_in_month:
                day_column_map[day_number] = column

        except (TypeError, ValueError):
            continue

    starts = list(range(1, days_in_month + 1, 7))

    for start in starts:
        end = min(start + 6, days_in_month)

        actual_columns = [
            day_column_map[day]
            for day in range(start, end + 1)
            if day in day_column_map
        ]

        if not actual_columns:
            stats.append((start, end, 0))
            continue

        values = editor_df[actual_columns].to_numpy(dtype=bool)

        total = values.size
        done = int(values.sum())

        rate = done / total if total else 0

        stats.append((start, end, rate))

    return stats

# -----------------------------
# Header
# -----------------------------
st.markdown("""
<div class="hero">
    <div class="small-title">personal consistency dashboard</div>
    <h1>HABIT <span class="tracker">Tracker</span></h1>
    <div class="tagline">Consistency today, progress tomorrow. ♡</div>
</div>
""", unsafe_allow_html=True)

# -----------------------------
# Month selector
# -----------------------------
today = date.today()
selector_col1, selector_col2, selector_col3 = st.columns([1.2, 1, 1.2])

# Streamlit's date_input only accepts numeric date formats, so use
# separate month/year selectors for a clean month-only control.
with selector_col1:
    month_options = list(range(1, 13))
    selected_month_num = st.selectbox(
        "MONTH",
        month_options,
        index=today.month - 1,
        format_func=lambda m: calendar.month_name[m],
    )

with selector_col2:
    year_options = list(range(today.year - 2, today.year + 3))
    selected_year = st.selectbox(
        "YEAR",
        year_options,
        index=year_options.index(today.year),
    )

days_in_month = calendar.monthrange(selected_year, selected_month_num)[1]
month_name = calendar.month_name[selected_month_num]
key = month_key(selected_year, selected_month_num)

metadata = get_month_metadata(key)

with selector_col2:
    st.markdown(f"<div class='month-title'>{month_name} {selected_year}</div>", unsafe_allow_html=True)

with selector_col3:
    intention = st.text_input(
        "THIS MONTH'S INTENTION",
        value=metadata["intention"],
        placeholder="What do you want to focus on?",
        key=f"intention_{key}",
    )

# -----------------------------
# Habit matrix
# -----------------------------
st.markdown('<div class="section-ribbon">HABITS</div>', unsafe_allow_html=True)

tasks = get_tasks()
saved = get_month_matrix(selected_year, selected_month_num)
initial_df = build_editor_dataframe(tasks, saved, days_in_month)

session_key = f"baseline_{key}"
if session_key not in st.session_state:
    st.session_state[session_key] = initial_df.copy()

column_config = {
    "Habit": st.column_config.TextColumn(
        "HABITS",
        width="medium",
        disabled=True,
    )
}

for day in range(1, days_in_month + 1):
    column_config[str(day)] = st.column_config.CheckboxColumn(
        str(day),
        help=f"Day {day}",
        default=False,
        width="small",
    )

edited_df = st.data_editor(
    initial_df,
    key=f"habit_editor_{key}",
    hide_index=True,
    use_container_width=True,
    column_config=column_config,
    height=min(620, 92 + len(tasks) * 62),
    num_rows="fixed",
)

if not edited_df.equals(st.session_state[session_key]):
    matrix = dataframe_to_matrix(edited_df, tasks)
    save_month_matrix(matrix, selected_year, selected_month_num)
    st.session_state[session_key] = edited_df.copy()
    st.toast("Saved ♡", icon="💾")

# -----------------------------
# Monthly summary
# -----------------------------
total_possible = len(tasks) * days_in_month
completed_total = int(edited_df.drop(columns=["Habit"]).to_numpy(dtype=bool).sum()) if tasks else 0
monthly_rate = completed_total / total_possible if total_possible else 0

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Month consistency", f"{monthly_rate:.0%}")
with m2:
    st.metric("Habits", len(tasks))
with m3:
    st.metric("Completed", completed_total)
with m4:
    st.metric("Days", days_in_month)

# -----------------------------
# Weekly progress / notes / reflection
# -----------------------------
st.markdown('<div class="section-ribbon">WEEKLY PROGRESS</div>', unsafe_allow_html=True)

weekly = weekly_stats(edited_df, days_in_month)
week_cols = st.columns(len(weekly))
for index, (start, end, rate) in enumerate(weekly):
    with week_cols[index]:
        st.markdown(f"**Week {index + 1}**  `{start}–{end}`")
        st.progress(rate)
        st.caption(f"{rate:.0%} complete")

st.divider()

left, middle, right = st.columns([1, 1.15, 1.15])

with left:
    st.markdown('<div class="section-ribbon">NOTES</div>', unsafe_allow_html=True)
    notes = st.text_area(
        "",
        value=metadata["notes"],
        height=220,
        placeholder="Small observations, wins, reminders...",
        key=f"notes_{key}",
        label_visibility="collapsed",
    )

with middle:
    st.markdown('<div class="section-ribbon">MONTHLY REFLECTION</div>', unsafe_allow_html=True)
    reflection_well = st.text_input(
        "What went well this month?",
        value=metadata["reflection_well"],
        key=f"well_{key}",
    )
    reflection_improve = st.text_input(
        "What can I improve?",
        value=metadata["reflection_improve"],
        key=f"improve_{key}",
    )

with right:
    st.markdown('<div class="section-ribbon">NEXT MONTH</div>', unsafe_allow_html=True)
    reflection_proud = st.text_area(
        "I am proud of myself for:",
        value=metadata["reflection_proud"],
        height=90,
        key=f"proud_{key}",
    )
    reflection_next = st.text_area(
        "Next month, I will:",
        value=metadata["reflection_next"],
        height=90,
        key=f"next_{key}",
    )

st.markdown('<div class="save-btn">', unsafe_allow_html=True)
if st.button("Save monthly intention & reflection", use_container_width=True):
    save_month_metadata(key, {
        "intention": intention,
        "notes": notes,
        "reflection_well": reflection_well,
        "reflection_improve": reflection_improve,
        "reflection_proud": reflection_proud,
        "reflection_next": reflection_next,
    })
    st.toast("Monthly reflection saved ♡", icon="💾")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-note">Focus on progress, not perfection. ♥</div>', unsafe_allow_html=True)
