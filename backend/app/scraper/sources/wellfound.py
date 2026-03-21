import logging
from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)

class WellfoundScraper(BaseScraper):
    source_name = "wellfound"
    base_url = "https://wellfound.com/jobs"

    def scrape(self) -> list[dict]:
        listings = []
        urls = [
            "https://wellfound.com/jobs?role=Software+Engineer&jobType=internship",
            "https://wellfound.com/jobs?role=Frontend+Engineer&jobType=internship",
            "https://wellfound.com/jobs?role=Data+Scientist&jobType=internship",
        ]
        for url in urls:
            try:
                soup = self.fetch_page(url)
                if not soup:
                    continue
                cards = soup.select("div[class*='JobListing']") or soup.select("[class*='job-listing']") or soup.select("div[data-test*='job']")
                for card in cards[:20]:
                    try:
                        title = card.select_one("a[class*='title']") or card.select_one("h2") or card.select_one("[class*='title']")
                        company = card.select_one("[class*='company']") or card.select_one("span[class*='name']")
                        location = card.select_one("[class*='location']")
                        link = card.select_one("a[href*='/jobs/']") or card.select_one("a")
                        if not title:
                            continue
                        href = link.get("href") if link else None
                        full_url = f"https://wellfound.com{href}" if href and href.startswith("/") else href or url
                        listings.append({
                            "title": title.get_text(strip=True),
                            "company": company.get_text(strip=True) if company else "Startup",
                            "location": location.get_text(strip=True) if location else "Remote",
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
                logger.error("scraper_error source=%s error=%s", self.source_name, url, type(exc).__name__)
        return listings
