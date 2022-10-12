from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon import TelegramClient, sync, events
from datetime import datetime, timedelta
from pytz import timezone
import re
import math
import asyncio
#Мои файлы
import Tinkoff_API as tinkoff
import Statistics as stats

#Мой Американский
api_id = ""
api_hash = ""
phone = "+18578918851"

#Add patterns for regex
pattern = r"(?<=Фирма: )(?P<firm>.*)(?=\sТикер:)\s(Тикер:)\s(?P<ticker>\w*)\s*(Тип операции:)\s(?P<operation>\w*\S{1})\s*(Цена:)\s(?P<price>\d*.\d*)\s(?P<currency>\w*)\s*(Количество:)\s(?P<amount>\d*)\s*(Статус:)\s(\w*)\s*(Дата:)\s(?P<date>\d{4}-\d{2}-\d{2})\s*(?P<time>\d{1,2}:\d{2}:\d{2})\s*"
c = re.compile(pattern)
order_error_pattern = r'(?<=message":")(?P<error_API_message>.*)(?=",")'
order_error_c = re.compile(order_error_pattern)
pattern_event = "^Фирма"

#Add a channel to listen to and a channel to which to send messages 
user_telegram_channel = -1001775547352 #MishaBot telegram channel
#listening_channel = нужно найти мишин ID и вписать 

#start telegram client
client = TelegramClient("MishaBot", api_id, api_hash)
print("starting telegram client")
client.start(phone)
print("telegram client started")
print("\nDid you update misha_stocks_dict, my_stocks_dict and yesterdays_portfolio_amt in Statistics.py?\n")

#==============================================================================================================#
#scheduler code
async def send_stats():
	"""Sends trading statistic for the day"""
	statistics = "_"
	try:
		statistics = stats.get_stats()
	except Exception as e:
		statistics = f"There was an error getting stats for today\nThis is the error:\n{e}"
	await client.send_message(-1001775547352, f'<pre>{statistics}</pre>', parse_mode = 'html')

async def reset_counter():
	"""Resets the trade_counter every day at 20:00"""
	stats.start_trade_counter()

scheduler = AsyncIOScheduler(timezone="US/Eastern", job_defaults={"misfire_grace_time": 1000})
scheduler.add_job(send_stats, "cron", day_of_week="mon-fri", hour = "17", minute ="00")
scheduler.add_job(reset_counter, "cron", day_of_week="mon-fri", hour = "20")
scheduler.start()
#==============================================================================================================#

@client.on(events.NewMessage(pattern = pattern_event))

