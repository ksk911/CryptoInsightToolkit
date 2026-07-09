import time
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta

# DB Connection
engine = create_engine("postgresql://postgres:kaustubh@localhost:5432/quantdb")

print("=" * 60)
print("🚀 Optimized Incremental Candle Generator")
print("=" * 60)
# Updated strategy description to reflect the new dynamic gap-filling:
print("Strategy: Dynamic Gap-Filling (from last candle)") 
print("Timeframes: 1s, 1m, 5m")
print("Press Ctrl+C to stop\n")

def generate_candles():
    """Generate OHLC candles from UNPROCESSED ticks since the last saved candle."""
    try:
        now = datetime.now()
        
        # --- NEW LOGIC: DETERMINE START TIME ---
        
        # 1. Default start time: 60 minutes ago (safe fallback if tables are empty)
        earliest_process_time = now - timedelta(minutes=60)
        
        # 2. Find the MAX(time) from the most frequently updated table (candles_1m)
        try:
            # We look up the latest time to ensure we don't reprocess any existing candles.
            latest_candle = pd.read_sql(
                f"SELECT MAX(time) as max_time FROM candles_1m", 
                engine
            )['max_time'].iloc[0]
            
            if latest_candle is not None:
                # Convert to datetime and add a small buffer (1 second) to avoid duplicate processing
                latest_time = pd.to_datetime(latest_candle).to_pydatetime()
                
                # Update the processing start time (do not go back further than 60 mins to prevent memory issues)
                earliest_process_time = max(now - timedelta(minutes=60), latest_time + timedelta(seconds=1))
            
        except Exception:
            # Ignore errors if the table doesn't exist or is empty (use default 60 min lookback)
            pass

        # Convert to milliseconds for the tick query
        cutoff_ts = int(earliest_process_time.timestamp() * 1000)
        
        # --- END NEW LOGIC ---
        
        # Get ALL tick data since the earliest required processing time (optimized query)
        query = f"""
            SELECT ts, symbol, price, size 
            FROM ticks 
            WHERE ts >= {cutoff_ts}
            ORDER BY ts ASC
        """
        
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print(f"⏳ No new ticks since {earliest_process_time.strftime('%H:%M:%S')}")
            return
        
        # The number of loaded ticks will now be variable, covering any gap
        print(f"📥 Loaded {len(df):,} new ticks starting from {earliest_process_time.strftime('%H:%M:%S')}")
        
        # Convert timestamp to proper datetime
        df['timestamp'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.set_index('timestamp').sort_index()
        
        # Get unique symbols
        symbols = df['symbol'].unique()
        print(f"📊 Processing symbols: {', '.join(symbols)}")
        
        # Generate candles for multiple timeframes
        timeframes = {
            '1s': 'candles_1s',
            '1min': 'candles_1m',
            '5min': 'candles_5m'
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
                candles = candles.dropna() # Still drops candles with zero volume/price (correct behavior)
                
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
                        
                        # Keep only recent data (7 days retention)
                        recent_cutoff = now - timedelta(days=7)
                        all_data = all_data[all_data['time'] >= recent_cutoff]
                        
                        combined = all_data
                        print(f"  🔄 Merged with existing data")
                
                except Exception:
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
    print(f"ℹ️  Starting full pipeline generator...")
    print(f"ℹ️  This will now fill historical gaps automatically.")
    
    while True:
        generate_candles()
        time.sleep(5)