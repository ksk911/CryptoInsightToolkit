# Quant Developer Evaluation Assignment: Real-Time Pairs Trading Analytics Platform

## 1. Project Overview

This application implements a comprehensive end-to-end analytical stack for real-time statistical arbitrage based on pairs trading strategies. The system demonstrates professional-grade software architecture designed for high-frequency trading environments, incorporating real-time data ingestion, quantitative analytics, and interactive visualization.

### Key Capabilities

- Real-time market data processing via Binance WebSocket streams for multiple cryptocurrency pairs
- Statistical arbitrage analytics using OLS regression, cointegration testing, and mean-reversion signals
- Interactive trading dashboard with real-time charts, metrics, and alert management
- PostgreSQL-backed data persistence with multi-timeframe OHLC candle generation
- Telegram-integrated alert system for threshold-based trading signals
- Historical data upload functionality for backtesting and external dataset analysis

### Design Philosophy

The architecture prioritizes modularity and extensibility. Components remain loosely coupled through clean interfaces, ensuring that scaling does not require fundamental rewrites. The system is designed such that plugging in different data feeds (CME futures, REST APIs, historical CSVs) or adding new analytics modules requires minimal code modification.

---

## 2. System Architecture

### Architecture Overview

The system follows a classic three-tier architecture pattern:

1. **Data Layer**: WebSocket ingestion and PostgreSQL storage
2. **Business Logic Layer**: Analytics computation and signal generation
3. **Presentation Layer**: Streamlit-based interactive dashboard

### Component Design Rationale

#### Data Ingestion Layer

**websocket_test.py** - Multi-Symbol WebSocket Collector
- Uses threading to maintain concurrent connections for 12 cryptocurrency pairs
- Implements price threshold filtering to reject erroneous ticks
- Direct WebSocket connection provides sub-millisecond latency

**build_ohlc.py** - OHLC Candle Aggregator
- Pandas time-series resampling with PostgreSQL upsert logic
- Dynamic gap-filling from last candle timestamp prevents reprocessing
- Supports 1-second, 1-minute, 5-minute intervals
- 7-day rolling window prevents unbounded table growth

#### Storage Layer

**PostgreSQL Database**
- Schema: `ticks`, `candles_1s`, `candles_1m`, `candles_5m`, `user_uploaded_ohlc`
- Chosen over SQLite for multi-process write concurrency and production-grade capabilities
- SQLAlchemy provides connection management and ORM abstraction

#### Analytics Layer

**analytics.py** - Quantitative Computing Engine

Core implementations:
1. **Hedge Ratio**: OLS regression to calculate optimal beta coefficient
2. **Spread Computation**: `Spread = Price1 - β × Price2`
3. **Z-Score Normalization**: `Z = (Spread - μ_rolling) / σ_rolling`
4. **Stationarity Testing**: Augmented Dickey-Fuller test (p < 0.05 indicates tradeable pair)
5. **Signal Generation**: Long/Short/Exit signals based on Z-score thresholds

**Data Access Abstraction**: Single parameter switches between live candle tables and uploaded data

#### Alert Management System

**alert_manager.py** - Rule Engine
- Observer pattern for metric threshold monitoring
- Telegram API integration for instant mobile alerts
- Extensible to support email, webhooks, SMS

**telegram_sender.py** - Communication Module
- Text messages, document upload, photo sharing capabilities
- Comprehensive error handling with retry logic

#### Presentation Layer

**Home.py** - Single Asset Price Dashboard
- Real-time price charts (candlestick, line, OHLC)
- Volume analysis with color-coded bars
- CSV export with metadata and Telegram sharing

**Analytics.py** - Pairs Trading Dashboard
- Dual-price chart, spread visualization, Z-score chart with threshold lines
- Rolling correlation plot
- OLS regression and ADF test statistics panels
- Trading signal recommendations with actionable advice
- Per-metric alert configuration UI
- Analytics data export with calculation formulas

---

## 3. Setup and Execution

### Prerequisites

- Python 3.8+
- PostgreSQL database (configured: `postgresql://postgres:kaustubh@localhost:5432/quantdb`)
- Internet connection for Binance WebSocket streams
- Telegram Bot (optional for alerts)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Required Packages**:
```
streamlit>=1.28.0
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
statsmodels>=0.14.0
plotly>=5.14.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
websocket-client>=1.5.0
requests>=2.31.0
```

### Database Initialization

```sql
CREATE DATABASE quantdb;
```

Tables auto-create on first run.

### Execution

**Single-Command Launch**

```bash
python run_system.py
```

This script:
1. Starts `websocket_test.py` (tick collection)
2. Starts `build_ohlc.py` (candle generation)
3. Waits for initial data accumulation (30-40 seconds)
4. Launches Streamlit dashboard

Press `Ctrl+C` to shut down all services.

### Usage Flow

1. **Initial Setup**: Wait 60-90 seconds after launch for data accumulation

2. **Home Dashboard**: View single-asset price charts, adjust timeframes, export data

3. **Upload Historical Data**: Import external CSV files for analysis (optional)

4. **Pairs Analytics Dashboard**:
   - Select two different symbols
   - Toggle between "Live Candles (DB)" and "Uploaded File"
   - Adjust parameters: lookback period (20-200), Z-score window (10-50), entry/exit thresholds
   - Configure alerts below each metric chart
   - Export analytics data with formulas

---

## 4. Core Quantitative Analytics

