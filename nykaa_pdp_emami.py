# ---- header limit fix: must be before any network calls ----
import http.client as _http_client

_http_client._MAXHEADERS = 1000  # accept up to 1000 headers (default=100)
# ------------------------------------------------------------

import sys
import os
import re
import json
import random
import scrapy  # This needs to come before using scrapy.utils
from scrapy.utils import project
import cloudscraper
from scrapy.selector import Selector
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError, TCPTimedOutError
from w3lib.html import remove_tags
from scrapy.spiders.init import InitSpider
from itertools import repeat
from utils import utils
from db.db_action import DBAction
from .addons import Session
import certifi

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

# Now scrapy is properly imported
SETTINGS = scrapy.utils.project.get_project_settings()


class FKWebsitePDPSpider(InitSpider):
    name = "nykaa_pdp_emami1"

    allowed_domains = ["nykaa.com"]
    start_urls = ["https://nykaa.com/"]
    custom_settings = {
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
    }

    def __init__(self, inputs, **kw):
        super(FKWebsitePDPSpider, self).__init__(**kw)
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
        if inputs.get('brand_id') and inputs.get('brand_id') != 'None':
            self.brand_id = int(inputs.get("brand_id"))
        else:
            self.brand_id = 0
        self.brand_name = inputs.get("brand_name")

        self.location_search = inputs.get("location_search")
        self.location_id = int(inputs.get("location_id"))
        self.location = inputs.get("location")
        self.pincode = inputs.get("pincode")

        self.base_dir = "C:/var/logs/" + self.site
        self.output_file = self.base_dir + "/output/" + self.pincode + "_" + self.web_pid + ".txt"

        self.output_cols = [
            "pf_id", "crawl_id", "sku_id", "web_pid", "pdp_title_value", "brand_id",
            "brand_name", "price_rp", "price_sp", "pdp_rating_value", "pdp_review_count",
            "pdp_rating_count", "pdp_qa_count", "five_star", "four_star", "three_star",
            "two_star", "one_star", "pdp_desc_value", "pdp_image_count", "pdp_image_url",
            "pdp_image_url_all", "osa", "osa_remark", "delivery_date", "pdp_page_url",
            "pdp_discount_value", "location_id", "location_name", "pincode", "created_by",
            "created_on", "status", "reseller_name_crawl", "ec_number_of_images", "ec_number_of_videos"
        ]

        self.visit_count = str(random.choice([10, 11, 12, 13]))

        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except Exception as error:
            self.logger.error("MySQL Error: " + str(error))
            print("Connection error with the database", error)

        self.session = Session()
        self.ua = random.choice(SETTINGS.get("USER_AGENTS"))

    def init_request(self):
        web_pid = self.web_pid
        self.logger.info("Crawl WEB PID : " + web_pid)
        scraper = cloudscraper.create_scraper()

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Cookie': 'countryCode=IN; storeId=nykaa; bcookie=44c2b87f-95a7-4ecc-a76a-0acdcc1692e0; pinCodeDel=' + self.pincode + '; PHPSESSID=QkTsO1Qg5YyGrI51772096780352',
            'Host': 'www.nykaa.com',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
        }
        url = self.pdp_page_url
        response = scraper.request("GET",url, headers=headers,verify=certifi.where(),timeout=30)
        self.logger.info(f"Data status code {response.status_code}")

        # self.logger.info(f"Data html {response.text}")


        if response.status_code == 200:
            self.parse_detail_page(response, self.web_pid)
        else:
            print("Failed to access nykaa: ", response.status_code, response.reason)

    def parse_detail_page(self, response, web_pid):
        self.logger.info("Got successful response from {}".format(response.url))

        webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        filename = "/%s-%s-%s.html" % (str(self.pincode), self.site, str(web_pid))
        if str(self.inputs.get("pdp_snapshot")) == "1":
            utils.save_source_content(webpage_dir, filename, response.content)
            self.logger.info("Saved file %s" % filename)

        self.logger.info("Data Extraction Start")
        # self.logger.info("Data pincode",str(self.pincode))

        items = []
        item = {}

        try:
            script = \
            re.findall(r'>\s*window.__PRELOADED_STATE__\s*=\s*({.*})\s*<', response.text)[0].split('</script', 1)[
                0].strip()
        except Exception as e:
            print('ERR_NEW_IMPLEMENTATION', e, self.pdp_page_url)
            script = None
        self.logger.info(f"Data data Start {script}")
        if script is not None:
            json_response = json.loads(script)
            if product := json_response['productPage'].get('product'):

                stars = {"one": 0, "two": 0, "three": 0, "four": 0, "five": 0}
                if reviews_ratings := product.get("reviewSplitUp"):
                    try:
                        stars["one"] = reviews_ratings[4]["count"]
                        stars["two"] = reviews_ratings[3]["count"]
                        stars["three"] = reviews_ratings[2]["count"]
                        stars["four"] = reviews_ratings[1]["count"]
                        stars["five"] = reviews_ratings[0]["count"]
                    except Exception:
                        pass

                product_info = json_response.get("dataLayer", {}).get("product", {})
                title = product_info.get("name", "")
                price = product_info.get("offerPrice", 0)
                skus = product.get("sku", "")
                mrp = product_info.get("mrp", 0)
                discount = product_info.get("discount", 0)
                star_rating = product.get("rating", 0)
                rating = product.get("ratingCount", 0)
                review = product.get("reviewCount", 0)
                qna_count = product.get("qnaCount", 0)

                try:
                    in_stock = json_response["dataLayer"]["product"]["inStock"]
                except:
                    in_stock = False

                if in_stock:
                    osa = 1
                    osa_remark = "IN STOCK"
                else:
                    osa = 0
                    osa_remark = "OOS"

                image_url = product.get("imageUrl", "")
                seller_name = product.get("sellerName", "")
                description = product.get("description", "")

                aplus_images = []
                try:
                    desc_sel = Selector(text=description)
                    aplus_content = Selector(text=desc_sel.xpath("//div[@class='APlus-MainParent']").get())
                    aplus_images = aplus_content.xpath("//img/@src").getall()
                except:
                    pass
                if not aplus_images:
                    try:
                        aplus_images = desc_sel.xpath("//img/@src").getall()
                    except:
                        aplus_images = []

                if aplus_images:
                    description = ""

                media_list = product.get("parentMedia", [])
                image_url_list = []
                video_url_list = []
                for media in media_list:
                    if "image" in media.get("mediaType", ""):
                        image_url_list.append(media.get("url", ""))
                    elif "video" in media.get("mediaType", ""):
                        video_url_list.append(media.get("url", ""))

                delivery_date = ""

                if str(self.location_search) == "1":
                    cookies = {
                        'bcookie': '44c2b87f-95a7-4ecc-a76a-0acdcc1692e0',
                        'pinCodeDel': self.pincode,
                        'PHPSESSID': 'QkTsO1Qg5YyGrI51772096780352',
                    }

                    headers = {
                        'accept': 'application/json, text/plain, */*',
                        'accept-language': 'en-US,en-IN;q=0.9,en;q=0.8,hi;q=0.7',
                        'content-type': 'application/json',
                        'origin': 'https://www.nykaa.com',
                        'referer': 'https://www.nykaa.com/godrej-expert-rich-creme-natural-brown/p/18173634?redirectpath=slug',
                        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                    }

                    json_data = {
                        'skus': [skus],
                        'type': 'simple',
                        'domain': 'nykaa',
                        'source': 'pdp',
                        'fetchDarkstoreDetails': False,
                        'pincode': str(self.pincode),
                    }

                    scraper = cloudscraper.create_scraper()
                    response_edd = scraper.post('https://www.nykaa.com/edd/product/edd/default/fetch', cookies=cookies,
                                                headers=headers, json=json_data)

                    if response_edd.status_code == 200:
                        x = json.loads(response_edd.text)
                        data = x.get("data", {}).get("details", {})
                        for key in data:
                            message = data[key].get('message')
                            if message:
                                delivery_date = message

                try:
                    item["pf_id"] = self.pf_id
                    item["crawl_id"] = self.crawl_id
                    item["sku_id"] = self.sku_id
                    item["pincode"] = self.pincode
                    item["location_id"] = self.location_id
                    item["location_name"] = self.location
                    item["web_pid"] = self.web_pid
                    item["brand_id"] = self.brand_id
                    item["brand_name"] = self.brand_name

                    item["pdp_title_value"] = title if title else ""
                    item["pdp_rating_value"] = star_rating if star_rating else 0
                    item["pdp_review_count"] = review if review else 0
                    item["pdp_rating_count"] = rating if rating else 0
                    item["pdp_qa_count"] = qna_count
                    item["five_star"] = stars["five"]
                    item["four_star"] = stars["four"]
                    item["three_star"] = stars["three"]
                    item["two_star"] = stars["two"]
                    item["one_star"] = stars["one"]

                    item["price_rp"] = mrp if mrp else 0.0
                    item["price_sp"] = price if price else 0.0
                    item["pdp_discount_value"] = discount if discount else 0.0
                    item["osa"] = osa
                    item["osa_remark"] = osa_remark

                    item["pdp_desc_value"] = remove_tags(description).split('}')[-1].replace('-->', '').strip()

                    item["pdp_image_count"] = len(image_url_list)
                    item["pdp_image_url_all"] = ", ".join(image_url_list)
                    item["pdp_image_url"] = image_url
                    item["ec_number_of_images"] = len(aplus_images)
                    item["ec_number_of_videos"] = len(video_url_list)

                    item["reseller_name_crawl"] = seller_name
                    item["delivery_date"] = delivery_date
                    item["pdp_page_url"] = "https://www.nykaa.com/abc/p/" + self.web_pid
                    item["created_by"] = "System"
                    item["created_on"] = self.current_time
                    item["status"] = 1
                    item = utils.clean_item_data(item)
                    items.append(item)
                    # self.logger.info("Data item Start", str(item))
                except Exception as e:
                    print(e)
                    # Create empty item with default values
                    empty_item = {
                        "pf_id": self.pf_id,
                        "crawl_id": self.crawl_id,
                        "sku_id": self.sku_id,
                        "pincode": self.pincode,
                        "location_id": self.location_id,
                        "location_name": self.location,
                        "web_pid": self.web_pid,
                        "brand_id": self.brand_id,
                        "brand_name": self.brand_name,
                        "pdp_title_value": "",
                        "pdp_rating_value": 0,
                        "pdp_review_count": 0,
                        "pdp_rating_count": 0,
                        "pdp_qa_count": 0,
                        "five_star": 0,
                        "four_star": 0,
                        "three_star": 0,
                        "two_star": 0,
                        "one_star": 0,
                        "price_rp": 0.0,
                        "price_sp": 0.0,
                        "pdp_discount_value": 0.0,
                        "osa": 0,
                        "osa_remark": "",
                        "pdp_desc_value": "",
                        "pdp_image_count": 0,
                        "pdp_image_url_all": "",
                        "pdp_image_url": "",
                        "ec_number_of_images": 0,
                        "ec_number_of_videos": 0,
                        "reseller_name_crawl": "",
                        "delivery_date": "",
                        "pdp_page_url": response.url,
                        "created_by": "System",
                        "created_on": self.current_time,
                        "status": 0
                    }
                    items.append(utils.clean_item_data(empty_item))
        else:
            empty_item = {
                        "pf_id": self.pf_id,
                        "crawl_id": self.crawl_id,
                        "sku_id": self.sku_id,
                        "pincode": self.pincode,
                        "location_id": self.location_id,
                        "location_name": self.location,
                        "web_pid": self.web_pid,
                        "brand_id": self.brand_id,
                        "brand_name": self.brand_name,
                        "pdp_title_value": "",
                        "pdp_rating_value": 0,
                        "pdp_review_count": 0,
                        "pdp_rating_count": 0,
                        "pdp_qa_count": 0,
                        "five_star": 0,
                        "four_star": 0,
                        "three_star": 0,
                        "two_star": 0,
                        "one_star": 0,
                        "price_rp": 0.0,
                        "price_sp": 0.0,
                        "pdp_discount_value": 0.0,
                        "osa": 0,
                        "osa_remark": "OOS",
                        "pdp_desc_value": "",
                        "pdp_image_count": 0,
                        "pdp_image_url_all": "",
                        "pdp_image_url": "",
                        "ec_number_of_images": 0,
                        "ec_number_of_videos": 0,
                        "reseller_name_crawl": "",
                        "delivery_date": "",
                        "pdp_page_url": response.url,
                        "created_by": "System",
                        "created_on": self.current_time,
                        "status": 0
                    }
            item = utils.clean_item_data(empty_item)
            items.append(item)

        # Create Raw file without header
        for item in items:
            utils.create_raw_file(self.output_file, item.keys(), item)

        # Create Header file
        if items:
            item = items[0]
            output_dir = self.base_dir + "/output"
            output_filename = "header.txt"
            output_file = output_dir + "/" + output_filename
            header_row = "|".join(item.keys()) + "\r"
            utils.create_file(output_file, header_row)

            # Converting into list of tuple
            records = []
            columns = self.output_cols
            for item in items:
                record = tuple(item.get(col, "0") for col in columns if col in item)
                self.logger.debug(record)
                records.append(record)

            self.logger.info("Data inserting")

            tbl_columns_str = "`" + "`,`".join(self.output_cols) + "`"
            values_list = []
            values_list.extend(repeat("%s", len(self.output_cols)))
            tbl_columns_val = ",".join(values_list)

            mySql_insert_query = """INSERT INTO `nykaa_crawl_pdp` (""" + tbl_columns_str + """) VALUES (""" + tbl_columns_val + """)"""
            # self.logger.info(f"Data mySql_insert_query Start {mySql_insert_query}")
            try:
                self.cursor.executemany(mySql_insert_query, records)
                self.connection.commit()
            except Exception as err:
                self.logger.error("Mysql Error occured: {}".format(str(err)))

        return item

    def errback_httpbin(self, failure):
        # log all failures
        self.logger.error(repr(failure))

        if failure.check(HttpError):
            response = failure.value.response
            self.logger.error("HttpError on %s", response.url)
            output_dir = self.base_dir + "/output"
            output_filename = str(self.pincode) + "_error.txt"
            output_file = output_dir + "/" + output_filename
            error_row = str(self.pf_id) + "|" + str(self.location_id) + "|" + str(self.location) + "|" + str(
                self.pincode) + "|" + str(self.sku_id) + "|" + str(self.web_pid) + "|" + str(
                self.pdp_page_url) + "|" + "HttpError " + response.url + "\r"
            utils.create_file(output_file, error_row)

        elif failure.check(DNSLookupError):
            request = failure.request
            self.logger.error("DNSLookupError on %s", request.url)
            output_dir = self.base_dir + "/output"
            output_filename = str(self.pincode) + "_error.txt"
            output_file = output_dir + "/" + output_filename
            error_row = str(self.pf_id) + "|" + str(self.location_id) + "|" + str(self.location) + "|" + str(
                self.pincode) + "|" + str(self.sku_id) + "|" + str(self.web_pid) + "|" + str(
                self.pdp_page_url) + "|" + "DNSLookupError " + response.url + "\n\r"
            utils.create_file(output_file, error_row)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error("TimeoutError on %s", request.url)
            output_dir = self.base_dir + "/output"
            output_filename = str(self.pincode) + "_error.txt"
            output_file = output_dir + "/" + output_filename
            error_row = str(self.pf_id) + "|" + str(self.location_id) + "|" + str(self.location) + "|" + str(
                self.pincode) + "|" + str(self.sku_id) + "|" + str(self.web_pid) + "|" + str(
                self.pdp_page_url) + "|" + "TimeoutError " + response.url + "\n\r"
            utils.create_file(output_file, error_row)