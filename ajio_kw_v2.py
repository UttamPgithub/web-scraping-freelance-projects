import sys
import os
import re
import pytz
import datetime
import scrapy
import json
import pymysql
import mysql.connector
import requests
import random
import time
import urllib.parse

from requests.utils import requote_uri
from scrapy.selector import Selector
from scrapy.loader import ItemLoader
from datetime import datetime
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError, TCPTimedOutError
from twisted.internet import reactor
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.http import HtmlResponse
from w3lib.html import remove_tags
from slugify import slugify
from itertools import repeat
from scrapy.spiders.init import InitSpider
from utils import utils
from db.db_action import DBAction

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

SETTINGS = scrapy.utils.project.get_project_settings()


class AJIOKWSpider(InitSpider):
    name = "ajio_kw_v2"
    handle_httpstatus_list = [400]

    allowed_domains = ["ajio.com"]
    start_urls = ["https://ajio.com/"]
    custom_settings = {
            # specifies exported fields and order
            "DOWNLOAD_TIMEOUT": 60000,
            "DOWNLOAD_MAXSIZE": 12406585060,
            "DOWNLOAD_WARNSIZE": 0,
            "CONCURRENT_REQUESTS": 1,
            "CONCURRENT_REQUESTS_PER_DOMAIN":1,
            "CONCURRENT_REQUESTS_PER_IP":1,
            "HTTPPROXY_ENABLED": True,
            "DOWNLOADER_MIDDLEWARES" : {
                "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
                "scrapy_web_crawlers.middlewares.RandomUserAgentMiddleware": 1
                },
        }    
    HOME_URL = "https://www.ajio.com/"
    
    def __init__(self, inputs, **kw): # pf_id=None, location_id=None, location=None, pincode=None, brand_id=None, brand_name=None, keyword_id=None, keyword=None, page=1, location_search="0",crawl_id=None, **kw):
        super(AJIOKWSpider, self).__init__(**kw)

        print("PF ID: {0} ".format(inputs.get("pf_id")))
        print("KEYWORD ID: {0} ".format(inputs.get("keyword_id")))
        print("KEYWORD:  {0} ".format(inputs.get("keyword")))
        print("LOCATION:  {0} ".format(inputs.get("location")))
        print("LOCATION ID: {0} ".format(inputs.get("location_id")))
        print("PINCODE:  {0} ".format(inputs.get("pincode")))
        print("PAGE: {0} ".format(inputs.get("page")))
        print("Site: {0} ".format(self.name))

        self.env = inputs.get("env")
        self.site = self.name
        self.db_name = inputs.get("db_name")
        self.crawl_id = int(inputs.get("crawl_id"))
        self.pf_id = int(inputs.get("pf_id"))        
        self.location_id = int(inputs.get("location_id"))
        self.location = inputs.get("location")
        self.pincode = str(inputs.get("pincode")) 
        self.keyword = inputs.get("keyword")
        self.keyword_id = int(inputs.get("keyword_id"))
        self.brand_id = int(inputs.get("brand_id"))
        self.brand_name = inputs.get("brand_name")
        self.page = int(inputs.get("page"))
        self.location_search = inputs.get("location_search")
        self.sponsored_index = 0
        self.index = 0

        self.tz = inputs.get("tz")
        self.current_time = inputs.get("current_time")
        self.dt = inputs.get("dt")
        self.base_dir = "C:/var/logs/"+self.site
        self.output_file = self.base_dir+"/output/out_"+self.pincode+"_"+self.keyword+".txt"

        self.db_table_name = "ajio_crawl_kw"       
        
        self.output_cols = [
                                "pf_id","crawl_id","page","keyword","keyword_id","brand_id","brand_name","brand_crawl","web_pid","pdp_title_value",
                                "position","price_sp","price_rp", "pdp_rating_value","pdp_rating_count","pdp_image_url","pdp_page_url","pdp_discount_value",
                                "pdp_sponsored","sponsored_brand", "location_id","location_name","pincode","created_by","created_on","status"
                            ]
        
        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as error:
            self.logger.error("Connection error with the database Error:{}:{}".format(error.errno, error.strerror))
            print("Connection error with the database Error{}:{}".format(error.errno, error.strerror))

        self.keyword_search()
        
    # def init_request(self):    
    #     #Home Page Request
    #     self.logger.info("Home Page Request")        
    #     session = requests.Session()
    #     yield scrapy.Request(url=self.HOME_URL, 
    #                         method="GET",
    #                         headers={
    #                                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
    #                                 },
    #                 		cookies={},
    #                         callback=self.keyword_search, 
    #                         errback=self.errback_httpbin,
    #                         priority=1
    #                         )

    def keyword_search(self):

        # webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        # filename = "/%s-%s.html" % (str(self.pincode), self.site)
        # utils.save_source_content(webpage_dir, filename, response.body)
        
        # self.logger.info("Got successful response from {}".format(response.url)) 
        # self.logger.info(response.request.headers)

        #for crawl_input in self.crawl_inputs:
        keyword = self.keyword
        self.logger.info("Crawl Keyword : "+keyword)          

        headers = {
            'Referer': 'https://www.ajio.com/',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

        params = {
            'text': self.keyword,
        }

        response = requests.get('https://www.ajio.com/search/', params=params, headers=headers)

        print('traily***', response)
        print(response.text)
        self.parse_list_page(response,self.keyword)


    def parse_list_page(self, response, keyword):
        print('trailytics***', response.text)
        # print('trailytics-----', response.status_code)
        page = 1
        items = list()
        # self.logger.info("Got successful response from {}".format(response.url))
        # self.logger.info(response.request.headers)
        
        # webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        # filename = "/%s-%s-%s-%s.html" % (str(page), str(self.pincode), self.site, keyword)
        # utils.save_source_content(webpage_dir, filename, response.body)
        
        # self.logger.info("Saved file %s" % filename)
        # self.logger.info("Data Extraction Start")

        response = Selector(text=response.text)
        script = response.xpath("//body").re_first(r'<script>\s*window\.__PRELOADED_STATE__\s*=\s*(.*?)\n\s*<\/script>')
        script = script.replace("}};", "}}") #.replace("\\r", "").replace("\\n", "").replace("\\","").replace('="', '=\\"').replace('">', '\\">').replace("\\u0003c","<").replace("u003c", "<")
        if script is not None:
            script = script.strip()
            json_response = json.loads(script)
            print('traily_json_response***', json_response)
            if '"grid":' in script:
                grid = json_response["grid"]
                results = grid["results"]
                products = grid["entities"]
                rank = 1
                for result in results:
                    product = products[result]

                    id = product["code"]
                    web_pid = product["code"]

                    title = product["name"]
                    fnlColorVariantData = product["fnlColorVariantData"]
                    brand_name = fnlColorVariantData["brandName"]

                    pdp_page_url = "https://www.ajio.com"+product["url"]

                    images = product["images"]
                    image_url = images[0]["url"]

                    price = product["price"]["value"]                    
                    mrp = product["wasPriceData"]["value"]
                    print('mrp:-----', mrp)

                    try:
                        discount = product["discountPercent"]
                        discount = int(discount.replace("% off", ""))
                    except KeyError as ke:
                        discount = 0
   
                    savings = mrp-price

                    try:
                        rating = product["averageRating"]
                    except:
                        rating = 0

                    try:
                        rating_count = product["ratingCount"]
                    except:
                        rating_count = 0 
                        
                    try:
                        if product["adsData"]:
                            sponsored = 1
                        else:
                            sponsored = 0
                    except:
                        sponsored = 0

                    sponsored_brand = ""                

                    review_count = 0                
                    in_stock = 1
                    seller_name = "" 


                    item = dict()
                    item["pf_id"] = self.pf_id
                    item["crawl_id"] = self.crawl_id
                    item["page"] = page
                    item["keyword"] = self.keyword
                    item["keyword_id"] = self.keyword_id            
                    item["brand_id"] = self.brand_id
                    item["brand_name"] = self.brand_name
                    item["brand_crawl"] = brand_name
                    item["web_pid"] = web_pid if web_pid else ""
                    item["pdp_title_value"] = title if title else ""
                    item["position"] = rank
                    item["price_rp"] = mrp if mrp else 0
                    item["price_sp"] = price if price else 0
                    item["pdp_rating_value"] = rating if rating else 0
                    item["pdp_rating_count"] = rating_count if rating_count else 0
                    item["pdp_image_url"] = image_url if image_url else ""
                    item["pdp_page_url"] = pdp_page_url
                    item["pdp_discount_value"] = discount
                    item["pdp_sponsored"] = sponsored
                    item["sponsored_brand"] = sponsored_brand   
                    item["location_id"] = self.location_id
                    item["location_name"] = self.location
                    item["pincode"] = self.pincode
                    item["created_by"] = "System"
                    item["created_on"] = self.current_time
                    item["status"] = 1 

                    item = utils.clean_item_data(item)
                    rank = rank+1
                    items.append(item)
            else:
                item = dict()
                item["pf_id"] = self.pf_id
                item["crawl_id"] = self.crawl_id
                item["page"] = page
                item["keyword"] = self.keyword
                item["keyword_id"] = self.keyword_id            
                item["brand_id"] = self.brand_id
                item["brand_name"] = self.brand_name
                item["brand_crawl"] = ""
                item["web_pid"] = ""
                item["pdp_title_value"] = ""
                item["position"] = 0
                item["price_rp"] = 0
                item["price_sp"] = 0
                item["pdp_rating_value"] = 0
                item["pdp_rating_count"] = 0
                item["pdp_image_url"] = ""
                item["pdp_page_url"] = ""
                item["pdp_discount_value"] = 0.0
                item["pdp_sponsored"] = 0
                item["pdp_sponsored_brand"] = ""   
                item["location_id"] = self.location_id
                item["location_name"] = self.location
                item["pincode"] = self.pincode
                item["created_by"] = "System"
                item["created_on"] = self.current_time
                item["status"] = 1
                items.append(item)
        else:
            item = dict()
            item["pf_id"] = self.pf_id
            item["crawl_id"] = self.crawl_id
            item["page"] = page
            item["keyword"] = self.keyword
            item["keyword_id"] = self.keyword_id            
            item["brand_id"] = self.brand_id
            item["brand_name"] = self.brand_name
            item["brand_crawl"] = ""
            item["web_pid"] = ""
            item["pdp_title_value"] = ""
            item["position"] = 0
            item["price_rp"] = 0
            item["price_sp"] = 0
            item["pdp_rating_value"] = 0
            item["pdp_rating_count"] = 0
            item["pdp_image_url"] = ""
            item["pdp_page_url"] = ""
            item["pdp_discount_value"] = 0.0
            item["pdp_sponsored"] = 0
            item["pdp_sponsored_brand"] = ""   
            item["location_id"] = self.location_id
            item["location_name"] = self.location
            item["pincode"] = self.pincode
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 1
            items.append(item)

        records = list()
        columns = self.output_cols
        for item in items:
            # Create Raw file without header
            utils.create_raw_file(self.output_file, item.keys(), item)
            # Converting dict list into list of tuple
            record = tuple(item.get(col, None) for col in columns if col in item)
            records.append(record) 
        #records = [tuple(item.values()) for item in items]
    
        # Create Header file
        item = items[0]
        output_dir = self.base_dir+"/output"
        output_filename = "header.txt"
        output_file = output_dir+"/"+output_filename
        header_row = "|".join(item.keys()) +"\r"
        utils.create_file(output_file, header_row)        

        tbl_columns_str = "`"+"`,`".join(self.output_cols)+"`"        
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)

        self.logger.info("Data inserting")
        mySql_insert_query = """INSERT INTO `ajio_crawl_kw` (""" +tbl_columns_str+ """)  VALUES (""" +tbl_columns_val+ """)"""
        try:
            self.cursor.executemany(mySql_insert_query, records)
            print("utka",records)
            products_count = self.cursor.rowcount
            self.connection.commit()
        except self.cursor.Error as err:
            self.logger.error("Database Error: "+str(err))

        # Next Page
        # if self.page>1:
        #     pages = [x for x in range(2, self.page+1)]
        #     for page in pages:
        #         next_page_url = "https://www.ajio.com/api/search?fields=SITE&currentPage=" +str(page-1)+ "&pageSize=45&format=json&query=" +keyword+ "%3Arelevance&sortBy=relevance&text=" +keyword+ "&gridColumns=3&advfilter=true&platform=site" 
        #         yield scrapy.Request(
        #                 url=next_page_url,
        #                 method="GET",
        #                 headers={
        #          			        "accept": "application/json",
        #          			        "Referer": response.url
        #                         },
        #                 cookies={},          
        #                 callback=self.parse_next_page, 
        #                 meta={"items":items},
        #                 errback=self.errback_httpbin,
        #                 cb_kwargs=dict(keyword=keyword, page=page)
        #             )
        # else:
        #     records = list()
        #     columns = self.output_cols
        #     for item in items:
        #         # Create Raw file without header
        #         utils.create_raw_file(self.output_file, item.keys(), item)
        #         # Converting dict list into list of tuple
        #         record = tuple(item.get(col, None) for col in columns if col in item)
        #         records.append(record) 
        #     #records = [tuple(item.values()) for item in items]
        
        #     # Create Header file
        #     item = items[0]
        #     output_dir = self.base_dir+"/output"
        #     output_filename = "header.txt"
        #     output_file = output_dir+"/"+output_filename
        #     header_row = "|".join(item.keys()) +"\r"
        #     utils.create_file(output_file, header_row)        

        #     tbl_columns_str = "`"+"`,`".join(self.output_cols)+"`"        
        #     values_list = []
        #     values_list.extend(repeat("%s", len(self.output_cols)))
        #     tbl_columns_val = ",".join(values_list)

        #     self.logger.info("Data inserting")
        #     mySql_insert_query = """INSERT INTO `ajio_crawl_kw` (""" +tbl_columns_str+ """)  VALUES (""" +tbl_columns_val+ """)"""
        #     try:
        #         self.cursor.executemany(mySql_insert_query, records)
        #         products_count = self.cursor.rowcount
        #         self.connection.commit()
        #     except self.cursor.Error as err:
        #         self.logger.error("Database Error: "+str(err))

    def parse_next_page(self, response, keyword, page):
        self.logger.debug("Page Number: "+str(page))
        items = response.meta["items"]
        self.logger.info("Got successful response from {}".format(response.url))
        self.logger.info(response.request.headers)
        
        webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        filename = "/%s-%s-%s-%s.html" % (str(page), str(self.pincode), self.site, keyword)
        utils.save_source_content(webpage_dir, filename, response.body)
        
        self.logger.debug("Saved file %s" % filename)
        self.logger.debug("Data Extraction Start")

        json_response = json.loads(response.text)

        if '"products":' in response.text:
            products = json_response["products"]
            rank = 1
            for product in products:
                id = product["code"]
                web_pid = product["code"]

                title = product["name"]
                fnlColorVariantData = product["fnlColorVariantData"]
                brand_name = fnlColorVariantData["brandName"]

                pdp_page_url = "https://www.ajio.com"+product["url"]

                images = product["images"]
                image_url = images[0]["url"]

                price = product["price"]["value"]                    
                mrp = product["wasPriceData"]["value"]
                try:
                    discount = product["discountPercent"]
                    discount = int(discount.replace("% off", ""))
                except KeyError as ke:
                    discount = 0
   
                savings = mrp-price

                rating = 0
                review_count = 0
                rating_count = 0
                
                in_stock = 1

                seller_name = "" 

                sponsored = 0
                sponsored_brand = ""                

                item = dict()
                item["pf_id"] = self.pf_id
                item["crawl_id"] = self.crawl_id
                item["page"] = page
                item["keyword"] = self.keyword
                item["keyword_id"] = self.keyword_id            
                item["brand_id"] = self.brand_id
                item["brand_name"] = self.brand_name
                item["brand_crawl"] = brand_name
                item["web_pid"] = web_pid if web_pid else ""
                item["pdp_title_value"] = title if title else ""
                item["position"] = rank
                item["price_rp"] = mrp if mrp else 0
                item["price_sp"] = price if price else 0
                item["pdp_rating_value"] = rating if rating else 0
                item["pdp_rating_count"] = rating_count if rating_count else 0
                item["pdp_image_url"] = image_url if image_url else ""
                item["pdp_page_url"] = pdp_page_url
                item["pdp_discount_value"] = discount
                item["pdp_sponsored"] = sponsored
                item["sponsored_brand"] = sponsored_brand   
                item["location_id"] = self.location_id
                item["location_name"] = self.location
                item["pincode"] = self.pincode
                item["created_by"] = "System"
                item["created_on"] = self.current_time
                item["status"] = 1  

                item = utils.clean_item_data(item)
                rank = rank+1
                items.append(item)
        else:
            item = dict()
            item["pf_id"] = self.pf_id
            item["crawl_id"] = self.crawl_id
            item["page"] = page
            item["keyword"] = self.keyword
            item["keyword_id"] = self.keyword_id            
            item["brand_id"] = self.brand_id
            item["brand_name"] = self.brand_name
            item["brand_crawl"] = ""
            item["web_pid"] = ""
            item["pdp_title_value"] = ""
            item["position"] = 0
            item["price_rp"] = 0
            item["price_sp"] = 0
            item["pdp_rating_value"] = 0
            item["pdp_rating_count"] = 0
            item["pdp_image_url"] = ""
            item["pdp_page_url"] = ""
            item["pdp_discount_value"] = 0.0
            item["pdp_sponsored"] = 0
            item["sponsored_brand"] = ""   
            item["location_id"] = self.location_id
            item["location_name"] = self.location_name
            item["pincode"] = self.pincode
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 1
            items.append(item)
            
        records = list()
        columns = self.output_cols
        for item in items:
            # Create Raw file without header
            utils.create_raw_file(self.output_file, item.keys(), item)
            # Converting dict list into list of tuple
            record = tuple(item.get(col, None) for col in columns if col in item)
            records.append(record) 
        #records = [tuple(item.values()) for item in items]
        
        # Create Header file
        item = items[0]
        output_dir = self.base_dir+"/output"
        output_filename = "header.txt"
        output_file = output_dir+"/"+output_filename
        header_row = "|".join(item.keys()) +"\r"
        utils.create_file(output_file, header_row)        

        tbl_columns_str = "`"+"`,`".join(self.output_cols)+"`"        
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)

        self.logger.info("Data inserting")
        mySql_insert_query = """INSERT INTO `ajio_crawl_kw` (""" +tbl_columns_str+ """)  VALUES (""" +tbl_columns_val+ """)"""
        try:
            self.cursor.executemany(mySql_insert_query, records)
            products_count = self.cursor.rowcount
            self.connection.commit()
        except self.cursor.Error as err:
            self.logger.error("Database Error: "+str(err))

        return items

    def errback_httpbin(self, failure):
        # log all failures
        self.logger.error(repr(failure))

        # in case you want to do something special for some errors,
        # you may need the failure's type:

        if failure.check(HttpError):
            # these exceptions come from HttpError spider middleware
            # you can get the non-200 response
            response = failure.value.response
            self.logger.error("HttpError on %s", response.url)
            output_dir = self.base_dir+"/output"
            output_filename = str(self.pincode)+"_error.txt"
            output_file = output_dir+"/"+output_filename
            error_row = str(self.pf_id)+"|"+str(self.location_id)+"|"+str(self.location)+"|"+str(self.pincode)+"|"+str(self.keyword)+"|"+"HttpError "+response.url+"\n\r"
            utils.create_file(output_file, error_row)

        elif failure.check(DNSLookupError):
            # this is the original request
            request = failure.request
            self.logger.error("DNSLookupError on %s", request.url)
            output_dir = self.base_dir+"/output"
            output_filename = str(self.pincode)+"_error.txt"
            output_file = output_dir+"/"+output_filename
            error_row = str(self.pf_id)+"|"+str(self.location_id)+"|"+str(self.location)+"|"+str(self.pincode)+"|"+str(self.keyword)+"|"+"DNSLookupError "+response.url+"\n\r"
            utils.create_file(output_file, error_row)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error("TimeoutError on %s", request.url)
            output_dir = self.base_dir+"/output"
            output_filename = str(self.pincode)+"_error.txt"
            output_file = output_dir+"/"+output_filename
            error_row = str(self.pf_id)+"|"+str(self.location_id)+"|"+str(self.location)+"|"+str(self.pincode)+"|"+str(self.keyword)+"|"+"TimeoutError/TCPTimedOutError "+response.url+"\n\r"
            utils.create_file(output_file, error_row)