### Pairs Trading Methodology

The system implements statistical arbitrage based on mean reversion of cointegrated asset pairs. Two assets with a long-term equilibrium relationship will temporarily diverge but eventually converge.

### Mathematical Framework

#### 1. Hedge Ratio Estimation

**Model**: Ordinary Least Squares Regression
```
Price₁(t) = α + β × Price₂(t) + ε(t)
```

Where:
- `β` (beta) = Hedge ratio
- `α` (alpha) = Intercept
- `ε(t)` = Residual (the spread)

**Interpretation**:
- R² > 0.8: Excellent correlation (ideal)
- R² > 0.6: Good correlation (acceptable)
- R² < 0.5: Poor correlation (unsuitable)

#### 2. Spread Calculation

```
Spread(t) = Price₁(t) - β × Price₂(t)
```

#### 3. Z-Score Normalization

```
Z(t) = [Spread(t) - μ_rolling(t)] / σ_rolling(t)
```

**Trading Interpretation**:
- Z > +2: Spread 2σ above mean → SHORT signal
- Z < -2: Spread 2σ below mean → LONG signal
- |Z| < 0.5: Spread near mean → EXIT signal

#### 4. Stationarity Testing

**Test**: Augmented Dickey-Fuller (ADF)

**Decision Rule**:
- p-value < 0.05: Spread is stationary → Tradeable pair
- p-value ≥ 0.05: Spread non-stationary → Avoid trading

**Confidence Levels**:
- p < 0.01: High confidence
- p < 0.05: Moderate confidence
- p ≥ 0.05: Low confidence

#### 5. Rolling Correlation

**Interpretation**:
- ρ > 0.7: Strong positive correlation
- 0.3 < ρ < 0.7: Moderate correlation
- ρ < 0.3: Weak correlation (pair broken)

#### 6. Trading Signal Generation

| Condition | Z-Score Range | Signal | Action |
|-----------|---------------|--------|--------|
| Spread too low | Z < -entry_threshold | LONG | Buy Asset 1, Sell β × Asset 2 |
| Spread too high | Z > +entry_threshold | SHORT | Sell Asset 1, Buy β × Asset 2 |
| Spread normalized | -exit < Z < +exit | EXIT | Close positions |

---

## 5. Data Export Features

### CSV Export Capabilities

#### Home Dashboard Export
**Format**: `{SYMBOL}_{TIMEFRAME}_data_{TIMESTAMP}.csv`

**Includes**: Metadata header with symbol, timeframe, price range, volume, plus OHLC data columns

#### Analytics Dashboard Export
**Format**: `{SYMBOL1}_{SYMBOL2}_analytics_{TIMEFRAME}_{TIMESTAMP}.csv`

**Includes**: 
- Metadata with calculation formulas (hedge ratio, spread, Z-score, correlation)
- Trading logic explanation (entry/exit thresholds)
- Data columns: time, prices, spread, zscore, correlation, trading_signal, hedge_ratio

**Formula Documentation Example**:
```
# Hedge Ratio (β): Calculated using OLS regression: BTCUSDT = α + β × ETHUSDT
# Hedge Ratio Value: 16.234567
# R-Squared: 0.8234
#
# Spread = Price_BTCUSDT - (Hedge_Ratio × Price_ETHUSDT)
# Z-Score = (Spread - Rolling_Mean) / Rolling_StdDev
```

### Telegram Integration

- Automatic document upload with formatted caption
- Real-time alert notifications with trading recommendations
- Error handling with console logging

---

## 6. Extensibility Points

### Implemented for Future Enhancement

1. **Regression Type Selector**: UI dropdown ready for Kalman Filter integration
2. **Data Source Abstraction**: Easy switching between live and uploaded data
3. **Alert Condition Engine**: Generic Alert class supports any metric with operator-based conditions
4. **Telegram Module**: Prepared for email/webhook integration

### Suggested Extensions (Not Implemented)

- Kalman Filter for dynamic hedge ratio estimation
- Robust regression (Huber/Theil-Sen) for outlier resistance
- Mini backtest engine with Sharpe ratio calculation
- Liquidity filters based on volume thresholds
- Cross-correlation heatmap for pair discovery
- Time-series feature table with minute-by-minute snapshots

---

## 7. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Streamlit 1.28+ | Interactive dashboard |
| Visualization | Plotly 5.14+ | Interactive charts |
| Backend | Python 3.8+ | Core logic |
| Database | PostgreSQL 13+ | Time-series storage |
| ORM | SQLAlchemy 2.0+ | Database abstraction |
| Analytics | Pandas 2.0+ | Data manipulation |
| Statistics | Statsmodels 0.14+ | OLS/ADF tests |
| WebSocket | websocket-client 1.5+ | Real-time streaming |
| Notifications | Telegram Bot API | Alert delivery |
| Numerical | NumPy 1.24+ | Array operations |
| Scientific | SciPy 1.10+ | Statistical functions |

---

## 8. Conclusion

This project demonstrates a production-quality approach to building real-time financial analytics systems. The emphasis on modularity, clean interfaces, and extensibility ensures the codebase can evolve without requiring fundamental rewrites.

The separation of concerns—data ingestion, storage, analytics computation, and presentation—reflects industry best practices and allows for independent scaling of each component. The system successfully meets all core requirements while providing a foundation for advanced features such as Kalman filtering, backtesting, and multi-asset portfolio analysis.
