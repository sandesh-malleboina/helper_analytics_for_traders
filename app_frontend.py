import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- Config ---
st.set_page_config(layout="wide", page_title="Quant Dashboard")
API_URL = "http://127.0.0.1:8000"

# --- NEW: Timeframe Options ---
TIMEFRAME_OPTIONS = ["1S", "2S", "5S", "10S", "30S", "1T", "2T", "5T", "15T", "30T", "1H"]

# --- NEW: Session State Initialization ---
# This holds the *index* of the selected timeframe for each chart
if 'tf_index_price' not in st.session_state:
    st.session_state.tf_index_price = 5 # Default to '1T'
if 'tf_index_spread' not in st.session_state:
    st.session_state.tf_index_spread = 5 # Default to '1T'
if 'tf_index_corr' not in st.session_state:
    st.session_state.tf_index_corr = 5 # Default to '1T'

# --- NEW: Callback functions for +/- buttons ---
def adjust_timeframe(chart_key, direction):
    """Increments or decrements the timeframe index for a specific chart."""
    current_index = st.session_state[chart_key]
    new_index = current_index + direction
    # Clamp the index to be within the bounds of the options list
    new_index = max(0, min(len(TIMEFRAME_OPTIONS) - 1, new_index))
    st.session_state[chart_key] = new_index

# --- Plotting Functions ---

def plot_prices(resampled_a, resampled_b, symbol_a, symbol_b, timeframe):
    """
    Plots the resampled close prices for both symbols on the
    SAME chart with two independent y-axes.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r['timestamp'] for r in resampled_a],
        y=[r['close'] for r in resampled_a],
        name=symbol_a,
        line=dict(color="#FF5733")
    ))
    fig.add_trace(go.Scatter(
        x=[r['timestamp'] for r in resampled_b],
        y=[r['close'] for r in resampled_b],
        name=symbol_b,
        line=dict(color="#00BFFF"),
        yaxis="y2"
    ))
    fig.update_layout(
        title_text=f"Resampled Prices ({timeframe})",
        height=500,
        xaxis_title="Timestamp",
        yaxis_title=f"{symbol_a} Price",
        yaxis2=dict(title=f"{symbol_b} Price", overlaying="y", side="right"),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    fig.update_yaxes(fixedrange=False)
    return fig

def plot_spread_zscore(pair_data, timeframe):
    """Plots the spread and its z-score."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        subplot_titles=(f"Pair Spread ({timeframe})", f"Spread Z-Score ({timeframe})"),
                        vertical_spacing=0.1)
    fig.add_trace(go.Scatter(x=[r['timestamp'] for r in pair_data], y=[r['spread'] for r in pair_data], name="Spread"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[r['timestamp'] for r in pair_data], y=[r['z_score'] for r in pair_data], name="Z-Score"), row=2, col=1)
    fig.add_hline(y=2.0, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=-2.0, line_dash="dash", line_color="red", row=2, col=1)
    fig.update_yaxes(fixedrange=False)
    fig.update_layout(title_text="Spread and Z-Score Analysis", height=500)
    return fig

