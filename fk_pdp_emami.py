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
from bs4 import BeautifulSoup as bs
import mysql.connector
from scrapy.selector import Selector
from scrapy.loader import ItemLoader
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
from utils import utils
from db.db_action import DBAction

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

SETTINGS = scrapy.utils.project.get_project_settings()
from urllib.parse import urlparse

class FKWebsitePDPSpider(InitSpider):
    name = "fk_pdp_emami"

    allowed_domains = ["flipkart.com"]
    start_urls = ["https://flipkart.com/"]
    custom_settings = {
        # specifies exported fields and order
        "DOWNLOAD_DELAY": 3,
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
    HOME_URL = "https://flipkart.com/"

    def __init__(self, inputs,
                 **kw):  # env=None, db_name=None, crawl_id=None, location_search="0", pf_id=None, sku_id=None, sku_name=None, web_pid=None, page_url=None, brand_id=None, brand_name=None, category_id=None, location_id=None, location=None, pincode=None, **kw):
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
        print("PDP Page Url: " + inputs.get("page_url"))

        self.site = self.name
        self.env = inputs.get("env")
        self.db_name = inputs.get("db_name")
        self.crawl_id = inputs.get("crawl_id")
        self.pf_id = inputs.get("pf_id")
        self.sku_id = inputs.get("sku_id")
        self.web_pid = inputs.get("web_pid")
        # self.web_pid = "ECKEFWZ69QAFPQWD"
        self.pdp_page_url = inputs.get("page_url")
        # self.pdp_page_url = "https://www.flipkart.com/abc/p/xyz?pid=ECKEFWZ69QAFPQWD"
        self.brand_id = inputs.get("brand_id")
        self.brand_name = inputs.get("brand_name")
        self.location_search = inputs.get("location_search")
        try:
            self.pincode = inputs.get("pincode")
            # self.pincode = "400005"
        except:
            self.pincode = "530068"
        self.location_id = inputs.get("location_id")
        self.location = inputs.get("location")

        self.base_dir = "C:/var/logs/" + self.site
        self.output_file = self.base_dir + "/output/" + self.pincode + "_" + self.web_pid + ".txt"

        self.output_cols = ["pf_id", "crawl_id", "sku_id", "web_pid", "pdp_title_value", "brand_id", "brand_name",
                            "extracted_brand_name", "price_rp",
                            "price_sp", "pdp_rating_value", "pdp_review_count", "pdp_rating_count", "pdp_qa_count",
                            "pdp_desc_value",
                            "pdp_image_count", "pdp_image_url", "pdp_image_url_all", "osa", "osa_remark",
                            "pdp_page_url", "pdp_discount_value",
                            "location_id", "location_name", "pincode", "delivery_date", "created_by", "created_on",
                            "ec_number_of_images", "ec_number_of_videos", "pdp_number_of_bulletin",
                            "pdp_bulletin_value", "reseller_name_crawl", "seller_rank", "five_star", "four_star",
                            "three_star", "two_star", "one_star", "status"
                            ]

        self.visit_count = str(random.choice([10, 11, 12, 13]))

        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as error:
            self.logger.error("MySQL Error: " + error)
            print("Connection error with the database", error)

    def init_request(self):
        self.web_pid_search()
        # Home Page Request
        # self.logger.info("Home Page Request")

        # yield scrapy.Request(
        #     url=self.HOME_URL,
        #     method="GET",
        #     headers={
        #                 "X-Requested-With": "XMLHttpRequest",
        #                 "Accept": "text/html,*/*",
        #                 "Content-Type": "application/x-www-form-urlencoded"
        #             },
        #     cookies={},
        #     callback=self.web_pid_search,
        #     errback=self.errback_httpbin,
        #     )

    def web_pid_search(self):
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Content-Length': '120',
            'Content-Type': 'application/json',
            'Cookie': 'T=clypbc5z43f212bfisj4tr984-BR1721188743232; K-ACTION=null; rt=null; vw=1536; dpr=1.25; _gcl_au=1.1.1570263868.1764577170; vh=695; _ga=GA1.1.1897072890.1768990121; _ga_HRPPMD631D=GS2.1.s1769070168$o1$g1$t1769070222$j6$l0$h0; at=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImQ2Yjk5NDViLWZmYTEtNGQ5ZC1iZDQyLTFkN2RmZTU4ZGNmYSJ9.eyJleHAiOjE3NzEzMDk3MTIsImlhdCI6MTc2OTU4MTcxMiwiaXNzIjoia2V2bGFyIiwianRpIjoiMGU2MzllY2ItZWM2ZS00NjgwLWI2M2UtNDE5ZmE3YjIyNDA2IiwidHlwZSI6IkFUIiwiZElkIjoiY2x5cGJjNXo0M2YyMTJiZmlzajR0cjk4NC1CUjE3MjExODg3NDMyMzIiLCJrZXZJZCI6IlZJRkJFMDY2OTQxRjVDNEM4OEI2MDUxNUY4MzczRTg3MjEiLCJ0SWQiOiJtYXBpIiwidnMiOiJMTyIsInoiOiJIWUQiLCJtIjp0cnVlLCJnZW4iOjR9.IKenGkTu1AyGugcoGdfFElQS0vn-zZgkp1gM3xITry8; _ga_ZPGRNTNNRT=GS2.1.s1769593518$o6$g0$t1769593518$j60$l0$h0; AMCVS_17EB401053DAF4840A490D4C%40AdobeOrg=1; AMCV_17EB401053DAF4840A490D4C%40AdobeOrg=-227196251%7CMCIDTS%7C20490%7CMCMID%7C00086832722153050842946098593820245571%7CMCAAMLH-1770883963%7C12%7CMCAAMB-1770883963%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1770286363s%7CNONE%7CMCAID%7CNONE; S=d1t11CRw/Jj8cBj8/Pz8/Pyg/PyCYeAT9sE9bH2q4WRl/2yi7moHVfLZn3yrUgrt2niKtr8FneEFQtM6ZV40gON2Dig==; vd=VIFBE066941F5C4C88B60515F8373E8721-1767761730552-10.1770279332.1770279139.157087608; SN=VIFBE066941F5C4C88B60515F8373E8721.TOKA11A23DA3E744C2395DCA59FA27DACFD.1770279343811.LO; ud=4.yLMB0bKfvQdG3yvxWxMfS-rYCYvI9X15on9Jpz-4oS5FE5XFE1fDFX3Twz28OmpYaTwYImUY5Owk-GcQuucLRFoJ0gRE3cloE5V_Jyht8yGILPSbSjWFicpmldsbJaKVAyVI1cseSuVjOtL36UOoO67__P3J9Yszy3KoWihr2dEt6WtFWSrc3_dzSrk0SL5hUOSpfQMyJcPX2t2KZkQGWxAuOU03j-rgK95XJiMomFM9l2ciOZWn746qbNcJHWx6NylKScF2bjpdl-QVrJ7Xw7Y0GU_TR7isaYtDsH5nWVrCLXiDTbEVWKXD1fxb4vJKjkQpKCDakUZkvDuFBiQm1KiRjIp79Rlo7jNT2h6kPy3VpI8P9LfaSO9G4oU7zInDa4w0VfZCI7Deb9TzPWysJPaaUacTuTimpg3ktkejUWb3K6-E__yV1xWFdrcWjS0fy9895ljhVDxt_pDSHiEH33S-i7e2_9m7n-zMNEQ1T6vsE8csg8bXcw7Wl98zR1Tj92v8ijRegpzMs15swgNpcmq6y2ymtdkqdC0Vw1vtms9Lvsif-1Kf6-dKqlGTnbto',
            'Host': '2.rome.api.flipkart.com',
            'Origin': 'https://www.flipkart.com',
            'Referer': 'https://www.flipkart.com/',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'X-User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 FKUA/website/42/website/Desktop'
        }

        updated_url = self.pdp_page_url
        'https://flipkart.com/abc/p/xyz?pid=BWSESTMUYGXGQYPB&marketplace=GROCERY'
        'https://flipkart.com/abc/p/xyz?pid=MSCD93YTZWRGZ7GQ&lid=LSTMSCD93YTZWRGZ7GQ'
        parsed_url = urlparse(updated_url)

        # remove leading slash
        desired_url = parsed_url.path.lstrip('/') + '?' + parsed_url.query
        print(desired_url, "ram")
        pin = '530068'
        if str(self.location_search) == "1":
            pin = self.pincode

        json_data = {
            'pageUri': '/' + desired_url.strip(),
            'locationContext': {
                'pincode': pin,
            },
            'isReloadRequest': True,
        }
        url = "https://2.rome.api.flipkart.com/api/4/page/fetch"
        try:
            output =  requests.request("POST", url, headers=headers, json=json_data)
        except:
            time.sleep(2)
            output = requests.request("POST", url, headers=headers, json=json_data)


        webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        filename = "/%s-%s.html" % (str(self.pincode), self.site)
        # if str(self.inputs.get("pdp_snapshot")) == "1":
        #     utils.save_source_content(webpage_dir, filename, response.body)
        #     self.logger.info("Saved file %s" % filename)
        if self.inputs.get("pdp_snapshot") == 1 or True:
            utils.save_source_content(webpage_dir, filename, output.text)
            self.logger.info("Saved file %s" % filename)
        self.parse_detail_page(output, self.web_pid)

        # self.logger.info("Got successful response from {}".format(response.url))
        # self.logger.info(response.request.headers)

        web_pid = self.web_pid
        print(self.pdp_page_url)
        self.logger.info("Crawl WEB PID : " + web_pid)

        self.visit_count = str(random.choice([2, 3, 4, 5]))



    def moq(self):
        url = self.pdp_page_url
        headers = {'Accept': 'application/pdf'}

        response = requests.get(url, headers=headers)
        soup = bs(response.text, 'html.parser')
        print(soup, "navvvv")

        min_order_quantity_div = soup.find('div', class_='_1REMSq _1B0GOL _6aiF2j')
        if min_order_quantity_div:
            min_order_quantity_text = min_order_quantity_div.get_text(strip=True)
            min_order_quantity_numeric = re.search(r'\d+', min_order_quantity_text).group()
        else:
            min_order_quantity_numeric = 1

        # Count occurrences of class _7eSDEz
        count_class_occurrences = len(soup.find_all(class_='_7eSDEz'))
        print(count_class_occurrences)

        return count_class_occurrences

    def days_until_delivery(self, delivery_date):
        # Get the current date
        current_date = datetime.now().date()

        # Convert the delivery date string to a datetime object
        delivery_date = datetime.strptime(delivery_date, "%d %b, %A")
        delivery_date = delivery_date.replace(year=current_date.year)

        # Calculate the difference in days
        difference = (delivery_date.date() - current_date).days

        if difference == 0:
            difference = 1

        return (difference)

    def parse_detail_page(self, response, web_pid):
        t = self.moq()
        # # self.logger.info("Got successful response from {}".format(response.url))
        # self.logger.info(response.request.headers)
        # if self.inputs.get("pdp_snapshot") == 1 or True:
        #     utils.save_source_content(webpage_dir, filename, response)
        #     self.logger.info("Saved file %s" % filename)
        # self.logger.info("Data Extraction Start")

        items = list()
        item = dict()
        json_response = json.loads(response.text)
        Unavailable_1 = True
        jsn = json_response["RESPONSE"]
        title_Unavailable = ''
        try:
            Unavailable = jsn['slots']
            for solts in range(len(Unavailable)):
                try:
                    title_Unavailable = Unavailable[solts]['widget']['data']["announcementComponent"]['value']['title']
                except:
                    continue
                if "Currently Unavailable" in title_Unavailable:
                    Unavailable_1 = False
                    break
        except:
            Unavailable_1 = False

        # script = response.xpath("//script[@id='is_script']/text()").get()
        if Unavailable_1:
            json_response = json.loads(response.text)
            # print('********', json_response)
            print('--JSON--', jsn)
            if "pageData" in jsn:
                # if jsn is not None:
                print("check")
                data = jsn["pageData"]["pageContext"]
                print(data)
                sections = list()
                for key in data.keys():
                    data_array = data[str(key)]
                    try:
                        for sec in data_array:
                            sections.append(sec)
                    except:
                        print('bool', data_array)
                if len(sections[0]) == 1:
                    data = jsn["slots"]

                    print(data)
                    sections = list()
                    for key in data:
                        sections.append(key)
                product_detail = None
                product_specification = None
                physical_attach = None
                multimedia = None
                qna = None
                highlights = None
                texts = None
                availability = None
                price_dict1 = None
                for section in sections:
                    try:
                        if "PRODUCT_SPECIFICATION" in section["elementId"]:
                            product_specification = section
                        elif "PHYSICAL_ATTACH" in section["elementId"]:
                            physical_attach = section
                        elif "PRODUCT_DETAILS" in section["elementId"]:
                            product_detail = section
                        elif "MULTIMEDIA" in section["elementId"]:
                            multimedia = section
                        elif "QNA" in section["elementId"]:
                            qna = section
                        elif "HIGHLIGHTS" in section["elementId"]:
                            highlights = section
                        elif "TEXT" in section["elementId"]:
                            texts = section
                        elif "AVAILABILITY" in section["elementId"]:
                            availability = section
                        elif "PRODUCT_PAGE_SUMMARY_V2" in section["elementId"]:
                            price_dict1 = section
                        else:
                            section = section
                    except (TypeError, ValueError, AttributeError, KeyError) as ke:
                        continue

                # for key specification
                if product_specification is not None:
                    try:
                        listing_manufacturer_info = product_specification["widget"]["data"]["listingManufacturerInfo"][
                            "value"]
                        detailed_components = listing_manufacturer_info["detailedComponents"]
                        manufacturer = ", ".join(detailed_components[0]["value"]["callouts"])
                        mapped_cards = listing_manufacturer_info["mappedCards"]
                        for card in mapped_cards:
                            if card["key"].strip() == "Country of Origin":
                                country_of_origin = ", ".join(card["values"])
                        model_number = ""
                    except  (TypeError, ValueError, AttributeError, KeyError) as ke:
                        manufacturer = ""
                        country_of_origin = ""
                        model_number = ""

                else:
                    country_of_origin = ""
                    manufacturer = ""
                    model_number = ""

                details = ""
                print("--TEXTS--", texts)
                if texts is not None:
                    renderable_components = texts["widget"]["data"]["renderableComponents"]
                    if len(renderable_components) > 1:
                        for item in renderable_components:
                            details = details + ";" + item["value"]["text"].replace("<p>", "")
                    else:
                        details = renderable_components[0]["value"]["text"]
                    # specification = renderable_components["specification"]
                    # about_this_item = specification
                else:
                    renderable_components = ""
                    details = ""
                    # specification = []
                    # about_this_item = specification

                print(details, "--DET--")
                if details == "":
                    if "slots" in jsn:
                        try:
                            det = jsn["slots"]
                            for i in range(0, len(det)):
                                j = det[i]
                                if j["id"] == 25:
                                    details = j["widget"]["data"]["renderableComponents"][0]["value"]["text"]
                            print("-----DETAILS-----")
                            print(details)
                        except Exception as e:
                            details = ""
                            print("--ERROR--", e)
                else:
                    print("-----DETAILS2-----")
                    print(details)

                if details == "":
                    if "slots" in jsn:
                        try:
                            det = jsn["slots"]
                            for i in range(0, len(det)):
                                j = det[i]
                                if j["id"] == 26:
                                    details = j["widget"]["data"]["renderableComponents"][0]["value"]["text"]
                            print("-----DETAILS-----")
                            print(details)
                        except Exception as e:
                            details = ""
                            print("--ERROR--", e)
                else:
                    print("-----DETAILS3-----")
                    print(details)

                if highlights is not None:
                    renderable_components = highlights["widget"]["data"]["highlights"]["value"]["text"]
                    pdp_bullet_points_value = renderable_components
                    pdp_number_of_bulletin = len(renderable_components)
                    print(pdp_bullet_points_value, "****N")
                else:
                    pdp_bullet_points_value = ""
                    pdp_number_of_bulletin = ""

                if renderable_components == "":
                    if "slots" in jsn:
                        try:
                            det = jsn["slots"]
                            for i in range(0, len(det)):
                                j = det[i]
                                if j["id"] == 15:
                                    renderable_components = j["widget"]["data"]["pdp_bullet_points_value"]["value"][
                                        "text"]
                            print("pdp_bullet_points_value")
                            print(renderable_components)
                            pdp_number_of_bulletin = len(renderable_components)
                        except Exception as e:
                            pdp_bullet_points_value = ""
                            print("--ERROR--", e)
                else:
                    print("pdp_number_of_bulletin_final")
                    print(pdp_number_of_bulletin)

                if physical_attach is not None:
                    in_stock = physical_attach["widget"]["data"]["parentProduct"]["value"]["availability"][
                        "displayState"]
                else:
                    in_stock = ""

                if qna is not None:
                    try:
                        answered_questions = qna["widget"]["data"]["questions"]
                        if answered_questions is None:
                            answered_questions = []
                    except (TypeError, ValueError, AttributeError, KeyError) as nt:
                        answered_questions = []
                    answered_questions = len(answered_questions)
                else:
                    answered_questions = 0

                images_list = list()
                try:
                    images = jsn["slots"][2]["widget"]["data"]["multimediaComponents"]
                    print(images, "--IMAGES--")
                    for image in images:
                        if image["value"]["contentType"] == "IMAGE":
                            print(image["value"], "--IMG--")

                            images_list.append(
                                image["value"]["url"].replace("{@width}", "612").replace("{@height}", "612").replace(
                                    "{@quality}", "70"))
                        else:
                            continue
                except (TypeError, ValueError, AttributeError, KeyError) as ke:
                    images_list = list()

                try:
                    image_url = images_list[0]
                except (IndexError, KeyError, TypeError, AttributeError) as err:
                    image_url = ""
                page_context = jsn["pageData"]["pageContext"]
                print('#####', page_context)
                try:
                    marketplace = page_context["marketplace"]
                    if marketplace == None:
                        marketplace = price_dict1['widget']['data']['ratingsAndReviews']['action']['params'][
                            "marketplace"]
                    print('******', marketplace)
                except:
                    marketplace = "Flipkart"
                try:
                    extracted_web_pid = page_context["productId"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    extracted_web_pid = ""
                try:
                    title = page_context["titles"]["title"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    title = ""
                try:
                    subtitle = page_context["titles"]["subtitle"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    subtitle = ""
                try:
                    brand = page_context["brand"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    brand = ""

                fetch_id = page_context["fetchId"]

                # rating and review
                try:
                    try:
                        rating = page_context["rating"]["average"]
                    except:
                        rating = price_dict1['widget']['data']['ratingsAndReviews']['value']["rating"]["average"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    rating = 0
                try:
                    try:
                        rating_count = page_context["rating"]["count"]
                    except:
                        rating_count = price_dict1['widget']['data']['ratingsAndReviews']['value']["rating"]["count"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    rating_count = 0

                try:
                    try:
                        review_count = page_context["rating"]["reviewCount"]
                    except:
                        review_count = price_dict1['widget']['data']['ratingsAndReviews']['value']["reviewCount"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    review_count = 0

                try:
                    try:
                        star_values = page_context["rating"]["breakup"]
                    except:
                        star_values = price_dict1['widget']['data']['ratingsAndReviews']['value']["rating"]["breakup"]
                    star_keys = ["one", "two", "three", "four", "five"]
                    stars = {star_keys[i]: star_values[i] for i in range(len(star_keys))}
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    stars = {"one": 0, "two": 0, "three": 0, "four": 0, "five": 0}
                # self.logger.debug("star: {}".format(stars))

                page_context_type = page_context["type"]

                item_id = page_context["itemId"]
                listing_id = page_context["listingId"]

                mrp = 0
                price = 0
                s_price = 0
                try:
                    pricing = price_dict1['widget']['data']["pricing"]
                    print("------------Pricing------------")
                    print(pricing)
                    currency = pricing['value']["finalPrice"]["currency"]
                    prices = pricing['value']["prices"]
                    price_dict = dict()

                    mrp = prices[0]["value"]
                    # mrp = prices["value"]
                    try:
                        price = prices[-1]["value"]
                    except:
                        price = prices[0]["value"]
                except (ValueError, KeyError, TypeError, AttributeError) as err:
                    mrp = 0
                    price = 0
                    currency = "INR"

                pricing = price_dict1['widget']['data']["pricing"]
                print("------------Pricing------------")
                print(pricing)
                try:
                    currency = pricing['value']["finalPrice"]["currency"]
                except:
                    currency = 0
                try:
                    prices = pricing['value']["prices"][1]['decimalValue']
                except:
                    prices = pricing['value']["prices"][0]['decimalValue']
                if mrp < price:
                    try:
                        mrp = pricing['value']["mrp"][2]['decimalValue']
                    except:
                        mrp = 0

                if mrp == 0 and price != 0:
                    mrp = price
                if price == 0 and mrp != 0:
                    price = mrp
                if s_price is not None and s_price != 0:
                    price = s_price

                try:
                    discount = pricing['value']["totalDiscount"]
                except (ValueError, KeyError, TypeError, AttributeError) as er:
                    discount = 0.0
                if discount == None:
                    discount = 0.0

                if mrp == 0:
                    if discount != 0.0:
                        mrp = price + (price * discount) / 100
                    else:
                        mrp = price
                savings = mrp - price

                # self.logger.info("MRP: {}".format(mrp))
                # self.logger.info("Price: {}".format(price))
                # self.logger.info("Discount: {}".format(discount))
                # self.logger.info("Saving: {}".format(savings))
                analytics_data = page_context["analyticsData"]
                if analytics_data == None:
                    analytics_data = price_dict1['widget']['data']["productDetailsAnnouncement"]['action']['params'][
                        "analyticsData"]
                category = analytics_data["category"]
                sub_category = analytics_data["subCategory"]
                super_category = analytics_data["superCategory"]
                vertical = analytics_data["vertical"]

                tracking_data = page_context["trackingDataV2"]
                try:
                    seller_name = tracking_data["sellerName"]
                except (ValueError, KeyError, TypeError, AttributeError) as er:
                    seller_name = ""
                try:
                    seller_rating = tracking_data["sellerRating"]
                except:
                    seller_rating = price_dict1['widget']['data']["sellerRating"]
                try:
                    product_status = tracking_data["productStatus"]

                except:
                    product_status = ''

                product_status_data = jsn['slots']
                for i_status in product_status_data:
                    try:
                        errorCode = i_status['widget']['data']["pincodeData"]['pincodeComponent']['value']['errorCode']
                        product_status = 'Out of Stock'
                        break
                    except:
                        pass

                if "current" in product_status:
                    product_status = "in stock"
                elif 'Out of Stock' in product_status:
                    product_status = "out of stock"
                else:
                    product_status = ""
                try:
                    delivery_date = tracking_data["slaText"]
                    print(delivery_date, "Shyam")
                    if delivery_date != None:
                        x = self.days_until_delivery(delivery_date)
                except (ValueError, KeyError, TypeError, AttributeError) as er:
                    x = ""

                print("------------Availablity---------")
                print(availability)
                if product_status == '':
                    if availability is not None:
                        announcement = availability["widget"]["data"]["announcementComponent"]["value"]["title"]
                        print(announcement)

                        if "Currently Unavailable" in announcement or "Sold Out" in announcement:
                            product_status = "out of stock"
                        else:
                            product_status = "in stock"

                    announcement2 = page_context["fdpEventTracking"]["events"]["psi"]["pls"]["availabilityStatus"]
                    if "IN_STOCK" in announcement2:
                        product_status = "in stock"

                    print(product_status)

                else:
                    print(title_Unavailable)
            def count_words(input_string):
                words = input_string.split()
                return len(words)

            item["marketplace"] = marketplace
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
            item["extracted_brand_name"] = brand if brand else ""

            item["pdp_review_count"] = review_count if review_count else 0
            item["pdp_rating_value"] = rating if rating else 0
            item["pdp_rating_count"] = rating_count if rating_count else 0
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
            if "out of stock" in product_status.lower():
                item["osa"] = 0
                item["osa_remark"] = "OOS"
            else:
                item["osa"] = 1
                item["osa_remark"] = "IN STOCK"

            item["manufacturer"] = manufacturer if manufacturer else ""
            item["model_number"] = model_number if model_number else ""
            item["country_of_origin"] = country_of_origin if country_of_origin else ""
            item["shipping_type"] = ""

            # item["about_this_item"] =
            item["product_details"] = details
            item["pdp_desc_value"] = details

            item["pdp_image_count"] = len(images_list)
            item["pdp_image_url_all"] = ", ".join(images_list).replace('http://', 'https://')
            item["pdp_image_url"] = image_url.replace('http://', 'https://')
            item["ec_number_of_images"] = 0
            item["ec_number_of_videos"] = 0
            item["aplus_images_list"] = ", ".join(images_list)

            item["pdp_number_of_bulletin"] = t
            item["pdp_bulletin_value"] = ";".join(pdp_bullet_points_value)

            item["reseller_name_crawl"] = seller_name
            item["reseller_info"] = seller_name
            item["seller_rating"] = seller_rating if seller_rating else 0
            item["seller_rank"] = 0

            item["delivery_date"] = x

            item["pdp_page_url"] = self.pdp_page_url
            item["group_id"] = 0
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 1
            item["pdp_title_count"] = count_words(item["pdp_title_value"])
            item["pdp_desc_count"] = count_words(details)
            item = utils.clean_item_data(item)
            items.append(item)
        else:
            item["marketplace"] = "Flipkart"
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
            item["pdp_title_value"] = "not available"
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
            item["osa_remark"] = "OOS"
            item["manufacturer"] = ""
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
            item["pdp_number_of_bulletin"] = ""
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
            item["pdp_title_count"] = 0
            item["pdp_desc_count"] = 0
            item = utils.clean_item_data(item)
            items.append(item)


        for item in items:
            utils.create_raw_file(self.output_file, item.keys(), item)

        # Create Header file
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
        # records = [tuple(item.values()) for item in items]

        # self.logger.info("Database connection create")
        self.logger.info("Data inserting")

        tbl_columns_str = "`" + "`,`".join(self.output_cols) + "`"
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)
        self.logger.debug(tbl_columns_str)
        mySql_insert_query = """INSERT INTO `flipkart_crawl_pdp` (""" + tbl_columns_str + """) VALUES (""" + tbl_columns_val + """)"""
        try:
            self.cursor.executemany(str(mySql_insert_query), records)
            products_count = self.cursor.rowcount
            self.connection.commit()
            self.connection.close()
        except self.cursor.Error as err:
            self.logger.error("Mysql Error occured: {}".format(str(err)))

        print("-----JSON ITEM-----")
        print("OSA")
        print(item["osa"])
        print(item["osa_remark"])
        json_item = json.dumps(item, indent=2)
        print(json_item)
        webpage_dir = "%s/response_logs/%s" % (self.base_dir, str(self.dt))
        try:
            if not os.path.exists(webpage_dir):
                os.makedirs(webpage_dir)
            filename = "/%s-%s-%s.json" % (str(self.pincode), self.site, self.web_pid)
            loc = webpage_dir + filename
            if item["osa_remark"] == "OOS":
                print(loc)
                print(str(self.inputs.get("pdp_snapshot")))

                with open(loc, "w") as json_file:
                    json_file.write(json_item)

                self.logger.info("Saved file %s" % filename)
                self.logger.info("Data Extraction Start")
            else:
                print("File not created because osa is not equal to 0.")
        except Exception as e:
            print(f"Error saving the file: {e}")

        webpage_dir2 = "%s/response_logs2/%s" % (self.base_dir, str(self.dt))
        try:
            if not os.path.exists(webpage_dir2):
                os.makedirs(webpage_dir2)
            filename2 = "/%s-%s-%s.json" % (str(self.pincode), self.site, self.web_pid)
            loc = webpage_dir2 + filename2
            if item["osa_remark"] != "OOS":
                print(loc)
                print(str(self.inputs.get("pdp_snapshot")))

                with open(loc, "w") as json_file:
                    json_file.write(json_item)

                self.logger.info("Saved file %s" % filename2)
                self.logger.info("Data Extraction Start")
            else:
                print("File not created because osa is not equal to 0.")
        except Exception as e:
            print(f"Error saving the file: {e}")
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
            output_dir = self.base_dir + "/output"
            output_filename = str(self.pincode) + "_error.txt"
            output_file = output_dir + "/" + output_filename
            error_row = str(self.pf_id) + "|" + str(self.location_id) + "|" + str(self.location) + "|" + str(
                self.pincode) + "|" + str(self.sku_id) + "|" + str(self.web_pid) + "|" + str(
                self.pdp_page_url) + "|" + "HttpError " + response.url + "\r"
            utils.create_file(output_file, error_row)

        elif failure.check(DNSLookupError):
            # this is the original request
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