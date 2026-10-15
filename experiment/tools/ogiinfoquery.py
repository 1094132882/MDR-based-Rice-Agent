"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 15:02
"""

from llm import llm
from graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from typing import AnyStr

CYPHER_GENERATION_TEMPLATE = """
您是Neo4j专家，将用户问题转化为Cypher语句查询OGI（直系同源基因索引）信息。

⚠️⚠️⚠️ 最重要的约束 ⚠️⚠️⚠️
关系方向必须是：(OGI)-[:has_a_gene]->(Gene)
绝对禁止写成：(Gene)-[:has_a_gene]->(OGI) ← 这会返回空结果！

Fine Tuning:
- OGI 节点的 name 格式为 "OGI:08031210"
- Gene 节点的 name 存储基因名称

Cypher 语句示例（请严格模仿）：

**示例1：基因→OGI**
问题：Os02g0692000对应的OGI编号是多少？
```
MATCH (ogi:OGI)-[:has_a_gene]->(g:Gene) 
WHERE g.name = 'Os02g0692000' 
RETURN ogi.name as ogi
```

**示例2：OGI→基因列表**
问题：OGI:08059490这个分类里有哪些水稻基因？
```
MATCH (ogi:OGI)-[:has_a_gene]->(g:Gene) 
WHERE ogi.name = 'OGI:08059490' 
RETURN g.name as gene_name
```

**示例3：基因所属OGI的成员数量**
问题：OsLaMu_09g0015600所属的OGI分组有多少个成员基因？
```
MATCH (ogi:OGI)-[:has_a_gene]->(g:Gene) 
WHERE g.name = 'OsLaMu_09g0015600'
WITH ogi
MATCH (ogi)-[:has_a_gene]->(member:Gene)
RETURN ogi.name as ogi, COUNT(member) AS member_count
```

**示例4：另一个成员数量查询**
问题：OsKY131G0511137200.01所在OGI记录的基因总数是多少？
```
MATCH (ogi:OGI)-[:has_a_gene]->(g:Gene) 
WHERE g.name = 'OsKY131G0511137200.01'
WITH ogi
MATCH (ogi)-[:has_a_gene]->(member:Gene)
RETURN ogi.name as ogi, COUNT(member) AS member_count
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

ogi_info_query = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    allow_dangerous_requests=True,
    return_direct=True,
    top_k=1000,
)

# chain = GraphCypherQAChain.from_llm(
#     llm,
#     graph=graph,
#     verbose=True,
#     cypher_prompt=cypher_prompt,
#     allow_dangerous_requests=True,
#     return_direct=True,
#     top_k=1000,
# )
#
#
# @tool
# def ogi_info_query(query: AnyStr):
#     """
#     使用Cypher查询OGI（Ortholog Gene Index，直系同源基因索引）的相关信息。
#     输入为自然语言描述的问题。
#     """
#     response = chain.invoke({"query": query})
#     return response["result"]
