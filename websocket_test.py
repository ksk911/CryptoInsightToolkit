import json
import threading
import websocket
from sqlalchemy import create_engine, text

# ---- DB CONNECTION ----
# Ensure this connection string is correct for your system
engine = create_engine("postgresql://postgres:kaustubh@localhost:5432/quantdb")

# ---- CONFIGURATION ----
SYMBOLS = ["btcusdt", "ethusdt"]  # Multiple symbols for pairs trading

class MultiSymbolCollector:
    def __init__(self, symbols):
        self.symbols = symbols
        self.websockets = []
        
    # --- UPDATED save_to_db: Accepts validated price/size parameters ---
    def save_to_db(self, data, price, size):
        """Save validated tick to database"""
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO ticks (ts, symbol, price, size)
                        VALUES (:ts, :symbol, :price, :size)
                    """),
                    {
                        "ts": data["T"],
                        "symbol": data["s"],
                        "price": price,   # Use the validated price
                        "size": size      # Use the validated size
                    }
                )
                conn.commit()
        except Exception as e:
            print(f"❌ DB Insert Error: {e}")

    # --- UPDATED on_message: Includes CRITICAL VALIDATION FILTER ---
    def on_message(self, ws, message):
        """Handle incoming WebSocket message with price validation"""
        try:
            data = json.loads(message)
            
            # 1. Safely extract price and size, defaulting to 0 if keys 'p' or 'q' are missing
            price = float(data.get("p", 0))
            size = float(data.get("q", 0))
            
            # 2. Define minimum price threshold. BTC/ETH should never be below this.
            # We use 1000 as a safe, generous floor for major cryptos.
            MIN_PRICE_THRESHOLD = 1000 
            
            # 3. APPLY THE FILTER: Drop the tick if price is too low or size is zero/negative.
            if price < MIN_PRICE_THRESHOLD or size <= 0:
                print(f"❌ REJECTED BAD TICK for {data['s']}: Price={price:,.2f}, Size={size:.4f}")
                return # EXIT the function without saving the bad tick
            
            # 4. If validation passes, proceed to print and save
            print(f"✅ {data['s']:<10} @ ${price:>10,.2f}  |  Size: {size:>8.4f}")
            self.save_to_db(data, price, size)
            
        except Exception as e:
            # This catches errors in json.loads or other unexpected exceptions
            print(f"❌ Message/Parsing Error: {e}")

    def on_open(self, ws):
        print(f"🔗 WebSocket Connected!")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"❌ WebSocket Closed")

    def on_error(self, ws, error):
        print(f"⚠️ WebSocket Error: {error}")

    def start_websocket(self, symbol):
        """Start WebSocket for a symbol"""
        url = f"wss://fstream.binance.com/ws/{symbol}@trade"
        
        ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Run in separate thread
        def run():
            print(f"📡 Connecting to {symbol.upper()}...")
            ws.run_forever()
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.websockets.append(ws)

    def run(self):
        """Start collecting data for all symbols"""
        print("=" * 60)
        print("🚀 Multi-Symbol WebSocket Collector")
        print("=" * 60)
        print(f"Symbols: {', '.join([s.upper() for s in self.symbols])}")
        print("Press Ctrl+C to stop\n")
        
        # Start WebSocket for each symbol
        for symbol in self.symbols:
            self.start_websocket(symbol)
        
        # Keep main thread alive
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping collector...")
            for ws in self.websockets:
                ws.close()

if __name__ == "__main__":
    collector = MultiSymbolCollector(SYMBOLS)
    collector.run()