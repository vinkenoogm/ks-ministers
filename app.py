"""Kingshot K398 prep appointment request form (MVP)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import traceback
import uuid

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

st.set_page_config(page_title="K398 prep appointments", page_icon="👑", layout="centered")

DAYS = {
    "monday": ("Monday, November 2", "Chief Minister — construction"),
    "thursday": ("Thursday, November 5", "Noble Advisor — troop training"),
    "friday": ("Friday, November 6", "Chief Minister — research"),
}
# Distinguish the day-before slot from the final slot for reliable storage.
FIRST_SLOT = "23:45 (previous day; first 15-min slot)"
FINAL_SLOT = "23:45 (event day; final 15-min slot)"
TIMES = [FIRST_SLOT] + [f"{h:02d}:15" for h in range(24)] + [FINAL_SLOT]


def expand_times(selections: list[str]) -> list[str]:
    """Expand :15 selection into actual appointments, retaining day-boundary labels."""
    expanded = []
    for slot in selections:
        if slot.startswith("23:45"):
            expanded.append(slot)
        else:
            expanded.extend([slot, FINAL_SLOT if slot == "23:15" else slot[:2] + ":45"])
    return list(dict.fromkeys(expanded))


@st.cache_resource(show_spinner=False)
def get_engine(url: str):
    driver_url = make_url(url).set(drivername="postgresql+psycopg2")
    return create_engine(driver_url, pool_pre_ping=True, pool_recycle=300)


def save_submission(payload: dict) -> str:
    url = st.secrets["DATABASE_URL"]
    engine = get_engine(url)
    submission_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ks_minister_requests (
                id UUID PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                username_alliance TEXT NOT NULL,
                in_game_id TEXT,
                payload JSONB NOT NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO ks_minister_requests (id, username_alliance, in_game_id, payload)
            VALUES (:id, :username_alliance, :in_game_id, CAST(:payload AS jsonb))
        """), {
            "id": submission_id,
            "username_alliance": payload["username_alliance"],
            "in_game_id": payload["in_game_id"],
            "payload": json.dumps(payload),
        })
    return submission_id


st.title("👑 K398 prep appointments — November")
st.caption("November 2, 5 and 6, 2026 · All times UTC")
st.write("Request your minister appointments below. Select only times when you can actually be online. Requests are **not confirmed appointments**.")

if st.session_state.get("submitted"):
    st.success("Your request was saved! 👑")
    st.write("Your submission reference:", st.session_state["submitted"])
    st.info("Appointments will be announced separately. You can close this page.")
    st.stop()

if st.session_state.get("review_payload"):
    payload = st.session_state["review_payload"]
    st.header("Review your request")
    st.caption("All times are UTC.")
    st.subheader("Player information")
    st.write("Username:", st.session_state["review_username"])
    st.write("Alliance:", st.session_state["review_alliance"])
    if payload["in_game_id"]:
        st.write("In-game ID:", payload["in_game_id"])
    for day, details in payload["days"].items():
        st.subheader(f"{details['date']} ? {details['minister']}")
        st.write("Selected availability (UTC):", ", ".join(details["selected_times"]))
        st.write("Expanded availability (UTC):", ", ".join(details["available_slots_utc"]))
        resources = details["resources"]
        st.write("Speedups (days):", resources["speedups_days"])
        if day == "monday":
            st.write("TG:", resources["tg"])
            st.write("TTG:", resources["ttg"])
        if day == "friday":
            st.write("Dust:", resources["dust"])
    if payload["comments"]:
        st.subheader("Additional information")
        st.write(payload["comments"])
    if st.button("? Edit request"):
        for key, value in st.session_state.pop("form_snapshot").items():
            st.session_state[key] = value
        del st.session_state["review_payload"]
        st.rerun()
    if st.button("Confirm & submit", type="primary", disabled=st.session_state.get("submitting", False)):
        st.session_state["submitting"] = True
        try:
            reference = save_submission(payload)
        except Exception as exc:
            logger.error("Submission could not be confirmed (%s).\n%s",
                         type(exc).__name__, "".join(traceback.format_tb(exc.__traceback__)))
            st.error("We couldn't confirm your submission. Please try again or use the Google Form backup.")
            try:
                backup_url = st.secrets.get("GOOGLE_FORM_BACKUP_URL")
            except Exception:
                backup_url = None
            if backup_url:
                st.link_button("Google Form backup", backup_url)
            st.session_state["submitting"] = False
        else:
            st.session_state["submitted"] = reference
            st.rerun()
    st.stop()

