import streamlit as st
import uuid
from datetime import datetime
from typing import List, Dict
from alert_manager import Alert

def render_alert_button(metric: str, default_threshold: float = 2.0, 
                       step: float = 0.1, key_suffix: str = ""):
    """
    Render alert creation button below a chart
    
    Args:
        metric: Metric name ('zscore', 'spread', 'correlation')
        default_threshold: Default threshold value
        step: Step size for number input
        key_suffix: Unique suffix for widget keys
    """
    
    # Metric display names
    metric_names = {
        'zscore': '📊 Z-Score',
        'spread': '📈 Spread',
        'correlation': '🔗 Correlation',
        'hedge_ratio': '⚖️ Hedge Ratio',
        'r_squared': '📉 R-Squared'
    }
    
    st.markdown(f"#### 🔔 Set Alert for {metric_names.get(metric, metric.title())}")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        st.markdown(f"**{metric_names.get(metric, metric.title())} Alert**")
    
    with col2:
        condition = st.selectbox(
            "Condition",
            [">", "<", ">=", "<="],
            key=f"alert_cond_{metric}_{key_suffix}"
        )
    
    with col3:
        threshold = st.number_input(
            "Threshold",
            value=default_threshold,
            step=step,
            format=f"%.{len(str(step).split('.')[-1])}f",
            key=f"alert_thresh_{metric}_{key_suffix}"
        )
    
    with col4:
        if st.button("➕ Add Alert", type="primary", key=f"add_alert_{metric}_{key_suffix}"):
            # Initialize alert manager in session state if not exists
            if 'alert_manager' not in st.session_state:
                from alert_manager import AlertManager
                st.session_state.alert_manager = AlertManager()
            
            # Create new alert
            alert_id = str(uuid.uuid4())[:8]
            description = f"{metric.upper()} {condition} {threshold}"
            
            new_alert = Alert(
                alert_id=alert_id,
                metric=metric,
                condition=condition,
                threshold=threshold,
                description=description
            )
            
            st.session_state.alert_manager.add_alert(new_alert)
            st.success(f"✅ Alert added: {description}")
            st.rerun()
    
    # Display active alerts for this metric
    if 'alert_manager' in st.session_state:
        active_alerts = st.session_state.alert_manager.get_alerts_by_metric(metric)
        
        if active_alerts:
            st.markdown("**Active Alerts:**")
            for alert in active_alerts:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(
                        f"<div style='background-color: #26a69a; color: white; padding: 8px 12px; "
                        f"border-radius: 5px; margin: 5px 0; display: inline-block;'>"
                        f"🟢 {alert.description}</div>",
                        unsafe_allow_html=True
                    )
                with col2:
                    if st.button("Remove", key=f"remove_{alert.alert_id}_{key_suffix}"):
                        st.session_state.alert_manager.remove_alert(alert.alert_id)
                        st.rerun()


def display_triggered_alerts(triggered_alerts: List[Dict]):
    """
    Display triggered alerts with animation
    
    Args:
        triggered_alerts: List of triggered alert info dicts
    """
    if not triggered_alerts:
        return
    
    st.markdown("### 🚨 TRIGGERED ALERTS")
    
    for alert in triggered_alerts:
        st.markdown(f"""
        <div style='
            background: linear-gradient(135deg, #ff3860 0%, #ff6b9d 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            font-weight: bold;
            animation: pulse 2s infinite;
        '>
            🚨 <strong>ALERT:</strong> {alert['description']}<br>
            📊 <strong>Current Value:</strong> {alert['actual_value']:.4f}<br>
            🎯 <strong>Threshold:</strong> {alert['condition']} {alert['threshold']}<br>
            🕐 <strong>Time:</strong> {alert['time'].strftime('%H:%M:%S') if alert['time'] else 'Just now'}
        </div>
        <style>
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.8; }}
            }}
        </style>
        """, unsafe_allow_html=True)


def show_alert_summary_sidebar():
    """Display alert count in sidebar"""
    if 'alert_manager' not in st.session_state:
        return
    
    all_alerts = st.session_state.alert_manager.get_all_alerts()
    active_count = sum(1 for a in all_alerts if a.active)
    
    st.sidebar.markdown("---")
    if active_count > 0:
        st.sidebar.success(f"🔔 {active_count} active alert(s)")
    else:
        st.sidebar.info("🔕 No active alerts")