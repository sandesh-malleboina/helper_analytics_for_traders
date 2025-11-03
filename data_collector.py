import websocket # pip install websocket-client
import json
import requests  # pip install requests
import time
import pandas as pd

# --- Configuration ---
API_ENDPOINT = "http://127.0.0.1:8000/ingest"
SYMBOLS = ["btcusdt", "ethusdt", "solusdt"] 
BINANCE_URL = "wss://fstream.binance.com/stream?streams="

def normalize(j: dict) -> dict:
    """Normalizes the Binance trade message to our TickInput format."""
    return {
        "symbol": j['s'].lower(),
        "ts": pd.Timestamp(j['T'], unit='ms').isoformat(), # Convert ms to ISO string
        "price": float(j['p']),
        "size": float(j['q'])
    }

def on_message(ws, message):
    """Callback for when a message is received."""
    try:
        data = json.loads(message)
        
        # Data is nested under 'data' key for multi-stream
        if 'data' in data:
            trade_data = data['data']
            if trade_data.get('e') == 'trade':
                tick = normalize(trade_data)
                
                # Send data to backend (synchronous blocking call)
                try:
                    requests.post(API_ENDPOINT, json=tick, timeout=2.0)
                    print(f"Logged: {tick['symbol']} | {tick['price']}")
                except requests.RequestException as e:
                    print(f"Error posting to API: {e}")
                    
    except Exception as e:
        print(f"Error processing message: {e}")

def on_error(ws, error):
    """Callback for errors."""
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    """Callback when connection is closed."""
    print(f"--- WebSocket Closed: {close_status_code} {close_msg} ---")
    
def on_open(ws):
    """Callback when connection is opened."""
    print(f"Connected to streams: {', '.join(SYMBOLS)}")

if __name__ == "__main__":
    # --- Check if backend is alive ---
    print("Checking if backend is alive at http://127.0.0.1:8000/docs")
    try:
        requests.get("http://127.0.0.1:8000/docs", timeout=3)
        print("Backend is alive. Starting collector...")
    except requests.ConnectionError:
        print("--- FATAL: Backend is not running. Start app_backend.py first. ---")
        exit()
    
    # --- Start WebSocket Client ---
    stream_names = [f"{sym}@trade" for sym in SYMBOLS]
    url = BINANCE_URL + "/".join(stream_names)
    
    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # run_forever() will block here and automatically reconnect on drops
    print(f"Connecting to Binance WebSocket: {url}")
    ws.run_forever(reconnect=5) # Auto-reconnect every 5 seconds if connection drops