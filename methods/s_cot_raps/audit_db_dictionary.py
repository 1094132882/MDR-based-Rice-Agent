#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔎 Neo4j 数据字典 + MDR 元数据 完整审计脚本（服务器侧运行）
=====================================================

目标：
1) 直接从 Neo4j 读取“业务图谱 schema 字典”
   - labels / relationshipTypes / propertyKeys
   - 关键业务节点（Gene/Chromosome/Position/Accession/SV/TE...）的数量与属性键
   - 关键出边关系（Gene->?, SV->?）的关系类型与目标标签

2) 读取并审计 “MDR 元数据字典”
   - DEC/DE/VD/VDG/PEV/VLM 数量
   - VD 是否有 PEV（允许值）
   - PEV 是否有 VLM（值含义/别名映射）
   - 关键值域（Stand/Strand、SV_Type、TE_Type、Accession、OGI_Class）是否齐全

3) 扫描仓库中 tools 的 Cypher 示例/模板，找出引用了不存在的：
   - 关系类型（例如 :strand）
   - 属性键（例如 g.strand / g.Strand）

使用方式（建议在服务器 tmux 中运行）：
-----------------------------------------------------
cd ~/xrb/rice_mdr1
python methods/s_cot_raps/audit_db_dictionary.py \
  --out-dir experiment/results/db_audit_run5

连接参数默认读取环境变量或 methods/s_cot_raps/config.py：
- NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD

输出：
- out_dir/schema_audit.json
- out_dir/schema_audit.md

注意：
本脚本只读，不会修改数据库。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_config() -> Tuple[str, str, str]:
    """优先从环境变量/Config 读取 Neo4j 连接信息。"""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if uri and username and password:
        return uri, username, password

    try:
        from methods.s_cot_raps.config import Config  # type: ignore

        uri = uri or getattr(Config, "NEO4J_URI", None)
        username = username or getattr(Config, "NEO4J_USERNAME", None)
        password = password or getattr(Config, "NEO4J_PASSWORD", None)
    except Exception:
        pass

    return (
        uri or "bolt://127.0.0.1:7689",
        username or "neo4j",
        password or "",
    )


