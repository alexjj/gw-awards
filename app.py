import json
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium


DATA_FILE = Path("gw_sota_data.json")
last_modified = DATA_FILE.stat().st_mtime

# ----------------------
# Data loading
# ----------------------

@st.cache_data
def load_data(last_modified=last_modified):
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_activation_dataframe(data):
    """
    Flatten JSON into a DataFrame with one row per activation per summit
    """
    rows = []

    for region in data["regions"].values():
        for summit_entry in region["summits"].values():
            summit = summit_entry["summit"]

            for act in summit_entry["activations"]:
                rows.append({
                    "userId": act["userId"],
                    "Callsign": act.get("Callsign"),
                    "activationDate": act["activationDate"],
                    "year": int(act["activationDate"][:4]),
                    "summitCode": summit["summitCode"],
                    "summitName": summit["name"],
                    "points": summit["points"],
                    "latitude": summit["latitude"],
                    "longitude": summit["longitude"],
                })

    return pd.DataFrame(rows)

# ----------------------
# App
# ----------------------

st.set_page_config(
    page_title="GW SOTA Activator Award",
    page_icon="🏔️"
)

st.title("🏔️ GW SOTA Activator Award")

data = load_data(last_modified)
df = build_activation_dataframe(data)
total_gw_summits = sum(region["region"]["summits"] for region in data["regions"].values())

current_year = datetime.now(UTC).year
available_years = sorted(df["year"].unique(), reverse=True)

# ----------------------
# Year selector
# ----------------------

selected_year = st.selectbox(
    "Select year",
    available_years,
    index=available_years.index(current_year) if current_year in available_years else 0
)

df_year = df[df["year"] == selected_year]

summary = (
    df_year
    .drop_duplicates(subset=["userId", "summitCode"])
    .groupby(["userId", "Callsign"])
    .agg(
        summits=("summitCode", "count")
    )
    .reset_index()
    .sort_values("summits", ascending=False)
)

# ----------------------
# GW summits per activator
# ----------------------

st.subheader(f"GW summits activated in {selected_year}")

col_left, col_right = st.columns([0.7,0.3])

with col_left:
    summary_display = (
        summary
        .drop(columns=["userId"])
        .rename(columns={"summits": "Summits Activated"})
    )

    summary_display["% of GW Summits"] = (
        summary_display["Summits Activated"] / total_gw_summits * 100).round(0)

    table_event = st.dataframe(
        summary_display,
        width="stretch",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
    )

with col_right:
    total_summits = summary["summits"].sum()
    total_activators = summary["Callsign"].nunique()

    st.metric(
        label="Total Summits Activated",
        value=int(total_summits),
        border=True
    )

    st.metric(
        label="Total Activators",
        value=int(total_activators),
        border=True
    )

# ----------------------
# Map Selection Logic
# ----------------------


selected_callsign = None

if table_event and table_event.selection.rows:
    selected_row = table_event.selection.rows[0]
    selected_callsign = summary_display.iloc[selected_row]["Callsign"]


# ----------------------
# Map by callsign
# ----------------------

st.subheader("Map of activations")

if selected_callsign:
    st.markdown(f"**Selected callsign:** `{selected_callsign}`")

    df_call = (
        df_year[df_year["Callsign"] == selected_callsign]
        .drop_duplicates(subset=["summitCode"])
    )

    if df_call.empty:
        st.info("No activations found for that callsign in this year.")
    else:
        m = folium.Map(
            location=[52.3, -3.7],
            zoom_start=8,
            tiles="OpenTopoMap"
        )

        for _, row in df_call.iterrows():
            popup = f"""
            <b>{row['summitName']}</b><br>
            <a href="https://sotl.as/summits/{row['summitCode']}" target="_blank">
                {row['summitCode']}
            </a><br>
            Points: {row['points']}
            """

            folium.Marker(
                location=[row["latitude"], row["longitude"]],
                popup=popup,
                tooltip=row["summitName"],
                icon=folium.Icon(
                    color=(
                        "lightgreen" if row["points"] == 1 else
                        "green" if row["points"] == 2 else
                        "darkgreen" if row["points"] == 4 else
                        "orange" if row["points"] == 6 else
                        "darkred" if row["points"] == 8 else
                        "red"
                    )
                )
            ).add_to(m)

        st_folium(m, width="stretch")
else:
    st.info("Click a callsign in the table above to show their activations on the map.")

# ----------------------
# Historical winners
# ----------------------

historical = (
    df
    .drop_duplicates(subset=["userId", "summitCode", "year"])
    .groupby(["year", "userId", "Callsign"])
    .agg(
        summits=("summitCode", "count")
    )
    .reset_index()
)

winners = (
    historical
    .sort_values(["year", "summits"], ascending=[True, False])
    .groupby("year")
    .head(1)
    .sort_values("year", ascending=False)
)

col_left, col_right = st.columns(2)

with col_left:

    st.subheader("Top activator per year")

    winners_display = (
        winners[["year", "Callsign", "summits"]]
        .rename(columns={
            "year": "Year",
            "summits": "Summits"
        })
    )

    winners_display["% of GW Summits"] = (
        winners_display["Summits"] / total_gw_summits * 100).round(0)

    st.dataframe(
        winners_display,
        width="stretch",
        hide_index=True
    )

with col_right:

    st.subheader("Total GW activations per year")

    yearly_totals = (
        df
        .drop_duplicates(subset=["userId", "summitCode", "year"])
        .groupby("year")
        .size()
        .reset_index(name="Total Activations")
        .sort_values("year")
    )

    st.bar_chart(
        yearly_totals.set_index("year"),
        y="Total Activations"
    )

# ----------------------
# Footer
# ----------------------

st.caption(
    f"Data generated nightly • Last update: {data['generated_at']}"
)
