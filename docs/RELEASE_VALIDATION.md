# Local release validation — 2026-10-15

## Scope

Prepared from the author working tree, preserving existing frontend/backend edits. This is a fresh repository with no original Git history. No GitHub push, model generation, actual database query, or re-evaluation of saved experimental answers was performed.

## Checks completed

- Python source compilation passed.
- All 100 existing `paper_eval` regression tests passed in the isolated evaluation environment; these include V2/V3 tests, constructed counterexamples, preprocessing and matching diagnostics. The 70 fact-run/fact-extractor tests also passed in the existing `rice_mdr1` environment.
- Eight new public-adapter tests passed: complete cohorts, canonical final answers, S/C counts, duplicate/incomplete cohort rejection, immutable references, malformed reasoning tags, overwrite protection, macro means, and pending-score bounds.
- Exported Vue application production build passed, using the existing development checkout's `node_modules` temporarily. Build reported large-bundle warnings. This was not a clean `npm ci` installation. Temporary dependency link and build outputs were removed from the public tree afterward.
- Runtime requirements resolved successfully with pip `--dry-run --ignore-installed` on Python 3.11/Linux (94 packages). `requirements-runtime.lock` records that resolution. No packages were installed into the running backend environment. A complete fresh-environment runtime/deployment test has not been performed.
- Launch scripts passed `bash -n`. Services were not restarted; frontend/backend/Neo4j/Ollama end-to-end startup remains unverified for this export.
- All 150 Gold questions/answers match the frozen profiles, with S=85/C=65 and 29 types. Gold profiles are copied byte-for-byte. The 50-row query dataset is byte-identical in the original source, experiment copy, and release copy.
- V3 fact extraction, V3 answer-format normalization, canonical preprocessing, BERTScore, long-text matching, and audited matching files are byte-identical to the source code used for the approved evaluation version.
- Neo4j benchmark dry run preserved all 50 supplied SQL/Cypher pairs verbatim, emitted a unique CSV header, and made no database requests. No actual timing or SQL/Cypher result-equivalence verification was performed.
- Static text scan found no long `sk-` keys, private-key headers, author-specific absolute home paths, or literal Python credential assignments in the export. Config values are supplied through private `.env`; no original environment files or Git history were copied. This is a static scan, not a guarantee against every possible secret pattern.

## Packaging changes

1. New relative-path launchers and `.env.example`; remove hardcoded credential defaults and private paths from exported copies only.
2. Frontend Vite backend proxy reads the configurable backend URL; remove the commented browser key example.
3. Public input adapter attaches frozen Gold/difficulty, canonicalizes final answers and validates identities without choosing runs. Semantic adapter calls the unchanged existing scorer with pinned XLM-R settings, preserving fact score columns.
4. Model download helper includes XLM-R SentencePiece vocabulary and creates checksum metadata. No weights are bundled.
5. Query benchmark respects supplied `cypher` and deduplicates the output header; original template generation remains only for legacy inputs without supplied Cypher. No KGQA scoring rules change.
6. Previous heuristics, API evaluation trials, analysis logs/results, environment exports with private paths, backup files, and original repository history are omitted. Retained legacy scorer modules are explicitly distinguished from the documented V3 workflow.

## Before publication

- Select a software/data license and confirm rights for reference answers, metadata tables, logos, and third-party assets.
- Decide how the actual rice graph and its provenance/build instructions will be made available. Metadata updates alone do not reconstruct it.
- The original repository tracked real credentials. Do not publish its existing history; revoke/rotate those credentials as appropriate before any publication of that original repository.
- With experiment outputs/adjudications excluded as requested, the public bundle cannot independently reproduce exact historical score tables. Disclose this availability limit and the post-hoc best-run selection.
- Perform a clean installation and real database/model-backed system smoke test before claiming fully reproducible deployment.
