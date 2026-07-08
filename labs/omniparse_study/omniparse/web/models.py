"""
Title: OmniParse
Author: Adithya S K
Date: 2024-07-02

This code includes portions of code from the crawl4ai repository by unclecode, licensed under the Apache 2.0 License.
Original repository: https://github.com/unclecode/crawl4ai

Original Author: unclecode

License: Apache 2.0 License
URL: https://github.com/unclecode/crawl4ai/blob/main/LICENSE
"""


from pydantic import BaseModel, HttpUrl


class UrlModel(BaseModel):
    url: HttpUrl
    forced: bool = False


class CrawlResult(BaseModel):
    url: str
    html: str
    success: bool
    cleaned_html: str | None = None
    media: dict[str, list[dict]] = {}
    links: dict[str, list[dict]] = {}
    screenshot: str | None = None
    markdown: str | None = None
    extracted_content: str | None = None
    metadata: dict | None = None
    error_message: str | None = None
