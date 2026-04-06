import os
import time
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
PORTFOLIO_CONFIG = {
    'BTCUSDT': 30.0,
    'ETHUSDT': 40.0,
    'SOLUSDT': 30.0,
}

FAST_WINDOW = 50
SLOW_WINDOW = 200
RSI_BUY_MAX = 55      
ADX_MIN_STRENGTH = 20 
COOLDOWN_MINUTES = 60 
KILL_SWITCH_THRESHOLD = -5.00 
SIPHON_THRESHOLD = 5.00  # Only siphon if profit is > $5.00

client = Client()

# --- 2. INITIALIZE ---
global_reserve = 0.0
bot_active = True
# Added 'starting_allocation' to track what to siphon against
portfolio = {symbol: {
                'trench_limit': amt, 
                'current_allocation': amt, 
                'starting_allocation': amt, 
                'has_position': False, 
                'entry_price': 0, 
                'coin_balance': 0, 
                'pnl_history': 0.0, 
                'status': 'IDLE',
                'last_sell_time': datetime.min 
            } for symbol, amt in PORTFOLIO_CONFIG.items()}

if not os.path.exists('logs'): os.makedirs('logs')
log_filename = f"logs/siphon_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

def save_log(data_row):
    # This remains the same, but now data_row will contain 'wallet_reserve'
    file_exists = os.path.isfile(log_filename)
    pd.DataFrame([data_row]).to_csv(
        log_filename, 
        mode='a', 
        index=False, 
        header=not file_exists
    )
# --- 3. PROFIT SIPHON FUNCTION ---
def handle_profit_siphon(symbol, trade_pnl):
    global global_reserve
    data = portfolio[symbol]
    
    # Only siphon if it's a win AND above our fee-protection threshold
    if trade_pnl >= SIPHON_THRESHOLD:
        global_reserve += trade_pnl
        # Reset current allocation to the original starting point
        data['current_allocation'] = data['starting_allocation']
        return f"💰 SIPHONED ${trade_pnl:.2f}"
    
    elif trade_pnl > 0:
        # It's a profit, but too small to siphon. 
        # We leave it in 'current_allocation' so the next trade is slightly larger (compounding).
        data['current_allocation'] += trade_pnl
        return f"📈 SMALL GAIN ${trade_pnl:.2f} (Compounded)"
        
    else:
        # Loss stays within the trench
        data['current_allocation'] += trade_pnl
        return f"📉 LOSS ${abs(trade_pnl):.2f}"
try:
    while bot_active:
        total_pnl_tracker = 0
        os.system('cls' if os.name == 'nt' else 'clear')
        
        for symbol in PORTFOLIO_CONFIG.keys():
            try:
                # INDICATORS CALCULATED SEPERATELY FOR EACH SYMBOL
                bars = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=300)
                df = pd.DataFrame(bars, columns=['T', 'O', 'H', 'L', 'C', 'V', 'CT', 'QA', 'TQ', 'TB', 'TQ2', 'I'])
                df[['O', 'H', 'L', 'C']] = df[['O', 'H', 'L', 'C']].astype(float)
                
                sma_f = ta.sma(df['C'], length=FAST_WINDOW).iloc[-1]
                sma_s = ta.sma(df['C'], length=SLOW_WINDOW).iloc[-1]
                adx_df = ta.adx(df['H'], df['L'], df['C'], length=14)
                current_adx = adx_df['ADX_14'].iloc[-1]
                current_rsi = ta.rsi(df['C'], length=14).iloc[-1]
                atr = ta.atr(df['H'], df['L'], df['C'], length=14).iloc[-1]
                
                current_price = df['C'].iloc[-1]
                data = portfolio[symbol]
                event = "NONE"
                siphon_msg = ""

                in_cooldown = datetime.now() < (data['last_sell_time'] + timedelta(minutes=COOLDOWN_MINUTES))

                # ENTRY LOGIC
                if (sma_f > sma_s and current_adx > ADX_MIN_STRENGTH and 
                    current_rsi < RSI_BUY_MAX and not data['has_position'] and not in_cooldown):
                    
                    data['entry_price'] = current_price
                    # Use current_allocation (which might be lower if a previous loss occurred)
                    data['coin_balance'] = (data['current_allocation'] * 0.999) / current_price
                    data['has_position'] = True
                    data['status'] = 'HOLDING'
                    event = "BUY"

                # EXIT LOGIC WITH SIPHONING
                elif data['has_position']:
                    stop_price = data['entry_price'] - (2 * atr)
                    
                    if current_price < stop_price or sma_f < sma_s:
                        sell_val = (data['coin_balance'] * current_price) * 0.999
                        trade_pnl = sell_val - data['current_allocation']
                        
                        # Trigger the Siphon
                        s_msg = handle_profit_siphon(symbol, trade_pnl)
                        
                        data['pnl_history'] += trade_pnl
                        data['has_position'] = False
                        data['status'] = 'IDLE'
                        data['last_sell_time'] = datetime.now()
                        event = f"SELL ({s_msg})"

                # LOGGING
                open_pnl = (current_price - data['entry_price']) * data['coin_balance'] if data['has_position'] else 0
                symbol_total_pnl = data['pnl_history'] + open_pnl
                total_pnl_tracker += symbol_total_pnl

                save_log({
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'symbol': symbol, 
                        'price': current_price, 
                        'rsi': current_rsi,
                        'status': data['status'], 
                        'event': event, 
                        'current_pnl': symbol_total_pnl,
                        'wallet_reserve': global_reserve  # <-- Add this line
                    })

            except Exception as e:
                with open("bot_errors.txt", "a") as f:
                    f.write(f"{datetime.now()} Error {symbol}: {str(e)}\n")

        # DASHBOARD
        print(f"💰 WALLET RESERVE: ${global_reserve:.2f} | ACTIVE PnL: ${total_pnl_tracker:.2f}")
        print("-" * 65)
        for sym, d in portfolio.items():
            cd = "❄️" if datetime.now() < (d['last_sell_time'] + timedelta(minutes=COOLDOWN_MINUTES)) else "  "
            print(f"{sym:10} {cd} | Cap: ${d['current_allocation']:6.2f} | {d['status']:8} | PnL: ${d['pnl_history']:6.2f}")
        
        if total_pnl_tracker <= KILL_SWITCH_THRESHOLD:
            print(f"\n🛑 KILL-SWITCH TRIGGERED AT ${total_pnl_tracker:.2f}")
            break

        time.sleep(60)

except KeyboardInterrupt:
    print("\nManual Stop.")