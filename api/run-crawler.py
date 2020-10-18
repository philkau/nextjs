#!/usr/bin/python
# -*- coding: utf-8 -*-

from http.server import BaseHTTPRequestHandler
import os
import json
import csv
import time
import logging

from datetime import date, datetime
from pymongo import MongoClient
from urllib.parse import urlparse, parse_qs

import requests
from lxml import etree

class handler(BaseHTTPRequestHandler):

  def do_GET(self):
    # Parse Query String
    query_string = urlparse(self.path).query
    is_debug = False
    if (query_string != ''):
      self.params = parse_qs(query_string)
      if ('debug' in self.params and self.params['debug'][0] == 'true'):
        is_debug = True
    else:
      self.params = {}

    # connect to Mongo
    client = MongoClient(os.environ.get('NEXT_PUBLIC_MONGO_URL'))
    db = client.kandan
    collection = db.predictions
    
    # Find the uncompleted predictions.
    cursor = collection.find({"isCompleted": False})
    totalCount = cursor.count()
    print (f"There are {totalCount} predictions to be updated.")

    # get all avoid to lost the connection.
    documents = list(cursor)

    counter = 0

    for document in documents:
      try:
        counter = counter + 1
        print (f"Progress => {counter}/{totalCount}")
        # there's an extra 'u', not sure if it will work
        id = document['_id']
        target = [document['stockId']]
        predictor = document['userName']
        targetStockID = target[0]
        targetStartPrice = document.get('startPrice')
        confidence = document['confidence']
        bearOrBull = document.get('bearOrBull')
        predictionHigh = document['highPrice']
        predictionLow = document['lowPrice']
        targetStartTime = document['startTime']
        numOfFollowers = len(document['followers'])

        # dirty code to skip predictions that have no start price, which shouldn't exist
        # dirty code to skip predictions that don't match 0.7
        if not targetStartPrice:
          continue
        if not predictionHigh:
          continue

        print (f"ID: {id}")
        print (f"PREDICTOR: {predictor.encode('utf-8')}")
        print (f"TARGET STOCKID: {targetStockID}")
        print (f"TARGET CONFIDENCE: {confidence}")
        print (f"TARGET BEARORBULL: {bearOrBull}")
        print (f"TARGET HIGH: {predictionHigh}")
        print (f"TARGET LOW: {predictionLow}")
        print (f"TARGET STARTIME: {targetStartTime}")
        print (f"NUMBER OF FOLLOWERS: {numOfFollowers}")
        print (f"TARGET STARTPRICE: {targetStartPrice}")
        
        currentTime = datetime.now()
        print (f"CURRENT TIME: {currentTime}")

        # probably very inefficient, but will do for now
        # find the end price
        data = self.get_data_from_yahoo(stock_id)
        
        if not data:
          print (f"FAULTY RESPONSE from YAHOO.")
          continue

        for row in data:
          if('z' in row):
            currentPrice = row['z']
          else:
            logging.warning("There is no current price from the api!! Return Value: ")
            logging.warning(unicode(json.dumps(row)))
            # It should use the dayHigh and dayLow.
            # So it couldn't be broken.
            # break

          # TODO: high & low price has weird bug, need to fix
          if ('h' in row and 'l' in row and is_float(row['h']) and is_float(row['l'])):
            dayHigh = row['h']
            dayLow = row['l']
          else:
            logging.warning("There are invalid high and low price from the api!! Return Value: ")
            logging.warning(unicode(json.dumps(row)))
            break

          if (not is_float(currentPrice)):
            currentPrice = f"{dayLow}-{dayHig}"

          logging.info("CURRENT PRICE in for: " + str(currentPrice))
          logging.info("MAX DAY HIGH in for: " + str(dayHigh))
          logging.info("MIN DAY LOW in for: " + str(dayLow))
          dayHigh = float(dayHigh)
          predictionHigh = float(predictionHigh)
          dayLow = float(dayLow)
          predictionLow = float(predictionLow)

          if(dayHigh >= predictionHigh or dayLow <= predictionLow):
            logging.info("*******This prediction is finished")
          if(dayHigh >= predictionHigh):
            endPrice = dayHigh
          else:
            endPrice = dayLow

          logging.info("NEW END PRICE: " + str(endPrice))
          predictionDuration = (currentTime - targetStartTime).days + 1
          dayHigh = float(dayHigh)
          predictionHigh = float(predictionHigh)
          targetStartPrice = float(targetStartPrice)
          logging.info("DURATION: " + str(predictionDuration))

          if not 'profitRate' in document:
            document['profitRate'] = 0

          # TODO: probably should use boolean
          if(bearOrBull > 0):
            if(dayHigh >= predictionHigh):
              profitRate = (predictionHigh - targetStartPrice) / predictionDuration / targetStartPrice * 100
              trophy = ((predictionHigh - targetStartPrice) * confidence) / predictionDuration / targetStartPrice * 100
              absProfit = (predictionHigh - targetStartPrice) / targetStartPrice * 100
              confidenceProfit = ((predictionHigh - targetStartPrice) * confidence) / targetStartPrice * 100
            else:
              profitRate = ((targetStartPrice - predictionLow) / predictionDuration) / targetStartPrice * 100 * -1
              trophy = (((targetStartPrice - predictionLow) * confidence) / predictionDuration) / targetStartPrice * 100 * -1
              absProfit = (targetStartPrice - predictionLow) / targetStartPrice * 100 * -1
              confidenceProfit = ((targetStartPrice - predictionLow) * confidence) / targetStartPrice * 100 * -1
          else:
            if(dayLow <= predictionLow):
              profitRate = (targetStartPrice - predictionLow) / predictionDuration / targetStartPrice * 100
              trophy = ((targetStartPrice - predictionLow) * confidence) / predictionDuration / targetStartPrice * 100
              absProfit = (targetStartPrice - predictionLow) / targetStartPrice * 100
              confidenceProfit = ((targetStartPrice - predictionLow) * confidence) / targetStartPrice * 100
            else:
              profitRate = ((predictionHigh - targetStartPrice) / predictionDuration) / targetStartPrice * 100 * -1
              trophy = (((predictionHigh - targetStartPrice) * confidence) / predictionDuration) / targetStartPrice * 100 * -1
              absProfit = (predictionHigh - targetStartPrice) / targetStartPrice * 100 * -1
              confidenceProfit = ((predictionHigh - targetStartPrice) * confidence) / targetStartPrice * 100 * -1

          # update predictions DB
          document['endTime'] = currentTime
          document['trophy'] = trophy
          document['profitRate'] = profitRate
          document['absProfit'] = absProfit
          document['confidenceProfit'] = confidenceProfit
          document['isCompleted'] = True
          document['endPrice'] = endPrice
          document['currentPrice'] = currentPrice
          # collection.save(document)
          logging.debug(document)

      except Exception as err:
        logging.error("Fail to process the prediction.")
        logging.error(err)

    stock_id = '2498'
    
    data = self.get_data_from_yahoo(stock_id)
    
    self.send_response(200)
    self.send_header('Content-type', 'text/plain')
    self.end_headers()
    
    self.wfile.write(json.dumps(data).encode("utf-8"))
    
    print (f"[{str(datetime.now().strftime('%Y-%m-%d %H:%M:%S')).encode()}] Finish")
    return

  def get_data_from_yahoo(self, stockId):
    try:
      url = 'https://tw.stock.yahoo.com/q/q?s=' + stockId
      xpath_stockName = '//center/table[2]/tr/td/table/tr[2]/td[1]/a'
      xpath_date = '//center/table[1]/tr[1]/td[2]/font'
      xpath_time = '//center/table[2]/tr/td/table/tr[2]/td[2]'
      xpath_lastPrice = '//center/table[2]/tr/td/table/tr[2]/td[3]/b'
      xpath_buyPrice = '//center/table[2]/tr/td/table/tr[2]/td[4]'
      xpath_sellPrice = '//center/table[2]/tr/td/table/tr[2]/td[5]'
      xpath_varible = '//center/table[2]/tr/td/table/tr[2]/td[6]/font'
      xpath_paperCount = '//center/table[2]/tr/td/table/tr[2]/td[7]'
      xpath_yesterdayPrice = '//center/table[2]/tr/td/table/tr[2]/td[8]'
      xpath_startPrice = '//center/table[2]/tr/td/table/tr[2]/td[9]'
      xpath_topPrice = '//center/table[2]/tr/td/table/tr[2]/td[10]'
      xpath_lowPrice = '//center/table[2]/tr/td/table/tr[2]/td[11]'

      req = requests.session()
      response = req.get(url, headers={'Accept-Language': 'zh-TW'})

      html = etree.HTML(response.text)
      date = html.xpath(xpath_date)[0].text.split(':')[1].strip()
      stockName = html.xpath(xpath_stockName)[0].text.strip().replace(stockId,"")
      time = html.xpath(xpath_time)[0].text.strip()

      item = {'stockId': stockId, 'd': date, 't': time,  'n': stockName}

      lastPriceText = html.xpath(xpath_lastPrice)[0].text.strip().replace(",","")
      if lastPriceText != u"－" and lastPriceText != "-":
        lastPrice = float(lastPriceText)
        item["z"] = lastPrice

      yesterdayPriceText = html.xpath(xpath_yesterdayPrice)[0].text.strip().replace(",","")
      if yesterdayPriceText != u"－" and yesterdayPriceText != "-":
        yesterdayPrice = float(yesterdayPriceText)
        item["y"] = yesterdayPrice

      topPriceText = html.xpath(xpath_topPrice)[0].text.strip().replace(",","")
      if topPriceText != u"－" and topPriceText != "-":
        topPrice = float(topPriceText)
        item["h"] = topPrice

      lowPrice = html.xpath(xpath_lowPrice)[0].text.strip().replace(",","")
      if topPriceText != u"－" and topPriceText != "-":
        lowPrice = float(topPriceText)
        item["l"] = lowPrice

      buyPriceText = html.xpath(xpath_buyPrice)[0].text.strip().replace(",","")
      if buyPriceText != u"－" and buyPriceText != "-":
        buyPrice = float(buyPriceText)
        item["buyPrice"] = buyPrice

      sellPriceText = html.xpath(xpath_sellPrice)[0].text.strip().replace(",","")
      if sellPriceText != u"－" and sellPriceText != "-":
        sellPrice = float(sellPriceText)
        item["sellPrice"] = sellPrice

      startPriceText = html.xpath(xpath_startPrice)[0].text.strip().replace(",","")
      if startPriceText != u"－" and startPriceText != "-":
        startPrice = float(startPriceText)
        item["startPrice"] = startPrice

      paperCountText = html.xpath(xpath_paperCount)[0].text.strip().replace(",","")
      if paperCountText != u"－" and paperCountText != "-":
        paperCount = int(paperCountText)
        item["paperCount"] = paperCount

      varible = html.xpath(xpath_varible)[0].text.strip()

      if varible.startswith(u'▽'):
        varible = -float(varible.encode('utf8')[3:])
      elif varible.startswith(u'△'):
        varible = float(varible.encode('utf8')[3:])

      item["varible"] = varible
    
      if ('debug' in self.params and self.params['debug'][0] == 'true'):
        print (f'URL: {url}')
        print (f'Response: {response}')
        print (f'HTML: {html}')
        print (f'Data: {json.dumps(item)}')
      return item

    except Exception as err:
      print (f'URL: {url}')
      print (f'Response: {response}')
      print (f'HTML: {html}')
      raise err

    return {}
    

