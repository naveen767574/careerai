import hashlib

from sqlalchemy import select

from app.models.internship import Internship


class Deduplicator:
    def generate_hash(self, title: str, company: str, location: str) -> str:
        normalized = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def is_duplicate(self, hash_value: str, db) -> Internship | None:
        return db.execute(select(Internship).where(Internship.duplicate_hash == hash_value)).scalar_one_or_none()
