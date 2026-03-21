import logging

from app.scraper.orchestrator import ScraperOrchestrator

logger = logging.getLogger(__name__)


def main():
    logger.info("Scraper cron job started")
    orchestrator = ScraperOrchestrator()
    results = orchestrator.scrape_all()
    logger.info(
        "Scraper complete: %s inserted, %s updated, %s failed",
        results.get("inserted"),
        results.get("updated"),
        results.get("failed"),
    )


if __name__ == "__main__":
    main()
