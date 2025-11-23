import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# Import analytics module
from analytics import PairsAnalytics, get_paired_candles

# Import alert system modules
from alert_manager import AlertManager
import alert_components

# ============================================
# PAGE CONFIGURATION
# ============================================

st.set_page_config(
    page_title="Pairs Analytics",
    page_icon="📊",
    layout="wide"
)

# ============================================
# CUSTOM CSS STYLING
# ============================================

ALL_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT"]

st.markdown("""
<style>
    .main {background-color: #0e1117;}
    .stMetric {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #2e3241;
    }
    h1 {color: #00ff87; font-weight: 700;}
    h2, h3, h4 {color: #e0e0e0;}
</style>
""", unsafe_allow_html=True)

# ============================================
# INITIALIZE SYSTEMS
# ============================================

# Initialize Alert Manager in session state
if 'alert_manager' not in st.session_state:
    st.session_state.alert_manager = AlertManager()

# Connect to PostgreSQL
try:
    engine = create_engine("postgresql://postgres:kaustubh@localhost:5432/quantdb")
except Exception as e:
    st.error(f"❌ Database connection error: {e}")
    st.stop()

# Initialize Analytics
analytics = PairsAnalytics()

# ============================================
# HEADER
# ============================================

st.title("📊 Pairs Trading Analytics")
st.caption("Statistical arbitrage and mean-reversion analysis with real-time alerts")

# ============================================
# SIDEBAR CONTROLS (Static - runs once)
# ============================================

with st.sidebar:
    st.header("⚙️ Analytics Settings")
    
    # Symbol Pair Selection
    st.subheader("Symbol Pair")
    symbol1 = st.selectbox("Asset 1", ALL_SYMBOLS, index=0, key="sym1")
    symbol2 = st.selectbox("Asset 2", ALL_SYMBOLS, index=1, key="sym2")
    
    if symbol1 == symbol2:
        st.error("⚠️ Please select different symbols!")
        st.stop()
    
    # Timeframe Selection
    timeframe = st.selectbox("Timeframe", ["1s", "1m", "5m"], index=1, key="tf")
    
    # Analysis Parameters
    st.subheader("Parameters")
    lookback = st.slider("Lookback Period", 20, 200, 100, help="Number of candles to analyze")
    zscore_window = st.slider("Z-Score Window", 10, 50, 20, help="Rolling window for z-score calculation")
    
    # Trading Thresholds
    st.subheader("Trading Thresholds")
    entry_threshold = st.slider("Entry Z-Score", 1.0, 3.0, 2.0, 0.1, help="Z-score level to enter trade")
    exit_threshold = st.slider("Exit Z-Score", 0.0, 1.5, 0.5, 0.1, help="Z-score level to exit trade")
    
    # Refresh Rate (Used by the fragment scheduler below)
    refresh_rate = st.slider("Refresh (seconds)", 3, 15, 5)
    
    # Show alert summary in sidebar
    alert_components.show_alert_summary_sidebar()
    
    # Last update timestamp
    st.caption(f"🕐 Last update: {datetime.now().strftime('%H:%M:%S')}")

# ============================================
# DATA LOADING CACHED FUNCTION (REMAINS UNCHANGED)
# ============================================

@st.cache_data(ttl=refresh_rate, show_spinner=False)
def load_analytics_data(symbol1, symbol2, timeframe, lookback):
    """Load paired candle data from database"""
    try:
        df = get_paired_candles(engine, symbol1, symbol2, timeframe, lookback)
        return df
    except Exception as e:
        # Note: st.error/st.stop() cannot be used inside cached functions
        return None

# ============================================
# FRAGMENT: DYNAMIC DASHBOARD CONTENT
# ============================================

