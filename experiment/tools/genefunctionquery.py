"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 14:37
"""
from llm import llm
from graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
CYPHER_GENERATION_TEMPLATE = """
您是一名专业的Neo4j开发专家，负责将将用户问题转化为Cypher语句，以回答有关水稻基因的功能或注释信息方面的问题。
请根据以下模式将用户问题转换为Cypher查询。

注意事项：
1. 仅使用模式中提供的关系类型和属性
2. 禁止使用模式中未定义的关系类型或属性
3. 不要返回完整节点或嵌入属性

Fine Tuning:
基因的 ID 或名称存储在 “name” 属性中。例如，,match(g:Gene) where g.name = 'OsY58SG0923659500.01' return g

Cypher 语句示例：

1. 查找一个基因的功能或注释：
```
match(g:Gene) -[:has_a_function]-> (f:Function) 
where g.name = 'OsY58SG0923659500.01'  
return f.name as function
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

gene_function_query = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    allow_dangerous_requests=True,
    return_direct=True,
    top_k=1000,
)
