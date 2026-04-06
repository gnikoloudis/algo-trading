import yfinance as yf
import pandas as pd
import time

ticker_symbol = "MMM"
investment_amount_usd = 20.0

# State Tracking
has_position = False
entry_price = 0
total_profit = 0

print(f"--- Algo Bot Started: {ticker_symbol} (NYSE) | Budget: ${investment_amount_usd} ---")

try:
    while True:
        # 1. Fetch latest data (1-minute intervals)
        data = yf.download(ticker_symbol, period="1d", interval="1m", progress=False)
        
        # Flatten MultiIndex if yfinance returns it
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        if len(data) > 50:
            # 2. Indicators (using smaller windows for faster testing)
            data['SMA20'] = data['Close'].rolling(window=20).mean()
            data['SMA50'] = data['Close'].rolling(window=50).mean()
            
            current_price = float(data['Close'].iloc[-1])
            sma20 = float(data['SMA20'].iloc[-1])
            sma50 = float(data['SMA50'].iloc[-1])

            # 3. Simulation Logic
            if sma20 > sma50 and not has_position:
                entry_price = current_price
                has_position = True
                print(f"\n[🚀 BUY {ticker_symbol}] Price: ${current_price:.2f}")

            elif sma20 < sma50 and has_position:
                profit = (current_price - entry_price) * (investment_amount_usd / entry_price)
                total_profit += profit
                has_position = False
                print(f"\n[💰 SELL {ticker_symbol}] Price: ${current_price:.2f} | Profit: ${profit:.2f}")
                print(f"Total Portfolio Gain: ${total_profit:.2f}")

            # status display
            status = "HOLDING" if has_position else "IDLE"
            print(f"Status: {status} | Price: ${current_price:.2f} | SMA20: {sma20:.2f} | SMA50: {sma50:.2f}", end='\r')

        # 4. Market Hours Check
        # Note: Stocks only move M-F, 9:30 AM - 4:00 PM EST. 
        # If the price isn't changing, the market might be closed!
        time.sleep(60) 

except KeyboardInterrupt:
    print(f"\nSimulation Ended. Final Profit: ${total_profit:.2f}")