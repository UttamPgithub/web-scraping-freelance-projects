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
import urllib.request
from amazoncaptcha import AmazonCaptcha
import cloudscraper
scraper = cloudscraper.create_scraper()
import certifi
# import tls_client
import undetected_chromedriver as uc


from selenium.webdriver.common.by import By


from scrapy.selector import Selector
from scrapy.loader import ItemLoader
from datetime import datetime
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError, TCPTimedOutError
from twisted.internet import reactor
from scrapy.utils.log import configure_logging
from scrapy.http import HtmlResponse
from w3lib.html import remove_tags
from slugify import slugify
from itertools import repeat
from bs4 import BeautifulSoup
from scrapy.spiders.init import InitSpider
from utils import utils
from db.db_action import DBAction


# Addons (For Now)
# from .addons import Get, Post, Session
from .amz_mods import *
import requests

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

SETTINGS = scrapy.utils.project.get_project_settings()

PINCODE_COOKIES = {}



# def change_pincode(session, headers, pincode):
#     url = "https://www.amazon.fr/portal-migration/hz/glow/address-change"
#     payload = {
#         "locationType": "LOCATION_INPUT",
#         "zipCode": str(pincode),
#         "storeContext": "NoStoreName",
#         "deviceType": "desktop",
#         "pageType": "Gateway",
#         "actionSource": "glow"
#     }

#     r = session.post(url, headers=headers, data=payload)
#     try:
#         if r.json().get("isAddressUpdated") == 1:
#             # store cookies in dictionary
#             PINCODE_COOKIES[str(pincode)] = requests.utils.dict_from_cookiejar(session.cookies)
#             return True
#     except Exception:
#         pass
#     return False

PINCODE_COOKIES = {}


def change_pincode(session, headers, pincode):
    # url = "https://www.amazon.fr/portal-migration/hz/glow/address-change"
    url = "https://www.amazon.fr/portal-migration/hz/glow/address-change?actionSource=glow"
    payload = {
          "locationType": "LOCATION_INPUT",
          "zipCode": "31905",
          "deviceType": "web",
          "storeContext": "grocery",
          "pageType": "Detail",
          "actionSource": "glow"
        }

    r = session.post(url, headers=headers, data=payload)

    updated = False
    try:
        data = r.json()
        if data.get("isAddressUpdated") == 1:
            updated = True
    except Exception:
        # Sometimes Amazon doesn't return JSON
        if r.status_code == 200 and "Set-Cookie" in str(r.headers):
            updated = True

    # Always store cookies if available
    if session.cookies:
        PINCODE_COOKIES[str(pincode)] = requests.utils.dict_from_cookiejar(session.cookies)

    return updated


def handle_continue_shopping_direct(session, response, headers):
    """Skip 'Continue shopping' form by jumping directly to the PDP URL."""
    soup = BeautifulSoup(response.text, "html.parser")
    hidden_input = soup.find("input", {"name": "amzn-r"})
    if not hidden_input:
        return response  # No continue shopping page

    pdp_path = hidden_input.get("value")
    if not pdp_path:
        return response

    pdp_url = "https://www.amazon.fr" + pdp_path
    resp2 = session.get(pdp_url, headers=headers)
    return resp2


# def change_pincode(session, headers, pincode):
#     url = "https://www.amazon.fr/portal-migration/hz/glow/address-change"
#     payload = {
#         "locationType": "LOCATION_INPUT",
#         "zipCode": str(pincode),
#         "storeContext": "NoStoreName",
#         "deviceType": "desktop",
#         "pageType": "Gateway",
#         "actionSource": "glow"
#     }
#     r = session.post(url, headers=headers, data=payload)
#     try:
#         return r.json().get("isAddressUpdated") == 1
#     except Exception:
#         return False

