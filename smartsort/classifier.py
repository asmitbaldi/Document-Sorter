"""Filename routing and pluggable AI classification providers."""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import VALID_DESTINATIONS
from .extractor import ExtractionResult


@dataclass(frozen=True)
class Classification:
    destination: str
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        if self.destination not in VALID_DESTINATIONS:
            raise ValueError(f"Model returned unsupported destination: {self.destination!r}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


class BaseClassifier(ABC):
    """Interface implemented by AI-backed classifiers."""

    @abstractmethod
    def classify(self, document: ExtractionResult) -> Classification:
        """Return a validated classification for one extracted document."""


class FilenameRouter:
    """Conservative, deterministic routing for unambiguous course keywords."""

    KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("ML", ("machine learning", "deep learning", "scikit", "sklearn", "tensorflow", "pytorch", "kaggle", "campusx", "hands-on machine", "hands on machine", "regression", "classification", "dataset", "neural network")),
        ("IVP", ("image processing", "video processing", "image and video", "computer vision")),
        ("OS", ("operating system", "operating systems", "os unit", "process scheduling", "deadlock", "paging", "virtual memory")),
        ("SWE", ("software engineering", "software design", "uml", "requirements engineering", "agile", "scrum")),
        ("SET", ("sustainable energy", "renewable energy", "solar energy", "wind energy", "energy technology")),
        ("MAD", ("mobile app development", "android development", "ios development", "flutter", "react native", "android studio", "kotlin", "swiftui")),
        ("LTLS", ("learning through life skills", "life skills", "soft skills", "ltls", "self awareness", "self-awareness", "emotional intelligence", "interpersonal skills", "communication skills", "time management", "stress management", "conflict resolution", "problem solving", "decision making", "teamwork", "leadership skills", "personal development", "resilience")),
        ("AI", ("artificial intelligence", "ai unit", "intelligent agents", "knowledge representation")),
    )

    def route(self, path: Path) -> Classification | None:
        normalized = path.stem.lower().replace("_", " ").replace("-", " ")
        for destination, keywords in self.KEYWORDS:
            if any(keyword in normalized for keyword in keywords):
                return Classification(destination, 1.0, f"Filename matched {destination} keyword")
        return None


class GeminiClassifier(BaseClassifier):
    """Google Gemini implementation using structured JSON output."""

    RESPONSE_SCHEMA: dict[str, Any] = {
        "type": "object",
        "properties": {
            "destination": {"type": "string", "enum": sorted(VALID_DESTINATIONS)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["destination", "confidence", "reason"],
    }

    def __init__(self, model: str, retries: int = 3) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Set it before running DocumentSorter.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Google GenAI SDK is unavailable. Run: pip install -r requirements.txt") from exc
        self._client = genai.Client(api_key=api_key)
        self._types, self._model, self._retries = types, model, retries

    def classify(self, document: ExtractionResult) -> Classification:
        prompt = self._build_prompt(document)
        last_error: Exception | None = None
        for attempt in range(self._retries):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=self._types.GenerateContentConfig(
                        response_mime_type="application/json", response_schema=self.RESPONSE_SCHEMA, temperature=0,
                    ),
                )
                payload = json.loads(response.text)
                return Classification(str(payload["destination"]), float(payload["confidence"]), str(payload["reason"]).strip()[:500])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Gemini returned invalid structured output: {exc}") from exc
            except Exception as exc:
                last_error = exc
                if attempt < self._retries - 1:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Gemini request failed after {self._retries} attempts: {last_error}") from last_error

    @staticmethod
    def _build_prompt(document: ExtractionResult) -> str:
        metadata = json.dumps(document.metadata, ensure_ascii=False)
        return f'''You are a document classifier.

Return ONLY valid JSON.

Possible destinations:
ML
AI
OS
IVP
SWE
SET
MAD
LTLS
Other
Downloads

Definitions:
ML: Machine learning, AI books, deep learning, Python ML, scikit-learn, TensorFlow, PyTorch, regression, classification, Kaggle, datasets, notebooks, CampusX material, Hands-On Machine Learning, research papers.
AI: Artificial Intelligence course material.
OS: Operating Systems.
IVP: Image and Video Processing.
SWE: Software Engineering.
SET: Sustainable Energy Technology.
MAD: Mobile App Development.
LTLS: Learning Through Life Skills, including communication, self-awareness, emotional intelligence, interpersonal skills, teamwork, leadership, time management, stress management, conflict resolution, problem solving, decision making, personal development, and resilience.
Other: Semester V material that doesn't belong to the above.
Downloads: Anything personal or unrelated.

Input:
Filename:
{document.filename}

Metadata:
{metadata}

Extracted Text:
{document.text}

Return ONLY:
{{"destination":"...","confidence":0.95,"reason":"..."}}'''
