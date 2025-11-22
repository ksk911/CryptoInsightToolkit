import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.stattools import adfuller

# Import your analytics module
from analytics import PairsAnalytics, get_paired_candles

# ---- Configuration ----
engine = create_engine("postgresql://postgres:kaustubh@localhost:5432/quantdb")

print("=" * 80)
print("📊 ANALYTICS VERIFICATION SCRIPT")
print("=" * 80)

# ---- Step 1: Load Data ----
print("\n📥 STEP 1: Loading paired candle data...")

symbol1 = "BTCUSDT"
symbol2 = "ETHUSDT"
timeframe = "1m"
lookback = 50

df = get_paired_candles(engine, symbol1, symbol2, timeframe, lookback)

if df is None or df.empty:
    print("❌ No data found! Make sure websocket and build_ohlc are running.")
    exit()

print(f"✅ Loaded {len(df)} paired candles")
print(f"\nFirst 5 rows:")
print(df.head())
print(f"\nData types:")
print(df.dtypes)

# Extract prices
prices1 = df[f'price_{symbol1.lower()}']
prices2 = df[f'price_{symbol2.lower()}']

print(f"\n{symbol1} prices: min={prices1.min():.2f}, max={prices1.max():.2f}, mean={prices1.mean():.2f}")
print(f"{symbol2} prices: min={prices2.min():.2f}, max={prices2.max():.2f}, mean={prices2.mean():.2f}")

# ---- Step 2: Calculate Hedge Ratio (OLS) ----
print("\n" + "=" * 80)
print("⚖️ STEP 2: Calculating Hedge Ratio (OLS Regression)")
print("=" * 80)

print("\n📐 Mathematical Formula:")
print(f"   Model: {symbol1} = α + β × {symbol2} + ε")
print(f"   Where β (beta) is the hedge ratio")

# Manual OLS calculation
print("\n🔢 Manual Calculation:")

# Prepare data
clean_df = pd.DataFrame({'y': prices1, 'x': prices2}).dropna()
print(f"   Valid data points: {len(clean_df)}")

if len(clean_df) < 10:
    print("❌ Insufficient data for regression!")
    exit()

# Add constant (intercept)
X = add_constant(clean_df['x'])
y = clean_df['y']

# Fit OLS
model = OLS(y, X).fit()

print(f"\n   Intercept (α): {model.params['const']:.6f}")
print(f"   Hedge Ratio (β): {model.params['x']:.6f}")
print(f"   R-squared: {model.rsquared:.6f}")
print(f"   P-value: {model.pvalues['x']:.6e}")

# Using your analytics module
print("\n🔧 Using Analytics Module:")
analytics = PairsAnalytics()
hedge_result = analytics.calculate_hedge_ratio(prices1, prices2)

if hedge_result:
    print(f"   Hedge Ratio (β): {hedge_result['hedge_ratio']:.6f}")
    print(f"   Intercept (α): {hedge_result['alpha']:.6f}")
    print(f"   R-squared: {hedge_result['r_squared']:.6f}")
    print(f"   P-value: {hedge_result['p_value']:.6e}")
    
    # Verify match
    manual_beta = model.params['x']
    module_beta = hedge_result['hedge_ratio']
    
    if abs(manual_beta - module_beta) < 0.0001:
        print(f"\n   ✅ VERIFICATION PASSED: Hedge ratios match!")
    else:
        print(f"\n   ❌ VERIFICATION FAILED: Hedge ratios don't match!")
        print(f"      Manual: {manual_beta:.6f}")
        print(f"      Module: {module_beta:.6f}")
else:
    print("   ❌ Analytics module returned None!")

# Interpretation
print("\n💡 Interpretation:")
if hedge_result and hedge_result['r_squared'] > 0.8:
    print(f"   ✅ Excellent fit (R² = {hedge_result['r_squared']:.4f})")
    print(f"   📊 For every $1 change in {symbol2}, {symbol1} changes by ${hedge_result['hedge_ratio']:.4f}")
elif hedge_result and hedge_result['r_squared'] > 0.6:
    print(f"   ⚠️ Good fit (R² = {hedge_result['r_squared']:.4f})")
else:
    print(f"   ❌ Poor fit (R² = {hedge_result['r_squared']:.4f} if available)")

# ---- Step 3: Calculate Spread ----
print("\n" + "=" * 80)
print("📈 STEP 3: Calculating Spread")
print("=" * 80)

