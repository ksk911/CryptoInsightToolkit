import time
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# Import analytics module (from root level)
from analytics import PairsAnalytics, get_paired_candles

# ---- Page Config ----
st.set_page_config(
    page_title="Pairs Analytics",
    page_icon="📊",
    layout="wide"
)

# ---- Custom CSS ----
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
</style>
""", unsafe_allow_html=True)

# ---- Connect to PostgreSQL ----
engine = create_engine("postgresql://postgres:kaustubh@localhost:5432/quantdb")

# ---- Initialize Analytics ----
analytics = PairsAnalytics()

# ---- Header ----
st.title("📊 Pairs Trading Analytics")
st.caption("Statistical arbitrage and mean-reversion analysis")

# ---- Sidebar Controls ----
with st.sidebar:
    st.header("⚙️ Analytics Settings")
    
    st.subheader("Symbol Pair")
    symbol1 = st.selectbox("Asset 1", ["BTCUSDT", "ETHUSDT"], index=0)
    symbol2 = st.selectbox("Asset 2", ["BTCUSDT", "ETHUSDT"], index=1)
    
    if symbol1 == symbol2:
        st.error("Select different symbols!")
        st.stop()
    
    timeframe = st.selectbox("Timeframe", ["1s", "1m", "5m"], index=1)
    
    st.subheader("Parameters")
    lookback = st.slider("Lookback Period", 20, 200, 100)
    zscore_window = st.slider("Z-Score Window", 10, 50, 20)
    
    st.subheader("Trading Thresholds")
    entry_threshold = st.slider("Entry Z-Score", 1.0, 3.0, 2.0, 0.1)
    exit_threshold = st.slider("Exit Z-Score", 0.0, 1.5, 0.5, 0.1)
    
    refresh_rate = st.slider("Refresh (seconds)", 3, 15, 5)
    
    st.markdown("---")
    st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

# ---- Load Data ----
@st.cache_data(ttl=refresh_rate)
def load_analytics_data(symbol1, symbol2, timeframe, lookback):
    df = get_paired_candles(engine, symbol1, symbol2, timeframe, lookback)
    return df

df = load_analytics_data(symbol1, symbol2, timeframe, lookback)

if df is None or df.empty or len(df) < 10:
    st.warning(f"⏳ Waiting for {symbol1}/{symbol2} data...")
    st.info("Make sure websocket_test.py and build_ohlc.py are running")
    st.stop()

# Extract prices
prices1 = df[f'price_{symbol1.lower()}']
prices2 = df[f'price_{symbol2.lower()}']

# Run analytics
hedge_result = analytics.calculate_hedge_ratio(prices1, prices2)
spread = analytics.calculate_spread(prices1, prices2, hedge_result['hedge_ratio']) if hedge_result else None
zscore = analytics.calculate_zscore(spread, window=zscore_window) if spread is not None else None
adf_result = analytics.run_adf_test(spread) if spread is not None else None
correlation = analytics.calculate_rolling_correlation(prices1, prices2, window=zscore_window)
signals = analytics.generate_trading_signals(zscore, entry_threshold, exit_threshold) if zscore is not None else None

# ---- Metrics ----
st.markdown("### 📈 Key Metrics")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if hedge_result:
        st.metric("Hedge Ratio (β)", f"{hedge_result['hedge_ratio']:.4f}")
    else:
        st.metric("Hedge Ratio", "N/A")

with col2:
    if hedge_result:
        st.metric("R² (Fit Quality)", f"{hedge_result['r_squared']:.4f}")
    else:
        st.metric("R²", "N/A")

with col3:
    if zscore is not None:
        st.metric("Current Z-Score", f"{zscore.iloc[-1]:.2f}")
    else:
        st.metric("Z-Score", "N/A")

with col4:
    if adf_result:
        st.metric("Stationarity", adf_result['interpretation'], f"p={adf_result['p_value']:.4f}")
    else:
        st.metric("Stationarity", "N/A")

st.markdown("---")

# ---- Price Comparison Chart ----
st.markdown("### 💹 Price Comparison")
fig1 = make_subplots(specs=[[{"secondary_y": True}]])
fig1.add_trace(
    go.Scatter(x=df['time'], y=prices1, name=symbol1, line=dict(color='#00ff87', width=2)),
    secondary_y=False
)
fig1.add_trace(
    go.Scatter(x=df['time'], y=prices2, name=symbol2, line=dict(color='#ff3860', width=2)),
    secondary_y=True
)
fig1.update_layout(
    height=400,
    template='plotly_dark',
    paper_bgcolor='#0e1117',
    plot_bgcolor='#1e2130',
    hovermode='x unified',
    showlegend=True
)
fig1.update_yaxes(title_text=f"{symbol1} Price", secondary_y=False)
fig1.update_yaxes(title_text=f"{symbol2} Price", secondary_y=True)
st.plotly_chart(fig1, use_container_width=True)

# ---- Spread & Z-Score ----
if spread is not None and zscore is not None:
    st.markdown("### 📊 Spread Analysis")
    
    fig2 = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.5, 0.5],
        subplot_titles=('Spread', 'Z-Score')
    )
    
    fig2.add_trace(
        go.Scatter(x=df['time'], y=spread, name='Spread', line=dict(color='#3b82f6', width=2)),
        row=1, col=1
    )
    fig2.add_hline(y=spread.mean(), line_dash="dash", line_color="gray", row=1, col=1)
    
    fig2.add_trace(
        go.Scatter(x=df['time'], y=zscore, name='Z-Score', line=dict(color='#fbbf24', width=2)),
        row=2, col=1
    )
    fig2.add_hline(y=entry_threshold, line_dash="dash", line_color="red", row=2, col=1)
    fig2.add_hline(y=-entry_threshold, line_dash="dash", line_color="green", row=2, col=1)
    fig2.add_hline(y=exit_threshold, line_dash="dot", line_color="gray", row=2, col=1)
    fig2.add_hline(y=-exit_threshold, line_dash="dot", line_color="gray", row=2, col=1)
    fig2.add_hline(y=0, line_color="white", line_width=1, row=2, col=1)
    
    fig2.update_layout(
        height=600,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#1e2130',
        hovermode='x unified',
        showlegend=False
    )
    
    st.plotly_chart(fig2, use_container_width=True)

# ---- Rolling Correlation ----
if correlation is not None:
    st.markdown("### 🔗 Rolling Correlation")
    
    fig3 = go.Figure()
    fig3.add_trace(
        go.Scatter(x=df['time'], y=correlation, name='Correlation', 
                  fill='tozeroy', line=dict(color='#8b5cf6', width=2))
    )
    fig3.add_hline(y=0.7, line_dash="dash", line_color="green", annotation_text="Strong")
    fig3.add_hline(y=0, line_color="white", line_width=1)
    
    fig3.update_layout(
        height=300,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#1e2130',
        hovermode='x',
        yaxis_range=[-1, 1]
    )
    
    st.plotly_chart(fig3, use_container_width=True)

# ---- Statistics Panel ----
st.markdown("---")
st.markdown("### 📋 Detailed Statistics")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### OLS Regression Results")
    if hedge_result:
        st.json({
            "Hedge Ratio (β)": f"{hedge_result['hedge_ratio']:.6f}",
            "Intercept (α)": f"{hedge_result['alpha']:.2f}",
            "R-Squared": f"{hedge_result['r_squared']:.6f}",
            "P-Value": f"{hedge_result['p_value']:.6e}",
            "Model Fit": "Excellent" if hedge_result['r_squared'] > 0.8 else "Good" if hedge_result['r_squared'] > 0.6 else "Moderate"
        })
    else:
        st.info("Insufficient data")

with col2:
    st.markdown("#### ADF Stationarity Test")
    if adf_result:
        st.json({
            "Test Statistic": f"{adf_result['adf_statistic']:.4f}",
            "P-Value": f"{adf_result['p_value']:.6f}",
            "Result": adf_result['interpretation'],
            "Tradeable": "✅ Yes" if adf_result['is_stationary'] else "❌ No",
            "Confidence": "High (p<0.01)" if adf_result['p_value'] < 0.01 else "Moderate (p<0.05)" if adf_result['p_value'] < 0.05 else "Low"
        })
    else:
        st.info("Insufficient data")

# ---- Trading Signals ----
if signals is not None:
    st.markdown("---")
    st.markdown("### 🎯 Current Trading Signal")
    
    current_signal = signals.iloc[-1]
    current_z = zscore.iloc[-1]
    
    if current_signal == 1:
        st.success(f"""
        ### 🟢 LONG SIGNAL
        **Z-Score:** {current_z:.2f} (Below -{entry_threshold})
        
        **Action:** 
        - Buy {symbol1}
        - Sell {hedge_result['hedge_ratio']:.4f} units of {symbol2}
        
        **Rationale:** Spread is abnormally low, expecting mean reversion
        """)
    elif current_signal == -1:
        st.error(f"""
        ### 🔴 SHORT SIGNAL
        **Z-Score:** {current_z:.2f} (Above +{entry_threshold})
        
        **Action:**
        - Sell {symbol1}
        - Buy {hedge_result['hedge_ratio']:.4f} units of {symbol2}
        
        **Rationale:** Spread is abnormally high, expecting mean reversion
        """)
    else:
        st.info(f"""
        ### ⚪ NEUTRAL / EXIT
        **Z-Score:** {current_z:.2f} (Between ±{exit_threshold})
        
        **Action:** No trade / Close existing positions
        
        **Rationale:** Spread near mean, no clear opportunity
        """)

# ---- Auto Refresh ----
time.sleep(refresh_rate)
st.rerun()