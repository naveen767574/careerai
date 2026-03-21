from urllib.parse import quote
import requests
from app.config import settings


class SupabaseStorage:

    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip("/")
        self.key = settings.SUPABASE_SERVICE_KEY
        self.bucket = settings.SUPABASE_BUCKET
        self.headers = {
            "Authorization": f"Bearer {self.key}",
            "apikey": self.key,
        }

    def upload(self, key: str, file_obj, content_type: str) -> str:
        """Upload file to Supabase Storage, return public URL."""
        upload_url = f"{self.url}/storage/v1/object/{self.bucket}/{key}"
        file_data = file_obj.read()
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        response = requests.post(upload_url, headers=headers, data=file_data)
        if response.status_code not in (200, 201):
            raise Exception(f"Supabase upload failed: {response.status_code} {response.text}")
        public_url = f"{self.url}/storage/v1/object/public/{self.bucket}/{quote(key)}"
        return public_url

    def delete(self, key: str) -> bool:
        """Delete file from Supabase Storage."""
        delete_url = f"{self.url}/storage/v1/object/{self.bucket}/{key}"
        response = requests.delete(delete_url, headers=self.headers)
        return response.status_code in (200, 204)

    def get_public_url(self, key: str) -> str:
        """Get public URL for a file."""
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{key}"


# Module-level instance
_storage_instance = None


def get_storage() -> SupabaseStorage:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = SupabaseStorage()
    return _storage_instance
