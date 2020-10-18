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
    
    # for correctness check, uncomment this
    # endTime is obsolete for complete checks starting from 0.7
    #cursor = collection.find({"isCompleted": False, "endTime": {"$lte": currentTime}})
    total_cursor = collection.find({"isCompleted": False})
    totalCount = total_cursor.count()
    logging.info(f"There are {totalCount} predictions to be updated.")

    predictions_cursor = collection.find({"isCompleted": False, "currentPriceUpdateTime": None}).sort("startTime").limit(1)
    new_predictions_totalCount = predictions_cursor.count()
    logging.info(f"There are {new_predictions_totalCount} new predictions to be updated.")

    if (new_predictions_totalCount == 0):
      predictions_cursor = collection.find({"isCompleted": False, "currentPriceUpdateTime": {"$ne":None}}).sort("currentPriceUpdateTime").limit(1)
      elder_predictions_totalCount = predictions_cursor.count()
      logging.info(f"There are {elder_predictions_totalCount} elder predictions to be updated.")

    # cursor = collection.aggregate([
    #     {
    #         "$match": {"isCompleted": False}
    #     },
    #     {
    #         "$addFields": {
    #             "sortField": {
    #                 "$cond": {
    #                     "if": { "$ne": [ "$checkTime", None ] },
    #                     "then": "$checkTime",
    #                     "else": "$startPriceTime"
    #                 }
    #             }
    #         }
    #     },
    #     {
    #         "$sort": {"sortField": 1}
    #     },
    #     {
    #         "$limit": 2
    #     }])

    documents = list(predictions_cursor)

    if (len(documents) == 0):
      logging.info("There is nothing to update.")
      return
    else:
      document = documents[0]
      logging.debug(document)

    prediction_updated = False
    try:
      id = document['_id']
      target = [document['stockId']]
      predictor = document['userName'].encode('utf-8')
      targetStockID = target[0]
      # endtime obsolete as of 0.7
      #targetEndTime = document['endTime']
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
        logging.error(f"The start price is empty!! ID:{id}")
        return
      if not predictionHigh:
        logging.error(f"The prediction high is empty!! ID:{id}")
        return

      currentTime = datetime.now()
      logging.info("CURRENT TIME: " + str(currentTime))

      # find the current price
      stock_info = self.get_data_from_yahoo(targetStockID)

      if not stock_info:
        logging.warning("FAULTY RESPONSE from TWSE, skipping")
        return

      if('z' in stock_info):
        currentPrice = stock_info['z']
      else:
        logging.warning(f"There is no current price from the api!! Return Value: {stock_info}")
        # It should use the dayHigh and dayLow.
        # So it couldn't be broken.
        return

      # TODO: high & low price has weird bug, need to fix
      if ('h' in stock_info and 'l' in stock_info and self.is_float(stock_info['h']) and self.is_float(stock_info['l'])):
        dayHigh = stock_info['h']
        dayLow = stock_info['l']
      else:
        logging.warning(f"There is no current price from the api!! Return Value: {stock_info}")
        return

      if (not self.is_float(currentPrice)):
        currentPrice = str(dayLow) + "-" + str(dayHigh);

      #print("DATA:" + str(data))
      logging.info("CURRENT PRICE in for: " + str(currentPrice))
      logging.info("MAX DAY HIGH in for: " + str(dayHigh))
      logging.info("MIN DAY LOW in for: " + str(dayLow))

      # new trophy calculation for 0.7 spec
      # when high || low is met
      # type cast to float on the prices
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
        document['checkTime'] = currentTime
        collection.save(document)
        prediction_updated = True
        logging.debug(document)

        # update users DB
        userCollection = db.users
        userCursor = userCollection.find({"name": predictor})
        for userDocument in userCursor:
          userDocument['trophy'] += trophy
          userDocument['profitRate'] += profitRate
          userDocument['absProfit'] += absProfit
          userDocument['confidenceProfit'] += confidenceProfit
          userDocument['finishedPredictionCount'] += 1
          userDocument['ongoingPredictionCount'] -= 1
          userDocument['avgTrophy'] = userDocument['trophy']/userDocument['finishedPredictionCount']
          userDocument['avgProfitRate'] = userDocument['profitRate']/userDocument['finishedPredictionCount']
          userDocument['avgAbsProfit'] = userDocument['absProfit']/userDocument['finishedPredictionCount']
          userDocument['avgConfidenceProfit'] = userDocument['confidenceProfit']/userDocument['finishedPredictionCount']
          if(trophy >=0):
            userDocument['experience'] += (numOfFollowers + 1) * trophy
            userDocument['currentStreak'] += 1
            userDocument['successPredictionCount'] += 1
            if(userDocument['trophy'] >= userDocument['highestTrophy']):
              userDocument['highestTrophy'] = userDocument['trophy']
            if(userDocument['currentStreak']  >= userDocument['highestStreak']):
              userDocument['highestStreak'] = userDocument['currentStreak']
          else:
            userDocument['currentStreak'] = 0
            userDocument['failPredictionCount'] +=1
          userCollection.save(userDocument)
      else:
        document['currentPrice'] = currentPrice
        document['currentPriceUpdateTime'] = currentTime
        document['checkTime'] = currentTime
        collection.save(document)
        prediction_updated = True
        logging.info(f"******This prediction {id} is not yet finished. Update current price.")

        
      self.send_response(200)
      self.send_header('Content-type', 'text/plain')
      self.end_headers()
      self.wfile.write(json.dumps(document).encode("utf-8"))
      
    except Exception as err:
      logging.exception("Fail to process the prediction.")
      raise err
      if (document and not prediction_updated):
        document['checkTime'] = currentTime
        collection.save(document)

    logging.info("=== Finish ==================================")

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

  def is_float(self, s):
    try:
        float(s)
        return True
    except ValueError:
        return False


