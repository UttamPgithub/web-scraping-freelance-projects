import json
import os
import random
import re
import sys
from bs4 import BeautifulSoup
import mysql.connector
import scrapy
from scrapy.spiders.init import InitSpider

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from db.db_action import DBAction


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_html_description(soup):
    # Find the heading whose exact text is "Description"
    heading = soup.find(
        lambda tag:
        tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]
        and tag.get_text(" ", strip=True).lower().strip() == "description"
    )

    if not heading:
        return ""

    # From that heading, find the next div
    # whose class contains "ContentGroups_htmlContent"
    content = heading.find_next(
        "div",
        class_=lambda c:
        c and "ContentGroups_htmlContent" in c
    )

    if not content:
        return ""

    # Extract all <p> tags inside that content container
    paragraphs = []

    for p in content.find_all("p"):

        text = p.get_text(
            " ",
            strip=True
        )

        if text:
            paragraphs.append(text)

    # If there are no <p> tags,
    # take the complete text of the content container
    if not paragraphs:

        text = content.get_text(
            " ",
            strip=True
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        ).strip()

        if text:
            paragraphs.append(text)

    # Join all paragraphs into one description
    description = " ".join(paragraphs)

    # Final whitespace cleanup
    description = re.sub(
        r"\s+",
        " ",
        description
    ).strip()

    return description


