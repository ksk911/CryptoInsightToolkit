import subprocess
import os
import signal
import time
import sys
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
STREAMLIT_APP_FILE = "Home.py"

BACKGROUND_SCRIPTS = [
    "websocket_test.py",
    "build_ohlc.py"
]

# Database connection for verification
DB_CONNECTION_STRING = "postgresql://postgres:kaustubh@localhost:5432/quantdb"

# --- PROCESS MANAGEMENT ---
background_processes = []

def check_database_ready():
    """Check if database has candle data ready"""
    print("\n[CHECK] Checking database status...")
    
    try:
        engine = create_engine(DB_CONNECTION_STRING)
        with engine.connect() as conn:
            # Check if we have recent candles in 1m table
            result = conn.execute(text("""
                SELECT COUNT(*) as count, MAX(time) as latest
                FROM candles_1m
                WHERE time > NOW() - INTERVAL '5 minutes'
            """))
            row = result.fetchone()
            
            if row and row[0] > 10:
                print(f"[SUCCESS] Database ready: {row[0]} recent candles found")
                print(f"[SUCCESS] Latest candle: {row[1]}")
                return True
            else:
                count = row[0] if row else 0
                print(f"[WAIT] Only {count} recent candles found, need more data...")
                return False
                
    except Exception as e:
        print(f"[WARNING] Database check failed: {e}")
        return False

def launch_background_scripts():
    """Launches data pipeline scripts in non-blocking mode."""
    global background_processes
    python_executable = sys.executable
    
    print("=" * 60)
    print("LAUNCHING BACKGROUND SERVICES...")
    print("=" * 60)

    for script in BACKGROUND_SCRIPTS:
        try:
            # CRITICAL FIX: Remove stdout/stderr pipes to see output
            if os.name == 'nt':  # Windows
                process = subprocess.Popen(
                    [python_executable, script],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:  # Linux/Mac
                process = subprocess.Popen(
                    [python_executable, script],
                    stdout=None,  # Let it print to console
                    stderr=None
                )
            
            background_processes.append(process)
            print(f"[SUCCESS] Started: {script} (PID: {process.pid})")
            time.sleep(1)  # Small delay between launches
            
        except FileNotFoundError:
            print(f"[ERROR] Could not find {script}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Error launching {script}: {e}")
            sys.exit(1)

    print("-" * 60)

def wait_for_data_pipeline():
    """Wait for data pipeline to collect enough data"""
    print("\n[WAIT] Waiting for data pipeline to initialize...")
    print("       This will take 20-30 seconds to collect enough tick data")
    print("       and generate initial candles...")
    
    max_wait = 40  # Maximum wait time in seconds
    check_interval = 5  # Check every 5 seconds
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(check_interval)
        elapsed += check_interval
        
        print(f"\n       -> {elapsed}s elapsed, checking database...")
        
        if check_database_ready():
            print("\n[SUCCESS] Data pipeline ready! Launching dashboard...\n")
            return True
    
    print("\n[WARNING] Timeout waiting for data, but launching dashboard anyway...")
    print("          (Charts may take a few more seconds to populate)")
    return False

def start_streamlit():
    """Starts the Streamlit application in the foreground."""
    print("=" * 60)
    print("STARTING STREAMLIT DASHBOARD")
    print("=" * 60)
    print("   Dashboard will open in your browser automatically")
    print("   Press Ctrl+C in this terminal to stop all services")
    print("=" * 60)
    print()
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", STREAMLIT_APP_FILE], check=True)
    except subprocess.CalledProcessError:
        print("\n[WARNING] Streamlit exited unexpectedly.")
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()

def shutdown():
    """Terminates all running background processes gracefully."""
    print("\n" + "=" * 60)
    print("SHUTTING DOWN ALL SERVICES...")
    print("=" * 60)
    
    for process in background_processes:
        if process.poll() is None:
            try:
                if os.name == 'nt':
                    # Windows: Send Ctrl+C event
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Linux/Mac: Terminate gracefully
                    process.terminate()
                    process.wait(timeout=5)
                
                print(f"  [SUCCESS] Stopped PID {process.pid}")
            except Exception as e:
                print(f"  [WARNING] Could not stop PID {process.pid}: {e}")
    
    print("=" * 60)
    print("[SUCCESS] System shutdown complete")
    print("=" * 60)

if __name__ == "__main__":
    try:
        print("\n" + "=" * 60)
        print("     CRYPTO TRADING SYSTEM LAUNCHER")
        print("=" * 60)
        print()
        
        # Step 1: Launch background services
        launch_background_scripts()
        
        # Step 2: Wait for data pipeline to be ready
        wait_for_data_pipeline()
        
        # Step 3: Start Streamlit dashboard
        start_streamlit()
        
    except KeyboardInterrupt:
        print("\n\n[WARNING] Interrupted by user")
        shutdown()
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        shutdown()
        sys.exit(1)