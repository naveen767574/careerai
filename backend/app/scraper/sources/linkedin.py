import logging
from datetime import date

from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    source_name = "linkedin"
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def scrape(self) -> list[dict]:
        listings: list[dict] = []
        try:
            start = 0
            while len(listings) < 50:
                params = {"keywords": "internship", "location": "India", "start": start}
                soup = self.fetch_page(self.base_url, params=params)
                if not soup:
                    break
                cards = soup.select(".base-card")
                if not cards:
                    break
                for card in cards:
                    title = (card.select_one(".base-search-card__title") or {}).get_text(strip=True)
                    company = (card.select_one(".base-search-card__subtitle") or {}).get_text(strip=True)
                    location = (card.select_one(".job-search-card__location") or {}).get_text(strip=True)
                    url = (card.select_one("a.base-card__full-link") or {}).get("href")
                    description = card.get_text(" ", strip=True)
                    if not (title and company and location and url):
                        continue
                    listings.append(
                        {
                            "title": title,
                            "company": company,
                            "location": location,
                            "description": description,
                            "application_url": url,
                            "posted_date": None,
                            "salary_range": None,
                            "source": self.source_name,
                        }
                    )
                    if len(listings) >= 50:
                        break
                start += 25
                self.respect_rate_limit()
        except Exception as exc:
            logger.error("scraper_error source=%s url=%s error=%s", self.source_name, self.base_url, type(exc).__name__)
            return []
        return listings
