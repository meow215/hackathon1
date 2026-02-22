# app.py
import os 
import streamlit as st
import json
import smtplib
import random
from email.message import EmailMessage
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


def generate_plan(tasks, weekday_cap_hours=3.0, weekend_cap_hours=2.0):
    today = date.today()

    active = [t for t in tasks if t["remaining_hours"] > 0]
    active.sort(key=lambda t: (parse_date(t["due_date"]), t["priority"]))

    plan = {}
    warnings = []

    if not active:
        return plan, warnings

    last_due = max(parse_date(t["due_date"]) for t in active)

    # Create days + capacity (weekday vs weekend)
    cap = {}
    day = today
    while day <= last_due:
        dkey = str(day)
        plan[dkey] = []

        # weekday: Mon(0)..Fri(4), weekend: Sat(5), Sun(6)
        if day.weekday() >= 5:
            cap[dkey] = float(weekend_cap_hours)
        else:
            cap[dkey] = float(weekday_cap_hours)

        day += timedelta(days=1)

    # Allocate hours greedily
    for t in active:
        due = parse_date(t["due_date"])
        hours_left = t["remaining_hours"]
        day = parse_date(t["start_date"])

        while day <= due and hours_left > 0:
            dkey = str(day)
            if cap.get(dkey, 0) > 0:
                h = min(cap[dkey], hours_left)
                plan[dkey].append((t["name"], round(h, 2)))
                cap[dkey] -= h
                hours_left -= h
            day += timedelta(days=1)

        if hours_left > 0:
            warnings.append(
                f"Not enough time for **{t['name']}**: short by {round(hours_left,2)} hours before {t['due_date']}."
            )

    # Remove empty days for cleaner display
    plan = {d: items for d, items in plan.items() if items}
    return plan, warnings


def SendReminderEmails(address, name, due_date):
    sender = st.secrets.get("EMAIL")
    password = st.secrets.get("PASSWORD")

    if not sender or not password:
        st.error("Missing EMAIL/PASSWORD in Streamlit secrets.")
        return

    
    message = EmailMessage()
    message["From"] = sender
    message["To"] = address
    message["Subject"] = f"⏰ Reminder: '{name}' due tomorrow"
    message.set_content(
        f"""
Hey there!

Just a friendly reminder that your task:

  📌 {name}

is due on:

  📅 {due_date}

Good luck!

-Smart Study Planner
"""
)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(message)

st.set_page_config(page_title="Smart Study Planner", layout="centered")
st.title("📚 Smart Study Planner")

tasks = load_tasks()

# Normalize tasks (add remaining_hours field)
for t in tasks:
    if "done_hours" not in t:
        t["done_hours"] = 0.0
    t["remaining_hours"] = max(0.0, float(t["estimated_hours"]) - float(t["done_hours"]))
    if "email" not in t:
        t["email"] = []
    if "email_sent" not in t:
        t["email_sent"] = False
    if "archived" not in t:
        t["archived"] = False
    if "start_date" not in t:
        t["start_date"] = str(date.today())

tasks_updated = False
today = date.today()
for t in tasks:
    due_date_obj = parse_date(t["due_date"])
    if t.get("email") and not t.get("email_sent", False):
        # Check if task is due tomorrow
        if due_date_obj - timedelta(days=1) == today:
            try:
                SendReminderEmails(t["email"], t["name"], t["due_date"])
                t["email_sent"] = True
                tasks_updated = True
                st.success(f"Reminder sent for '{t['name']}'!")
            except Exception as e:
                st.error(f"Failed to send email for '{t['name']}': {e}")

# Save updates if any emails were sent
if tasks_updated:
    save_tasks(tasks)

tab1, tab2, tab3, tab4, tab5= st.tabs(["📰 Today's Tasks", "➕ Add Task", "📋 All Tasks", "🗓️ Plan", "📓 History"])

with tab1:
    n = random.randint(1, 5)
    match n:
        case 1:
            header = "What's new for today? 🌤️"
        case 2:
            header = "Are you ready for a fresh new day? 🌈"
        case 3:
            header = "Good to see you again! Eager for some productivity? 💪"
        case 4:
            header = "Keep on with the good work! 😊"
        case 5:
            header = "What a lovely day for a new adventure! 🎵"
    st.subheader(header)
    no_task = True
    index = 1
    for t in tasks:
        if t["archived"] == False and parse_date(t["start_date"]) <= parse_date(str(date.today())) and parse_date(str(date.today())) <= parse_date(t["due_date"]):
            cols = st.columns([1, 8])
            cols[0].write(f"{index}.")
            cols[1].write(f"**{t['name']}**")
            index += 1
            no_task = False
    if no_task:
        st.info("Hooray! No task for today!")

