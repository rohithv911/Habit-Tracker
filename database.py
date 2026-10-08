import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "data" / "consistency.db"

DEFAULT_TASKS = [
    ("Leetcode", "DSA/Interviews"),
    ("Running/Workout", "Fitness"),
    ("Codeforces", "Competitive Programming"),
    ("Oats + Eggs", "Diet"),
    ("Courses", "Upskilling"),
    ("7 hours of academics", "Academics"),
    ("6 hours of academics", "Academics"),
    ("5 hours of academics", "Academics"),
    ("Wake up before 5:30", "Personal"),
    ("7-8 hours of sleep", "Personal"),
    ("Reading", "Personal"),
]


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_completion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                UNIQUE(task_id, date),
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_metadata (
                month TEXT PRIMARY KEY,
                intention TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                reflection_well TEXT NOT NULL DEFAULT '',
                reflection_improve TEXT NOT NULL DEFAULT '',
                reflection_proud TEXT NOT NULL DEFAULT '',
                reflection_next TEXT NOT NULL DEFAULT ''
            )
        """)


def seed_tasks():
    with get_connection() as conn:
        default_names = [name for name, category in DEFAULT_TASKS]

        # Deactivate tasks that are no longer part of the current task list
        if default_names:
            placeholders = ",".join("?" for _ in default_names)
            conn.execute(
                f"""
                UPDATE tasks
                SET active = 0
                WHERE name NOT IN ({placeholders})
                """,
                default_names,
            )

        # Add new tasks and reactivate current tasks
        for name, category in DEFAULT_TASKS:
            exists = conn.execute(
                "SELECT 1 FROM tasks WHERE name = ? LIMIT 1",
                (name,),
            ).fetchone()

            if exists:
                conn.execute(
                    "UPDATE tasks SET active = 1, category = ? WHERE name = ?",
                    (category, name),
                )
            else:
                conn.execute(
                    "INSERT INTO tasks (name, category) VALUES (?, ?)",
                    (name, category),
                )


def get_tasks():
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, name, category
            FROM tasks
            WHERE active = 1
            ORDER BY id
        """).fetchall()


def get_month_matrix(year: int, month: int):
    prefix = f"{year:04d}-{month:02d}-%"
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT task_id, date, completed
            FROM daily_completion
            WHERE date LIKE ?
        """, (prefix,)).fetchall()

    return {(task_id, day): bool(completed) for task_id, date, completed in rows
            for day in [int(date[-2:])]}


def save_month_matrix(matrix, year: int, month: int):
    with get_connection() as conn:
        for task_id, days in matrix.items():
            for day, completed in days.items():
                date_string = f"{year:04d}-{month:02d}-{day:02d}"
                conn.execute("""
                    INSERT INTO daily_completion (task_id, date, completed)
                    VALUES (?, ?, ?)
                    ON CONFLICT(task_id, date)
                    DO UPDATE SET completed = excluded.completed
                """, (task_id, date_string, int(bool(completed))))


def get_month_metadata(month_key: str):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT intention, notes, reflection_well,
                   reflection_improve, reflection_proud, reflection_next
            FROM monthly_metadata
            WHERE month = ?
        """, (month_key,)).fetchone()

    if not row:
        return {
            "intention": "",
            "notes": "",
            "reflection_well": "",
            "reflection_improve": "",
            "reflection_proud": "",
            "reflection_next": "",
        }

    keys = [
        "intention", "notes", "reflection_well", "reflection_improve",
        "reflection_proud", "reflection_next"
    ]
    return dict(zip(keys, row))


def save_month_metadata(month_key: str, values: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO monthly_metadata
                (month, intention, notes, reflection_well,
                 reflection_improve, reflection_proud, reflection_next)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(month) DO UPDATE SET
                intention = excluded.intention,
                notes = excluded.notes,
                reflection_well = excluded.reflection_well,
                reflection_improve = excluded.reflection_improve,
                reflection_proud = excluded.reflection_proud,
                reflection_next = excluded.reflection_next
        """, (
            month_key,
            values.get("intention", ""),
            values.get("notes", ""),
            values.get("reflection_well", ""),
            values.get("reflection_improve", ""),
            values.get("reflection_proud", ""),
            values.get("reflection_next", ""),
        ))
