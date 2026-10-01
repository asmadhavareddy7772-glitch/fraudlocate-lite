"""
FraudLocate Lite - Temporal Analytics & Interactive Visualizations.
Provides hourly, day-of-week, and cross-tabulated heatmap analytics with Plotly.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

DAYS_OF_WEEK_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]

CYBER_THEME = {
    "paper_bgcolor": "rgba(15, 23, 42, 0.0)",
    "plot_bgcolor": "rgba(30, 41, 59, 0.4)",
    "font_family": "Inter, system-ui, -apple-system, sans-serif",
    "font_color": "#e2e8f0",
    "accent_cyan": "#06b6d4",
    "accent_emerald": "#10b981",
    "accent_amber": "#f59e0b",
    "accent_rose": "#f43f5e",
    "grid_color": "rgba(148, 163, 184, 0.15)",
}


def filter_dataset(
    df: pd.DataFrame,
    cluster_filter: Optional[str] = "All",
    day_filter: Optional[List[str]] = None,
    hour_range: Optional[tuple[int, int]] = None,
    date_range: Optional[tuple[str, str]] = None,
    activity_filter: Optional[str] = "All",
) -> pd.DataFrame:
    """
    Filter dataframe by cluster, day of week, hour range, date range, or activity level.
    """
    filtered = df.copy()

    if cluster_filter and cluster_filter != "All":
        filtered = filtered[filtered["cluster_label"] == cluster_filter]

    if day_filter and len(day_filter) > 0 and "All" not in day_filter:
        filtered = filtered[filtered["day_of_week"].isin(day_filter)]

    if hour_range:
        h_min, h_max = hour_range
        filtered = filtered[(filtered["hour"] >= h_min) & (filtered["hour"] <= h_max)]

    if date_range and "date" in filtered.columns:
        d_min, d_max = date_range
        filtered = filtered[(filtered["date"] >= str(d_min)) & (filtered["date"] <= str(d_max))]

    if activity_filter and activity_filter != "All" and "priority_tier" in filtered.columns:
        filtered = filtered[filtered["priority_tier"] == activity_filter]

    return filtered


def generate_hourly_chart(df: pd.DataFrame) -> go.Figure:
    """
    Generate an interactive Plotly bar + trendline chart for 24-hour withdrawal activity.
    """
    if df.empty or "hour" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="<b>No withdrawal activity data available</b>")
        return fig

    hourly_counts = df.groupby("hour").agg(
        transactions=("transaction_id", "count"),
        total_amount=("withdrawal_amount", "sum"),
        avg_amount=("withdrawal_amount", "mean"),
    ).reindex(range(24), fill_value=0).reset_index()

    peak_hour = hourly_counts.loc[hourly_counts["transactions"].idxmax(), "hour"]

    # Color bars with highlight on peak hour
    bar_colors = [
        CYBER_THEME["accent_rose"] if h == peak_hour else CYBER_THEME["accent_cyan"]
        for h in hourly_counts["hour"]
    ]

    fig = go.Figure()

    # Bar trace for transaction volume
    fig.add_trace(
        go.Bar(
            x=[f"{h:02d}:00" for h in hourly_counts["hour"]],
            y=hourly_counts["transactions"],
            name="Withdrawals",
            marker=dict(color=bar_colors, opacity=0.85, line=dict(color="#38bdf8", width=1)),
            hovertemplate="<b>%{x}</b><br>Withdrawals: %{y}<extra></extra>",
        )
    )

    # Smooth trendline overlay
    fig.add_trace(
        go.Scatter(
            x=[f"{h:02d}:00" for h in hourly_counts["hour"]],
            y=hourly_counts["transactions"],
            mode="lines+markers",
            name="Activity Trend",
            line=dict(color="#a855f7", width=2.5, shape="spline"),
            marker=dict(size=6, color="#c084fc"),
            hovertemplate="Trend: %{y} txns<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"<b>24-Hour Withdrawal Activity Pattern</b> (Historical Peak: {peak_hour:02d}:00 - {(peak_hour+1)%24:02d}:00)",
        xaxis_title="Hour of Day",
        yaxis_title="Number of Withdrawals",
        font=dict(family=CYBER_THEME["font_family"], color=CYBER_THEME["font_color"], size=12),
        paper_bgcolor=CYBER_THEME["paper_bgcolor"],
        plot_bgcolor=CYBER_THEME["plot_bgcolor"],
        margin=dict(l=40, r=40, t=60, b=40),
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(gridcolor=CYBER_THEME["grid_color"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def generate_day_of_week_chart(df: pd.DataFrame) -> go.Figure:
    """
    Generate an interactive Plotly bar chart for day-of-week withdrawal frequency.
    """
    if df.empty or "day_of_week" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="<b>No withdrawal activity data available</b>")
        return fig

    day_counts = df.groupby("day_of_week").agg(
        transactions=("transaction_id", "count"),
        total_amount=("withdrawal_amount", "sum"),
    ).reindex(DAYS_OF_WEEK_ORDER, fill_value=0).reset_index()

    peak_day = day_counts.loc[day_counts["transactions"].idxmax(), "day_of_week"]

    colors = [
        CYBER_THEME["accent_rose"] if d == peak_day else CYBER_THEME["accent_emerald"]
        for d in day_counts["day_of_week"]
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=day_counts["day_of_week"],
            y=day_counts["transactions"],
            marker=dict(color=colors, opacity=0.88, line=dict(color="#34d399", width=1)),
            hovertemplate="<b>%{x}</b><br>Withdrawals: %{y}<br>Total Amount: ₹%{customdata:,.0f}<extra></extra>",
            customdata=day_counts["total_amount"],
        )
    )

    fig.update_layout(
        title=f"<b>Day-of-Week Withdrawal Distribution</b> (Most Active: {peak_day})",
        xaxis_title="Day of Week",
        yaxis_title="Number of Withdrawals",
        font=dict(family=CYBER_THEME["font_family"], color=CYBER_THEME["font_color"], size=12),
        paper_bgcolor=CYBER_THEME["paper_bgcolor"],
        plot_bgcolor=CYBER_THEME["plot_bgcolor"],
        margin=dict(l=40, r=40, t=60, b=40),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=CYBER_THEME["grid_color"]),
    )
    return fig


def generate_day_hour_heatmap(df: pd.DataFrame) -> go.Figure:
    """
    Generate a 2D Day x Hour heatmap matrix showing historical withdrawal intensity.
    """
    if df.empty or "day_of_week" not in df.columns or "hour" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="<b>No withdrawal activity data available</b>")
        return fig

    # Cross-tabulate day of week and hour
    matrix = pd.crosstab(
        df["day_of_week"],
        df["hour"],
    ).reindex(index=DAYS_OF_WEEK_ORDER, columns=range(24), fill_value=0)

    hour_labels = [f"{h:02d}:00" for h in range(24)]

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=hour_labels,
            y=matrix.index.tolist(),
            colorscale="Viridis",
            hoverongaps=False,
            hovertemplate="<b>%{y} at %{x}</b><br>Withdrawals: %{z}<extra></extra>",
            colorbar=dict(title="Txns", thickness=15),
        )
    )

    fig.update_layout(
        title="<b>Day of Week × Hour-of-Day Intensity Matrix</b>",
        xaxis_title="Hour of Day",
        yaxis_title="Day of Week",
        font=dict(family=CYBER_THEME["font_family"], color=CYBER_THEME["font_color"], size=12),
        paper_bgcolor=CYBER_THEME["paper_bgcolor"],
        plot_bgcolor=CYBER_THEME["plot_bgcolor"],
        margin=dict(l=40, r=40, t=60, b=40),
        xaxis=dict(tickangle=-45),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def generate_money_movement_timeline_chart(df: pd.DataFrame) -> go.Figure:
    """
    Generate chronological timeline of cash withdrawal volume and cumulative amount.
    Highlights liquidation velocity across dates/hours.
    """
    if df.empty or "date" not in df.columns:
        return go.Figure()

    df_time = df.copy()
    if "timestamp" in df_time.columns:
        df_time["dt"] = pd.to_datetime(df_time["timestamp"], errors="coerce")
    else:
        df_time["dt"] = pd.to_datetime(df_time["date"] + " " + df_time.get("time", "12:00:00"), errors="coerce")

    df_time = df_time.dropna(subset=["dt"]).sort_values("dt")
    if df_time.empty:
        return go.Figure()

    # Aggregate by 4-hour intervals or daily
    df_time["time_bin"] = df_time["dt"].dt.floor("6h")
    agg = df_time.groupby("time_bin").agg(
        txns=("transaction_id", "count"),
        total_amount=("withdrawal_amount", "sum"),
        avg_amount=("withdrawal_amount", "mean"),
    ).reset_index()

    agg["cumulative_amount"] = agg["total_amount"].cumsum()
    agg["cum_lakhs"] = agg["cumulative_amount"] / 100000.0

    fig = go.Figure()

    # Bar chart for interval amount
    fig.add_trace(
        go.Bar(
            x=agg["time_bin"],
            y=agg["total_amount"],
            name="Periodic Cash-Out (₹)",
            marker=dict(color="rgba(56, 189, 248, 0.75)", line=dict(color="#0284c7", width=1)),
            hovertemplate="<b>%{x|%d %b %H:%M}</b><br>Volume: ₹%{y:,.0f}<extra></extra>",
            yaxis="y1",
        )
    )

    # Line chart for cumulative sum
    fig.add_trace(
        go.Scatter(
            x=agg["time_bin"],
            y=agg["cum_lakhs"],
            name="Cumulative Total (Lakhs)",
            mode="lines+markers",
            line=dict(color="#f43f5e", width=3),
            marker=dict(size=5, color="#fda4af"),
            hovertemplate="<b>Cumulative:</b> ₹%{y:.2f} Lakhs<extra></extra>",
            yaxis="y2",
        )
    )

    fig.update_layout(
        title="<b>Money Movement & Cash-Out Velocity Timeline</b>",
        xaxis_title="Timeline Window",
        yaxis=dict(
            title="Periodic Cash-Out (₹)",
            gridcolor=CYBER_THEME["grid_color"],
            side="left",
        ),
        yaxis2=dict(
            title="Cumulative Total (₹ Lakhs)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        font=dict(family=CYBER_THEME["font_family"], color=CYBER_THEME["font_color"], size=12),
        paper_bgcolor=CYBER_THEME["paper_bgcolor"],
        plot_bgcolor=CYBER_THEME["plot_bgcolor"],
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig

