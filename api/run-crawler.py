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

import requests
from lxml import etree

class handler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.send_header('Content-type', 'text/plain')
    self.end_headers()
    self.wfile.write(str(datetime.now().strftime('%Y-%m-%d %H:%M:%S')).encode())
    return

  def main():
    currentTime = datetime.now()
    logging.info("=== Start ==================================")
    
    # for correctness check, uncomment this
    # endTime is obsolete for complete checks starting from 0.7
    logging.info("=== Finish ==================================")
