import subprocess
import os
import signal
import time
import sys

# --- CONFIGURATION ---
# Path to the main Streamlit file
STREAMLIT_APP_FILE = "Home.py"

# Scripts to run in the background (data pipeline)
BACKGROUND_SCRIPTS = [
    "websocket_test.py",
    "build_ohlc.py"
]

# --- PROCESS MANAGEMENT ---
background_processes = []

def launch_background_scripts():
    """Launches data pipeline scripts in non-blocking mode."""
    global background_processes
    python_executable = sys.executable # Guarantees correct Python environment
    
    print("=" * 60)
    print("🚀 LAUNCHING BACKGROUND SERVICES...")
    print("=" * 60)

    for script in BACKGROUND_SCRIPTS:
        try:
            # Popen starts the process asynchronously
            process = subprocess.Popen([python_executable, script], 
                                     creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            background_processes.append(process)
            print(f"✅ Started: {script} (PID: {process.pid})")
        except FileNotFoundError:
            print(f"❌ Error: Python executable not found. Check your environment.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error launching {script}: {e}")
            sys.exit(1)

    print("-" * 60)

def start_streamlit():
    """Starts the Streamlit application in the foreground."""
    print("✅ Starting Streamlit Dashboard in foreground...")
    print("   (Ctrl+C here will stop all processes)")
    try:
        # Launch Streamlit, which takes over the current console
        subprocess.run([sys.executable, "-m", "streamlit", "run", STREAMLIT_APP_FILE], check=True)
    except subprocess.CalledProcessError:
        print("\n⚠️ Streamlit exited unexpectedly.")
    except KeyboardInterrupt:
        # This catches Ctrl+C when Streamlit is running
        pass
    finally:
        shutdown()

def shutdown():
    """Terminates all running background processes gracefully."""
    print("\n=" * 60)
    print("🛑 SHUTTING DOWN ALL SERVICES...")
    
    for process in background_processes:
        if process.poll() is None: # Check if process is still running
            try:
                # Terminate process gently
                if os.name == 'nt':
                    # Windows specific termination
                    os.kill(process.pid, signal.CTRL_C_EVENT)
                else:
                    # Linux/macOS termination
                    process.terminate()
                print(f"  🛑 Terminated PID {process.pid}")
            except Exception as e:
                print(f"  ❌ Error terminating PID {process.pid}: {e}")
    
    print("✅ System shutdown complete.")

if __name__ == "__main__":
    try:
        launch_background_scripts()
        # Give the pipeline a moment to initialize the DB and start collecting ticks
        time.sleep(3) 
        start_streamlit()
    except KeyboardInterrupt:
        # Catch Ctrl+C in the main script before Streamlit takes over
        print("\nInterrupted by user.")
        shutdown()