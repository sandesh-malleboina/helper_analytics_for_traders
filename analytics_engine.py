import pandas as pd
import numpy as np  # Import numpy
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
from scipy.stats import zscore

def sanitize_float(value):
    """Converts numpy inf/nan to None for JSON compliance."""
    if pd.isna(value) or np.isinf(value):
        return None
    return float(value)

def resample_data(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resamples tick data to get close price and volume.
    """
    if df.empty:
        return pd.DataFrame()

    # --- SIMPLIFIED LOGIC ---
    # 1. Resample to get the 'close' price (last price in interval)
    resampled_close = df['price'].resample(timeframe).last()
    
    # 2. Resample to get Volume. Empty intervals will be 0.
    resampled_volume = df['size'].resample(timeframe).sum().fillna(0)
    
    # 3. Forward-fill the close price to fill gaps
    resampled_close.ffill(inplace=True)
    
    # 4. Backward-fill any gaps at the very start
    resampled_close.bfill(inplace=True)

    # 5. Combine into a new DataFrame
    resampled_df = pd.DataFrame({
        'close': resampled_close,
        'volume': resampled_volume
    })
    # --- END OF SIMPLIFIED LOGIC ---
    
    return resampled_df

def compute_pair_analytics(
    ticks_df: pd.DataFrame, 
    symbol_a: str, 
    symbol_b: str, 
    timeframe: str, 
    rolling_window: int,
    regression_type: str = "OLS"
):
    """
    Main function to compute all requested analytics for a pair of symbols.
    """
    if ticks_df.empty:
        return {"error": "No data available."}

    # 1. Separate and resample data
    df_a = ticks_df[ticks_df['symbol'] == symbol_a].set_index('timestamp').sort_index()
    df_b = ticks_df[ticks_df['symbol'] == symbol_b].set_index('timestamp').sort_index()

    if df_a.empty or df_b.empty:
        return {"error": "Data missing for one or both symbols."}

    resampled_a = resample_data(df_a, timeframe)
    resampled_b = resample_data(df_b, timeframe)
    
    # 2. Align dataframes
    pair_df = pd.DataFrame({
        'price_a': resampled_a['close'],
        'price_b': resampled_b['close'],
        'volume_a': resampled_a['volume'],
        'volume_b': resampled_b['volume']
    }).dropna() # Drop rows if one symbol has data but the other doesn't

    if pair_df.empty or len(pair_df) < rolling_window:
        return {"error": f"Not enough aligned data. Need at least {rolling_window} data points."}

    # 3. Compute Analytics
    
    # --- OLS Hedge Ratio (Robust) ---
    try:
        y = pair_df['price_a']
        X = sm.add_constant(pair_df['price_b'])
        model = sm.OLS(y, X).fit()
        hedge_ratio = sanitize_float(model.params.get('price_b', 0.0))
    except Exception as e:
        print(f"Analytics Error (OLS): {e}")
        hedge_ratio = 0.0

    # --- Spread, Z-Score, Correlation ---
    pair_df['spread'] = pair_df['price_a'] - hedge_ratio * pair_df['price_b']
    pair_df['z_score'] = zscore(pair_df['spread'])
    pair_df['rolling_corr'] = pair_df['price_a'].rolling(rolling_window).corr(pair_df['price_b'])

    # --- ADF Test (Robust) ---
    try:
        adf_input = pair_df['spread'].dropna()
        if adf_input.empty or adf_input.var() == 0:
             raise ValueError("ADF test requires non-empty series with variance.")
             
        adf_result_raw = adfuller(adf_input)
        adf_result = {
            'test_statistic': sanitize_float(adf_result_raw[0]),
            'p_value': sanitize_float(adf_result_raw[1]),
            '1%_critical_value': sanitize_float(adf_result_raw[4]['1%']),
            'is_stationary_99_conf': bool(adf_result_raw[0] < adf_result_raw[4]['1%'])
        }
    except Exception as e:
        print(f"Analytics Error (ADF): {e}")
        adf_result = {'test_statistic': None, 'p_value': None, 'error': str(e)}

    # --- Summary Stats ---
    stats_a_raw = resampled_a['close'].describe().to_dict()
    stats_a = {k: sanitize_float(v) for k, v in stats_a_raw.items()}
    
    stats_b_raw = resampled_b['close'].describe().to_dict()
    stats_b = {k: sanitize_float(v) for k, v in stats_b_raw.items()}

    # 4. Prepare results for JSON response

    # --- FINAL FIX (NaN/Inf) for CHARTS ---
    replace_values = [np.nan, np.inf, -np.inf, pd.NA, pd.NaT]
    pair_df.replace(replace_values, None, inplace=True)
    resampled_a.replace(replace_values, None, inplace=True)
    resampled_b.replace(replace_values, None, inplace=True)
    
    pair_df.reset_index(inplace=True)
    pair_df['timestamp'] = pair_df['timestamp'].astype(str)
    resampled_a.reset_index(inplace=True)
    resampled_a['timestamp'] = resampled_a['timestamp'].astype(str)
    resampled_b.reset_index(inplace=True)
    resampled_b['timestamp'] = resampled_b['timestamp'].astype(str)

    results = {
        "status": "success",
        "controls": {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "timeframe": timeframe,
            "rolling_window": rolling_window
        },
        "analytics": {
            "hedge_ratio": hedge_ratio,
            "adf_test_spread": adf_result,
            "stats_a": stats_a,
            "stats_b": stats_b
        },
        "charts": {
            # We now send the resampled data directly
            "resampled_a": resampled_a.to_dict('records'),
            "resampled_b": resampled_b.to_dict('records'),
            "pair_data": pair_df.to_dict('records')
        }
    }
    
    return results