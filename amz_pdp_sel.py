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

import undetected_chromedriver as uc

from tabulate import tabulate
from IPython.display import display
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service

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
from selenium.webdriver.chrome.options import Options

# Addons (For Now)
# from .addons import Get, Post, Session
from .amz_mods import *

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

SETTINGS = scrapy.utils.project.get_project_settings()

class AmzWebsitePDPSpider(InitSpider):
    name = "amz_pdp_sel"
    
    allowed_domains = ["amazon.in"]
    start_urls = ["https://www.amazon.in/"]
    custom_settings = {
            # specifies exported fields and order
            "DOWNLOAD_TIMEOUT": 60000,
            "DOWNLOAD_MAXSIZE": 12406585060,
            "DOWNLOAD_WARNSIZE": 0,
            "CONCURRENT_REQUESTS": 1,
            "CONCURRENT_REQUESTS_PER_DOMAIN":1,
            "CONCURRENT_REQUESTS_PER_IP":1,
            "HTTPPROXY_ENABLED": True,
            "TELNETCONSOLE_ENABLED": False,
            "DOWNLOADER_MIDDLEWARES" : {
                "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
                "scrapy_web_crawlers.middlewares.RandomUserAgentMiddleware": 1,
                } 
        }    
    HOME_URL = "https://www.amazon.in/"
    
    def __init__(self, inputs, **kw):
        super(AmzWebsitePDPSpider, self).__init__(**kw)
        self.inputs = inputs
        self.tz = inputs.get("tz")
        self.current_time = inputs.get("current_time")
        self.dt = inputs.get("dt")
        self.timestamp = inputs.get("timestamp")

        print("PF ID: "+inputs.get("pf_id"))
        print("SKU ID: "+inputs.get("sku_id"))
        print("WEB PID: "+inputs.get("web_pid"))
        print("URL: "+inputs.get("page_url"))
        print("LOCATION: "+inputs.get("location"))
        print("LOCATION ID: "+inputs.get("location_id"))
        print("PINCODE: "+inputs.get("pincode"))
        print("crawl_id: "+inputs.get("crawl_id"))
        print("ENV:" + inputs.get("env"))
        
        self.site = self.name
        self.env = inputs.get("env")
        self.db_name = inputs.get("db_name")        
        self.crawl_id = int(inputs.get("crawl_id"))
        self.pf_id = int(inputs.get("pf_id"))
        self.sku_id = int(inputs.get("sku_id"))      
        self.web_pid = inputs.get("web_pid")
        self.pdp_page_url = inputs.get("page_url")
        # self.pdp_page_url = "https://www.amazon.in/dp/B084884GKX"
        if inputs.get("brand_id") and inputs.get("brand_id") != "None":
            self.brand_id = int(inputs.get("brand_id"))
        else:
            self.brand_id = 0
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
                                "pdp_bulletin_value","reseller_name_crawl", "seller_rank", "five_star", "four_star","three_star","two_star","one_star", "status","deal_flag","pdp_top_review"
                            ]
        
        self.visit_count = str(random.choice([10,11,12,13]))

        self.session = Session()
        # self.session.headers.update({
        #     # 'Referer': 'https://www.amazon.in/'
        #     'referer':'https://www.google.com/',
        #     'authority': 'www.amazon.in',
        #     'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        #     'accept-language': 'en-US,en;q=0.9',
        #     'cache-control': 'max-age=0',
        #     'cookie': 'session-id=260-5764615-0101400; ubid-acbin=262-7407149-5048046; s_fid=71EFFABE73B1C8A2-2FE8BFD6F9BE531C; ab.storage.sessionId.a9882122-ac6c-486a-bc3b-fab39ef624c5=%7B%22g%22%3A%223fc0ec75-b9d8-4343-3711-896210ed833c%22%2C%22e%22%3A1680938289501%2C%22c%22%3A1680934689501%2C%22l%22%3A1680934689501%7D; ab.storage.deviceId.a9882122-ac6c-486a-bc3b-fab39ef624c5=%7B%22g%22%3A%22c340779e-2f74-b8b8-327b-33bcf9f0f1c9%22%2C%22c%22%3A1679650366223%2C%22l%22%3A1680934689502%7D; ab.storage.userId.a9882122-ac6c-486a-bc3b-fab39ef624c5=%7B%22g%22%3A%22d4f27a36-4ec2-4d12-a5b0-d414ac70be9b%22%2C%22c%22%3A1680934689497%2C%22l%22%3A1680934689503%7D; lc-acbin=en_IN; at-acbin=Atza|IwEBIOAnYky0fVr0liedsMlDoFS_2lttlp88d4mbI7nplCO5WCVbTXr9QekxZQ7-1wO3rhFuIe1-w2tQm3cqLqJuUwmhOujL4nkJNZ3qzthTpVIR3kWwytt9VkVQLaoLsGvb7Du4vjZwwzTPGL645gJtrlitshqa8SaN1o4y_O5a_6GSig4LN95F4GJQeyoyFhgtnl8m-mLyliCKfjWhTcV1eNeoUASYJftIm_zLzQA09FT-vMjvw5n__cO1uaCppeQD6N9730RtwHulnEtMbemFYicNvksf3votXAHspIlcuOwh4w; x-acbin="Vt1GkOypKTK@gFWp0CcUcBU7QSig2@AspiPmdzwFFvxDph5YTkOgAIAkwhId2U9s"; sst-acbin=Sst1|PQEtsAOAJs94R9qpa2-_x0XYDJXV8kLSOfsIUcT0tsdhHJIx1XrOWPNncw4Ms1euNdibsPq4F6BAA7fEgWiRECdY0h6NCSfmABFvqwdTSuYeiN2GKRU7KUZ7UrGFYEAkyWckrik5yk-lx_Y9sIuMLU_z69Ic5A8NQRC_wG7oCNKnCR1HjGYuUzZ2yNnPaXA3g9daMLyeWKUNvhpr86-vHePQ6Pzsc1KtTxMoLXCTtiBX17e1sf1VC2wAjsfgAzC8sTJVcvD7exUb-0OA0CLRD_UuppUXm-yDCvHIy2YmDFs67xiacAqMOeX7_K7xSCTkdd0HoZB9loPap15xQ1yV7t_Q_2_ivLenhAWtMApqmDGjiQc; i18n-prefs=INR; session-id-time=2082787201l; csm-hit=tb:TQQRJ8HT3NFTE7701GJ2+s-TQQRJ8HT3NFTE7701GJ2|1685108978410&t:1685108978410&adb:adblk_no; session-token="LRqJOYzLASe9XBFuvW7M4V932EpUhdWfr0iX1O1CFVX1N227EMw/d3xrWh8OmMT4V3D2jPaeRXiMQF3rCWJJviYHJe4r9pk5AmFQtZUugBG3CWdJIkUniAipTC2Qo1UeRfHvSMnrmdSmVof+KkbEdJQ+7RLyeizCLGQqOSPaigZI73XxB1G/dvoyBCzyp4GTuULb4kblTrM5GMppxjPC/732XmN6nAha0UJFzmBiQIcGWYhmRYYlag=="',
        #     'device-memory': '8',
        #     'dnt': '1',
        #     'downlink': '10',
        #     'dpr': '1.25',
        #     'ect': '4g',
        #     'rtt': '100',
        #     'sec-ch-device-memory': '8',
        #     'sec-ch-dpr': '1.25',
        #     'sec-ch-ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
        #     'sec-ch-ua-mobile': '?0',
        #     'sec-ch-ua-platform': '"Windows"',
        #     'sec-ch-ua-platform-version': '"15.0.0"',
        #     'sec-ch-viewport-width': '352',
        #     'sec-fetch-dest': 'document',
        #     'sec-fetch-mode': 'navigate',
        #     'sec-fetch-site': 'same-origin',
        #     'sec-fetch-user': '?1',
        #     'service-worker-navigation-preload': 'true',
        #     'upgrade-insecure-requests': '1',
        #     'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
        #     'viewport-width': '352',
        #     })
        self.db_action = DBAction()
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as error:
            self.logger.error("MySQL Error: "+error)
            print("Connection error with the database", error)

    def captcha_resolve_v2(self,driver,i):
        img_link = driver.find_element(By.XPATH,"//div[@class='a-row a-text-center']/img").get_attribute("src")
        file_cap_path="C:/var/logs/amz_pdp/Captcha"

        if os.path.exists(file_cap_path):
            print(f"The directory '{file_cap_path}' exists.")
        else:
            os.makedirs(file_cap_path)
        file_img = "C:/var/logs/amz_pdp/Captcha/test_"+str(self.web_pid)+str(i)+".jpg"
        if os.path.exists(file_img):
            print(f"The file '{file_img}' exists.")
        else:
            # Create the file test2.png
            with open(file_img, "w"):
                pass
        urllib.request.urlretrieve(img_link, file_img)
        captcha = AmazonCaptcha(file_img)
        cap_text = captcha.solve()
        driver.find_element(By.ID,"captchacharacters").send_keys(str(cap_text))
        # a-button-inner
        driver.find_element(By.CSS_SELECTOR,".a-button-inner").click()
            
    def captcha_resolve(self,soup,n):
        image_tags = soup.find_all("img", src=lambda src: src and ".jpg" in src)
        i=str(image_tags)
        img_link=i[11:-4]
        file_cap_path="C:/var/logs/amz_pdp/Captcha"

        if os.path.exists(file_cap_path):
            print(f"The directory '{file_cap_path}' exists.")
        else:
            os.makedirs(file_cap_path)
        file_img = "C:/var/logs/amz_pdp/Captcha/test_"+str(self.web_pid)+str(n)+".jpg"
        if os.path.exists(file_img):
            print(f"The file '{file_img}' exists.")
        else:
            # Create the file test2.png
            with open(file_img, "w"):
                pass
        urllib.request.urlretrieve(img_link, file_img)
        captcha = AmazonCaptcha(file_img)
        cap_text = captcha.solve()
        print(cap_text)
        amzn = soup.find('input', {'name': 'amzn'}).get('value')
        amzn_r = soup.find('input', {'name': 'amzn-r'}).get('value')
        url="https://www.amazon.in/errors/validateCaptcha?amzn="+str(urllib.parse.quote(amzn))+"&amzn-r="+str(urllib.parse.quote(amzn_r))+"&field-keywords="+str(cap_text)
        response = Get(session=self.session, url=url)
        if(response==None):
            if self.location_search == str(1):
                res = ChangePin(self.session, str(self.pincode))
            response = Get(session=self.session, url=self.pdp_page_url)
        return response

    def init_request(self):    
        # Home Page Request
        self.logger.info("Home Page Request")           
        # if self.location_search == str(1):
        #     res = ChangePin(self.session, str(self.pincode))            

        # print("pin got changed")
        # pdp_response = Get(session=self.session, url=self.pdp_page_url)
        # soup = BeautifulSoup(pdp_response, 'html.parser')

        # captcha_text = "we just need to make sure you're not a robot"
        # n=5
        # for i in range(0,n):
        #     if(pdp_response.status_code==200 and pdp_response!=None):
        #         soup = BeautifulSoup(pdp_response, 'html.parser')
        #     if captcha_text in soup.get_text():
        #         pdp_response=self.captcha_resolve(soup,i)
        #     else:
        #         break



        # chromeOptions = uc.ChromeOptions()
        # prefs = {
        # #             "download.default_directory" : download_path,
        #             "download.prompt_for_download":False,
        #             "browser.helperApps.alwaysAsk.force": False,
        #             "browser.download.manager.useWindow": False,
        #             "download.directory_upgrade": True,
        #             "safebrowsing_for_trusted_sources_enabled": False,
        #             "safebrowsing.enabled": False
        #         }
        # chromeOptions.add_experimental_option("prefs",prefs)
        # # chromeOptions.add_argument(f'--geolocation-override={lat},{lon}')
        # # chromeOptions.add_argument("--headless")
        # # chrome_driver_path = "D:/Trailytics/crawlers"                     #change path according to your sys
        # # os.environ["PATH"] += os.pathsep + chrome_driver_path
        # # driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=chromeOptions)
        # driver = uc.Chrome(options=chromeOptions)
        chromeOptions = webdriver.ChromeOptions()
        prefs = {
            "download.prompt_for_download": False,
            "browser.helperApps.alwaysAsk.force": False,
                "browser.download.manager.useWindow": False,
    "download.directory_upgrade": True,
    "safebrowsing_for_trusted_sources_enabled": False,
    "safebrowsing.enabled": False
}
        # Add preferences to Chrome options
        chromeOptions.add_experimental_option("prefs", prefs)