class PharmeasyPdpSpider(InitSpider):
    name = "pharmeasy_pdp_dr_reddy"
    allowed_domains = ["pharmeasy.in"]

    custom_settings = {
        "DOWNLOAD_TIMEOUT": 60,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS_PER_IP": 1,
        "HTTPPROXY_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "scrapy_web_crawlers.middlewares.RandomUserAgentMiddleware": 1,
        },
        "LOG_ENABLED": True,
    }

    OUTPUT_COLS = [
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
        "pdp_image_count",
        "pdp_image_url",
        "pdp_image_url_all",
        "pdp_qa_count",
        "pdp_desc_value",
        "reseller_name_crawl",
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
    ]

    def __init__(self, inputs=None, **kwargs):
        super(PharmeasyPdpSpider, self).__init__(**kwargs)
        self.inputs = inputs or {}

        # Identifiers
        self.site = self.name
        self.env = self.inputs.get("env")
        self.db_name = self.inputs.get("db_name")
        self.crawl_id = int(self.inputs.get("crawl_id", 0))
        self.pf_id = int(self.inputs.get("pf_id", 0))
        self.sku_id = int(self.inputs.get("sku_id", 0))
        self.web_pid = str(self.inputs.get("web_pid", ""))
        self.pdp_page_url = self.inputs.get("page_url", "")
        self.brand_id = int(self.inputs.get("brand_id", 0))
        self.brand_name = self.inputs.get("brand_name", "")

        # Location details
        self.location = self.inputs.get("location", "")
        self.location_id = int(self.inputs.get("location_id", 0))
        self.pincode = "110011" if str(self.location).lower() == "nation" else str(self.inputs.get("pincode", "110011"))
        self.current_time = self.inputs.get("current_time", "")

        # Database Setup
        self.db_action = DBAction()
        self.connection = None
        self.cursor = None
        try:
            self.connection = self.db_action.db_connection(db_name=self.db_name, env=self.env)
            self.cursor = self.connection.cursor()
        except Exception as error:
            self.logger.error("Database connection failed: %s", error)

    def init_request(self):
        """Starts the crawling lifecycle through Scrapy's pipeline."""
        headers = {
            "authority": "pharmeasy.in",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "referer": self.pdp_page_url,
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "upgrade-insecure-requests": "1",
        }
        cookies = {"X-Pincode": self.pincode}

        yield scrapy.Request(
            url=self.pdp_page_url,
            headers=headers,
            cookies=cookies,
            callback=self.parse_detail_page,
            errback=self.handle_error,
            dont_filter=True,
        )

    def handle_error(self, failure):
        self.logger.error("Request failed: %s", failure.getErrorMessage())

    def parse_detail_page(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        extracted_data = {}

        # Try parsing Next.js hydrated state first
        next_data_script = soup.find("script", id="__NEXT_DATA__", type="application/json")
        if next_data_script and next_data_script.string:
            try:
                raw_json = json.loads(next_data_script.string)
                extracted_data = self._parse_next_data(raw_json, soup)
            except Exception as e:
                self.logger.error("Failed to parse __NEXT_DATA__: %s", str(e))

        # Fallback to JSON-LD if __NEXT_DATA__ extraction was incomplete
        if not extracted_data.get("pdp_title_value"):
            extracted_data = self._parse_json_ld(soup, fallback_data=extracted_data)

        # Fallback description via direct HTML

        extracted_data["pdp_desc_value"] = extract_html_description(soup)

        record = self._build_record_dict(extracted_data)
        self._insert_into_db(record)

    def _parse_next_data(self, data: dict, soup: BeautifulSoup) -> dict:
        page_props = data.get("props", {}).get("pageProps", {})
        details = page_props.get("productDetails", {})
        seo_data = page_props.get("productSeoData", {})

        title = details.get("name") or seo_data.get("title", "")
        cost_price = float(details.get("costPrice") or 0.0)
        sale_price = float(details.get("salePrice") or 0.0)
        discount = float(details.get("discount") or 0.0)

        # Images
        dam_images = details.get("damImages", []) or []
        image_urls = [img["url"] for img in dam_images if isinstance(img, dict) and img.get("url")]

        # Stock / Availability
        is_available = details.get("isAvailable", False)

        return {
            "pdp_title_value": title,
            "price_rp": cost_price,
            "price_sp": sale_price,
            "pdp_discount_value": discount,
            "pdp_desc_value": seo_data.get("metadata", {}).get("metaDescription", ""),
            "pdp_image_url": image_urls[0] if image_urls else "",
            "pdp_image_url_all": ",".join(image_urls),
            "pdp_image_count": len(image_urls),
            "osa": 1 if is_available else 0,
            "osa_remark": "INSTOCK" if is_available else "OOS",
            "reseller_name_crawl": details.get("sellerName", ""),
        }

    def _parse_json_ld(self, soup: BeautifulSoup, fallback_data: dict) -> dict:
        data = fallback_data.copy()
        product_obj = None

        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                parsed = json.loads(script.string)
                if isinstance(parsed, dict) and parsed.get("@type") == "Product":
                    product_obj = parsed
                    break
                elif isinstance(parsed, dict) and "@graph" in parsed:
                    for node in parsed["@graph"]:
                        if node.get("@type") == "Product":
                            product_obj = node
                            break
            except Exception:
                continue

        if not product_obj:
            return data

        # Fill missing values
        if not data.get("pdp_title_value"):
            data["pdp_title_value"] = product_obj.get("name", "")

        offers = product_obj.get("offers", {})
        if isinstance(offers, dict):
            if not data.get("price_sp"):
                data["price_sp"] = float(offers.get("price") or 0.0)
            mrp = 0.0
            price_specs = offers.get('priceSpecification', [])
            if isinstance(price_specs, list):
                for spec in price_specs:
                    if spec.get('name') == 'MRP':
                        mrp = spec.get('price', "")
                        break
            data["price_rp"] = float(mrp)
            data["pdp_discount_value"] = float(data["price_rp"]) - float(data["price_sp"])
            availability = str(offers.get("availability", ""))
            if "InStock" in availability:
                data["osa"] = 1
                data["osa_remark"] = "INSTOCK"
            elif "OutOfStock" in availability:
                data["osa"] = 0
                data["osa_remark"] = "OOS"

            seller = offers.get("seller", {})
            if isinstance(seller, dict) and not data.get("reseller_name_crawl"):
                data["reseller_name_crawl"] = seller.get("name", "")

        # Ratings
        aggregate_rating = product_obj.get("aggregateRating", {})
        if isinstance(aggregate_rating, dict):
            data["pdp_rating_value"] = float(aggregate_rating.get("ratingValue") or 0.0)
            data["pdp_rating_count"] = int(aggregate_rating.get("ratingCount") or 0)
            data["pdp_review_count"] = int(aggregate_rating.get("reviewCount") or 0)

        # Fallback image
        if not data.get("pdp_image_url"):
            images = product_obj.get("image", [])
            if isinstance(images, list) and images:
                data["pdp_image_url"] = images[0]
                data["pdp_image_url_all"] = ",".join(images)
                data["pdp_image_count"] = len(images)
            elif isinstance(images, str):
                data["pdp_image_url"] = images
                data["pdp_image_url_all"] = images
                data["pdp_image_count"] = 1

        return data

    def _build_record_dict(self, parsed: dict) -> dict:
        return {
            "pf_id": self.pf_id,
            "crawl_id": self.crawl_id,
            "sku_id": self.sku_id,
            "web_pid": self.web_pid,
            "pdp_title_value": parsed.get("pdp_title_value", ""),
            "brand_id": self.brand_id,
            "brand_name": self.brand_name,
            "price_rp": parsed.get("price_rp", 0.0),
            "price_sp": parsed.get("price_sp", 0.0),
            "pdp_rating_value": parsed.get("pdp_rating_value", 0.0),
            "pdp_review_count": parsed.get("pdp_review_count", 0),
            "pdp_rating_count": parsed.get("pdp_rating_count", 0),
            "pdp_image_count": parsed.get("pdp_image_count", 0),
            "pdp_image_url": parsed.get("pdp_image_url", ""),
            "pdp_image_url_all": parsed.get("pdp_image_url_all", ""),
            "pdp_qa_count": 0,
            "pdp_desc_value": parsed.get("pdp_desc_value", ""),
            "reseller_name_crawl": parsed.get("reseller_name_crawl", ""),
            "osa": parsed.get("osa", 0),
            "osa_remark": parsed.get("osa_remark", "OOS"),
            "pdp_page_url": self.pdp_page_url,
            "pdp_discount_value": parsed.get("pdp_discount_value", 0.0),
            "location_id": self.location_id,
            "location_name": self.location,
            "pincode": self.pincode,
            "created_by": "System",
            "created_on": self.current_time,
            "status": 1,
        }

    def _insert_into_db(self, record: dict):
        if not self.cursor or not self.connection:
            self.logger.error("Skipping DB insert: active database connection not found.")
            return

        cols = "`" + "`, `".join(self.OUTPUT_COLS) + "`"
        placeholders = ", ".join(["%s"] * len(self.OUTPUT_COLS))
        query = f"INSERT INTO `pharmeasy_crawl_pdp` ({cols}) VALUES ({placeholders})"

        values = tuple(record.get(col, "") for col in self.OUTPUT_COLS)

        try:
            self.cursor.execute(query, values)
            self.connection.commit()
            self.logger.info("Successfully inserted record for web_pid: %s", self.web_pid)
        except Exception as err:
            self.logger.error("MySQL Insert error: %s", str(err))

    def closed(self, reason):
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass