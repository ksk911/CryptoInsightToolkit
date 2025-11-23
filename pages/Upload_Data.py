import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from datetime import datetime
import os
import sys
from pathlib import Path

# --- CONFIGURATION ---
# This is the name of the table where the uploaded data will be temporarily stored
UPLOAD_TABLE_NAME = "user_uploaded_ohlc" 
DB_CONNECTION_STRING = "postgresql://postgres:kaustubh@localhost:5432/quantdb"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Upload Historical Data",
    page_icon="📥",
    layout="wide"
)

# --- INITIALIZATION ---
# Connect to PostgreSQL
try:
    engine = create_engine(DB_CONNECTION_STRING)
    # Store engine in session state for reuse if needed, though direct import works here too
    st.session_state.engine = engine 
except Exception as e:
    st.error(f"❌ Database connection error: {e}")
    st.stop()

# --- HELPER FUNCTION ---
def handle_upload(uploaded_file, engine):
    """Parses uploaded CSV, validates, and saves to a separate DB table."""
    st.info("⚙️ Processing file...")
    
    try:
        # --- FIX: Added comment='#' to skip metadata lines ---
        df_uploaded = pd.read_csv(uploaded_file, comment='#')
        # --- END FIX ---
        
        # 1. Column Validation (case-insensitive check is robust)
        required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        # Rename columns to lowercase for consistent internal processing
        df_uploaded.columns = [c.lower() for c in df_uploaded.columns]
        
        if not all(col in df_uploaded.columns for col in required_cols):
            st.error(f"❌ Error: Missing required columns in the CSV. Expected: {', '.join(required_cols)}")
            return
        
        # 2. Type Conversion
        df_uploaded['time'] = pd.to_datetime(df_uploaded['time'])
        
        # 3. Symbol Tagging (Creates a unique symbol tag for the uploaded dataset)
        uploaded_symbol_tag = f"UPLOAD_{datetime.now().strftime('%Y%m%d%H%M')}"
        df_uploaded['symbol'] = uploaded_symbol_tag
        
        # 4. Save to database (if_exists="replace" ensures only the latest file is active)
        df_uploaded.to_sql(
            UPLOAD_TABLE_NAME, 
            engine, 
            if_exists="replace", 
            index=False
        )
        
        # 5. Update session state flags for the Analytics page to read
        st.session_state['uploaded_data_ready'] = True
        st.session_state['uploaded_symbol'] = uploaded_symbol_tag
        
        st.balloons()
        st.success(f"✅ Data uploaded successfully! {len(df_uploaded)} rows saved to table `{UPLOAD_TABLE_NAME}`.")
        st.warning("👉 Now navigate to the **Pairs Analytics** page and select the **'Uploaded File'** source.")

    except Exception as e:
        st.error(f"❌ Failed to process uploaded file: {e}")
        st.code(f"Error details: {e}")


# ============================================
# MAIN PAGE LAYOUT
# ============================================

st.title("📥 Historical OHLC Data Ingestion")
st.markdown("Use this page to upload a CSV file and analyze it using the Pairs Trading tools.")

st.info("""
**Required CSV Format:** Must contain the following columns (case-insensitive) for a single asset:
* `Time` (or `Timestamp`)
* `Open`
* `High`
* `Low`
* `Close`
* `Volume`
""")

uploaded_file = st.file_uploader(
    "Choose a CSV file to upload", 
    type="csv",
    key="ohlc_upload_main"
)

if uploaded_file is not None:
    # Use a button to trigger processing (prevents re-running the heavy DB logic unnecessarily)
    if st.button("🚀 Process and Save Data", type="primary", use_container_width=True):
        handle_upload(uploaded_file, engine)
        
# Display status
st.markdown("---")
if st.session_state.get('uploaded_data_ready', False):
    st.success(f"File Ready: {st.session_state.get('uploaded_symbol')}. Ready for analysis!")
else:
    st.info("No historical file currently uploaded.")