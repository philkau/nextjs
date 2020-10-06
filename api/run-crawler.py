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
from urllib.parse import parse_qs

import requests
from lxml import etree

class handler(BaseHTTPRequestHandler):

  def do_GET(self):
    print (f"[{str(datetime.now().strftime('%Y-%m-%d %H:%M:%S')).encode()}] Start...")
    if (self.path is not None):
      self.params = parse_qs(self.path)
    else:
      self.params = {}
    data = self.get_data_from_yahoo('2498')
    
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
        print (f'Data: {json.dumps(item)}')
      return item

    except Exception as err:
      print (f'URL: {url}')
      print (f'Response: {response}')
      print (f'HTML: {html}')
      raise err

    return {}
    