def _ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def _json_dump(obj: Any, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _md_write(text: str, path: Path) -> None:
    path.write_text(text, encoding="utf-8")


class StepProgress:
    """
    极简进度条（无第三方依赖），适合 tmux/日志查看。

    用法：
        p = StepProgress(total=6)
        p.step("Connecting ...")
        p.log("  detail ...")
    """

    def __init__(self, total: int, width: int = 28):
        self.total = max(1, int(total))
        self.width = max(10, int(width))
        self.current = 0

    def step(self, msg: str) -> None:
        self.current = min(self.total, self.current + 1)
        filled = int(self.width * self.current / self.total)
        bar = "#" * filled + "-" * (self.width - filled)
        print(f"[{bar}] {self.current}/{self.total} {msg}", flush=True)

    def log(self, msg: str) -> None:
        print(msg, flush=True)


def _try_import_neo4j():
    try:
        from neo4j import GraphDatabase  # type: ignore

        return GraphDatabase
    except Exception as e:
        raise RuntimeError(
            "缺少 neo4j Python driver。请在服务器环境安装：pip install neo4j\n"
            f"Import error: {e}"
        )


@dataclass
class Neo4jConn:
    uri: str
    username: str
    password: str


def _run(session, cypher: str, params: Optional[dict] = None) -> List[dict]:
    result = session.run(cypher, params or {})
    return [dict(r) for r in result]


def _safe_label(label: str) -> str:
    # 用于构造 MATCH (n:`label`)
    return f"`{label}`" if not label.startswith("`") else label


def _extract_rel_types_from_text(text: str) -> List[str]:
    # -[:REL]-> / <-[:REL]- / -[:REL]- 关系提取
    # 允许中文关系名（但这里我们只做提示/比对）
    rels = re.findall(r"\-\s*\[\s*:\s*([A-Za-z0-9_\u4e00-\u9fff]+)\s*\]\s*\-", text)
    return rels


def _extract_prop_keys_from_text(text: str) -> List[str]:
    # 粗略提取形如 n.prop / g.prop / sv.SVTYPE 的 prop
    # 只取在 Cypher 语句里常见的 <var>.<prop> 模式
    props = re.findall(r"\b[A-Za-z_]\w*\.\s*([A-Za-z_]\w*)\b", text)
    return props


def _extract_codeblocks_from_py(path: Path) -> List[str]:
    """
    从 .py 文件中提取三引号字符串里出现的 ```code``` 块内容（通常是 Cypher 示例）。
    目的是降低误报，避免扫到非 Cypher 文本。
    """
    s = path.read_text(encoding="utf-8", errors="ignore")
    blocks: List[str] = []

    # 提取 markdown code fences
    for m in re.finditer(r"```(?:cypher)?\s*([\s\S]*?)```", s, re.IGNORECASE):
        code = m.group(1).strip()
        if "MATCH" in code or "RETURN" in code:
            blocks.append(code)
    return blocks


def audit_business_schema(session, log: Callable[[str], None]) -> Dict[str, Any]:
    def q(name: str, cypher: str, params: Optional[dict] = None) -> List[dict]:
        t0 = time.time()
        log(f"  - running: {name}")
        rows = _run(session, cypher, params)
        log(f"    done: {name} rows={len(rows)} time={time.time() - t0:.2f}s")
        return rows

    labels_rows = q("CALL db.labels()", "CALL db.labels()")
    rel_rows = q("CALL db.relationshipTypes()", "CALL db.relationshipTypes()")
    prop_rows = q("CALL db.propertyKeys()", "CALL db.propertyKeys()")

    labels = [r.get("label") for r in labels_rows if r.get("label")]
    rel_types = [r.get("relationshipType") for r in rel_rows if r.get("relationshipType")]
    prop_keys = [r.get("propertyKey") for r in prop_rows if r.get("propertyKey")]

    labels_sorted = sorted(set(labels))
    rel_sorted = sorted(set(rel_types))
    props_sorted = sorted(set(prop_keys))

    # 关键节点：计数 + 一条样本属性键
    key_labels = [
        "Gene",
        "Chromosome",
        "Position",
        "Accession",
        "Structural_Variations",
        "TE",
        "Mutant",
        "OGI",
        "Expression",
        "mRNA",
        "Protein",
    ]
    nodes: Dict[str, Any] = {}
    for lb in key_labels:
        if lb not in labels_sorted:
            continue
        cnt = q(f"count({lb})", f"MATCH (n:{_safe_label(lb)}) RETURN count(n) AS count")
        props = q(f"keys({lb}) sample", f"MATCH (n:{_safe_label(lb)}) WITH n LIMIT 1 RETURN keys(n) AS props")
        nodes[lb] = {
            "count": cnt[0]["count"] if cnt else 0,
            "sample_props": sorted(props[0]["props"]) if props and props[0].get("props") else [],
        }

    # Gene 出边关系（采样）
    gene_edges = q(
        "Gene outgoing edges sample",
        """
        MATCH (g:Gene)-[r]->(n)
        RETURN DISTINCT type(r) AS rel_type, labels(n) AS target_labels
        ORDER BY rel_type
        LIMIT 200
        """,
    )
    # SV 出边关系（采样）
    sv_edges = []
    if "Structural_Variations" in labels_sorted:
        sv_edges = q(
            "SV outgoing edges sample",
            """
            MATCH (sv:Structural_Variations)-[r]->(n)
            RETURN DISTINCT type(r) AS rel_type, labels(n) AS target_labels
            ORDER BY rel_type
            LIMIT 200
            """,
        )

    return {
        "labels": labels_sorted,
        "relationshipTypes": rel_sorted,
        "propertyKeys": props_sorted,
        "key_nodes": nodes,
        "gene_edges_sample": gene_edges,
        "sv_edges_sample": sv_edges,
    }


def audit_mdr_metadata(session, log: Callable[[str], None]) -> Dict[str, Any]:
    def q(name: str, cypher: str, params: Optional[dict] = None) -> List[dict]:
        t0 = time.time()
        log(f"  - running: {name}")
        rows = _run(session, cypher, params)
        log(f"    done: {name} rows={len(rows)} time={time.time() - t0:.2f}s")
        return rows

    # MDR 相关标签（中文）
    mdr_labels = {
        "DEC": "数据元概念",
        "DE": "数据元",
        "VD": "值域",
        "VDG": "值域组",
        "PEV": "可允许值",
        "VLM": "值含义",
    }

    counts: Dict[str, int] = {}
    for k, lb in mdr_labels.items():
        try:
            r = q(f"count({lb})", f"MATCH (n:{_safe_label(lb)}) RETURN count(n) AS c")
            counts[k] = int(r[0]["c"]) if r else 0
        except Exception:
            counts[k] = 0

    # VD -> (VDG) -> PEV 统计
    vd_pv = []
    vd_without_values = []
    try:
        vd_pv = q(
            "VD -> VDG -> PEV (collect values)",
            """
            MATCH (vd:`值域`)
            OPTIONAL MATCH (vd)-[:组]->(vdg:`值域组`)-[:可允许值]->(pv:`可允许值`)
            RETURN vd.name AS vd_name, count(DISTINCT pv) AS pv_count, collect(DISTINCT pv.name) AS pv_values
            ORDER BY pv_count ASC, vd_name
            """,
        )
        for row in vd_pv:
            if int(row.get("pv_count") or 0) == 0:
                vd_without_values.append(row.get("vd_name"))
    except Exception:
        pass

    # PEV -> VLM 映射覆盖
    pev_total = 0
    pev_with_vlm = 0
    pev_without_vlm_samples: List[str] = []
    try:
        r1 = q("count(PEV)", "MATCH (pv:`可允许值`) RETURN count(pv) AS c")
        pev_total = int(r1[0]["c"]) if r1 else 0
        r2 = q("count(PEV with VLM)", "MATCH (pv:`可允许值`)-[:值含义]->(vm:`值含义`) RETURN count(pv) AS c")
        pev_with_vlm = int(r2[0]["c"]) if r2 else 0
        r3 = q(
            "PEV without VLM samples",
            """
            MATCH (pv:`可允许值`)
            WHERE NOT (pv)-[:值含义]->(:`值含义`)
            RETURN pv.name AS name
            LIMIT 20
            """,
        )
        pev_without_vlm_samples = [x.get("name") for x in r3 if x.get("name")]
    except Exception:
        pass

    # 关键值域抽样
    key_vds = ["Stand", "Strand", "Structural Variation Type", "SV_Type", "Transposable Elements Type", "TE_Type", "Accession", "OGI Class", "OGI_Class"]
    key_vd_values: Dict[str, List[str]] = {}
    for vd_name in key_vds:
        try:
            r = q(
                f"key VD values: {vd_name}",
                """
                MATCH (vd:`值域` {name: $vd_name})-[:组]->(vdg:`值域组`)-[:可允许值]->(pv:`可允许值`)
                RETURN collect(DISTINCT pv.name) AS values
                """,
                {"vd_name": vd_name},
            )
            if r and r[0].get("values"):
                key_vd_values[vd_name] = sorted([str(v) for v in r[0]["values"] if v is not None])
        except Exception:
            continue

    return {
        "counts": counts,
        "vd_pv_stats": vd_pv[:200],  # 防止太大
        "vd_without_values": vd_without_values,
        "pev_total": pev_total,
        "pev_with_vlm": pev_with_vlm,
        "pev_without_vlm_samples": pev_without_vlm_samples,
        "key_value_domains": key_vd_values,
    }


def audit_tool_templates(
    repo_root: Path,
    relationship_types: Sequence[str],
    property_keys: Sequence[str],
    log: Callable[[str], None],
) -> Dict[str, Any]:
    rel_set = set(relationship_types)
    prop_set = set(property_keys)

    tool_files = []
    for pattern in [
        "experiment/tools/*.py",
        "rice_Python/App/chat/tools/*.py",
    ]:
        tool_files.extend(sorted(repo_root.glob(pattern)))

    findings = []
    total = len(tool_files)
    for i, fp in enumerate(tool_files, start=1):
        log(f"  - scanning tool templates: {i}/{total} {fp.relative_to(repo_root)}")
        codeblocks = _extract_codeblocks_from_py(fp)
        if not codeblocks:
            continue
        rels = []
        props = []
        for block in codeblocks:
            rels.extend(_extract_rel_types_from_text(block))
            props.extend(_extract_prop_keys_from_text(block))

        # 只保留可能是关系/属性的“候选项”
        rels = sorted(set(rels))
        props = sorted(set(props))

        unknown_rels = [r for r in rels if r not in rel_set]
        unknown_props = [p for p in props if p not in prop_set]

        if unknown_rels or unknown_props:
            findings.append(
                {
                    "file": str(fp.relative_to(repo_root)),
                    "unknown_relationship_types": unknown_rels,
                    "unknown_property_keys": unknown_props[:200],
                }
            )

    return {
        "scanned_files": [str(p.relative_to(repo_root)) for p in tool_files],
        "findings": findings,
        "summary": {
            "files_scanned": len(tool_files),
            "files_with_issues": len(findings),
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    bs = report["business_schema"]
    mdr = report["mdr_metadata"]
    tmpl = report["tool_template_audit"]

    lines: List[str] = []
    lines.append("# Neo4j 数据字典 + MDR 元数据 审计报告\n")

    lines.append("## 1) 连接信息\n")
    lines.append(f"- **NEO4J_URI**: `{report['conn']['uri']}`\n")

    lines.append("## 2) 业务图谱 Schema 字典\n")
    lines.append(f"- **labels**: {len(bs['labels'])}\n")
    lines.append(f"- **relationshipTypes**: {len(bs['relationshipTypes'])}\n")
    lines.append(f"- **propertyKeys**: {len(bs['propertyKeys'])}\n")

    lines.append("\n### 2.1 关键节点统计\n")
    for lb, info in bs.get("key_nodes", {}).items():
        lines.append(f"- **{lb}**: count={info.get('count', 0)}, props={info.get('sample_props', [])}\n")

    lines.append("\n### 2.2 Gene 出边关系采样（前 200）\n")
    for row in bs.get("gene_edges_sample", [])[:50]:
        lines.append(f"- (Gene)-[:{row.get('rel_type')}]->{row.get('target_labels')}\n")
    if len(bs.get("gene_edges_sample", [])) > 50:
        lines.append(f"- ... more: {len(bs.get('gene_edges_sample', [])) - 50}\n")

    lines.append("\n## 3) MDR 元数据字典审计\n")
    lines.append("### 3.1 MDR 节点计数\n")
    for k, c in mdr.get("counts", {}).items():
        lines.append(f"- **{k}**: {c}\n")

    lines.append("\n### 3.2 VD 完整性\n")
    lines.append(f"- **VD without any PEV**: {len(mdr.get('vd_without_values', []))}\n")
    if mdr.get("vd_without_values"):
        lines.append(f"  - samples: {mdr.get('vd_without_values', [])[:20]}\n")

    lines.append("\n### 3.3 PEV→VLM 映射覆盖\n")
    lines.append(f"- **PEV total**: {mdr.get('pev_total', 0)}\n")
    lines.append(f"- **PEV with VLM**: {mdr.get('pev_with_vlm', 0)}\n")
    if mdr.get("pev_without_vlm_samples"):
        lines.append(f"- **PEV without VLM (samples)**: {mdr.get('pev_without_vlm_samples')}\n")

    lines.append("\n### 3.4 关键值域（若存在）\n")
    for name, values in mdr.get("key_value_domains", {}).items():
        lines.append(f"- **{name}**: {values[:50]}{' ...' if len(values) > 50 else ''}\n")

    lines.append("\n## 4) Tools Cypher 模板与数据库字典一致性\n")
    lines.append(f"- **files_scanned**: {tmpl.get('summary', {}).get('files_scanned', 0)}\n")
    lines.append(f"- **files_with_issues**: {tmpl.get('summary', {}).get('files_with_issues', 0)}\n")

    if tmpl.get("findings"):
        lines.append("\n### 4.1 发现的问题（文件级别）\n")
        for f in tmpl["findings"][:30]:
            lines.append(f"- **{f['file']}**\n")
            if f.get("unknown_relationship_types"):
                lines.append(f"  - unknown_relationship_types: {f['unknown_relationship_types']}\n")
            if f.get("unknown_property_keys"):
                lines.append(f"  - unknown_property_keys(sample): {f['unknown_property_keys'][:30]}\n")
        if len(tmpl["findings"]) > 30:
            lines.append(f"\n... more findings: {len(tmpl['findings']) - 30}\n")

    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Neo4j business schema + MDR metadata completeness")
    parser.add_argument("--uri", type=str, default=None, help="Neo4j bolt URI (override Config/env)")
    parser.add_argument("--username", type=str, default=None, help="Neo4j username (override Config/env)")
    parser.add_argument("--password", type=str, default=None, help="Neo4j password (override Config/env)")
    parser.add_argument("--out-dir", type=str, required=True, help="Output directory for audit reports")
    args = parser.parse_args()

    uri, username, password = _load_config()
    if args.uri:
        uri = args.uri
    if args.username:
        username = args.username
    if args.password:
        password = args.password

    out_dir = Path(args.out_dir)
    _ensure_out_dir(out_dir)

    progress = StepProgress(total=6)
    progress.step("Loading config")
    progress.log(f"NEO4J_URI={uri}")

    GraphDatabase = _try_import_neo4j()
    progress.step("Creating Neo4j driver")
    driver = GraphDatabase.driver(uri, auth=(username, password))

    report: Dict[str, Any] = {
        "conn": {"uri": uri, "username": username, "password_masked": "*" * len(password)},
        "business_schema": {},
        "mdr_metadata": {},
        "tool_template_audit": {},
    }

    progress.step("Verifying connectivity")
    try:
        t0 = time.time()
        driver.verify_connectivity()
        progress.log(f"connectivity OK ({time.time() - t0:.2f}s)")
    except Exception as e:
        # 兼容旧版本 driver / 或某些环境不支持 verify_connectivity
        progress.log(f"connectivity check skipped/failed: {e}")

    with driver.session() as session:
        progress.step("Auditing business schema (labels/relTypes/propertyKeys/edges)")
        report["business_schema"] = audit_business_schema(session, log=progress.log)

        progress.step("Auditing MDR metadata (DEC/VD/MPS completeness)")
        report["mdr_metadata"] = audit_mdr_metadata(session, log=progress.log)

    bs = report["business_schema"]
    progress.step("Scanning tool Cypher templates vs schema dictionary")
    report["tool_template_audit"] = audit_tool_templates(
        repo_root=PROJECT_ROOT,
        relationship_types=bs.get("relationshipTypes", []),
        property_keys=bs.get("propertyKeys", []),
        log=progress.log,
    )

    progress.step("Writing reports")
    json_path = out_dir / "schema_audit.json"
    md_path = out_dir / "schema_audit.md"
    _json_dump(report, json_path)
    _md_write(render_markdown(report), md_path)

    print(f"✅ Audit completed.\n- JSON: {json_path}\n- MD:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


