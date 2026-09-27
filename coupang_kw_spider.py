#
#
#
# import sys
# import os
# import re
# from bs4 import BeautifulSoup
# import pytz
# import datetime
# import scrapy
# import json
# import pymysql
# import mysql.connector
# import requests
# import random
# import asyncio
# import time
# import cloudscraper
# import urllib.parse
# from urllib.parse import quote_plus
# from scrapy.selector import Selector
# from scrapy.loader import ItemLoader
# from datetime import datetime
# from scrapy.spidermiddlewares.httperror import HttpError
# from twisted.internet.error import DNSLookupError
# from twisted.internet.error import TimeoutError, TCPTimedOutError
# from twisted.internet import reactor
# from scrapy.crawler import CrawlerRunner
# from scrapy.utils.log import configure_logging
# from scrapy.http import HtmlResponse
# from w3lib.html import remove_tags
# from slugify import slugify
# from itertools import repeat
# from scrapy.spiders.init import InitSpider
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from mysql.connector import Error
# import requests
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
# import time
# import json
#
# from utils import utils
# from db.db_action import DBAction
# # import spacy
# # from spacy import displacy
# import time
# from urllib.parse import quote_plus
# from scrapy import Selector
# import undetected_chromedriver as uc
# import re
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import hashlib
# import time
# from requests.adapters import HTTPAdapter
# from urllib3.util.retry import Retry
# # from deep_translator import GoogleTranslator
#
# def create_hash_id(text):
#     return hashlib.md5(text.encode()).hexdigest()
# # =========================
# # CONFIG
# # =========================
# CHROME_PROFILE_PATH = r"C:\selenium-profile"
# BASE_URL = "https://www.coupang.com/np/search?q={}"
# WAIT_TIME = 10
# from googletrans import Translator
#
# # NER = spacy.load("en_core_web_sm")
# translator = Translator()
#
# currentdir = os.path.dirname(os.path.realpath(__file__))
# parentdir = os.path.dirname(currentdir)
# sys.path.append(parentdir)
#
# SETTINGS = scrapy.utils.project.get_project_settings()
# def get_coupang_cookies():
#     """
#     Opens coupang.com using Selenium and returns cookies as a dictionary.
#     """
#     chrome_options = Options()
#     # chrome_options.add_argument("--headless")  # Uncomment for headless mode
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--disable-blink-features=AutomationControlled")
#     chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
#     chrome_options.add_experimental_option('useAutomationExtension', False)
#     chrome_options.add_argument(
#         "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#     )
#
#     driver = webdriver.Chrome(
#         service=Service(ChromeDriverManager().install()),
#         options=chrome_options
#     )
#
#     # Remove the navigator.webdriver flag
#     driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
#
#     try:
#         driver.get("https://www.coupang.com/")
#         print("Page loaded. Waiting for cookies...")
#         time.sleep(5)
#
#         selenium_cookies = driver.get_cookies()
#         cookie_dict = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
#
#         print(f"Retrieved {len(cookie_dict)} cookies")
#         return cookie_dict
#
#     except Exception as e:
#         print(f"Error: {e}")
#         return {}
#     finally:
#         driver.quit()
# def create_session_with_retries():
#     """Create a session with retry logic"""
#     session = requests.Session()
#
#     retry_strategy = Retry(
#         total=3,
#         backoff_factor=2,
#         status_forcelist=[429, 500, 502, 503, 504],
#         allowed_methods=["GET"]
#     )
#
#     adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
#     session.mount("http://", adapter)
#     session.mount("https://", adapter)
#
#     return session
#
# def extract_all_products(sel):
#
#     scripts = sel.xpath('//script[contains(text(), "__next_f.push")]/text()').getall()
#
#     all_products = []
#
#     for script in scripts:
#         # Find all push arguments
#         matches = re.findall(r'self\.__next_f\.push\(\[\d+,"([\s\S]*?)"\]\)', script)
#
#         for m in matches:
#             try:
#                 decoded = bytes(m, "utf-8").decode("unicode_escape")
#
#                 # Look for "products": [ ... ]
#                 products_match = re.search(r'"products"\s*:\s*(\[)', decoded)
#                 if not products_match:
#                     continue
#
#                 start_idx = products_match.start(1)
#                 # Find the matching closing bracket using a counter
#                 bracket_count = 1
#                 end_idx = start_idx + 1
#                 while end_idx < len(decoded) and bracket_count > 0:
#                     if decoded[end_idx] == '[':
#                         bracket_count += 1
#                     elif decoded[end_idx] == ']':
#                         bracket_count -= 1
#                     end_idx += 1
#
#                 products_json_str = decoded[start_idx:end_idx]
#                 products_list = json.loads(products_json_str)
#
#                 # Each item in products_list is a product dict
#                 for product in products_list:
#                     if isinstance(product, dict):
#                         # Extract relevant fields
#                         try:
#                             i18nOriginalPrice = product.get('priceArea', {}).get('i18nOriginalPrice',{}).get("amount",0)
#                             if not i18nOriginalPrice or i18nOriginalPrice == '0' :
#                                 i18nOriginalPrice = product.get('priceArea', {}).get('i18nSalesPrice',{}).get("amount",0)
#
#                             product_info = {
#                                 'itemId': product.get('legacyProductId', ""),
#                                 'price_sp': product.get('priceArea', {}).get('i18nSalesPrice',{}).get("amount",0),
#                                 'price_rp': i18nOriginalPrice,
#                                 'product_url': 'https://www.coupang.com' + product.get('link', ''),
#                                 'ratingRatio': product.get('reviewArea', {}).get('ratingRatio'),
#                             }
#                             all_products.append(product_info)
#                         except:
#                             continue
#             except Exception as e:
#                 print(e)
#                 # Skip malformed chunks
#                 continue
#
#     return all_products
# class NYKAAKWSpider(InitSpider):
#     name = "coupang_kw_spider"
#
#     def __init__(self, inputs,
#                  **kw):  # pf_id=None, location_id=None, location=None, pincode=None, brand_id=None, brand_name=None, keyword_id=None, keyword=None, page=1, location_search="0",
#         super(NYKAAKWSpider, self).__init__(**kw)
#         print("PF ID: {0} ".format(inputs.get("pf_id")))
#         print("KEYWORD ID: {0} ".format(inputs.get("keyword_id")))
#         print("KEYWORD:  {0} ".format(inputs.get("keyword")))
#         print("LOCATION:  {0} ".format(inputs.get("location")))
#         print("LOCATION ID: {0} ".format(inputs.get("location_id")))
#         print("PINCODE:  {0} ".format(inputs.get("pincode")))
#         print("PAGE: {0} ".format(inputs.get("page")))
#         print("Site: {0} ".format(self.name))
#
#         self.env = inputs.get("env")
#         self.site = self.name
#         self.db_name = inputs.get("db_name")
#         self.crawl_id = int(inputs.get("crawl_id"))
#         self.pf_id = int(inputs.get("pf_id"))
#         self.location_id = int(inputs.get("location_id"))
#         self.location = inputs.get("location")
#         self.pincode = str(inputs.get("pincode"))
#         self.keyword = inputs.get("keyword")
#         self.keyword_id = int(inputs.get("keyword_id"))
#         if inputs.get('brand_id') and inputs.get('brand_id') != 'None':
#             self.brand_id = int(inputs.get("brand_id"))
#         else:
#             self.brand_id = 0
#         self.brand_name = inputs.get("brand_name")
#         self.page = int(inputs.get("page"))
#         self.location_search = inputs.get("location_search")
#
#         self.tz = inputs.get("tz")
#         self.current_time = inputs.get("current_time")
#         self.dt = inputs.get("dt")
#         self.base_dir = "C:/var/logs/" + self.site
#         self.output_file = self.base_dir + "/output/out_" + self.pincode + "_" + self.keyword + ".txt"
#
#         self.db_table_name = "coupang_crawl_kw"
#
#         self.output_cols = ["pf_id", "crawl_id", "keyword", "keyword_id", "brand_id", "brand_name", "brand_crawl",
#                             "web_pid", "pdp_title_value", "position",
#                             "price_rp", "price_sp", "pdp_rating_value", "pdp_rating_count", "pdp_image_url",
#                             "pdp_page_url", "pdp_discount_value", "pdp_sponsored",
#                             "location_id", "location_name", "pincode", "created_by", "created_on", "modified_by",
#                             "modified_on", "status", "page", "grammage",
#                             "pdp_title_eng", "keyword_eng", "unique_id"]
#
#         self.visit_count = str(random.choice([10, 11, 12, 13, 14, 15, 16]))
#
#         self.db_action = DBAction()
#         try:
#             self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
#             self.cursor = self.connection.cursor()
#         except mysql.connector.Error as error:
#             self.logger.error("Connection error with the database Error:{}:{}".format(error.errno, error.strerror))
#             print("Connection error with the database Error{}:{}".format(error.errno, error.strerror))
#
#         self.keyword_search()
#
#     def keyword_search(self):
#         keyword = self.keyword
#         self.logger.info("Crawl Keyword: " + keyword)
#         encoded = quote_plus(keyword, encoding="utf-8")
#
#         proxy_token='4a5d29bbe6444c26a54283420230efeb8bb7c973818'
#         proxies_sc_do = {
#             'http': f'http://{proxy_token}:@proxy.scrape.do:8080?geoCode=kr',
#             'https': f'http://{proxy_token}:@proxy.scrape.do:8080?geoCode=kr',
#         }
#
#         proxies_scra_api = {
#             "http": "http://scraperapi:1ddac84e2ee5e0e1d224be6dee101d98@proxy-server.scraperapi.com:8001?geoCode=kr&premium=true",
#             "https": "http://scraperapi:1ddac84e2ee5e0e1d224be6dee101d98@proxy-server.scraperapi.com:8001?geoCode=kr&premium=true"
#         }
#
#         proxies_list = [proxies_sc_do]
#         proxies = random.choice(proxies_list)
#         url = BASE_URL.format(quote_plus(self.keyword))
#         headers = {
#             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
#             "Accept-Encoding": "gzip, deflate, br",  # ✅ Removed 'zstd' to fix decoding error
#             "Accept-Language": "en-US,en;q=0.9",
#             "Connection": "keep-alive",
#             # "Cookie": "x-coupang-target-market=KR; x-coupang-accept-language=ko-KR;",
#             "Host": "www.coupang.com",
#             "Referer": "https://www.coupang.com/np/search",
#             "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
#             "sec-ch-ua-mobile": "?0",
#             "sec-ch-ua-platform": '"Windows"',
#             "Sec-Fetch-Dest": "document",
#             "Sec-Fetch-Mode": "navigate",
#             "Sec-Fetch-Site": "same-origin",
#             "Sec-Fetch-User": "?1",
#             "Upgrade-Insecure-Requests": "1",
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
#         }
#
#         session = create_session_with_retries()
#         cookies = get_coupang_cookies()
#         response = session.get(
#             url,
#             headers=headers,
#             cookies=cookies,
#             timeout=60,  # Increased timeout
#             verify=False
#         )
#         sel = Selector(response)
#         data_html = extract_all_products(sel)
#
#         new_json = sel.xpath('//script[@type="application/ld+json"]/text()').get("")
#         data_json = json.loads(new_json)
#         self.parse_list_page(data_json,data_html)
#
#         # return data
#
#     def parse_list_page(self, data,data_html):
#
#         print("*******************************************************************************************")
#         print(data, "shagun")
#         print("//////////////////////////////////////////////////////////////////////////////////////")
#         if data is None:
#             print(f"❌ No data found for Web_pid {self.keyword}")
#             return "Not Found"
#         print("data is ", data)
#         # page = 1
#         items = list()
#         spons_index = 1
#         org_index = 1
#         entity_list = data.get("mainEntity",{}).get("itemListElement",[])
#
#         for idx, item in enumerate(entity_list):
#             item_data = item.get('item', {})
#
#             product_url = item_data.get('url','')
#             for data_html_i in data_html:
#                 if str(data_html_i['itemId']) in product_url:
#                     index = str(data_html_i['itemId'])
#                     product_name = item_data["name"]
#                     spons_flag = 0
#
#                     try:
#                         spons_ele = item_data["rData"]["entityList"][idx]["entity"]["isAds"]
#
#                         if spons_ele:
#                             spons_flag = 1
#                             position = spons_index
#                             spons_index += 1
#                         else:
#                             spons_flag = 0
#                             position = org_index
#                             org_index += 1
#                     except (KeyError, IndexError, TypeError) as e:
#                         spons_flag = 0
#                         position = org_index
#                         org_index += 1
#                         print(f"⚠️ Error processing entity at index {idx}: {e}")
#
#                     try:
#                         selling_price = item_data.get("offers", {}).get("price", "")
#                     except (KeyError, IndexError, TypeError):
#                         selling_price = None
#
#                     try:
#                         mrp = data_html_i['price_rp']
#                     except (KeyError, IndexError, TypeError):
#                         mrp = selling_price
#
#                     if selling_price > mrp:
#                         mrp = selling_price
#
#                     try:
#                         rating = item_data.get("aggregateRating", {}).get("ratingValue", "")
#                     except KeyError:
#                         rating = None
#
#                     try:
#                         ratings = item_data.get("aggregateRating", {}).get("reviewCount", "")
#                     except KeyError:
#                         ratings = None
#
#
#                     try:
#                         img_url = item_data["image"]
#                     except KeyError:
#                         img_url = None
#
#                     def google_translate_web(text, source='ko', target='en'):
#                         try:
#                             if not text:
#                                 return ""
#                             url = "https://translate.googleapis.com/translate_a/single"
#                             params = {
#                                 "client": "gtx",
#                                 "sl": source,
#                                 "tl": target,
#                                 "dt": "t",
#                                 "q": text
#                             }
#                             response = requests.get(url, params=params, timeout=30)
#                             data = response.json()
#                             return ''.join([sentence[0] for sentence in data[0]])
#                         except Exception as e:
#                             print("[Google WebTranslate Error]", e)
#                             return text
#
#                     product_eng = google_translate_web(product_name, source='ko', target='en')
#                     keyword_eng = google_translate_web(self.keyword, source='ko', target='en')
#                     brand_crawl = product_name.split()[0] if product_name else ''
#                     brand_name = google_translate_web(brand_crawl, source='ko', target='en')
#
#                     unique_id = create_hash_id(product_url)
#
#
#
#                     try:
#                         if int(mrp) > 0 and int(selling_price) > 0:
#                             pdp_discount_value = round(((int(mrp) - int(selling_price)) / int(mrp)) * 100, 2)
#                         else:
#                             pdp_discount_value = 0.0
#                     except (ValueError, AttributeError, ZeroDivisionError):
#                         pdp_discount_value = 0.0
#
#                     item = {
#                         "pf_id": self.pf_id,
#                         "crawl_id": self.crawl_id,
#                         "keyword": self.keyword,
#                         "keyword_eng": keyword_eng,
#                         "keyword_id": self.keyword_id,
#                         "brand_id": self.brand_id,
#                         'brand_name': brand_name if brand_name else self.brand_name,
#                         "brand_crawl": product_name.split()[0] if product_name else '',
#                         "web_pid": index,
#                         "pdp_title_value": product_name,
#                         "pdp_title_eng": product_eng,
#                         "position": position,
#                         "price_rp": mrp,
#                         "price_sp": selling_price,
#                         "pdp_rating_value": rating,
#                         "pdp_rating_count": ratings,
#                         "pdp_image_url": img_url,
#                         "pdp_page_url": product_url,
#                         "pdp_discount_value": pdp_discount_value,
#                         "pdp_sponsored": spons_flag,
#                         "location_id": self.location_id,
#                         "location_name": self.location,
#                         "pincode": self.pincode,
#                         "created_by": "System",
#                         "created_on": self.current_time,
#                         "modified_by": None,
#                         "modified_on": self.current_time,
#                         "status": 1,
#                         "page": self.page,
#                         'grammage': '',
#                         'unique_id': unique_id
#                     }
#
#                     items.append(item)
#                     break
#
#         records = list()
#         columns = self.output_cols
#         for item in items:
#             # Create Raw file without header
#             utils.create_raw_file(self.output_file, item.keys(), item)
#             # Converting dict list into list of tuple
#             record = tuple(item.get(col, None) for col in columns if col in item)
#             records.append(record)
#
#             # Create Header file
#         item = items[0]
#         output_dir = self.base_dir + "/output"
#         output_filename = "header.txt"
#         output_file = output_dir + "/" + output_filename
#         header_row = "|".join(item.keys()) + "\r"
#         utils.create_file(output_file, header_row)
#
#         tbl_columns_str = "" + ",".join(self.output_cols) + ""
#         values_list = []
#         values_list.extend(repeat("%s", len(self.output_cols)))
#         tbl_columns_val = ",".join(values_list)
#
#         self.logger.info("Data inserting")
#         mySql_insert_query = """INSERT INTO coupang_crawl_kw (""" + tbl_columns_str + """)  VALUES (""" + tbl_columns_val + """)"""
#         # print("Aatif",mySql_insert_query)
#         try:
#             self.cursor.executemany(mySql_insert_query, records)
#             print("utka", records)
#             products_count = self.cursor.rowcount
#             self.connection.commit()
#         except Error as err:
#             self.logger.error("Database Error: " + str(err))