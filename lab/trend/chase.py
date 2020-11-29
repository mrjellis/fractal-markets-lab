import django
from django.apps import apps
from dotenv import load_dotenv
import json
import os
import sys
from datetime import date
from .functions import *
from ..core.functions import chunks
from ..core.api import quoteStatsBatchRequest, getHistoricalEarnings, getPriceTarget
from ..core.output import printTable
from ..core.export import writeCSV
from ..twitter.tweet import send_tweet
import texttable
load_dotenv()
django.setup()

Stock = apps.get_model('database', 'Stock')
Trend = apps.get_model('database', 'Trend')
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
            volume = quote['volume'] if ('volume' in quote and quote['volume']) else 0
            previousVolume = quote['previousVolume'] if ('previousVolume' in quote and quote['previousVolume']) else 0

            critical = [changeToday, week52high, ttmEPS, volume, previousVolume]

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

            if (price > 1):
                if ((fromHigh < 105) and (fromHigh > 95)):
                    if (changeToday > 12):
                        if (volume > previousVolume):
                            priceTargets = getPriceTarget(ticker)
                            fromPriceTarget = round((price / priceTargets['priceTargetHigh']) * 100, 3) if (priceTargets and 'priceTargetLow' in priceTargets) else 0
                            avgPricetarget = priceTargets['priceTargetAverage'] if (priceTargets and 'priceTargetAverage' in priceTargets) else None
                            highPriceTarget = priceTargets['priceTargetHigh'] if (priceTargets and 'priceTargetHigh' in priceTargets) else None


                            # Save Trends to DB
                            Trend.objects.filter(stock=stock).update(                            
                                avgPricetarget=avgPricetarget,
                                highPriceTarget=highPriceTarget,
                                fromPriceTarget=fromPriceTarget,
                            )
                        
                            keyStats = {
                                'week52': stats['week52high'],
                                'ttmEPS': ttmEPS,
                                'peRatio': stats['peRatio'],
                                'day5ChangePercent': day5ChangePercent,
                                'month1ChangePercent': round(stats['month1ChangePercent'] * 100, 2) if ('month1ChangePercent' in stats) else None,
                                'ytdChangePercent': round(stats['ytdChangePercent'] * 100, 2) if ('ytdChangePercent' in stats) else None,
                                'day50MovingAvg': stats['day50MovingAvg'],
                                'day200MovingAvg': stats['day200MovingAvg'],                            
                                'highPriceTarget': highPriceTarget,
                                'fromPriceTarget': fromPriceTarget,
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

                            stockData['changeToday'] = changeToday                        
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
        changeToday = data['changeToday']
        tweet_data = "{} +{}% \n".format(ticker, changeToday)
        tweet = tweet + tweet_data

    send_tweet(tweet, True)