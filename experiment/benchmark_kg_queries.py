#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Benchmark direct Neo4j queries for the MySQL-vs-KG experiment.

Input CSV columns: type, question, mysql, cypher; optional MySQL round1..round5.
Supplied Cypher is executed verbatim. Legacy rows without it use query templates.

The input produced by the MySQL benchmark is GBK/GB18030 encoded. This script
keeps the original rows, generates an equivalent direct Cypher query for each
question, runs every query for N rounds, and writes a comparable CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_URI = "bolt://127.0.0.1:7689"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = ""


GENE_PATTERNS = [
    r"LOC_Os\d+g\d+(?:\.\d+)?",
    r"Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?",
    r"R\d+C\d+g\d+",
    r"Oglab_\d+",
    r"TMG\d+(?:\.\d+)?",
    r"Os\d{2}g\d+(?:\.\d+)?",
]
MUTANT_PATTERN = r"22NB[A-Z]\d+"


QUERY_TEMPLATES: Dict[str, str] = {
    "gene_location": """
MATCH (g:Gene {name: $gene})
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end
""",
    "gene_strand": """
MATCH (g:Gene {name: $gene})
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand
""",
    "gene_location_dna": """
MATCH (g:Gene {name: $gene})
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       g.dna_seq AS dna
""",
    "mutant_gene_location": """
MATCH (m:Mutant {name: $mutant})<-[:has_a_mutant]-(g:Gene)
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
RETURN DISTINCT g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       m.name AS mutant
ORDER BY chromosome, toInteger(start), gene
""",
    "gene_location_function_mutant": """
MATCH (g:Gene {name: $gene})
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
OPTIONAL MATCH (g)-[:has_a_function]->(f:Function)
OPTIONAL MATCH (g)-[:has_a_mutant]->(m:Mutant)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       collect(DISTINCT f.name) AS functions,
       collect(DISTINCT m.name) AS mutants
""",
    "ogi_members_location_mutant": """
MATCH (ogi:OGI)-[:has_a_gene]->(:Gene {name: $gene})
MATCH (ogi)-[:has_a_gene]->(g:Gene)
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
OPTIONAL MATCH (g)-[:has_a_mutant]->(m:Mutant)
RETURN ogi.name AS ogi,
       g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       collect(DISTINCT m.name) AS mutants
ORDER BY chromosome, toInteger(start), gene
""",
    "gene_location_function_mutant_ogi": """
MATCH (g:Gene {name: $gene})
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
OPTIONAL MATCH (g)-[:has_a_function]->(f:Function)
OPTIONAL MATCH (g)-[:has_a_mutant]->(m:Mutant)
OPTIONAL MATCH (ogi:OGI)-[:has_a_gene]->(g)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       collect(DISTINCT f.name) AS functions,
       collect(DISTINCT m.name) AS mutants,
       collect(DISTINCT ogi.name) AS ogis
""",
    "gene_location_transcript_mutant_ogi": """
MATCH (g:Gene {name: $gene})
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
OPTIONAL MATCH (g)-[:has_a_transcript]->(tr:mRNA)
OPTIONAL MATCH (g)-[:has_a_mutant]->(m:Mutant)
OPTIONAL MATCH (ogi:OGI)-[:has_a_gene]->(g)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       collect(DISTINCT tr.name) AS transcripts,
       collect(DISTINCT m.name) AS mutants,
       collect(DISTINCT ogi.name) AS ogis
""",
    "gene_basic_function_transcript_expression_mutant": """
MATCH (g:Gene {name: $gene})
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
OPTIONAL MATCH (g)-[:has_a_function]->(f:Function)
OPTIONAL MATCH (g)-[:has_a_transcript]->(tr:mRNA)
OPTIONAL MATCH (g)-[:measures_gene_expression]->(e:Expression)
OPTIONAL MATCH (g)-[:has_a_mutant]->(m:Mutant)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       collect(DISTINCT f.name) AS functions,
       collect(DISTINCT tr.name) AS transcripts,
       collect(DISTINCT {
           leaf: e.leaf_value,
           root: e.root_value,
           young_ear: e.young_ear_value
       }) AS expression,
       collect(DISTINCT m.name) AS mutants
""",
    "mutant_gene_basic_ogi_transcript_function": """
MATCH (m:Mutant {name: $mutant})<-[:has_a_mutant]-(g:Gene)
OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
OPTIONAL MATCH (ogi:OGI)-[:has_a_gene]->(g)
OPTIONAL MATCH (g)-[:has_a_transcript]->(tr:mRNA)
OPTIONAL MATCH (g)-[:has_a_function]->(f:Function)
RETURN g.name AS gene,
       c.name AS chromosome,
       sp.name AS start,
       ep.name AS end,
       st.name AS strand,
       m.name AS mutant,
       collect(DISTINCT ogi.name) AS ogis,
       collect(DISTINCT tr.name) AS transcripts,
       collect(DISTINCT f.name) AS functions
ORDER BY chromosome, toInteger(start), gene
""",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run direct Neo4j benchmark queries equivalent to the MySQL test CSV."
    )
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parent / "datasets/mysql_vs_kg.csv"),
        help="MySQL benchmark CSV path.",
    )
    parser.add_argument(
        "--output",
        default="experiment/results/kg_query_benchmark/new_all_kg.csv",
        help="Output CSV path.",
    )
    parser.add_argument("--rounds", type=int, default=5, help="Measured rounds per query.")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup rounds per query.")
    parser.add_argument("--encoding", default="auto", help="Input CSV encoding or auto.")
    parser.add_argument("--dry-run", action="store_true", help="Only generate Cypher CSV, do not connect to Neo4j.")
    parser.add_argument(
        "--avoid-indexes",
        action="store_true",
        help="Rewrite starting-node matches to avoid property indexes for a no-index contrast run.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Only process first N rows after header.")
    parser.add_argument("--start", type=int, default=1, help="1-based first data row to process.")
    parser.add_argument("--end", type=int, default=0, help="1-based last data row to process.")
    parser.add_argument(
        "--ensure-indexes",
        action="store_true",
        help="Create common Neo4j indexes before timing. Use once on the server.",
    )
    return parser.parse_args()


