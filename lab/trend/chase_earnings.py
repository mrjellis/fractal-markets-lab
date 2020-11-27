import django
from django.apps import apps
from dotenv import load_dotenv
import json
import os
import sys
from datetime import date
from .functions import *
from ..core.functions import chunks
from ..core.api import quoteStatsBatchRequest, getEarnings, getPriceTarget
from ..core.output import printTable
from ..core.export import writeCSV
from ..twitter.tweet import send_tweet
import texttable
load_dotenv()
django.setup()

Stock = apps.get_model('database', 'Stock')
Earnings = apps.get_model('database', 'Earnings')
Watchlist = apps.get_model('database', 'Watchlist')

# Main Thread Start
print('Running...')

results = []
tickers = Stock.objects.all().values_list('ticker', flat=True)

chunked_tickers = chunks(tickers, 100)
for i, chunk in enumerate(chunked_tickers):
    batch = quoteStatsBatchRequest(chunk)

    for ticker, stockinfo in batch.items():
        print('Chunk {}: {}'.format(i, ticker))

        if (stockinfo.get('quote', False) and stockinfo.get('stats', False)):
            quote = stockinfo.get('quote')
            stats = stockinfo.get('stats')

            price = quote.get('latestPrice', 0)

            if (price and isinstance(price, float)):
                stock, created = Stock.objects.update_or_create(
                    ticker=ticker,
                    defaults={'lastPrice': price},
                )
            else:
                continue

            ttmEPS = stats['ttmEPS'] if ('ttmEPS' in stats and stats['ttmEPS']) else 0
            week52high = stats['week52high'] if ('week52high' in stats and stats['week52high']) else 0
            changeToday = quote['changePercent'] * 100 if ('changePercent' in quote and quote['changePercent']) else 0
            day5ChangePercent = stats['day5ChangePercent'] * 100 if ('day5ChangePercent' in stats and stats['day5ChangePercent']) else 0

            critical = [changeToday, week52high, ttmEPS, day5ChangePercent]

            if ((0 in critical)):
                continue

            fromHigh = round((price / week52high) * 100, 3)

            # Save Data to DB
            data_for_db = {
                'Valuation':  {
                    'peRatio': stats['peRatio'],
                },
                'Trend': {
                    'week52': week52high,
                    'day5ChangePercent': stats['day5ChangePercent'],
                    'month1ChangePercent': stats.get('month1ChangePercent', None),
                    'ytdChangePercent': stats.get('ytdChangePercent', None),
                    'day50MovingAvg': stats.get('day50MovingAvg', None),
                    'day200MovingAvg': stats.get('day200MovingAvg', None),
                    'fromHigh': fromHigh
                },
                'Earnings': {
                    'ttmEPS': ttmEPS
                },
            }

            dynamicUpdateCreate(data_for_db, stock)

            if ((fromHigh < 105) and (fromHigh > 95)):
                if (changeToday > 10):
                    earningsData = getEarnings(ticker)
                    if (earningsData and isinstance(earningsData, dict)):
                        print('{} ---- Checking Earnings ----'.format(ticker))
                        earningsChecked = checkEarnings(earningsData)
                        if (isinstance(earningsChecked, dict) and earningsChecked['actual'] and earningsChecked['consensus']):
                            # Save Earnings to DB
                            Earnings.objects.filter(stock=stock).update(
                                reportedEPS=earningsChecked['actual'],
                                reportedConsensus=earningsChecked['consensus'],
                            )

                            if (earningsChecked['improvement'] == True):
                                keyStats = {
                                    'week52': stats['week52high'],
                                    'ttmEPS': ttmEPS,
                                    'reportedEPS': earningsChecked['actual'],
                                    'reportedConsensus': earningsChecked['consensus'],
                                    'peRatio': stats['peRatio'],
                                    'day5ChangePercent': round(stats['day5ChangePercent'] * 100, 2) if ('day5ChangePercent' in stats) else None,
                                    'month1ChangePercent': round(stats['month1ChangePercent'] * 100, 2) if ('month1ChangePercent' in stats) else None,
                                    'ytdChangePercent': round(stats['ytdChangePercent'] * 100, 2) if ('ytdChangePercent' in stats) else None,
                                    'day50MovingAvg': stats['day50MovingAvg'],
                                    'day200MovingAvg': stats['day200MovingAvg'],
                                    'fromHigh': fromHigh,

                                }
                                stockData = {
                                    'ticker': ticker,
                                    'name': stock.name,
                                    'lastPrice': price
                                }
                                stockData.update(keyStats)

                                # Save to Watchlist
                                Watchlist.objects.update_or_create(
                                    stock=stock,
                                    defaults=stockData
                                )

                                print('{} saved to Watchlist'.format(ticker))
                                results.append(stockData)
                                printTable(stockData)

if results:
    today = date.today().strftime('%m-%d')
    writeCSV(results, 'trend/trend_chasing_{}.csv'.format(today))

    # Tweet
    tweet = ""
    for i, data in enumerate(results):
        ticker = '${}'.format(data['ticker'])
        ttmEPS = data['ttmEPS']
        day5ChangePercent = data['day5ChangePercent']
        tweet_data = "{} ttmEPS: {}, 5dayChange: {} \n".format(ticker, ttmEPS, day5ChangePercent)
        tweet = tweet + tweet_data

    send_tweet(tweet, True)