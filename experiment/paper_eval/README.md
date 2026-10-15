# Current evaluation workflow

Supported automatic fact scorer: `structured_facts_v3.py` (`rice-structured-facts-v3.0`). Frozen contracts: `../datasets/gold_profiles.json`. Existing core fact scorer and BERTScore matching implementations are copied without scoring changes. New public adapters only make input preparation and execution independent of private result directories.

## Metrics

- **Accuracy**: binary whole-question correctness under its approved type contract. Missing/wrong required facts or recognized conflicting target facts fail the question. Unsupported statements may require manual review.
- **Structured Fact F1**: facts include subject, relation, object, qualifiers, and polarity. TP/FP/FN are calculated by the task-specific extractor with approved non-redundant count/list handling. P=TP/(TP+FP), R=TP/(TP+FN), F1=2TP/(2TP+FP+FN). Report the arithmetic mean of per-question F1, not F1 derived from aggregate Accuracy. Empty/failure predictions follow the existing zero policy. Unresolved records retain the full denominator and produce bounds, not a fabricated point estimate.
- **BERTScore-F1**: auxiliary textual semantic similarity; arithmetic mean of individual F1 values. Report as 100 × mean. It is not factual correctness, percentage of correct answers, or retrieval faithfulness.

The fact metrics cover the requested task facts. Supplementary prose is audited separately; arbitrary biological statements are not exhaustively extracted or verified. Function annotations use the gene-bound single-annotation contract; paraphrases the extractor cannot establish require review. Correct gene IDs and numbers still need exact fact metrics, even if semantic similarity is high.

All metrics use the same canonical `final_answer` plus original `ground_truth`. Preprocessing removes closed `<think>` blocks and trims boundary whitespace; malformed tags stop processing for review. Markdown/URLs are preserved. Scorers then apply their own documented fact normalization or tokenization. No model-generated answers or human verdicts are included in this release.

## 1. Prepare explicit saved outputs

From the repository root, supply a UTF-8 CSV with at least:

```text
model,method,run,sample_id,answer
```

Methods: `baseline`, `mdr_static`, `no_gotci`, `s_cot_raps`. `sample_id` is 0–149. Include all 150 questions for each supplied model/method/run. Keep raw answer text in `answer`. Optional generation failures belong in `generation_error` or `error`. If question/Gold/difficulty/final_answer fields are supplied, they are verified, not silently overwritten on a mismatch. No run is chosen or discarded automatically.

```bash
python -m experiment.prepare_eval_input \
  --input /path/to/explicit_saved_answers.csv \
  --output outputs/eval/prepared.csv

# Four models × four methods × 150 = 2400, one fixed run per cohort.
python -m experiment.paper_eval.structured_run_v3 \
  --input outputs/eval/prepared.csv \
  --profiles experiment/datasets/gold_profiles.json \
  --output outputs/eval/structured_v3
```

For another complete cohort collection, set `--expected-records N`; a single model/configuration uses 150. The 2400-record mode additionally checks 16 fixed cohorts and four models. Human verdict replay is supported only for the existing restricted annotation contract via `--human-verdicts`; do not invent or reuse historical verdicts for changed text. New unresolved answers require a separate documented review process. Missing verdicts remain pending with bounds.

## 2. XLM-R semantic metric

Use a separate Python 3.11 environment; do not mix its NumPy/Torch/Transformers versions with a live backend:

```bash
python -m venv .venv/eval
source .venv/eval/bin/activate
python -m pip install -r experiment/paper_eval/requirements.txt
python -m experiment.download_bertscore_model --output models/xlm-roberta-base
python -m experiment.score_bertscore \
  --input outputs/eval/structured_v3/per_question.csv \
  --bert-snapshot models/xlm-roberta-base \
  --output outputs/eval/xlm_r
```

Download uses a pinned revision, includes XLM-R SentencePiece vocabulary, and records weight SHA-256 in `source.json`. A compatible preverified local snapshot may be supplied instead. Weights are excluded from Git. The scoring entrypoint always supplies the snapshot, XLM-R tokenizer/encoder pair, layer 9, and the existing matching implementation.

| Setting | Value |
|---|---|
| Model | `FacebookAI/xlm-roberta-base` |
| Revision | `e73636d4f797dec63c3081bb6ed5c7b0bb3f2089` |
| Hidden layers | 9, fixed BERTScore preset; not tuned on the benchmark |
| Tokenizer | Corresponding slow `XLMRobertaTokenizer`, `use_fast_tokenizer=False` |
| Encoder | Corresponding XLM-R encoder from the same snapshot |
| Language / IDF / rescaling | `zh` / `False` / `False` |
| Text transform | `' '.join(jieba.cut(final_answer))`, same for Gold |
| Device | CPU, 4 threads |
| Short inputs | Standard BERTScore, ≤512 total tokens |
| Long inputs | 510 payload tokens/window + boundary special tokens, no overlap or truncation |
| Matching | Concatenate window embeddings; global greedy cosine matching, allowing many-to-one matches |
| Normalization | Separate whole-text non-special-token denominators for P/R; harmonic F1, not mean window F1 |
| Special tokens | Zero weight, retained as match targets, matching the frozen implementation |

Long answers use a **window-encoded BERTScore variant**: context does not cross windows. Disclose it explicitly. XLM-R reduces known gene-ID token collisions but cannot make semantic similarity an exact identifier or numerical validator. Unknown tokens remain possible; use `paper_eval/probe_tokenizer.py` for diagnostics.

The semantic adapter preserves all existing fact scores and run identities. It outputs `per_question.csv`, `per_group.csv`, model and ablation tables, `summary.md`, and a manifest of configuration, input/code hashes, and package versions. Existing output paths are refused. Generation failures retain zero and the denominator; neural failures stop rather than silently dropping rows. Fact scores with pending decisions remain ranges in the combined report.

## Historical modules and paper reproducibility

V1/V2 modules, `run.py`, and `xlm_only_run.py` remain for historical provenance or helper imports, and may expect private historical directories or older metrics. They are not the public workflow above. The old root `evaluate_metrics.py` compatibility CLI is intentionally not included as a default entrypoint to an outdated scorer. RAGAs experiments were abandoned and are not the paper evaluation protocol.

The author-selected historical runs used post-hoc best Accuracy and unequal candidate run counts. This release never reselects them. Because the author excludes experimental outputs and adjudications from GitHub, exact historical tables cannot be independently reconstructed from this public bundle alone. Describe that availability limit honestly rather than claiming full result reproduction.

## Regression checks

```bash
python -m unittest experiment.paper_eval.test_structured_facts_v2 \
  experiment.paper_eval.test_structured_run_v2 \
  experiment.paper_eval.test_structured_facts_v3 \
  experiment.paper_eval.test_structured_run_v3 \
  experiment.test_public_adapters
# With evaluation dependencies installed:
python -m unittest discover -s experiment/paper_eval -t . -q
```

These use Gold self-checks and constructed counterexamples, not the excluded 2400 saved model outputs. No API calls or model generation are needed for fact tests.
