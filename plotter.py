import sys
import os
import pandas as pd
import matplotlib
# Force the interactive backend for Linux
matplotlib.use('TkAgg') 
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from datetime import datetime

# --- 1. ARGUMENT HANDLING ---
if len(sys.argv) < 2:
    print("❌ Error: No log file provided.")
    print("Usage: python plotter.py <path_to_csv_file>")
    sys.exit(1)

LOG_FILE = sys.argv[1]

# --- 2. SETUP PLOT ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

def animate(i):
    if not os.path.exists(LOG_FILE):
        return
    
    try:
        # read_csv with 'engine=python' avoids file-lock issues if the bot is writing
        df = pd.read_csv(LOG_FILE, engine='python')
        if df.empty or len(df) < 2:
            return
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        ax1.clear()
        ax2.clear()
        
        # Panel 1: Prices
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol]
            ax1.plot(symbol_data['timestamp'], symbol_data['price'], label=symbol)
        
        ax1.set_title(f"Live Asset Prices | {os.path.basename(LOG_FILE)}")
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.2)

        # Panel 2: Total Portfolio PnL
        total_pnl = df.groupby('timestamp')['current_pnl'].sum().reset_index()
        ax2.plot(total_pnl['timestamp'], total_pnl['current_pnl'], color='green', linewidth=2)
        ax2.axhline(0, color='red', linestyle='--', alpha=0.5)
        
        current_pnl_val = total_pnl['current_pnl'].iloc[-1]
        ax2.set_title(f"Total Portfolio PnL: ${current_pnl_val:.2f}")
        ax2.set_ylabel("PnL ($)")
        ax2.grid(True, alpha=0.2)
        
        plt.tight_layout()

    except Exception:
        # Ignore errors caused by simultaneous file access
        pass

# --- 3. PERSISTENCE FIX ---
# Assigning to a global variable is the standard way to stop the 
# UserWarning: Animation was deleted without rendering anything
global_anim_reference = FuncAnimation(fig, animate, interval=5000, cache_frame_data=False)

print(f"--- 📈 Live Plotter Started on {LOG_FILE} ---")
# block=True ensures the script stays alive as long as the window is open
plt.show(block=True)