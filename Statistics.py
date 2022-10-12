import Tinkoff_API as tinkoff
#from termcolor import colored пока не смог понять как использовать
#Trade counter code
def start_trade_counter():
	global trade_count
	trade_count = 0
	print(f"restarted trade_count, trade_count = {trade_count}")

def increment_trade_count():
	global trade_count
	trade_count += 1
	return trade_count

start_trade_counter()

#Trading statistics
global yesterdays_portfolio_amt
yesterdays_portfolio_amt = 3568.36
leftover_stocks_dict = {'VIR': (21, -82.46, 826.8399999999999), 'GTHX': (64, -29.34, 674.66), 'BABA': (35, -117.29, 4021.1099999999997)}
 #similar to opened_positions_dict, but with a different purpose
def get_stats():
	global yesterdays_portfolio_amt
	stats = ""
	portfolio_amt = 0
	opened_positions_dict = {} #key = ticker, value = tuple (lots, profit/loss, value)
	ticker_payment_dict = {"BrokerCommission": 0} #key = ticker, values = payments
	ops = tinkoff.print_24hr_operations()
	
	#get current opened positions in portfolio
	portfolio = tinkoff.get_portfolio()
	#run through each position in the portfolio
	for position in portfolio:
		#fill opened_positions dictionary
		try:
			if position.ticker != "USD000UTSTOM":
				amount = position.average_position_price.value*position.lots+position.expected_yield.value
				if position.average_position_price.currency == "RUB":
					amount = amount / tinkoff.get_price("BBG0013HGFT4")
				opened_positions_dict[position.ticker] = (position.lots, position.expected_yield.value, amount)
				leftover_stocks_dict[position.ticker] = (position.lots, position.expected_yield.value, amount)
				portfolio_amt += opened_positions_dict[position.ticker][2]
			else:
				portfolio_amt += position.balance #adding to the portfolio amount however many dollars we have left
		except Exception as e:
			if position.average_position_price == None:
				print("Something is wrong again with the average_position_price in the API")
				stats += "Something is wrong again with the average_position_price in the API\n\n"
			else:
				print(f"There was some new error with a position: {position}, {e}")
	#add some entries to stats
	stats += f"<b>Стоимость портфеля:</b> $ {round(portfolio_amt,2):>6}\n"
	portfolio_chg = round(portfolio_amt - yesterdays_portfolio_amt,2)
	if portfolio_chg > 0:
		stats += f"<b>Изменение стоимости:</b> $ {portfolio_chg:>6} &#127823\n\n" #with green apple
	else:
		stats += f"<b>Изменение стоимости:</b> $ {portfolio_chg:>6} &#127822\n\n" #with red apple
	stats += f"<b>Всего сделок сегодня:</b> {trade_count}\n\n"
	stats += "<b>Detailed profit/loss по закрытым сделкам и комиссия за день:</b>\n"

	#update yesterdays_portfolio_amt
	yesterdays_portfolio_amt = portfolio_amt
	#run through ps.payload.operations and extract payment amount, commission and fill the dictionary with ticker:
	#payment key-values (the payment will show how much we gained or lost with a given stock)
	for operation in ops:
		#transform figi into tickers
		try:
			ticker = list(tinkoff.ticker_figi_dict.keys())[list(tinkoff.ticker_figi_dict.values()).index(operation.figi)]
		except:
			ticker = operation.figi
		
		#fill the ticker_payment_dict
		try:
			if operation.operation_type == "BrokerCommission":
				ticker_payment_dict["BrokerCommission"] += operation.payment
			elif operation.operation_type == "MarginCommission":
				ticker_payment_dict["BrokerCommission"] += operation.payment / tinkoff.get_price("BBG0013HGFT4") #margin commission is always in RUB
			else:
				if ticker in leftover_stocks_dict:
					if ticker in ticker_payment_dict:
						ticker_payment_dict[ticker] -= leftover_stocks_dict[ticker][2]
					else:
						ticker_payment_dict[ticker] = -leftover_stocks_dict[ticker][2]
					del(leftover_stocks_dict[ticker])
				if ticker in ticker_payment_dict:
					ticker_payment_dict[ticker] += operation.payment
				else:
					ticker_payment_dict[ticker] = operation.payment
		except Exception as e:
			if operation.status != "Decline":
				#the following print statements are here to better understand where the error is coming from
				print("--------------------------------------------------------------------------------------------")
				print("TAKE A LOOK AT THIS OPERATION (print statement came from get_stats() function)\n")
				print(operation)
				print("This is the error", e)
				print("Ticker:", ticker)
				print("operation.payment = ", operation.payment)
				print("ticker_payment_dict =", ticker_payment_dict)
				print("ticker in leftover_stocks_dict? -", ticker in leftover_stocks_dict)
				print("ticker in ticker_payment_dict? -", ticker in ticker_payment_dict)
				print("--------------------------------------------------------------------------------------------")
				print()
				with open(r"СделкиМишани.txt", "a") as fp:
					fp.write(f"There is something wrong with the following operation:\n{operation}\n")

	#loop trhough the ticker_payment_dict and subtract current positions by ticker from it to get 
	#profit/loss на закрытые сделки
	for ticker in ticker_payment_dict:
		if ticker in opened_positions_dict:
			ticker_payment_dict[ticker] += opened_positions_dict[ticker][2]

	#add closed position to stats
	# &#127822 - red apple &#127823 - green apple
	profit_loss = 0 #initiate profit_loss variable
	for ticker in ticker_payment_dict:
		if ticker not in opened_positions_dict:
			profit_loss = ticker_payment_dict[ticker]
			if ticker != "BrokerCommission":
				if profit_loss > 0:
					stats += f"{ticker:>4}: $ {round(profit_loss, 2):>7} {'profit':>6} &#127823\n"
				else:
					stats += f"{ticker:>4}: $ {round(profit_loss, 2):>7} {'loss':>6} &#127822\n"

	stats += f"Комиссия: $ {round(ticker_payment_dict['BrokerCommission'] ,2)}\n\n"
	
	#add opened position to stats
	stats += "<b>Открытые сделки в портфеле:</b>\n"
	for ticker in opened_positions_dict:
		profit_loss = opened_positions_dict[ticker][1]
		if profit_loss > 0:
			stats += f"{ticker:>4}: {opened_positions_dict[ticker][0]:>3} lots $ {profit_loss:>5} profit &#127823\n"
		else:
			stats += f"{ticker:>4}: {opened_positions_dict[ticker][0]:>3} lots $ {profit_loss:>5}   loss &#127822\n"
	stats += "_________________________"
	return stats

