# RAGAS Evaluation Guide

This document explains how to use RAGAS (Retrieval Augmented Generation Assessment) to evaluate your FAQ retrieval system.

## Installation

Install RAGAS and dependencies:

```bash
cd backend
pip install -e ".[ragas]"
```

This installs:
- `ragas>=0.1.0` - RAG evaluation framework
- `datasets>=2.18.0` - Hugging Face Datasets library

## Evaluation Metrics

The RAGAS evaluation framework uses the following metrics for FAQ retrieval:

### 1. **Context Precision**
- Measures the fraction of retrieved contexts that are relevant to the query
- Formula: `(relevant retrieved chunks) / (total retrieved chunks)`
- **Target**: ≥ 0.4 (40% of retrieved chunks should be relevant)

### 2. **Context Recall**
- Measures the fraction of relevant contexts that were actually retrieved
- Formula: `(relevant retrieved chunks) / (all relevant chunks)`
- **Target**: ≥ 0.3 (we should retrieve at least 30% of all relevant chunks)

### 3. **Answer Relevance**
- Measures how relevant the generated answer is to the input query
- Uses question-to-answer similarity scoring
- **Target**: ≥ 0.5 (50% relevance)

### 4. **Faithfulness**
- Measures how faithful the generated answer is to the retrieved contexts
- Checks if answer claims are factually supported by contexts
- **Target**: ≥ 0.4 (40% faithfulness)

## Running Evaluations

Run from `backend/`:

```bash
python scripts/run_ragas_evaluation.py
```

The script now does both:
- Label-based retrieval metrics using your evaluation dataset:
  - Context Precision
  - Context Recall
  - Top-1 Accuracy
- Semantic RAGAS metrics:
  - Context Precision
  - Context Recall
  - Faithfulness
  - Answer Relevancy

### Tune Retrieval Settings Automatically

```bash
python scripts/run_ragas_evaluation.py --tune
```

This runs a grid search over retrieval settings and then evaluates the tuned configuration with RAGAS.

### Evaluate a Specific Configuration

```bash
python scripts/run_ragas_evaluation.py \
  --top-k 8 \
  --min-chunk-score 0.1 \
  --relative-score-floor 0.6 \
  --max-context-chunks 5
```

## Evaluation Dataset

Test cases are stored in `backend/data/evaluation_dataset.json` with structure:

```json
{
  "question": "where can i order food?",
  "intent": "order_placement",
  "expected_chunk_ids": ["order-placement-v1-1", "order-placement-v1-2"],
  "expected_answer_contains": ["order", "place"],
  "ground_truth": "You can place an order through our order placement page."
}
```

- **question**: User query to evaluate
- **intent**: Expected intent classification
- **expected_chunk_ids**: FAQ chunks that should be retrieved
- **expected_answer_contains**: Keywords the answer should include
- **ground_truth**: Ground truth answer for RAGAS evaluation

## Interpreting Results

### Good Results (✓)
- Context Precision ≥ 0.6 (60% of retrieved chunks are relevant)
- Context Recall ≥ 0.5 (50% of relevant chunks retrieved)
- Top-1 Accuracy ≥ 60% (most queries retrieve a relevant top result)
- Answer Relevancy ≥ 0.5
- Faithfulness ≥ 0.4

### Needs Improvement (⚠)
- Context Precision < 0.4 → Too many irrelevant chunks being retrieved
  - Fix: Adjust retrieval scoring in `FAQRepository.retrieve_chunks()`
- Context Recall < 0.3 → Missing relevant chunks
  - Fix: Expand FAQ chunks dataset or adjust intent bonus scoring
- Top-1 Accuracy < 40% → Ranking is poor
  - Fix: Tune lexical scoring weights or add semantic scoring

## Adding New Test Cases

To evaluate new query patterns:

1. Add entry to `backend/data/evaluation_dataset.json`:
```json
{
  "question": "your new question",
  "intent": "intent_name",
  "expected_chunk_ids": ["chunk-id-1", "chunk-id-2"],
  "expected_answer_contains": ["keyword1", "keyword2"],
  "ground_truth": "Expected answer text"
}
```

2. Re-run evaluation:
```bash
python scripts/run_ragas_evaluation.py
```

## Workflow Integration

Add evaluation to CI/CD with the script:

```bash
python scripts/run_ragas_evaluation.py --tune
```

Use threshold checks in your pipeline to catch regressions when FAQ data or retrieval logic changes.

## Troubleshooting

### Issue: "No module named 'ragas'"
```bash
pip install -e ".[ragas]"
```

### Issue: "OPENAI_API_KEY is required"
- Set `OPENAI_API_KEY` in `.env`
- Ensure `LLM_PROVIDER=openai`

### Issue: "RAGAS evaluation is slow"
- Semantic metrics call the LLM and embeddings endpoints
- Reduce runtime with a smaller evaluation dataset during local iteration

### Issue: "Low context recall score"
- Add more similar questions to evaluation dataset
- Expand FAQ chunks with more specific guidance
- Adjust intent bonus scoring in `FAQRepository`

### Issue: "Evaluation dataset not found"
```bash
# Ensure you're in the backend directory
cd backend
python scripts/run_ragas_evaluation.py
```

## References

- [RAGAS Documentation](https://docs.ragas.io/)
- [RAG Evaluation Best Practices](https://docs.ragas.io/en/latest/concepts/metrics/)
