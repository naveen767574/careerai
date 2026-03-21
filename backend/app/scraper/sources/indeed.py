import logging
from app.scraper.sources.base import BaseScraper

logger = logging.getLogger(__name__)

class IndeedScraper(BaseScraper):
    source_name = "indeed"
    base_url = "https://in.indeed.com/jobs"

    def scrape(self) -> list[dict]:
        listings = []
        queries = [
            "https://in.indeed.com/jobs?q=software+intern&l=India",
            "https://in.indeed.com/jobs?q=python+internship&l=India",
            "https://in.indeed.com/jobs?q=web+developer+intern&l=India",
            "https://in.indeed.com/jobs?q=data+science+intern&l=India",
        ]
        for url in queries:
            try:
                soup = self.fetch_page(url)
                if not soup:
                    continue
                cards = soup.select("div.job_seen_beacon") or soup.select(".jobsearch-ResultsList li")
                for card in cards[:15]:
                    try:
                        title = card.select_one("h2.jobTitle span") or card.select_one("[class*='jobTitle']")
                        company = card.select_one("[class*='companyName']") or card.select_one("span.companyName")
                        location = card.select_one("[class*='companyLocation']") or card.select_one("div.companyLocation")
                        link = card.select_one("a[id^='job_']") or card.select_one("a[href*='/rc/clk']")
                        if not title:
                            continue
                        href = link.get("href") if link else None
                        full_url = f"https://in.indeed.com{href}" if href and href.startswith("/") else href or url
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
                logger.error("scraper_error source=%s url=%s error=%s", self.source_name, url, type(exc).__name__)
        return listings
