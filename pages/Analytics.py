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
import os
import tempfile

# Import analytics module
from analytics import PairsAnalytics, get_paired_candles

# Import alert system modules
from alert_manager import AlertManager
import alert_components

# Import telegram sender
from telegram_sender import send_telegram_document

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
    .export-section {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border: 2px solid #00ff87;
        margin-top: 30px;
    }
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
    
    # --- Data Source Selector ---
    st.markdown("---")
    st.header("Data Source")

    if 'analysis_source' not in st.session_state:
        st.session_state.analysis_source = "Live Candles (DB)"
        
    uploaded_ready = st.session_state.get('uploaded_data_ready', False)

    options = ["Live Candles (DB)"]
    if uploaded_ready:
        options.append("Uploaded File")

    analysis_mode = st.radio(
        "Select Source",
        options,
        index=options.index(st.session_state.analysis_source) if st.session_state.analysis_source in options else 0,
        key='analysis_mode_radio',
        help="Switch between live stream data and a file uploaded via the 'Upload Data' page."
    )
    st.session_state.analysis_source = analysis_mode 
    
    # Analysis Parameters
    st.subheader("Parameters")
    lookback = st.slider("Lookback Period", 20, 200, 100, help="Number of candles to analyze")
    zscore_window = st.slider("Z-Score Window", 10, 50, 20, help="Rolling window for z-score calculation")
    
    regression_type = st.selectbox(
        "Regression Type",
        options=["OLS (Ordinary Least Squares)", "Kalman Filter (Extension)"],
        index=0,
        help="Select the method for calculating the optimal hedge ratio."
    )
    
    # Trading Thresholds
    st.subheader("Trading Thresholds")
    entry_threshold = st.slider("Entry Z-Score", 1.0, 3.0, 2.0, 0.1, help="Z-score level to enter trade")
    exit_threshold = st.slider("Exit Z-Score", 0.0, 1.5, 0.5, 0.1, help="Z-score level to exit trade")
    
    refresh_rate = st.slider("Refresh (seconds)", 3, 15, 5)
    
    alert_components.show_alert_summary_sidebar()
    
    st.caption(f"🕐 Last update: {datetime.now().strftime('%H:%M:%S')}")

# ============================================
# HELPER FUNCTIONS FOR CSV EXPORT
# ============================================

def export_analytics_to_csv(df, symbol1, symbol2, timeframe, spread, zscore, correlation, signals, hedge_result):
    """Convert analytics dataframe to CSV string with metadata and formulas"""
    
    # Build metadata header with formulas
    csv_data = f"# Pairs Trading Analytics Export\n"
    csv_data += f"# Pair: {symbol1} / {symbol2}\n"
    csv_data += f"# Timeframe: {timeframe}\n"
    csv_data += f"# Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    csv_data += f"# Total Data Points: {len(df)}\n"
    csv_data += f"#\n"
    csv_data += f"# === CALCULATION FORMULAS ===\n"
    csv_data += f"# Hedge Ratio (β): Calculated using OLS regression: {symbol1} = α + β × {symbol2}\n"
    csv_data += f"# Hedge Ratio Value: {hedge_result['hedge_ratio']:.6f}\n"
    csv_data += f"# R-Squared: {hedge_result['r_squared']:.6f}\n"
    csv_data += f"#\n"
    csv_data += f"# Spread = Price_{symbol1} - (Hedge_Ratio × Price_{symbol2})\n"
    csv_data += f"# Z-Score = (Spread - Rolling_Mean) / Rolling_StdDev\n"
    csv_data += f"# Correlation = Rolling correlation between {symbol1} and {symbol2} prices\n"
    csv_data += f"# Signal: 1 = LONG, -1 = SHORT, 0 = NEUTRAL/EXIT\n"
    csv_data += f"#\n"
    csv_data += f"# === TRADING LOGIC ===\n"
    csv_data += f"# LONG Signal: Z-Score < -{entry_threshold} (Spread abnormally low)\n"
    csv_data += f"# SHORT Signal: Z-Score > +{entry_threshold} (Spread abnormally high)\n"
    csv_data += f"# EXIT Signal: |Z-Score| < {exit_threshold} (Spread near mean)\n"
    csv_data += f"#\n"
    
    # Create export dataframe
    export_df = pd.DataFrame({
        'time': df['time'],
        f'price_{symbol1.lower()}': df[f'price_{symbol1.lower()}'],
        f'price_{symbol2.lower()}': df[f'price_{symbol2.lower()}'],
        'spread': spread,
        'zscore': zscore,
        'correlation': correlation,
        'trading_signal': signals,
        'hedge_ratio': hedge_result['hedge_ratio']
    })
    
    # Add the actual data
    csv_data += export_df.to_csv(index=False)
    
    return csv_data