username = st.text_input("What's your username? *", max_chars=150, key="username")
alliance = st.text_input("What's your alliance? *", max_chars=150, key="alliance")
player_id = st.text_input("What's your in-game ID? (optional)", max_chars=80, key="player_id")
st.divider()

want = {}
for day, (date, minister) in DAYS.items():
    want[day] = st.checkbox(f"{date}: {minister}", key=f"want_{day}")

requests = {}
for day, (date, minister) in DAYS.items():
    if not want[day]:
        continue
    st.subheader(f"{date} — {minister}")
    st.caption("Select all available UTC times. Every :15 selection also includes :45 of that hour. The two 23:45 slots are only 15 minutes each.")
    sources = [earlier for earlier in DAYS if earlier != day and list(DAYS).index(earlier) < list(DAYS).index(day) and want[earlier]]
    if sources:
        source = st.selectbox("Copy availability from", sources, format_func=str.title, key=f"copy_{day}")
        if st.button("Copy availability", key=f"apply_copy_{day}"):
            for index, slot in enumerate(TIMES):
                st.session_state[f"time_{day}_{index}"] = slot in requests[source]["selected"]
    st.caption("Available start times (UTC) *")
    selected = []
    for row in range(0, len(TIMES), 2):
        columns = st.columns(2)
        for offset, column in enumerate(columns):
            index = row + offset
            if index < len(TIMES):
                slot = TIMES[index]
                if column.checkbox(slot, key=f"time_{day}_{index}"):
                    selected.append(slot)
    resources = {}
    if day == "monday":
        resources["tg"] = st.number_input("How much TG will you use? (approximately)", min_value=0, step=1, key="tg")
        resources["ttg"] = st.number_input("How much TTG will you use? (approximately)", min_value=0, step=1, key="ttg")
    resources["speedups_days"] = st.number_input("How many days of speedups will you use? (approximately)", min_value=0.0, step=0.5, key=f"speedups_{day}")
    if day == "friday":
        resources["dust"] = st.number_input("How much dust will you spend? (approximately)", min_value=0, step=1, key="dust")
    requests[day] = {"copy_from": None, "selected": selected, "resources": resources}

comments = st.text_area("Any comments, complaints, rants, secrets? Spill 'em here 😈", max_chars=3000, key="comments")

if st.button("Review request", type="primary"):
    errors = []
    if not username.strip():
        errors.append("Please enter your username.")
    if not alliance.strip():
        errors.append("Please enter your alliance.")
    if not requests:
        errors.append("Please request at least one appointment.")
    resolved = {}
    for day, request in requests.items():
        slots = expand_times(request["selected"] or [])
        if not slots:
            errors.append(f"Select available times for {day.title()} (or copy from a day with selected times).")
        resolved[day] = slots
    if errors:
        for error in errors:
            st.error(error)
    else:
        payload = {
            "schema_version": 1,
            "event": "K398 prep November 2026",
            "username_alliance": f"{username.strip()} [{alliance.strip()}]",
            "in_game_id": player_id.strip() or None,
            "comments": comments.strip(),
            "days": {day: {
                "date": DAYS[day][0],
                "minister": DAYS[day][1],
                "copy_from": request["copy_from"],
                "selected_times": request["selected"],
                "available_slots_utc": resolved[day],
                "resources": request["resources"],
            } for day, request in requests.items()},
        }
        st.session_state["form_snapshot"] = {
            key: st.session_state[key] for key in st.session_state
            if key not in {"review_payload", "form_snapshot", "review_username", "review_alliance", "submitting", "submitted"}
            and not key.startswith("apply_copy_")
        }
        st.session_state["review_username"] = username.strip()
        st.session_state["review_alliance"] = alliance.strip()
        st.session_state["review_payload"] = payload
        st.rerun()