# Set Chrome to run headless
        # chromeOptions.add_argument("--headless=new")
# Initialize Chrome WebDriver with specified options and service
        driver = webdriver.Chrome(service=webdriver.ChromeService(r'C:\crawlers\chromedriver.exe'), options=chromeOptions)


        driver.implicitly_wait(random.choice([4,5,6,7]))
        driver.get(self.pdp_page_url)
        #driver.maximize_window()
        time.sleep(random.choice([3,4]))
        html_container=""
        # driver.find_element(By.ID,"GLUXZipUpdateInput").send_keys(str(self.pincode))
        # time.sleep(random.choice([2]))
        # driver.find_element(By.ID,"GLUXZipUpdate").click()
        # time.sleep(random.choice([3,4]))
        # html_container = driver.find_element(By.ID,"a-page").get_attribute('innerHTML')
        page=""
        captcha_text = "we just need to make sure you're not a robot"
        n=5
        for i in range(0,n):
            if captcha_text in driver.page_source:
                print("we got some thing")
                self.captcha_resolve_v2(driver,i)
            else:
                print("happy :-")
                break
        
        try:
            html_container=driver.find_element(By.ID,"a-page").get_attribute('innerHTML')
        except:
            html_container = driver.find_element(By.CSS_SELECTOR, "#a-page").get_attribute('innerHTML')
        
        if self.location_search == str(1):       
            try:
                driver.find_element(By.ID,"nav-global-location-slot").click()
                time.sleep(random.choice([2,3,4]))
                driver.find_element(By.ID,"GLUXZipUpdateInput").send_keys(str(self.pincode))
                time.sleep(random.choice([3,4]))
                driver.find_element(By.ID,"GLUXZipUpdate").click()
                time.sleep(random.choice([3,4]))
                html_container = driver.find_element(By.ID,"a-page").get_attribute('innerHTML')
                page=driver.page_source
            except:
                # try:
                driver.find_element(By.CSS_SELECTOR,"#nav-global-location-slot").click()
                time.sleep(random.choice([3,4]))
                driver.find_element(By.CSS_SELECTOR, "#GLUXZipUpdateInput").send_keys(str(self.pincode))
                time.sleep(random.choice([3,4]))
                driver.find_element(By.CSS_SELECTOR, "#GLUXZipUpdate").click()
                time.sleep(random.choice([3,4]))
                html_container = driver.find_element(By.CSS_SELECTOR, "#a-page").get_attribute('innerHTML')
                page=driver.page_source

            global review_count

            #Review count section
            try:
                # chrome_options = Options()
                # # chrome_options.add_argument("--headless")  # Run Chrome in headless mode
                # chrome_options.add_argument("--disable-gpu")
                # chrome_options.add_argument("--window-size=1920x1080")
                # service = Service(r'D:\chrome_drivers\chromedriver.exe')  # Replace with the path to your chromedriver
                # driver2 = webdriver.Chrome(service=service, options=chrome_options)
                # # Extract the product ID from the given URL
                product_id = self.pdp_page_url.split('/')[-1]
                # Construct the reviews URL
                reviews_url = f"https://www.amazon.in/dp/product-reviews/{product_id}/"
                # Fetch the reviews page
                driver.get(reviews_url)

                time.sleep(5)

                try:
                    # Get the page source and parse it with BeautifulSoup
                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                    
                    # Find the review count element
                    review_count_div = soup.find('div', {'data-hook': 'cr-filter-info-review-rating-count'})
                    if review_count_div:
                        review_count_text = review_count_div.get_text()
                        # Split the text content to get the required number
                        parts = review_count_text.split(', ')
                        reviews_with_text = parts[1].split()[0]
                        # Extract the number from the text
                        review_count = reviews_with_text
                        print('Author : Pankaj, Parameter : review_count, Value :  ' + review_count)
                    else:
                        review_count = 0

                except Exception as e:
                    print('Author : Pankaj, Parameter : Error, Value :  From Line 345 to Line 359')
                    review_count = 0
            except Exception as e:
                print('Author : Pankaj, Parameter : Error, Value :  From Line 344 to Line 363')
                review_count = 0

            reviews_url = f"https://www.amazon.in/dp/{product_id}/"
            # Fetch the reviews page
            driver.get(reviews_url)

            
                # except:
                #     print("some error incountered")
        # time.sleep(random.choice([20]))
        try:
            cache_path = chromedriver_autoinstaller.cache_dir
            shutil.rmtree(cache_path)
        except:
            print("Hi")
        driver.delete_all_cookies()
        items = self.parse_detail_page(response=html_container, web_pid=self.web_pid,page=page)

        if len(items):
            self.logger.info(f'Scrapped PDP - {self.web_pid} {self.pdp_page_url}')
        else:
            self.logger.error(f'PDP Failed - {self.web_pid} {self.pdp_page_url}')

    def web_pid_search(self, response):
        webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
        filename = "/%s-%s.html" % (str(self.pincode), self.site)
        if True:
            utils.save_source_content(webpage_dir, filename, response.body)
        
        self.logger.info("Got successful response from {}".format(response.url)) 
        self.logger.info(response.request.headers)
        
        url = "https://www.amazon.in/dp/"       
        #for crawl_input in self.crawl_inputs:

        self.logger.info("Crawl web_pid : "+self.web_pid)            
        yield scrapy.Request(
                url = self.pdp_page_url,
                method="GET",
                headers={
                 			"Content-Type": "application/x-www-form-urlencoded",
                 			"Accept": "text/html,*/*",
                 			"X-Requested-With": "XMLHttpRequest",
                 			"Referer": response.url
                            },
                cookies={
                            "amzn-app-id": "Amazon.in/20.04.0.350/20.04.0.350",
                            "i18n-prefs":"INR",
                            "lc-acbin":"en_IN",                                         
                            "visitCount":self.visit_count
                            },          
                callback=self.parse_detail_page, 
                errback=self.errback_httpbin,
                cb_kwargs=dict(web_pid=self.web_pid)
            )            
            
    def parse_detail_page(self, response, web_pid,page=None):
        global review_count
        items = list()
        try:
            # self.logger.info("Got successful response from {}".format(response))
            # self.logger.info(response.request.headers)
            
            webpage_dir = "%s/webpages/%s" % (self.base_dir, str(self.dt))
            if not os.path.exists(webpage_dir):
                os.makedirs(webpage_dir)
            filename = "/%s-%s-%s.html" % (str(self.pincode), self.site, web_pid)
            loc=webpage_dir+filename
            print(loc)
            print(str(self.inputs.get("pdp_snapshot")))
            if str(self.inputs.get("pdp_snapshot")) == "1" or True:
                # try:
                #     utils.save_source_content(webpage_dir, filename, response)
                # except:
                #     utils.save_source_content(webpage_dir, filename, response)     
                with open(loc, "w", encoding="utf-8") as html_file:
                    html_file.write(page)
                self.logger.info("Saved file %s" % filename)     
                
            self.logger.info("Data Extraction Start")
        except:
            print("Error saving the file")
    
            
        self.logger.info("Data Extraction Start")

        response_selector = Selector(text=response)
        soup = BeautifulSoup(response, 'html.parser')
        print("Atul-soup",soup)
        #soup = BeautifulSoup(html_code, 'html.parser')
        #stars
        # Extract breakdown of ratings
        total_ratings = int(soup.find('span', {'data-hook': 'total-review-count'}).text.strip().split()[0].replace(',', ''))

