# -*- coding: utf-8 -*-
import json
import time as true_time
import pprint
import pandas as pd
import operator

from datetime import datetime
from datetime import timedelta
from configparser import ConfigParser

from pyrobot.trades import Trade
from pyrobot.robot import PyRobot
from pyrobot.indicators import Indicators

from td.client import TDClient

# Read the Config File
config = ConfigParser()
config.read("config/config.ini")

# Read the different values
CLIENT_ID = config.get("main", "CLIENT_ID")
REDIRECT_URI = config.get("main", "REDIRECT_URI")
CREDENTIALS_PATH = config.get("main", "JSON_PATH")
ACCOUNT_NUMBER = config.get("main", "ACCOUNT_NUMBER")

# Initialize the PyRobot Object
trading_robot = PyRobot(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    credentials_path=CREDENTIALS_PATH,
    trading_account=ACCOUNT_NUMBER,
    paper_trading=True
    )

# Create a portfolio.
trading_robot_portfolio = trading_robot.create_portfolio()

# Define trading Symbol.
trading_symbol = "FCEL"

# Add a position.
trading_robot_portfolio.add_position(
    symbol=trading_symbol,
    asset_type="equity"
    )

# Grab the historical prices.
end_date = datetime.today()
start_date = end_date - timedelta(days=30)

historical_prices = trading_robot.grab_historical_prices(
    start=start_date,
    end=end_date,
    bar_size=1,
    bar_type='minute'
    )

# Convert the data to a StockFrame.
stock_frame = trading_robot.create_stock_frame(
    data=historical_prices['aggregated'])

# Let's add the stock frame to the portfolio.
trading_robot.portfolio.stock_frame = stock_frame
trading_robot.portfolio.historical_prices = historical_prices

# Create a new indicator object.
indicator_client = Indicators(
    price_data_frame=stock_frame)

# Add the 200-day SMA.
indicator_client.sma(period=200, column_name='sma_200')

# Add the 50-day SMA.
indicator_client.sma(period=50, column_name='sma_50')

# Add the 50-day EMA.
indicator_client.ema(period=50, column_name="ema")

# Add a Signal Check.
indicator_client.set_indicator_signal_compare(
    indicator_1='sma_50',
    indicator_2='sma200',
    condition_buy=operator.ge,
    condition_sell=operator.le
    )

# Create a new Trade Object.
new_long_trade = trading_robot.create_trade(
    trade_id='long_enter',
    enter_or_exit='enter',
    long_or_short='long',
    order_type='mkt'
    )

# Add an Order Leg.
new_long_trade.instrument(
    symbol=trading_symbol,
    quantity=1,
    asset_type='EQUITY'
    )


# Create a new Trade Object for Exiting a position.
new_exit_trade = trading_robot.create_trade(
    trade_id='long_exit',
    enter_or_exit='exit',
    long_or_short='long',
    order_type='mkt'
    )

# Add an Order Leg.
new_exit_trade.instrument(
    symbol=trading_symbol,
    quantity=1,
    asset_type='EQUITY'
    )

def default(obj):
    if isinstance(obj, TDClient):
        return str(obj)

# Save Order.
with open(file='order_strategies.jsonc', mode='w+') as order_file:
    json.dump(
        obj=[new_long_trade.to_dict(), new_exit_trade.to_dict()],
        fp=order_file,
        default=default,
        indent=4
        )

# Define a trading dictionary.
trades_dict = {
    trading_symbol: {
        'buy': {
            'trade_func': trading_robot.trades['long_enter'],
            'trade_id': trading_robot.trades['long_enter]'].trade_id
            },
        'sell': {
            'trade_func': trading_robot.trades['long_exit'],
            'trade_id': trading_robot.trades['long_exit]'].trade_id
            }
        }
    }

# Define the ownership (Hardcoded to "not owned").
ownership_dict = {
    trading_symbol: False
    }

# Initialize a Order Variable
order = None

while trading_robot.regular_market_open:

    # Grab the latest bar.
    latest_bars = trading_robot.get_latest_bar()
    
    # Add to the stock frame.
    stock_frame.add_rows(data=latest_bars)
    
    # Refresh the indicators.
    indicator_client.refresh()
    
    print("="*50)
    print("Current StockFrame")
    print("-"*50)
    print(stock_frame.symbol_groups.tail())
    print("-"*50)
    print("")
    
    #Check for the signals.
    signals = indicator_client.check_signals()
    
    #Define the buy and sell signals.
    buys = signals['buys'].to_list()
    sells = signals['sells'].to_list()
    
    print("="*50)
    print("Current Symbols")
    print("-"*50)
    print("Symbol: {}".format(trading_symbol))
    print("Ownership Status: {}".format(ownership_dict[trading_symbol]))
    print("Buy Signals: {}".format(buys))
    print("Sells Signals: {}".format(sells))
    print("-"*50)
    print("")
    
    if ownership_dict[trading_symbol] is False and buys:
        
        # Execute trade
        trading_robot.execute_signals(
            signals=signals, 
            trades_to_execute=trades_dict
            )
        
        ownership_dict[trading_symbol] = True
        
        order: Trade = trades_dict[trading_symbol]['buy']['trade_func']

    if ownership_dict[trading_symbol] is True and sells:
        
        #Execute trade
        trading_robot.execute_signals(
            signals=signals, 
            trades_to_execute=trades_dict
            )
    
        ownership_dict[trading_symbol] = False
        
        order: Trade = trades_dict[trading_symbol]['sell']['trade_func']
    
    # Grab the Last Row
    last_row = trading_robot.stock_frame.frame.tail(n=1)
    
    # Grab the last bar timestamp
    last_bar_timestamp = last_row.index.get_level_values(1)
    
    # Wait till the next bar
    trading_robot.wait_till_next_bar(last_bar_timestamp=last_bar_timestamp)
    
    if order:
        order.check_status()