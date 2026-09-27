from doctest import OutputChecker
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
import uuid
from requests.utils import requote_uri
from scrapy.selector import Selector
from scrapy.loader import ItemLoader
from datetime import datetime
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError, TCPTimedOutError
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
import mysql.connector
import cloudscraper
import undetected_chromedriver as uc
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
scraper = cloudscraper.create_scraper()
import certifi
from .addons import Get, Post, Session
from curl_cffi import requests

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

SETTINGS = scrapy.utils.project.get_project_settings()

#import winreg

ACCESS_TOKEN_FILE = "accessToken.txt"
REFRESH_TOKEN_FILE = "refreshToken.txt"

# Module-level token, loaded once at import. This is now treated as a
# mutable cache: token_bypass() below updates this variable directly
# (via `global accessToken`) whenever it successfully refreshes, so
# every subsequent request in this process picks up the new token
# instead of continuing to use the stale one that was loaded at import.
with open(ACCESS_TOKEN_FILE, 'r', encoding='utf-8') as _f:
    accessToken = _f.read().strip()


def data_check(response):
    output = json.loads(response.text)
    check_data_status = False
    data_list = output.get("layout", [])
    if not data_list:
        return []

    for block in data_list:
        widget_id = block.get("widgetId", "")

        if widget_id != "PRODUCT_GRID":
            check_data_status =True

    return check_data_status