# Extract breakdown of ratings
        try:
            stars = {}
            histogram_rows = soup.select('tr.a-histogram-row')
            for row in histogram_rows:
                rating = row.find('a', {'class': 'a-link-normal'}).text.strip()
                percentage_str = row.find('div', {'class': 'a-meter-bar'})['style']

                # Extract numerical percentage value
                percentage = float(percentage_str.replace('width:', '').replace('%', '').strip()) / 100

                # Multiply percentage by total global ratings
                stars[rating] = int(percentage * total_ratings)

            # Print the updated stars dictionary
            print("Updated Stars Dictionary:")
            for rating, count in stars.items():
                print(f"{rating}: {count}")
                print(stars)
        except:
            pass

        center_col = response_selector.xpath("//div[@id='centerCol']").get()        
        if center_col != None:            
            center_col_sel = Selector(text=center_col)
            
            name = center_col_sel.xpath("//span[@id='productTitle']/text()").get()
            if name is None or name == "" or len(name)==0:
                name = response_selector.xpath("//span[@id='productTitle']").get()
            name = name.strip().replace("        ",'')
            if "        " in name:
                print("kunsh1",name.replace("        ",''))
            brand = center_col_sel.xpath("//a[@id='bylineInfo']/text()").get()
            if brand is None:
                brand = center_col_sel.xpath("//div[@id='bylineInfo_feature_div']/div/text()").get()
                if brand is None:
                    brand = center_col_sel.xpath("//div[@id='productOverview_feature_div']").re_first(r'Brand\s*</span>\s*</td>\s*<td[^>]+>\s*<span[^>]+>([^<]+)<')
            if brand:
                brand = re.sub("\s*Brand\s*:\s*", "", brand)
                brand = re.sub("\s*Visit the\s*", "", brand)
                brand = re.sub("\s*Store\s*", "", brand)
            else:
                brand = name and name.split(' ', 1)[0] or brand
            self.logger.info("brand: {0}".format(brand))
            # Rating Review Section
            try:
                review_sel = Selector(text=center_col_sel.xpath("//div[@id='averageCustomerReviews']").get())                       
                rating_value = review_sel.xpath("//span[@id='acrPopover']/span/a/i/span[@class='a-icon-alt']/text()").re_first(r'([0-9\.]+)\s*out')
                rating_value = rating_value.strip().replace(",", "") 
            
                rating_count = review_sel.xpath("//a[@id='acrCustomerReviewLink']/span[@id='acrCustomerReviewText']/text()").re_first('([0-9,]+)\s*rating')
                rating_count = int(rating_count.strip().replace(",", ""))
            except (ValueError, AttributeError, TypeError) as er:
                rating_value = 0.0
                rating_count = 0

            rtng_brk_up_sel = Selector(text=response_selector.xpath("//div[@id='reviewsMedley']").get())
            all_ratings = rtng_brk_up_sel.xpath("//td[@class='aok-nowrap']/span[@class='a-size-base']/a/@title").extract()
            ratings = dict()


            
            try:
                ratings = {"5 stars": 0, "4 stars": 0, "3 stars": 0, "2 stars": 0, "1 stars": 0}
                for r in all_ratings:
                    rtng = r.replace("% of reviews have", ":")
                    rtng = rtng.strip()
                    r = rtng.split(":")[0].strip()
                    star = rtng.split(":")[1].strip()
                    rtng=round((int(r)*int(rating_count))/100,0)
                    ratings[star] = rtng
            except:
                ratings = {"5 stars": 0, "4 stars": 0, "3 stars": 0, "2 stars": 0, "1 stars": 0}

                
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
            self.logger.info("ratings star: " + str(stars))
            # Price Section
            try:
                price_sel = Selector(text=center_col_sel.xpath("//div[@id='desktop_unifiedPrice']").get())
                try:
                    mrp = price_sel.xpath("//span[@class='priceBlockStrikePriceString a-text-strike']/text()").get()
                    if mrp is None:
                        mrp = price_sel.xpath("//span[@class='a-size-base a-color-secondary priceBlockStrikePriceString a-text-strike']/text()").get()
                        mrp = mrp.replace(",", "")
                    if mrp is None:
                        price_sel.css("#a-price a-text-price a-size-base::text")    
                    mrp = re.sub('[^A-Za-z0-9.]+', '', mrp)       
                except:
                    mrp = 0.0
                try:
                    price = center_col_sel.css("#priceblock_saleprice::text").get()\
                            or center_col_sel.css("#priceblock_ourprice::text").get()\
                            or center_col_sel.css("#priceblock_dealprice::text").get()\
                            or center_col_sel.css("#corePrice_feature_div .a-offscreen::text").get()\
                            or response_selector.css("#tp_price_block_total_price_ww .a-offscreen::text").get()
                    price = price.replace(",", "")
                    price = re.sub('[^A-Za-z0-9.]+', '', price)
                except (ValueError, TypeError, AttributeError) as ve:
                    try:
                        price = price_sel.xpath("//*[@id='priceblock_dealprice']/text()").get()
                        price = price.replace(",", "")
                        price = re.sub('[^A-Za-z0-9.]+', '', price)
                    except Exception as e:
                        price = 0
                # Grabbing Current Price (so we don't need to grab saving and discount manually)
                try:
                    current_price = response_selector.css('.priceBlockSavingsString::text')[-1].get()
                    current_price = current_price.replace(',', '')
                except:
                    current_price = None
                
                try:
                    current_price = response_selector.css('span[class="a-price-whole"]').get()
                except:
                    current_price = response_selector.css('span[class="a-price-whole"]').get()


                if current_price:
                    try:
                        savings = re.findall(r'([0-9]+).', current_price)[0]
                        discount = re.findall(r'\(([0-9]+)%\)', current_price)[0]
                    except:
                        savings = 0
                        discount = 0
                else:
                        savings = 0
                        discount = 0
                # print(savings, discount, 'AMAZON')
                if not savings or not discount:
                    # print('In failsafe')
                    try:
                        savings = price_sel.xpath("//tr[@id='regularprice_savings']/td[2]/text()").get()
                        savings = price_sel.xpath("//tr[@id='regularprice_savings']/td[2]").re_first(r'([0-9\.]+)')
                        savings = savings.replace(",", "")
                    except (ValueError, TypeError, AttributeError) as ve:
                        savings = 0.0
                    
                    try:
                        discount = price_sel.xpath("//tr[@id='regularprice_savings']").re_first(r'priceBlockSavingsString">[^\(]+\(\s*([^\)]+)\)')
                        discount = discount.replace(",", "").replace("%","")
                    except(ValueError, TypeError, AttributeError) as ve:
                        discount = 0.0
                
                try:
                    currency = price_sel.xpath("//span[@id='priceblock_ourprice']").re_first(r'([^&]+)&')
                    if currency == "₹":
                        currency = "INR"
                    elif currency == "$":
                        currency = "USD"
                    else:
                        currency = "INR"            
                except(ValueError, TypeError, AttributeError) as ve:
                    currency = ""
            except (ValueError, TypeError, AttributeError) as ve:
                try:
                    price_sel = Selector(text=center_col_sel.xpath("//div[@id='almDetailPagePrice_price']").get())
                    mrp = price_sel.xpath("//span[@class='priceBlockStrikePriceString a-text-strike']/text()").get()
                    try:
                        mrp = price_sel.xpath("//span[@class='a-size-base a-color-secondary priceBlockStrikePriceString a-text-strike']/text()").get()
                        mrp = mrp.replace(",", "")
                        mrp = re.sub('[^A-Za-z0-9.]+', '', mrp)
                    except (ValueError, TypeError, AttributeError) as ve:
                        mrp = 0.0
                    self.logger.info("SECOND MRP: " + str(mrp))
                    try:
                        price = center_col_sel.css("#priceblock_saleprice::text").get()\
                            or center_col_sel.css("#priceblock_ourprice::text").get()\
                            or center_col_sel.css("#priceblock_dealprice::text").get()\
                            or center_col_sel.css("#corePrice_feature_div .a-offscreen::text").get()\
                            or response_selector.css("#tp_price_block_total_price_ww .a-offscreen::text").get()
                        price = price.replace(",", "")
                        price = re.sub('[^A-Za-z0-9.]+', '', price)
                    except (ValueError, TypeError, AttributeError) as ve:
                        price = 0.0

                    # Grabbing Current Price (so we don't need to grab saving and discount manually)
                    try:
                        current_price = response_selector.css('.priceBlockSavingsString::text')[-1].get()
                        current_price = current_price.replace(',', '')
                    except:
                        current_price = None

                    if current_price:
                        try:
                            savings = re.findall(r'([0-9]+).', current_price)[0]
                            discount = re.findall(r'\(([0-9]+)%\)', current_price)[0]
                        except:
                            savings = 0
                            discount = 0
                    else:
                        savings = 0
                        discount = 0
                    # print(savings, discount, 'AMAZON')
                    # Failsafe for saving and discount
                    if not (savings or discount):
                        try:
                            savings = price_sel.xpath("//tr[@id='regularprice_savings']/td[2]/text()").get()
                            savings = price_sel.xpath("//tr[@id='regularprice_savings']/td[2]").re_first(r'([0-9\.]+)')
                            savings = savings.replace(",", "")
                        except (ValueError, TypeError, AttributeError):
                            savings = 0.0
                        try:
                            discount = price_sel.xpath("//tr[@id='regularprice_savings']").re_first(r'priceBlockSavingsString">[^\(]+\(\s*([^\)]+)\)')
                            discount = discount.replace(",", "").replace("%","")
                        except (ValueError, TypeError, AttributeError):
                            discount = 0.0

                    try:
                        currency = price_sel.xpath("//span[@id='priceblock_ourprice']").re_first(r'([^&]+)&')
                        if currency == "₹":
                            currency = "INR"
                        elif currency == "$":
                            currency = "USD"
                        else:
                            currency = "INR"            
                    except (ValueError, TypeError, AttributeError) as ve:
                        currency = ""
                except (ValueError, TypeError, AttributeError) as ve:
                    mrp = 0
                    price = 0
                    savings = 0
                    discount = 0
                    currency = "INR"

            if not mrp:
                mrp = float(mrp) or center_col_sel.css(".a-price[data-a-strike='true'] .a-offscreen::text").get()
            if not price:
                price = center_col_sel.css("#priceblock_saleprice::text").get()\
                        or center_col_sel.css("#priceblock_ourprice::text").get()\
                        or center_col_sel.css("#priceblock_dealprice::text").get()\
                        or center_col_sel.css("#corePrice_feature_div .a-offscreen::text").get()\
                        or response_selector.css("#tp_price_block_total_price_ww .a-offscreen::text").get()

            mrp = mrp and re.sub('[^A-Za-z0-9.]+', '', mrp.replace(",", "").strip()) or 0
            price = price and re.sub('[^A-Za-z0-9.]+', '', price.replace(",", "").strip()) or 0

            try:
                price_sp =  response_selector.css('span[class="a-price-whole"]::text').get()
                print(price_sp)

            except:
                price_sp = response_selector.css('span[class="a-offscreen"]::text').get()
                print(price_sp)


            
            if not mrp:
                mrp = price
            elif not price:
                price = mrp

            try:
                mrp = float(mrp)
                price = float(price)
                savings = mrp-price
                discount = mrp-price and round(((mrp-price)/mrp)*100, 2) or 0
            except Exception as e:
                print('ERR_PRICE_AFTERMATH', e, price, mrp)
                savings = 0
                discount = 0.0
                mrp = 0
                price = 0


            if mrp == 0 and price!=0:
                mrp = price
            if price == 0 and mrp!=0:
                price = mrp
            self.logger.info("MRP: " + str(mrp))
            self.logger.info("PRICE: " + str(price))
            self.logger.info("SAVINGS: " + str(savings))
            self.logger.info("DISCOUNT: " + str(discount))
            self.logger.info("CURRENCY: " + str(currency))


           
              
            
            # Stock Section
            in_stock = center_col_sel.xpath(
                "//div[@id='availability']/span/text()").get()
            if in_stock is None:
                in_stock = center_col_sel.xpath(
                    "//div[@id='availability-string']/span/text()").get()
                if in_stock is None:
                    in_stock = ""
            else:
                in_stock = in_stock.replace(".", "")

            if not in_stock:
                in_stock = response_selector.xpath(
                    "//div[@id='availability']/span/text()").get()
                if in_stock is None:
                    in_stock = response_selector.xpath(
                        "//div[@id='availability-string']/span/text()").get()
                    if in_stock is None:
                        in_stock = ""
                else:
                    in_stock = in_stock.replace(".", "")
            
            # Seller Section
            seller = response_selector.css('#merchant-info a span::text').get() or center_col_sel.xpath("//a[@id='sellerProfileTriggerId']/text()").get()
            if not seller:
                seller = response_selector.css('#fresh-merchant-info a span::text').get() or center_col_sel.xpath("//div[@id='fresh-merchant-info']/a/text()").get()

            # New Implementation
            if not seller:
                seller_element = soup.select_one('#merchant-info a') or soup.select_one('#fresh-merchant-info a')
                if seller_element:
                    seller = getattr(seller_element, 'text', '').strip() or None
            

            seller = response_selector.css('#merchant-info a span::text').get() or center_col_sel.xpath("//a[@id='sellerProfileTriggerId']/text()").get()
            if not seller:
                seller = response_selector.css('#fresh-merchant-info a span::text').get() or center_col_sel.xpath("//div[@id='fresh-merchant-info']/a/text()").get()
            if not seller:
                try:
                    seller = soup.find('a', {'id': 'sellerProfileTriggerId'}).text.strip()
                except:
                    seller=""
            # New Implementation
            if not seller:
                seller_element = soup.select_one('#merchant-info a') or soup.select_one('#fresh-merchant-info a')
                if seller_element:
                    seller = getattr(seller_element, 'text', '').strip() or None













            # print('Seller', seller, self.pdp_page_url)
                
            amazon_shipping_type = center_col_sel.xpath("//span[@id='price-shipping-message']/i/span[@class='a-icon-text-fba']/text()").get()
            
            info = center_col_sel.xpath("//div[@id='productOverview_feature_div']/div[@class='a-section a-spacing-small a-spacing-top-small']").get()
            feature_bullets = center_col_sel.xpath("//div[@id='feature-bullets']")

            # about_this_items = feature_bullets.xpath("//div[@id='featurebullets_feature_div']/div[@id='feature-bullets']/ul/li").getall()
            # about_this_items = [remove_tags(item.replace("\n", "").strip()) for item in about_this_items]            

            # if about_this_items is None:
            #     about_this_items = feature_bullets.xpath("//ul[@class='a-unordered-list a-vertical a-spacing-mini']/li").getall()
            #     about_this_items = [remove_tags(item.replace("\n", "").strip()) for item in about_this_items]

            # if len(about_this_items) > 0:
            #     about_this_item = ";".join(about_this_items)
            # else:
            #     about_this_item = ""
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

            # # Image Section
            # images_sel = Selector(text = response_selector.xpath("//div[@id='main-image-container']").get())
            # images = images_sel.xpath("//img[@id='landingImage']/@data-a-dynamic-image").extract_first()
            # images = re.sub(r":\[\d+,\d+\]", '', images)
            # images = images.replace("{","").replace("}","").replace("\"","")
            # images_list = images.split(",")            
            # image_url = images_list[0]

            # Image Section New Implementation
            images_list = []
            if 'altImages' in response:
                for img in response_selector.css('#landingImage'):
                    if 'common' not in img.attrib['src']:
                        images_list.append(img.attrib['src'])
                image_url = images_list[0]
            else:
                images_list = []
                image_url = ""

            
            # A-Plus Image Section
            try:
                ec_images_sel = Selector(text=response_selector.xpath("//div[@id='aplus']").get())
                ec_images_list = ec_images_sel.xpath("//img/@data-src").extract()
                self.logger.info(ec_images_list)
                if len(ec_images_list) != 0:
                    vec_number_of_image = len(ec_images_list)
                else:
                    vec_number_of_image = 0
            except (ValueError, TypeError) as nt:
                ec_images_list = ""
                vec_number_of_image = 0

            # Forth Rank Implementation
            try:
                best_sellers_rank = ""
                rankings = []
                # First Ranking (returns list -> [rank, rank category])
                if 'SalesRank' in response:
                    rankings += response_selector.css('#SalesRank').re('.*Bestsellers\s*Rank:\s*.+#([^\s<]+)\s*in\s*([^\(]+)')
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



                
            if "<h2>Product details</h2>" in response:
                self.logger.info("Page Type 1 layout found")
                
                product_dtls_sel = Selector(text=response_selector.xpath("//div[@id='detailBulletsWrapper_feature_div']").get())
                technical_details = product_dtls_sel.xpath("//div[@id='detailBulletsWrapper_feature_div']")
                #additional_information = product_dtls_sel.xpath("//div[@id='productDetails_db_sections']")
                product_details = product_dtls_sel.xpath("//div[@id='detailBullets_feature_div']/text()").get()
            
                model_number = technical_details.re_first(r'<span class="a-text-bold">\s*Item\s*model\s*number\s*:\s*</span>\s*<span>([^<]*)<')
                manufacturer = technical_details.re_first(r'<span class="a-text-bold">\s*Manufacturer\s*:\s*</span>\s*<span>([^<]*)<')
                country_of_origin = technical_details.re_first(r'<span class="a-text-bold">\s*Country\s*of\s*Origin\s*:\s*</span>\s*<span>([^<]*)<')
                extracted_web_pid = technical_details.re_first(r'<span class="a-text-bold">\s*ASIN\s*[^:]+:\s*[^<]+</span>\s*<span>([^<]*)<')
                if not best_sellers_rank:
                    best_sellers_rank = technical_details.re(r'<span class="a-text-bold">\s*Best Sellers Rank\s*:\s*<\/span>\s*(.+?)\s*<ul[^>]*>\s*<li><span[^>]*>(.+?)\s*<\/a>')
                    best_sellers_rank = remove_tags("/".join(best_sellers_rank))
                
            elif '<div id="prodDetails" class="a-section">' in response:
                self.logger.info("Page Type 2 layout found")
                product_dtls_sel = Selector(text=response_selector.xpath("//div[@id='prodDetails']").get())
                technical_details = product_dtls_sel.xpath("//table[@id='productDetails_techSpec_section_1']")
                additional_information = product_dtls_sel.xpath("//div[@id='productDetails_db_sections']")
                product_details = product_dtls_sel.xpath("//table[@id='productDetails_techSpec_section_1']/text()").get()
                
                model_number = technical_details.re_first(r'prodDetSectionEntry">\s*Model\s*Number\s*</th>\s*<td\s*class="a-size-base">\s*([^<]+)<')
                manufacturer = technical_details.re_first(r'prodDetSectionEntry">\s*Manufacturer\s*</th>\s*<[^>]+>\s*([^<]+)<')
                country_of_origin = technical_details.re_first(r'prodDetSectionEntry">\s*Country\s+of\s+Origin\s*</th>\s*<[^>]+>\s*([^<]+)<')
                extracted_web_pid = additional_information.re_first(r'prodDetSectionEntry">\s*ASIN\s*</th>\s*<td[^>]+>\s*([^<]+)<')
                if not best_sellers_rank:
                    best_sellers_rank = additional_information.re(r'prodDetSectionEntry">\s*Best\s*Sellers\s*Rank\s*<\/th>\s*<td>\s*<span>\s*<span>\s*(.+?)\s*<\/span>\s*<br>\s*<span>(.+?)<\/span>')
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
                    product_desc_sel = Selector(text=response_selector.xpath("//div[@id='productDescription_feature_div']").get())
                    product_description = product_desc_sel.xpath("//div[@id='productDescription']").get()
                except:
                    product_description = ""
            
            if best_sellers_rank is not None:
                best_sellers_rank = re.sub("\([^\)]+\)", "", best_sellers_rank)
                best_sellers_rank = best_sellers_rank.replace("#", "").replace(",","").replace("/", ";").replace("in", ";").replace(" ", "")
            else:
                best_sellers_rank = "0"

            # Third Rank Implementation
            if not best_sellers_rank or best_sellers_rank == "0":
                # Grabs any number of rankings (variant 2nd) (grabs any number of rankings)
                try:
                    rankings = []
                    # First Ranking (returns list -> [rank, rank category])
                    rankings += response_selector.css('#SalesRank').re('.*Bestsellers\s*Rank:\s*.+#([^\s<]+)\s*in\s*([^\(]+)')
                    # Grab others
                    for li in response_selector.css('.zg_hrsr_item'):
                        rankings.append(li.css('span::text').get())
                        rankings.append(li.css('a::text').get())
                    if rankings:
                        best_sellers_rank = ';'.join([rank.strip().replace(',', '').replace(' ', '') for rank in rankings])
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

            print("jaishreeram")
            try:
                delivery_time = response_selector.xpath("//div[@id='mir-layout-DELIVERY_BLOCK']//span[@data-csa-c-delivery-time]/@data-csa-c-delivery-time").get()
            except:
                delivery_time = 0

            try:
                best_sellers_rank = response_selector.xpath("//ul[@class='a-unordered-list a-nostyle a-vertical a-spacing-none detail-bullet-list']/li/span[@class='a-list-item']/span[@class='a-text-bold' and contains(text(), 'Best Sellers Rank')]/following-sibling::text()").get()
                print(best_sellers_rank,"radhe")
                categories = response_selector.xpath("//ul[@class='a-unordered-list a-nostyle a-vertical a-spacing-none detail-bullet-list']/li/span[@class='a-list-item']/ul[@class='a-unordered-list a-nostyle a-vertical zg_hrsr']/li/span[@class='a-list-item']/text()").getall()
                category_text = response_selector.xpath("//ul[@class='a-unordered-list a-nostyle a-vertical a-spacing-none detail-bullet-list']/li/span[@class='a-list-item']/ul[@class='a-unordered-list a-nostyle a-vertical zg_hrsr']/li/span[@class='a-list-item']/a/text()").get()
                