def detect_encoding(path: Path) -> str:
    if path.exists():
        data = path.read_bytes()[:8192]
        for encoding in ("utf-8-sig", "gb18030", "gbk", "latin1"):
            try:
                data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
    return "utf-8-sig"


def read_rows(path: Path, encoding: str) -> List[Dict[str, str]]:
    actual_encoding = detect_encoding(path) if encoding == "auto" else encoding
    with path.open(newline="", encoding=actual_encoding) as f:
        return list(csv.DictReader(f))


def extract_gene(question: str) -> str:
    for pattern in GENE_PATTERNS:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            return match.group(0)
    raise ValueError(f"Cannot extract gene from question: {question}")


def extract_mutant(question: str) -> str:
    match = re.search(MUTANT_PATTERN, question, re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot extract mutant from question: {question}")
    return match.group(0)


def infer_query_kind(row_type: str, ordinal_in_type: int) -> str:
    key = (row_type, 1 if ordinal_in_type <= 5 else 2)
    mapping = {
        ("1", 1): "gene_location",
        ("1", 2): "gene_strand",
        ("2", 1): "gene_location_dna",
        ("2", 2): "mutant_gene_location",
        ("3", 1): "gene_location_function_mutant",
        ("3", 2): "ogi_members_location_mutant",
        ("4", 1): "gene_location_function_mutant_ogi",
        ("4", 2): "gene_location_transcript_mutant_ogi",
        ("5", 1): "gene_basic_function_transcript_expression_mutant",
        ("5", 2): "mutant_gene_basic_ogi_transcript_function",
    }
    if key not in mapping:
        raise ValueError(f"Unsupported query type/ordinal: type={row_type}, ordinal={ordinal_in_type}")
    return mapping[key]


def build_query(row: Dict[str, str], ordinal_in_type: int) -> Tuple[str, Dict[str, Any], str, str]:
    kind = infer_query_kind(row["type"], ordinal_in_type)
    question = row["question"]
    if kind.startswith("mutant_"):
        identifier = extract_mutant(question)
        params = {"mutant": identifier}
    else:
        identifier = extract_gene(question)
        params = {"gene": identifier}
    return kind, params, QUERY_TEMPLATES[kind].strip(), identifier


def avoid_property_indexes(kind: str, cypher: str) -> str:
    """Rewrite entry-point lookups so Neo4j cannot use property indexes.

    This is a safe contrast mode for benchmark analysis. It keeps existing
    indexes in the database and changes only this benchmark's Cypher.
    """
    if kind == "ogi_members_location_mutant":
        return cypher.replace(
            "MATCH (ogi:OGI)-[:has_a_gene]->(:Gene {name: $gene})\n"
            "MATCH (ogi)-[:has_a_gene]->(g:Gene)",
            "MATCH (target:Gene)\n"
            "WHERE toString(target.name) = $gene\n"
            "MATCH (ogi:OGI)-[:has_a_gene]->(target)\n"
            "MATCH (ogi)-[:has_a_gene]->(g:Gene)",
        )
    if kind.startswith("mutant_"):
        return cypher.replace(
            "MATCH (m:Mutant {name: $mutant})<-[:has_a_mutant]-(g:Gene)",
            "MATCH (m:Mutant)<-[:has_a_mutant]-(g:Gene)\n"
            "WHERE toString(m.name) = $mutant",
        )
    return cypher.replace(
        "MATCH (g:Gene {name: $gene})",
        "MATCH (g:Gene)\nWHERE toString(g.name) = $gene",
    )


def mysql_average(row: Dict[str, str]) -> float | None:
    values = []
    for idx in range(1, 6):
        raw = (row.get(f"round{idx}") or "").strip()
        if raw:
            values.append(float(raw))
    return statistics.mean(values) if values else None


def preview_records(records: Iterable[Dict[str, Any]], max_chars: int = 500) -> str:
    payload = []
    for record in records:
        clean = {}
        for key, value in record.items():
            if isinstance(value, str) and len(value) > 120:
                clean[key] = value[:117] + "..."
            else:
                clean[key] = value
        payload.append(clean)
        if len(payload) >= 3:
            break
    return json.dumps(payload, ensure_ascii=False, default=str)[:max_chars]


def get_driver():
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI", DEFAULT_URI)
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or DEFAULT_USER
    password = os.environ["NEO4J_PASSWORD"]
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_indexes(driver) -> None:
    indexes = [
        ("gene_name_idx", "Gene", "name"),
        ("chr_name_idx", "Chromosome", "name"),
        ("position_name_idx", "Position", "name"),
        ("ogi_name_idx", "OGI", "name"),
        ("mutant_name_idx", "Mutant", "name"),
        ("function_name_idx", "Function", "name"),
    ]
    with driver.session() as session:
        for name, label, prop in indexes:
            session.run(f"CREATE INDEX {name} IF NOT EXISTS FOR (n:{label}) ON (n.{prop})").consume()


def run_once(session, cypher: str, params: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    start = time.perf_counter()
    result = session.run(cypher, params)
    records = [dict(record) for record in result]
    elapsed = time.perf_counter() - start
    return elapsed, records


def selected_rows(rows: List[Dict[str, str]], start: int, end: int, limit: int) -> List[Tuple[int, Dict[str, str]]]:
    pairs = list(enumerate(rows, start=1))
    pairs = [(idx, row) for idx, row in pairs if idx >= start]
    if end:
        pairs = [(idx, row) for idx, row in pairs if idx <= end]
    if limit:
        pairs = pairs[:limit]
    return pairs


def summarize(output_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in output_rows:
        groups[row["type"]].append(row)

    def as_float(row: Dict[str, str], key: str) -> float | None:
        value = row.get(key, "")
        return float(value) if value else None

    summary = {"overall": {}, "by_type": {}}
    all_mysql = [as_float(row, "mysql_avg_s") for row in output_rows if as_float(row, "mysql_avg_s") is not None]
    all_kg = [as_float(row, "kg_avg_s") for row in output_rows if as_float(row, "kg_avg_s") is not None]
    if all_mysql and all_kg:
        summary["overall"] = {
            "mysql_avg_s": statistics.mean(all_mysql),
            "kg_avg_s": statistics.mean(all_kg),
            "speedup": statistics.mean(all_mysql) / statistics.mean(all_kg) if statistics.mean(all_kg) else None,
        }
    for typ, rows in sorted(groups.items(), key=lambda item: int(item[0])):
        mysql_vals = [as_float(row, "mysql_avg_s") for row in rows if as_float(row, "mysql_avg_s") is not None]
        kg_vals = [as_float(row, "kg_avg_s") for row in rows if as_float(row, "kg_avg_s") is not None]
        if mysql_vals and kg_vals:
            summary["by_type"][typ] = {
                "n": len(rows),
                "mysql_avg_s": statistics.mean(mysql_vals),
                "kg_avg_s": statistics.mean(kg_vals),
                "speedup": statistics.mean(mysql_vals) / statistics.mean(kg_vals) if statistics.mean(kg_vals) else None,
            }
    return summary


def write_summary_csv(summary: Dict[str, Any], path: Path) -> None:
    rows = []
    overall = summary.get("overall") or {}
    if overall:
        rows.append(
            {
                "group": "overall",
                "n": "",
                "mysql_avg_s": overall.get("mysql_avg_s", ""),
                "kg_avg_s": overall.get("kg_avg_s", ""),
                "speedup": overall.get("speedup", ""),
            }
        )
    for typ, item in (summary.get("by_type") or {}).items():
        rows.append(
            {
                "group": f"type_{typ}",
                "n": item.get("n", ""),
                "mysql_avg_s": item.get("mysql_avg_s", ""),
                "kg_avg_s": item.get("kg_avg_s", ""),
                "speedup": item.get("speedup", ""),
            }
        )
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["group", "n", "mysql_avg_s", "kg_avg_s", "speedup"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        print(f"Input CSV not found: {input_path}", file=sys.stderr)
        return 2

    rows = read_rows(input_path, args.encoding)
    pairs = selected_rows(rows, args.start, args.end, args.limit)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ordinals_by_type: Dict[str, int] = defaultdict(int)
    prepared = []
    for idx, row in enumerate(rows, start=1):
        ordinals_by_type[row["type"]] += 1
        if not any(selected_idx == idx for selected_idx, _ in pairs):
            continue
        if row.get("cypher", "").strip():
            if args.avoid_indexes:
                raise ValueError("--avoid-indexes is not defined for supplied Cypher")
            kind, params, cypher, identifier = "supplied_cypher", {}, row["cypher"], ""
        else:
            kind, params, cypher, identifier = build_query(row, ordinals_by_type[row["type"]])
        if args.avoid_indexes:
            cypher = avoid_property_indexes(kind, cypher)
        prepared.append((idx, row, kind, params, cypher, identifier))

    driver = None
    if not args.dry_run:
        try:
            driver = get_driver()
            driver.verify_connectivity()
            if args.ensure_indexes:
                ensure_indexes(driver)
        except Exception as exc:
            uri = os.getenv("NEO4J_URI", DEFAULT_URI)
            print(
                f"Cannot connect to Neo4j at {uri}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            print(
                "Set NEO4J_URI, NEO4J_USERNAME/NEO4J_USER, and NEO4J_PASSWORD, "
                "or run with --dry-run to only generate Cypher.",
                file=sys.stderr,
            )
            if driver:
                driver.close()
            return 3

    out_rows: List[Dict[str, str]] = []
    fieldnames = [k for k in rows[0] if k != "cypher"] + [
        "kg_query_kind",
        "kg_identifier",
        "cypher",
        *[f"kg_round{i}" for i in range(1, args.rounds + 1)],
        "kg_avg_s",
        "mysql_avg_s",
        "speedup",
        "row_count",
        "result_preview",
        "error",
    ]

    try:
        session_ctx = driver.session() if driver else None
        session = session_ctx.__enter__() if session_ctx else None
        for idx, row, kind, params, cypher, identifier in prepared:
            out = dict(row)
            out.update(
                {
                    "kg_query_kind": kind,
                    "kg_identifier": identifier,
                    "cypher": cypher,
                    "kg_avg_s": "",
                    "mysql_avg_s": "",
                    "speedup": "",
                    "row_count": "",
                    "result_preview": "",
                    "error": "",
                }
            )
            for round_idx in range(1, args.rounds + 1):
                out[f"kg_round{round_idx}"] = ""

            mysql_avg = mysql_average(row)
            if mysql_avg is not None:
                out["mysql_avg_s"] = f"{mysql_avg:.9f}"

            print(f"[{idx:02d}] {kind} {identifier}")
            if args.dry_run:
                out_rows.append(out)
                continue

            try:
                for _ in range(args.warmup):
                    run_once(session, cypher, params)

                timings = []
                last_records: List[Dict[str, Any]] = []
                for round_idx in range(1, args.rounds + 1):
                    elapsed, records = run_once(session, cypher, params)
                    timings.append(elapsed)
                    last_records = records
                    out[f"kg_round{round_idx}"] = f"{elapsed:.9f}"

                kg_avg = statistics.mean(timings)
                out["kg_avg_s"] = f"{kg_avg:.9f}"
                if mysql_avg is not None and kg_avg:
                    out["speedup"] = f"{mysql_avg / kg_avg:.6f}"
                out["row_count"] = str(len(last_records))
                out["result_preview"] = preview_records(last_records)
            except Exception as exc:  # keep the benchmark moving across bad rows
                out["error"] = f"{type(exc).__name__}: {exc}"
                print(f"  ERROR: {out['error']}", file=sys.stderr)
            out_rows.append(out)
    finally:
        if driver:
            try:
                if "session_ctx" in locals() and session_ctx:
                    session_ctx.__exit__(None, None, None)
            finally:
                driver.close()

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary = summarize(out_rows)
    summary_path = output_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_csv_path = output_path.with_suffix(".summary.csv")
    write_summary_csv(summary, summary_csv_path)

    print(f"\nWrote: {output_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {summary_csv_path}")
    if summary.get("overall"):
        overall = summary["overall"]
        print(
            "Overall: "
            f"MySQL {overall['mysql_avg_s']:.6f}s, "
            f"KG {overall['kg_avg_s']:.6f}s, "
            f"speedup {overall['speedup']:.2f}x"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
