import logging
from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)

class ShineScraper(BaseScraper):
    source_name = "shine"
    base_url = "https://www.shine.com/job-search/internship-jobs"

    def scrape(self) -> list[dict]:
        listings = []
        urls = [
            "https://www.shine.com/job-search/internship-jobs",
            "https://www.shine.com/job-search/python-internship-jobs",
            "https://www.shine.com/job-search/web-developer-internship-jobs",
            "https://www.shine.com/job-search/data-science-internship-jobs",
        ]
        for url in urls:
            try:
                soup = self.fetch_page(url)
                if not soup:
                    continue
                cards = (
                    soup.select("div.jobCard") or
                    soup.select("[class*='job-card']") or
                    soup.select("[class*='jobCard']") or
                    soup.select("article[class*='job']") or
                    soup.select("div[class*='listing']")
                )
                for card in cards[:25]:
                    try:
                        title = (
                            card.select_one("a.jobTitle") or
                            card.select_one("[class*='title'] a") or
                            card.select_one("h2 a") or
                            card.select_one("h3 a")
                        )
                        company = (
                            card.select_one("[class*='company']") or
                            card.select_one("[class*='employer']") or
                            card.select_one("span.company")
                        )
                        location = (
                            card.select_one("[class*='location']") or
                            card.select_one("span.location")
                        )
                        salary = card.select_one("[class*='salary']") or card.select_one("[class*='ctc']")
                        if not title:
                            continue
                        href = title.get("href") if title else None
                        full_url = f"https://www.shine.com{href}" if href and href.startswith("/") else href or url
                        listings.append({
                            "title": title.get_text(strip=True),
                            "company": company.get_text(strip=True) if company else "Company",
                            "location": location.get_text(strip=True) if location else "India",
                            "description": card.get_text(" ", strip=True)[:500],
                            "application_url": full_url,
                            "posted_date": None,
                            "salary_range": salary.get_text(strip=True) if salary else None,
                            "source": self.source_name,
                        })
                    except Exception:
                        continue
                self.respect_rate_limit()
            except Exception as exc:
                logger.error("scraper_error source=%s error=%s", self.source_name, type(exc).__name__)
        return listings
