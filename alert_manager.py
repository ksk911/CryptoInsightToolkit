import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from telegram_sender import send_telegram_message

class Alert:
    """Individual alert configuration"""
    
    def __init__(self, alert_id: str, metric: str, condition: str, 
                 threshold: float, description: str = ""):
        self.alert_id = alert_id
        self.metric = metric  # 'zscore', 'spread', 'correlation', etc.
        self.condition = condition  # '>', '<', '>=', '<='
        self.threshold = threshold
        self.description = description or f"{metric} {condition} {threshold}"
        self.created_at = datetime.now()
        self.triggered_count = 0
        self.last_triggered = None
        self.active = True
    
    def check(self, current_value: float) -> bool:
        """Check if alert condition is met"""
        if not self.active or pd.isna(current_value):
            return False
        
        conditions = {
            '>': current_value > self.threshold,
            '<': current_value < self.threshold,
            '>=': current_value >= self.threshold,
            '<=': current_value <= self.threshold
        }
        
        is_triggered = conditions.get(self.condition, False)
        
        if is_triggered:
            self.triggered_count += 1
            self.last_triggered = datetime.now()
        
        return is_triggered
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for display"""
        return {
            'id': self.alert_id,
            'metric': self.metric,
            'description': self.description,
            'active': self.active,
            'triggers': self.triggered_count,
            'last_triggered': self.last_triggered
        }


class AlertManager:
    """Manages all alerts"""
    
    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
    
    def add_alert(self, alert: Alert) -> bool:
        """Add new alert"""
        self.alerts[alert.alert_id] = alert
        return True
    
    def remove_alert(self, alert_id: str) -> bool:
        """Remove alert"""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            return True
        return False
    
    def get_alerts_by_metric(self, metric: str) -> List[Alert]:
        """Get all active alerts for a specific metric"""
        return [a for a in self.alerts.values() if a.metric == metric and a.active]
    
    def check_alerts(self, current_metrics: Dict[str, float]) -> List[Dict]:
        """
        Check all active alerts against current metrics and send Telegram notifications.
        
        Returns:
            List of triggered alert info dicts
        """
        triggered = []
        
        for alert in self.alerts.values():
            if not alert.active:
                continue
            
            current_value = current_metrics.get(alert.metric)
            
            if current_value is not None and alert.check(current_value):
                
                # --- NEW: TELEGRAM DISPATCH LOGIC ---
                
                # 1. Determine the recommended trading action (crucial for Z-Score signals)
                action_text = ""
                if alert.metric == 'zscore':
                    if current_value > 0: # If Z-Score is positive (spread is high)
                        action_text = "\n🔴 *ACTION: SHORT PAIR* (Sell BTC / Buy ETH Hedge)"
                    else: # If Z-Score is negative (spread is low)
                        action_text = "\n🟢 *ACTION: LONG PAIR* (Buy BTC / Sell ETH Hedge)"
                
                # 2. Build the message content for Telegram
                metric_name = alert.metric.upper().replace("_", " ")
                
                telegram_message = (
                    f"🚨 *TRADING ALERT: {metric_name}*\n"
                    f"Condition: `{metric_name} {alert.condition} {alert.threshold}`\n"
                    f"Current Value: *{current_value:.4f}*\n"
                    f"Time: {alert.last_triggered.strftime('%H:%M:%S')}"
                    f"{action_text}" # Append the action text
                )
                
                # 3. Send the message
                send_telegram_message(telegram_message)
                
                # --- END TELEGRAM DISPATCH LOGIC ---

                # This section remains for the Streamlit dashboard display:
                triggered.append({
                    'id': alert.alert_id,
                    'metric': alert.metric,
                    'description': alert.description,
                    'actual_value': current_value,
                    'threshold': alert.threshold,
                    'condition': alert.condition,
                    'time': alert.last_triggered
                })
        
        return triggered
    
    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts"""
        return list(self.alerts.values())