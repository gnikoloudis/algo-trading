import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime, time as dt_time

# --- 1. CONFIGURATION ---
TICKERS = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'SPY']
ALLOCATION_PER_STOCK = 1000.0  # Virtual $1000 per stock
FAST_SMA = 50
SLOW_SMA = 200

# Simulation Settings
CHECK_INTERVAL = 3600  # Check every 1 hour
LOG_FILE = f"logs/stock_sim_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


# --- 2. INITIALIZE PORTFOLIO ---
portfolio = {symbol: {
    'shares': 0,
    'balance': ALLOCATION_PER_STOCK,
    'entry_price': 0,
    'status': 'IDLE',
    'pnl': 0.0
} for symbol in TICKERS}

def is_market_open():
    """Checks if the US Market is open (9:30 AM - 4:00 PM EST, Mon-Fri)"""
    now = datetime.now()
    # Simple check for weekday (0=Mon, 4=Fri)
    if now.weekday() > 4:
        return False
    
    current_time = now.time()
    start_time = dt_time(9, 30)
    end_time = dt_time(16, 0)
    return start_time <= current_time <= end_time

def log_event(data):
    df = pd.DataFrame([data])
    df.to_csv(LOG_FILE, mode='a', index=False, header=not pd.io.common.file_exists(LOG_FILE))

print(f"--- 📈 Stock Trend Simulator Started ({', '.join(TICKERS)}) ---")

# --- 3. MAIN LOOP ---
try:
    while True:
        if not is_market_open():
            print(f"[{datetime.now().strftime('%H:%M')}] Market is closed. Sleeping...")
            time.sleep(1800) # Check every 30 mins if market is closed
            continue

        print(f"\n--- Market Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        for ticker in TICKERS:
            try:
                # Fetch recent daily data (need at least 200 days for the SMA)
                data = yf.download(ticker, period="2y", interval="1d", progress=False)
                
                # Clean columns for yfinance v0.2.40+
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)

                # Calculate Indicators
                data['SMA_50'] = ta.sma(data['Close'], length=FAST_SMA)
                data['SMA_200'] = ta.sma(data['Close'], length=SLOW_SMA)
                
                current_price = data['Close'].iloc[-1]
                sma_f = data['SMA_50'].iloc[-1]
                sma_s = data['SMA_200'].iloc[-1]
                
                state = portfolio[ticker]
                event = "NONE"

                # STRATEGY LOGIC
                # BUY: Golden Cross + Price above 200
                if sma_f > sma_s and current_price > sma_s and state['shares'] == 0:
                    state['shares'] = state['balance'] / current_price
                    state['entry_price'] = current_price
                    state['balance'] = 0
                    state['status'] = 'HOLDING'
                    event = "BUY"
                    print(f"🚀 BUY {ticker} at ${current_price:.2f}")

                # SELL: Death Cross
                elif sma_f < sma_s and state['shares'] > 0:
                    state['balance'] = state['shares'] * current_price
                    state['pnl'] += (state['balance'] - ALLOCATION_PER_STOCK)
                    state['shares'] = 0
                    state['status'] = 'IDLE'
                    event = "SELL"
                    print(f"⚠️ SELL {ticker} at ${current_price:.2f} | PnL: ${state['pnl']:.2f}")

                # Update PnL display
                current_val = state['balance'] + (state['shares'] * current_price)
                live_pnl = current_val - ALLOCATION_PER_STOCK
                
                log_event({
                    'timestamp': datetime.now(),
                    'ticker': ticker,
                    'price': round(current_price, 2),
                    'sma_50': round(sma_f, 2),
                    'sma_200': round(sma_s, 2),
                    'status': state['status'],
                    'event': event,
                    'total_val': round(current_val, 2),
                    'pnl': round(live_pnl, 2)
                })

                print(f"{ticker:5} | Price: ${current_price:8.2f} | SMA50: ${sma_f:8.2f} | Status: {state['status']:8} | PnL: ${live_pnl:8.2f}")

            except Exception as e:
                print(f"Error updating {ticker}: {e}")

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print("\n--- Simulation Stopped by User ---")