if hedge_result:
    beta = hedge_result['hedge_ratio']
    
    print(f"\n📐 Mathematical Formula:")
    print(f"   Spread = {symbol1} - (β × {symbol2})")
    print(f"   Spread = {symbol1} - ({beta:.4f} × {symbol2})")
    
    # Manual calculation
    print(f"\n🔢 Manual Calculation (first 5 values):")
    for i in range(min(5, len(prices1))):
        p1 = prices1.iloc[i]
        p2 = prices2.iloc[i]
        spread_manual = p1 - (beta * p2)
        print(f"   Row {i}: {p1:.2f} - ({beta:.4f} × {p2:.2f}) = {spread_manual:.2f}")
    
    # Using analytics module
    spread = analytics.calculate_spread(prices1, prices2, beta)
    
    print(f"\n🔧 Using Analytics Module (first 5 values):")
    for i in range(min(5, len(spread))):
        print(f"   Row {i}: {spread.iloc[i]:.2f}")
    
    # Verify
    spread_manual = prices1 - (beta * prices2)
    difference = (spread - spread_manual).abs().max()
    
    if difference < 0.01:
        print(f"\n   ✅ VERIFICATION PASSED: Spreads match!")
    else:
        print(f"\n   ❌ VERIFICATION FAILED: Max difference = {difference:.6f}")
    
    print(f"\n📊 Spread Statistics:")
    print(f"   Mean: {spread.mean():.2f}")
    print(f"   Std Dev: {spread.std():.2f}")
    print(f"   Min: {spread.min():.2f}")
    print(f"   Max: {spread.max():.2f}")
    print(f"   Current: {spread.iloc[-1]:.2f}")

# ---- Step 4: Calculate Z-Score ----
print("\n" + "=" * 80)
print("📊 STEP 4: Calculating Z-Score")
print("=" * 80)

if spread is not None:
    window = 20
    
    print(f"\n📐 Mathematical Formula:")
    print(f"   Z-Score = (Spread - Rolling_Mean) / Rolling_Std")
    print(f"   Window size: {window}")
    
    # Manual calculation
    print(f"\n🔢 Manual Calculation:")
    rolling_mean = spread.rolling(window=window).mean()
    rolling_std = spread.rolling(window=window).std()
    zscore_manual = (spread - rolling_mean) / rolling_std
    
    print(f"   Last 5 values:")
    for i in range(-5, 0):
        idx = len(spread) + i
        if idx >= window:  # Only show where z-score is valid
            s = spread.iloc[idx]
            rm = rolling_mean.iloc[idx]
            rs = rolling_std.iloc[idx]
            z = zscore_manual.iloc[idx]
            print(f"   Row {idx}: ({s:.2f} - {rm:.2f}) / {rs:.2f} = {z:.4f}")
    
    # Using analytics module
    zscore = analytics.calculate_zscore(spread, window=window)
    
    print(f"\n🔧 Using Analytics Module (last 5 values):")
    for i in range(-5, 0):
        idx = len(zscore) + i
        if not pd.isna(zscore.iloc[idx]):
            print(f"   Row {idx}: {zscore.iloc[idx]:.4f}")
    
    # Verify
    zscore_diff = (zscore - zscore_manual).abs().max()
    
    if pd.isna(zscore_diff) or zscore_diff < 0.0001:
        print(f"\n   ✅ VERIFICATION PASSED: Z-scores match!")
    else:
        print(f"\n   ❌ VERIFICATION FAILED: Max difference = {zscore_diff:.6f}")
    
    print(f"\n📊 Z-Score Statistics (valid values only):")
    valid_zscore = zscore.dropna()
    if not valid_zscore.empty:
        print(f"   Mean: {valid_zscore.mean():.4f}")
        print(f"   Std Dev: {valid_zscore.std():.4f}")
        print(f"   Min: {valid_zscore.min():.4f}")
        print(f"   Max: {valid_zscore.max():.4f}")
        print(f"   Current: {valid_zscore.iloc[-1]:.4f}")
        
        # Interpretation
        current_z = valid_zscore.iloc[-1]
        print(f"\n💡 Interpretation:")
        if current_z > 2:
            print(f"   🔴 SHORT SIGNAL: Z-score = {current_z:.2f} (spread too high)")
        elif current_z < -2:
            print(f"   🟢 LONG SIGNAL: Z-score = {current_z:.2f} (spread too low)")
        else:
            print(f"   ⚪ NEUTRAL: Z-score = {current_z:.2f} (spread near mean)")

# ---- Step 5: ADF Test ----
print("\n" + "=" * 80)
print("📉 STEP 5: Augmented Dickey-Fuller (ADF) Test")
print("=" * 80)

if spread is not None:
    print(f"\n📐 Purpose:")
    print(f"   Tests if the spread is stationary (mean-reverting)")
    print(f"   Null hypothesis: Spread has unit root (non-stationary)")
    print(f"   If p-value < 0.05: Reject null → Spread is stationary ✅")
    
    # Manual calculation
    print(f"\n🔢 Manual ADF Test:")
    clean_spread = spread.dropna()
    
    if len(clean_spread) >= 10:
        result = adfuller(clean_spread, autolag='AIC')
        
        print(f"   Test Statistic: {result[0]:.4f}")
        print(f"   P-value: {result[1]:.6f}")
        print(f"   Critical Values:")
        for key, value in result[4].items():
            print(f"      {key}: {value:.4f}")
        
        if result[1] < 0.05:
            print(f"   ✅ Spread is STATIONARY (good for mean reversion)")
        else:
            print(f"   ❌ Spread is NON-STATIONARY (not ideal for trading)")
    
    # Using analytics module
    print(f"\n🔧 Using Analytics Module:")
    adf_result = analytics.run_adf_test(spread)
    
    if adf_result:
        print(f"   Test Statistic: {adf_result['adf_statistic']:.4f}")
        print(f"   P-value: {adf_result['p_value']:.6f}")
        print(f"   Result: {adf_result['interpretation']}")
        print(f"   Tradeable: {'✅ Yes' if adf_result['is_stationary'] else '❌ No'}")
        
        # Verify
        if abs(result[0] - adf_result['adf_statistic']) < 0.0001:
            print(f"\n   ✅ VERIFICATION PASSED: ADF tests match!")
        else:
            print(f"\n   ❌ VERIFICATION FAILED: Test statistics don't match!")

