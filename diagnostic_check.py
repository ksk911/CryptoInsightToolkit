import pandas as pd
from sqlalchemy import create_engine, inspect

engine = create_engine("postgresql://postgres:kaustubh@localhost:5432/quantdb")

print("=" * 60)
print("🔍 DATABASE DIAGNOSTIC CHECK")
print("=" * 60)

# Check what tables exist
inspector = inspect(engine)
tables = inspector.get_table_names()

print("\n📋 TABLES IN DATABASE:")
for table in tables:
    print(f"  ✅ {table}")

if not tables:
    print("  ❌ No tables found! Database is empty.")
    print("\n💡 Make sure websocket_test.py is running to collect data.")
    exit()

print("\n" + "=" * 60)

# Check ticks table
if 'ticks' in tables:
    print("\n📊 TICKS TABLE:")
    try:
        tick_count = pd.read_sql("SELECT COUNT(*) as count FROM ticks", engine)
        print(f"  Total ticks: {tick_count['count'].iloc[0]:,}")
        
        symbols = pd.read_sql("SELECT DISTINCT symbol FROM ticks", engine)
        print(f"  Symbols: {', '.join(symbols['symbol'].tolist())}")
        
        recent = pd.read_sql(
            "SELECT symbol, price, ts FROM ticks ORDER BY ts DESC LIMIT 5", 
            engine
        )
        print("\n  Recent ticks:")
        for _, row in recent.iterrows():
            print(f"    {row['symbol']:<10} @ ${row['price']:>10,.2f}")
    except Exception as e:
        print(f"  ❌ Error reading ticks: {e}")
else:
    print("\n❌ 'ticks' table not found!")
    print("   Run websocket_test.py to start collecting data.")

print("\n" + "=" * 60)

# Check candle tables
candle_tables = ['candles_1s', 'candles_1m', 'candles_5m']

for table in candle_tables:
    if table in tables:
        print(f"\n📈 {table.upper()} TABLE:")
        try:
            count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table}", engine)
            print(f"  Total candles: {count['count'].iloc[0]:,}")
            
            symbols = pd.read_sql(f"SELECT DISTINCT symbol FROM {table}", engine)
            print(f"  Symbols: {', '.join(symbols['symbol'].tolist())}")
            
            recent = pd.read_sql(
                f"SELECT symbol, time, close, volume FROM {table} ORDER BY time DESC LIMIT 3", 
                engine
            )
            print(f"\n  Recent candles:")
            for _, row in recent.iterrows():
                time_str = pd.to_datetime(row['time']).strftime('%H:%M:%S')
                print(f"    {row['symbol']:<10} {time_str}  ${row['close']:>10,.2f}  Vol: {row['volume']:.4f}")
        except Exception as e:
            print(f"  ❌ Error reading {table}: {e}")
    else:
        print(f"\n❌ '{table}' table not found!")
        print(f"   Run build_ohlc.py to generate candles.")

print("\n" + "=" * 60)
print("\n✅ DIAGNOSTIC COMPLETE")
print("\n📌 WHAT TO DO NEXT:")
print("  1. If 'ticks' table is empty → Start websocket_test.py")
print("  2. If candle tables missing → Start build_ohlc.py")
print("  3. If everything has data → Check Streamlit dashboard")
print("=" * 60)
