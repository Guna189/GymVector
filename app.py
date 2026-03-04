import streamlit as st
import hashlib
import datetime
import pandas as pd
from supabase import create_client, Client
import os

# -----------------------------
# Supabase Setup
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Utility Functions
# -----------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def calculate_age(dob):
    if isinstance(dob, str):
        dob = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
    today = datetime.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

# -----------------------------
# Supabase DB Operations
# -----------------------------
def register_user(username, password, weight, height, dob):
    existing = supabase.table("users").select("*").eq("username", username).execute()
    if existing.data:
        return False
    supabase.table("users").insert({
        "username": username,
        "password": hash_password(password),
        "weight": weight,
        "height": height,
        "dob": dob
    }).execute()
    return True

def login_user(username, password):
    hashed = hash_password(password)
    result = supabase.table("users").select("*").eq("username", username).eq("password", hashed).execute()
    if result.data:
        return result.data[0]
    return None

def update_profile(user_id, weight, height):
    supabase.table("users").update({"weight": weight, "height": height}).eq("id", user_id).execute()

def insert_log(user_id, log_type, description, calories=0, water=0, log_date=None):
    if log_date is None:
        log_date = datetime.datetime.now()
    else:
        log_date = datetime.datetime.combine(log_date, datetime.datetime.now().time())
    supabase.table("logs").insert({
        "user_id": user_id,
        "type": log_type,
        "description": description,
        "calories": calories,
        "water": water,
        "created_at": log_date.isoformat()
    }).execute()

def get_logs(user_id):
    result = supabase.table("logs").select("*").eq("user_id", user_id).execute()
    return result.data if result.data else []

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
# Streamlit Session
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
    user_id = user["id"]
    username = user["username"]
    weight = user["weight"]
    height = user["height"]
    dob = user["dob"]

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
        entry_type = st.selectbox("Entry Type", ["Food", "Workout", "Water"])
        description = st.text_input("Description (Food / Workout name)")
        water_amount = st.number_input("Water Intake (ml) — only for Water type", min_value=0, value=0)
        submit = st.form_submit_button("Add Entry")

        if submit:
            if entry_type in ["Food", "Workout"] and description.strip() == "":
                st.error("Please enter description.")
            elif entry_type == "Water" and water_amount <= 0:
                st.error("Please enter water amount.")
            else:
                if entry_type == "Food":
                    calories = estimate_food_calories(description)
                    insert_log(user_id, "food", description, calories=calories, log_date=entry_date)
                    st.success(f"Food logged: {calories} calories")
                elif entry_type == "Workout":
                    burned = estimate_workout_calories(description, weight)
                    insert_log(user_id, "workout", description, calories=burned, log_date=entry_date)
                    st.success(f"Workout logged: {burned} calories burned")
                elif entry_type == "Water":
                    insert_log(user_id, "water", "Water Intake", water=water_amount, log_date=entry_date)
                    st.success(f"Water logged: {water_amount} ml")
                st.rerun()

    # -----------------------------
    # Analysis Section
    # -----------------------------
    st.header("📊 Analysis Dashboard")

    logs = get_logs(user_id)
    df = pd.DataFrame(logs)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["date"] = df["created_at"].dt.date

        range_option = st.radio("Select Range", ["Last 7 Days", "Last 30 Days", "Last 1 Year"], horizontal=True)
        today = datetime.date.today()
        if range_option == "Last 7 Days":
            start_date = today - pd.Timedelta(days=7)
        elif range_option == "Last 30 Days":
            start_date = today - pd.Timedelta(days=30)
        else:
            start_date = today - pd.Timedelta(days=365)
        filtered = df[df["date"] >= start_date]

        # KPI Section
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

        # Calories Trend
        st.subheader("🔥 Calories Trend")
        calories_chart = filtered[filtered["type"].isin(["food", "workout"])]
        calories_grouped = calories_chart.groupby(["date", "type"])["calories"].sum().unstack().fillna(0)
        st.line_chart(calories_grouped)

        # Water Intake Chart
        st.subheader("💧 Water Intake")
        water_chart = filtered[filtered["type"] == "water"].groupby("date")["water"].sum()
        st.bar_chart(water_chart)
    else:
        st.info("No data logged yet.")