def token_bypass():
    """
    FIXED:
      1. accessToken/refreshToken were being swapped when written to disk.
      2. No validation that the refresh actually returned tokens -- a failed
         refresh (e.g. because the refresh token itself was already dead)
         used to crash downstream with "write() argument must be str, not None"
         instead of being reported clearly.
      3. Now returns the new access token (or None on failure) so callers
         can update their in-memory copy immediately, instead of relying on
         a module-level variable that was only ever read once at import.
    """
    session_id = str(uuid.uuid4())

    try:
        with open(ACCESS_TOKEN_FILE, 'r', encoding='utf-8') as f:
            AUTH_TOKEN = f.read().strip()
        with open(REFRESH_TOKEN_FILE, 'r', encoding='utf-8') as f:
            REFRESH_TOKEN = f.read().strip()
    except FileNotFoundError as e:
        print(f"token_bypass: token file missing ({e}). Cannot refresh -- manual login required.")
        return None

    if not AUTH_TOKEN or not REFRESH_TOKEN:
        print("token_bypass: accessToken.txt or refreshToken.txt is empty. Cannot refresh -- manual login required.")
        return None

    headers = {
        "accept": "application/json",
        "content-type": "application/json; charset=utf-8",
        "platform": "android",
        "session_id": session_id,
        "sessionid": session_id,
        "tenant": "ZEPTO",
        "User-Agent": "okhttp/4.12.0",
        "x-requested-with": "XMLHttpRequest",
        "app_version": "26.6.4",
        "appversion": "26.6.4",
        "device_brand": "samsung",
        "device_model": "SM-N976N",
        "device_uid": "cd0fa6d23c0cff9d",
        "deviceuid": "cd0fa6d23c0cff9d",
        "source": "PLAY_STORE",
        "system_version": "7.1.2",
        "systemversion": "7.1.2",
        "auth_revamp_flow": "v2",
        "Connection": "Keep-Alive",
        "accept-encoding": "gzip",
        "access-control-allow-credentials": "true",
        "accessibility_layout": "false",
        "performance_mode": "NORMAL",
        "user_gppo": "0",
        "user_order_number": "0",
        "user_variant_hash": "3",
        "user_wallet_balance_bucket_78": "0",
        "gps_latitude": "",
        "gps_longitude": "",
        "store_id": "",
        "baggage": "sentry-environment=production,sentry-public_key=83e04266eecec2baa6a3445018bec453,sentry-trace_id=5a1fa1776a5f42e0aba2c1a987780c71",
        "sentry-trace": "5a1fa1776a5f42e0aba2c1a987780c71-b39609a7267b6162",
    }

    payload = {
        "refreshToken": REFRESH_TOKEN,
        "authToken": "Bearer " + AUTH_TOKEN
    }

    try:
        response = requests.post(
            "https://bouncer.zepto.co.in/auth/refresh/auth-token/",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except Exception as e:
        print(f"token_bypass: refresh request failed with exception: {e}")
        return None

    print(f"token_bypass: refresh endpoint status={response.status_code}")

    if response.status_code != 200:
        print(f"token_bypass: refresh failed, body={response.text[:500]}")
        return None

    try:
        main_json = response.json()
    except Exception as e:
        print(f"token_bypass: could not parse refresh response as JSON: {e}")
        return None

    new_refresh_token = main_json.get("data", {}).get("refreshToken")
    new_access_token = main_json.get("data", {}).get("accessToken")

    if not new_access_token or not new_refresh_token:
        print(f"token_bypass: refresh response missing tokens: {main_json}")
        return None

    # FIXED: correct file <-> token pairing (previously swapped)
    with open(ACCESS_TOKEN_FILE, 'w', encoding='utf-8') as f:
        f.write(new_access_token)
    with open(REFRESH_TOKEN_FILE, 'w', encoding='utf-8') as f:
        f.write(new_refresh_token)

    print("token_bypass: refreshed and saved new tokens successfully")
    return new_access_token


class ZEPTOKWSpider(InitSpider):
    name = "zepto_kw_EY_login"

    allowed_domains = ["shop.zeptonow.com"]
    start_urls = ["https://shop.zeptonow.com/Home"]
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
    HOME_URL = "https://shop.zeptonow.com/Home/"

    PINCODE_STORE_FALLBACK = {
        "110084": [
            "23e18cbf-7e46-49ec-a559-d5a6cdb09d3b",
            "94ec12c0-9fd4-45fe-aea4-1e41e70413fb",
            "f02ef084-eab2-4651-8168-a4814b97ca06",
            "c978abd4-1b79-40d2-ab47-ec19b7c29d41"
        ],
        "380058": [
            "35225fcb-30cc-4ab8-939b-a0a5e0887285",
            "1105d3fb-0556-4f7e-bd83-416274e9924a",
            "e4bfd8b0-11a9-475c-b34e-a4c43cbafe65",
        ],
        "400004": [
            "3b579acc-ff7e-4e12-8b96-8e144cff0aa7",
        ],
        "411015": [
            "ab0913f7-59e4-4cd7-b2b1-56d50fc56096",
            "7644b7fa-98d0-4bdd-a093-965dac5a807b",
        ],
        "500005": [
            "5eb1e899-1cb8-4374-a4de-69cf86cc36cc",
        ],
        "560067": [
            "e58fff62-7695-44c2-aba0-6bc96074bc64",
            "3169658f-77f5-47a3-a87d-e9016e7f3ebe",
            "cf1fab3e-edc1-4a8a-8054-5abe91c20f69",
        ],
        "600043": [
            "3587d930-d517-4847-8e2c-c48ecabeba45",
            "2e2bb69c-1bee-4ae1-b0ad-5d74128d8ebf",
            "083a3e0d-4b0c-4353-927f-02c4614e6f47",
        ],
        "700136": [
            "285e3359-d42c-4b88-9edb-35550d7f3b41",
            "d4965e43-bb99-400e-9107-7371e08cf06a",
            "ab3bee45-6ef0-4dbe-bf5f-253d0817ceb5",
        ],
        "110003": [
            "73b0c599-728d-4642-a0e3-1e5b68836327",
            "73b0c599-728d-4642-a0e3-1e5b68836327",
            "73b0c599-728d-4642-a0e3-1e5b68836327"
        ],
        "121001": [
            "3d277bf6-7a5f-498a-a956-56fd8ab9ef82",
            "b463b5a9-6661-4ee9-b58b-03b285ac536e",
            "fb48fc60-af3a-421b-9cce-928e2c0cb95f",
            "fb48fc60-af3a-421b-9cce-928e2c0cb95f",
            "2398d252-ec15-485b-bd2f-2b03432ea794"
        ],
        "122001": [
            "c2e46a52-b65f-4fbe-8332-06856db49e25",
            "f234bb80-5551-416a-ac32-e3734ecd6258",
            "d56e42a4-7150-4aa4-b7fc-84f9caa43963",
            "d56e42a4-7150-4aa4-b7fc-84f9caa43963",
            "f5e682bc-1124-4bcf-8fca-734bd8b59d7f"
        ],
        "160101": [
            "9e82a26c-9e78-4ea5-93a7-b0b077538621",
            "317f08d2-bf42-40ce-b4b9-2a1dd60dcbfe"
        ],
        "226001": [
            "2140ad97-8423-4f24-9961-ed3ad44306c0",
            "6af4daba-3f48-4037-a5e4-0bb3c4042203",
            "c3937bd5-02ec-43db-b411-93951a26a159"
        ],
        "380015": [
            "71e632bb-df6a-45e2-9fa2-08fa0f5cdbe9",
            "71e632bb-df6a-45e2-9fa2-08fa0f5cdbe9",
            "9c6fce71-3aec-455c-969f-075ba74fa0d5",
            "594e08e1-87d1-4502-9e92-182e895a6c0c",
            "9c6fce71-3aec-455c-969f-075ba74fa0d5"
        ],
        "400002": [
            "fac79573-63ae-4dd4-a7b5-bd8d8fa61ce2",
            "551d5b20-6c19-465c-aaf8-0624166cbf93",
            "3b579acc-ff7e-4e12-8b96-8e144cff0aa7"
        ],
        "411006": [
            "befaa444-90e6-4691-a2d0-614d59ac0f1d",
            "ab0913f7-59e4-4cd7-b2b1-56d50fc56096",
            "596b77f1-86e7-4246-ad37-f87897a9779a",
            "befaa444-90e6-4691-a2d0-614d59ac0f1d",
            "4cc5f8ae-6495-44d0-9212-b63fe11a3af5"
        ],
        "500004": [
            "77acda94-75cc-4146-952c-813f5bd745dd",
            "b1bd6011-b070-4300-81cd-07f886eca089"
        ],
        "560004": [
            "cf384ecd-5e1f-47e9-9194-8e9dc940e8c3",
            "4f54ea62-0269-4b93-87cd-ef7ed796c6b1"
        ],
        "600007": [
            "993f0320-ff43-4904-aca7-570e60b128bd",
            "443fffe1-024b-4c04-9b3a-eaf3af01c83d"
        ],
        "700029": [
            "4d3f28cf-646c-49cb-833b-0dbce82498d5",
            "4d3f28cf-646c-49cb-833b-0dbce82498d5",
            "e6020704-f789-4a3f-9f3a-1f289bcb343f",
            "4d3f28cf-646c-49cb-833b-0dbce82498d5"
        ],
        "380005":[
            "4ef0ca3e-626a-4770-8efe-9eda4c147b0b",
            "5c720bb8-ef8e-45c7-a249-be01de180a15",
            "c6b9ceb3-8f60-49b2-9c08-5a44ad7186ca"

        ],
        "500006":[
            "7ed513e4-0a4c-453d-9446-7ab609bafdbf",
            "9b6c805a-0324-4d78-96c0-0e9c3dec81ff"

        ],
        "560002":[
            "4f54ea62-0269-4b93-87cd-ef7ed796c6b1",
            "34774f44-f41c-4bde-993b-8e93684ff94f"
        ],
        "600002":[
            "993f0320-ff43-4904-aca7-570e60b128bd",
            "22cd61da-18f7-490b-9394-24abc3780214"
        ],
        "700009":[
            "eedbad6f-ada7-40cd-922e-828198efed50"
        ],
        "110002" : [
            "3d03e7a7-4ded-458a-9349-2978cd333ef0"
        ],
        "411001" : [
            "596b77f1-86e7-4246-ad37-f87897a9779a",
            "931f1ec1-e287-4412-9b52-df3f8ab9c95c"
        ],
        "560001" : [
            "b1403534-cd6b-49d0-a7cd-ce20e6497768"
        ],
        "700002" : [
            "f953916f-d684-447e-b750-c1f4ca34bc33"

        ],
        "600100" : [
            "3054cc18-1476-426c-a67b-51028bd50319",
            "6e16ae4d-592d-4017-a51c-37c7d85989e0"
        ],
          "380001" : [
              "594e08e1-87d1-4502-9e92-182e895a6c0c",
              "678815bc-3943-4281-b104-3ca57a007ee0",
              "f0700405-c162-4855-8b39-3a75fe3a9d35",
          ],
          "400001" : [
              "fac79573-63ae-4dd4-a7b5-bd8d8fa61ce2",
              "551d5b20-6c19-465c-aaf8-0624166cbf93",
          ],
          "500002" : [
              "6671859b-cb7c-4dc7-bba6-d6554b27b7b2",
              "7ed513e4-0a4c-453d-9446-7ab609bafdbf",
              "f0700405-c162-4855-8b39-3a75fe3a9d35",
          ],
          "700001" : [
              "6b5fe466-21a5-42ee-b250-c3520dc0fb6b",
              "f5a49f9a-8888-481e-b96c-f7a191ea1256",
              "f0700405-c162-4855-8b39-3a75fe3a9d35",
          ],
          "500001" : [
              "8275a3ee-3b08-4201-9be3-6e12aed69ea9",
              "7ed513e4-0a4c-453d-9446-7ab609bafdbf",
              "b9881384-2b90-44c7-8af2-e22c10f20ca2",
              "5870b5a1-60c2-45f7-bc13-60b9b8dda974",
          ],
          "400014" : [
              "71ca681c-6ee4-467d-9d0a-8d761ce8400f"
          ],
          "110095" : [
              "34420157-825b-4822-acc8-9f20ae822fe3",
              "afa2d113-3c8f-4b16-bee3-d391523a895a",
          ],
          "380009" : [
              "754e6a75-5f25-4e49-ad20-d4034241e11c",
              "9c6fce71-3aec-455c-969f-075ba74fa0d5"
          ],
          "400068" : [
              "9afa54f1-78a4-4ce7-a632-be8e99531cb0",
              "2050a7de-e13c-4947-bac7-7995d8c6e72d",
              "5f267ad5-446b-4a8b-86f0-df174ad545dd"
          ],
          "411057" : [
              "74dfeece-0ec5-4b41-a83b-576add66078e",
              "edbcfecc-a753-4fc8-ab8a-eb7b7d3dfbd7",
              "34597f4e-8acd-434a-a983-4c7d80c7afd7"          ],
          "700039" : [
              "547ab61d-8d0e-47b5-a5b4-82952f43e814",
          ],
          "500008" : [
              "bb713aac-cd12-4b4d-9026-704e3deaaac3",
              "b2b8106d-74fa-4f6c-8edb-e491da91ddf1",
              "0148e85f-0f97-4829-bc35-cee59262a82c",
              "6500290b-eea8-460e-a447-14e27bbfe116",
              "e4a9d9d2-dcea-46bb-b683-83dda1e9e6d6",
              "5b1796e1-36c2-4ae9-83a0-c03c25cac05a",
          ],
          "560008" : [
              "8275a3ee-3b08-4201-9be3-6e12aed69ea9",
              "7ed513e4-0a4c-453d-9446-7ab609bafdbf",
              "b9881384-2b90-44c7-8af2-e22c10f20ca2",
              "5870b5a1-60c2-45f7-bc13-60b9b8dda974",
          ],
          "600020" : [
              "ee6f8d8a-94dc-47c7-a4c5-7ea1efe3031b"
          ]
    }

    def __init__(self, inputs, **kw):
        super(ZEPTOKWSpider, self).__init__(**kw)
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
        self.rank = 1

        self.tz = inputs.get("tz")
        self.current_time = inputs.get("current_time")
        self.dt = inputs.get("dt")

        self.db_table_name = "zepto_crawl_kw"

        self.output_cols = [
            "pf_id", "crawl_id", "keyword", "keyword_id", "brand_id", "brand_name", "brand_crawl", "web_pid",
            "pdp_title_value",
            "position", "price_sp", "pdp_rating_value", "pdp_rating_count", "pdp_image_url", "pdp_page_url",
            "pdp_discount_value",
            "pdp_sponsored", "location_id", "location_name", "pincode", "status", "page", "sponsored_brand",
            "grammage", "price_rp"
        ]

        self.visit_count = str(random.choice([10, 11, 12, 13, 14, 15, 16]))

        self.session = Session()
        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as error:
            self.logger.error("Connection error with the database Error:{}:{}".format(error.errno, error.strerror))
            print("Connection error with the database Error{}:{}".format(error.errno, error.strerror))

    def _build_headers(self, store_id, trace_id, request_id, session_id, store_etas, keyword, secondary_store_id=None):
        device_uid = "cd0fa6d23c0cff9d"

        if secondary_store_id and secondary_store_id != store_id:
            primary_eta = list(store_etas.values())[0] if store_etas else 21
            secondary_eta = list(store_etas.values())[1] if len(store_etas) > 1 else 25

            store_serviceability = {
                "data": {
                    store_id: {"cost": 1228, "eta": primary_eta, "type": "PRIMARY_STORE"},
                    secondary_store_id: {"cost": 11509, "eta": secondary_eta, "type": "SECONDARY_STORE"}
                },
                "version": "v1"
            }
            store_ids = f"{store_id},{secondary_store_id}"
        else:
            eta = list(store_etas.values())[0] if store_etas else 6
            store_serviceability = {
                "data": {
                    store_id: {"cost": 343, "eta": eta, "type": "PRIMARY_STORE"}
                },
                "version": "v1"
            }
            store_ids = store_id

        headers = {
            "accept": "application/json",
            "accept-encoding": "gzip",
            "access-control-allow-credentials": "true",
            "accessibility_layout": "false",
            "advertiser_id": str(uuid.uuid4()),
            "app_version": "26.5.5",
            "appversion": "26.5.5",
            "auth_revamp_flow": "v2",
            # FIXED: read the *current* module-level accessToken at call time
            # (updated in-place by token_bypass on 401) instead of whatever
            # value was loaded once at import.
            # "authorization": accessToken,
            "baggage": f"sentry-environment=production,sentry-public_key=83e04266eecec2baa6a3445018bec453,sentry-trace_id={trace_id}",
            "bundle_version": "",
            "bundleversion": "",
            "Connection": "Keep-Alive",
            "Content-Type": "application/json; charset=utf-8",
            "device_brand": "samsung",
            "device_model": "SM-N976N",
            "device_uid": device_uid,
            "deviceuid": device_uid,
            "experience_variant": "SS_UNIFIED",
            "gps_latitude": "",
            "gps_longitude": "",
            "Host": "api-gateway.zepto.co.in",
            "is_internal_user": "false",
            "is_new_font": "true",
            "isinternaluser": "false",
            "last_selected_store_id": store_id,
            "lastselectedstoreid": store_id,
            "marketplace_type": "SUPER_SAVER",
            "performance_mode": "NORMAL",
            "platform": "android",
            "request_id": request_id,
            "requestid": request_id,
            "sentry-trace": f"{trace_id}-85303d37c6b3a899",
            "session_id": session_id,
            "sessionid": session_id,
            "source": "PLAY_STORE",
            "store_etas": json.dumps(store_etas),
            "store_id": store_id,
            "store_ids": store_ids,
            "store_serviceability": json.dumps(store_serviceability),
            "storeid": store_id,
            "system_version": "7.1.2",
            "systemversion": "7.1.2",
            "tenant": "ZEPTO",
            "tobacco_consent_given": "false",
            "tobaccoconsentgiven": "false",
            "trace_metric": f"search_page_load_{keyword.replace(' ', '_')}_SHOW_ALL_RESULTS_request",
            "User-Agent": "okhttp/4.12.0",
            "user_gppo": "0",
            "user_order_number": "0",
            "user_variant_hash": "40",
            "user_wallet_balance_bucket_78": "0",
            "x-requested-with": "XMLHttpRequest",
        }

        return headers

    def _fetch_search(self, store_id):
        """
        FIXED:
          - headers are now rebuilt on every attempt (previously built once,
            so a mid-loop token refresh was never actually used)
          - on a 401, we call token_bypass(), update the module-level
            accessToken IN-PLACE via `global`, and retry with the new token
          - if token_bypass() itself fails (refresh token dead), we stop
            retrying immediately instead of burning attempts against a
            token we already know is bad
        """
        global accessToken

        trace_id = str(uuid.uuid4()).replace('-', '')
        request_id = str(uuid.uuid4()).replace('-', '')
        session_id = str(uuid.uuid4()).replace('-', '')
        intent_id = f"{uuid.uuid4()}_"

        secondary_store_id_dict = {
            "380005": "e677968e-5901-4ff2-8613-ebd72359a67c",
            "110001": "",
            "500006": "e052e083-dbfe-4156-a86e-e2fd848f8c3e",
            "500004": "33a1d02e-1bb7-44cc-8d38-9697bcc23dba",
            "560002":"abd85a95-f3f3-42fd-aeb0-71b9127335f5",
            "400002": "2175898f-b70e-46d9-8def-aba7f0745662",
            "411001": "931f1ec1-e287-4412-9b52-df3f8ab9c95c",
            "560001": "843e630a-7896-462d-b7cf-712140483ed3",
            "110003": "94f50df3-fb2e-4c36-ad6f-8a00bfd1c6af",
            "600007": "59099ea0-3411-4169-9c90-206cb03ef12a",
            "121001": "a95989f3-34a1-4288-b318-a01c946b6919",
            "600002":"59099ea0-3411-4169-9c90-206cb03ef12a",
            "700009": "e879c6cf-e4bd-4b11-a605-4e9b2ee2365d",
            "122001": "b6ac55e9-9d60-4ea1-86b8-fe554ea1490c",
            "411015": "931f1ec1-e287-4412-9b52-df3f8ab9c95c",
            "400004": "2175898f-b70e-46d9-8def-aba7f0745662",
            "500005": "",
            "560067": "0059ff6a-7eb0-477a-a7f5-69256f2c444b",
            "600043": "37906ef4-331c-471c-b332-0bf7a979fc07",
            "226001": "c08f4318-403b-4381-8a30-f9da9735ee2b",
            "411006": "931f1ec1-e287-4412-9b52-df3f8ab9c95c",
            "560004": "2614cabb-fff2-4ef6-aa5b-e94c2b875880",
            "700029": "5d94bdb2-32fe-42f1-bc68-732d1d7ccb11",
            "700136": "",
            "600001": "",
            "700002": "",
            "400001": "dd0aebf0-fb91-4644-bf64-5ac156a4b57f",
            "700001": "5d94bdb2-32fe-42f1-bc68-732d1d7ccb11",
            "500001": "33a1d02e-1bb7-44cc-8d38-9697bcc23dba",
            "400014": "dd0aebf0-fb91-4644-bf64-5ac156a4b57f",
            "110095": "57a0c2ae-1cf1-4c4a-99eb-eb2e19864075",
            "380009": "e0a0c84c-0819-482e-8b95-55d4b32592d8",
            "411057": "c1a7b76d-8cfc-4195-83f0-74095169a89f",
            "500008": "f931724a-0140-4c06-b832-027e03fc320a",
            "600020": "778b5c2b-0468-4f1e-8fa0-241cc91608a2",
            "700039": "de95e00b-0ebf-4f65-8f27-df66fd91dc13",

        }
        secondary_store_id = secondary_store_id_dict.get(str(self.pincode.strip()), store_id)

        if not secondary_store_id or secondary_store_id == store_id:
            secondary_store_id = None
            store_etas = {store_id: 6}
        else:
            store_etas = {store_id: 21, secondary_store_id: 25}

        json_data = {
            "query": self.keyword,
            "userSessionId": "",
            "mode": "SHOW_ALL_RESULTS",
            "intentId": intent_id,
            "user_action_meta": [],
            "requestMeta": {},
            "pageNumber": 0,
            "retryCount": 0,
        }

        session = requests.Session(impersonate='chrome')
        base_url = "https://user-search.zepto.co.in/api/v3/search"


        for attempt in range(3):
            # Rebuild headers each attempt so a refreshed token is picked up
            headers = self._build_headers(
                store_id, trace_id, request_id, session_id, store_etas,
                keyword=self.keyword, secondary_store_id=secondary_store_id
            )
            try:
                # output = session.request(
                #     "POST", base_url,
                #     json=json_data,
                #     headers=headers,
                #     verify=False,
                #     timeout=30
                # )

                # data_check_login = data_check(output)
                # if data_check_login:
                base_url = "https://api-gateway.zepto.co.in/user-search-service/api/v3/search"
                headers["authorization"] = accessToken
                output = session.request(
                    "POST", base_url,
                    json=json_data,
                    headers=headers,
                    verify=False,
                    timeout=30
                )

                print(f"store_id={store_id} | attempt={attempt+1} | status_code={output.status_code}")

                if output.status_code == 200:
                    print(output.text)
                    return output.text

                if output.status_code != 200:
                    print(f"401 received for store_id={store_id}, attempting token refresh...")
                    new_token = token_bypass()
                    if new_token:
                        accessToken = new_token  # update in-memory copy for this and future requests
                        print("Token refreshed successfully, retrying request...")
                        continue
                    else:
                        print("Token refresh failed (refresh token likely expired too). "
                              "Manual re-login required. Aborting retries for this store.")
                        break

                # Any other non-200 status: just log and retry
                print(f"Unexpected status {output.status_code}: {output.text[:300]}")

            except Exception as e:
                print(f"Request exception on attempt {attempt+1} for store_id={store_id}: {e}")

        return None

    def init_request(self):
        pincode_key = str(self.pincode.strip())

        raw_fallback = self.PINCODE_STORE_FALLBACK.get(pincode_key, [])
        seen = set()
        fallback_store_ids = []
        for sid in raw_fallback:
            if sid not in seen:
                seen.add(sid)
                fallback_store_ids.append(sid)

        if not fallback_store_ids:
            print(f"WARNING: No store IDs configured for pincode {pincode_key}. Aborting.")
            return None

        records = []

        for idx, store_id in enumerate(fallback_store_ids):
            print(
                f"[STORE ATTEMPT {idx+1}/{len(fallback_store_ids)}] "
                f"pincode={pincode_key} | store_id={store_id} | keyword={self.keyword}"
            )
            response_text = self._fetch_search(store_id)

            if response_text is None:
                print(f"  -> All HTTP attempts failed for store_id={store_id}. Trying next store.")
                continue

            records = self.parse_list_page(response_text)

            if records:
                print(f"  -> SUCCESS: Got {len(records)} records with store_id={store_id}")
                break
            else:
                print(
                    f"  -> BLOCK ERROR / no PRODUCT_GRID for store_id={store_id}. "
                    f"Trying next store."
                )

        if not records:
            print(
                f"All store IDs exhausted for pincode={pincode_key}, "
                f"keyword={self.keyword}. No records found."
            )
            return None

        tbl_columns_str = "`" + "`,`".join(self.output_cols) + "`"
        values_list = ["%s"] * len(self.output_cols)
        tbl_columns_val = ",".join(values_list)
        mySql_insert_query = (
            "INSERT INTO `zepto_crawl_kw` ("
            + tbl_columns_str
            + ") VALUES ("
            + tbl_columns_val
            + ")"
        )

        data = []
        for ech_rec in records:
            row = []
            for col in self.output_cols:
                row.append(str(ech_rec[col]) if col in ech_rec else "")
            data.append(tuple(row))

        try:
            self.cursor.executemany(str(mySql_insert_query), data)
            self.connection.commit()
        except self.cursor.Error as err:
            self.logger.error("Mysql Error occurred: {}".format(str(err)))

    def parse_list_page(self, response):
        try:
            output = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return []

        records = []
        pos = 0
        found_product_grid = False

        data_list = output.get("layout", [])
        if not data_list:
            return []

        for block in data_list:
            widget_id = block.get("widgetId", "")

            if widget_id != "PRODUCT_GRID":
                continue

            found_product_grid = True
            items = (
                block.get("data", {})
                     .get("resolver", {})
                     .get("data", {})
                     .get("items", [])
            )

            if items and isinstance(items, list):
                for each in items:
                    try:
                        records.append(self.product_formatting(each, pos + 1))
                        pos += 1
                    except Exception as e:
                        print(f"Error formatting product at pos {pos+1}: {e}")
            else:
                print(f"BLOCK ERROR: PRODUCT_GRID found but items is empty or invalid.")

        if not found_product_grid:
            print("BLOCK ERROR: No PRODUCT_GRID widget found in layout.")

        return records

    def product_formatting(self, product, pos):
        item = dict()

        item["pf_id"] = self.pf_id
        item["crawl_id"] = self.crawl_id
        item["keyword"] = self.keyword
        item["keyword_id"] = self.keyword_id
        item["brand_id"] = self.brand_id
        item["brand_name"] = self.brand_name

        item["brand_crawl"] = product['productResponse']['product']['brand']
        item["web_pid"] = product['productResponse']['productVariant']['id']
        item["pdp_title_value"] = product['productResponse']['product']['name']
        item["position"] = pos

        item['price_rp'] = (
            int(product['productResponse']['mrp'] / 100)
            if product['productResponse']['mrp']
            else None
        )
        item["price_sp"] = int(product['productResponse']['sellingPrice'] / 100)

        try:
            item["pdp_rating_value"] = (
                product['productResponse']['productVariant']['ratingSummary']['averageRating']
                if product['productResponse']['productVariant']['ratingSummary']
                else 0.0
            )
        except Exception:
            item["pdp_rating_value"] = 0.0

        try:
            item["pdp_rating_count"] = (
                product['productResponse']['productVariant']['ratingSummary']['totalRatings']
                if product['productResponse']['productVariant']['ratingSummary']
                else 0
            )
        except Exception:
            item["pdp_rating_count"] = 0

        images = product['productResponse']['productVariant'].get('images', [])
        item["pdp_image_url"] = images[0]["path"] if images else ""

        item["pdp_page_url"] = "https://www.zeptonow.com/pn/abc/pvid/" + item['web_pid']

        item["pdp_discount_value"] = (
            product['productResponse']['discountPercent']

            if product['productResponse']['discountPercent']
            else 0.0
        )

        sponsored_tag = False
        meta = product['productResponse'].get('meta', {})

        if meta:
            for tag in meta.get('tags', []):
                if tag.get('type') == 'SPONSORED':
                    sponsored_tag = True
                    break
            if not sponsored_tag:
                for tag_key, tag_value in meta.get('tagsV2', {}).items():
                    if tag_value.get('tagType') == 'SPONSORED':




                        sponsored_tag = True
                        break

        item["pdp_sponsored"] = 1 if sponsored_tag else 0
        item["sponsored_brand"] = (
            product['productResponse']['product']['brand'] if sponsored_tag else ""
        )
        item["location_id"] = self.location_id
        item["location_name"] = self.location
        item["pincode"] = str(self.pincode).strip()
        item["status"] = 1
        item["page"] = self.page
        item['grammage'] = (
            product['productResponse']['productVariant'].get('formattedPacksize') or ""
        )

        return item