from binance.client import Client
import pandas as pd
import time

client = Client() # Public access
symbol = "BTCUSDT"
investment_amount_usd = 20.0  # How much we want to "spend"

# State Tracking
has_position = False
entry_price = 0
total_profit = 0

print(f"--- Algo Bot Started: {symbol} | Budget: ${investment_amount_usd} ---")

try:
    while True:
        # 1. Get Data
        bars = client.get_klines(symbol=symbol, interval='1m', limit=100)
        df = pd.DataFrame(bars, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Vol', 'CT', 'QA', 'T', 'TB', 'TQ', 'I'])
        df['Close'] = df['Close'].astype(float)

        # 2. Indicators
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        
        current_price = df['Close'].iloc[-1]
        sma20 = df['SMA20'].iloc[-1]
        sma50 = df['SMA50'].iloc[-1]

        # 3. Buy/Sell Logic
        if sma20 > sma50 and not has_position:
            # SIMULATE BUY
            quantity = investment_amount_usd / current_price
            entry_price = current_price
            has_position = True
            print(f"\n[🚀 BUY] Price: ${current_price:,.2f} | Quantity: {quantity:.6f} BTC")

        elif sma20 < sma50 and has_position:
            # SIMULATE SELL
            exit_price = current_price
            profit = (exit_price - entry_price) * (investment_amount_usd / entry_price)
            total_profit += profit
            has_position = False
            print(f"\n[💰 SELL] Price: ${current_price:,.2f} | Trade Profit: ${profit:.2f}")
            print(f"Cumulative Profit: ${total_profit:.2f}")

        # Console Log
        status = "HOLDING" if has_position else "IDLE"
        print(f"Status: {status} | Price: ${current_price:,.2f} | SMA20: {sma20:.2f} | SMA50: {sma50:.2f}")
        time.sleep(60) # Wait 1 minute before next check

except KeyboardInterrupt:
    print("\nBot stopped. Final Profit: $", round(total_profit, 2))