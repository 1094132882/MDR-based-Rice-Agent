"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 14:54
"""
from llm import llm
from graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

CYPHER_GENERATION_TEMPLATE = """
你是一名专业的 Neo4j 开发专家，需要把关于“基因 ↔ 突变体”关系的问题转换为 Cypher 查询。

注意事项：
1. 基因名称存储在 Gene.name，突变体名称存储在 Mutant.name
2. 当问题询问"某个基因有哪些突变体"时，使用 MATCH (g:Gene) WHERE g.name = '基因名' 然后 MATCH (g)-[:has_a_mutant]->(m:Mutant) 并返回 DISTINCT m.name 作为 mutant_id
3. 当问题给出突变体名称时，使用 MATCH (m:Mutant) WHERE m.name = '突变体名' 然后 MATCH (g:Gene)-[:has_a_mutant]->(m) 并返回 DISTINCT g.name 作为 gene_name
4. 结果字段请统一为 mutant_id（突变体列表）或 gene_name（基因列表），禁止返回整节点
5. 仅使用提供的模式信息，禁止随意增加关系或属性

Fine Tuning:
基因或突变体的 ID 都存储在 “name” 属性中，例如：
```
MATCH (g:Gene) WHERE g.name = 'OsY58SG0923659500.01' RETURN g
```

Cypher 语句示例：

1. 查找某个基因的突变体：
```
MATCH (g:Gene) WHERE g.name = 'OsD62G0100039900.01'
MATCH (g)-[:has_a_mutant]->(m:Mutant)
RETURN DISTINCT m.name AS mutant_id
```

2. 查找与突变体相关的基因：
```
MATCH (m:Mutant) WHERE m.name = '22NBD59'
MATCH (g:Gene)-[:has_a_mutant]->(m)
RETURN DISTINCT g.name AS gene_name
```

3. 如果问题只问"是否有突变体"，也要返回所有突变体的名称列表：
```
MATCH (g:Gene) WHERE g.name = 'OsKoshG0304523500.01'
MATCH (g)-[:has_a_mutant]->(m:Mutant)
RETURN DISTINCT m.name AS mutant_id
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

gene_mutant_info_query = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    allow_dangerous_requests=True,
    return_direct=True,
    top_k=1000,
)
