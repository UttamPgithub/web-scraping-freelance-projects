import sys
import os
import re
import pytz
import datetime
import scrapy
import json
import pymysql
import requests
import random
import time

from scrapy.selector import Selector
from scrapy.loader import ItemLoader
import mysql.connector
from datetime import datetime
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError, TCPTimedOutError
from twisted.internet import reactor
from scrapy.utils.log import configure_logging
from scrapy.http import HtmlResponse
from w3lib.html import remove_tags
from scrapy.spiders.init import InitSpider
from slugify import slugify
from itertools import repeat
from lxml import html
from utils import utils
from db.db_action import DBAction

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

SETTINGS = scrapy.utils.project.get_project_settings()

class AJIOPDPSpider(InitSpider):
    name = "ajio_pdp"
    
    allowed_domains = ["ajio.com"]
    start_urls = ["https://www.ajio.com/"]
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
                "scrapy_web_crawlers.middlewares.RandomUserAgentMiddleware": 1,
                },
        }    
    HOME_URL = "https://www.ajio.com/"
    
    def __init__(self,inputs, **kw): #pf_id=None, sku_id=None, web_pid=None, brand_id=None, brand_name=None, page_url=None, location_id=None, location=None, pincode=None, 
        super(AJIOPDPSpider, self).__init__(**kw)
        self.inputs = inputs
        self.tz = inputs.get("tz")
        self.current_time = inputs.get("current_time")
        self.dt = inputs.get("dt")
        self.timestamp = inputs.get("timestamp")
        self.session = requests.Session()

        print("PF ID: "+inputs.get("pf_id"))
        print("SKU ID: "+inputs.get("sku_id"))
        print("WEB PID: "+inputs.get("web_pid"))
        print("URL: "+inputs.get("page_url"))
        print("LOCATION: "+inputs.get("location"))
        print("LOCATION ID: "+inputs.get("location_id"))
        print("PINCODE: "+inputs.get("pincode"))
        print("crawl_id: "+inputs.get("crawl_id"))
        
        self.site = self.name
        self.env = inputs.get("env")
        self.db_name = inputs.get("db_name")        
        self.crawl_id = int(inputs.get("crawl_id"))
        self.pf_id = int(inputs.get("pf_id"))
        self.sku_id = int(inputs.get("sku_id"))      
        self.web_pid = inputs.get("web_pid")
        self.pdp_page_url = inputs.get("page_url")
        self.brand_id = int(inputs.get("brand_id"))
        self.brand_name = inputs.get("brand_name")

        self.location_search = inputs.get("location_search")
        self.location_id = int(inputs.get("location_id"))
        self.location = inputs.get("location")
        self.pincode = inputs.get("pincode")

        self.base_dir = "C:/var/logs/" + self.site
        self.output_file = self.base_dir+"/output/"+self.pincode+"_"+self.web_pid+".txt"        
        
        self.output_cols = ["pf_id","crawl_id", "sku_id","web_pid", "pdp_title_value", "brand_id", "brand_name", "extracted_brand_name", "price_rp",
                                "price_sp","pdp_rating_value", "pdp_review_count","pdp_rating_count","pdp_qa_count","pdp_desc_value", 
                                "pdp_image_count", "pdp_image_url", "pdp_image_url_all", "osa","osa_remark","pdp_page_url","pdp_discount_value",
                                "location_id", "location_name", "pincode", "delivery_date", "created_by", "created_on","ec_number_of_images", "ec_number_of_videos", "pdp_number_of_bulletin",
                                "pdp_bulletin_value","reseller_name_crawl", "seller_rank", "five_star", "four_star","three_star","two_star","one_star", "status"
                            ]
        
        self.visit_count = str(random.choice([10,11,12,13]))
        
        
        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as error:
            self.logger.error("MySQL Error: "+error)
            print("Connection error with the database", error)

    def init_request(self):    
        #Home Page Request
        self.logger.info("Home Page Request")
        
        home_page_res = self.session.get(url=self.HOME_URL, 
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                        #"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        #"Content-Type": "application/x-www-form-urlencoded"
                        },
                    cookies={}
                    )
        try:
            pdp_response = self.session.get(url=self.pdp_page_url,
                                   headers={
                                       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                                        #"Content-Type": "application/x-www-form-urlencoded",
                                        #"Accept": "text/html,*/*",
                                        #"X-Requested-With": "XMLHttpRequest"
                                        "Referer": self.HOME_URL
                                        },
                                    cookies={}
                                    )
            pdp_response.raise_for_status()
            self.logger.debug("Header: {}".format(pdp_response.headers))
        except requests.exceptions.HTTPError as http_err:
            self.logger.error("HTTP error occurred: {}".format(http_err))  # Python 3.6
        except requests.exceptions.Timeout as errt:
            self.logger.error("Timeout Error: {}".format(errt))
        except requests.exceptions.RequestException as re:
            self.logger.error("OOps: Something Else".format(re))
        except requests.exceptions.ConnectionError as ce:
            self.logger.error ("Error Connecting: {} ".format(ce))

        items = self.parse_detail_page(pdp_response.content, web_pid=self.web_pid) 

        records = []
        columns = self.output_cols        
        for item in items:
            # Create Raw file without header
            utils.create_raw_file(self.output_file, item.keys(), item)
            # Converting into list of tuple
            record = tuple(item.get(col, "0") for col in columns if col in item) 
            self.logger.debug(record)
            records.append(record)
        #records = [tuple(item.values()) for item in items]
        
        # Create Header file
        item = items[0]
        output_dir = self.base_dir+"/output"
        output_filename = "header.txt"
        output_file = output_dir+"/"+output_filename
        header_row = "|".join(item.keys()) +"\r"
        utils.create_file(output_file, header_row)

        self.logger.info("Data inserting")

        tbl_columns_str = "`"+"`,`".join(self.output_cols)+"`"        
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)
        mySql_insert_query = """INSERT INTO `ajio_crawl_pdp` (""" +tbl_columns_str+ """) VALUES (""" +tbl_columns_val+ """)"""
        try:
            self.cursor.executemany(str(mySql_insert_query), records)
            products_count = self.cursor.rowcount
            self.connection.commit()
        except self.cursor.Error as err:
            self.logger.error("Mysql Error occured: {}".format(str(err))) 
            
    def parse_detail_page(self, response, web_pid): 
        
        #self.logger.info("Got successful response from {}".format(response.url))

        webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        filename = "/%s-%s-%s.html" % (str(self.pincode), self.site, str(web_pid))
        if str(self.inputs.get("pdp_snapshot")) == "1":
            utils.save_source_content(webpage_dir, filename, response)        
            self.logger.info("Saved file %s" % filename) 
        
        self.logger.info("Data Extraction Start")
        items = list()
        item = dict() 
        response = Selector(text=response)
        script = response.xpath("//body").re_first(r'<script>\s*window\.__PRELOADED_STATE__\s*=\s*(.*?)\n\s*<\/script>')
        script = script.replace("}}};", "}}}") #.replace("\\r", "").replace("\\n", "").replace("\\","").replace('="', '=\\"').replace('">', '\\">').replace("\\u0003C","<").replace("u003E", ">").replace("\\u20B9","INR ").replace("u003Cbru003E","<br>").replace("u003Cbr>","").replace("u002F","/")

        if script is not None:
            json_response = json.loads(script.strip())
            if '"product":' in script:

                product = json_response["product"]["productDetails"]
                id = product["code"]
                extracted_web_pid = product["code"]
                base_product = product["baseProduct"]
                title = product["name"]
                brand_name = product["brandName"]
                
                review = product["numberOfReviews"]
                rating = 0
                rating_count = 0
                answered_questions = 0

                stars = {"one":"0","two":"0","three":"0","four":"0","five":"0"}

                # New
                if 'variantOptions' in product:
                    variantOptions = product['variantOptions'][0]
                    mrp = variantOptions["wasPriceData"]["value"]
                    price = variantOptions["priceData"]["value"]
                    discount = variantOptions["priceData"]["discountValue"]
                    currency = variantOptions["priceData"]["currencyIso"]
                else:
                    # Old
                    mrp = product["wasPriceData"]["value"]
                    price = product["price"]["value"]
                    discount = product["price"]["discountValue"]
                    currency = product["price"]["currencyIso"]
                savings = mrp-price
                currency = "INR"
                
                in_stock = product["stock"]["stockLevelStatus"]

                if in_stock.lower() == "instock":
                    in_stock = "1"
                else:
                    in_stock = "0"

                details = dict()
                # Bulletin Consists of FeatureData + Product Code + MRP + mandatoryInfo
                featured_info = product["featureData"]
                mandatory_info = product["mandatoryInfo"]    
                country_of_origin = ""
                manufacturer = ""
                seller_name = ""
                model_number = ""

                if featured_info:
                    for feature in featured_info:
                        details[feature['name']] = feature["featureValues"][0]['value']

                # Completing Bulletin with Product Code and MRP
                if details:
                    details['Product Code'] = self.web_pid
                    details['MRP'] = mrp

                if len(mandatory_info)>0:
                    for item in mandatory_info:
                        key = item["key"]
                        value = item["title"]
                        details[key] = value
                        if "Country Of Origin" in item["key"]:
                            country_of_origin = item["title"]
                        elif "Manufactured By" in item["key"]:
                            manufacturer = item["title"]
                        elif "Marketed By" in item["key"]:
                            seller = item["title"]


                feature_data = product["featureData"]

                images = product["images"]
                images_url_list = []
                try:
                    # New Implementation
                    for img in images:
                        if "473Wx593H" in img["url"] and img["url"] not in images_url_list:
                            images_url_list.append(img["url"])
                    
                    # Reverts to old if new one fails :/
                    if not images_url_list:
                        # Old Implementation
                        for albm in images:
                            if "product" in albm["format"]:
                                images_url_list .append(albm["url"])
                            else:
                                continue
                except:
                    pass

                pdp_bullet_count = len(details.keys())
                pdp_bullet_value = details

                pdp_page_url = "https://www.ajio.com"+product["url"]
                product_code = product["variantOptions"][0]["code"]

                delivery_date = ""
                item["marketplace"] = "AJIO"
                item["pf_id"] = self.pf_id
                item["crawl_id"] = self.crawl_id
                item["sku_id"] = self.sku_id                
                item["pincode"] = self.pincode  
                item["location_id"] = self.location_id
                item["location_name"] = self.location
                item["web_pid"] = self.web_pid
                item["brand_id"] = self.brand_id
                item["brand_name"] = self.brand_name
                
                item["extracted_web_pid"] = extracted_web_pid if extracted_web_pid else ""
                item["pdp_title_value"] = title if title else ""                
                item["extracted_brand_name"] = brand_name if brand_name else ""
                
                item["pdp_rating_value"] = rating if rating else 0
                item["pdp_rating_count"] = rating_count if rating_count else 0
                item["pdp_review_count"] = review if review else 0
                item["pdp_qa_count"] = answered_questions
                item["five_star"] = stars["five"]
                item["four_star"] = stars["four"]
                item["three_star"] = stars["three"]
                item["two_star"] = stars["two"]
                item["one_star"] = stars["one"]
            
                item["price_rp"] = mrp if mrp else 0.0
                item["price_sp"] = price if price else 0.0
                item["savings"] = savings if savings else 0.0
                item["pdp_discount_value"] = discount if discount else 0.0
                item["currency"] = currency if currency else ""
            
                item["in_stock"] = in_stock if in_stock else 0
                if str(item["in_stock"]) == "0":
                    item["osa"] = 0
                    item["osa_remark"] = "OOS"
                else:
                    item["osa"] = 1
                    item["osa_remark"] = "IN STOCK"
            
                item["manufacturer"] = manufacturer if manufacturer else ""
                item["model_number"] = model_number if model_number else ""
                item["country_of_origin"] = country_of_origin if country_of_origin else ""
                item["shipping_type"] = ""
            
                item["about_this_item"] = ""
                item["product_details"] = ""
                item["pdp_desc_value"] = ""
            
                item["pdp_image_count"] = len(images_url_list)
                item["pdp_image_url_all"] = ", ".join(images_url_list)
                item["pdp_image_url"] = images_url_list[0]
                item["ec_number_of_images"] = 0
                item["ec_number_of_videos"] = 0
                item["aplus_images_list"] = 0
                
                item["pdp_number_of_bulletin"] = pdp_bullet_count
                item["pdp_bulletin_value"] = pdp_bullet_value
                
                item["reseller_name_crawl"] = seller_name
                item["reseller_info"] = seller_name
                item["seller_rating"] = 0
                item["seller_rank"] = 0

                item["delivery_date"] = delivery_date

                item["pdp_page_url"] = self.pdp_page_url           
                item["group_id"] = 0
                item["created_by"] = "System"
                item["created_on"] = self.current_time
                item["status"] = 1
                
                # Pincode Set Up
                if str(self.location_search) == "1"  and str(item["in_stock"]) == "1":
                    today = datetime.now(self.tz)
                    unixtime = datetime.timestamp(today)*1000
                    ts = str(unixtime).split(".")[0]
                    url = "https://login.web.ajio.com/api/edd/checkDeliveryDetails?productCode=" +product_code+ "&postalCode=" +self.pincode+ "&quantity=1&IsExchange=false"

                    pincode_res = self.session.get(
                                                    url,
                                                    headers={
                                                                "Accept": "application/json",
                                                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                                                                #"Referer":  response.url
                                                            },
                                                    cookies={}
                                                    )
                    webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
                    filename = "/%s-%s-%s-availiablity.html" % (str(self.pincode), self.site, str(self.web_pid))
                    utils.save_source_content(webpage_dir, filename, pincode_res.content)
                    osa_data = json.loads(pincode_res.content)

                    print(osa_data)
                    servicability = osa_data["servicability"]
                    codEligible = osa_data["codEligible"]
                    productDetails = osa_data["productDetails"][0]

                    if servicability:
                        item["in_stock"] = 1
                        item["osa"] = 1
                        item["osa_remark"] = "IN STOCK"
                        item["delivery_date"] = productDetails["eddUpper"].split("T")[0]
                    else:
                        item["in_stock"] = 0
                        item["osa"] = 0
                        item["osa_remark"] = "OOS"
                        item["delivery_date"] = ""
                
                item = utils.clean_item_data(item)
                items.append(item)
                return items

            else:
                item["marketplace"] = "AJIO"
                item["pf_id"] = self.pf_id
                item["crawl_id"] = self.crawl_id
                item["sku_id"] = self.sku_id
                item["pincode"] = self.pincode  
                item["location_id"] = self.location_id
                item["location_name"] = self.location
                item["web_pid"] = self.web_pid
                item["brand_id"] = self.brand_id
                item["brand_name"] = self.brand_name
                item["extracted_web_pid"] = ""
                item["pdp_title_value"] = ""                
                item["extracted_brand_name"] = ""

                item["pdp_rating_value"] = 0
                item["pdp_rating_count"] = 0
                item["pdp_review_count"] = 0                                
                item["pdp_qa_count"] = 0
                item["five_star"] = 0
                item["four_star"] = 0
                item["three_star"] = 0
                item["two_star"] = 0
                item["one_star"] = 0
            
                item["price_rp"] = 0.0
                item["price_sp"] = 0.0
                item["savings"] = 0.0
                item["pdp_discount_value"] = 0.0
                item["currency"] = ""
                item["osa"] = 0
                item["osa_remark"] = ""
            
                item["manufacturer"] =  ""
                item["model_number"] = ""
                item["country_of_origin"] = ""
                item["shipping_type"] = ""
            
                item["about_this_item"] = ""
                item["product_details"] = ""
                item["pdp_desc_value"] = ""
            
                item["pdp_image_count"] = 0
                item["pdp_image_url_all"] = ""
                item["pdp_image_url"] = ""
                item["ec_number_of_images"] = 0
                item["ec_number_of_videos"] = 0
                item["aplus_images_list"] = ""
                
                item["pdp_number_of_bulletin"] = 0
                item["pdp_bulletin_value"] = ""
                
                item["reseller_name_crawl"] = ""
                item["reseller_info"] = ""
                item["seller_rank"] = 0
                item["seller_rating"] = 0

                item["delivery_date"] = ""

                item["pdp_page_url"] = self.pdp_page_url           
                item["group_id"] = 0
                item["created_by"] = "System"
                item["created_on"] = self.current_time 
                item["status"] = 0
                items.append(item)
                self.logger.error("Something went wrong....")

        else:            
            item["marketplace"] = "Myntra"
            item["pf_id"] = self.pf_id
            item["crawl_id"] = self.crawl_id
            item["sku_id"] = self.sku_id
            item["pincode"] = self.pincode  
            item["location_id"] = self.location_id
            item["location_name"] = self.location
            item["web_pid"] = self.web_pid
            item["brand_id"] = self.brand_id
            item["brand_name"] = self.brand_name
            item["extracted_web_pid"] = ""
            item["pdp_title_value"] = ""
            item["extracted_brand_name"] = ""

            item["pdp_review_count"] = 0
            item["pdp_rating_value"] = 0
            item["pdp_rating_count"] = 0
            item["pdp_qa_count"] = 0
            item["five_star"] = 0
            item["four_star"] = 0
            item["three_star"] = 0
            item["two_star"] = 0
            item["one_star"] = 0
            
            item["price_rp"] = 0.0
            item["price_sp"] = 0.0
            item["savings"] = 0.0
            item["pdp_discount_value"] = 0.0
            item["currency"] = ""
            item["osa"] = 0
            item["osa_remark"] = ""
            
            item["manufacturer"] =  ""
            item["model_number"] = ""
            item["country_of_origin"] = ""
            item["shipping_type"] = ""
            
            item["about_this_item"] = ""
            item["product_details"] = ""
            item["pdp_desc_value"] = ""
            
            item["pdp_image_count"] = 0
            item["pdp_image_url_all"] = ""
            item["pdp_image_url"] = ""
            item["ec_number_of_images"] = 0
            item["ec_number_of_videos"] = 0
            item["aplus_images_list"] = ""
                
            item["pdp_number_of_bulletin"] = 0
            item["pdp_bulletin_value"] = ""
                
            item["reseller_name_crawl"] = ""
            item["reseller_info"] = ""
            item["seller_rank"] = 0
            item["seller_rating"] = 0

            item["delivery_date"] = "" 

            item["pdp_page_url"] = self.pdp_page_url           
            item["group_id"] = 0
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 0
            items.append(item)
            self.logger.error("Something went wrong....") 
        
        return items  
    
    def parse_pincode_page(self, response, web_pid):
        item = response.meta["item"]
        items = list()
        self.logger.info("Got successful response from {}".format(response.url))
        #self.logger.info(response.request.headers)
        
        webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        filename = "/%s-%s-%s-availiablity.html" % (str(self.pincode), self.site, str(self.web_pid))
        utils.save_source_content(webpage_dir, filename, response.body)

        osa_data = json.loads(response.body)
        print(osa_data)
        serviceabilityEntries = osa_data["itemServiceabilityEntries"][0]["serviceabilityEntries"]

        if len(serviceabilityEntries) > 0:
            timestamp = serviceabilityEntries[0]["promiseDate"]  
            timestamp = timestamp/1000
            delivery_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))                  
            if ("promiseDate" in serviceabilityEntries[0].keys() and "orderByTime" in serviceabilityEntries[0].keys()):
                in_stock = 1
            else:
                in_stock = 0

            item["in_stock"] = in_stock if in_stock else 0
            if item["in_stock"] == 0:
                item["osa"] = 0
                item["osa_remark"] = "OOS"
            else:
                item["osa"] = 1
                item["osa_remark"] = "IN STOCK"

            item["delivery_date"] = delivery_date
        else:
            item["osa"] = 0
            item["osa_remark"] = "OOS"
            item["delivery_date"] = ""

        
        item = utils.clean_item_data(item)
        items.append(item)

        records = []
        columns = self.output_cols        
        for item in items:
            # Create Raw file without header
            utils.create_raw_file(self.output_file, item.keys(), item)
            # Converting into list of tuple
            record = tuple(item.get(col, "0") for col in columns if col in item) 
            self.logger.debug(record)
            records.append(record)
        #records = [tuple(item.values()) for item in items]
        
        # Create Header file
        item = items[0]
        output_dir = self.base_dir+"/output"
        output_filename = "header.txt"
        output_file = output_dir+"/"+output_filename
        header_row = "|".join(item.keys()) +"\r"
        utils.create_file(output_file, header_row)

        self.logger.info("Data inserting")

        tbl_columns_str = "`"+"`,`".join(self.output_cols)+"`"        
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)
        mySql_insert_query = """INSERT INTO `myntra_crawl_pdp` (""" +tbl_columns_str+ """) VALUES (""" +tbl_columns_val+ """)"""
        try:
            self.cursor.executemany(str(mySql_insert_query), records)
            products_count = self.cursor.rowcount
            self.connection.commit()
        except self.cursor.Error as err:
            self.logger.error("Mysql Error occured: {}".format(str(err)))   
        
        return item

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
            error_row = str(self.pf_id)+"|"+str(self.location_id)+"|"+str(self.location)+"|"+str(self.pincode)+"|"+str(self.sku_id)+"|"+str(self.web_pid)+"|"+str(self.pdp_page_url)+"|"+"HttpError "+response.url+"\r"
            utils.create_file(output_file, error_row)

        elif failure.check(DNSLookupError):
            # this is the original request
            request = failure.request
            self.logger.error("DNSLookupError on %s", request.url)
            output_dir = self.base_dir+"/output"
            output_filename = str(self.pincode)+"_error.txt"
            output_file = output_dir+"/"+output_filename
            error_row = str(self.pf_id)+"|"+str(self.location_id)+"|"+str(self.location)+"|"+str(self.pincode)+"|"+str(self.sku_id)+"|"+str(self.web_pid)+"|"+str(self.pdp_page_url)+"|"+"DNSLookupError "+response.url+"\n\r"
            utils.create_file(output_file, error_row)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error("TimeoutError on %s", request.url)
            output_dir = self.base_dir+"/output"
            output_filename = str(self.pincode)+"_error.txt"
            output_file = output_dir+"/"+output_filename
            error_row = str(self.pf_id)+"|"+str(self.location_id)+"|"+str(self.location)+"|"+str(self.pincode)+"|"+str(self.sku_id)+"|"+str(self.web_pid)+"|"+str(self.pdp_page_url)+"|"+"TimeoutError "+response.url+"\n\r"
            utils.create_file(output_file, error_row)
