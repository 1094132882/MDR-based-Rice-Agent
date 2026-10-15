# MDR-based RGI Agent

A metadata-registry-guided rice knowledge-graph question-answering system, with a Vue interface, Flask backend, KGQA tools, and task-based evaluation scripts.

This source release includes the **150-question KGQA benchmark** (85 Simple / 65 Complex), frozen Gold fact contracts, and the **50-query MySQL/Neo4j benchmark**. Model answers, scores, experiment reports, traces, logs, model weights, Neo4j databases, local credentials, and original Git history are excluded.

## Code layout

| Path | Contents |
|---|---|
| `rice_vue/` | Vue/Vite user interface |
| `rice_Python/` | Flask routes, graph/metadata services, language adapters |
| `experiment/agent_scot.py`, `experiment/tools/` | Agent and executable KGQA tools |
| `methods/s_cot_raps/` | MDR schema, constraints, prompt construction, method implementation |
| `methods/s_cot_raps/dataset.csv` | Original Chinese questions and reference answers |
| `experiment/datasets/` | Approved Gold profiles and query benchmark |
| `experiment/paper_eval/` | Versioned fact and semantic scorers, regression tests |
| `update_graph/` | Metadata registration tables and explicit database-update utilities |
| `scripts/` | Portable service launchers |

The web backend currently delegates to `experiment/agent_scot.py`. Keep both `rice_Python/` and `experiment/`; the experiment directory also contains live runtime dependencies.

## Run locally

Use Python 3.11 and a separate environment. The original development environment was named `rice_mdr1`.

```bash
conda create -n rice_mdr1_public python=3.11
conda activate rice_mdr1_public
python -m pip install -r requirements-runtime.lock
cp .env.example .env
# Edit .env: set your database password, ports, and model/provider.
cd rice_vue
npm ci
cd ..
```

Start Neo4j 5.24.x with the rice graph and RGI/MDR metadata already loaded. Set its Bolt port to match `NEO4J_URI`. A blank Neo4j instance cannot reproduce the system. This release includes metadata tables and schema snapshots, **not the full graph or a complete raw-data-to-database reconstruction pipeline**. Database distribution and its provenance remain a separate author release decision; see [database notes](docs/DATABASE.md).

Start each component in a separate terminal, from this checkout:

```bash
# Terminal 1, only if Ollama is not already serving at the configured endpoint
bash scripts/start_ollama.sh
# In a separate shell, populate the model for that same endpoint:
OLLAMA_HOST=127.0.0.1:11501 ollama pull qwen3:14b

# Terminal 2, with the Python environment active
bash scripts/start_backend_scot.sh

# Terminal 3
bash scripts/start_frontend_dev.sh
```

Default addresses: frontend `http://127.0.0.1:5173`, Flask `11500`, Neo4j Bolt `7690`, Ollama `11501`. These are configurable, not mandatory system ports. Cloud LLMs use `LLM_PROVIDER=openai`, your compatible `LLM_API_BASE`, `LLM_MODEL_NAME`, and backend-only `LLM_API_KEY` in `.env`. Never put a provider key in frontend code.

The Flask/Vite commands are development launchers. Neo4j and Ollama are external services; their binaries and model weights are not bundled. Metadata update utilities write to a database and are never invoked automatically.

## Evaluate

The supported paper metrics are **Accuracy + Structured Fact F1 + XLM-R BERTScore-F1**. Read [evaluation instructions](experiment/paper_eval/README.md) and [dataset documentation](experiment/datasets/README.md). The public adapters call the existing approved scorer; they do not select runs or change fact rules.

```bash
python -m unittest experiment.paper_eval.test_structured_facts_v3 experiment.paper_eval.test_structured_run_v3 experiment.test_public_adapters
```

Historical evaluation modules are retained for code provenance/dependencies, not as the default paper method. In particular, `paper_eval/run.py`, `accuracy.py`, `factual_run.py`, and V2 modules implement previous evaluation versions. Use the V3 workflow documented below. Generation-time `is_correct` in `evaluate_scot.py` is an old diagnostic, **not final paper Accuracy**.

## Reproducibility and release scope

The paper evaluated four generators (DeepSeek-V3, GPT-4o, MiniMax-M2.5, Qwen3-14B) and four configurations (Baseline, Static, w/o Semantic Validation, Full). Configure a generator before running `experiment/evaluate_scot.py --help`; actual generation requires the external graph and model endpoint and may incur provider charges. No experiment is started on import of the release preparation scripts.

Historical paper runs were chosen after observing Accuracy; numbers of candidate runs differed across configurations. This is a best-observed single-run selection, not a preregistered single run, average, or uncertainty estimate. The public evaluator accepts explicit saved outputs and performs **no automatic run selection**. Original outputs and human adjudication records are intentionally not included, so the released benchmark/code alone cannot reconstruct the exact historical 2,400-record score tables. It can evaluate new outputs using the same automatic rules, with new manual decisions where required.

The historical environment freeze is retained in `docs/historical-environment-freeze.txt` as provenance. It contains incompatible historical LangChain pins and must not be installed as a lock file. `requirements.txt` is a separate runtime dependency specification; fresh-environment resolution/build status is recorded in `docs/RELEASE_VALIDATION.md`.

No software license is asserted by this preparation. Before publication, the authors must select a license and confirm redistribution rights for the benchmark references, registration tables, institutional logos, and third-party assets. Existing author attributions and third-party notices are retained. This preparation does not upload to GitHub.