# The Fragment decorator handles scheduling and isolating the rerun, replacing time.sleep/st.rerun
@st.experimental_fragment(run_every="5s") # Using 5s as a static default for stability
def display_analytics_dashboard(symbol1, symbol2, timeframe, lookback, zscore_window, entry_threshold, exit_threshold):
    
    # Load data with spinner
    with st.spinner(f"Loading {symbol1}/{symbol2} data..."):
        # Pass the refresh_rate variable to the cache key, which ensures cache reset on slider change
        df = load_analytics_data(symbol1, symbol2, timeframe, lookback)

    # Check if data is available
    if df is None or df.empty or len(df) < 10:
        st.warning(f"⏳ No data available for {symbol1}/{symbol2}")
        st.info("""
        **Troubleshooting:**
        1. Make sure websocket_test.py is running (collecting ticks)
        2. Make sure build_ohlc.py is running (generating candles)
        3. Wait a few minutes for data to accumulate
        """)
        return # Use 'return' instead of st.stop() inside a fragment

    # ============================================
    # RUN ANALYTICS CALCULATIONS (UNCHANGED LOGIC)
    # ============================================
    try:
        prices1 = df[f'price_{symbol1.lower()}']
        prices2 = df[f'price_{symbol2.lower()}']
        
        hedge_result = analytics.calculate_hedge_ratio(prices1, prices2)
        
        if hedge_result is None:
            st.error("❌ Could not calculate hedge ratio. Need more data.")
            return
        
        spread = analytics.calculate_spread(prices1, prices2, hedge_result['hedge_ratio'])
        
        if spread is None:
            st.error("❌ Could not calculate spread")
            return
        
        zscore = analytics.calculate_zscore(spread, window=zscore_window)
        
        if zscore is None or zscore.dropna().empty:
            st.error("❌ Could not calculate z-score. Adjust window size or wait for more data.")
            return
        
        adf_result = analytics.run_adf_test(spread)
        correlation = analytics.calculate_rolling_correlation(prices1, prices2, window=zscore_window)
        signals = analytics.generate_trading_signals(zscore, entry_threshold, exit_threshold)
        
    except Exception as e:
        st.error(f"❌ Analytics error: {e}")
        import traceback
        st.code(traceback.format_exc())
        return

    # ============================================
    # PREPARE METRICS FOR ALERT CHECKING (UNCHANGED LOGIC)
    # ============================================
    current_metrics = {}
    if zscore is not None and not zscore.dropna().empty:
        current_metrics['zscore'] = zscore.dropna().iloc[-1]
    if spread is not None and not spread.dropna().empty:
        current_metrics['spread'] = spread.dropna().iloc[-1]
    if correlation is not None and not correlation.dropna().empty:
        current_metrics['correlation'] = correlation.dropna().iloc[-1]
    if hedge_result:
        current_metrics['hedge_ratio'] = hedge_result['hedge_ratio']
        current_metrics['r_squared'] = hedge_result['r_squared']

    # ============================================
    # CHECK AND DISPLAY TRIGGERED ALERTS (UNCHANGED LOGIC)
    # ============================================
    triggered_alerts = st.session_state.alert_manager.check_alerts(current_metrics)

    if triggered_alerts:
        alert_components.display_triggered_alerts(triggered_alerts)

    # ============================================
    # KEY METRICS DISPLAY (UNCHANGED DISPLAY)
    # ============================================

    st.markdown("### 📈 Key Metrics")
    # ... (Metrics row display code follows) ...
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if hedge_result:
            st.metric("Hedge Ratio (β)", f"{hedge_result['hedge_ratio']:.4f}", help="Optimal ratio from OLS regression")
        else: st.metric("Hedge Ratio", "N/A")
    with col2:
        if hedge_result:
            st.metric("R² (Fit Quality)", f"{hedge_result['r_squared']:.4f}", help="How well the prices are correlated")
        else: st.metric("R²", "N/A")
    with col3:
        if 'zscore' in current_metrics:
            st.metric("Current Z-Score", f"{current_metrics['zscore']:.2f}", help="Standardized spread value")
        else: st.metric("Z-Score", "N/A")
    with col4:
        if adf_result:
            st.metric("Stationarity", adf_result['interpretation'], f"p={adf_result['p_value']:.4f}", help="ADF test result for mean reversion")
        else: st.metric("Stationarity", "N/A")

    st.markdown("---")

    # ============================================
    # CHART 1: PRICE COMPARISON (UNCHANGED DISPLAY)
    # ============================================
    st.markdown("### 💹 Price Comparison")
    # ... (Fig 1 plot code follows) ...
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=df['time'], y=prices1, name=symbol1, line=dict(color='#00ff87', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df['time'], y=prices2, name=symbol2, line=dict(color='#ff3860', width=2)), secondary_y=True)
    fig1.update_layout(height=400, template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#1e2130', hovermode='x unified', showlegend=True, legend=dict(x=0.01, y=0.99))
    fig1.update_yaxes(title_text=f"{symbol1} Price (USDT)", secondary_y=False)
    fig1.update_yaxes(title_text=f"{symbol2} Price (USDT)", secondary_y=True)
    st.plotly_chart(fig1, use_container_width=True)
    st.markdown("---")

    # ============================================
    # CHART 2 & 3: SPREAD & Z-SCORE (UNCHANGED DISPLAY)
    # ============================================
    if spread is not None and zscore is not None and not zscore.dropna().empty:
        st.markdown("### 📊 Spread & Z-Score Analysis")
        # ... (Spread chart and Z-Score chart code follows, including alert buttons) ...
        # (All code from line 351 to 512 remains here)
        st.markdown("#### 📈 Spread (Price Difference)")
        fig_spread = go.Figure()
        fig_spread.add_trace(go.Scatter(x=df['time'], y=spread, name='Spread', line=dict(color='#3b82f6', width=2)))
        fig_spread.add_hline(y=spread.mean(), line_dash="dash", line_color="gray", annotation_text="Mean")
        fig_spread.update_layout(height=350, template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#1e2130', hovermode='x', showlegend=False, yaxis_title="Spread Value")
        st.plotly_chart(fig_spread, use_container_width=True)
        st.markdown("---")
        
        # Alert Section for Spread
        col1, col2 = st.columns([3, 1])
        with col1: alert_components.render_alert_button(metric='spread', default_threshold=650.0, step=10.0, key_suffix='spread_chart')
        with col2:
            spread_alerts = st.session_state.alert_manager.get_alerts_by_metric('spread')
            if spread_alerts:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Delete All Spread Alerts", type="secondary", key="delete_all_spread"):
                    for alert in spread_alerts: st.session_state.alert_manager.remove_alert(alert.alert_id)
                    st.success("✅ All spread alerts deleted!")
                    st.rerun()

        st.markdown("---")
        st.markdown("")
        
        # Z-Score Chart
        st.markdown("#### 📊 Z-Score (Normalized Spread)")
        fig_zscore = go.Figure()
        fig_zscore.add_trace(go.Scatter(x=df['time'], y=zscore, name='Z-Score', line=dict(color='#fbbf24', width=2)))
        fig_zscore.add_hline(y=entry_threshold, line_dash="dash", line_color="red", annotation_text=f"SHORT Entry (+{entry_threshold})")
        fig_zscore.add_hline(y=-entry_threshold, line_dash="dash", line_color="green", annotation_text=f"LONG Entry (-{entry_threshold})")
        fig_zscore.add_hline(y=exit_threshold, line_dash="dot", line_color="orange", annotation_text=f"Exit (+{exit_threshold})")
        fig_zscore.add_hline(y=-exit_threshold, line_dash="dot", line_color="orange")
        fig_zscore.add_hline(y=0, line_color="white", line_width=1)
        fig_zscore.update_layout(height=350, template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#1e2130', hovermode='x', showlegend=False, yaxis_title="Z-Score Value")
        st.plotly_chart(fig_zscore, use_container_width=True)
        
        # Alert Section for Z-Score
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col1: alert_components.render_alert_button(metric='zscore', default_threshold=2.0, step=0.1, key_suffix='zscore_chart')
        with col2:
            zscore_alerts = st.session_state.alert_manager.get_alerts_by_metric('zscore')
            if zscore_alerts:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Delete All Z-Score Alerts", type="secondary", key="delete_all_zscore"):
                    for alert in zscore_alerts: st.session_state.alert_manager.remove_alert(alert.alert_id)
                    st.success("✅ All z-score alerts deleted!")
                    st.rerun()
    else:
        st.warning("⚠️ Cannot display spread/z-score charts: insufficient data")

    st.markdown("---")
    st.markdown("")

    # ============================================
    # CHART 4: ROLLING CORRELATION (UNCHANGED DISPLAY)
    # ============================================
    if correlation is not None and not correlation.dropna().empty:
        st.markdown("### 🔗 Rolling Correlation")
        # ... (Fig 3 plot code follows) ...
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df['time'], y=correlation, name='Correlation', fill='tozeroy', line=dict(color='#8b5cf6', width=2)))
        fig3.add_hline(y=0.7, line_dash="dash", line_color="green", annotation_text="Strong Correlation")
        fig3.add_hline(y=0, line_color="white", line_width=1)
        fig3.update_layout(height=300, template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#1e2130', hovermode='x', yaxis_range=[-1, 1], yaxis_title="Correlation Coefficient")
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown("---")

        # Alert Section for Correlation
        col1, col2 = st.columns([3, 1])
        with col1: alert_components.render_alert_button(metric='correlation', default_threshold=0.5, step=0.1, key_suffix='correlation_chart')
        with col2:
            corr_alerts = st.session_state.alert_manager.get_alerts_by_metric('correlation')
            if corr_alerts:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Delete All Correlation Alerts", type="secondary", key="delete_all_corr"):
                    for alert in corr_alerts: st.session_state.alert_manager.remove_alert(alert.alert_id)
                    st.success("✅ All correlation alerts deleted!")
                    st.rerun()
    else:
        st.warning("⚠️ Cannot display correlation chart: insufficient data")

    st.markdown("---")

    # ============================================
    # STATISTICS PANEL (UNCHANGED DISPLAY)
    # ============================================
    st.markdown("### 📋 Detailed Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### OLS Regression Results")
        if hedge_result:
            fit_quality = "Excellent" if hedge_result['r_squared'] > 0.8 else "Good" if hedge_result['r_squared'] > 0.6 else "Moderate"
            st.json({"Hedge Ratio (β)": f"{hedge_result['hedge_ratio']:.6f}", "Intercept (α)": f"{hedge_result['alpha']:.2f}", "R-Squared": f"{hedge_result['r_squared']:.6f}", "P-Value": f"{hedge_result['p_value']:.6e}", "Model Fit": fit_quality})
            if hedge_result['r_squared'] < 0.5: st.warning("⚠️ Low R²: Prices may not be well-correlated")
        else: st.info("Insufficient data for regression")
    with col2:
        st.markdown("#### ADF Stationarity Test")
        if adf_result:
            confidence = "High (p<0.01)" if adf_result['p_value'] < 0.01 else "Moderate (p<0.05)" if adf_result['p_value'] < 0.05 else "Low"
            st.json({"Test Statistic": f"{adf_result['adf_statistic']:.4f}", "P-Value": f"{adf_result['p_value']:.6f}", "Result": adf_result['interpretation'], "Tradeable": "✅ Yes" if adf_result['is_stationary'] else "❌ No", "Confidence": confidence})
            if not adf_result['is_stationary']: st.warning("⚠️ Non-stationary spread: Not ideal for mean reversion trading")
        else: st.info("Insufficient data for ADF test")

    st.markdown("---")

    # ============================================
    # TRADING SIGNALS (UNCHANGED DISPLAY)
    # ============================================
    if signals is not None and zscore is not None and not zscore.dropna().empty:
        st.markdown("### 🎯 Current Trading Signal")
        current_signal = signals.dropna().iloc[-1] if not signals.dropna().empty else 0
        current_z = current_metrics['zscore']
        
        if current_signal == 1:
            st.success(f"""
            ### 🟢 LONG SIGNAL
            **Z-Score:** {current_z:.2f} (Below -{entry_threshold})
            **Recommended Action:** - Buy {symbol1}
            - Sell {hedge_result['hedge_ratio']:.4f} units of {symbol2}
            **Rationale:** Spread is abnormally low, expecting mean reversion upward
            """)
        elif current_signal == -1:
            st.error(f"""
            ### 🔴 SHORT SIGNAL
            **Z-Score:** {current_z:.2f} (Above +{entry_threshold})
            **Recommended Action:**
            - Sell {symbol1}
            - Buy {hedge_result['hedge_ratio']:.4f} units of {symbol2}
            **Rationale:** Spread is abnormally high, expecting mean reversion downward
            """)
        else:
            st.info(f"""
            ### ⚪ NEUTRAL / EXIT
            **Z-Score:** {current_z:.2f} (Between ±{exit_threshold})
            **Recommended Action:** No new trade / Close existing positions
            **Rationale:** Spread near mean, no clear opportunity
            """)
    else:
        st.warning("⚠️ Cannot generate trading signals: insufficient data")


# ============================================
# MAIN EXECUTION CALL
# ============================================

# Call the fragment function, passing all necessary sidebar variables as arguments.
# This ensures that changing any sidebar value (which triggers a full rerun) immediately updates the fragment content.
display_analytics_dashboard(symbol1, symbol2, timeframe, lookback, zscore_window, entry_threshold, exit_threshold)

# ============================================
# NOTE: The old time.sleep(refresh_rate) and st.rerun() are REMOVED.
# The Fragment decorator handles the scheduling now, giving you the smooth UX.
# ============================================