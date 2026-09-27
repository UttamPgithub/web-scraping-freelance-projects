from email import header
import cloudscraper
import sys
import os
import re
import pytz
import datetime
import scrapy
import json
import pymysql
import certifi
import requests
import random
import time
from cloudscraper import create_scraper
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
from scrapy.spiders.init import InitSpider
from slugify import slugify
from itertools import repeat
from utils import utils
from db.db_action import DBAction

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
from scrapy.utils.log import configure_logging
from bs4 import BeautifulSoup


class MNMPDPSpider(InitSpider):
    name = "us_pdp_mms"

    allowed_domains = ["mms.com"]
    start_urls = ["https://www.mms.com/"]
    custom_settings = {
        # specifies exported fields and order
        "DOWNLOAD_TIMEOUT": 60000,
        "DOWNLOAD_MAXSIZE": 12406585060,
        "DOWNLOAD_WARNSIZE": 0,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS_PER_IP": 1,
        "HTTPPROXY_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "scrapy_web_crawlers.middlewares.RandomUserAgentMiddleware": 1,
        },
        "COOKIES_ENABLED": True
    }
    HOME_URL = "https://www.mms.com/"

    def __init__(self, inputs, **kw):
        super(MNMPDPSpider, self).__init__(**kw)
        self.inputs = inputs
        self.tz = inputs.get("tz")
        self.current_time = inputs.get("current_time")
        self.dt = inputs.get("dt")
        self.timestamp = inputs.get("timestamp")

        print("PF ID: " + inputs.get("pf_id"))
        print("SKU ID: " + inputs.get("sku_id"))
        print("WEB PID: " + inputs.get("web_pid"))
        print("URL: " + inputs.get("page_url"))
        print("LOCATION: " + inputs.get("location"))
        print("LOCATION ID: " + inputs.get("location_id"))
        print("PINCODE: " + inputs.get("pincode"))
        print("crawl_id: " + inputs.get("crawl_id"))

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
        self.output_file = self.base_dir + "/output/" + self.pincode + "_" + self.web_pid + ".txt"

        self.output_cols = [
            "pf_id",
            "crawl_id",
            "sku_id",
            "web_pid",
            "pdp_title_value",
            "brand_id",
            "brand_name",
            "price_rp",
            "price_sp",
            "pdp_rating_value",
            "pdp_review_count",
            "pdp_rating_count",
            "pdp_qa_count",
            "pdp_desc_value",
            "osa",
            "osa_remark",
            "pdp_page_url",
            "pdp_discount_value",
            "location_id",
            "location_name",
            "pincode",
            "created_by",
            "created_on",
            "status",
            "one_star",
            "two_star",
            "three_star",
            "four_star",
            "five_star",
            "reseller_name_crawl",
            "pdp_image_count",
            "pdp_title_count",
            "pdp_desc_count",
            "pdp_image_url",
            "pdp_image_url_all",
            "pdp_title_score",
            "pdp_image_score",
            "pdp_rating_score",
            "pdp_review_score",
            "pdp_desc_score"
        ]

        self.visit_count = str(random.choice([10, 11, 12, 13]))

        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as error:
            self.logger.error("MySQL Error: " + error)
            print("Connection error with the database", error)
        self.session = requests.Session()
        self.logger.info("Home Page Request")

    def init_request(self):

        self.logger.info("Home Page Request")

        s = requests.Session()
        response = self.web_pid_search(s)
        print(response)
        records = self.parse_detail_page(response)

        self.logger.info("Data inserting")

        tbl_columns_str = "`" + "`,`".join(self.output_cols) + "`"
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)
        mySql_insert_query = """INSERT INTO `us_crawl_pdp` (""" + tbl_columns_str + """) VALUES (""" + tbl_columns_val + """)"""
        print(mySql_insert_query)
        rec = []
        for i in self.output_cols:
            if i in records:
                rec.append(str(records[i]))
            else:
                print(i)
                rec.append("")
        for i in range(0, len(rec)):
            print(rec[i])
        print("Data Inserting")
        try:
            self.cursor.executemany(str(mySql_insert_query), [tuple(rec)])
            self.connection.commit()
        except self.cursor.Error as err:
            self.logger.error("Mysql Error occured: {}".format(str(err)))

    def web_pid_search(self, session):

        scraper = cloudscraper.create_scraper()



        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,hi;q=0.8',
            'cache-control': 'max-age=0',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        }

        response = scraper.get(self.pdp_page_url, headers=headers, verify=certifi.where())

        return response

    def parse_detail_page(self, data):

        item = dict()

        if data.status_code == 200:

            soup = BeautifulSoup(data.content, 'html.parser')

            scripts = soup.find_all('script', type='application/ld+json')

            hasVariant = None
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if data.get('@type') == 'Product' or data.get('@type') == 'ProductGroup':
                        hasVariant = data
                        break
                except json.JSONDecodeError:
                    continue
            try:
                product_info = hasVariant.get("hasVariant", [])[0]
                if not product_info:
                    product_info = hasVariant
            except:
                product_info = hasVariant

            if product_info:
                product_name = hasVariant.get('name', '')
                rating_value = hasVariant.get('aggregateRating', {}).get('ratingValue', '')
                review_count = hasVariant.get('aggregateRating', {}).get('reviewCount', '')
                brand_name = hasVariant.get('brand', {}).get('name', '')
                availability_url = product_info.get('offers', {}).get('availability', '')
                price_alt = product_info.get('offers', {}).get('price', '')

                if "InStock" in availability_url:
                    osa = 1
                    osa_remark = "INSTOCK"
                else:
                    osa = 0
                    osa_remark = "OOS"

            else:
                product_name = ""
                rating_value = ""
                review_count = ""
                brand_name = ""
                availability_url = ""
                price_alt = ""
                osa = 0
                osa_remark = "OOS"

            script = soup.find('script', type='application/json')

            data = json.loads(script.string)

            try:
                sp = \
                data['props']['pageProps']['page']['pageContent']['value']['mainSlot']['features'][0]['price']['value'][
                    'amount']
            except:
                sp = price_alt
            try:
                mrp = data['props']['pageProps']['page']['pageContent']['value']['mainSlot']['features'][0]['price'][
                    'wasValue']['amount']
            except:
                mrp = sp

            try:
                discount = (mrp - sp) / mrp * 100
            except:
                discount = 0

            try:
                image_urls = [asset["imageUrl"] for asset in
                              data['props']['pageProps']['page']['pageContent']['value']['mainSlot']['features'][0][
                                  "galleryAssets"]]

                image_count = len(image_urls)

                image_url = image_urls[0]

                image_urls = ",".join(image_urls)
            except:
                image_urls = ""
                image_url = ""
                image_count = 0

            try:
                product_description = ' '.join(BeautifulSoup(
                    data['props']['pageProps']['page']['pageContent']['value']['mainSlot']['features'][0]['accordions'][
                        'productDescription']['longDescription'], 'html.parser').find_all(text=True)).replace('\n',
                                                                                                              ' ').strip()
            except:
                product_description = ""

            print(sp, mrp, image_urls, image_count, image_url, product_description, osa, osa_remark)

            item["pf_id"] = self.pf_id
            item["crawl_id"] = self.crawl_id
            item["sku_id"] = self.sku_id
            item["pincode"] = self.pincode
            item["location_id"] = self.location_id
            item["location_name"] = self.location
            item["brand_id"] = self.brand_id
            item["web_pid"] = self.web_pid
            item["extracted_web_pid"] = self.web_pid
            item["pdp_title_value"] = product_name
            item["brand_name"] = brand_name
            item["pdp_rating_value"] = rating_value
            item["pdp_rating_count"] = ""
            item["pdp_review_count"] = review_count
            item["pdp_qa_count"] = 0
            item["five_star"] = 0
            item["four_star"] = 0
            item["three_star"] = 0
            item["two_star"] = 0
            item["one_star"] = 0
            item["price_rp"] = mrp if mrp else 0.0
            item["price_sp"] = sp if sp else 0.0
            item["pdp_discount_value"] = discount if discount else 0.0
            item["pdp_image_count"] = image_count
            item["pdp_title_count"] = len(product_name)
            item["pdp_desc_count"] = len(product_description)
            item["pdp_image_url"] = image_url
            item["pdp_image_url_all"] = image_urls
            item["osa"] = osa
            item["osa_remark"] = osa_remark
            item["pdp_desc_value"] = product_description
            item["pdp_page_url"] = self.pdp_page_url
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 1

            def calculate_title_score(title):
                length = len(title.strip()) if title else 0

                if 30 <= length:
                    return 100
                elif 20 <= length <= 29:
                    return 50
                elif 10 <= length <= 19:
                    return 25
                else:
                    return 0

            def calculate_image_score(count):
                if count >= 3:
                    return 100
                elif count == 2:
                    return 50
                elif count == 1:
                    return 25
                else:
                    return 0

            def calculate_rating_score(rating):
                try:
                    rating = float(rating)
                    if 4.5 <= rating:
                        return 100
                    elif 4.0 <= rating < 4.49:
                        return 50
                    elif 3.0 <= rating < 3.99:
                        return 25
                    else:
                        return 0
                except (ValueError, TypeError):
                    return 0

            def calculate_review_score(review_count):
                try:
                    count = int(review_count)
                    if count >= 5:
                        return 100
                    elif 3 <= count <= 4:
                        return 50
                    elif 2 == count:
                        return 25
                    else:
                        return 0
                except (ValueError, TypeError):
                    return 0

            def calculate_desc_score(desc_char_count):
                try:
                    count = len(desc_char_count)
                    if count >= 100:
                        return 100
                    elif 85 <= count <= 99:
                        return 70
                    elif 70 <= count <= 84:
                        return 50
                    elif 50 <= count <= 69:
                        return 25
                    else:
                        return 0
                except (ValueError, TypeError):
                    return 0

            item["pdp_title_score"] = calculate_title_score(item.get("pdp_title_value", 0))
            item["pdp_image_score"] = calculate_image_score(item.get("pdp_image_count", 0))
            item["pdp_rating_score"] = calculate_rating_score(item.get("pdp_rating_value", 0))
            item["pdp_review_score"] = calculate_review_score(item.get("pdp_review_count", 0))
            item["pdp_desc_score"] = calculate_desc_score(item.get("pdp_desc_value", 0))

        else:
            item["pf_id"] = self.pf_id
            item["crawl_id"] = self.crawl_id
            item["sku_id"] = self.sku_id
            item["pincode"] = self.pincode
            item["location_id"] = self.location_id
            item["location_name"] = self.location
            item["brand_id"] = self.brand_id
            item["web_pid"] = self.web_pid
            item["extracted_web_pid"] = self.web_pid
            item["pdp_title_value"] = ""
            item["brand_name"] = ""
            item["pdp_rating_value"] = ""
            item["pdp_rating_count"] = ""
            item["pdp_review_count"] = ""
            item["pdp_qa_count"] = 0
            item["five_star"] = 0
            item["four_star"] = 0
            item["three_star"] = 0
            item["two_star"] = 0
            item["one_star"] = 0
            item["price_rp"] = ""
            item["price_sp"] = ""
            item["pdp_discount_value"] = ""
            item["pdp_image_count"] = 0
            item["pdp_title_count"] = 0
            item["pdp_desc_count"] = 0
            item["pdp_image_url"] = ""
            item["pdp_image_url_all"] = ""
            item["osa"] = 0
            item["osa_remark"] = "OOS"
            item["pdp_desc_value"] = ""
            item["pdp_page_url"] = self.pdp_page_url
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 1
            item["pdp_title_score"] = 0
            item["pdp_image_score"] = 0
            item["pdp_rating_score"] = 0
            item["pdp_review_score"] = 0
            item["pdp_desc_score"] = 0
        return item

