import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium


DATA_FILE = Path("gw_sota_data.json")


# ----------------------
# Data loading
# ----------------------

@st.cache_data
def load_data():
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
    layout="wide"
)

st.title("🏔️ GW SOTA Activator Award")

data = load_data()
df = build_activation_dataframe(data)

current_year = datetime.utcnow().year
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

# ----------------------
# GW summits per activator
# ----------------------

st.subheader(f"GW summits activated in {selected_year}")

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

summary_display = (
    summary
    .drop(columns=["userId"])
    .rename(columns={"summits": "Summits Activated"})
)

st.dataframe(
    summary_display,
    use_container_width=True,
    hide_index=True
)


# ----------------------
# Map by callsign
# ----------------------

st.subheader("Map of activations by callsign")

callsigns = sorted(summary["Callsign"].dropna().unique())
selected_callsign = st.text_input(
    "Enter callsign (exact match, e.g. MW0PDV)",
    ""
)

if selected_callsign:
    df_call = df_year[
        (df_year["Callsign"] == selected_callsign)
    ].drop_duplicates(subset=["summitCode"])

    if df_call.empty:
        st.info("No activations found for that callsign in this year.")
    else:
        m = folium.Map(
            location=[52.3, -3.7],
            zoom_start=7,
            tiles="OpenStreetMap"
        )

        for _, row in df_call.iterrows():
            folium.Marker(
                location=[row["latitude"], row["longitude"]],
                popup=f"{row['summitCode']} – {row['summitName']}",
            ).add_to(m)

        st_folium(m, use_container_width=True)

# ----------------------
# Historical winners
# ----------------------

st.subheader("Historical top activator per year")

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

winners_display = (
    winners[["year", "Callsign", "summits"]]
    .rename(columns={
        "year": "Year",
        "summits": "Summits Activated"
    })
)

st.dataframe(
    winners_display,
    use_container_width=True,
    hide_index=True
)


# ----------------------
# Footer
# ----------------------

st.caption(
    f"Data generated nightly • Last update: {data['generated_at']}"
)
