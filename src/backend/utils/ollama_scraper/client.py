# client.py
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed

from .utils import build_url
from .models import OllamaModel


class OllamaScraper:

    def __init__(self, max_pages=5, timeout=30):
        self.max_pages = max_pages
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _fetch_page(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _parse_page(self, html: str) -> list[OllamaModel]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("a[href^='/library/']")
        results: list[OllamaModel] = []

        for card in cards:
            text = card.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if not lines:
                continue

            name = lines[0]
            description = lines[1] if len(lines) > 1 else None

            results.append(
                OllamaModel(
                    name=name,
                    description=description,
                )
            )

        return results

    async def scrape(
        self,
        query=None,
        categories=None,
        order="newest",
    ):
        all_models: list[OllamaModel] = []

        for page_num in range(1, self.max_pages + 1):
            url = build_url(query, categories, order, page_num)
            html = await self._fetch_page(url)

            models = self._parse_page(html)
            if not models:
                break

            all_models.extend(models)

        return all_models