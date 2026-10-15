"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 15:37
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from ..llm import llm
from ..graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

CYPHER_GENERATION_TEMPLATE = """
你是一名专业的Neo4j开发专家，负责将用户问题转化为 Cypher 语句，以回答水稻基因的上下游或特定区域内的基因查询。
请根据以下模式将用户问题转换为 Cypher 查询。

⚠️⚠️⚠️ 最重要的约束 ⚠️⚠️⚠️
1. 只输出 Cypher 语句，禁止输出 SQL、解释文字或其他内容
2. 查询某个基因的上游/下游基因时，必须约束返回同一品种(Accession)的基因
3. 基因名格式包括：OsXXX_NNgNNNNNNN, LOC_OsNNgNNNNN, TMGxxxxxxxx.xx, R9311CxxgNNNNN 等

🚫🚫🚫 Cypher 禁令（严格遵守）🚫🚫🚫
1. **严禁**使用 `RETURN count(n)` 或 `count(g2)`！必须返回完整的基因名列表 `RETURN g2.name AS gene_name`
2. 即使用户问"有多少个基因"，也要返回完整列表，让渲染层去计数，不要在 Cypher 里计数！
3. **严禁**省略 gene_name 字段，必须返回 `g2.name AS gene_name`

注意事项：
1. 仅使用模式中提供的关系类型和属性
2. 禁止使用模式中未定义的关系类型或属性
3. 不要返回完整节点或嵌入属性
4. 禁止使用 BETWEEN 语法；若需要范围过滤，请显式写成 toInteger(value) >= 起点 AND toInteger(value) <= 终点
5. 如果题目使用 "kb" 单位，请将其转换为碱基数（乘以 1000）后再写入常量
6. 染色体格式为 Chr01-Chr12（两位数字）
7. 品种名格式多样，包括：Azucena, Y3551, DHX2, OsLiXu, OsARC, TMG 等
8. 查询中只允许一个 RETURN 语句，且必须出现在 Cypher 的最后一行；不要在 WITH 之前或中间添加 RETURN。
9. ⚠️ 范围邻近基因（上/下游 N kb）必须使用“完全落入范围”定义（避免多返回 1 个基因）：
   - 上游 N kb（默认以 g1.start_pos 为锚点）：toInteger(g2.end_pos) < toInteger(g1.start_pos) 且 toInteger(g2.start_pos) >= toInteger(g1.start_pos) - N
   - 下游 N kb（默认以 g1.end_pos 为锚点）：toInteger(g2.start_pos) > toInteger(g1.end_pos) 且 toInteger(g2.end_pos) <= toInteger(g1.end_pos) + N

Cypher 语句示例：

1.  查询基因OsARC_03g0037750的上游100kb范围内的基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:type]->(a1:Accession),
      (g1)-[:start_pos]->(p1s:Position),
      (g1)-[:end_pos]->(p1e:Position)
WHERE g1.name = 'OsARC_03g0037750'
WITH c, a1, toInteger(p1s.name) AS anchor_start
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2s:Position),
      (g2)-[:end_pos]->(p2e:Position),
      (g2)-[:type]->(a2:Accession)
WHERE a1.name = a2.name
  AND toInteger(p2e.name) < anchor_start
  AND toInteger(p2s.name) >= (anchor_start - 100000)
RETURN g2.name AS gene_name
```

2.  查询基因OsARC_03g003775的下游100kb范围内的基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:type]->(a1:Accession),
      (g1)-[:start_pos]->(p1s:Position),
      (g1)-[:end_pos]->(p1e:Position)
WHERE g1.name = 'OsARC_03g0037750'
WITH c, a1, toInteger(p1e.name) AS anchor_end
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2s:Position),
      (g2)-[:end_pos]->(p2e:Position),
      (g2)-[:type]->(a2:Accession)
WHERE a1.name = a2.name
  AND toInteger(p2s.name) > anchor_end
  AND toInteger(p2e.name) <= (anchor_end + 100000)
RETURN g2.name AS gene_name
```

3.  查询基因OsARC_03g003775的上游最近的基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:start_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'OsARC_03g0037750'
WITH g1, c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:end_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name < p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name DESC
LIMIT 1
```

4.  查询基因OsARC_03g003775的下游最近的基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:end_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'OsARC_03g0037750'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name > p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name
LIMIT 1
```

5.  查询 Azucena 一号染色体 100000-150000 区域的所有基因。
注意：查询区域内基因时，使用"区间交集"条件：start_pos <= 区域终点 AND end_pos >= 区域起点
```
MATCH (acc:Accession) WHERE acc.name = 'Azucena'
MATCH (chr:Chromosome) WHERE chr.name = 'Chr01'
MATCH (g:Gene)-[:type]->(acc)
MATCH (g)-[:chromosome_no]->(chr)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE toInteger(sp.name) <= 150000 AND toInteger(ep.name) >= 100000
RETURN g.name AS gene_name
ORDER BY toInteger(sp.name)
```

6.  查询 Y3551 品种 Chr02 染色体 5000-8000 区域的所有基因。
注意：使用"区间交集"条件，确保捕获所有与区域有重叠的基因
```
MATCH (acc:Accession) WHERE acc.name = 'Y3551'
MATCH (chr:Chromosome) WHERE chr.name = 'Chr02'
MATCH (g:Gene)-[:type]->(acc)
MATCH (g)-[:chromosome_no]->(chr)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE toInteger(sp.name) <= 8000 AND toInteger(ep.name) >= 5000
RETURN g.name AS gene_name
ORDER BY toInteger(sp.name)
```

7.  查询基因OsLiXu_02g0032830的上游最近5个基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:start_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'OsLiXu_02g0032830'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:end_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name < p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name DESC
LIMIT 5
```

8.  查询基因TMG0307888400.01的下游最近5个基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:end_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'TMG0307888400.01'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name > p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name
LIMIT 5
```

9.  查询参考基因组基因 Os10g0463600 的上游最近7个基因（无需 Accession 约束）。
⚠️ 当基因名格式为 OsXXgXXXXXXX 或 LOC_OsXXgXXXXX（IRGSP参考基因组）时，不需要 Accession 约束。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:start_pos]->(p1:Position)
WHERE g1.name = 'Os10g0463600'
WITH c, p1
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:end_pos]->(p2:Position)
WHERE p2.name < p1.name AND g2.name STARTS WITH 'Os10g'
RETURN g2.name AS gene_name
ORDER BY p2.name DESC
LIMIT 7
```

10. 查询参考基因组基因 Os10g0463600 的下游最近5个基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:end_pos]->(p1:Position)
WHERE g1.name = 'Os10g0463600'
WITH c, p1
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2:Position)
WHERE p2.name > p1.name AND g2.name STARTS WITH 'Os10g'
RETURN g2.name AS gene_name
ORDER BY p2.name
LIMIT 5
```

11. 查询 R9311C03g11777 上游最近3个基因（同品种约束）。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:start_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'R9311C03g11777'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:end_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name < p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name DESC
LIMIT 3
```

12. 查询 OsLima_09g0002600 下游最近5个基因（同品种约束）。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:end_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'OsLima_09g0002600'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name > p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name
LIMIT 5
```

13. 查询 OsZS97_03G0203900 尾部后面（下游）25kb 范围内的基因（同品种约束）。
⚠️ 注意："尾部后面" 表示基因结束位置的下游，必须使用 end_pos 作为起点。
⚠️ 关键：必须约束 a1.name = a2.name 确保返回同一品种的基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:type]->(a1:Accession),
      (g1)-[:end_pos]->(p1:Position)
WHERE g1.name = 'OsZS97_03G0203900'
WITH c, a1, p1
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2:Position),
      (g2)-[:type]->(a2:Accession)
WHERE p2.name > p1.name
  AND p2.name <= (p1.name + 25000)
  AND a1.name = a2.name
RETURN g2.name AS gene_name
ORDER BY p2.name
```

14. 查询 Os02428G0100443200.01 上游方向第一个基因（同品种约束）。
⚠️ 基因名格式 Os02428G... 属于 02428 品种，必须约束 Accession。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:start_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'Os02428G0100443200.01'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:end_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name < p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name DESC
LIMIT 1
```

15. 查询 Oglab_018058 后面紧接着的3个基因（同品种约束）。
⚠️ 基因名格式 Oglab_... 属于 Oglab 品种。
⚠️ "后面紧接着" 表示下游最近的几个基因。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:end_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'Oglab_018058'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name > p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name
LIMIT 3
```

16. 查询 OsIR64_05g0022620 的DNA链下游方向6个基因（同品种约束）。
⚠️ 基因名格式 OsIR64_... 属于 IR64 品种。
```
MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
      (g1)-[:end_pos]->(p1:Position),
      (g1)-[:type]->(a:Accession)
WHERE g1.name = 'OsIR64_05g0022620'
WITH c, p1, a
MATCH (g2:Gene)-[:chromosome_no]->(c),
      (g2)-[:start_pos]->(p2:Position),
      (g2)-[:type]->(a)
WHERE p2.name > p1.name
RETURN g2.name AS gene_name
ORDER BY p2.name
LIMIT 6
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

# ---------------------------
# Deterministic helpers
# ---------------------------

GENE_NAME_PATTERNS = [
    r"(LOC_Os\d+g\d+(?:\.\d+)?)",
    r"(Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?)",
    r"(Os[A-Za-z0-9_]+_\d+[Gg]\d+(?:\.\d+)?)",
    r"(R\d+C\d+g\d+)",
    r"(Oglab_\d+)",
    r"(TMG\d+(?:\.\d+)?)",
    r"(Os\d{2}g\d+(?:\.\d+)?)",
]

ACCESSION_PATTERNS = [
    r'([A-Za-z0-9_]+)品种',
    r'([A-Za-z0-9_]+)的Chr',
    r'([A-Za-z0-9_]+)的染色体',
    r'([A-Za-z0-9_]+)染色体',
    r'\b([A-Za-z]{2,}\d{0,4})\b',
    r'\b(\d{5,6})\b',
]

CHINESE_NUMERAL_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}


def _escape_cypher_str(value: str) -> str:
    return value.replace("'", "\\'")


def _extract_gene_name(question: str) -> Optional[str]:
    if not question:
        return None
    for pattern in GENE_NAME_PATTERNS:
        m = re.search(pattern, question, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _extract_accession_name(question: str) -> Optional[str]:
    if not question:
        return None
    for pattern in ACCESSION_PATTERNS:
        m = re.search(pattern, question)
        if m:
            candidate = m.group(1)
            if candidate.lower().startswith("chr"):
                continue
            return candidate
    return None


def _chinese_to_int(text: str) -> Optional[int]:
    if not text:
        return None
    if text in CHINESE_NUMERAL_MAP:
        return CHINESE_NUMERAL_MAP[text]
    if text.endswith("十") and len(text) == 2:
        base = CHINESE_NUMERAL_MAP.get(text[0], 0)
        return base * 10
    if text.startswith("十") and len(text) == 2:
        base = CHINESE_NUMERAL_MAP.get(text[1], 0)
        return 10 + base
    return None


def _extract_chromosome_label(question: str) -> Optional[str]:
    if not question:
        return None
    match = re.search(r'Chr\s*0*(\d+)', question, re.IGNORECASE)
    if match:
        return f"Chr{int(match.group(1)):02d}"
    for pattern in [r'染色体([一二三四五六七八九十]{1,3})号', r'([一二三四五六七八九十]{1,3})号染色体']:
        m = re.search(pattern, question)
        if m:
            num = _chinese_to_int(m.group(1))
            if num:
                return f"Chr{num:02d}"
    return None


def _extract_coordinate_range(question: str) -> Tuple[Optional[int], Optional[int]]:
    if not question:
        return None, None
    text = question.replace(",", "")
    match = re.search(r'Chr\d+\s*[:：]\s*(\d+)\s*[-–~～]\s*(\d+)', text, re.IGNORECASE)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return min(start, end), max(start, end)
    match = re.search(r'(\d+)\s*kb\s*(?:到|[-–~～])\s*(\d+)\s*kb', text, re.IGNORECASE)
    if match:
        start = int(match.group(1)) * 1000
        end = int(match.group(2)) * 1000
        return min(start, end), max(start, end)
    match = re.search(r'(\d+)\s*(?:kb)?\s*(?:到|[-–~～])\s*(\d+)\s*(?:bp|碱基)?', text, re.IGNORECASE)
    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        if 'kb' in text[match.start():match.end()].lower():
            start *= 1000
            end *= 1000
        return min(start, end), max(start, end)
    return None, None


def _extract_kb_distance(question: str) -> Optional[int]:
    if not question:
        return None
    m = re.search(r'(\d+)\s*kb', question, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 1000
    return None


def _extract_neighbor_count(question: str) -> Optional[int]:
    if not question:
        return None
    for m in re.finditer(r'(\d+)\s*个', question):
        span = question[max(0, m.start() - 3):m.end() + 3].lower()
        if 'kb' in span:
            continue
        return int(m.group(1))
    return None


def _detect_direction(question: str) -> Optional[str]:
    if not question:
        return None
    if any(k in question for k in ["上游", "前面", "头部", "起始", "起始点", "上一个", "左边"]):
        return "upstream"
    if any(k in question for k in ["下游", "后面", "尾部", "结束", "终止", "下一个", "右边"]):
        return "downstream"
    return None


def _is_reference_gene(gene: str) -> bool:
    if not gene:
        return False
    return bool(re.match(r'^(?:LOC_Os\d+g\d+(?:\.\d+)?|Os\d{2}g\d+(?:\.\d+)?)$', gene, re.IGNORECASE))


def _reference_gene_prefix(gene: str) -> Optional[str]:
    if not gene:
        return None
    m = re.match(r'^(LOC_Os\d{2}g)\d+(?:\.\d+)?$', gene, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.match(r'^(Os\d{2}g)\d+(?:\.\d+)?$', gene, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _query_graph(query: str) -> Optional[List[Dict[str, Any]]]:
    if not graph:
        return None
    try:
        records = graph.query(query)
    except Exception:
        return None
    return records if records else None


def _format_gene_results(genes: List[str], question: str) -> str:
    payload = {"query": question, "result": [{"gene_name": g} for g in genes]}
    return json.dumps(payload, ensure_ascii=False)


def _query_region(accession: str, chromosome: str, start_bp: int, end_bp: int) -> Optional[List[str]]:
    acc = _escape_cypher_str(accession)
    chr_label = _escape_cypher_str(chromosome)
    query = f"""
    MATCH (acc:Accession {{name: '{acc}'}})
    MATCH (chr:Chromosome {{name: '{chr_label}'}})
    MATCH (g:Gene)-[:type]->(acc)
    MATCH (g)-[:chromosome_no]->(chr)
    MATCH (g)-[:start_pos]->(sp:Position)
    MATCH (g)-[:end_pos]->(ep:Position)
    WHERE toInteger(sp.name) <= {end_bp} AND toInteger(ep.name) >= {start_bp}
    RETURN g.name AS gene_name
    ORDER BY toInteger(sp.name)
    """
    records = _query_graph(query)
    if not records:
        return None
    return [r.get("gene_name") for r in records if r.get("gene_name")]


def _query_adjacent_range(gene: str, direction: str, distance_bp: int) -> Optional[List[str]]:
    gene_safe = _escape_cypher_str(gene)
    use_accession = not _is_reference_gene(gene)
    prefix = _reference_gene_prefix(gene) if not use_accession else None
    prefix_safe = _escape_cypher_str(prefix) if prefix else None
    if direction == "upstream":
        anchor_pos = "p1s"
        where_range = f"toInteger(p2e.name) < anchor AND toInteger(p2s.name) >= (anchor - {distance_bp})"
    else:
        anchor_pos = "p1e"
        where_range = f"toInteger(p2s.name) > anchor AND toInteger(p2e.name) <= (anchor + {distance_bp})"
    if use_accession:
        query = f"""
        MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
              (g1)-[:type]->(a1:Accession),
              (g1)-[:start_pos]->(p1s:Position),
              (g1)-[:end_pos]->(p1e:Position)
        WHERE g1.name = '{gene_safe}'
        WITH c, a1, toInteger({anchor_pos}.name) AS anchor
        MATCH (g2:Gene)-[:chromosome_no]->(c),
              (g2)-[:start_pos]->(p2s:Position),
              (g2)-[:end_pos]->(p2e:Position),
              (g2)-[:type]->(a2:Accession)
        WHERE a1.name = a2.name
          AND {where_range}
        RETURN g2.name AS gene_name
        """
    else:
        prefix_clause = f" AND g2.name STARTS WITH '{prefix_safe}'" if prefix_safe else ""
        query = f"""
        MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
              (g1)-[:start_pos]->(p1s:Position),
              (g1)-[:end_pos]->(p1e:Position)
        WHERE g1.name = '{gene_safe}'
        WITH c, toInteger({anchor_pos}.name) AS anchor
        MATCH (g2:Gene)-[:chromosome_no]->(c),
              (g2)-[:start_pos]->(p2s:Position),
              (g2)-[:end_pos]->(p2e:Position)
        WHERE {where_range}{prefix_clause}
        RETURN g2.name AS gene_name
        """
    records = _query_graph(query)
    if not records:
        return None
    return [r.get("gene_name") for r in records if r.get("gene_name")]


def _query_adjacent_nearest(gene: str, direction: str, count: int) -> Optional[List[str]]:
    gene_safe = _escape_cypher_str(gene)
    use_accession = not _is_reference_gene(gene)
    prefix = _reference_gene_prefix(gene) if not use_accession else None
    prefix_safe = _escape_cypher_str(prefix) if prefix else None
    if direction == "upstream":
        anchor_pos = "p1s"
        where_dir = "toInteger(p2e.name) < anchor"
        order_by = "toInteger(p2e.name) DESC"
    else:
        anchor_pos = "p1e"
        where_dir = "toInteger(p2s.name) > anchor"
        order_by = "toInteger(p2s.name) ASC"
    if use_accession:
        query = f"""
        MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
              (g1)-[:type]->(a1:Accession),
              (g1)-[:start_pos]->(p1s:Position),
              (g1)-[:end_pos]->(p1e:Position)
        WHERE g1.name = '{gene_safe}'
        WITH c, a1, toInteger({anchor_pos}.name) AS anchor
        MATCH (g2:Gene)-[:chromosome_no]->(c),
              (g2)-[:start_pos]->(p2s:Position),
              (g2)-[:end_pos]->(p2e:Position),
              (g2)-[:type]->(a2:Accession)
        WHERE a1.name = a2.name
          AND {where_dir}
        RETURN g2.name AS gene_name
        ORDER BY {order_by}
        LIMIT {count}
        """
    else:
        prefix_clause = f" AND g2.name STARTS WITH '{prefix_safe}'" if prefix_safe else ""
        query = f"""
        MATCH (g1:Gene)-[:chromosome_no]->(c:Chromosome),
              (g1)-[:start_pos]->(p1s:Position),
              (g1)-[:end_pos]->(p1e:Position)
        WHERE g1.name = '{gene_safe}'
        WITH c, toInteger({anchor_pos}.name) AS anchor
        MATCH (g2:Gene)-[:chromosome_no]->(c),
              (g2)-[:start_pos]->(p2s:Position),
              (g2)-[:end_pos]->(p2e:Position)
        WHERE {where_dir}{prefix_clause}
        RETURN g2.name AS gene_name
        ORDER BY {order_by}
        LIMIT {count}
        """
    records = _query_graph(query)
    if not records:
        return None
    return [r.get("gene_name") for r in records if r.get("gene_name")]


_adjacent_chain = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    return_direct=True,
    allow_dangerous_requests=True,
    top_k=1000,
)


def _run_chain(question: str):
    try:
        result = _adjacent_chain.invoke({"query": question})
    except Exception:
        result = _adjacent_chain.run(question)
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return result


def adjacent_genes_query(question: str):
    # 1) Region query: accession + chromosome + range
    accession = _extract_accession_name(question)
    chromosome = _extract_chromosome_label(question)
    start_bp, end_bp = _extract_coordinate_range(question)
    if accession and chromosome and start_bp is not None and end_bp is not None:
        genes = _query_region(accession, chromosome, start_bp, end_bp)
        if genes:
            return _format_gene_results(genes, question)

    # 2) Gene-adjacent query
    gene = _extract_gene_name(question)
    direction = _detect_direction(question)
    if gene and direction:
        distance_bp = _extract_kb_distance(question)
        neighbor_count = _extract_neighbor_count(question)
        if distance_bp:
            genes = _query_adjacent_range(gene, direction, distance_bp)
            if genes:
                return _format_gene_results(genes, question)
        elif neighbor_count:
            genes = _query_adjacent_nearest(gene, direction, neighbor_count)
            if genes:
                return _format_gene_results(genes, question)
        elif any(k in question for k in ["最近", "第一个", "最邻近", "最接近"]):
            genes = _query_adjacent_nearest(gene, direction, 1)
            if genes:
                return _format_gene_results(genes, question)

    return _run_chain(question)
