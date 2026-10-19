"""Existing OCR output contract, without the Cloud Vision API client."""
from pydantic import BaseModel, Field

class Vertex(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)

class TextRegion(BaseModel):
    text: str
    position: list[Vertex] = Field(min_length=2)

class OCRResult(BaseModel):
    regions: list[TextRegion]
