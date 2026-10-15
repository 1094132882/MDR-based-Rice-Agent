"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 15:22
"""
from llm import llm
from graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

CYPHER_GENERATION_TEMPLATE = """
你是一名专业的Neo4j开发专家，负责将用户问题转化为Cypher语句，以回答有关水稻基因位置信息的问题。
请根据以下模式将用户问题转换为Cypher查询。

注意事项：
1. 仅使用模式中提供的关系类型和属性
2. 禁止使用模式中未定义的关系类型或属性
3. 不要返回完整节点或嵌入属性

⚠️ 严格约束:
1. 基因名称存储在 Gene 节点的 "name" 属性中
2. 染色体格式为 Chr01, Chr02, ..., Chr12（两位数字）
3. 必须返回 chromosome, start_pos, end_pos
4. 查询中只允许一个 RETURN 语句，且必须出现在 Cypher 的最后一行

Fine Tuning:
- 当查询染色体时，需将数字编号转换为Chr01格式（例如：一号/1号 → Chr01，三号/3号 → Chr03）
- 基因的名称存储在 "name" 属性中
- 如果用户使用 "kb" 单位，需乘以 1000 转换为碱基数（例如：500kb → 500000）
- 品种名格式多样：G46, Y3551, DHX2, Azucena, 125827, 117425 等

Cypher 语句示例：

**示例1：查询基因的染色体位置和坐标范围**
问题：LOC_Os08g02050在基因组中的具体物理坐标是多少？
```
MATCH (g:Gene)-[:chromosome_no]->(c:Chromosome)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE g.name = 'LOC_Os08g02050'
RETURN c.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
```

**示例2：查询另一个基因的位置**
问题：基因OsJ4155_10g0136300所在的染色体及其坐标范围是什么？
```
MATCH (g:Gene)-[:chromosome_no]->(c:Chromosome)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE g.name = 'OsJ4155_10g0136300'
RETURN c.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
```

**示例3：查找某品种染色体指定范围内的基因（数字品种名）**
问题：117425的2号染色体上8KB至20KB范围内有哪些基因？
```
MATCH (acc:Accession) WHERE acc.name = '117425'
MATCH (chr:Chromosome) WHERE chr.name = 'Chr02'
MATCH (g:Gene)-[:type]->(acc)
MATCH (g)-[:chromosome_no]->(chr)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE toInteger(sp.name) <= 20000 AND toInteger(ep.name) >= 8000
RETURN g.name AS gene_name, chr.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
ORDER BY toInteger(sp.name)
```

**示例4：查找 G46 品种染色体三号 500kb-550kb 区域的基因**
问题：G46的染色体三号在500kb到550kb之间有哪些基因？
```
MATCH (acc:Accession) WHERE acc.name = 'G46'
MATCH (chr:Chromosome) WHERE chr.name = 'Chr03'
MATCH (g:Gene)-[:type]->(acc)
MATCH (g)-[:chromosome_no]->(chr)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE toInteger(sp.name) <= 550000 AND toInteger(ep.name) >= 500000
RETURN g.name AS gene_name, chr.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
ORDER BY toInteger(sp.name)
```

**示例5：查找 Y3551 品种 Chr02 区域 5000-8000 的基因**
问题：请提供Y3551品种Chr02:5000-8000区域的所有基因
```
MATCH (acc:Accession) WHERE acc.name = 'Y3551'
MATCH (chr:Chromosome) WHERE chr.name = 'Chr02'
MATCH (g:Gene)-[:type]->(acc)
MATCH (g)-[:chromosome_no]->(chr)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE toInteger(sp.name) <= 8000 AND toInteger(ep.name) >= 5000
RETURN g.name AS gene_name, chr.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
ORDER BY toInteger(sp.name)
```

**示例6：查找 Azucena 品种一号染色体 100kb-150kb 区域的基因**
问题：Azucena的一号染色体在100kb到150kb范围内有哪些基因？
```
MATCH (acc:Accession) WHERE acc.name = 'Azucena'
MATCH (chr:Chromosome) WHERE chr.name = 'Chr01'
MATCH (g:Gene)-[:type]->(acc)
MATCH (g)-[:chromosome_no]->(chr)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE toInteger(sp.name) <= 150000 AND toInteger(ep.name) >= 100000
RETURN g.name AS gene_name, chr.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
ORDER BY toInteger(sp.name)
```

**示例7：查找 IR64 品种三号染色体 250kb-280kb 区域的基因**
问题：IR64染色体三号的250kb到280kb区域有哪些基因信息？
⚠️ 中文数字"三号"需转换为 Chr03
⚠️ RETURN 必须包含 g.name AS gene_name
```
MATCH (acc:Accession) WHERE acc.name = 'IR64'
MATCH (chr:Chromosome) WHERE chr.name = 'Chr03'
MATCH (g:Gene)-[:type]->(acc)
MATCH (g)-[:chromosome_no]->(chr)
MATCH (g)-[:start_pos]->(sp:Position)
MATCH (g)-[:end_pos]->(ep:Position)
WHERE toInteger(sp.name) <= 280000 AND toInteger(ep.name) >= 250000
RETURN g.name AS gene_name, chr.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
ORDER BY toInteger(sp.name)
```

**示例8：查找 OsY3551 品种区域基因（品种名处理）**
问题：请提供Y3551品种Chr02:5000-8000区域的所有基因
⚠️ 品种名 Y3551 有时写作 OsY3551，需要尝试多种格式
⚠️ RETURN 必须包含 g.name AS gene_name
```
MATCH (chr:Chromosome) WHERE chr.name = 'Chr02'
MATCH (g:Gene)-[:chromosome_no]->(chr)
MATCH (g)-[:type]->(acc:Accession)
WHERE acc.name IN ['Y3551', 'OsY3551']
MATCH (g)-[:start_pos]->(sp:Position) 
MATCH (g)-[:end_pos]->(ep:Position) 
WHERE toInteger(sp.name) <= 8000 AND toInteger(ep.name) >= 5000
RETURN g.name AS gene_name, chr.name AS chromosome, sp.name AS start_pos, ep.name AS end_pos
ORDER BY toInteger(sp.name)
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

gene_locator_query = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    allow_dangerous_requests=True,
    return_direct=True,
    top_k=1000,
)
