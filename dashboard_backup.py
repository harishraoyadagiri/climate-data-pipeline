"""
Climate Data Analytics Dashboard — powered by Streamlit.

4-page interactive dashboard:
1. Overview — KPIs and city comparison
2. Trends — Temperature and precipitation time-series
3. Heatmap — Monthly temperature heatmap across cities
4. Data Quality — Validation report and data health

Usage:
    streamlit run dashboard.py
"""

import json
import os
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import PROCESSED_DIR, WAREHOUSE_DB

# ──────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Climate Data Pipeline Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif; }

    /* ── Spider-Verse Watercolor Canvas ── */
    .stApp {
        background:
            radial-gradient(ellipse at 15% 20%, rgba(180, 120, 200, 0.12) 0%, transparent 50%),
            radial-gradient(ellipse at 85% 15%, rgba(100, 200, 220, 0.10) 0%, transparent 45%),
            radial-gradient(ellipse at 50% 80%, rgba(240, 140, 120, 0.08) 0%, transparent 50%),
            radial-gradient(ellipse at 75% 60%, rgba(130, 160, 240, 0.06) 0%, transparent 40%),
            linear-gradient(160deg, #0d0b1a 0%, #140e22 30%, #0f1520 60%, #0d0b1a 100%);
    }

    .main {
        background: transparent;
    }

    /* ── Sidebar: soft violet frost ── */
    section[data-testid="stSidebar"] {
        background:
            linear-gradient(180deg,
                rgba(22, 15, 35, 0.97) 0%,
                rgba(18, 18, 32, 0.98) 40%,
                rgba(15, 20, 28, 0.97) 100%
            );
        border-right: 1px solid rgba(180, 140, 220, 0.08);
    }

    /* ── KPI Cards: frosted glass with pastel glow ── */
    .kpi-card {
        background: rgba(255, 255, 255, 0.035);
        border: 1px solid rgba(200, 170, 240, 0.1);
        border-radius: 16px;
        padding: 22px 16px;
        text-align: center;
        backdrop-filter: blur(24px);
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg,
            rgba(240,140,180,0.4),
            rgba(160,120,240,0.5),
            rgba(100,200,220,0.4)
        );
        opacity: 0;
        transition: opacity 0.35s ease;
    }
    .kpi-card:hover {
        background: rgba(255,255,255,0.055);
        border-color: rgba(200, 170, 240, 0.2);
        transform: translateY(-3px);
        box-shadow:
            0 8px 32px rgba(180, 120, 200, 0.08),
            0 4px 16px rgba(100, 200, 220, 0.05);
    }
    .kpi-card:hover::before { opacity: 1; }

    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #e8b4d0, #c4b0e8, #a0d8e0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
        margin: 6px 0 4px;
    }
    .kpi-label {
        font-size: 0.72rem;
        color: rgba(220, 200, 240, 0.5);
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 600;
    }
    .kpi-sublabel {
        font-size: 0.7rem;
        color: rgba(200, 180, 220, 0.3);
        margin-top: 2px;
    }

    /* ── Section Headers: pastel underline ── */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: rgba(230, 210, 250, 0.85);
        margin: 36px 0 18px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(180, 140, 220, 0.12);
        letter-spacing: 0.3px;
    }

    /* ── Typography: watercolor gradient headings ── */
    h1 {
        background: linear-gradient(135deg, #f0c0d8 0%, #c8a8e8 40%, #a0d4e4 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }
    h2, h3 {
        color: rgba(230, 210, 250, 0.85) !important;
        font-weight: 600 !important;
    }

    /* ── Page subtitle ── */
    .page-subtitle {
        color: rgba(200, 180, 220, 0.45);
        font-size: 0.95rem;
        font-weight: 300;
        margin-top: -8px;
        margin-bottom: 28px;
    }

    /* ── Sidebar labels ── */
    .stSelectbox label, .stMultiSelect label, .stSlider label {
        color: rgba(200, 180, 230, 0.5) !important;
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
    }

    /* ── Quality Badge: pastel accent ── */
    .quality-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .quality-pass {
        background: rgba(120, 220, 180, 0.12);
        color: #78dcb4;
        border: 1px solid rgba(120, 220, 180, 0.2);
    }
    .quality-fail {
        background: rgba(240, 140, 140, 0.12);
        color: #f08c8c;
        border: 1px solid rgba(240, 140, 140, 0.2);
    }

    /* ── Streamlit overrides ── */
    .stRadio > div { gap: 2px !important; }
    .stRadio > div > label {
        padding: 6px 0 !important;
        color: rgba(200, 180, 230, 0.5) !important;
    }
    .stRadio > div > label[data-checked="true"] {
        color: #e0d0f0 !important;
    }
    .stExpander {
        border: 1px solid rgba(180, 140, 220, 0.06) !important;
        border-radius: 12px !important;
        background: rgba(255,255,255,0.02) !important;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(180, 140, 220, 0.08);
        border-radius: 12px;
    }

    /* ── Top toolbar (Deploy bar) ── */
    header[data-testid="stHeader"] {
        background: linear-gradient(90deg,
            rgba(13,11,26,0.95) 0%,
            rgba(20,14,34,0.92) 40%,
            rgba(15,21,32,0.95) 100%
        ) !important;
        backdrop-filter: blur(16px);
        border-bottom: 1px solid rgba(180, 140, 220, 0.08);
    }
    /* Deploy button area */
    header[data-testid="stHeader"] button {
        color: rgba(200, 180, 230, 0.6) !important;
    }

    /* ── Dropdowns / Selectboxes ── */
    div[data-baseweb="select"] > div {
        background: rgba(22, 18, 36, 0.9) !important;
        border-color: rgba(180, 140, 220, 0.15) !important;
        color: #e0d0f0 !important;
    }
    div[data-baseweb="select"] > div:hover {
        border-color: rgba(200, 170, 240, 0.3) !important;
    }
    div[data-baseweb="select"] > div:focus-within {
        border-color: rgba(200, 170, 240, 0.4) !important;
        box-shadow: 0 0 0 1px rgba(200, 170, 240, 0.15) !important;
    }
    /* Dropdown menu popup */
    ul[data-testid="stSelectboxVirtualDropdown"],
    div[data-baseweb="popover"] > div {
        background: rgba(18, 14, 30, 0.98) !important;
        border: 1px solid rgba(180, 140, 220, 0.12) !important;
        backdrop-filter: blur(20px);
    }
    li[role="option"] {
        color: rgba(220, 200, 240, 0.8) !important;
    }
    li[role="option"]:hover {
        background: rgba(180, 140, 220, 0.1) !important;
    }
    li[role="option"][aria-selected="true"] {
        background: rgba(180, 140, 220, 0.15) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_data():
    """Load data from SQLite warehouse."""
    if not os.path.exists(WAREHOUSE_DB):
        return None, None, None

    conn = sqlite3.connect(WAREHOUSE_DB)
    try:
        fact = pd.read_sql_query("SELECT * FROM fact_weather", conn)
        dim_city = pd.read_sql_query("SELECT * FROM dim_city", conn)
        dim_date = pd.read_sql_query("SELECT * FROM dim_date", conn)
        return fact, dim_city, dim_date
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_quality_report():
    """Load the latest quality report."""
    report_path = os.path.join(PROCESSED_DIR, "quality_report.json")
    if not os.path.exists(report_path):
        return None
    with open(report_path, "r") as f:
        return json.load(f)


def build_merged_data(fact, dim_city, dim_date):
    """Join fact with dimensions for analytics."""
    df = fact.merge(dim_city, on="city_id", how="left")
    df = df.merge(dim_date, on="date_id", how="left")
    df["date"] = pd.to_datetime(df["date"])
    # Ensure numeric types (SQLite can sometimes return mixed types)
    numeric_cols = [
        "temp_avg", "temp_min", "temp_max", "humidity_avg",
        "precip_total", "wind_speed_avg", "wind_speed_max",
        "pressure_avg", "cloud_cover_avg", "heat_index",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ──────────────────────────────────────────────
# Plotly Theme
# ──────────────────────────────────────────────

CITY_COORDS = {
    "New York": (40.7128, -74.0060),
    "Los Angeles": (34.0522, -118.2437),
    "Chicago": (41.8781, -87.6298),
    "Houston": (29.7604, -95.3698),
    "Phoenix": (33.4484, -112.0740),
    "Philadelphia": (39.9526, -75.1652),
    "San Antonio": (29.4241, -98.4936),
    "San Diego": (32.7157, -117.1611),
    "Dallas": (32.7767, -96.7970),
    "Austin": (30.2672, -97.7431),
    "Denver": (39.7392, -104.9903),
}

PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#c0c0e0"),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(
        bgcolor="rgba(0,0,0,0.2)",
        bordercolor="rgba(139,92,246,0.2)",
        borderwidth=1,
    ),
)

COLOR_PALETTE = px.colors.qualitative.Pastel


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────

# Sidebar — brand
st.sidebar.markdown(
    '<div style="padding:12px 0 4px;font-size:1.4rem;font-weight:700;'
    'background:linear-gradient(135deg,#f0c0d8,#c8a8e8,#a0d4e4);'
    '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
    'letter-spacing:-0.3px;">'
    '🌍 Climate Pipeline</div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    '<div style="font-size:0.72rem;color:rgba(200,180,230,0.35);'
    'text-transform:uppercase;letter-spacing:2px;margin-bottom:20px;">'
    'Data Analytics Dashboard</div>',
    unsafe_allow_html=True,
)

# Main navigation — 3 core pages
page = st.sidebar.radio(
    "Navigate",
    ["📊 Overview", "📈 Trends", "🗺️ Heatmaps", "🌎 Map"],
    label_visibility="collapsed",
)

# Load data
fact, dim_city, dim_date = load_data()

if fact is None:
    st.error(
        "⚠️ No data found. Run the pipeline first:\n\n"
        "```bash\npython pipeline.py --start 2024-01-01 --end 2024-12-31\n```"
    )
    st.stop()

merged = build_merged_data(fact, dim_city, dim_date)

# Sidebar filters
st.sidebar.markdown(
    '<div style="margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.05);'
    'font-size:0.72rem;color:rgba(255,255,255,0.35);text-transform:uppercase;'
    'letter-spacing:2px;margin-bottom:8px;">Filters</div>',
    unsafe_allow_html=True,
)
available_cities = sorted(dim_city["city_name"].unique())
selected_cities = st.sidebar.multiselect(
    "Cities",
    available_cities,
    default=available_cities,
)

years = sorted(merged["year"].unique())
if len(years) > 1:
    year_range = st.sidebar.slider(
        "Year Range",
        min_value=int(min(years)),
        max_value=int(max(years)),
        value=(int(min(years)), int(max(years))),
    )
else:
    year_range = (int(years[0]), int(years[0]))

# Apply filters
filtered = merged[
    (merged["city_name"].isin(selected_cities))
    & (merged["year"] >= year_range[0])
    & (merged["year"] <= year_range[1])
]

# Sidebar stats
st.sidebar.markdown(
    f'<div style="padding:12px 0;border-top:1px solid rgba(255,255,255,0.05);'
    f'margin-top:12px;font-size:0.78rem;color:rgba(255,255,255,0.4);line-height:1.8;">'
    f'<span style="color:#e0e7ff;font-weight:600;">{len(filtered):,}</span> records &nbsp;·&nbsp; '
    f'<span style="color:#e0e7ff;font-weight:600;">{filtered["city_name"].nunique()}</span> cities &nbsp;·&nbsp; '
    f'<span style="color:#e0e7ff;font-weight:600;">{year_range[0]}–{year_range[1]}</span></div>',
    unsafe_allow_html=True,
)

# Quality badge in sidebar (compact)
report = load_quality_report()
if report is not None:
    badge_class = "quality-pass" if report["overall_status"] == "PASS" else "quality-fail"
    badge_icon = "✓" if report["overall_status"] == "PASS" else "✗"
    st.sidebar.markdown(
        f'<div style="padding-top:8px;">'
        f'<span class="quality-badge {badge_class}">'
        f'{badge_icon} Quality: {report["pass_rate"]}% ({report["passed"]}/{report["total_checks"]})'
        f'</span></div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════
# PAGE 1: Overview
# ══════════════════════════════════════════════

if page == "📊 Overview":
    st.markdown("# 📊 Climate Overview")
    st.markdown('<div class="page-subtitle">Key metrics and city-level comparisons across the selected period.</div>', unsafe_allow_html=True)

    # KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        avg_temp = filtered["temp_avg"].mean()
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-label">Avg Temperature</div>
                <div class="kpi-value">{avg_temp:.1f}°C</div>
                <div class="kpi-sublabel">{avg_temp * 9/5 + 32:.1f}°F</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col2:
        total_precip = filtered["precip_total"].sum()
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-label">Total Precipitation</div>
                <div class="kpi-value">{total_precip:,.0f}</div>
                <div class="kpi-sublabel">mm across all cities</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col3:
        extreme_heat_days = int(filtered["is_extreme_heat"].sum())
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-label">Extreme Heat Days</div>
                <div class="kpi-value">{extreme_heat_days:,}</div>
                <div class="kpi-sublabel">&gt; 35°C / 95°F</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col4:
        freezing_days = int(filtered["is_freezing"].sum())
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-label">Freezing Days</div>
                <div class="kpi-value">{freezing_days:,}</div>
                <div class="kpi-sublabel">&lt; 0°C / 32°F</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col5:
        avg_wind = filtered["wind_speed_avg"].mean()
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-label">Avg Wind Speed</div>
                <div class="kpi-value">{avg_wind:.1f}</div>
                <div class="kpi-sublabel">km/h</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("")

    # City comparison charts
    st.markdown('<div class="section-header">🏙️ City Comparison</div>', unsafe_allow_html=True)

    city_stats = (
        filtered.groupby("city_name")
        .agg(
            avg_temp=("temp_avg", "mean"),
            total_precip=("precip_total", "sum"),
            extreme_heat=("is_extreme_heat", "sum"),
            freezing=("is_freezing", "sum"),
        )
        .reset_index()
        .sort_values("avg_temp", ascending=True)
    )

    col_left, col_right = st.columns(2)

    with col_left:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=city_stats["avg_temp"],
            y=city_stats["city_name"],
            orientation="h",
            marker=dict(
                color=city_stats["avg_temp"],
                colorscale="RdYlBu_r",
                line_width=0,
            ),
            text=[f"{v:.1f}°C" for v in city_stats["avg_temp"]],
            textposition="auto",
            textfont=dict(color="white", size=12),
        ))
        fig.update_layout(
            **PLOT_LAYOUT,
            height=450,
            title=f"Average Temperature by City ({year_range[0]}–{year_range[1]})",
            xaxis_title="Temperature (°C)",
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # Use city_stats order (sorted by avg_temp) so axes match exactly
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=city_stats["total_precip"],
            y=city_stats["city_name"],
            orientation="h",
            marker=dict(
                color=city_stats["total_precip"],
                colorscale="Blues",
                line_width=0,
            ),
            text=[f"{v:,.0f} mm" for v in city_stats["total_precip"]],
            textposition="auto",
            textfont=dict(color="white", size=12),
        ))
        fig.update_layout(
            **PLOT_LAYOUT,
            height=450,
            title=f"Total Precipitation by City ({year_range[0]}–{year_range[1]})",
            xaxis_title="Precipitation (mm)",
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Temperature distribution per city
    st.markdown('<div class="section-header">🌤️ Temperature Distribution by City</div>', unsafe_allow_html=True)

    dist_col1, dist_col2 = st.columns([3, 2])

    with dist_col1:
        # Violin + strip chart per city
        city_order = (
            filtered.groupby("city_name")["temp_avg"]
            .median()
            .sort_values()
            .index.tolist()
        )

        violin_colors = [
            "#f43f5e", "#8b5cf6", "#06b6d4", "#f97316", "#22c55e",
            "#ec4899", "#3b82f6", "#eab308", "#14b8a6", "#a855f7", "#ef4444",
        ]

        fig = go.Figure()
        for i, city in enumerate(city_order):
            city_data = filtered[filtered["city_name"] == city]["temp_avg"]
            fig.add_trace(go.Violin(
                y=city_data,
                name=city,
                box_visible=True,
                meanline_visible=True,
                fillcolor=violin_colors[i % len(violin_colors)],
                line_color="rgba(255,255,255,0.4)",
                opacity=0.75,
                points="all",
                pointpos=0,
                jitter=0.3,
                marker=dict(size=3, color=violin_colors[i % len(violin_colors)], opacity=0.5),
                hovertemplate="<b>" + city + "</b><br>Temp: %{y:.1f}°C<extra></extra>",
            ))
        fig.update_layout(
            **PLOT_LAYOUT,
            height=450,
            title=f"Daily Temperature Spread by City ({year_range[0]}–{year_range[1]})",
            yaxis_title="Temperature (°C)",
            xaxis_title="",
            showlegend=False,
            xaxis_tickangle=-30,
        )
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
        st.plotly_chart(fig, use_container_width=True)

    with dist_col2:
        # Humidity vs Temperature scatter
        fig = px.scatter(
            filtered,
            x="temp_avg",
            y="humidity_avg",
            color="city_name",
            size="wind_speed_avg",
            size_max=12,
            opacity=0.7,
            color_discrete_sequence=[
                "#f43f5e", "#8b5cf6", "#06b6d4", "#f97316", "#22c55e",
                "#ec4899", "#3b82f6", "#eab308", "#14b8a6", "#a855f7", "#ef4444",
            ],
            title="Humidity vs Temperature",
            labels={
                "temp_avg": "Avg Temp (°C)",
                "humidity_avg": "Avg Humidity (%)",
                "wind_speed_avg": "Wind Speed",
                "city_name": "City",
            },
        )
        fig.update_layout(**PLOT_LAYOUT, height=450)
        fig.update_layout(
            legend=dict(
                bgcolor="rgba(0,0,0,0.3)",
                bordercolor="rgba(139,92,246,0.2)",
                borderwidth=1,
                font=dict(size=10),
            ),
        )
        fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════
# PAGE 2: Trends
# ══════════════════════════════════════════════

elif page == "📈 Trends":
    st.markdown("# 📈 Climate Trends")
    st.markdown('<div class="page-subtitle">Interactive time-series of temperature and precipitation patterns.</div>', unsafe_allow_html=True)

    # Use daily data directly — works for any date range
    daily = filtered.sort_values(["city_name", "date"])

    # Temperature trends — daily with optional smoothing
    st.markdown('<div class="section-header">🌡️ Daily Temperature Trends</div>', unsafe_allow_html=True)

    smoothing = st.radio(
        "Smoothing",
        ["Raw Daily", "7-Day Average", "14-Day Average"],
        horizontal=True,
    )

    trend_data = daily.copy()
    if smoothing == "7-Day Average":
        trend_data["temp_plot"] = trend_data.groupby("city_name")["temp_avg"].transform(
            lambda x: x.rolling(7, min_periods=1, center=True).mean()
        )
    elif smoothing == "14-Day Average":
        trend_data["temp_plot"] = trend_data.groupby("city_name")["temp_avg"].transform(
            lambda x: x.rolling(14, min_periods=1, center=True).mean()
        )
    else:
        trend_data["temp_plot"] = trend_data["temp_avg"]

    # Vibrant color palette for cities
    city_colors = [
        "#f43f5e", "#8b5cf6", "#06b6d4", "#f97316", "#22c55e",
        "#ec4899", "#3b82f6", "#eab308", "#14b8a6", "#a855f7", "#ef4444",
    ]

    fig = go.Figure()
    for i, city in enumerate(sorted(trend_data["city_name"].unique())):
        city_data = trend_data[trend_data["city_name"] == city]
        fig.add_trace(go.Scatter(
            x=city_data["date"],
            y=city_data["temp_plot"],
            mode="lines+markers" if smoothing == "Raw Daily" else "lines",
            name=city,
            line=dict(color=city_colors[i % len(city_colors)], width=2.5),
            marker=dict(size=4) if smoothing == "Raw Daily" else None,
            hovertemplate=f"<b>{city}</b><br>"
                          "Date: %{x|%b %d, %Y}<br>"
                          "Temp: %{y:.1f}°C<extra></extra>",
        ))
    fig.update_layout(
        **PLOT_LAYOUT,
        height=500,
        title=f"Temperature by City ({smoothing})",
        xaxis_title="Date",
        yaxis_title="Temperature (°C)",
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig, use_container_width=True)

    # Precipitation trends — daily stacked area
    st.markdown('<div class="section-header">🌧️ Daily Precipitation</div>', unsafe_allow_html=True)

    fig = go.Figure()
    for i, city in enumerate(sorted(daily["city_name"].unique())):
        city_data = daily[daily["city_name"] == city]
        fig.add_trace(go.Bar(
            x=city_data["date"],
            y=city_data["precip_total"],
            name=city,
            marker_color=city_colors[i % len(city_colors)],
            opacity=0.8,
            hovertemplate="<b>" + city + "</b><br>"
                          "Date: %{x|%b %d, %Y}<br>"
                          "Precip: %{y:.1f} mm<extra></extra>",
        ))
    fig.update_layout(
        **PLOT_LAYOUT,
        height=400,
        title="Daily Precipitation by City",
        barmode="stack",
        xaxis_title="Date",
        yaxis_title="Precipitation (mm)",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig, use_container_width=True)

    # Temperature range bands for selected city
    st.markdown('<div class="section-header">🌡️ Temperature Range — Daily</div>', unsafe_allow_html=True)

    range_city = st.selectbox("Select city for range view", selected_cities)
    city_daily = daily[daily["city_name"] == range_city].sort_values("date")

    fig = go.Figure()

    # Max temperature (upper bound)
    fig.add_trace(go.Scatter(
        x=city_daily["date"], y=city_daily["temp_max"],
        mode="lines", name="Max Temp",
        line=dict(color="rgba(249,115,22,0.7)", width=1.5),
        hovertemplate="Max: %{y:.1f}°C<extra></extra>",
    ))
    # Min temperature (lower bound with fill)
    fig.add_trace(go.Scatter(
        x=city_daily["date"], y=city_daily["temp_min"],
        mode="lines", name="Min Temp",
        fill="tonexty",
        fillcolor="rgba(139,92,246,0.12)",
        line=dict(color="rgba(96,165,250,0.7)", width=1.5),
        hovertemplate="Min: %{y:.1f}°C<extra></extra>",
    ))
    # Average temperature (center line — bold)
    fig.add_trace(go.Scatter(
        x=city_daily["date"], y=city_daily["temp_avg"],
        mode="lines+markers", name="Avg Temp",
        line=dict(color="#a78bfa", width=3),
        marker=dict(size=4, color="#a78bfa"),
        hovertemplate="Avg: %{y:.1f}°C<extra></extra>",
    ))

    fig.update_layout(
        **PLOT_LAYOUT,
        height=420,
        title=f"Daily Temperature Range — {range_city}",
        xaxis_title="Date",
        yaxis_title="Temperature (°C)",
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════
# PAGE 3: Heatmap
# ══════════════════════════════════════════════

elif page == "🗺️ Heatmaps":
    st.markdown("# 🗺️ Climate Heatmaps")
    st.markdown('<div class="page-subtitle">Visualize weather patterns across cities — powered by daily data.</div>', unsafe_allow_html=True)

    heatmap_year = st.selectbox("Select Year", sorted(filtered["year"].unique(), reverse=True))
    year_data = filtered[filtered["year"] == heatmap_year]

    # Determine if we have enough months—use daily granularity if single month
    unique_months = sorted(year_data["month"].unique())
    month_names_full = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    # -- Custom colorscales --
    temp_colorscale = [
        [0.0, "#1e3a5f"],      # Deep navy (cold)
        [0.15, "#2563eb"],     # Royal blue
        [0.3, "#06b6d4"],      # Cyan
        [0.45, "#10b981"],     # Emerald
        [0.55, "#fbbf24"],     # Gold
        [0.7, "#f97316"],      # Orange
        [0.85, "#ef4444"],     # Red
        [1.0, "#991b1b"],      # Deep crimson (hot)
    ]

    precip_colorscale = [
        [0.0, "#0f172a"],      # Dark slate
        [0.1, "#1e3a5f"],      # Navy
        [0.3, "#2563eb"],      # Blue
        [0.5, "#06b6d4"],      # Cyan
        [0.7, "#22d3ee"],      # Light cyan
        [0.85, "#67e8f9"],     # Ice blue
        [1.0, "#ecfeff"],      # Almost white
    ]

    heatmap_layout = dict(
        **PLOT_LAYOUT,
        xaxis=dict(side="top", tickfont=dict(size=12, color="#c0c0e0")),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12, color="#c0c0e0")),
        xaxis_title="",
        yaxis_title="",
    )

    if len(unique_months) > 1:
        # --- MULTI-MONTH VIEW (monthly aggregation) ---
        x_labels = [month_names_full[m - 1] for m in unique_months]

        # Temperature heatmap
        st.markdown('<div class="section-header">🌡️ Temperature Heatmap</div>', unsafe_allow_html=True)

        pivot_temp = (
            year_data.groupby(["city_name", "month"])["temp_avg"]
            .mean().reset_index()
            .pivot(index="city_name", columns="month", values="temp_avg")
        )

        fig = go.Figure(data=go.Heatmap(
            z=pivot_temp[unique_months].values,
            x=x_labels,
            y=pivot_temp.index,
            colorscale=temp_colorscale,
            text=pivot_temp[unique_months].round(1).values,
            texttemplate="<b>%{text}°</b>",
            textfont=dict(size=13, color="white"),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f}°C<extra></extra>",
            colorbar=dict(
                title=dict(text="°C", font=dict(color="#c0c0e0")),
                tickfont=dict(color="#c0c0e0"),
                bgcolor="rgba(0,0,0,0)",
                outlinewidth=0,
            ),
            xgap=3,
            ygap=3,
        ))
        fig.update_layout(**heatmap_layout, height=max(450, len(pivot_temp) * 48))
        fig.update_layout(title=f"Monthly Average Temperature ({heatmap_year})")
        st.plotly_chart(fig, use_container_width=True)

        # Precipitation heatmap
        st.markdown('<div class="section-header">🌧️ Precipitation Heatmap</div>', unsafe_allow_html=True)

        pivot_precip = (
            year_data.groupby(["city_name", "month"])["precip_total"]
            .sum().reset_index()
            .pivot(index="city_name", columns="month", values="precip_total")
        )

        fig = go.Figure(data=go.Heatmap(
            z=pivot_precip[unique_months].values,
            x=x_labels,
            y=pivot_precip.index,
            colorscale=precip_colorscale,
            text=pivot_precip[unique_months].round(0).values,
            texttemplate="<b>%{text}</b>",
            textfont=dict(size=13, color="white"),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.0f} mm<extra></extra>",
            colorbar=dict(
                title=dict(text="mm", font=dict(color="#c0c0e0")),
                tickfont=dict(color="#c0c0e0"),
                bgcolor="rgba(0,0,0,0)",
                outlinewidth=0,
            ),
            xgap=3,
            ygap=3,
        ))
        fig.update_layout(**heatmap_layout, height=max(450, len(pivot_precip) * 48))
        fig.update_layout(title=f"Monthly Total Precipitation ({heatmap_year})")
        st.plotly_chart(fig, use_container_width=True)

    else:
        # --- SINGLE MONTH VIEW (daily granularity) ---
        month_label = month_names_full[unique_months[0] - 1]

        # Temperature heatmap — daily
        st.markdown('<div class="section-header">🌡️ Daily Temperature Heatmap</div>', unsafe_allow_html=True)

        pivot_temp = (
            year_data.assign(day=year_data["date"].dt.day)
            .pivot_table(index="city_name", columns="day", values="temp_avg", aggfunc="mean")
        )
        day_labels = [f"{month_label} {d}" for d in pivot_temp.columns]

        fig = go.Figure(data=go.Heatmap(
            z=pivot_temp.values,
            x=day_labels,
            y=pivot_temp.index,
            colorscale=temp_colorscale,
            text=pivot_temp.round(1).values,
            texttemplate="<b>%{text}°</b>",
            textfont=dict(size=10, color="white"),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f}°C<extra></extra>",
            colorbar=dict(
                title=dict(text="°C", font=dict(color="#c0c0e0")),
                tickfont=dict(color="#c0c0e0"),
                bgcolor="rgba(0,0,0,0)",
                outlinewidth=0,
            ),
            xgap=2,
            ygap=3,
        ))
        fig.update_layout(**heatmap_layout, height=max(450, len(pivot_temp) * 48))
        fig.update_layout(title=f"Daily Average Temperature — {month_label} {heatmap_year}")
        fig.update_xaxes(tickangle=-45, dtick=2)
        st.plotly_chart(fig, use_container_width=True)

        # Precipitation heatmap — daily
        st.markdown('<div class="section-header">🌧️ Daily Precipitation Heatmap</div>', unsafe_allow_html=True)

        pivot_precip = (
            year_data.assign(day=year_data["date"].dt.day)
            .pivot_table(index="city_name", columns="day", values="precip_total", aggfunc="sum")
        )

        fig = go.Figure(data=go.Heatmap(
            z=pivot_precip.values,
            x=day_labels,
            y=pivot_precip.index,
            colorscale=precip_colorscale,
            text=pivot_precip.round(1).values,
            texttemplate="<b>%{text}</b>",
            textfont=dict(size=10, color="white"),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f} mm<extra></extra>",
            colorbar=dict(
                title=dict(text="mm", font=dict(color="#c0c0e0")),
                tickfont=dict(color="#c0c0e0"),
                bgcolor="rgba(0,0,0,0)",
                outlinewidth=0,
            ),
            xgap=2,
            ygap=3,
        ))
        fig.update_layout(**heatmap_layout, height=max(450, len(pivot_precip) * 48))
        fig.update_layout(title=f"Daily Precipitation — {month_label} {heatmap_year}")
        fig.update_xaxes(tickangle=-45, dtick=2)
        st.plotly_chart(fig, use_container_width=True)

    # --- Wind Speed Heatmap (always shown) ---
    st.markdown('<div class="section-header">💨 Wind Speed Heatmap</div>', unsafe_allow_html=True)

    wind_colorscale = [
        [0.0, "#0f172a"],
        [0.2, "#1e3a5f"],
        [0.4, "#059669"],
        [0.6, "#fbbf24"],
        [0.8, "#f97316"],
        [1.0, "#dc2626"],
    ]

    if len(unique_months) > 1:
        pivot_wind = (
            year_data.groupby(["city_name", "month"])["wind_speed_avg"]
            .mean().reset_index()
            .pivot(index="city_name", columns="month", values="wind_speed_avg")
        )
        x_wind = [month_names_full[m - 1] for m in unique_months if m in pivot_wind.columns]
        cols_wind = [m for m in unique_months if m in pivot_wind.columns]
        title_wind = f"Monthly Avg Wind Speed ({heatmap_year})"
    else:
        pivot_wind = (
            year_data.assign(day=year_data["date"].dt.day)
            .pivot_table(index="city_name", columns="day", values="wind_speed_avg", aggfunc="mean")
        )
        x_wind = [f"{month_label} {d}" for d in pivot_wind.columns]
        cols_wind = list(pivot_wind.columns)
        title_wind = f"Daily Avg Wind Speed — {month_label} {heatmap_year}"

    fig = go.Figure(data=go.Heatmap(
        z=pivot_wind[cols_wind].values,
        x=x_wind,
        y=pivot_wind.index,
        colorscale=wind_colorscale,
        text=pivot_wind[cols_wind].round(1).values,
        texttemplate="<b>%{text}</b>",
        textfont=dict(size=10 if len(unique_months) == 1 else 13, color="white"),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f} km/h<extra></extra>",
        colorbar=dict(
            title=dict(text="km/h", font=dict(color="#c0c0e0")),
            tickfont=dict(color="#c0c0e0"),
            bgcolor="rgba(0,0,0,0)",
            outlinewidth=0,
        ),
        xgap=2,
        ygap=3,
    ))
    fig.update_layout(**heatmap_layout, height=max(450, len(pivot_wind) * 48))
    fig.update_layout(title=title_wind)
    if len(unique_months) == 1:
        fig.update_xaxes(tickangle=-45, dtick=2)
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════
# PAGE 4: Interactive Map
# ══════════════════════════════════════════════

