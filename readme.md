# GemsCap Quantitative Developer Evaluation Project

This project implements a robust, multi-process system for real-time quantitative analysis of live market data, fulfilling the requirements of the Quantitative Developer evaluation assignment.

## 🚀 Core Application Architecture

The system is decoupled into three main processes running concurrently:
1.  **Data Collector:** Connects to the Binance WebSocket and feeds data.
2.  **FastAPI Backend:** Ingests data, stores it in SQLite, and performs all core analytics on demand.
3.  **Streamlit Frontend:** The interactive web dashboard for user control and visualization.

## ✨ Key Features Implemented

* **Data Ingestion:** Live tick data from Binance Futures (BTCUSDT, ETHUSDT, SOLUSDT).
* **Storage:** Persistent tick data storage using **SQLite** (`ticks.db`).
* **Analytics Engine:** Performs core calculations using **Pandas** and **Statsmodels**.
    * **Hedge Ratio** (OLS Regression)
    * **Spread & Z-Score**
    * **Rolling Correlation**
    * **ADF Test** (Stationarity check)
* **User Interface (Streamlit):**
    * **On-Demand Refresh:** No automatic updates; data is refreshed only when the user clicks a button.
    * **Per-Chart Timeframes:** Timeframe (`1S`, `5T`, `1H`, etc.) is controlled independently for each graph using simple **+ / - buttons**.
    * **Alerting:** Real-time Z-Score alerts based on editable user thresholds.
    * **Data Export:** Download button for processed analytics CSV.
    * **Robustness:** Implements multiple data sanitation steps to prevent UI crashes from `NaN` or `0` values.

## 🛠️ Project Setup and Installation

**Prerequisites:** Python 3.8+ is required.

1.  **Activate Environment:** Ensure you are in your project directory with your virtual environment active.
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the System (Requires 3 Terminals)

| Terminal | Command | Description |
| :--- | :--- | :--- |
| **1. Backend API** | `python app_backend.py` | Starts the FastAPI server, initializes the database, and waits for requests. **Must be started first.** |
| **2. Data Collector** | `python data_collector.py` | Connects to Binance WebSocket and pushes raw ticks to the API server. |
| **3. Frontend UI** | `streamlit run app_frontend.py` | Starts the interactive web dashboard in your browser. |

---

## 📐 Architecture Diagram Description

I recommend using the **Box & Arrow** style in `draw.io` (app.diagrams.net). The architecture is clearly separated into three domains (Ingestion, Backend/Analytics, and Presentation) across three running processes. 

### I. Data Ingestion Flow (Continuous)

This path represents how raw data enters the system.

| Component | Technology | Role / Action |
| :--- | :--- | :--- |
| **External Source** | Binance WebSocket | Emits **raw tick data** (`{symbol, price, time, size}`). |
| **Data Collector** | `data_collector.py` (Process 2) | Subscribes to the WebSocket, normalizes the data, and sends it to the API. |
| **Backend API** | `app_backend.py` (Process 1) | Receives data via **POST /ingest**. Calls the DB Manager. |
| **Data Storage** | `ticks.db` (SQLite) | Persistent, file-based storage for all raw ticks. |

### II. Analytics/Query Flow (On-Demand)

This path runs every time a user clicks the **Refresh** button on the Streamlit dashboard.

| Component | Technology | Role / Action |
| :--- | :--- | :--- |
| **Frontend UI** | `app_frontend.py` (Process 3) | Sends a **GET /analytics/pair** request with parameters (symbols, timeframe, window). |
| **DB Manager** | `db_manager.py` | Queries the **SQLite DB** for the last 50,000 raw ticks. |
| **Analytics Engine** | `analytics_engine.py` | Takes the raw ticks, performs: **Resampling** ($\rightarrow$ Close Price & Volume), **OLS Regression**, **Z-Score**, **Correlation**, and **ADF Test**. |
| **Backend API** | `app_backend.py` | Encodes the cleaned analytics results (NaN/Inf replaced with None) into **JSON**. |
| **Frontend UI** | Streamlit | Decodes the JSON and renders the **Plotly Charts** and **Summary Metrics**. |

---

## 🤖 ChatGPT Usage Transparency

As per the assignment requirements, this is a transparency note on AI usage.

ChatGPT (GPT-4) was used as a **development assistant** throughout the construction of this prototype. Its primary functions were centered on **debugging, logic refinement, and documentation**.

* **Core Logic Implementation:** Generated the initial structures for the multi-process setup (FastAPI/Streamlit decoupling).
* **Critical Debugging:** Provided solutions for complex technical issues that arose from framework and library interactions, specifically:
    * Resolving **JSON serialization errors** (`ValueError: nan`, `TypeError: numpy.bool_`) by identifying the need for explicit type casting (`sanitize_float`).
    * Fixing the **"low price equals zero" bug** by implementing a robust `pandas.ffill().bfill()` chain within the `resample_data` function.
* **UI/UX Implementation:** Assisted in designing the **session state logic** in `app_frontend.py` to allow for per-chart, decoupled timeframe adjustment via `+ / -` buttons.
* **Documentation:** Structured the final `README.md` and provided the architectural blueprint.