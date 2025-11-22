import time
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta

# DB Connection
engine = create_engine("postgresql://postgres:kaustubh@localhost:5432/quantdb")

print("=" * 60)
print("🚀 Optimized Incremental Candle Generator")
print("=" * 60)
print("Strategy: Rolling window (last 60 minutes)")
print("Timeframes: 1s, 1m, 5m")
print("Press Ctrl+C to stop\n")

# Configuration
LOOKBACK_MINUTES = 60  # Only process last 60 minutes

def generate_candles():
    """Generate OHLC candles from RECENT ticks only"""
    try:
        # Calculate time window (last 60 minutes)
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=LOOKBACK_MINUTES)
        cutoff_ts = int(cutoff_time.timestamp() * 1000)  # Convert to milliseconds
        
        # Get ONLY recent tick data (optimized query)
        query = f"""
            SELECT ts, symbol, price, size 
            FROM ticks 
            WHERE ts >= {cutoff_ts}
            ORDER BY ts ASC
        """
        
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print("⏳ No recent tick data...")
            return
        
        print(f"📥 Loaded {len(df):,} recent ticks (last {LOOKBACK_MINUTES} min)")
        
        # Convert timestamp to proper datetime
        df['timestamp'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.set_index('timestamp').sort_index()
        
        # Get unique symbols
        symbols = df['symbol'].unique()
        print(f"📊 Processing symbols: {', '.join(symbols)}")
        
        # Generate candles for multiple timeframes
        timeframes = {
            '1S': 'candles_1s',
            '1T': 'candles_1m',
            '5T': 'candles_5m'
        }
        
        for interval, table_name in timeframes.items():
            all_candles = []
            
            # Generate candles per symbol
            for symbol in symbols:
                symbol_df = df[df['symbol'] == symbol].copy()
                
                if symbol_df.empty:
                    continue
                
                # Aggregating into OHLC candles
                ohlc = symbol_df['price'].resample(interval).ohlc()
                volume = symbol_df['size'].resample(interval).sum()
                
                # Combine OHLC + Volume
                candles = ohlc.join(volume)
                candles.rename(columns={'size': 'volume'}, inplace=True)
                candles = candles.dropna()
                
                if not candles.empty:
                    candles = candles.reset_index()
                    candles.rename(columns={'timestamp': 'time'}, inplace=True)
                    candles['symbol'] = symbol
                    all_candles.append(candles)
                    print(f"  ✅ {symbol}: {len(candles)} {interval} candles")
            
            # Combine all symbols
            if all_candles:
                combined = pd.concat(all_candles, ignore_index=True)
                combined = combined.sort_values('time')
                
                # UPSERT logic: Merge with existing data
                try:
                    # Read existing candles
                    existing = pd.read_sql(f"SELECT * FROM {table_name}", engine)
                    
                    if not existing.empty:
                        existing['time'] = pd.to_datetime(existing['time'])
                        
                        # Combine old + new, keep latest for duplicates
                        all_data = pd.concat([existing, combined])
                        all_data = all_data.drop_duplicates(
                            subset=['time', 'symbol'], 
                            keep='last'
                        )
                        all_data = all_data.sort_values('time')
                        
                        # Keep only recent data (to prevent table bloat)
                        recent_cutoff = now - timedelta(hours=24)  # Keep 24 hours
                        all_data = all_data[all_data['time'] >= recent_cutoff]
                        
                        combined = all_data
                        print(f"  🔄 Merged with existing data")
                
                except Exception as e:
                    # Table doesn't exist or is empty, use new data only
                    print(f"  📝 Creating new table")
                
                # Save to database
                combined.to_sql(table_name, engine, if_exists="replace", index=False)
                print(f"💾 Saved {len(combined)} total candles to {table_name}")
        
        print(f"⏰ Update complete: {now.strftime('%H:%M:%S')}")
        print("-" * 60 + "\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

# ---- AUTO-RUN LOOP ----
if __name__ == "__main__":
    print(f"ℹ️  Using {LOOKBACK_MINUTES}-minute rolling window")
    print(f"ℹ️  This prevents processing millions of old ticks\n")
    
    while True:
        generate_candles()
        time.sleep(5)