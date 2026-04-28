# models.py
from pydantic import BaseModel
from typing import List, Optional

class OllamaModel(BaseModel):
    name: str
    description: Optional[str] = None
    tags: List[str] = []
    sizes: List[str] = []
    pulls: Optional[int] = None
    updated: Optional[str] = None
