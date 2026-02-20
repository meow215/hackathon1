# app.py
import os 
import streamlit as st
import json
from datetime import date, datetime, timedelta

DB_FILE = "tasks.json"

def load_tasks():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        # Backup the broken file so you can inspect it later
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{DB_FILE}.broken_{ts}.bak"
        try:
            os.rename(DB_FILE, backup_name)
        except OSError:
            # If rename fails (rare), just ignore and start fresh
            pass
        return []


def save_tasks(tasks):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date()


def generate_plan(tasks, daily_cap_hours=3.0, start_day=None):
    start_day = start_day or date.today()
    # only unfinished tasks
    active = [t for t in tasks if t["remaining_hours"] > 0]
    # sort by due date then priority (1 highest)
    active.sort(key=lambda t: (parse_date(t["due_date"]), t["priority"]))

    plan = {}  # day -> list of (task_name, hours)
    warnings = []

    # build list of days up to max due date
    if not active:
        return plan, warnings
    
    last_due = max(parse_date(t["due_date"]) for t in active)

#add cap?




    day = start_day
    while day <= last_due:
        plan[str(day)] = []
        day += timedelta(days=1)

    # track remaining capacity per day
    cap = {d: daily_cap_hours for d in plan.keys()}



    for t in active:
        due = parse_date(t["due_date"])
        hours_left = t["remaining_hours"]
        day = start_day

        # allocate from start_day to due date for each task
        while day <= due and hours_left > 0:
            dkey = str(day)
            if dkey in cap and cap[dkey] > 0:
                h = min(cap[dkey], hours_left)
                plan[dkey].append((t["name"], round(h, 2)))
                cap[dkey] -= h
                hours_left -= h
            day += timedelta(days=1)

        if hours_left > 0:
            warnings.append(
                f"Not enough time for **{t['name']}**: short by {round(hours_left,2)} hours before {t['due_date']}."
            )

    # remove empty days
    plan = {d: items for d, items in plan.items() if items}
    return plan, warnings

st.set_page_config(page_title="Smart Study Planner", layout="centered")
st.title("📚 Smart Study Planner")

tasks = load_tasks()

# Normalize tasks (add remaining_hours field)
for t in tasks:
    if "done_hours" not in t:
        t["done_hours"] = 0.0
    t["remaining_hours"] = max(0.0, float(t["estimated_hours"]) - float(t["done_hours"]))

tab1, tab2, tab3 = st.tabs(["➕ Add Task", "📋 Tasks", "🗓️ Plan"])

with tab1:
    st.subheader("Add a task")
    name = st.text_input("Task name")
    due = st.date_input("Due date", value=date.today() + timedelta(days=7))
    hours = st.number_input("Estimated hours", min_value=0.5, max_value=200.0, value=5.0, step=0.5)
    priority = st.selectbox("Priority (1 = high)", [1, 2, 3], index=1)

    if st.button("Add"):
        if not name.strip():
            st.error("Please enter a task name.")
        else:
            tasks.append({
                "name": name.strip(),
                "due_date": str(due),
                "estimated_hours": float(hours),
                "done_hours": 0.0,
                "priority": int(priority)
            })
            save_tasks(tasks)
            st.success("Task added!")

with tab2:
    st.subheader("Your tasks")
    if not tasks:
        st.info("No tasks yet. Add one!")
    else:
        for i, t in enumerate(tasks):
            remaining = max(0.0, t["estimated_hours"] - t["done_hours"])
            cols = st.columns([3, 2, 2, 2])
            cols[0].write(f"**{t['name']}**")
            cols[1].write(f"Due: {t['due_date']}")
            cols[2].write(f"Remaining: {remaining:.1f}h")
            add_done = cols[3].number_input(
                "Add done hours",
                min_value=0.0, max_value=float(t["estimated_hours"]), value=0.0, step=0.5,
                key=f"done_{i}"
            )
            c1, c2 = st.columns([1, 1])
            if c1.button("Update", key=f"upd_{i}"):
                t["done_hours"] = min(t["estimated_hours"], t["done_hours"] + add_done)
                save_tasks(tasks)
                st.success("Updated!")
            if c2.button("Delete", key=f"del_{i}"):
                tasks.pop(i)
                save_tasks(tasks)
                st.warning("Deleted.")
                st.rerun()

with tab3:
    st.subheader("Generate your plan")
    daily_cap = st.slider("Max study hours per day", 1.0, 10.0, 3.0, 0.5)

    # Recompute remaining hours
    for t in tasks:
        t["remaining_hours"] = max(0.0, float(t["estimated_hours"]) - float(t["done_hours"]))

    plan, warnings = generate_plan(tasks, daily_cap_hours=float(daily_cap))

    if warnings:
        for w in warnings:
            st.error(w)

    if not plan:
        st.info("Nothing to schedule (either no tasks or all done).")
    else:
        for day, items in plan.items():
            st.markdown(f"### {day}")
            for task_name, h in items:
                st.write(f"- {task_name}: **{h}h**")