def plot_rolling_corr(pair_data, timeframe):
    """Plots the rolling correlation."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r['timestamp'] for r in pair_data],
        y=[r['rolling_corr'] for r in pair_data],
        name="Rolling Correlation"
    ))
    fig.update_yaxes(fixedrange=False)
    fig.update_layout(title_text=f"Rolling Correlation ({timeframe})", height=400)
    return fig

# --- Helper Functions ---
@st.cache_data(ttl=10) # Cache for 10 seconds
def get_available_symbols():
    """Fetches available symbols from the backend."""
    try:
        res = requests.get(f"{API_URL}/data/symbols")
        if res.status_code == 200:
            return res.json()
    except requests.ConnectionError:
        return ["btcusdt", "ethusdt"]
    return ["btcusdt", "ethusdt"]

# --- REMOVED 5-SECOND TTL ---
@st.cache_data
def get_analytics_data(params):
    """Fetches analytics data from the backend."""
    try:
        res = requests.get(f"{API_URL}/analytics/pair", params=params)
        if res.status_code == 200:
            return res.json()
        else:
            try:
                detail = res.json().get("detail", "Unknown error")
            except requests.exceptions.JSONDecodeError:
                detail = f"Server returned status {res.status_code} with non-JSON body. Check backend logs."
            return {"error": detail}
    except requests.ConnectionError:
        return {"error": "Backend is not running."}

@st.cache_data
def get_tick_count():
    """Fetches the total tick count from the backend."""
    try:
        res = requests.get(f"{API_URL}/data/tick_count")
        if res.status_code == 200:
            return res.json().get("tick_count", 0)
    except requests.ConnectionError:
        return 0
    return 0

# --- Main App UI ---
st.title("GemsCap Quantitative Analytics Dashboard")

# --- Sidebar Controls ---
st.sidebar.header("Analysis Controls")
available_symbols = get_available_symbols()

symbol_a = st.sidebar.selectbox("Symbol A (e.g., Target)", available_symbols, index=0)
symbol_b = st.sidebar.selectbox("Symbol B (e.g., Hedge)", available_symbols, index=1)

# --- Rolling window is now a number_input box ---
rolling_window = st.sidebar.number_input(
    "Rolling Window", 
    min_value=5, 
    max_value=200, 
    value=20, 
    step=1
)

regression_type = st.sidebar.selectbox("Regression Type", ["OLS"]) 
adf_trigger = st.sidebar.button("Run ADF Test on Spread")

# --- Alert Configuration ---
st.sidebar.header("Alert Configuration")
st.sidebar.write("Define simple alerts (checked on new data):")
alert_data = [
    {'metric': 'z-score', 'operator': '>', 'value': 2.0},
    {'metric': 'z-score', 'operator': '<', 'value': -2.0},
]
edited_alerts = st.sidebar.data_editor(
    alert_data, 
    num_rows="dynamic",
    key="alerts_editor"
)

# --- Main Dashboard ---

tick_count = get_tick_count()
st.metric("Total Ticks Collected", f"{tick_count:,}")
st.markdown("---")


# --- Chart 1: Price ---
st.header("Interactive Charts")
st.subheader("Resampled Prices")

# Get current timeframe for this chart
tf_price = TIMEFRAME_OPTIONS[st.session_state.tf_index_price]

# Add controls for this chart
c1, c2, c3, c4 = st.columns([1, 1, 1, 10])
c1.button("➖", on_click=adjust_timeframe, args=('tf_index_price', -1), key='price_minus')
c2.button("➕", on_click=adjust_timeframe, args=('tf_index_price', 1), key='price_plus')
if c3.button("Refresh", key='price_refresh'):
    # Clear cache for this specific function
    get_analytics_data.clear()
c4.markdown(f"**Current Timeframe: {tf_price}**")

# API Request for this chart
api_params_price = {
    "symbol_a": symbol_a, "symbol_b": symbol_b,
    "timeframe": tf_price, "rolling_window": rolling_window,
    "regression_type": regression_type
}
data_price = get_analytics_data(api_params_price)

if "error" in data_price:
    st.error(f"Error for Price Chart: {data_price['error']}")
else:
    charts_price = data_price.get("charts", {})
    resampled_a = charts_price.get("resampled_a", [])
    resampled_b = charts_price.get("resampled_b", [])
    if resampled_a:
        st.plotly_chart(plot_prices(resampled_a, resampled_b, symbol_a, symbol_b, tf_price), use_container_width=True)
    else:
        st.warning("Not enough data to plot prices.")


# --- Chart 2: Spread / Z-Score ---
st.subheader("Spread & Z-Score Analysis")

# Get current timeframe for this chart
tf_spread = TIMEFRAME_OPTIONS[st.session_state.tf_index_spread]

# Add controls for this chart
c1, c2, c3, c4 = st.columns([1, 1, 1, 10])
c1.button("➖", on_click=adjust_timeframe, args=('tf_index_spread', -1), key='spread_minus')
c2.button("➕", on_click=adjust_timeframe, args=('tf_index_spread', 1), key='spread_plus')
if c3.button("Refresh", key='spread_refresh'):
    get_analytics_data.clear()
c4.markdown(f"**Current Timeframe: {tf_spread}**")

# API Request for this chart
api_params_spread = {
    "symbol_a": symbol_a, "symbol_b": symbol_b,
    "timeframe": tf_spread, "rolling_window": rolling_window,
    "regression_type": regression_type
}
data_spread = get_analytics_data(api_params_spread)

if "error" in data_spread:
    st.error(f"Error for Spread Chart: {data_spread['error']}")
else:
    charts_spread = data_spread.get("charts", {})
    pair_data_spread = charts_spread.get("pair_data", [])
    if pair_data_spread:
        st.plotly_chart(plot_spread_zscore(pair_data_spread, tf_spread), use_container_width=True)
    else:
        st.warning("Not enough data to plot spread/z-score.")


# --- Chart 3: Rolling Correlation ---
st.subheader("Rolling Correlation Analysis")

# Get current timeframe for this chart
tf_corr = TIMEFRAME_OPTIONS[st.session_state.tf_index_corr]

# Add controls for this chart
c1, c2, c3, c4 = st.columns([1, 1, 1, 10])
c1.button("➖", on_click=adjust_timeframe, args=('tf_index_corr', -1), key='corr_minus')
c2.button("➕", on_click=adjust_timeframe, args=('tf_index_corr', 1), key='corr_plus')
if c3.button("Refresh", key='corr_refresh'):
    get_analytics_data.clear()
c4.markdown(f"**Current Timeframe: {tf_corr}**")

# API Request for this chart
api_params_corr = {
    "symbol_a": symbol_a, "symbol_b": symbol_b,
    "timeframe": tf_corr, "rolling_window": rolling_window,
    "regression_type": regression_type
}
data_corr = get_analytics_data(api_params_corr)

if "error" in data_corr:
    st.error(f"Error for Correlation Chart: {data_corr['error']}")
else:
    charts_corr = data_corr.get("charts", {})
    pair_data_corr = charts_corr.get("pair_data", [])
    if pair_data_corr:
        st.plotly_chart(plot_rolling_corr(pair_data_corr, tf_corr), use_container_width=True)
    else:
        st.warning("Not enough data to plot correlation.")


# --- Static Sections (using data from the last API call) ---
st.markdown("---")
st.header("Static Analytics")
st.write(f"These analytics are based on the **Rolling Correlation** chart's timeframe ({tf_corr}).")

analytics = data_corr.get("analytics", {})
if analytics:
    # --- Check Alerts ---
    pair_data_for_alerts = data_corr.get("charts", {}).get("pair_data", [])
    if pair_data_for_alerts:
        current_zscore = pair_data_for_alerts[-1].get('z_score')
        if current_zscore is not None:
            for alert in edited_alerts:
                if alert['metric'] == 'z-score':
                    if alert['operator'] == '>' and current_zscore > alert['value']:
                        st.error(f"🚨 ALERT: Z-Score ({current_zscore:.2f}) is > {alert['value']}")
                    elif alert['metric'] == '<' and current_zscore < alert['value']:
                        st.error(f"🚨 ALERT: Z-Score ({current_zscore:.2f}) is < {alert['value']}")

    # --- Summary Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hedge Ratio (OLS)", f"{analytics.get('hedge_ratio', 0):.4f}")
    
    latest_spread = pair_data_for_alerts[-1].get('spread') if pair_data_for_alerts else None
    col2.metric(
        f"Latest Spread ({symbol_a} - {analytics.get('hedge_ratio', 0):.2f}*{symbol_b})", 
        f"{latest_spread:.2f}" if latest_spread is not None else "N/A"
    )
    col3.metric("Latest Z-Score", f"{current_zscore:.4f}" if current_zscore is not None else "N/A")
    
    adf_pval = analytics.get('adf_test_spread', {}).get('p_value')
    col4.metric(
        "Spread ADF p-value", 
        f"{adf_pval:.3f}" if adf_pval is not None else "N/A"
    )
    
    if adf_trigger:
        st.subheader("Spread Stationarity (ADF Test)")
        st.json(analytics.get('adf_test_spread', {}))

    # --- Summary Stats & Download ---
    st.header("Summary Statistics")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader(f"{symbol_a} Stats")
        st.dataframe(pd.DataFrame(analytics.get("stats_a", {}), index=[0]))
    with c2:
        st.subheader(f"{symbol_b} Stats")
        st.dataframe(pd.DataFrame(analytics.get("stats_b", {}), index=[0]))
    
    download_params = f"symbol_a={symbol_a}&symbol_b={symbol_b}&timeframe={tf_corr}&rolling_window={rolling_window}"
    st.markdown(
        f"🔗 [Download Processed Analytics CSV]({API_URL}/data/download?{download_params})",
        unsafe_allow_html=True
    )
else:
    st.warning("Run an analysis to see summary statistics.")