from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9]+", text.lower()) if token}


@dataclass(frozen=True)
class FAQEntry:
    intent: str
    source_id: str
    source_label: str
    policy_version: str
    answer: str


@dataclass(frozen=True)
class FAQChunk:
    chunk_id: str
    intent: str
    source_id: str
    source_label: str
    policy_version: str
    text: str


class FAQRepository:
    def __init__(self, faq_chunks_path: str | Path | None = None) -> None:
        self._chunks = self._load_chunks(faq_chunks_path)

    @staticmethod
    def _backend_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _resolve_chunks_path(self, faq_chunks_path: str | Path | None) -> Path:
        if faq_chunks_path is None:
            return self._backend_root() / "data" / "faq_chunks.json"

        resolved = Path(faq_chunks_path)
        if resolved.is_absolute():
            return resolved

        backend_root = self._backend_root()
        repo_root = backend_root.parent
        candidates = [backend_root / resolved, repo_root / resolved]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _load_chunks(self, faq_chunks_path: str | Path | None) -> list[FAQChunk]:
        chunks_path = self._resolve_chunks_path(faq_chunks_path)
        if not chunks_path.exists():
            raise FileNotFoundError(f"FAQ chunks file not found: {chunks_path}")

        raw = json.loads(chunks_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("FAQ chunks file must contain a list")

        chunks: list[FAQChunk] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(f"FAQ chunk at index {index} must be an object")
            chunks.append(
                FAQChunk(
                    chunk_id=str(item["chunk_id"]),
                    intent=str(item["intent"]),
                    source_id=str(item["source_id"]),
                    source_label=str(item["source_label"]),
                    policy_version=str(item["policy_version"]),
                    text=str(item["text"]),
                )
            )

        return chunks

    def retrieve_chunks(self, *, intent: str, query_text: str, top_k: int = 3) -> list[tuple[FAQChunk, float]]:
        query_tokens = _tokenize(query_text)
        candidates = [chunk for chunk in self._chunks if chunk.intent == intent]
        if not candidates:
            candidates = self._chunks

        scored: list[tuple[FAQChunk, float]] = []
        for chunk in candidates:
            chunk_tokens = _tokenize(chunk.text)
            if not chunk_tokens:
                continue

            overlap = len(query_tokens & chunk_tokens)
            lexical_score = overlap / max(1, len(query_tokens))
            intent_bonus = 0.45 if chunk.intent == intent else 0.2
            score = min(intent_bonus + lexical_score, 0.99)
            scored.append((chunk, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def find_best_match(self, *, intent: str, query_text: str) -> tuple[FAQEntry, float] | None:
        retrieved = self.retrieve_chunks(intent=intent, query_text=query_text, top_k=3)
        if not retrieved:
            return None

        top_chunk, top_score = retrieved[0]
        answer = " ".join(chunk.text for chunk, _ in retrieved)
        entry = FAQEntry(
            intent=top_chunk.intent,
            source_id=top_chunk.source_id,
            source_label=top_chunk.source_label,
            policy_version=top_chunk.policy_version,
            answer=answer,
        )
        return entry, top_score
