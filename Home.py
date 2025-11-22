import time
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ---- Page Config ----
st.set_page_config(
    page_title="Crypto Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
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

# ---- Header ----
st.title("📈 Live Price Charts")
st.caption("Real-time cryptocurrency price monitoring")

# ---- Sidebar Controls ----
with st.sidebar:
    st.header("⚙️ Chart Settings")
    
    symbol = st.selectbox(
        "Select Symbol",
        ["BTCUSDT", "ETHUSDT"],
        index=0,
        help="Choose trading pair"
    )
    
    timeframe = st.selectbox(
        "Timeframe",
        ["1s", "1m", "5m"],
        index=1,
        help="Select candle timeframe"
    )
    
    num_candles = st.slider(
        "Candles to Display", 
        min_value=20, 
        max_value=200, 
        value=60,
        help="Number of candles to show"
    )
    
    refresh_rate = st.slider(
        "Refresh Rate (seconds)", 
        min_value=2, 
        max_value=10, 
        value=3
    )
    
    chart_type = st.selectbox(
        "Chart Type",
        ["Candlestick", "Line", "OHLC"]
    )
    
    show_volume = st.checkbox("Show Volume", value=True)
    
    st.markdown("---")
    st.info("💡 Use sidebar to switch to **Analytics** for pairs trading!")
    st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

# ---- Main Content ----
placeholder = st.empty()

def calculate_metrics(df):
    """Calculate trading metrics"""
    if df.empty or len(df) < 2:
        return None, None, None, None
    
    current_price = df['close'].iloc[-1]
    previous_price = df['close'].iloc[0]
    price_change = current_price - previous_price
    price_change_pct = (price_change / previous_price) * 100
    total_volume = df['volume'].sum()
    
    return current_price, price_change, price_change_pct, total_volume

@st.cache_data(ttl=refresh_rate)
def load_data(symbol, timeframe, num_candles):
    """Load candle data from database"""
    table_name = f"candles_{timeframe}"
    
    try:
        query = f"""
            SELECT * FROM {table_name} 
            WHERE symbol = '{symbol}'
            ORDER BY time DESC 
            LIMIT {num_candles * 2}
        """
        df = pd.read_sql(query, engine)
        
        if df.empty:
            return None
            
        df = df.sort_values("time").tail(num_candles)
        df['time'] = pd.to_datetime(df['time'])
        return df
        
    except Exception as e:
        return None

def load_and_plot():
    """Load data and create dashboard"""
    
    df = load_data(symbol, timeframe, num_candles)
    
    if df is None or df.empty:
        st.warning(f"⏳ Waiting for {symbol} candle data...")
        st.info(f"""
        **Make sure these are running:**
        
        **Terminal 1:** `python websocket_test.py`
        
        **Terminal 2:** `python build_ohlc.py`
        
        **Current:** {symbol} @ {timeframe} timeframe
        """)
        return
    
    current_price, price_change, price_change_pct, total_volume = calculate_metrics(df)
    
    with placeholder.container():
        # ---- Metrics Row ----
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label=f"💰 {symbol} Price",
                value=f"${current_price:,.2f}",
                delta=f"{price_change:+.2f} ({price_change_pct:+.2f}%)"
            )
        
        with col2:
            st.metric("📈 High", f"${df['high'].max():,.2f}")
        
        with col3:
            st.metric("📉 Low", f"${df['low'].min():,.2f}")
        
        with col4:
            st.metric("📊 Volume", f"{total_volume:.4f}")
        
        st.markdown("---")
        
        # ---- Create Chart ----
        if show_volume:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3],
                subplot_titles=(f'{symbol} Price', 'Volume')
            )
        else:
            fig = go.Figure()
        
        # Price Chart
        if chart_type == "Candlestick":
            candlestick = go.Candlestick(
                x=df['time'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name=symbol,
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350',
                increasing_fillcolor='#26a69a',
                decreasing_fillcolor='#ef5350',
                line=dict(width=1)
            )
            
            if show_volume:
                fig.add_trace(candlestick, row=1, col=1)
            else:
                fig = go.Figure(data=[candlestick])
                
        elif chart_type == "Line":
            line = go.Scatter(
                x=df['time'],
                y=df['close'],
                mode='lines',
                name='Close Price',
                line=dict(color='#00ff87', width=2)
            )
            
            if show_volume:
                fig.add_trace(line, row=1, col=1)
            else:
                fig = go.Figure(data=[line])
                
        else:  # OHLC
            ohlc = go.Ohlc(
                x=df['time'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name=symbol,
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            )
            
            if show_volume:
                fig.add_trace(ohlc, row=1, col=1)
            else:
                fig = go.Figure(data=[ohlc])
        
        # Volume bars
        if show_volume:
            colors = ['#26a69a' if row['close'] >= row['open'] else '#ef5350' 
                     for idx, row in df.iterrows()]
            
            volume_bars = go.Bar(
                x=df['time'],
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                opacity=0.7
            )
            fig.add_trace(volume_bars, row=2, col=1)
        
        # Layout styling
        fig.update_layout(
            height=700,
            template='plotly_dark',
            paper_bgcolor='#0e1117',
            plot_bgcolor='#1e2130',
            font=dict(color='#e0e0e0', size=12),
            xaxis_rangeslider_visible=False,
            showlegend=False,
            margin=dict(t=50, b=50, l=50, r=50),
            hovermode='x unified'
        )
        
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#2e3241')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#2e3241')
        
        if show_volume:
            fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # ---- Stats Table ----
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Statistics")
            stats_df = pd.DataFrame({
                'Metric': ['Open', 'Close', 'High', 'Low', 'Range'],
                'Value': [
                    f"${df['open'].iloc[0]:,.2f}",
                    f"${df['close'].iloc[-1]:,.2f}",
                    f"${df['high'].max():,.2f}",
                    f"${df['low'].min():,.2f}",
                    f"${df['high'].max() - df['low'].min():,.2f}"
                ]
            })
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("### ⏱️ Time Info")
            time_df = pd.DataFrame({
                'Info': ['Start Time', 'End Time', 'Candles', 'Timeframe'],
                'Value': [
                    df['time'].iloc[0].strftime('%H:%M:%S'),
                    df['time'].iloc[-1].strftime('%H:%M:%S'),
                    len(df),
                    timeframe.upper()
                ]
            })
            st.dataframe(time_df, use_container_width=True, hide_index=True)

# ---- Auto-refresh ----
load_and_plot()
time.sleep(refresh_rate)
st.rerun()