#!/usr/bin/env python3
"""Run FAQ retrieval evaluation with optional retrieval tuning and RAGAS metrics."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from app.repositories.faq_repository import FAQChunk
from app.repositories.faq_repository import FAQRepository
from dotenv import load_dotenv


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int
    min_chunk_score: float
    relative_score_floor: float
    max_context_chunks: int


class RAGASEvaluator:
    def __init__(self, *, dataset_path: Path, faq_chunks_path: Path) -> None:
        self.dataset = self._load_dataset(dataset_path)
        self.repository = FAQRepository(faq_chunks_path=faq_chunks_path)

    @staticmethod
    def _load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("test_cases"), list):
            return payload["test_cases"]
        raise ValueError("Evaluation dataset must be a list or {'test_cases': [...]} payload")

    @staticmethod
    def _select_chunks(
        retrieved: list[tuple[FAQChunk, float]],
        *,
        min_chunk_score: float,
        relative_score_floor: float,
        max_context_chunks: int,
    ) -> list[tuple[FAQChunk, float]]:
        if not retrieved:
            return []

        top_score = retrieved[0][1]
        relative_floor = top_score * relative_score_floor
        selected: list[tuple[FAQChunk, float]] = []

        for chunk, score in retrieved:
            if score < min_chunk_score:
                continue
            if top_score > 0 and score < relative_floor:
                continue
            selected.append((chunk, score))
            if len(selected) >= max_context_chunks:
                break

        if selected:
            return selected
        return [retrieved[0]]

    def evaluate_retrieval(self, config: RetrievalConfig) -> dict[str, float]:
        precision_scores: list[float] = []
        recall_scores: list[float] = []
        top1_scores: list[float] = []

        for case in self.dataset:
            question = str(case.get("question", ""))
            intent = str(case.get("intent", "general_support"))
            expected = set(case.get("expected_chunk_ids", []))

            retrieved = self.repository.retrieve_chunks(intent=intent, query_text=question, top_k=config.top_k)
            selected = self._select_chunks(
                retrieved,
                min_chunk_score=config.min_chunk_score,
                relative_score_floor=config.relative_score_floor,
                max_context_chunks=config.max_context_chunks,
            )
            retrieved_ids = [chunk.chunk_id for chunk, _ in selected]
            retrieved_set = set(retrieved_ids)

            overlap = len(retrieved_set & expected)
            precision_scores.append(overlap / len(retrieved_set) if retrieved_set else 0.0)
            recall_scores.append(overlap / len(expected) if expected else 1.0)
            top1_scores.append(1.0 if retrieved_ids and retrieved_ids[0] in expected else 0.0)

        return {
            "context_precision": mean(precision_scores) if precision_scores else 0.0,
            "context_recall": mean(recall_scores) if recall_scores else 0.0,
            "top_1_accuracy": mean(top1_scores) if top1_scores else 0.0,
        }

    def tune_retrieval(self) -> tuple[RetrievalConfig, dict[str, float]]:
        top_k_values = [3, 5, 8, 10]
        min_score_values = [0.0, 0.1, 0.15]
        relative_floor_values = [0.0, 0.5, 0.6, 0.7]

        best_config = RetrievalConfig(top_k=5, min_chunk_score=0.1, relative_score_floor=0.6, max_context_chunks=5)
        best_metrics = self.evaluate_retrieval(best_config)
        best_objective = self._objective(best_metrics)

        for top_k in top_k_values:
            for min_score in min_score_values:
                for relative_floor in relative_floor_values:
                    config = RetrievalConfig(
                        top_k=top_k,
                        min_chunk_score=min_score,
                        relative_score_floor=relative_floor,
                        max_context_chunks=min(5, top_k),
                    )
                    metrics = self.evaluate_retrieval(config)
                    objective = self._objective(metrics)
                    if objective > best_objective:
                        best_config = config
                        best_metrics = metrics
                        best_objective = objective

        return best_config, best_metrics

    @staticmethod
    def _objective(metrics: dict[str, float]) -> float:
        # Prioritize top-1 relevance, then precision, then recall.
        return (
            metrics["top_1_accuracy"] * 0.50
            + metrics["context_precision"] * 0.30
            + metrics["context_recall"] * 0.20
        )

    def build_ragas_rows(self, config: RetrievalConfig) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for case in self.dataset:
            question = str(case.get("question", ""))
            intent = str(case.get("intent", "general_support"))

            retrieved = self.repository.retrieve_chunks(intent=intent, query_text=question, top_k=config.top_k)
            selected = self._select_chunks(
                retrieved,
                min_chunk_score=config.min_chunk_score,
                relative_score_floor=config.relative_score_floor,
                max_context_chunks=config.max_context_chunks,
            )

            contexts = [chunk.text for chunk, _ in selected]
            answer = contexts[0] if contexts else "I could not find a reliable answer right now."
            ground_truth = str(case.get("ground_truth", ""))
            row = {
                "user_input": question,
                "response": answer,
                "retrieved_contexts": contexts,
                "reference": ground_truth,
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": ground_truth,
            }
            rows.append(row)

        return rows


def run_ragas(rows: list[dict[str, Any]]) -> dict[str, float]:
    try:
        from datasets import Dataset
        from langchain_openai import ChatOpenAI
        from langchain_openai import OpenAIEmbeddings
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import AnswerRelevancy
        from ragas.metrics import ContextPrecision
        from ragas.metrics import ContextRecall
        from ragas.metrics import Faithfulness
    except ImportError as exc:
        print("RAGAS dependencies are missing. Install with: pip install -e '.[ragas]'")
        raise SystemExit(1) from exc

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required for semantic RAGAS metrics.")
        raise SystemExit(1)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    embedding_model = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small")

    dataset = Dataset.from_list(rows)
    llm = LangchainLLMWrapper(ChatOpenAI(model=model_name, temperature=0.0))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=embedding_model))
    metrics = [ContextPrecision(), ContextRecall(), Faithfulness(), AnswerRelevancy()]

    result = evaluate(
        dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
    )

    if hasattr(result, "to_pandas"):
        frame = result.to_pandas()
        return {
            "context_precision": float(frame["context_precision"].mean()),
            "context_recall": float(frame["context_recall"].mean()),
            "faithfulness": float(frame["faithfulness"].mean()),
            "answer_relevancy": float(frame["answer_relevancy"].mean()),
        }

    if isinstance(result, dict):
        return {
            "context_precision": float(result.get("context_precision", 0.0)),
            "context_recall": float(result.get("context_recall", 0.0)),
            "faithfulness": float(result.get("faithfulness", 0.0)),
            "answer_relevancy": float(result.get("answer_relevancy", 0.0)),
        }

    print("Unsupported RAGAS result format.")
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate FAQ retrieval with RAGAS")
    parser.add_argument("--top-k", type=int, default=10, help="Retriever top-k")
    parser.add_argument("--min-chunk-score", type=float, default=0.1, help="Minimum chunk score")
    parser.add_argument("--relative-score-floor", type=float, default=0.6, help="Relative score floor")
    parser.add_argument("--max-context-chunks", type=int, default=5, help="Max selected chunks")
    parser.add_argument("--tune", action="store_true", help="Tune retrieval config before RAGAS evaluation")
    return parser.parse_args()


def print_retrieval_metrics(metrics: dict[str, float]) -> None:
    print("\nRetrieval Metrics (dataset labels)")
    print(f"  Context Precision: {metrics['context_precision']:.2%}")
    print(f"  Context Recall:    {metrics['context_recall']:.2%}")
    print(f"  Top-1 Accuracy:    {metrics['top_1_accuracy']:.2%}")


def main() -> None:
    args = parse_args()

    backend_dir = Path(__file__).resolve().parent.parent
    load_dotenv(backend_dir / ".env")
    dataset_path = backend_dir / "data" / "evaluation_dataset.json"
    faq_chunks_path = backend_dir / "data" / "faq_chunks.json"

    if not dataset_path.exists() or not faq_chunks_path.exists():
        print("Missing evaluation files in backend/data")
        raise SystemExit(1)

    evaluator = RAGASEvaluator(dataset_path=dataset_path, faq_chunks_path=faq_chunks_path)

    config = RetrievalConfig(
        top_k=args.top_k,
        min_chunk_score=args.min_chunk_score,
        relative_score_floor=args.relative_score_floor,
        max_context_chunks=args.max_context_chunks,
    )

    if args.tune:
        tuned_config, tuned_metrics = evaluator.tune_retrieval()
        config = tuned_config
        print("\nTuned retrieval configuration")
        print(f"  top_k={config.top_k}")
        print(f"  min_chunk_score={config.min_chunk_score}")
        print(f"  relative_score_floor={config.relative_score_floor}")
        print(f"  max_context_chunks={config.max_context_chunks}")
        print_retrieval_metrics(tuned_metrics)
    else:
        base_metrics = evaluator.evaluate_retrieval(config)
        print("\nUsing provided retrieval configuration")
        print(f"  top_k={config.top_k}")
        print(f"  min_chunk_score={config.min_chunk_score}")
        print(f"  relative_score_floor={config.relative_score_floor}")
        print(f"  max_context_chunks={config.max_context_chunks}")
        print_retrieval_metrics(base_metrics)

    rows = evaluator.build_ragas_rows(config)
    ragas_metrics = run_ragas(rows)

    print("\nRAGAS Metrics (semantic)")
    print(f"  Context Precision: {ragas_metrics['context_precision']:.4f}")
    print(f"  Context Recall:    {ragas_metrics['context_recall']:.4f}")
    print(f"  Faithfulness:      {ragas_metrics['faithfulness']:.4f}")
    print(f"  Answer Relevancy:  {ragas_metrics['answer_relevancy']:.4f}")


if __name__ == "__main__":
    main()
