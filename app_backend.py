from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import io
import pandas as pd

import db_manager
import analytics_engine

# --- Pydantic Models ---
class TickInput(BaseModel):
    """Pydantic model for incoming tick data."""
    symbol: str
    ts: str  # Timestamp in ISO format
    price: float
    size: float

# --- FastAPI App ---
app = FastAPI(
    title="GemsCap Quant Analytics API",
    description="API for ingesting tick data and serving quantitative analytics."
)

@app.on_event("startup")
async def startup_event():
    """On startup, create the database and tables."""
    print("Starting up and initializing database...")
    db_manager.create_database()
    print("Database initialized.")

# --- API Endpoints ---

@app.post("/ingest")
async def ingest_tick(tick: TickInput):
    """
    Endpoint to receive tick data from the collector.
    """
    try:
        db_manager.insert_tick_data(
            timestamp=tick.ts,
            symbol=tick.symbol,
            price=tick.price,
            size=tick.size
        )
        return {"status": "success", "symbol": tick.symbol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/pair")
async def get_pair_analytics(
    symbol_a: str,
    symbol_b: str,
    timeframe: str = Query("1T", description="Resampling timeframe (e.g., '1S', '5T', '1H')"),
    rolling_window: int = Query(20, description="Rolling window for correlation/stats"),
    regression_type: str = Query("OLS", description="Regression type (e.g., 'OLS')")
):
    """
    Main endpoint to fetch and compute all pair analytics.
    """
    # 1. Fetch raw data
    raw_ticks_df = db_manager.get_ticks_df(symbol_a, symbol_b)
    
    if raw_ticks_df.empty:
        raise HTTPException(status_code=404, detail="No data found for the given symbols.")

    # 2. Compute analytics
    results = analytics_engine.compute_pair_analytics(
        ticks_df=raw_ticks_df,
        symbol_a=symbol_a,
        symbol_b=symbol_b,
        timeframe=timeframe,
        rolling_window=rolling_window,
        regression_type=regression_type
    )
    
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])
        
    return results
        

@app.get("/data/symbols")
async def get_symbols():
    """
    Endpoint to get a list of all distinct symbols in the database.
    """
    symbols = db_manager.get_distinct_symbols()
    if not symbols:
        # Provide defaults if DB is empty
        return ["btcusdt", "ethusdt"]
    return symbols

# --- NEW ENDPOINT ---
@app.get("/data/tick_count")
async def get_tick_count():
    """
    Returns the total count of ticks collected in the database.
    """
    count = db_manager.get_tick_count()
    return {"tick_count": count}
# --- END NEW ENDPOINT ---

@app.get("/data/download")
async def download_pair_data(
    symbol_a: str,
    symbol_b: str,
    timeframe: str = "1T",
    rolling_window: int = 20
):
    """
    Provides a CSV download of the processed analytics data.
    """
    raw_ticks_df = db_manager.get_ticks_df(symbol_a, symbol_b)
    if raw_ticks_df.empty:
        raise HTTPException(status_code=404, detail="No data.")

    results = analytics_engine.compute_pair_analytics(
        raw_ticks_df, symbol_a, symbol_b, timeframe, rolling_window
    )
    
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])

    # Convert the main "pair_data" to a CSV
    df_to_download = pd.DataFrame(results['charts']['pair_data'])
    
    stream = io.StringIO()
    df_to_download.to_csv(stream, index=False)
    
    response = StreamingResponse(
        iter([stream.getvalue()]), 
        media_type="text/csv"
    )
    response.headers["Content-Disposition"] = f"attachment; filename=analytics_{symbol_a}_{symbol_b}.csv"
    return response

if __name__ == "__main__":
    print("Starting FastAPI server at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)