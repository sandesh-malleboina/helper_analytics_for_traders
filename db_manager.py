import sqlite3
from sqlalchemy import create_engine, text
import pandas as pd

# Use SQLAlchemy engine for easier pandas integration, but raw SQL for setup
DB_NAME = "ticks.db"
engine = create_engine(f"sqlite:///{DB_NAME}")

def create_database():
    """Creates the initial database and 'ticks' table if it doesn't exist."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Create ticks table
        # Using TEXT for timestamp to store ISO 8601 strings
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            size REAL NOT NULL
        );
        """)
        
        # Create an index for faster lookups by symbol and timestamp
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON ticks (symbol, timestamp);")
        
        conn.commit()
        conn.close()
        print("Database and 'ticks' table created successfully.")
    except Exception as e:
        print(f"Error creating database: {e}")

def insert_tick_data(timestamp: str, symbol: str, price: float, size: float):
    """Inserts a single tick into the database."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ticks (timestamp, symbol, price, size) VALUES (?, ?, ?, ?)",
                (timestamp, symbol, price, size)
            )
            conn.commit()
    except Exception as e:
        print(f"Error inserting tick: {e}")

def get_ticks_df(symbol_a: str, symbol_b: str, max_rows=50000) -> pd.DataFrame:
    """
    Fetches recent ticks for two symbols and returns a combined DataFrame.
    Limits rows for performance.
    """
    try:
        query = text(f"""
        SELECT timestamp, symbol, price, size 
        FROM ticks
        WHERE symbol = :sym_a OR symbol = :sym_b
        ORDER BY timestamp DESC
        LIMIT :limit
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"sym_a": symbol_a, "sym_b": symbol_b, "limit": max_rows})
            
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
        return df
    except Exception as e:
        print(f"Error fetching ticks: {e}")
        return pd.DataFrame(columns=['timestamp', 'symbol', 'price', 'size'])

def get_distinct_symbols() -> list:
    """Fetches all distinct symbols from the database."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT DISTINCT symbol FROM ticks"))
            symbols = [row[0] for row in result]
            return symbols
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

def get_tick_count() -> int:
    """Counts the total number of ticks in the database."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(id) FROM ticks"))
            count = result.scalar()
            return count
    except Exception as e:
        print(f"Error counting ticks: {e}")
        return 0

if __name__ == "__main__":
    # Initialize the database
    create_database()