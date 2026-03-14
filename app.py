import streamlit as st
import hashlib
import datetime
import pandas as pd
from supabase import create_client, Client
import os
import requests
import re
from langchain_groq import ChatGroq

# -----------------------------
# Supabase Setup
# -----------------------------
SUPABASE_URL = "https://jkhiifxrcykqkfwyqbcn.supabase.co"
SUPABASE_KEY = "sb_publishable_JNCq_i2OBZl-j_H1p96R4Q_sHdhzXUo"

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
def register_user(username, password, weight, height, dob, gender):
    existing = supabase.table("users").select("*").eq("username", username).execute()
    if existing.data:
        return False
    supabase.table("users").insert({
        "username": username,
        "password": hash_password(password),
        "weight": weight,
        "height": height,
        "dob": dob,
        "gender": gender
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

    # NEW: weight history log
    supabase.table("weight_logs").insert({
        "user_id": user_id,
        "weight": weight
    }).execute()

def insert_log(user_id, log_type, description, calories=0, water=0, log_date=None):
    if log_date is None:
        log_date = datetime.datetime.now()
    else:
        log_date = datetime.datetime.combine(log_date, datetime.datetime.now().time())

    result = supabase.table("logs").insert({
        "user_id": user_id,
        "type": log_type,
        "description": description,
        "calories": calories,
        "water": water,
        "created_at": log_date.isoformat()
    }).execute()

    return result.data[0]["id"] if result.data else None


def get_logs(user_id):
    result = supabase.table("logs").select("*").eq("user_id", user_id).execute()
    return result.data if result.data else []

# -----------------------------
# LLM Setup
# -----------------------------
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.2,
)

# -----------------------------
# Calorie Estimation via LLM
# -----------------------------
def estimate_food_calories(description, weight, height, age, gender):

    prompt = f"""
Estimate the number of calories for the following food.

User info:
- Weight: {weight} kg
- Height: {height} cm
- Age: {age}
- Gender: {gender}
- Food Style : Hyderabad, Telangana, India 

Food:
{description}

IMPORTANT:
Return ONLY the numeric calorie value.
"""

    try:
        response = llm.invoke(prompt)
        match = re.search(r"\d+", response.content)
        return int(match.group()) if match else 500
    except:
        return 500


def estimate_workout_calories(description, weight, height, age, gender):

    prompt = f"""
Estimate calories burned.

User info:
- Weight: {weight}
- Height: {height}
- Age: {age}
- Gender: {gender}

Workout:
{description}

Return ONLY number.
"""

    try:
        response = llm.invoke(prompt)
        match = re.search(r"\d+", response.content)
        return int(match.group()) if match else 200
    except:
        return 200


# -----------------------------
# NEW: Nutrition Estimation
# -----------------------------
def estimate_food_nutrition(description):

    prompt = f"""
Estimate nutrition values for this food.

Food:
{description}

Return ONLY numbers like:

protein: 10
carbs: 20
fats: 5
fiber: 3
sugar: 4
sodium: 200
calcium: 50
"""

    try:
        response = llm.invoke(prompt)
        text = response.content.lower()

        def get_val(name):
            m = re.search(fr"{name}\s*:\s*(\d+)", text)
            return int(m.group(1)) if m else 0

        return {
            "protein": get_val("protein"),
            "carbs": get_val("carbs"),
            "fats": get_val("fats"),
            "fiber": get_val("fiber"),
            "sugar": get_val("sugar"),
            "sodium": get_val("sodium"),
            "calcium": get_val("calcium")
        }

    except:
        return {
            "protein":0,"carbs":0,"fats":0,
            "fiber":0,"sugar":0,"sodium":0,"calcium":0
        }

# -----------------------------
# Streamlit Session
# -----------------------------
st.set_page_config(page_title="GymVector")

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
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        dob = st.date_input("Date of Birth")

        if st.button("Register"):
            success = register_user(
                username, password, weight, height, dob.strftime("%Y-%m-%d"), gender
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
    gender = user.get("gender", "Other")

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
# Add Entry
# -----------------------------
    st.subheader("➕ Add Entry")

    with st.form("entry_form"):

        entry_date = st.date_input("Select Date", value=datetime.date.today())
        entry_type = st.selectbox("Entry Type", ["Food", "Workout", "Water"])
        description = st.text_input("Description (Food / Workout)")
        manual_calories = st.number_input("Calories (optional)", min_value=0, value=0)
        water_amount = st.number_input("Water Intake (ml)", min_value=0, value=0)

        submit = st.form_submit_button("Add Entry")

        if submit:

            if entry_type == "Food":

                calories = manual_calories if manual_calories>0 else estimate_food_calories(description, weight, height, age, gender)

                log_id = insert_log(user_id, "food", description, calories=calories, log_date=entry_date)

                # NEW: nutrition logging
                nutrition = estimate_food_nutrition(description)

                supabase.table("nutrition_logs").insert({
                    "log_id": log_id,
                    **nutrition
                }).execute()

                st.success(f"Food logged: {calories} calories")

            elif entry_type == "Workout":

                burned = manual_calories if manual_calories>0 else estimate_workout_calories(description, weight, height, age, gender)

                insert_log(user_id, "workout", description, calories=burned, log_date=entry_date)

                st.success(f"Workout logged: {burned} calories burned")

            elif entry_type == "Water":

                insert_log(user_id, "water", "Water Intake", water=water_amount, log_date=entry_date)

                st.success(f"Water logged: {water_amount} ml")

            st.rerun()

# -----------------------------
# Load Logs
# -----------------------------
    logs = get_logs(user_id)
    df = pd.DataFrame(logs)

    if df.empty:
        st.info("No data logged yet.")
        st.stop()

    df["created_at"] = pd.to_datetime(df["created_at"])
    df["date"] = df["created_at"].dt.date

# -----------------------------
# Today's Summary
# -----------------------------
    st.header("📅 Today's Summary")

    today = datetime.date.today()
    today_df = df[df["date"] == today]

    today_food = today_df[today_df["type"] == "food"]["calories"].sum()
    today_workout = today_df[today_df["type"] == "workout"]["calories"].sum()
    today_water = today_df[today_df["type"] == "water"]["water"].sum()

    col1, col2, col3 = st.columns(3)

    col1.metric("Calories Consumed Today", today_food)
    col2.metric("Calories Burned Today", today_workout)
    col3.metric("Water Intake Today (ml)", today_water)

# -----------------------------
# NEW: Nutrition Summary
# -----------------------------
    nutrition_rows = supabase.table("nutrition_logs").select("*").execute().data
    nut_df = pd.DataFrame(nutrition_rows)

    if not nut_df.empty:

        totals = nut_df.sum()

        st.subheader("🥗 Nutrition Summary")

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Protein", totals["protein"])
        c2.metric("Carbs", totals["carbs"])
        c3.metric("Fats", totals["fats"])
        c4.metric("Fiber", totals["fiber"])

        c5,c6,c7 = st.columns(3)
        c5.metric("Sugar", totals["sugar"])
        c6.metric("Sodium", totals["sodium"])
        c7.metric("Calcium", totals["calcium"])

# -----------------------------
# Analysis Dashboard
# -----------------------------
    st.header("📊 Analysis Dashboard")

    calories_grouped = df.groupby(["date","type"])["calories"].sum().unstack().fillna(0)

    st.subheader("🔥 Calories Trend")
    st.line_chart(calories_grouped)

    water_chart = df[df["type"]=="water"].groupby("date")["water"].sum()

    st.subheader("💧 Water Trend")
    st.bar_chart(water_chart)

# -----------------------------
# NEW: Weight Progress
# -----------------------------
    weight_logs = supabase.table("weight_logs").select("*").eq("user_id", user_id).execute().data
    wdf = pd.DataFrame(weight_logs)

    if not wdf.empty:

        wdf["created_at"] = pd.to_datetime(wdf["created_at"])

        st.subheader("⚖️ Weight Progress")

        st.line_chart(wdf.set_index("created_at")["weight"])

# -----------------------------
# View Specific Day
# -----------------------------
    st.header("📅 View Specific Day")

    selected_date = st.date_input("Select a date", value=datetime.date.today())

    day_df = df[df["date"] == selected_date]

    day_food = day_df[day_df["type"] == "food"]["calories"].sum()
    day_workout = day_df[day_df["type"] == "workout"]["calories"].sum()
    day_water = day_df[day_df["type"] == "water"]["water"].sum()

    c1,c2,c3 = st.columns(3)

    c1.metric("Calories Consumed", day_food)
    c2.metric("Calories Burned", day_workout)
    c3.metric("Water Intake (ml)", day_water)

    if not day_df.empty:
        st.dataframe(day_df)
    else:
        st.info("No logs for this date.")

    
    # -----------------------------
    # Nutrition For Selected Day
    # -----------------------------
    st.subheader("🥗 Nutrition For Selected Day")

    nutrition_rows = supabase.table("nutrition_logs")\
        .select("*, logs(created_at,user_id)")\
        .execute().data

    nut_df = pd.DataFrame(nutrition_rows)

    if not nut_df.empty:

        # extract log date
        nut_df["created_at"] = nut_df["logs"].apply(lambda x: x["created_at"])
        nut_df["user_id"] = nut_df["logs"].apply(lambda x: x["user_id"])

        nut_df["created_at"] = pd.to_datetime(nut_df["created_at"])
        nut_df["date"] = nut_df["created_at"].dt.date

        # filter selected day + user
        day_nutrition = nut_df[
            (nut_df["date"] == selected_date) &
            (nut_df["user_id"] == user_id)
        ]

        if day_nutrition.empty:

            totals = {
                "protein":0,
                "carbs":0,
                "fats":0,
                "fiber":0,
                "sugar":0,
                "sodium":0,
                "calcium":0
            }

        else:

            totals = day_nutrition[
                ["protein","carbs","fats","fiber","sugar","sodium","calcium"]
            ].sum()

    else:

        totals = {
            "protein":0,
            "carbs":0,
            "fats":0,
            "fiber":0,
            "sugar":0,
            "sodium":0,
            "calcium":0
        }

    # Display Metrics
    col1,col2,col3,col4 = st.columns(4)

    col1.metric("Protein (g)", totals["protein"])
    col2.metric("Carbs (g)", totals["carbs"])
    col3.metric("Fats (g)", totals["fats"])
    col4.metric("Fiber (g)", totals["fiber"])

    col5,col6,col7 = st.columns(3)

    col5.metric("Sugar (g)", totals["sugar"])
    col6.metric("Sodium (mg)", totals["sodium"])
    col7.metric("Calcium (mg)", totals["calcium"])

    # Chart
    st.bar_chart(pd.Series(totals))