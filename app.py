import streamlit as st
import sqlite3
import hashlib
import datetime
import pandas as pd

# -----------------------------
# Database Setup
# -----------------------------
conn = sqlite3.connect("fitness.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    weight REAL,
    height REAL,
    dob TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    description TEXT,
    calories INTEGER,
    water INTEGER,
    created_at TEXT
)
""")

conn.commit()

# -----------------------------
# Utility Functions
# -----------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def calculate_age(dob):
    dob = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
    today = datetime.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def register_user(username, password, weight, height, dob):
    try:
        cursor.execute(
            "INSERT INTO users (username, password, weight, height, dob) VALUES (?, ?, ?, ?, ?)",
            (username, hash_password(password), weight, height, dob)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, hash_password(password))
    )
    return cursor.fetchone()

def update_profile(user_id, weight, height):
    cursor.execute(
        "UPDATE users SET weight=?, height=? WHERE id=?",
        (weight, height, user_id)
    )
    conn.commit()

def insert_log(user_id, log_type, description, calories=0, water=0, log_date=None):
    if log_date is None:
        log_date = datetime.now()
    else:
        log_date = datetime.combine(log_date, datetime.now().time())

    cursor.execute(
        "INSERT INTO logs (user_id, type, description, calories, water, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, log_type, description, calories, water,
         log_date.strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

def get_logs(user_id):
    cursor.execute("SELECT * FROM logs WHERE user_id=?", (user_id,))
    return cursor.fetchall()

# -----------------------------
# Calorie Estimation
# -----------------------------
def estimate_food_calories(text):
    return 500  # placeholder

def estimate_workout_calories(text, weight):
    text = text.lower()
    base = weight * 0.1
    if "run" in text:
        return int(base * 8)
    elif "walk" in text:
        return int(base * 4)
    elif "gym" in text:
        return int(base * 6)
    else:
        return int(base * 5)

# -----------------------------
# Session
# -----------------------------
if "user" not in st.session_state:
    st.session_state.user = None

# -----------------------------
# Auth Section
# -----------------------------
if not st.session_state.user:

    st.title("🔐 Fitness Tracker")

    menu = st.radio("Select", ["Login", "Register"])

    if menu == "Register":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        weight = st.number_input("Weight (kg)", min_value=1.0)
        height = st.number_input("Height (cm)", min_value=1.0)
        dob = st.date_input(
                    "Date of Birth",
                    min_value=datetime.date(1960, 1, 1),
                    max_value=datetime.date.today()
                )

        if st.button("Register"):
            success = register_user(
                username, password, weight, height, dob.strftime("%Y-%m-%d")
            )
            if success:
                st.success("Account created! Please login.")
            else:
                st.error("Username already exists!")

    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials")

# -----------------------------
# Dashboard
# -----------------------------
else:
    user = st.session_state.user
    user_id = user[0]
    username = user[1]
    weight = user[3]
    height = user[4]
    dob = user[5]

    age = calculate_age(dob)

    st.title(f"🔥 Welcome {username}")

    st.write(f"Age: {age}")
    st.write(f"Weight: {weight} kg | Height: {height} cm")

    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()

    # -----------------------------
    # Update Profile
    # -----------------------------
    st.subheader("Update Weight & Height")
    new_weight = st.number_input("New Weight", value=float(weight))
    new_height = st.number_input("New Height", value=float(height))

    if st.button("Update Profile"):
        update_profile(user_id, new_weight, new_height)
        st.success("Profile Updated")
        st.rerun()

    # -----------------------------
    # Logging Section
    # -----------------------------
    st.subheader("➕ Add Entry")

    with st.form("entry_form"):

        entry_date = st.date_input("Select Date", value=datetime.date.today())

        entry_type = st.selectbox(
            "Entry Type",
            ["Food", "Workout", "Water"]
        )

        description = st.text_input("Description (Food / Workout name)")

        water_amount = st.number_input(
            "Water Intake (ml) — only for Water type",
            min_value=0,
            value=0
        )

        submit = st.form_submit_button("Add Entry")

        if submit:

            if entry_type in ["Food", "Workout"] and description.strip() == "":
                st.error("Please enter description.")
            elif entry_type == "Water" and water_amount <= 0:
                st.error("Please enter water amount.")
            else:

                if entry_type == "Food":
                    calories = estimate_food_calories(description)
                    insert_log(
                        user_id,
                        "food",
                        description,
                        calories=calories,
                        log_date=entry_date
                    )
                    st.success(f"Food logged: {calories} calories")

                elif entry_type == "Workout":
                    burned = estimate_workout_calories(description, weight)
                    insert_log(
                        user_id,
                        "workout",
                        description,
                        calories=burned,
                        log_date=entry_date
                    )
                    st.success(f"Workout logged: {burned} calories burned")

                elif entry_type == "Water":
                    insert_log(
                        user_id,
                        "water",
                        "Water Intake",
                        water=water_amount,
                        log_date=entry_date
                    )
                    st.success(f"Water logged: {water_amount} ml")

                st.rerun()

    # -----------------------------
    # Analysis Section
    # -----------------------------
    st.header("📊 Analysis Dashboard")

    logs = get_logs(user_id)
    df = pd.DataFrame(
        logs,
        columns=["id", "user_id", "type", "desc", "calories", "water", "created_at"]
    )

    if not df.empty:

        df["created_at"] = pd.to_datetime(df["created_at"])
        df["date"] = df["created_at"].dt.date

        # -----------------------------
        # Filter Buttons
        # -----------------------------
        range_option = st.radio(
            "Select Range",
            ["Last 7 Days", "Last 30 Days", "Last 1 Year"],
            horizontal=True
        )

        today = datetime.date.today()

        if range_option == "Last 7 Days":
            start_date = today - pd.Timedelta(days=7)
        elif range_option == "Last 30 Days":
            start_date = today - pd.Timedelta(days=30)
        else:
            start_date = today - pd.Timedelta(days=365)

        filtered = df[df["date"] >= start_date]

        # -----------------------------
        # KPI Section (2 Columns)
        # -----------------------------
        food_total = filtered[filtered["type"] == "food"]["calories"].sum()
        workout_total = filtered[filtered["type"] == "workout"]["calories"].sum()
        water_total = filtered[filtered["type"] == "water"]["water"].sum()
        net = food_total - workout_total

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Calories Consumed", food_total)
            st.metric("Net Calories", net)

        with col2:
            st.metric("Calories Burned", workout_total)
            st.metric("Water Intake (ml)", water_total)

        # -----------------------------
        # Calories Trend (2 Lines)
        # -----------------------------
        st.subheader("🔥 Calories Trend")

        calories_chart = filtered[filtered["type"].isin(["food", "workout"])]
        calories_grouped = calories_chart.groupby(
            ["date", "type"]
        )["calories"].sum().unstack().fillna(0)

        st.line_chart(calories_grouped)

        # -----------------------------
        # Water Bar Chart
        # -----------------------------
        st.subheader("💧 Water Intake")

        water_chart = filtered[filtered["type"] == "water"].groupby(
            "date"
        )["water"].sum()

        st.bar_chart(water_chart)

    else:
        st.info("No data logged yet.")