#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import json
import csv
import time
import logging

from datetime import date, datetime
from pymongo import MongoClient

import requests
from lxml import etree

def initialize():
    loggingFormat = '%(asctime)-15s [%(levelname)s] %(message)s'
    loggingTimeFormat = '%Y-%m-%d %H:%M:%S'
    loggingDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(loggingDir):
            os.makedirs(loggingDir)
    logFileName = '%s/sync_price-%s.log' % (loggingDir, datetime.now().strftime("%Y-%m-%d"))
    logging.basicConfig(
        format=loggingFormat, 
        datefmt=loggingTimeFormat, 
        level=logging.DEBUG,
        handlers=[logging.FileHandler(logFileName), logging.StreamHandler()])


def main():
    currentTime = datetime.now()
    logging.info("=== Start ==================================")
    
    # for correctness check, uncomment this
    # endTime is obsolete for complete checks starting from 0.7
    logging.info("=== Finish ==================================")

if __name__ == '__main__':
    initialize()
    main()
