import logging
from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)

class FreshersworldScraper(BaseScraper):
    source_name = "freshersworld"
    base_url = "https://www.freshersworld.com/internships"

    def scrape(self) -> list[dict]:
        listings = []
        urls = [
            "https://www.freshersworld.com/internships/jobtype-Summer_Internship",
            "https://www.freshersworld.com/jobs/freshers-jobs-for-btech-computer-science",
            "https://www.freshersworld.com/internships/jobtype-Industrial_Training",
        ]
        for url in urls:
            try:
                soup = self.fetch_page(url)
                if not soup:
                    continue
                cards = (
                    soup.select("div.job-container") or
                    soup.select(".job_listing") or
                    soup.select("[class*='job-box']") or
                    soup.select("li.job-list-item")
                )
                for card in cards[:25]:
                    try:
                        title = (
                            card.select_one("a.job-title") or
                            card.select_one("h3 a") or
                            card.select_one("[class*='title'] a") or
                            card.select_one("a[href*='/jobs/']")
                        )
                        company = (
                            card.select_one("span.company-name") or
                            card.select_one("[class*='company']") or
                            card.select_one("span.org")
                        )
                        location = (
                            card.select_one("span.location") or
                            card.select_one("[class*='location']")
                        )
                        if not title:
                            continue
                        href = title.get("href") if title else None
                        full_url = f"https://www.freshersworld.com{href}" if href and href.startswith("/") else href or url
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