# ---- Step 6: Rolling Correlation ----
print("\n" + "=" * 80)
print("🔗 STEP 6: Rolling Correlation")
print("=" * 80)

window = 20

print(f"\n📐 Mathematical Formula:")
print(f"   Correlation = Pearson correlation over rolling {window}-period window")

# Manual calculation
print(f"\n🔢 Manual Calculation (last 5 values):")
corr_manual = prices1.rolling(window=window).corr(prices2)

for i in range(-5, 0):
    idx = len(corr_manual) + i
    if not pd.isna(corr_manual.iloc[idx]):
        print(f"   Row {idx}: {corr_manual.iloc[idx]:.4f}")

# Using analytics module
correlation = analytics.calculate_rolling_correlation(prices1, prices2, window=window)

print(f"\n🔧 Using Analytics Module (last 5 values):")
for i in range(-5, 0):
    idx = len(correlation) + i
    if not pd.isna(correlation.iloc[idx]):
        print(f"   Row {idx}: {correlation.iloc[idx]:.4f}")

# Verify
corr_diff = (correlation - corr_manual).abs().max()

if pd.isna(corr_diff) or corr_diff < 0.0001:
    print(f"\n   ✅ VERIFICATION PASSED: Correlations match!")
else:
    print(f"\n   ❌ VERIFICATION FAILED: Max difference = {corr_diff:.6f}")

# Interpretation
valid_corr = correlation.dropna()
if not valid_corr.empty:
    current_corr = valid_corr.iloc[-1]
    print(f"\n💡 Interpretation:")
    print(f"   Current correlation: {current_corr:.4f}")
    if current_corr > 0.7:
        print(f"   ✅ Strong positive correlation (good for pairs trading)")
    elif current_corr > 0.5:
        print(f"   ⚠️ Moderate correlation")
    else:
        print(f"   ❌ Weak correlation (risky for pairs trading)")

# ---- Summary ----
print("\n" + "=" * 80)
print("📋 VERIFICATION SUMMARY")
print("=" * 80)

tests_passed = []
tests_failed = []

# Check all verifications
if hedge_result and abs(model.params['x'] - hedge_result['hedge_ratio']) < 0.0001:
    tests_passed.append("✅ Hedge Ratio (OLS)")
else:
    tests_failed.append("❌ Hedge Ratio (OLS)")

if spread is not None and difference < 0.01:
    tests_passed.append("✅ Spread")
else:
    tests_failed.append("❌ Spread")

if zscore is not None and (pd.isna(zscore_diff) or zscore_diff < 0.0001):
    tests_passed.append("✅ Z-Score")
else:
    tests_failed.append("❌ Z-Score")

if adf_result and abs(result[0] - adf_result['adf_statistic']) < 0.0001:
    tests_passed.append("✅ ADF Test")
else:
    tests_failed.append("❌ ADF Test")

if correlation is not None and (pd.isna(corr_diff) or corr_diff < 0.0001):
    tests_passed.append("✅ Rolling Correlation")
else:
    tests_failed.append("❌ Rolling Correlation")

print("\n" + "\n".join(tests_passed))
if tests_failed:
    print("\n" + "\n".join(tests_failed))

if not tests_failed:
    print("\n" + "=" * 80)
    print("🎉 ALL VERIFICATIONS PASSED!")
    print("✅ Your analytics calculations are correct!")
    print("=" * 80)
else:
    print("\n" + "=" * 80)
    print("⚠️ SOME VERIFICATIONS FAILED")
    print("Please review the failed tests above")
    print("=" * 80)

# ---- Export Sample Data ----
print("\n📤 Exporting sample data for manual verification...")

export_df = pd.DataFrame({
    f'{symbol1}_price': prices1[:10],
    f'{symbol2}_price': prices2[:10],
    'spread': spread[:10] if spread is not None else None,
    'zscore': zscore[:10] if zscore is not None else None,
    'correlation': correlation[:10] if correlation is not None else None
})

export_df.to_csv('analytics_verification_sample.csv', index=False)
print("✅ Saved to: analytics_verification_sample.csv")

print("\n" + "=" * 80)
print("🔬 VERIFICATION COMPLETE")
print("=" * 80)