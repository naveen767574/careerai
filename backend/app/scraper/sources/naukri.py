import logging
from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)

class NaukriScraper(BaseScraper):
    source_name = "naukri"
    base_url = "https://www.naukri.com/internship-jobs"

    def scrape(self) -> list[dict]:
        listings = []
        urls = [
            "https://www.naukri.com/internship-jobs",
            "https://www.naukri.com/python-internship-jobs",
            "https://www.naukri.com/web-developer-internship-jobs",
            "https://www.naukri.com/data-science-internship-jobs",
        ]
        for url in urls:
            try:
                soup = self.fetch_page(url)
                if not soup:
                    continue
                cards = soup.select("article.jobTuple") or soup.select(".job-container") or soup.select("[class*='jobTuple']")
                for card in cards[:20]:
                    try:
                        title = card.select_one("a.title") or card.select_one("[class*='title']")
                        company = card.select_one("a.subTitle") or card.select_one("[class*='companyInfo']")
                        location = card.select_one("li.location") or card.select_one("[class*='location']")
                        salary = card.select_one("li.salary") or card.select_one("[class*='salary']")
                        if not title:
                            continue
                        link = title.get("href") or (card.select_one("a") or {}).get("href")
                        listings.append({
                            "title": title.get_text(strip=True),
                            "company": company.get_text(strip=True) if company else "Company",
                            "location": location.get_text(strip=True) if location else "India",
                            "description": card.get_text(" ", strip=True)[:500],
                            "application_url": link or url,
                            "posted_date": None,
                            "salary_range": salary.get_text(strip=True) if salary else None,
                            "source": self.source_name,
                        })
                    except Exception:
                        continue
                self.respect_rate_limit()
            except Exception as exc:
                logger.error("scraper_error source=%s url=%s error=%s", self.source_name, url, type(exc).__name__)
        return listings
