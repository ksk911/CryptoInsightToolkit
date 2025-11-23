import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.stattools import adfuller

# --- CONFIGURATION FOR UPLOAD ---
UPLOAD_TABLE_NAME = "user_uploaded_ohlc" 
# --- END CONFIGURATION ---

class PairsAnalytics:
    """Statistical analytics for pairs trading strategies"""
    
    def __init__(self):
        self.results = {}
    
    def calculate_hedge_ratio(self, prices1, prices2):
        """
        Calculate optimal hedge ratio using OLS regression
        Model: price1 = alpha + beta * price2 + error
        """
        try:
            df = pd.DataFrame({'y': prices1, 'x': prices2}).dropna()
            
            if len(df) < 10:
                return None
            
            X = add_constant(df['x'])
            y = df['y']
            model = OLS(y, X).fit()
            
            return {
                'hedge_ratio': model.params['x'],
                'alpha': model.params['const'],
                'r_squared': model.rsquared,
                'p_value': model.pvalues['x'],
                'model': model
            }
        except Exception as e:
            print(f"Error calculating hedge ratio: {e}")
            return None
    
    def calculate_spread(self, prices1, prices2, hedge_ratio):
        """Calculate spread = price1 - hedge_ratio * price2"""
        try:
            df = pd.DataFrame({'p1': prices1, 'p2': prices2}).dropna()
            spread = df['p1'] - hedge_ratio * df['p2']
            return spread
        except Exception as e:
            print(f"Error calculating spread: {e}")
            return None
    
    def calculate_zscore(self, series, window=20):
        """Calculate rolling z-score"""
        try:
            rolling_mean = series.rolling(window=window).mean()
            rolling_std = series.rolling(window=window).std()
            zscore = (series - rolling_mean) / rolling_std
            return zscore
        except Exception as e:
            print(f"Error calculating z-score: {e}")
            return None
    
    def run_adf_test(self, series):
        """Augmented Dickey-Fuller test for stationarity"""
        try:
            clean_series = series.dropna()
            
            if len(clean_series) < 10:
                return None
            
            result = adfuller(clean_series, autolag='AIC')
            
            return {
                'adf_statistic': result[0],
                'p_value': result[1],
                'critical_values': result[4],
                'is_stationary': result[1] < 0.05,
                'interpretation': 'Stationary' if result[1] < 0.05 else 'Non-stationary'
            }
        except Exception as e:
            print(f"Error running ADF test: {e}")
            return None
    
    def calculate_rolling_correlation(self, prices1, prices2, window=20):
        """Calculate rolling correlation"""
        try:
            df = pd.DataFrame({'p1': prices1, 'p2': prices2}).dropna()
            correlation = df['p1'].rolling(window=window).corr(df['p2'])
            return correlation
        except Exception as e:
            print(f"Error calculating correlation: {e}")
            return None
    
    def generate_trading_signals(self, zscore, entry_threshold=2.0, exit_threshold=0.5):
        """Generate trading signals based on z-score"""
        try:
            signals = pd.Series(0, index=zscore.index)
            signals[zscore > entry_threshold] = -1  # SHORT
            signals[zscore < -entry_threshold] = 1  # LONG
            signals[abs(zscore) < exit_threshold] = 0  # EXIT
            return signals
        except Exception as e:
            print(f"Error generating signals: {e}")
            return None


def get_paired_candles(engine, symbol1, symbol2, timeframe='1m', limit=100, analysis_mode="Live Candles (DB)"): # <--- MODIFIED: ADDED analysis_mode
    """Load and align candle data for two symbols, supporting uploaded data source."""
    
    if analysis_mode == "Uploaded File":
        try:
            # --- NEW LOGIC: Load from the temporary UPLOADED table ---
            
            # Load ALL data from the temporary uploaded table
            query = f"""
                SELECT time, close
                FROM {UPLOAD_TABLE_NAME}
                ORDER BY time ASC
            """
            df_uploaded = pd.read_sql(query, engine)
            df_uploaded['time'] = pd.to_datetime(df_uploaded['time'])
            
            # For pairs analysis, we need two series. We use the single 'close' column
            # from the uploaded file for BOTH symbols (a testing simplification).
            df_uploaded[f'price_{symbol1.lower()}'] = df_uploaded['close']
            df_uploaded[f'price_{symbol2.lower()}'] = df_uploaded['close'] 
            
            # Limit the size (lookback) and return
            df = df_uploaded.tail(limit).sort_values('time').reset_index(drop=True)
            
            # Check for minimum data length
            if len(df) < 10:
                print(f"Warning: Uploaded data only contains {len(df)} rows.")
                return None
                
            return df
            
        except Exception as e:
            print(f"Error loading uploaded data from {UPLOAD_TABLE_NAME}: {e}")
            return None
    
    else: # analysis_mode == "Live Candles (DB)" (Existing logic remains the default)
        try:
            table_name = f"candles_{timeframe}"
            
            # Load symbol1
            query1 = f"""
                SELECT time, close as price_{symbol1.lower()}
                FROM {table_name}
                WHERE symbol = '{symbol1}'
                ORDER BY time DESC
                LIMIT {limit}
            """
            df1 = pd.read_sql(query1, engine)
            df1['time'] = pd.to_datetime(df1['time'])
            
            # Load symbol2
            query2 = f"""
                SELECT time, close as price_{symbol2.lower()}
                FROM {table_name}
                WHERE symbol = '{symbol2}'
                ORDER BY time DESC
                LIMIT {limit}
            """
            df2 = pd.read_sql(query2, engine)
            df2['time'] = pd.to_datetime(df2['time'])
            
            # Merge
            df = pd.merge(df1, df2, on='time', how='inner')
            df = df.sort_values('time').reset_index(drop=True)
            
            return df
        except Exception as e:
            print(f"Error loading paired candles: {e}")
            return None