# Append the category text to the list
                if category_text:
                    categories.append(category_text.strip())
                print(categories,"radhe")
                best_sellers_rank = best_sellers_rank+ ', '.join(categories)
                print(best_sellers_rank,"radhe")


            except:
                pass


            print(delivery_time,"jaishreeram")
            delivery_date = '0'
            for _ in range(20):
                try:
        # First attempt using center_col_sel
                    delivery_time = response.css('div#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE span[data-csa-c-delivery-time]::text').get()
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
                    delivery_date = response.css("#mir-layout-DELIVERY_BLOCK-slot-SECONDARY_DELIVERY_MESSAGE_LARGE > span::text").get()
                    delivery_date = delivery_date.strip()
                    print(delivery_date)
                except Exception as e:
                    delivery_date = '0'

    # If delivery_date is found, break out of the loop
                if delivery_date and delivery_date != '0':
                    break
                    
                try:
                    delivery_info = response.css('span[data-csa-c-type="element"][data-csa-c-id="5wtpci-ilxcxj-sypair-6w1b3b"]')
                    fastest_delivery_date = delivery_info.css('span.a-text-bold::text').get()
                except Exception as e:
                    delivery_date = '0'
                
                try:
                    delivery_info = response.css('span[data-csa-c-type="element"][data-csa-c-id="5wtpci-ilxcxj-sypair-6w1b3b"]')
                    delivery_time = delivery_info.xpath('@data-csa-c-delivery-time').get()
                except Exception as e:
                    delivery_date = '0'

                try:
                    delivery_time = response.css('#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE span[data-csa-c-delivery-time]::text').get()
                except Exception as e:
                    delivery_date = '0'




          
                


            
                

                

 

            if delivery_date != '0':
                if 'in stock' not in in_stock.lower():
                    in_stock = 'in stock'
            # Setting A deal In Nivea
            try:
                text_price_title  =response_selector.xpath("//td[@class='a-color-secondary a-size-base a-text-right a-nowrap']/text()").getall()
                print(text_price_title)
                if len(text_price_title)<2:
                    deal_flag = 0
                else:
                    if 'deal' in text_price_title[1].lower():
                        deal_flag = 1
                    else:
                        deal_flag = 0
            except Exception as e:
                deal_flag = 0
                self.logger.info("Error while fetching Deal Flag")

            def create_review_compressed_string(reviewers_name,reviews_star_rating,reviews_statement,reviews_date,reviews_helpful_number):
                if len(reviewers_name)==0 or len(reviews_star_rating)==0 or len(reviews_statement)==0 or len(reviews_date)==0 or len(reviews_helpful_number)==0:
                    return ""
                a = []
                for i in reviewers_name:
                    if len(a) and a[-1]==i:
                        continue
                    a.append(i)
                st =[]
                for i in list(zip(a,reviews_star_rating,reviews_statement,reviews_date,reviews_helpful_number)):
                    st.append("::".join(i))
                return ';'.join(st)
            # Getting most recent interview
            try:
                top_reviews = Selector(text = response_selector.xpath("//*[@id='reviewsMedley']/div/div[2]/div/div[2]/span[2]/div/div").get())
                reviewers_name = top_reviews.xpath("//span[@class='a-profile-name']/text()").getall()
                #print(reviewers_name,len(reviewers_name))
                reviews_star_rating = top_reviews.xpath("//i[@data-hook='review-star-rating']/span/text()").getall()
                #print(reviews_star_rating,len(reviews_star_rating))
                reviews_statement = top_reviews.xpath("//a[@data-hook='review-title']/span/text()").getall()
                #print(reviews_statement,len(reviews_statement))
                reviews_date = top_reviews.xpath("//span[@data-hook='review-date']/text()").getall()
                #print(reviews_date,len(reviews_date))
                # reviews_description = top_reviews.xpath("//div[@data-hook='review-collapsed']/span/text()").getall()
                # print(reviews_description,len(reviews_description))
                reviews_helpful_number = top_reviews.xpath("//span[@data-hook='helpful-vote-statement']/text()").getall()
                #print(reviews_helpful_number,len(reviews_helpful_number))
                pdp_top_review_info = create_review_compressed_string(reviewers_name,reviews_star_rating,reviews_statement,reviews_date,reviews_helpful_number)
                print(pdp_top_review_info)
            except Exception as e:
                pdp_top_review_info = ""
                self.logger.info("Error in Getting recent review info ")
            
            try:
               best_sellers_rank = best_sellers_rank.replace("#", "").replace(",", "").replace("(", ";").replace(")", "").replace(" ", "").replace("in",";")
            except:
                best_sellers_rank=""

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
            
            item["pdp_rating_value"] = rating_value if rating_value else 0
            item["pdp_rating_count"] = rating_count if rating_count else 0
            item["pdp_review_count"] = review_count if review_count else 0
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
            
            item["product_details"] = product_details and remove_tags(product_details.replace("\n","")) or ""
            item["pdp_desc_value"] = product_description and remove_tags(product_description.replace("\n","")) or ""
            
            item["pdp_image_count"] = len(images_list)
            item["pdp_image_url"] = image_url
            item["pdp_image_url_all"] = ", ".join((images_list))
            item["aplus_images_list"] = ", ".join(ec_images_list)
            item["ec_number_of_images"] = vec_number_of_image
            item["ec_number_of_videos"] = 0

            item["pdp_number_of_bulletin"] = len(about_this_items+add_bullets)            
            item["pdp_bulletin_value"] = add_bullet
            
            item["reseller_name_crawl"] = seller            
            item["seller_rank"] = best_sellers_rank
            item["best_sellers_rank"] = best_sellers_rank if best_sellers_rank else ""

            try:
                item["five_star"] = stars["5 star"]
            except:
                item["five_star"] = 0
                
            try:
                item["four_star"] = stars["4 star"]
            except:
                item["four_star"] = 0

            try:
                item["three_star"] = stars["3 star"]
            except:
                item["three_star"] = 0
            try:
                item["two_star"] = stars["2 star"]
            except:
                item["two_star"] = 0

            try:
                item["one_star"] = stars["1 star"]
            except:
                item["one_star"] = 0

            if "in stock" in in_stock.lower() or ("available" in in_stock.lower() and "unavailable" not in in_stock.lower()) :
                item["osa"] = 1
                item["osa_remark"] = "IN STOCK"
            else:
                item["osa"] = 0
                item["osa_remark"] = "OOS" 
                delivery_date = 0
            item['pdp_top_review'] = pdp_top_review_info
            item['deal_flag'] = deal_flag
            item["pdp_page_url"] = self.pdp_page_url
            item["delivery_date"] = delivery_time
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
            item["location_id"] = self.location_id
            item["location_name"] = self.location
            item["pincode"] = self.pincode      
            item["brand_id"] = self.brand_id
            item["brand_name"] = self.brand_name
            item["web_pid"] = self.web_pid
            item["extracted_web_pid"] = ""
            item["pdp_title_value"] = ""
            
            item["extracted_brand_name"] = ""

            item["pdp_review_count"] = 0
            item["pdp_rating_value"] = 0
            item["pdp_rating_count"] = 0
            item["pdp_qa_count"] = 0
            
            item["price_rp"] = 0
            item["price_sp"] = 0
            item["savings"] = 0
            item["pdp_discount_value"] = 0
            item["currency"] = ""           
            
            item["manufacturer"] = ""
            item["model_number"] = ""
            item["country_of_origin"] = ""
            item["shipping_type"] = ""
            
            item["about_this_item"] = ""
            item["product_details"] = ""
            item["pdp_desc_value"] = ""
            
            item["pdp_image_count"] = 0
            item["pdp_image_url"] = ""
            item["pdp_image_url_all"] = ""
            item["aplus_images_list"] = ""
            item["ec_number_of_images"] = 0
            item["ec_number_of_videos"] = 0

            item["pdp_number_of_bulletin"] = 0
            item["pdp_bulletin_value"] = ""

            item["reseller_name_crawl"] = ""
            item["seller_rank"] = 0

            item["five_star"] = 0
            item["four_star"] = 0
            item["three_star"] = 0
            item["two_star"] = 0
            item["one_star"] = 0

            item["osa"] = 0
            item["osa_remark"] = "0" 

            item["pdp_page_url"] = self.pdp_page_url
            item["group_id"] = 0
            item["created_by"] = "System"
            item["created_on"] = self.current_time
            item["status"] = 0
            items.append(item)
            self.logger.error("Something went wrong....")
        
        # Create Raw file without header
        for item in items:
            utils.create_raw_file(self.output_file, item.keys(), item)
        
        # Create Header file
        item = items[0]
        output_dir = self.base_dir+"/output"
        output_filename = "header.txt"
        output_file = output_dir+"/"+output_filename
        header_row = "|".join(item.keys()) +"\r"
        utils.create_file(output_file, header_row)

        # Converting into list of tuple
        records = []
        columns = self.output_cols
        for item in items:
            record = tuple(item.get(col, "0") for col in columns if col in item) 
            records.append(record)
        #records = [tuple(item.values()) for item in items]

        #self.logger.info("Database connection create")
        self.logger.info("Data inserting")

        tbl_columns_str = "`"+"`,`".join(self.output_cols)+"`"        
        values_list = []
        values_list.extend(repeat("%s", len(self.output_cols)))
        tbl_columns_val = ",".join(values_list)

        mySql_insert_query = """INSERT INTO `amazon_crawl_pdp` (""" +tbl_columns_str+ """) VALUES (""" +tbl_columns_val+ """)"""
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
