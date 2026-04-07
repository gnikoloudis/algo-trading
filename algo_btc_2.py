import os
import time
import json
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timedelta

# --- 1. CONFIG & STATE PATHS ---
CONFIG_FILE = 'blockchain_config.json'
STATE_FILE = 'blockchain_state.json'
LOG_DIR = 'logs'

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- 2. SYSTEM FUNCTIONS ---
def hard_reset_wifi():
    print("🚨 Network failure! Attempting WiFi restart...")
    os.system('sudo nmcli radio wifi off && sleep 2 && sudo nmcli radio wifi on')
    time.sleep(15)

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Config Load Error: {e}")
        return None

def save_state(portfolio, reserve):
    state = {'global_reserve': reserve, 'portfolio': portfolio.copy()}
    for symbol in state['portfolio']:
        lst = state['portfolio'][symbol]['last_sell_time']
        # Always save as ISO string for JSON compatibility
        if isinstance(lst, datetime):
            state['portfolio'][symbol]['last_sell_time'] = lst.isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def load_state(initial_portfolio):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                stored = json.load(f)
                port = stored['portfolio']
                for s in port:
                    ts = port[s].get('last_sell_time', None)
                    if isinstance(ts, str):
                        try:
                            port[s]['last_sell_time'] = datetime.fromisoformat(ts)
                        except:
                            port[s]['last_sell_time'] = datetime.min
                    else:
                        port[s]['last_sell_time'] = datetime.min
                return port, stored.get('global_reserve', 0.0)
        except Exception as e:
            print(f"⚠️ State Load Error: {e}")
    return initial_portfolio, 0.0

# --- 3. INITIALIZATION ---
client = Client() 
config = load_config()

raw_portfolio = {symbol: {
    'current_allocation': amt, 'starting_allocation': amt,
    'has_position': False, 'entry_price': 0, 'max_price_seen': 0,
    'coin_balance': 0, 'pnl_history': 0.0, 'status': 'IDLE',
    'last_sell_time': datetime.min
} for symbol, amt in config['PORTFOLIO_CONFIG'].items()}

portfolio, global_reserve = load_state(raw_portfolio)

# --- 4. MAIN TRADING ENGINE ---
try:
    while True:
        temp_config = load_config()
        if temp_config: config = temp_config
        params = config['STRATEGY_PARAMS']
        
        os.system('clear' if os.name != 'nt' else 'cls')
        print(f"--- 🛡️ SNIPER BOT ACTIVE | {datetime.now().strftime('%H:%M:%S')} ---")
        print(f"Reserve: ${global_reserve:.2f} | Strategy: Buy the Dip")
        print("-" * 60)

        for symbol in config['PORTFOLIO_CONFIG'].keys():
            try:
                # 1. DATA FETCHING
                klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_15MINUTE, "5 days ago UTC")
                df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
                for col in ['c', 'h', 'l']: df[col] = pd.to_numeric(df[col])

                # 2. INDICATORS
                sma_f = ta.sma(df['c'], length=params['fast_sma'])
                sma_s = ta.sma(df['c'], length=params['slow_sma'])
                rsi = ta.rsi(df['c'], length=params['rsi_period'])
                adx_df = ta.adx(df['h'], df['l'], df['c'], length=params['adx_period'])
                bb = ta.bbands(df['c'], length=params['bb_period'], std=params['bb_std'])
                atr = ta.atr(df['h'], df['l'], df['c'], length=params['atr_period'])

                if sma_s is None or sma_s.isna().iloc[-1]:
                    continue

                # Dynamic Bollinger Mapping
                mid_bb_col = [c for c in bb.columns if c.startswith('BBM_')][0]
                
                curr_price = df['c'].iloc[-1]
                curr_sma_f = sma_f.iloc[-1]
                curr_sma_s = sma_s.iloc[-1]
                curr_rsi = rsi.iloc[-1]
                curr_adx = adx_df['ADX_14'].iloc[-1]
                curr_mid_bb = bb[mid_bb_col].iloc[-1]
                curr_atr = atr.iloc[-1]

                data = portfolio[symbol]
                event = "NONE"

                # 3. VOTING
                v_trend = 1 if curr_sma_f > curr_sma_s else 0
                v_mom = 1 if (curr_rsi < params['rsi_buy_max'] and curr_adx > params['adx_min_strength']) else 0
                v_vol = 1 if curr_price < curr_mid_bb else 0
                total_votes = v_trend + v_mom + v_vol

                # 🟢 ENTRY LOGIC
                if not data['has_position']:
                    # --- CRITICAL TYPE GUARD ---
                    last_sell = data['last_sell_time']
                    if isinstance(last_sell, str):
                        try:
                            last_sell = datetime.fromisoformat(last_sell)
                        except:
                            last_sell = datetime.min
                    
                    cooldown_time = last_sell + timedelta(minutes=params['cooldown_minutes'])
                    in_cooldown = datetime.now() < cooldown_time
                    
                    if total_votes >= params['buy_vote_threshold'] and not in_cooldown:
                        data.update({
                            'has_position': True, 'entry_price': curr_price,
                            'max_price_seen': curr_price, 'status': 'HOLDING',
                            'coin_balance': data['current_allocation'] / curr_price
                        })
                        event = "BUY"

                # 🔴 EXIT LOGIC
                elif data['has_position']:
                    data['max_price_seen'] = max(data['max_price_seen'], curr_price)
                    floor = data['max_price_seen'] - (params['atr_multiplier'] * curr_atr)
                    open_pnl = (curr_price - data['entry_price']) * data['coin_balance']
                    
                    if (curr_price < floor) or (curr_sma_f < curr_sma_s):
                        trade_pnl = open_pnl * 0.999
                        if trade_pnl >= params['siphon_threshold']:
                            global_reserve += trade_pnl
                            data['current_allocation'] = data['starting_allocation']
                        else:
                            data['current_allocation'] += trade_pnl
                        
                        data.update({
                            'pnl_history': data['pnl_history'] + trade_pnl,
                            'has_position': False, 'status': 'IDLE',
                            'last_sell_time': datetime.now()
                        })
                        event = f"SELL"

                print(f"[{symbol}] Price: {curr_price:.2f} | Votes: {total_votes}/{params['buy_vote_threshold']}")

            except Exception as e:
                print(f"Error {symbol}: {e}")

        save_state(portfolio, global_reserve)
        time.sleep(config['LOOP_INTERVAL'])

except KeyboardInterrupt:
    save_state(portfolio, global_reserve)
    print("\n✅ Session saved. Bot Halted.")