class AmzWebsitePDPSpider(InitSpider):
    name = "amz_spider_mnm_fr"
    custom_settings = {
        # specifies exported fields and order
        "DOWNLOAD_TIMEOUT": 60000,
        "DOWNLOAD_MAXSIZE": 12406585060,
        "DOWNLOAD_WARNSIZE": 0,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS_PER_IP": 1,
        "HTTPPROXY_ENABLED": True,
        "TELNETCONSOLE_ENABLED": False,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "scrapy_web_crawlers.middlewares.RandomUserAgentMiddleware": 1,
        }
    }
    HOME_URL = "https://www.amazon.fr/"

    def __init__(self, inputs, **kw):
        super(AmzWebsitePDPSpider, self).__init__(**kw)
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
        print("ENV:" + inputs.get("env"))

        self.site = self.name
        self.env = inputs.get("env")
        self.db_name = inputs.get("db_name")
        self.crawl_id = int(inputs.get("crawl_id"))
        self.pf_id = int(inputs.get("pf_id"))
        self.sku_id = int(inputs.get("sku_id"))
        self.web_pid = inputs.get("web_pid")
        self.pdp_page_url = inputs.get("page_url")
        # self.pdp_page_url = "https://www.amazon.fr/dp/B0F9WNK4HM"
        if inputs.get("brand_id") and inputs.get("brand_id") != "None":
            self.brand_id = int(inputs.get("brand_id"))
        else:
            self.brand_id = 0
        self.brand_name = inputs.get("brand_name")

        self.location_search = inputs.get("location_search")
        self.location_id = int(inputs.get("location_id"))
        self.location = inputs.get("location")
        self.pincode = inputs.get("pincode")
        self.sku_name = inputs.get("sku_name")

        self.base_dir = "C:/var/logs/" + self.site
        self.output_file = self.base_dir + "/output/" + self.pincode + "_" + self.web_pid + ".txt"

        self.output_cols = ["pf_id", "crawl_id", "sku_id", "web_pid", "pdp_title_value", "brand_id", "brand_name",
                            "extracted_brand_name", "price_rp",
                            "price_sp", "pdp_rating_value", "pdp_review_count", "pdp_rating_count", "pdp_qa_count",
                            "pdp_desc_value",
                            "pdp_image_count", "pdp_image_url", "pdp_image_url_all","aplus_images_list","mhri_images", "osa", "osa_remark",
                            "pdp_page_url", "pdp_discount_value",
                            "location_id", "location_name", "pincode", "delivery_date", "created_by", "created_on",
                            "ec_number_of_images", "ec_number_of_videos", "pdp_number_of_bulletin",
                            "pdp_bulletin_value", "reseller_name_crawl", "seller_rank", "five_star", "four_star",
                            "three_star", "two_star", "one_star", "status", "deal_flag", "pdp_top_review"
                            ]

        self.visit_count = str(random.choice([10, 11, 12, 13]))

        # self.session = Session()

        # self.session = tls_client.Session(client_identifier="chrome_114")
        self.session = requests.Session()
        # self.session.verify = certifi.where()

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        }

        # Visit homepage to initialize cookies
        self.session.get("https://www.amazon.fr/", headers=self.headers)


        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as error:
            self.logger.error("MySQL Error: " + error)
            print("Connection error with the database", error)

    def init_request(self):
        # Home Page Request
        self.logger.info("Home Page Request")
        self.session.get("https://www.amazon.fr/", headers=self.headers)


        updated = change_pincode(self.session, self.headers, str(self.pincode))
        self.logger.info(f"Pincode {self.pincode} updated: {updated}")



        print("pin got changed")
        time.sleep(random.uniform(0.5, 2.0))
        # pdp_response = Get(session=self.session, url=self.pdp_page_url)


        headers = {
            "authority": "www.amazon.fr",
            "method": "GET",
            "path": f"/dp/{self.web_pid}",
            "scheme": "https",

            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9",

            "cache-control": "max-age=0",
            "upgrade-insecure-requests": "1",

            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",

            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',

            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "navigate",
            "sec-fetch-user": "?1",
            "sec-fetch-dest": "document",

            "referer": "https://www.amazon.fr/",

            "cookie": "session-id=520-1840962-1626047; session-id-time=2082787201l; i18n-prefs=EUR; lc-acbfr=en_GB; ubid-acbfr=522-5389690-1955220; session-token=lAkRQNDy/IOIYB461017m4Xdc0AmmLsIzVRgcZfCiwkAL53FUewpUu3gB5wBMbcEBGSpuDKLoFfdW1EPUkXagUkpPDChxY8yHhnZjnDP7+YpMXnrA1Yu+29RHbf0m3avxqkUFnl0o4IdjKLUrePM9KcAFWwDqAUFhBeczZFP/TgHdj/RnGxbouXHrJvgqEnIW/jyEgTti9fQ8kcmyCwg0lXkWKxj9dWG; csm-hit=tb:5848A46ZCX6FT9M32Y40+s-5848A46ZCX6FT9M32Y40|1775652248279&t:1775652248279&adb:adblk_no; rxc=AJoAe9dIJ+HgUoAqbX0",

            "connection": "keep-alive"
        }

        pdp_response = requests.request("GET",f'https://www.amazon.fr/dp/{self.web_pid}', headers=headers,timeout=30)
        status_code = pdp_response.status_code
        soup = BeautifulSoup(pdp_response.text, 'html.parser')

        captcha_text = "we just need to make sure you're not a robot"
        continue_text = "Continue shopping"

        n = 5
        for i in range(0, n):
            if pdp_response is None or pdp_response.status_code != 200:
                break

            soup = BeautifulSoup(pdp_response.text, 'html.parser')

            # --- Case 1: Captcha page ---
            if captcha_text in soup.get_text():
                self.logger.warning("Amazon returned captcha page... trying to resolve")
                pdp_response = self.captcha_resolve(soup, i)

            # --- Case 2: Continue Shopping page ---
            elif continue_text in soup.get_text() and "/errors/validateCaptcha" in pdp_response.text:
                self.logger.warning("Amazon returned Continue Shopping page... skipping to PDP directly")
                pdp_response = handle_continue_shopping_direct(self.session, pdp_response, self.headers)

            else:
                break

        items = self.parse_detail_page(response=pdp_response, web_pid=self.web_pid,status_code=status_code)

        if len(items):
            self.logger.info(f'Scrapped PDP - {self.web_pid} {self.pdp_page_url}')
        else:
            self.logger.error(f'PDP Failed - {self.web_pid} {self.pdp_page_url}')

    allowed_domains = ["amazon.fr"]
    start_urls = ["https://www.amazon.fr/"]

    def web_pid_search(self, response):
        webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        filename = "/%s-%s.html" % (str(self.pincode), self.site)
        if True:
            utils.save_source_content(webpage_dir, filename, response.body)

        self.logger.info("Got successful response from {}".format(response.url))
        self.logger.info(response.request.headers)

        url = "https://www.amazon.fr/dp/"
        # for crawl_input in self.crawl_inputs:

        self.logger.info("Crawl web_pid : " + self.web_pid)
        yield scrapy.Request(
            url=self.pdp_page_url,
            method="GET",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": response.url
            },
            cookies={
                "amzn-app-id": "amazon.fr/20.04.0.350/20.04.0.350",
                'i18n-prefs': 'USD',
                'lc-main': 'en_US',
                "visitCount": self.visit_count
            },
            callback=self.parse_detail_page,
            errback=self.errback_httpbin,
            cb_kwargs=dict(web_pid=self.web_pid)
        )
        time.sleep(2)

    def parse_detail_page(self, response, web_pid,status_code):
        vec_number_of_image = 0

        items = list()
        try:
            webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
            if not os.path.exists(webpage_dir):
                os.makedirs(webpage_dir)
            filename = "/%s-%s-%s.html" % (str(self.pincode), self.site, web_pid)
            loc = webpage_dir + filename
            print(loc)

            # Get HTML text
            html_text = response.text if hasattr(response, "text") else str(response)

            if str(self.inputs.get("pdp_snapshot")) == "1" or True:
                with open(loc, "w", encoding="utf-8") as html_file:
                    html_file.write(html_text)
                self.logger.info("Saved file %s" % filename)

            self.logger.info("Data Extraction Start")
        except Exception as e:
            print("Error saving the file", e)

        # Use HTML text for parsing
        html_text = response.text if hasattr(response, "text") else str(response)
        response_selector = Selector(text=html_text)
        soup = BeautifulSoup(html_text, 'html.parser')
        # print("Atul-soup",soup)
        try:
            element = soup.select_one('#fulfillerInfoFeature_feature_div > div.offer-display-feature-text > div > span')

            # Check     if the element is found and print its text
            if element:
                adnan = (element.text)
        except:
            adnan = ""
        # soup = BeautifulSoup(html_code, 'html.parser')

        center_col = response_selector.xpath("//div[@id='centerCol']").get()
        if center_col != None:
            center_col_sel = Selector(text=center_col)

            name = center_col_sel.xpath("//span[@id='productTitle']/text()").get()
            if name is None or name == "" or len(name) == 0:
                name = response_selector.xpath("//span[@id='productTitle']").get()
            name = name.strip().replace("        ", '')
            if "        " in name:
                print("kunsh1", name.replace("        ", ''))
            brand = center_col_sel.xpath("//a[@id='bylineInfo']/text()").get()
            if brand is None:
                brand = center_col_sel.xpath("//div[@id='bylineInfo_feature_div']/div/text()").get()
                if brand is None:
                    brand = center_col_sel.xpath("//div[@id='productOverview_feature_div']").re_first(
                        r'Brand\s*</span>\s*</td>\s*<td[^>]+>\s*<span[^>]+>([^<]+)<')
            if brand:
                brand = re.sub("\s*Brand\s*:\s*", "", brand)
                brand = re.sub("\s*Visit the\s*", "", brand)
                brand = re.sub("\s*Store\s*", "", brand)
            else:
                brand = name and name.split(' ', 1)[0] or brand
            self.logger.info("brand: {0}".format(brand))

            rating_value = 0.0
            rating_count = 0
            five_star = four_star = three_star = two_star = one_star = 0

            # ---------------- RATINGS (ACR POPOVER STRUCTURE) ----------------
            try:
                rating_value = response_selector.xpath(
                    "//span[@id='acrPopover']//span[@class='a-icon-alt']/text()"
                ).re_first(r"([0-9.]+)")

                rating_value = float(rating_value) if rating_value else 0.0
            except Exception:
                rating_value = 0.0

            try:
                rating_count = response_selector.xpath(
                    "//span[@id='acrCustomerReviewText']/text()"
                ).re_first(r"([\d,]+)")

                rating_count = int(rating_count.replace(",", "")) if rating_count else 0
            except Exception:
                rating_count = 0


            five_star = four_star = three_star = two_star = one_star = 0

            try:
                rows = response_selector.xpath("//ul[@id='histogramTable']/li")

                if rows and rating_count > 0:
                    for row in rows:
                        try:
                            # 1️⃣ Get percentage (MOST RELIABLE)
                            percent = row.xpath(".//div[@class='a-meter']/@aria-valuenow").get()

                            # 2️⃣ Get star number
                            star_text = row.xpath(".//a/@aria-label").get()

                            if not percent or not star_text:
                                continue

                            percent = int(percent)

                            # Extract star number safely
                            match = re.search(r"(\d)\s*star", star_text.lower())
                            if not match:
                                continue

                            star = match.group(1)
                            count = round((percent / 100) * rating_count)

                            if star == "5":
                                five_star = count
                            elif star == "4":
                                four_star = count
                            elif star == "3":
                                three_star = count
                            elif star == "2":
                                two_star = count
                            elif star == "1":
                                one_star = count

                        except Exception:
                            continue  # skip bad row safely

            except Exception as e:
                self.logger.warning(f"Star breakup skipped: {e}")

            # QA Section
            try:
                answered_questions_sel = Selector(
                    text=center_col_sel.xpath("//div[@id='ask_feature_div']").get())
                answered_questions = answered_questions_sel.xpath(
                    "//a[@id='askATFLink']/span[@class='a-size-base']/text()").re_first('([0-9,\.\+]+)\s*answered')
                if answered_questions is not None:
                    answered_questions = answered_questions.replace(
                        "+", "").replace(",", "")
                else:
                    answered_questions = 0
            except:
                answered_questions = 0

            self.logger.info("rating: " + str(rating_value))
            self.logger.info("rating count: " + str(rating_count))
            self.logger.info("answered_questions: " + str(answered_questions))
            self.logger.info(
                f"ratings star: "
                f"5★={five_star}, "
                f"4★={four_star}, "
                f"3★={three_star}, "
                f"2★={two_star}, "
                f"1★={one_star}"
            )

            price = mrp = "0"
            currency = "INR"
            savings = discount = 0

            try:
                # -------------------------------------------------
                # 1) PDP SP (NEW XPATHS – QCOM / GROCERY SAFE)
                # -------------------------------------------------
                price = response_selector.xpath('//div[@id="desktop_accordion"]//span[@class="a-price-whole"]/text()').get('').strip()
                if price == '':
                    price = response_selector.xpath(
                        '//*[@id="tp-tool-tip-price"]/span/span[@class="a-price-whole"]/text()').get('').strip()
                if price == '':
                    price = response_selector.xpath(
                        "//div[contains(@class,'a-spacing-none') and contains(@class,'aok-align-center')]//span[contains(@class,'aok-offscreen')]/text()"
                    ).get()

                # fallback
                if not price:
                    price = response_selector.xpath(
                        "//span[contains(@class,'priceToPay')]//span[@class='a-offscreen']/text()"
                    ).get()

                price = re.sub(r"[^\d.]", "", price) if price else "0"

                # -------------------------------------------------
                # 2) PDP MRP (STRIKE PRICE – NEW LAYOUT)
                # -------------------------------------------------
                mrp = response_selector.xpath(
                    "//div[contains(@class,'centralizedApexBasisPriceCSS')]"
                    "//span[@class='a-offscreen']/text()"
                ).get()

                if not mrp:
                    mrp = response_selector.xpath(
                        "//div[@id='centerCol']//span[@data-a-strike='true']//span[@class='a-offscreen']/text()"
                    ).get()

                mrp = re.sub(r"[^\d.]", "", mrp) if mrp else price


                price_f = float(price)
                mrp_f = float(mrp)

                if mrp_f > price_f > 0:
                    savings = round(mrp_f - price_f, 2)
                    discount = round((savings / mrp_f) * 100, 2)
                else:
                    savings = discount = 0

            except Exception as e:
                self.logger.warning(f"PRICE ERROR: {e}")
                price = mrp = "0"
                savings = discount = 0
                currency = "INR"


            in_stock = response_selector.xpath("//div[@id='availability']/span/text()").get()
            if in_stock:
                in_stock = "In stock"
            if not in_stock:
                in_stock = response_selector.xpath("//div[@id='availability-string']/span/text()").get()
                if in_stock:
                    in_stock = "In stock"
            if not in_stock:
                in_stock_path = response_selector.xpath('//span[@id="submit.add-to-cart"]/span/span/text()').get(
                    "").strip()
                if "Add to basket".lower() in in_stock_path.strip():
                    in_stock = "In stock"
                    not_date_in_stock = response_selector.xpath(
                        '//span[@id="submit.add-to-cart"]//input[@disabled="disabled"]/following-sibling::span/text()').get(
                        "")
                    if "Add to basket".lower() in not_date_in_stock.strip():
                        in_stock = ""

            if not in_stock:
                # Always extract from the full response FIRST
                in_stock = response_selector.css("#availability span.a-color-success::text").get()

            # Backup: some pages use different class
            if not in_stock:
                in_stock = response_selector.css("#availability span::text").get()

            # Buy-box availability (common case for groceries)
            if not in_stock:
                in_stock = response_selector.css("#availabilityInsideBuyBox_feature_div span::text").get()

            # Fallback: wildcard text search
            if not in_stock:
                in_stock = response_selector.xpath(
                    "//*[contains(text(),'In Stock') or contains(text(),'In stock')]/text()"
                ).get()
            if not in_stock:
                in_stock_path = response_selector.xpath('//span[@id="submit.add-to-cart"]/span/span/text()').get("").strip()
                if "Add to cart".lower() in in_stock_path.strip():
                    in_stock = "In stock"

            # Normalize
            in_stock = in_stock.strip().lower() if in_stock else ""
            if not mrp:
                in_stock = ""



            # no of vedios
            # Find the element by tag name and attributes
            try:
                video_count = soup.find('span', {'id': 'videoCount',
                                                 'class': 'a-size-mini a-color-secondary video-count a-text-bold a-nowrap'})
                vedio_count = (video_count.text)
                print(vedio_count)
                try:
                    ec_vedio = (vedio_count[0])
                    if ec_vedio == "V":
                        ec_vedio = 1
                    elif ec_vedio > "1":
                        ec_vedio = int(vedio_count[0])
                    else:
                        ec_vedio = 0
                except:
                    ec_vedio = 0
            except:
                ec_vedio = 0

            # Seller Section
            seller = response_selector.xpath('//span[contains(text(),"Seller")]/../following-sibling::div/text()').get()
            if not seller:
                seller = response_selector.css('#merchant-info a span::text').get() or center_col_sel.xpath(
                    "//a[@id='sellerProfileTriggerId']/text()").get()
            if not seller:
                seller = response_selector.css('#fresh-merchant-info a span::text').get() or center_col_sel.xpath(
                    "//div[@id='fresh-merchant-info']/a/text()").get()
            if not seller:
                try:
                    seller = soup.find('a', {'id': 'sellerProfileTriggerId'}).text.strip()
                except:
                    seller = ""
            # New Implementation
            if not seller:
                seller_element = soup.select_one('#merchant-info a') or soup.select_one('#fresh-merchant-info a')
                if seller_element:
                    seller = getattr(seller_element, 'text', '').strip() or None

            # print('Seller', seller, self.pdp_page_url)

            amazon_shipping_type = center_col_sel.xpath(
                "//span[@id='price-shipping-message']/i/span[@class='a-icon-text-fba']/text()").get()

            info = center_col_sel.xpath(
                "//div[@id='productOverview_feature_div']/div[@class='a-section a-spacing-small a-spacing-top-small']").get()
            feature_bullets = center_col_sel.xpath("//div[@id='feature-bullets']")

            about_this_items = []
            about_this_item = ""

            try:
                # Bulletin Value fix (new implementation)
                # Grabs every bullet even if it is hidden [hidden by default]
                add_bullets = response_selector.css('#feature-bullets li span::text').getall()
                add_bullets = [item.replace("\n", "").strip() for item in add_bullets]
            except:
                # Failsafe (old)
                add_bullets = feature_bullets.xpath("//div[@aria-live='polite']/div/ul/li").getall()
                add_bullets = [remove_tags(item.replace("\n", "").strip()) for item in add_bullets]

            if add_bullets is None:
                add_bullets = []

            if len(add_bullets) > 0:
                add_bullet = ";".join(add_bullets)
            else:
                add_bullet = ""

            # ----------------------------
            # Image extraction block
            # ----------------------------
            images_list = []
            image_url = ""
            vec_number_of_image = 0  # default
            ec_images_list = []  # default
            a_plus_image_count = 0  # default
            thumbnail_images = []

            # 1) AltImages (thumbnails)
            if "altImages" in response.text:
                for img in response_selector.css("#altImages .a-button-thumbnail img"):
                    if "common" not in img.attrib.get("src", ""):
                        images_list.append(img.attrib["src"])
                        thumbnail_images.append(img.attrib["src"])

                if images_list:
                    image_url = images_list[0]
                    vec_number_of_image = len(images_list)

            # 2) Main Image JSON (data-a-dynamic-image)
            main_img_json = response_selector.css("#imgTagWrapperId img::attr(data-a-dynamic-image)").get()
            if main_img_json:
                try:
                    img_dict = json.loads(main_img_json)
                    for img_url in img_dict.keys():
                        if img_url not in images_list:
                            images_list.append(img_url)
                    vec_number_of_image = len(images_list)
                except Exception as e:
                    self.logger.warning(f"Failed to parse main image JSON: {e}")

            # 3) A+ Image Section
            try:
                ec_images_sel = Selector(text=response_selector.xpath("//div[@id='aplus']").get())
                ec_images_list = ec_images_sel.xpath("//img/@data-src").extract()
                self.logger.info(f"A+ images: {ec_images_list}")
                if ec_images_list:
                    images_list.extend(ec_images_list)
                    vec_number_of_image = len(set(images_list))  # avoid duplicates
            except Exception as e:
                self.logger.warning(f"A+ image parsing failed: {e}")
                ec_images_list = []  # ensure defined even on error

            # 4) A+ Content Images (secondary section)
            try:
                a_plus_content_images = response_selector.xpath("//div[@id='aplus_feature_div']//img/@src").getall()
                if a_plus_content_images == []:
                    a_plus_content_images = response_selector.xpath("//div[@id='aplus_feature_div']//img/@src").getall()
                a_plus_image_count = int(len(a_plus_content_images))
            except Exception:
                a_plus_image_count = 0

            # Carousel Images

            try:
                Carousel_images = response_selector.xpath(
                    '//div[@class="apm-brand-story-background-image"]//img/@src').getall()
                Carousel_image_count = int(len(Carousel_images))
            except Exception:
                Carousel_image_count = 0

            # Forth Rank Implementation
            try:
                best_sellers_rank = ""
                rankings = []
                # First Ranking (returns list -> [rank, rank category])
                if 'SalesRank' in response:
                    rankings += response_selector.css('#SalesRank').re(
                        '.*Bestsellers\s*Rank:\s*.+#([^\s<]+)\s*in\s*([^\(]+)')
                elif 'Best Sellers Rank:' in response:
                    rankings += response_selector.css('ul').re('#([^\s<]+)\s*in\s*([^\(]+)')[:2]

                # Other rankings
                if 'zg_hrsr_item' in response:
                    other_rankings = response_selector.css('.zg_hrsr_item')
                else:
                    other_rankings = response_selector.css('.zg_hrsr li')

                # Grab others
                for li in other_rankings:
                    rankings.append(li.css('span::text').get().replace('#', '').replace(' in', '').strip())
                    rankings.append(li.css('a::text').get())

                if rankings:
                    best_sellers_rank = ';'.join([rank.strip().replace(',', '').replace(' ', '') for rank in rankings])
            except:
                best_sellers_rank = ""

            if "<h2>Product details</h2>" in response.text:
                self.logger.info("Page Type 1 layout found")

                product_dtls_sel = Selector(
                    text=response_selector.xpath("//div[@id='detailBulletsWrapper_feature_div']").get())
                technical_details = product_dtls_sel.xpath("//div[@id='detailBulletsWrapper_feature_div']")
                # additional_information = product_dtls_sel.xpath("//div[@id='productDetails_db_sections']")
                product_details = product_dtls_sel.xpath("//div[@id='detailBullets_feature_div']/text()").get()

                model_number = technical_details.re_first(
                    r'<span class="a-text-bold">\s*Item\s*model\s*number\s*:\s*</span>\s*<span>([^<]*)<')
                manufacturer = technical_details.re_first(
                    r'<span class="a-text-bold">\s*Manufacturer\s*:\s*</span>\s*<span>([^<]*)<')
                country_of_origin = technical_details.re_first(
                    r'<span class="a-text-bold">\s*Country\s*of\s*Origin\s*:\s*</span>\s*<span>([^<]*)<')
                extracted_web_pid = technical_details.re_first(
                    r'<span class="a-text-bold">\s*ASIN\s*[^:]+:\s*[^<]+</span>\s*<span>([^<]*)<')
                if not best_sellers_rank:
                    best_sellers_rank = technical_details.re(
                        r'<span class="a-text-bold">\s*Best Sellers Rank\s*:\s*<\/span>\s*(.+?)\s*<ul[^>]*>\s*<li><span[^>]*>(.+?)\s*<\/a>')
                    best_sellers_rank = remove_tags("/".join(best_sellers_rank))

            elif '<div id="prodDetails" class="a-section">' in response.text:
                self.logger.info("Page Type 2 layout found")
                product_dtls_sel = Selector(text=response_selector.xpath("//div[@id='prodDetails']").get())
                technical_details = product_dtls_sel.xpath("//table[@id='productDetails_techSpec_section_1']")
                additional_information = product_dtls_sel.xpath("//div[@id='productDetails_db_sections']")
                product_details = product_dtls_sel.xpath(
                    "//table[@id='productDetails_techSpec_section_1']/text()").get()

                model_number = technical_details.re_first(
                    r'prodDetSectionEntry">\s*Model\s*Number\s*</th>\s*<td\s*class="a-size-base">\s*([^<]+)<')
                manufacturer = technical_details.re_first(
                    r'prodDetSectionEntry">\s*Manufacturer\s*</th>\s*<[^>]+>\s*([^<]+)<')
                country_of_origin = technical_details.re_first(
                    r'prodDetSectionEntry">\s*Country\s+of\s+Origin\s*</th>\s*<[^>]+>\s*([^<]+)<')
                extracted_web_pid = additional_information.re_first(
                    r'prodDetSectionEntry">\s*ASIN\s*</th>\s*<td[^>]+>\s*([^<]+)<')
                if not best_sellers_rank:
                    best_sellers_rank = additional_information.re(
                        r'prodDetSectionEntry">\s*Best\s*Sellers\s*Rank\s*<\/th>\s*<td>\s*<span>\s*<span>\s*(.+?)\s*<\/span>\s*<br>\s*<span>(.+?)<\/span>')
                    best_sellers_rank = remove_tags("/".join(best_sellers_rank))
            else:
                manufacturer = ""
                model_number = ""
                country_of_origin = ""
                extracted_web_pid = ""
                # best_sellers_rank = "0"
                product_details = ""

            try:
                product_desc_sel = Selector(text=response_selector.xpath("//div[@id='descriptionAndDetails']").get())
                product_description = product_desc_sel.xpath("//div[@id='productDescription']").get()
            except ValueError as ve:
                try:
                    product_desc_sel = Selector(
                        text=response_selector.xpath("//div[@id='productDescription_feature_div']").get())
                    product_description = product_desc_sel.xpath("//div[@id='productDescription']").get()
                except:
                    product_description = ""

            if best_sellers_rank is not None:
                best_sellers_rank = re.sub("\([^\)]+\)", "", best_sellers_rank)
                best_sellers_rank = best_sellers_rank.replace("#", "").replace(",", "").replace("/", ";").replace("in",
                                                                                                                  ";").replace(
                    " ", "")
            else:
                best_sellers_rank = "0"

            # Third Rank Implementation
            if not best_sellers_rank or best_sellers_rank == "0":
                # Grabs any number of rankings (variant 2nd) (grabs any number of rankings)
                try:
                    rankings = []
                    # First Ranking (returns list -> [rank, rank category])
                    rankings += response_selector.css('#SalesRank').re(
                        '.*Bestsellers\s*Rank:\s*.+#([^\s<]+)\s*in\s*([^\(]+)')
                    # Grab others
                    for li in response_selector.css('.zg_hrsr_item'):
                        rankings.append(li.css('span::text').get())
                        rankings.append(li.css('a::text').get())
                    if rankings:
                        best_sellers_rank = ';'.join(
                            [rank.strip().replace(',', '').replace(' ', '') for rank in rankings])
                except:
                    pass

                # # Checking if only 2 rankings (variant 1st) (old method)
                # # (Don't Delete) (<-blaze)
                # try:
                #     best_sellers_rank = response_selector.css('#SalesRank').re('.*Bestsellers\s*Rank:\s*.+#([^\s<]+)\s*in\s*([^\(]+).*#([^\s<]+).*in.*<a.*>([^<]+)</a>')
                #     best_sellers_rank = ';'.join([rank.strip().replace(',', '').replace(' ', '') for rank in best_sellers_rank])
                # except:
                #     pass

            self.logger.info(best_sellers_rank)
            impo = best_sellers_rank

            print("jaishreeram")
            try:
                delivery_time = response_selector.xpath(
                    "//div[@id='mir-layout-DELIVERY_BLOCK']//span[@data-csa-c-delivery-time]/@data-csa-c-delivery-time").get()
            except:
                delivery_time = 0

            try:
                best_sellers_rank = response_selector.xpath(
                    "//ul[@class='a-unordered-list a-nostyle a-vertical a-spacing-none detail-bullet-list']/li/span[@class='a-list-item']/span[@class='a-text-bold' and contains(text(), 'Best Sellers Rank')]/following-sibling::text()").get()
                print(best_sellers_rank, "radhe")
                categories = response_selector.xpath(
                    "//ul[@class='a-unordered-list a-nostyle a-vertical a-spacing-none detail-bullet-list']/li/span[@class='a-list-item']/ul[@class='a-unordered-list a-nostyle a-vertical zg_hrsr']/li/span[@class='a-list-item']/text()").getall()
                category_text = response_selector.xpath(
                    "//ul[@class='a-unordered-list a-nostyle a-vertical a-spacing-none detail-bullet-list']/li/span[@class='a-list-item']/ul[@class='a-unordered-list a-nostyle a-vertical zg_hrsr']/li/span[@class='a-list-item']/a/text()").get()

                # Append the category text to the list
                if category_text:
                    categories.append(category_text.strip())
                print(categories, "radhe")
                best_sellers_rank = best_sellers_rank + ', '.join(categories)
                print(best_sellers_rank, "radhe")


            except:
                pass

            print(delivery_time, "jaishreeram")
            delivery_date = '0'
            for _ in range(20):
                try:
                    # First attempt using center_col_sel
                    delivery_time = response.css(
                        'div#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE span[data-csa-c-delivery-time]::text').get()
                    delivery_date = delivery_time.strip()
                    print(delivery_date)
                except Exception as e:
                    delivery_date = '0'

                # If delivery_date is found, break out of the loop
                if delivery_date and delivery_date != '0':
                    break

                try:
                    # Second attempt using response_selector
                    delivery_date = response_selector.xpath("//*[@id='ddmDeliveryMessage']/b/text()").get()
                    delivery_date = delivery_date.strip()
                    print(delivery_date)
                except Exception as e:
                    delivery_date = '0'

                # If delivery_date is found, break out of the loop
                if delivery_date and delivery_date != '0':
                    break

                try:
                    # Third attempt using response CSS selector
                    delivery_date = response.css(
                        "#mir-layout-DELIVERY_BLOCK-slot-SECONDARY_DELIVERY_MESSAGE_LARGE > span::text").get()
                    delivery_date = delivery_date.strip()
                    print(delivery_date)
                except Exception as e:
                    delivery_date = '0'

                # If delivery_date is found, break out of the loop
                if delivery_date and delivery_date != '0':
                    break

                try:
                    delivery_info = response.css(
                        'span[data-csa-c-type="element"][data-csa-c-id="5wtpci-ilxcxj-sypair-6w1b3b"]')
                    fastest_delivery_date = delivery_info.css('span.a-text-bold::text').get()
                except Exception as e:
                    delivery_date = '0'

                try:
                    delivery_info = response.css(
                        'span[data-csa-c-type="element"][data-csa-c-id="5wtpci-ilxcxj-sypair-6w1b3b"]')
                    delivery_time = delivery_info.xpath('@data-csa-c-delivery-time').get()
                except Exception as e:
                    delivery_date = '0'

                try:
                    delivery_time = response.css(
                        '#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE span[data-csa-c-delivery-time]::text').get()
                except Exception as e:
                    delivery_date = '0'

            # Setting A deal In Nivea
            try:
                text_price_title = response_selector.xpath(
                    "//td[@class='a-color-secondary a-size-base a-text-right a-nowrap']/text()").getall()
                print(text_price_title)
                if len(text_price_title) < 2:
                    deal_flag = 0
                else:
                    if 'deal' in text_price_title[1].lower():
                        deal_flag = 1
                    else:
                        deal_flag = 0
            except Exception as e:
                deal_flag = 0
                self.logger.info("Error while fetching Deal Flag")

            def create_review_compressed_string(reviewers_name, reviews_star_rating, reviews_statement, reviews_date,
                                                reviews_helpful_number):
                if len(reviewers_name) == 0 or len(reviews_star_rating) == 0 or len(reviews_statement) == 0 or len(
                        reviews_date) == 0 or len(reviews_helpful_number) == 0:
                    return ""
                a = []
                for i in reviewers_name:
                    if len(a) and a[-1] == i:
                        continue
                    a.append(i)
                st = []
                for i in list(zip(a, reviews_star_rating, reviews_statement, reviews_date, reviews_helpful_number)):
                    st.append("::".join(i))
                return ';'.join(st)

            # Getting most recent interview
            try:
                top_reviews = Selector(text=response_selector.xpath(
                    "//*[@id='reviewsMedley']/div/div[2]/div/div[2]/span[2]/div/div").get())
                reviewers_name = top_reviews.xpath("//span[@class='a-profile-name']/text()").getall()
                # print(reviewers_name,len(reviewers_name))
                reviews_star_rating = top_reviews.xpath("//i[@data-hook='review-star-rating']/span/text()").getall()
                # print(reviews_star_rating,len(reviews_star_rating))
                reviews_statement = top_reviews.xpath("//a[@data-hook='review-title']/span/text()").getall()
                # print(reviews_statement,len(reviews_statement))
                reviews_date = top_reviews.xpath("//span[@data-hook='review-date']/text()").getall()
                # print(reviews_date,len(reviews_date))
                # reviews_description = top_reviews.xpath("//div[@data-hook='review-collapsed']/span/text()").getall()
                # print(reviews_description,len(reviews_description))
                reviews_helpful_number = top_reviews.xpath(
                    "//span[@data-hook='helpful-vote-statement']/text()").getall()
                # print(reviews_helpful_number,len(reviews_helpful_number))
                pdp_top_review_info = create_review_compressed_string(reviewers_name, reviews_star_rating,
                                                                      reviews_statement, reviews_date,
                                                                      reviews_helpful_number)
                print(pdp_top_review_info)
            except Exception as e:
                pdp_top_review_info = ""
                self.logger.info("Error in Getting recent review info ")

            try:
                best_sellers_rank = best_sellers_rank.replace("#", "").replace(",", "").replace("(", ";").replace(")",
                                                                                                                  "").replace(
                    " ", "").replace("in", ";")
            except:
                best_sellers_rank = ""

            fastest_delivery_date = '0'

            try:

                fastest_delivery_date = response_selector.xpath(
                    "//*[@id='mir-layout-DELIVERY_BLOCK-slot-SECONDARY_DELIVERY_MESSAGE_LARGE']/span/@data-csa-c-delivery-time").get()
                fastest_delivery_date = fastest_delivery_date.strip()
                print("Delivery date 2nd is tanuj ", fastest_delivery_date)
            except:
                fastest_delivery_date = None

            from datetime import datetime

            def days_difference(user_input):
                today = datetime.today().date()

                # Extract the date part using regex
                # Pattern to find date like "9 January" or "7 October"
                date_pattern = r'(\d{1,2})\s+([A-Za-z]+)'
                match = re.search(date_pattern, user_input)

                if not match:
                    raise ValueError(f"Could not extract date from: {user_input}")

                day = int(match.group(1))
                month_name = match.group(2)

                # Parse the month name
                try:
                    month_num = datetime.strptime(month_name, '%B').month
                except ValueError:
                    # Try abbreviated month name
                    try:
                        month_num = datetime.strptime(month_name, '%b').month
                    except ValueError:
                        raise ValueError(f"Invalid month name: {month_name}")

                # Create the date in current year
                user_date = datetime(today.year, month_num, day).date()

                # If the date is in the past (e.g., January and we're in December),
                # it should be next year's date
                if user_date < today:
                    user_date = datetime(today.year + 1, month_num, day).date()

                # Calculate the difference in days
                difference = (user_date - today).days

                return difference

            try:
                if fastest_delivery_date != None:

                    days_difff = days_difference(fastest_delivery_date)
                    # print(f"Days difference: {days_diff} days")
                else:
                    days_difff = 0
            except ValueError as e:
                days_difff = 0

            item = dict()
            item["marketplace"] = "Amazon"
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
            item["pdp_title_value"] = name if name else ""

            item["extracted_brand_name"] = brand if brand else ""

            item["pdp_rating_value"] = rating_value or 0
            item["pdp_rating_count"] = rating_count or 0

            # Amazon PDP: reviews == ratings
            item["pdp_review_count"] = rating_count or 0

            item["pdp_qa_count"] = answered_questions if answered_questions else 0

            item["price_rp"] = mrp if mrp else 0.0
            item["price_sp"] = price if price else 0.0
            item["savings"] = savings if savings else 0.0
            item["pdp_discount_value"] = discount if discount else 0.0
            item["currency"] = currency if currency else 0.0

            item["manufacturer"] = manufacturer if manufacturer else ""
            item["model_number"] = model_number if model_number else ""
            item["country_of_origin"] = country_of_origin if country_of_origin else ""
            item["shipping_type"] = amazon_shipping_type if amazon_shipping_type else ""

            item["about_this_item"] = add_bullet

            item["product_details"] = product_details and remove_tags(product_details.replace("\n", "")) or ""
            item["pdp_desc_value"] = product_description and remove_tags(product_description.replace("\n", "")) or ""

            if ec_vedio != 0:
                item["pdp_image_count"] = len(images_list) - 1 - 1
            else:
                item["pdp_image_count"] = len(images_list) - 1

            item["pdp_image_url"] = image_url
            item["pdp_image_url_all"] = ", ".join((images_list))
            item["aplus_images_list"] = ", ".join(ec_images_list)
            item["mhri_images"] = ", ".join(thumbnail_images)
            item["carousel_images"] = ", ".join(Carousel_images)
            item["ec_number_of_images"] = vec_number_of_image
            item["ec_number_of_videos"] = ec_vedio

            item["pdp_number_of_bulletin"] = len(about_this_items + add_bullets)
            item["pdp_bulletin_value"] = add_bullet
            try:
                item["reseller_name_crawl"] = seller
            except:
                item["reseller_name_crawl"] = ""

            if best_sellers_rank == "":
                item["seller_rank"] = impo
            else:
                item["seller_rank"] = best_sellers_rank

            item["best_sellers_rank"] = best_sellers_rank if best_sellers_rank else ""

            # ---------------- STAR COUNTS (FINAL) ----------------
            item["five_star"] = five_star if five_star else 0
            item["four_star"] = four_star if four_star else 0
            item["three_star"] = three_star if three_star else 0
            item["two_star"] = two_star if two_star else 0
            item["one_star"] = one_star if one_star else 0

            if not mrp:
                in_stock = ""

            if "in stock" in in_stock:
                item["osa"] = 1
                item["osa_remark"] = "INSTOCK"
            else:
                item["osa"] = 0
                item["osa_remark"] = "OOS"
                delivery_date = 0

            item['pdp_top_review'] = pdp_top_review_info
            item['deal_flag'] = deal_flag
            item["pdp_page_url"] = f"https://www.amazon.fr/dp/{self.web_pid}"

            from datetime import datetime

            def days_difference(user_input):
                today = datetime.today().date()

                # Extract the date part using regex
                # Pattern to find date like "9 January" or "7 October"
                date_pattern = r'(\d{1,2})\s+([A-Za-z]+)'
                match = re.search(date_pattern, user_input)

                if not match:
                    raise ValueError(f"Could not extract date from: {user_input}")

                day = int(match.group(1))
                month_name = match.group(2)

                # Parse the month name
                try:
                    month_num = datetime.strptime(month_name, '%B').month
                except ValueError:
                    # Try abbreviated month name
                    try:
                        month_num = datetime.strptime(month_name, '%b').month
                    except ValueError:
                        raise ValueError(f"Invalid month name: {month_name}")

                # Create the date in current year
                user_date = datetime(today.year, month_num, day).date()

                # If the date is in the past (e.g., January and we're in December),
                # it should be next year's date
                if user_date < today:
                    user_date = datetime(today.year + 1, month_num, day).date()

                # Calculate the difference in days
                difference = (user_date - today).days

                return difference

            try:
                if delivery_time != None:

                    days_diff = days_difference(delivery_time)
                    print(f"Days difference: {days_diff} days")
                else:
                    days_diff = 0
            except ValueError as e:
                days_diff = 0

            item["delivery_date"] = days_diff
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 1
            item = utils.clean_item_data(item)
            items.append(item)

        else:
            item = dict()
            item["marketplace"] = "Amazon"
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
            item["pdp_title_value"] = self.sku_name
            item["extracted_brand_name"] = self.brand_name
            item["pdp_rating_value"] =  0
            item["pdp_rating_count"] = 0
            # Amazon PDP: reviews == ratings
            item["pdp_review_count"] = 0
            item["pdp_qa_count"] =  0
            item["price_rp"] = 0.0
            item["price_sp"] = 0.0
            item["savings"] = 0.0
            item["pdp_discount_value"] = 0.0
            item["currency"] = 0.0
            item["manufacturer"] = ""
            item["model_number"] = ""
            item["country_of_origin"] = ""
            item["shipping_type"] = ""
            item["about_this_item"] = ""
            item["product_details"] = ""
            item["pdp_desc_value"] = ""
            item["pdp_image_count"] = ""
            item["pdp_image_url"] = ""
            item["pdp_image_url_all"] = ""
            item["aplus_images_list"] = ""
            item["mhri_images"] = ""
            item["carousel_images"] = ""
            item["ec_number_of_images"] = ""
            item["ec_number_of_videos"] = ""
            item["pdp_number_of_bulletin"] = ""
            item["pdp_bulletin_value"] = ""
            item["reseller_name_crawl"] = ""
            item["seller_rank"] = ""
            item["best_sellers_rank"] = ""
            item["five_star"] = 0
            item["four_star"] = 0
            item["three_star"] = 0
            item["two_star"] = 0
            item["one_star"] = 0
            item["osa"] = 0
            item["osa_remark"] = "OOS"
            delivery_date = 0
            item['pdp_top_review'] = ""
            item['deal_flag'] = ""
            item["pdp_page_url"] = f"https://www.amazon.fr/dp/{self.web_pid}"
            item["delivery_date"] = 0
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 1
            item = utils.clean_item_data(item)
            items.append(item)
            self.logger.error("Something went wrong....")

        # Create Raw file without header
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
            records.append(record)
        # records = [tuple(item.values()) for item in items]

        # self.logger.info("Database connection create")
        self.logger.info("Data inserting")

        tbl_columns_str = "`" + "`,`".join(self.output_cols) + "`"
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)

        mySql_insert_query = """INSERT INTO `amazon_fr_crawl_pdp` (""" + tbl_columns_str + """) VALUES (""" + tbl_columns_val + """)"""
        try:
            self.cursor.executemany(str(mySql_insert_query), records)
            products_count = self.cursor.rowcount
            self.connection.commit()
            self.connection.close()
        except self.cursor.Error as err:
            print(str(err))
            self.logger.error("Mysql Error occured: {}".format(str(err)))
        except Exception as e:
            print('ERR_AMZ_PDP', e, len(self.output_cols), len(records[0]), self.web_pid)
            # print(len(self.output_cols), mySql_insert_query, records[0])
            pass

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
