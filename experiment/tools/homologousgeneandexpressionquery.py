"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 15:45
"""
import json
import re
from typing import Any, Dict, List, Optional

from llm import llm
from graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

CYPHER_GENERATION_TEMPLATE = """
你是一名专业的Neo4j开发专家，负责将将用户问题转化为Cypher语句，以回答给定水稻基因的同源基因以及表达信息相关问题。
请根据以下模式将用户问题转换为Cypher查询。

注意事项：
1. 仅使用模式中提供的关系类型和属性
2. 禁止使用模式中未定义的关系类型或属性
3. 不要返回完整节点或嵌入属性
4. 只允许一个 RETURN 语句，且必须放在查询的最后一行；不要在查询中出现多个 RETURN。


Fine Tuning:
同源基因的关系类型包含两种：SBH和RBH。
基因的 ID 或名称存储在 “name” 属性中。例如，,match(g:Gene) where g.name = 'OsY58SG0923659500.01' return g

Cypher 语句示例：

1. 查询基因OsARC_04g0000150的RBH关系的同源基因。
```
match(g1:Gene) -[:RBH]-> (g2:Gene) 
where g1.name = 'OsARC_04g0000150'
return g2.name as gene_name
```

2. 查询基因OsARC_04g0000150的RBH关系的同源基因，并返回其accession为02428的基因。
```
match(g1:Gene) -[:RBH]-> (g2:Gene),
     (g2) -[:type]-> (a:Accession)  
where g1.name = 'OsARC_04g0000150' and a.name = '02428'
return  g2.name as gene2_name, 
```

3.  查询基因OsARC_02g0004980的表达信息。
⚠️ 表达量查询必须返回所有三个组织的数据：leaf_value, root_value, young_ear_value
```
match(n:Gene) -[:measures_gene_expression]-> (m:Expression)  
where toLower(n.name) = toLower('OsARC_02g0004980') OR n.name STARTS WITH 'OsARC_02g0004980.'
with n, m order by n.name limit 1
return m.leaf_value, m.root_value, m.young_ear_value
```

4.  比较基因OsLaMu_05g0004930在根和茎中的表达差异。
⚠️ 即使问题只问了部分组织，也必须返回所有三个字段（leaf_value, root_value, young_ear_value）
```
match(n:Gene) -[:measures_gene_expression]-> (m:Expression)  
where toLower(n.name) = toLower('OsLaMu_05g0004930') OR n.name STARTS WITH 'OsLaMu_05g0004930.'
with n, m order by n.name limit 1
return m.leaf_value, m.root_value, m.young_ear_value
```

5.  查询基因OsLima_01g0000510在穗发育阶段的表达量。
⚠️ 穗发育 = young_ear_value，但仍需返回所有三个字段以提供完整信息
```
match(n:Gene) -[:measures_gene_expression]-> (m:Expression)  
where toLower(n.name) = toLower('OsLima_01g0000510') OR n.name STARTS WITH 'OsLima_01g0000510.'
with n, m order by n.name limit 1
return m.leaf_value, m.root_value, m.young_ear_value
```

⚠️ 重要约束：
- 对于任何表达量相关的查询，必须始终返回 m.leaf_value, m.root_value, m.young_ear_value 三个字段
- 不要返回 m.stem_value（数据库中没有此字段）
- 如果用户问"哪里能查表达量"，直接返回该基因的表达数据
- ⚠️ 如果基因名可能缺少版本号（如未带“.01”），必须兼容：`n.name STARTS WITH '{{gene}}.'`，并通过 `ORDER BY n.name LIMIT 1` 选定一个基因

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

_homologous_chain = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    allow_dangerous_requests=True,
    return_direct=True,
    top_k=1000,
)

GENE_NAME_PATTERNS = [
    r"(LOC_Os\d+g\d+(?:\.\d+)?)",
    r"(Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?)",
    r"(R\d+C\d+g\d+)",
    r"(Oglab_\d+)",
    r"(TMG\d+(?:\.\d+)?)",
    r"(Os\d{2}g\d+(?:\.\d+)?)",
]


def _is_expression_question(question: str) -> bool:
    if not question:
        return False
    q = question.lower()
    return any(kw in q for kw in ["表达", "expression", "leaf", "root", "young", "叶", "根", "穗", "幼穗", "茎"])


def _extract_gene_name(question: str) -> Optional[str]:
    if not question:
        return None
    for pattern in GENE_NAME_PATTERNS:
        m = re.search(pattern, question, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _query_expression(gene: str) -> Optional[List[Dict[str, Any]]]:
    if not graph or not gene:
        return None
    gene_safe = gene.replace("'", "\\'")
    gene_lower = gene_safe.lower()
    query = f"""
    MATCH (n:Gene)-[:measures_gene_expression]->(m:Expression)
    WHERE toLower(n.name) = '{gene_lower}'
       OR toLower(n.name) STARTS WITH '{gene_lower}.'
    WITH n, m ORDER BY n.name LIMIT 1
    RETURN m.leaf_value AS leaf_value, m.root_value AS root_value, m.young_ear_value AS young_ear_value
    """
    try:
        records = graph.query(query)
    except Exception:
        return None
    return records if records else None


def _run_chain(question: str):
    try:
        result = _homologous_chain.invoke({"query": question})
    except Exception:
        result = _homologous_chain.run(question)
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return result


def homologous_gene_and_expression_query(question: str):
    if _is_expression_question(question):
        gene = _extract_gene_name(question)
        if gene:
            records = _query_expression(gene)
            if records:
                payload = {"query": question, "result": records, "gene": gene}
                return json.dumps(payload, ensure_ascii=False)
    return _run_chain(question)
