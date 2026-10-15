"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/02/20 17:41
"""
from ..llm import llm
from ..graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from typing import AnyStr

CYPHER_GENERATION_TEMPLATE = """
您是一名专业的Neo4j开发专家，负责将用户关于水稻基因基本信息的问题转换为Cypher查询语句。
请根据以下模式将用户问题转换为Cypher查询。

注意事项：
1. 仅使用模式中提供的关系类型和属性
2. 禁止使用模式中未定义的关系类型或属性
3. 基因名称存储在 Gene 节点的 "name" 属性中

⚠️ 严格约束（必须遵守，否则查询会失败）:
1. Gene 节点没有 strand 属性（不要写 g.strand / g.Strand / g.strand_direction 等）
2. 不存在 :position 关系！只能使用 :start_pos 和 :end_pos
3. 对于DNA序列、CDS序列、蛋白质序列的查询，只返回基因的URL即可
4. ⚠️ 对于 mRNA/转录本 查询，必须返回转录本列表（字段名必须是 transcripts），不要只返回 URL 或 mrna_count

🚫🚫🚫 禁止使用的关系和属性（会导致查询失败）🚫🚫🚫
- ❌ -[:strand]->  不存在此关系！
- ❌ -[:position]-> 不存在此关系！
- ❌ g.strand      Gene节点没有strand属性！
- ✅ 正确做法：使用真实关系 (Gene)-[:strand_info]->(Strand) 并返回 st.name

Cypher示例：

**示例1：查询基因所在的链（正链/负链）**
问题：Os02428G0380001552.01基因所在的DNA链是正链还是负链？
⚠️ 重要：
- 数据库真实关系是：`(Gene)-[:strand_info]->(Strand)`（不是 `:strand`）
- ✅ 统一做法：直接返回 `st.name AS strand`（值一般为 `+/-` 或 `正链/负链`，由渲染层做归一化）
```
MATCH (g:Gene) -[:chromosome_no]-> (c:Chromosome) 
MATCH (g) -[:start_pos]-> (sp:Position)
MATCH (g) -[:end_pos]-> (ep:Position)
MATCH (g) -[:strand_info]-> (st:Strand)
WHERE g.name = 'Os02428G0380001552.01' 
RETURN
  g.URL as gene_url,
  c.name as chromosome,
  sp.name as start_pos,
  ep.name as end_pos,
  st.name AS strand
```

**示例2：查询基因的mRNA转录本**
问题：OsN22_01G017170基因注释中记录的mRNA转录本有哪些？
```
MATCH (g:Gene)-[:has_a_transcript]->(m:mRNA)
WHERE g.name = 'OsN22_01G017170'
RETURN collect(m.name) AS transcripts
```

**示例3：查询基因的DNA序列**
问题：TMG0203363700.01基因的完整DNA序列是什么？
```
MATCH (g:Gene)
WHERE g.name = 'TMG0203363700.01' 
RETURN g.URL as gene_url
```

**示例4：查询基因的CDS序列**
问题：OsII32G0309435900.01基因的编码区全序列？
```
MATCH (g:Gene)
WHERE g.name = 'OsII32G0309435900.01' 
RETURN g.URL as gene_url
```

**示例5：查询基因的蛋白质序列**
问题：OsII32G0825878500.01基因编码的蛋白质完整氨基酸序列是什么？
```
MATCH (g:Gene)
WHERE g.name = 'OsII32G0825878500.01' 
RETURN g.URL as gene_url
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

gene_basic_info_query = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    return_direct=True,
    allow_dangerous_requests=True,
    top_k=1000,
)

# chain = GraphCypherQAChain.from_llm(
#     llm,
#     graph=graph,
#     verbose=True,
#     cypher_prompt=cypher_prompt,
#     return_direct=True,
#     allow_dangerous_requests=True,
#     top_k=1000,
# )


# @tool
# def gene_basic_info_query(query: AnyStr):
#     """
#     使用Cypher提供水稻基因的基本信息。
#     包括位置信息（染色体、起始/终止位点）、转录本（mRNA）、蛋白质序列、DNA序列、CDS序列等。
#     输入为自然语言描述的问题。
#     """
#     print("gene_basic_info_query is running...")
#     print("query: ", query)
#     response = chain.invoke({"query": query})
#     print("gene_basic_info_query is done.")
#     print(response)
#     return response["result"]