def send_analytics_csv_to_telegram(df, symbol1, symbol2, timeframe, spread, zscore, correlation, signals, hedge_result, current_metrics):
    """Send analytics CSV data to Telegram"""
    
    try:
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create CSV file
        csv_filename = f"{symbol1}_{symbol2}_analytics_{timeframe}_{timestamp}.csv"
        csv_filepath = os.path.join(temp_dir, csv_filename)
        
        # Generate CSV content
        csv_content = export_analytics_to_csv(df, symbol1, symbol2, timeframe, spread, zscore, correlation, signals, hedge_result)
        
        # Write file and ensure it's flushed to disk
        with open(csv_filepath, 'w', encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk
        
        # Verify file exists and has content
        if not os.path.exists(csv_filepath):
            st.error("❌ Failed to create CSV file")
            return False
        
        file_size = os.path.getsize(csv_filepath)
        if file_size == 0:
            st.error("❌ CSV file is empty")
            return False
        
        # Prepare Telegram caption
        current_z = current_metrics.get('zscore', 0)
        current_spread = current_metrics.get('spread', 0)
        current_corr = current_metrics.get('correlation', 0)
        
        # Determine current signal
        signal_text = "NEUTRAL/EXIT"
        if not signals.dropna().empty:
            current_signal = signals.dropna().iloc[-1]
            if current_signal == 1:
                signal_text = "🟢 LONG"
            elif current_signal == -1:
                signal_text = "🔴 SHORT"
        
        caption = f"📊 *Pairs Trading Analytics Export*\n\n"
        caption += f"📈 Pair: {symbol1} / {symbol2}\n"
        caption += f"⏰ Timeframe: `{timeframe}`\n"
        caption += f"📅 Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        caption += f"📊 Data Points: {len(df)}\n\n"
        caption += f"*Current Metrics:*\n"
        caption += f"⚖️ Hedge Ratio: {hedge_result['hedge_ratio']:.4f}\n"
        caption += f"📉 R²: {hedge_result['r_squared']:.4f}\n"
        caption += f"📏 Spread: {current_spread:.2f}\n"
        caption += f"📊 Z-Score: {current_z:.2f}\n"
        caption += f"🔗 Correlation: {current_corr:.2f}\n"
        caption += f"🎯 Signal: {signal_text}"
        
        # Send to Telegram with status message
        with st.spinner("📱 Sending to Telegram..."):
            success = send_telegram_document(csv_filepath, caption=caption)
        
        if success:
            st.success("✅ Analytics CSV sent to Telegram successfully!")
            st.info(f"📄 File: {csv_filename} ({file_size/1024:.1f} KB)")
        else:
            st.error("❌ Failed to send CSV to Telegram. Check console for errors.")
        
        # Don't delete immediately - let it persist briefly
        # Temp folder will auto-cleanup eventually
        
        return success
        
    except Exception as e:
        st.error(f"❌ Error preparing analytics CSV: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False

# ============================================
# DATA LOADING CACHED FUNCTION
# ============================================

@st.cache_data(ttl=refresh_rate, show_spinner=False)
def load_analytics_data(symbol1, symbol2, timeframe, lookback, analysis_mode, regression_type):
    """Load paired candle data from database or uploaded table."""
    try:
        df = get_paired_candles(engine, symbol1, symbol2, timeframe, lookback, analysis_mode)
        return df
    except Exception as e:
        return None

# ============================================
# FRAGMENT: DYNAMIC DASHBOARD CONTENT
# ============================================

@st.fragment(run_every="5s")
def display_analytics_dashboard(symbol1, symbol2, timeframe, lookback, zscore_window, entry_threshold, exit_threshold, analysis_mode, regression_type):
    
    # Load data with spinner
    with st.spinner(f"Loading {symbol1}/{symbol2} data..."):
        df = load_analytics_data(symbol1, symbol2, timeframe, lookback, analysis_mode, regression_type)

    # Check if data is available
    if df is None or df.empty or len(df) < 10:
        if analysis_mode == "Uploaded File":
            st.warning("⏳ No data available from the Uploaded File. Please check the 'Upload Data' page.")
        else:
            st.warning(f"⏳ No live data available for {symbol1}/{symbol2}")
            st.info("""
            **Troubleshooting:**
            1. Make sure websocket_test.py is running (collecting ticks)
            2. Make sure build_ohlc.py is running (generating candles)
            3. Wait a few minutes for data to accumulate
            """)
        return

    # ============================================
    # RUN ANALYTICS CALCULATIONS
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
    # PREPARE METRICS FOR ALERT CHECKING
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
    # CHECK AND DISPLAY TRIGGERED ALERTS
    # ============================================
    triggered_alerts = st.session_state.alert_manager.check_alerts(current_metrics)

    if triggered_alerts:
        alert_components.display_triggered_alerts(triggered_alerts)

    # ============================================
    # KEY METRICS DISPLAY
    # ============================================

    st.markdown("### 📈 Key Metrics")
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
    # CHART 1: PRICE COMPARISON
    # ============================================
    st.markdown("### 💹 Price Comparison")
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=df['time'], y=prices1, name=symbol1, line=dict(color='#00ff87', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df['time'], y=prices2, name=symbol2, line=dict(color='#ff3860', width=2)), secondary_y=True)
    fig1.update_layout(height=400, template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#1e2130', hovermode='x unified', showlegend=True, legend=dict(x=0.01, y=0.99))
    fig1.update_yaxes(title_text=f"{symbol1} Price (USDT)", secondary_y=False)
    fig1.update_yaxes(title_text=f"{symbol2} Price (USDT)", secondary_y=True)
    st.plotly_chart(fig1, use_container_width=True)
    st.markdown("---")

    # ============================================
    # CHART 2 & 3: SPREAD & Z-SCORE
    # ============================================
    if spread is not None and zscore is not None and not zscore.dropna().empty:
        st.markdown("### 📊 Spread & Z-Score Analysis")
        
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
    # CHART 4: ROLLING CORRELATION
    # ============================================
    if correlation is not None and not correlation.dropna().empty:
        st.markdown("### 🔗 Rolling Correlation")
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
    # STATISTICS PANEL
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
    # TRADING SIGNALS
    # ============================================
    if signals is not None and zscore is not None and not zscore.dropna().empty:
        st.markdown("### 🎯 Current Trading Signal")
        current_signal = signals.dropna().iloc[-1] if not signals.dropna().empty else 0
        current_z = current_metrics['zscore']
        
        if current_signal == 1:
            st.success(f"""
            ### 🟢 LONG SIGNAL
            **Z-Score:** {current_z:.2f} (Below -{entry_threshold})
            **Recommended Action:** 
            - Buy {symbol1}
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
    # NEW: EXPORT & SHARE ANALYTICS SECTION
    # ============================================
    
    st.markdown("---")
    st.markdown("<div class='export-section'>", unsafe_allow_html=True)
    st.markdown("### 📤 Export Analytics Data")
    st.caption("Download complete analytics with formulas or send to Telegram")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV Download Button
        csv_data = export_analytics_to_csv(df, symbol1, symbol2, timeframe, spread, zscore, correlation, signals, hedge_result)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"{symbol1}_{symbol2}_analytics_{timeframe}_{timestamp}.csv"
        
        st.download_button(
            label="📥 Download Analytics CSV",
            data=csv_data,
            file_name=csv_filename,
            mime="text/csv",
            help="Download complete analytics data with calculation formulas",
            use_container_width=True,
            key=f"download_analytics_{timestamp}"
        )
    
    with col2:
        # Send to Telegram Button (remove timestamp from key to avoid regeneration issues)
        if st.button("📱 Send Analytics to Telegram", type="primary", use_container_width=True, help="Send analytics CSV to your Telegram"):
            send_analytics_csv_to_telegram(df, symbol1, symbol2, timeframe, spread, zscore, correlation, signals, hedge_result, current_metrics)
    
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================
# MAIN EXECUTION CALL
# ============================================

display_analytics_dashboard(
    symbol1, 
    symbol2, 
    timeframe, 
    lookback, 
    zscore_window, 
    entry_threshold, 
    exit_threshold,
    st.session_state.analysis_source,
    regression_type 
)