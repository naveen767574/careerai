import logging
from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)

class UnstopScraper(BaseScraper):
    source_name = "unstop"
    base_url = "https://unstop.com/internships"

    def scrape(self) -> list[dict]:
        listings = []
        urls = [
            "https://unstop.com/internships?oppstatus=open",
            "https://unstop.com/internships?domain=technology&oppstatus=open",
            "https://unstop.com/internships?domain=engineering&oppstatus=open",
        ]
        for url in urls:
            try:
                soup = self.fetch_page(url)
                if not soup:
                    continue
                cards = (
                    soup.select("div.opportunity-card") or
                    soup.select("div[class*='card']") or
                    soup.select("div[class*='listing']") or
                    soup.select("app-browse-card") or
                    soup.select("li[class*='item']")
                )
                for card in cards[:25]:
                    try:
                        title = (
                            card.select_one("div.name") or
                            card.select_one("h3") or
                            card.select_one("h2") or
                            card.select_one("[class*='title']")
                        )
                        company = (
                            card.select_one("div.org-name") or
                            card.select_one("[class*='org']") or
                            card.select_one("[class*='company']")
                        )
                        location = (
                            card.select_one("[class*='location']") or
                            card.select_one("div.location")
                        )
                        link = card.select_one("a[href*='/internship']") or card.select_one("a[href*='/o/']") or card.select_one("a")
                        if not title:
                            continue
                        href = link.get("href") if link else None
                        full_url = f"https://unstop.com{href}" if href and href.startswith("/") else href or url
                        listings.append({
                            "title": title.get_text(strip=True),
                            "company": company.get_text(strip=True) if company else "Company",
                            "location": location.get_text(strip=True) if location else "India",
                            "description": card.get_text(" ", strip=True)[:500],
                            "application_url": full_url,
                            "posted_date": None,
                            "salary_range": None,
                            "source": self.source_name,
                        })
                    except Exception:
                        continue
                self.respect_rate_limit()
            except Exception as exc:
                logger.error("scraper_error source=%s error=%s", self.source_name, type(exc).__name__)
        return listings