elif page == "🌎 Map":
    st.markdown("# 🌎 Climate Map")
    st.markdown(
        '<div class="page-subtitle">'
        'Interactive map of monitored cities — click a marker to explore climate highlights.'
        '</div>',
        unsafe_allow_html=True,
    )

    # Build per-city summary stats
    city_stats = (
        filtered.groupby("city_name")
        .agg(
            temp_avg=("temp_avg", "mean"),
            temp_min=("temp_min", "min"),
            temp_max=("temp_max", "max"),
            precip_total=("precip_total", "sum"),
            humidity_avg=("humidity_avg", "mean"),
            wind_avg=("wind_speed_avg", "mean"),
            wind_max=("wind_speed_max", "max"),
            pressure_avg=("pressure_avg", "mean"),
            cloud_avg=("cloud_cover_avg", "mean"),
            freezing_days=("temp_min", lambda x: (x < 0).sum()),
            records=("date_id", "count"),
        )
        .reset_index()
    )

    # Climate personality notes
    def climate_vibe(row):
        t = row["temp_avg"]
        p = row["precip_total"]
        w = row["wind_avg"]
        if t > 15 and p < 30:
            return "☀️ Warm & dry — perfect outdoor weather"
        elif t > 15 and p >= 30:
            return "🌴 Warm & wet — tropical energy"
        elif t > 5 and p < 50:
            return "🍂 Mild & moderate — comfortable seasons"
        elif t > 5 and p >= 50:
            return "🌧️ Mild & rainy — pack an umbrella"
        elif t <= 5 and w > 15:
            return "🌬️ Cold & windy — brace yourself"
        elif t <= 5:
            return "❄️ Cold climate — cozy indoors weather"
        return "🌤️ Pleasant conditions"

    city_stats["vibe"] = city_stats.apply(climate_vibe, axis=1)

    # Add coordinates
    city_stats["lat"] = city_stats["city_name"].map(lambda c: CITY_COORDS.get(c, (0, 0))[0])
    city_stats["lon"] = city_stats["city_name"].map(lambda c: CITY_COORDS.get(c, (0, 0))[1])

    # Build hover text
    city_stats["hover"] = city_stats.apply(
        lambda r: (
            f"<b style='font-size:14px'>{r['city_name']}</b><br>"
            f"<br>"
            f"🌡️ Avg Temp: <b>{r['temp_avg']:.1f}°C</b><br>"
            f"📊 Range: {r['temp_min']:.1f}°C → {r['temp_max']:.1f}°C<br>"
            f"🌧️ Total Precip: <b>{r['precip_total']:.0f} mm</b><br>"
            f"💧 Avg Humidity: {r['humidity_avg']:.0f}%<br>"
            f"💨 Avg Wind: {r['wind_avg']:.1f} km/h<br>"
            f"❄️ Freezing Days: {r['freezing_days']}<br>"
            f"<br>"
            f"<i>{r['vibe']}</i>"
        ),
        axis=1,
    )

    # Marker size: scale by temperature range
    t_min, t_max = city_stats["temp_avg"].min(), city_stats["temp_avg"].max()
    city_stats["marker_size"] = 12 + 18 * (
        (city_stats["temp_avg"] - t_min) / max(t_max - t_min, 1)
    )

    # Create Scattergeo map
    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lat=city_stats["lat"],
        lon=city_stats["lon"],
        text=city_stats["city_name"],
        hovertext=city_stats["hover"],
        hoverinfo="text",
        mode="markers+text",
        textposition="top center",
        textfont=dict(size=10, color="rgba(230,210,250,0.7)"),
        customdata=city_stats["city_name"],
        marker=dict(
            size=city_stats["marker_size"],
            color=city_stats["temp_avg"],
            colorscale=[
                [0.0, "#6366f1"],
                [0.25, "#a78bfa"],
                [0.5, "#f0abfc"],
                [0.75, "#fb923c"],
                [1.0, "#f43f5e"],
            ],
            colorbar=dict(
                title=dict(text="Avg °C", font=dict(color="#c0c0e0", size=12)),
                tickfont=dict(color="#c0c0e0"),
                bgcolor="rgba(0,0,0,0)",
                outlinewidth=0,
                len=0.5,
                y=0.5,
            ),
            line=dict(width=1, color="rgba(255,255,255,0.3)"),
            opacity=0.9,
        ),
    ))

    fig.update_layout(
        height=600,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#c0c0e0"),
        geo=dict(
            scope="usa",
            bgcolor="rgba(0,0,0,0)",
            lakecolor="rgba(100,150,220,0.08)",
            landcolor="rgba(20,16,36,0.9)",
            subunitcolor="rgba(180,140,220,0.1)",
            countrycolor="rgba(180,140,220,0.15)",
            coastlinecolor="rgba(180,140,220,0.12)",
            showlakes=True,
            showland=True,
            showsubunits=True,
            projection_type="albers usa",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # City detail cards below the map
    st.markdown(
        '<div class="section-header">📍 City Climate Profiles</div>',
        unsafe_allow_html=True,
    )

    # Display in 3-column grid
    cols_per_row = 3
    rows = [city_stats.iloc[i:i + cols_per_row] for i in range(0, len(city_stats), cols_per_row)]

    for row_chunk in rows:
        cols = st.columns(cols_per_row)
        for idx, (_, city) in enumerate(row_chunk.iterrows()):
            with cols[idx]:
                # Temperature-based card styling
                t = city["temp_avg"]
                if t > 15:
                    temp_color = "#f43f5e"
                    card_bg = "linear-gradient(135deg, rgba(244,63,94,0.08), rgba(251,146,60,0.04))"
                    border_col = "rgba(244,63,94,0.15)"
                    accent = "linear-gradient(90deg, #f43f5e, #fb923c)"
                elif t > 5:
                    temp_color = "#fb923c"
                    card_bg = "linear-gradient(135deg, rgba(251,146,60,0.07), rgba(200,170,240,0.04))"
                    border_col = "rgba(251,146,60,0.12)"
                    accent = "linear-gradient(90deg, #fb923c, #f0abfc)"
                elif t > 0:
                    temp_color = "#a78bfa"
                    card_bg = "linear-gradient(135deg, rgba(167,139,250,0.08), rgba(100,200,220,0.04))"
                    border_col = "rgba(167,139,250,0.15)"
                    accent = "linear-gradient(90deg, #a78bfa, #60a5fa)"
                else:
                    temp_color = "#6366f1"
                    card_bg = "linear-gradient(135deg, rgba(99,102,241,0.1), rgba(167,139,250,0.05))"
                    border_col = "rgba(99,102,241,0.18)"
                    accent = "linear-gradient(90deg, #6366f1, #818cf8)"

                st.markdown(
                    f"""
                    <div style="background:{card_bg};border:1px solid {border_col};
                        border-radius:14px;padding:18px;margin-bottom:12px;
                        position:relative;overflow:hidden;
                        transition:all 0.3s ease;">
                        <div style="position:absolute;top:0;left:0;right:0;height:2px;
                            background:{accent};"></div>
                        <div style="font-size:1.05rem;font-weight:600;color:#e0d0f0;
                            margin-bottom:10px;">{city['city_name']}</div>
                        <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;">
                            <span style="background:{temp_color}22;color:{temp_color};
                                padding:2px 8px;border-radius:12px;font-size:0.75rem;
                                font-weight:600;">{city['temp_avg']:.1f}°C avg</span>
                            <span style="background:rgba(100,200,220,0.12);color:#64c8dc;
                                padding:2px 8px;border-radius:12px;font-size:0.75rem;
                                font-weight:600;">{city['precip_total']:.0f} mm rain</span>
                            <span style="background:rgba(200,180,230,0.12);color:#c8b4e6;
                                padding:2px 8px;border-radius:12px;font-size:0.75rem;
                                font-weight:600;">{city['wind_avg']:.1f} km/h</span>
                        </div>
                        <div style="font-size:0.78rem;color:rgba(200,180,220,0.5);line-height:1.6;">
                            Range: {city['temp_min']:.1f}°C → {city['temp_max']:.1f}°C<br>
                            Humidity: {city['humidity_avg']:.0f}% · Cloud: {city['cloud_avg']:.0f}%<br>
                            ❄️ {int(city['freezing_days'])} freezing days · {int(city['records'])} records
                        </div>
                        <div style="margin-top:8px;font-size:0.8rem;color:rgba(230,210,250,0.6);
                            font-style:italic;">{city['vibe']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ══════════════════════════════════════════════
# Data Quality — shown inside sidebar expander
# ══════════════════════════════════════════════

# The quality details are rendered inside the sidebar expander defined above.
# We populate it here so it's always available regardless of which page is active.
with st.sidebar.expander("🔍 Data Quality Details", expanded=False):
    if report is not None:
        st.markdown(
            f'**Status:** <span class="quality-badge '
            f'{"quality-pass" if report["overall_status"] == "PASS" else "quality-fail"}">'
            f'{report["overall_status"]}</span> &nbsp; '
            f'**Rate:** {report["pass_rate"]}% &nbsp; '
            f'({report["passed"]}/{report["total_checks"]} checks)',
            unsafe_allow_html=True,
        )

        checks_df = pd.DataFrame(report["checks"])
        checks_df["Status"] = checks_df["passed"].map({True: "✅", False: "❌"})
        st.dataframe(
            checks_df[["check", "Status", "details"]].rename(
                columns={"check": "Check", "details": "Details"}
            ),
            use_container_width=True,
            hide_index=True,
            height=300,
        )
    else:
        st.info("No quality report. Run the pipeline first.")
