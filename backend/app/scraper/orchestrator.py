import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.resume import Resume
from app.scraper.sources.unstop import UnstopScraper
from app.scraper.sources.shine import ShineScraper
from app.scraper.sources.internshala import IntershalaScraper
from app.scraper.sources.linkedin import LinkedInScraper
from app.scraper.utils.deduplicator import Deduplicator
from app.scraper.utils.extractor import DescriptionExtractor
from app.services.recommendation_engine import RecommendationEngine
from app.services.skill_extractor import SKILL_KEYWORDS

logger = logging.getLogger(__name__)


class ScraperOrchestrator:
    def __init__(self) -> None:
        self.deduplicator = Deduplicator()
        self.description_extractor = DescriptionExtractor()

    def scrape_all(self) -> dict:
        sources = [
            LinkedInScraper(),
            IntershalaScraper(),
            UnstopScraper(),
            ShineScraper(),
        ]
        results = {"inserted": 0, "updated": 0, "failed": 0, "sources": {}}
        listings_by_source: dict[str, list[dict]] = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {executor.submit(scraper.scrape): scraper for scraper in sources}
            for future in as_completed(future_map):
                scraper = future_map[future]
                try:
                    listings = future.result() or []
                except Exception as exc:
                    logger.error(
                        "scraper_error source=%s url=%s error=%s timestamp=%s",
                        scraper.source_name,
                        getattr(scraper, "base_url", ""),
                        type(exc).__name__,
                        datetime.utcnow().isoformat(),
                    )
                    results["failed"] += 1
                    listings = []
                listings_by_source[scraper.source_name] = listings
                results["sources"][scraper.source_name] = len(listings)

        db = SessionLocal()
        try:
            for source, listings in listings_by_source.items():
                for listing in listings:
                    try:
                        status = self.process_listing(listing, db)
                        if status == "inserted":
                            results["inserted"] += 1
                        elif status == "updated":
                            results["updated"] += 1
                    except Exception as exc:
                        logger.error(
                            "scraper_error source=%s url=%s error=%s timestamp=%s",
                            source,
                            listing.get("application_url"),
                            type(exc).__name__,
                            datetime.utcnow().isoformat(),
                        )
                        results["failed"] += 1

            try:
                users_with_resumes = db.query(Resume.user_id).filter(Resume.analyzed == True).all()
            except Exception:
                users_with_resumes = db.query(Resume.user_id).all()

            for (user_id,) in users_with_resumes:
                try:
                    engine = RecommendationEngine(db)
                    engine.refresh_for_user(user_id)
                    logger.info("Refreshed recommendations for user %s", user_id)
                except Exception as exc:
                    logger.error("Failed to refresh recommendations for user %s: %s", user_id, exc)
                    continue

            return results
        finally:
            db.close()

    def process_listing(self, listing: dict, db) -> str:
        hash_value = self.deduplicator.generate_hash(
            listing.get("title", ""),
            listing.get("company", ""),
            listing.get("location", ""),
        )
        existing = self.deduplicator.is_duplicate(hash_value, db)
        if existing:
            existing.description = listing.get("description") or existing.description
            existing.application_url = listing.get("application_url") or existing.application_url
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            db.add(existing)
            db.commit()
            self._upsert_skills(existing.id, listing.get("description", ""), db)
            return "updated"

        internship = Internship(
            title=listing.get("title"),
            company=listing.get("company"),
            location=listing.get("location"),
            description=listing.get("description"),
            application_url=listing.get("application_url"),
            source=listing.get("source"),
            posted_date=listing.get("posted_date"),
            salary_range=listing.get("salary_range"),
            duplicate_hash=hash_value,
        )
        db.add(internship)
        db.commit()
        db.refresh(internship)
        self._upsert_skills(internship.id, listing.get("description", ""), db)
        # Auto-embed new internship for semantic search and matching
        try:
            from app.services.embedding_service import embed_internship
            import sqlalchemy
            vector = embed_internship(
                title=internship.title or '',
                company=internship.company or '',
                description=internship.description or '',
                location=internship.location or '',
            )
            db.execute(
                sqlalchemy.text("UPDATE internships SET embedding = :vec WHERE id = :id"),
                {"vec": str(vector), "id": internship.id}
            )
            db.commit()
        except Exception as e:
            logger.error(f"Embedding failed for internship {internship.id}: {e}")
        return "inserted"

    def extract_skills_from_description(self, description: str) -> list[str]:
        description_lower = description.lower()
        return sorted({skill for skill in SKILL_KEYWORDS if skill in description_lower})

    def _upsert_skills(self, internship_id: int, description: str, db) -> None:
        db.query(InternshipSkill).filter(InternshipSkill.internship_id == internship_id).delete()
        skills = self.description_extractor.extract_skills(description)
        for skill in skills:
            db.add(InternshipSkill(internship_id=internship_id, skill_name=skill))
        db.commit()