#make sure we always sell the correct amount, without trying to go short
misha_stocks_dict = {'BABA': 289, 'GTHX': 500, 'OSUR': 0, 'SLDB': 0, 'VIPS': 0, 'POLY': 0, 'BILI': 100, 'MAC': 0, 'VIR': 200, 'ACAD': 0}
my_stocks_dict = {'BABA': 38, 'GTHX': 64, 'OSUR': 0, 'SLDB': 0, 'VIPS': 0, 'BILI': 13, 'POLY': 0, 'MAC': 0, 'VIR': 21, 'ACAD': 0}
def update_stocks_dicts(ticker, my_amount, misha_amount, operation):
    """updates the current lots of each stock in my portfolio and Misha's portfolio
    """
    #update portfolios
    if ticker in misha_stocks_dict:
        if operation == "Buy":
            misha_stocks_dict[ticker] += misha_amount
            my_stocks_dict[ticker] += my_amount
        else:
            misha_stocks_dict[ticker] = misha_stocks_dict[ticker] - misha_amount
            my_stocks_dict[ticker] -= my_amount
    else:
        if operation == "Buy":
            misha_stocks_dict[ticker] = misha_amount
            my_stocks_dict[ticker] = my_amount
        else:
            misha_stocks_dict[ticker] = -misha_amount
            my_stocks_dict[ticker] = -my_amount

def check_amount(ticker, my_amount, misha_amount, operation):
    """checks how many lots we have to sell, in order to not go short and not get an error when executing
    make_order()
    """
    amount = my_amount
    lots_left = 1
    
    if ticker in misha_stocks_dict:
        try:
            if operation == "Buy":
                lots_left = misha_stocks_dict[ticker] + misha_amount
            
            elif operation == "Sell":
                lots_left = misha_stocks_dict[ticker] - misha_amount
            
            if lots_left == 0:
                amount = my_stocks_dict[ticker]
        except Exception as e:
            print(f"There was an error with executing check_amount()\nThis is the error:\n{e}\n")
    return abs(amount)

#operation example
"""{'commission': None,
 'currency': 'USD',
 'date': datetime.datetime(2021, 10, 29, 22, 2, 48, 108000, tzinfo=tzoffset(None, 10800)),
 'figi': 'BBG006G2JVL2',
 'id': '1821046061',
 'instrument_type': 'Stock',
 'is_margin_call': False,
 'operation_type': 'BrokerCommission',
 'payment': -0.16,
 'price': None,
 'quantity': 0,
 'status': 'Done',
 'trades': None}

{'commission': {'currency': 'USD', 'value': -0.16},
 'currency': 'USD',
 'date': datetime.datetime(2021, 10, 29, 22, 2, 47, 108000, tzinfo=tzoffset(None, 10800)),
 'figi': 'BBG006G2JVL2',
 'id': '19859567',
 'instrument_type': 'Stock',
 'is_margin_call': False,
 'operation_type': 'Sell',
 'payment': 329.39,
 'price': 164.695,
 'quantity': 2,
 'status': 'Done',
 'trades': [{'date': datetime.datetime(2021, 10, 29, 22, 2, 47, 108000, tzinfo=tzoffset(None, 10800)),
			 'price': 164.695,
			 'quantity': 2,
			 'trade_id': '9899092'}]}


"""

#position example
"""{'average_position_price': {'currency': 'USD', 'value': 9.74},
 'average_position_price_no_nkd': None,
 'balance': 14.0,
 'blocked': None,
 'expected_yield': {'currency': 'USD', 'value': -1.33},
 'figi': 'BBG00FYCQ352',
 'instrument_type': 'Stock',
 'isin': 'US74347M1080',
 'lots': 14,
 'name': 'ProPetro Holding Corp',
 'ticker': 'PUMP'}
"""