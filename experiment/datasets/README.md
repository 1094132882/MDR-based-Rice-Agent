# Evaluation datasets

## KGQA question set

Canonical source: `../../methods/s_cot_raps/dataset.csv`, 150 questions. `sample_id` is its **zero-based** row index (0–149), not a separate source column. Preserve row order. `split` contains `type1`–`type29`; it is a question type, not a train/test split. All 150 are evaluation questions. The file contains original questions/Gold answers and no model-generated answers.

`../paper_eval/difficulty.json` records the fixed per-question S/C map: 85 Simple, 65 Complex. `gold_profiles.json` contains the approved type-specific Gold facts, scope, polarity, hashes, and difficulty. It is a dataset contract, not an experimental result. Do not regenerate it with earlier versions and silently replace it. Checksums and encoding are in `provenance.json`.

## MySQL versus Neo4j query set

`mysql_vs_kg.csv`: **50 rows**, columns `type,question,mysql,cypher`, **GB18030** encoding. This is a byte-for-byte copy of the author-provided file. Both SQL and Cypher queries are supplied. It contains **no timings**, generated model answers, or benchmark scores.

```python
import pandas as pd
queries = pd.read_csv('experiment/datasets/mysql_vs_kg.csv', encoding='gb18030')
```

The published `benchmark_kg_queries.py` executes the supplied Cypher verbatim; legacy CSVs without a Cypher field use its existing query templates. The CSV header is deduplicated to avoid two `cypher` columns. Those packaging changes are separate from all KGQA fact-scoring rules. No queries were executed against a database during release preparation.

```bash
# Inspect exact input queries without connecting to a database; generates local output.
python experiment/benchmark_kg_queries.py --dry-run \
  --input experiment/datasets/mysql_vs_kg.csv \
  --output outputs/query_benchmark/dry_run.csv
# Actual timing, only after configuring the database/environment:
python experiment/benchmark_kg_queries.py \
  --input experiment/datasets/mysql_vs_kg.csv \
  --output outputs/query_benchmark/neo4j.csv --rounds 5 --warmup 1
```

The existing runner measures Neo4j, not MySQL. MySQL SQL is included as data; no standalone MySQL timing runner was present in the inspected source. Without externally supplied matching MySQL timing columns, MySQL averages and speedups remain blank. SQL/Cypher result equivalence, database versions, schemas, indexes, cache policy, and timing units must be validated before making a cross-database efficiency claim. An index-creation option is explicit and never enabled by default.
