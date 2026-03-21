from io import BytesIO

from PyPDF2 import PdfReader
from docx import Document


class TextExtractor:
    @staticmethod
    def extract_text(file_bytes: bytes, file_type: str) -> str:
        if file_type == "pdf":
            return TextExtractor._extract_pdf(file_bytes)
        if file_type == "docx":
            return TextExtractor._extract_docx(file_bytes)
        raise ValueError("Unsupported file type")

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError("Corrupted PDF file") from exc

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> str:
        try:
            doc = Document(BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except Exception as exc:
            raise ValueError("Corrupted DOCX file") from exc
