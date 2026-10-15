"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 16:18
"""
from llm import llm
from graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

CYPHER_GENERATION_TEMPLATE = """
你是一名专业的Neo4j开发专家，负责将用户问题转化为Cypher语句，以回答有关与结构变异相关的基因和转座元件的问题。
请根据以下模式将用户问题转换为Cypher查询。

注意事项：
1. 仅使用模式中提供的关系类型和属性
2. 禁止使用模式中未定义的关系类型或属性
3. 不要返回完整节点或嵌入属性
4. 查询中只允许一个 RETURN 语句，且必须出现在 Cypher 的最后一行

Fine Tuning:
- 基因的 ID 或名称存储在 "name" 属性中
- 结构变异（SV）的名称格式：品种名_参考基因组_类型+编号，如 Y58S_Nipponbare_INS0434890
- 在转座元件（TE）类型的数据中，"name" 属性没有意义，只需返回 te.type
- 转座元件类型包括：long_terminal_repeat, Gypsy_LTR_retrotransposon, Copia_LTR_retrotransposon, LTR_retrotransposon, repeat_region, target_site_duplication, helitron 等

### 结构变异类型（SVTYPE）转换规则：
在查询结构变异类型时，将完整的文本描述转换为以下缩写形式：
- 倒位 -> INV
- 缺失 -> DEL
- 其他 -> OTH
- 易位 -> TRA
- 插入 -> INS

Cypher 语句示例：

1. 查找某个基因的结构变异：
```
MATCH (g:Gene)-[:in_this_region]->(sv:Structural_Variations) 
WHERE g.name = 'OsN22_01G030690' 
RETURN sv.name AS sv_name
```

2. 查找某个基因的特定类型的结构变异：
```
MATCH (g:Gene)-[:in_this_region]->(sv:Structural_Variations) 
WHERE g.name = 'OsN22_06G016250' AND sv.SVTYPE = 'INV' 
RETURN sv.name AS sv_name
```

3. 查找结构变异的转座元件（TE注释）：
```
MATCH (sv:Structural_Variations)<-[:in_this_region]-(te:TE) 
WHERE sv.name = '02428_117425_INS0734090' 
RETURN te.type AS te_type
```

4. 查找 Y58S_Nipponbare_INS0434890 关联的转座元件：
问题：Y58S_Nipponbare_INS0434890是否关联转座子？
```
MATCH (sv:Structural_Variations)<-[:in_this_region]-(te:TE) 
WHERE sv.name = 'Y58S_Nipponbare_INS0434890' 
RETURN te.type AS te_type
```

5. 查找 132278_ZS97RS3_DEL0216520 区域内的 TE 注释：
问题：132278_ZS97RS3_DEL0216520区域内有没有TE注释？
```
MATCH (sv:Structural_Variations)<-[:in_this_region]-(te:TE) 
WHERE sv.name = '132278_ZS97RS3_DEL0216520' 
RETURN te.type AS te_type
```

6. 查找 Azucena_G8_INS0518170_2 的转座元件注释：
问题：Azucena_G8_INS0518170_2有没有转座元件注释？
```
MATCH (sv:Structural_Variations)<-[:in_this_region]-(te:TE) 
WHERE sv.name = 'Azucena_G8_INS0518170_2' 
RETURN te.type AS te_type
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

structural_variation_link_query = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    return_direct=True,
    allow_dangerous_requests=True,
    top_k=1000,
)