#main function
async def newMessageListener(event):
	me = await client.get_me()
	newMessage = str(event.message.message)
	#filter the messages to read only the ones that match the pattern
	match = c.search(newMessage)
	try:
		match.groups()
	except AttributeError:
		print("String did not match the pattern")
		print("THIS MESSAGE SHOULD NOT HAVE BEEN READ!")
		return 0

	#extract the trade information needed to make an order
	ticker = match.group("ticker")
	operation = match.group("operation")
	price = float(match.group("price"))
	currency = match.group("currency")
	misha_amount = int(match.group("amount"))
	amount = math.ceil(misha_amount/8) #buy only 1/8 of the amount, take the ceiling of the quotient
	
	#get the figi
	figi = tinkoff.search_instrument_by_ticker(ticker)

	#if the price comes as 0.0, get the last price for this ticker and make an order with that price
	if price == 0.0:
		price = tinkoff.get_price(figi)

	#adjust order price to make sure the trade completes
	if operation[:-1] == "покупка":
		price += price * 0.0035
		price = round(price, 2)
		operation = "Buy"
	elif operation[:-1] == "продажа":
		price -= price * 0.006
		price = round(price, 2)
		operation = "Sell"

	#if currency is RUB, then round to the required decimal places; look for the required price increment trhough tinkoff API
	if currency == "RUB":
		price_increment = tinkoff.get_price_increment(ticker)
		if price_increment == 1.0: price = round(price, 0)
		elif price_increment == 0.1: price = round(price, 1)
		elif price_increment == 0.01: price = round(price, 2)
		elif price_increment == 0.001: price = round(price, 3)
		elif price_increment == 2.0:
			price = round(price, 0)
			if price % 2 != 0: price += 1
		else: print("What is the price_increment?")


	if figi == "BBG0013HGFT4":
		return 0 #make sure we dont buy dollars

	#make the order
	try:
		try:
			amount = stats.check_amount(ticker, amount, misha_amount, operation)
		except Exception as e:
			await client.send_message(user_telegram_channel, str(e))
		order_response = tinkoff.make_order(figi, amount, operation, price)
		if order_response.payload.status == "New":
			trade_count = stats.increment_trade_count()
			print("Order made at:", datetime.now(tz=timezone('Europe/Moscow')).isoformat()[11:19]) #older print: print(f"New order made! Order number: {trade_count}\nOrder details:\nticker = {ticker}\noperation = {operation}\nprice = {price}\namount = {amount}\n\n")
			try:
				stats.update_stocks_dicts(ticker, amount, misha_amount, operation)
			except Exception as e:
				await client.send_message(user_telegram_channel, str(e))
	except Exception as make_order_exception:
		reason = make_order_exception #in case regex does not work, send the whole error message
		try:
			order_error_string = make_order_exception.body
			order_error_match = order_error_c.search(order_error_string)
			reason = order_error_match.group("error_API_message")
		except Exception as regex_error:
			print("There is a problem with make_order exception regex, this is the error", regex_error)
		error_message = f"There was an error when executing make_order() with:\nticker: {ticker}\namount: {amount}\noperation: {operation}\nprice: {price}\nreason: {reason}"
		await client.send_message(user_telegram_channel, error_message)
		print(error_message)
		print("This is the error:", make_order_exception)
		print()
		#write the problematic trade to a file
		with open(r"СделкиМишани.txt", "a") as fp:
			fp.write(error_message)

	#check the status of the trade and let me know if it was rejected
	try:	
		if order_response.payload.status == "Rejected":
			rejection_message = f"An order was rejected!\nMessage from API: {order_response.payload.message}\nOrder details:\nTicker: {ticker}\nOperation: {operation}\nPrice: {price}\nAmount: {amount}\n\n"
			await client.send_message(user_telegram_channel, rejection_message)
			print(rejection_message)
			with open(r"СделкиМишани.txt", "a") as fp:
				fp.write(rejection_message)
	except: pass #dont care about the exception because the reason for it is that there was an error with executing the order, we handle that in the lines above
	#Check if the trade actually happened today within the current hour (and let me know if the code repeated some old trade)
	try:
		date = match.group("date").split("-")
		time = match.group("time").split(":")
		trade_datetime = datetime(int(date[0]), int(date[1]), int(date[2]), int(time[0]), int(time[1]), int(time[2]))
		zone = timezone("Europe/Moscow")
		trade_datetime = zone.localize(trade_datetime)
		now = datetime.now(tz = timezone("Europe/Moscow"))
		lower = now - timedelta(minutes = 30)
		upper = now + timedelta(minutes = 30)
		if not lower <= trade_datetime <= upper:
			firm = match.group("firm")
			await client.send_message(user_telegram_channel, f"Hi!\nI just repeated an old order. Have a look at the order details for me please:\n\nFirm: {firm}\nTicker: {ticker}\nOperation: {operation}\nPrice: {price}\nAmount: {amount}")
			if operation == "Buy": operation == "Sell"
			else: operation = "Buy"
			#cancel the upgrade of the dictionaries since that was an old trade
			stats.update_stocks_dicts(ticker, amount, misha_amount, operation)
	except Exception as e: print(e) #print the error

try:
	client.run_until_disconnected()
except KeyboardInterrupt:
	client.disconnect()
finally:
	print("\nBye-bye!\n")
	print("yesterdays_portfolio_amt:", stats.yesterdays_portfolio_amt)
	print("leftover_stocks_dict:", stats.leftover_stocks_dict)
	print("misha_stocks_dict:", stats.misha_stocks_dict)
	print("my_stocks_dict:", stats.my_stocks_dict)
	print()