with tab2:
    st.subheader("Add a task")
    name = st.text_input("Task name")
    start = st.date_input("Start date", value = date.today())
    due = st.date_input("Due date", value=date.today() + timedelta(days=7))
    hours = st.number_input("Estimated hours", min_value=0.5, max_value=200.0, value=5.0, step=0.5)
    priority = st.selectbox("Priority (1 = high)", [1, 2, 3], index=1)
    email = st.text_input("Reminder email address (optional)")

    if st.button("Add"):
        if not name.strip():
            st.error("Please enter a task name.")
        else:
            tasks.append({
                "name": name.strip(),
                "start_date": str(start),
                "due_date": str(due),
                "estimated_hours": float(hours),
                "done_hours": 0.0,
                "priority": int(priority),
                "email": email.strip(),
                "email_sent": False,
                "archived": False
            })
            save_tasks(tasks)
            st.success("Task added!")
            st.rerun()

with tab3:
    st.subheader("Your tasks")
    no_task = True
    for t in tasks:
        if t["archived"] == False:
            no_task = False
    if no_task:
        st.info("No tasks yet. Add one!")
    else:
        for i, t in enumerate(tasks):
            if t["archived"] == True:
                continue
            remaining = max(0.0, t["estimated_hours"] - t["done_hours"])
            progress = min(1.0, t["done_hours"] / t["estimated_hours"])
            percent = int(100 * progress)
            cols = st.columns([3, 2, 2, 2])
            cols[0].write(f"**{t['name']}**")
            cols[1].write(f"Due: {t['due_date']}")
            cols[2].write(f"Remaining: {remaining:.1f}h")
            add_done = cols[3].number_input(
                "Add done hours",
                min_value=0.0, max_value=float(t["estimated_hours"]), value=0.0, step=0.5,
                key=f"done_{i}"
            )
            st.progress(progress, text = f"{percent}% complete")
            edit_open = st.checkbox("Edit", key=f"edit_{i}")

            if edit_open:
                with st.expander("Edit task", expanded=True):
                    new_due = st.date_input("Due date", value=parse_date(t["due_date"]), key=f"due_edit_{i}")
                    new_est = st.number_input(
                        "Estimated hours",
                        min_value=0.5,
                        max_value=200.0,
                        value=float(t["estimated_hours"]),
                        step=0.5,
                        key=f"est_edit_{i}",
                    )

                    # Optional: let user directly set remaining hours
                    # This works by adjusting done_hours accordingly.
                    new_remaining = st.number_input(
                        "Remaining hours",
                        min_value=0.0,
                        max_value=float(new_est),
                        value=max(0.0, float(new_est) - float(t["done_hours"])),
                        step=0.5,
                        key=f"rem_edit_{i}",
                    )

                    if st.button("Save edits", key=f"save_edit_{i}"):
                        t["due_date"] = str(new_due)
                        t["estimated_hours"] = float(new_est)

                        # Convert "remaining hours" into done_hours
                        t["done_hours"] = max(0.0, float(new_est) - float(new_remaining))

                        # If due date changed, you probably want to allow email again:
                        t["email_sent"] = False

                        save_tasks(tasks)
                        st.success("Edits saved!")
                        st.rerun()
            c1, spacer, c3 = st.columns([1, 6, 1])  # spacer pushes Delete to the right

            if c1.button("Update", key=f"upd_{i}"):
                t["done_hours"] = min(t["estimated_hours"], t["done_hours"] + add_done)
                save_tasks(tasks)
                st.success("Updated!")
                st.rerun()

            if c3.button("Delete", key=f"del_{i}"):
                t["archived"] = True
                save_tasks(tasks)
                st.warning("Deleted.")
                st.rerun()

with tab4:
    st.subheader("Generate your plan")
    weekday_cap = st.slider("Max study hours per weekday (Mon–Fri)", 0.0, 10.0, 3.0, 0.5)
    weekend_cap = st.slider("Max study hours per weekend day (Sat–Sun)", 0.0, 10.0, 2.0, 0.5)
    # Recompute remaining hours
    for t in tasks:
        t["remaining_hours"] = max(0.0, float(t["estimated_hours"]) - float(t["done_hours"]))

    plan, warnings = generate_plan(tasks, weekday_cap_hours=float(weekday_cap), weekend_cap_hours=float(weekend_cap))

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

with tab5:
    st.subheader("View plan history")
    no_task = True
    for t in tasks:
        if t["archived"] == True:
            no_task = False
    if no_task:
        st.info("No history to view yet")
    else:
        for i, t in enumerate(tasks):
            if t["archived"] == False:
                continue
            cols = st.columns([3, 2, 2, 2])
            cols[0].write(f"**{t['name']}**")
            cols[1].write(f"Due: {t['due_date']}")
            cols[2].write(f"Estimated time: {t['estimated_hours']}")
            if cols[3].button("Restore", key = f"res_{i}"):
                t["archived"] = False
                t["done_hours"] = 0.0
                save_tasks(tasks)
                st.success("Updated!")
                st.rerun()