# Habit Tracker Dashboard

A personal monthly habit dashboard inspired by the provided printable habit-tracker design.

## Features

- Monthly habit grid with 1–28/29/30/31 day columns
- Clickable Done / Not Done checkboxes
- Persistent SQLite storage
- Monthly consistency percentage
- Weekly progress bars
- Monthly intention
- Notes
- Monthly reflection
- Warm paper / sage / peach visual theme
- Month selector for reviewing previous months

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The database is created automatically at `data/consistency.db`.
