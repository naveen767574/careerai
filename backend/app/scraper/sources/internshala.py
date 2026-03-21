import logging
from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)

class IntershalaScraper(BaseScraper):
    source_name = "internshala"
    base_url = "https://internshala.com/internships/keywords-python,java,web-development,data-science,machine-learning"

    def scrape(self) -> list[dict]:
        listings = []
        try:
            soup = self.fetch_page(self.base_url)
            if not soup:
                return []
            cards = soup.select(".individual_internship")
            for card in cards[:50]:
                try:
                    title = card.select_one(".job-internship-name")
                    company = card.select_one(".company-name")
                    location = card.select_one(".location_link") or card.select_one(".locations")
                    stipend = card.select_one(".stipend_status")
                    link = card.select_one("a.view_detail_button") or card.select_one("a[href*='/internship/']")
                    if not title or not company:
                        continue
                    url = None
                    if link and link.get("href"):
                        href = link.get("href")
                        url = f"https://internshala.com{href}" if href.startswith("/") else href
                    listings.append({
                        "title": title.get_text(strip=True),
                        "company": company.get_text(strip=True),
                        "location": location.get_text(strip=True) if location else "India",
                        "description": card.get_text(" ", strip=True)[:500],
                        "application_url": url or self.base_url,
                        "posted_date": None,
                        "salary_range": stipend.get_text(strip=True) if stipend else None,
                        "source": self.source_name,
                    })
                except Exception:
                    continue
            self.respect_rate_limit()
        except Exception as exc:
            logger.error("scraper_error source=%s error=%s", self.source_name, type(exc).__name__)
        return listings
