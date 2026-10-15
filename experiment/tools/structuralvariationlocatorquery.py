"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/05 16:26
"""
from llm import llm
from graph import graph

# from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

CYPHER_GENERATION_TEMPLATE = """
你是一名专业的Neo4j开发专家，负责将用户问题转化为Cypher语句，以回答有关结构变异（SV）的问题。
请根据以下模式将用户问题转换为Cypher查询。

注意事项：
1. 仅使用模式中提供的关系类型和属性
2. 禁止使用模式中未定义的关系类型或属性
3. 不要返回完整节点或嵌入属性
4. 不要使用参数占位符如 {{start_pos}}，直接使用具体的数值

🚫🚫🚫 字段完整性约束（严格遵守）🚫🚫🚫
1. 查询结构变异时，**必须**同时返回以下字段（缺一不可）：
   - sv.name as sv_name（结构变异名称）
   - sv.SVTYPE as sv_type（结构变异类型）
   - sv.SVLENGTH as sv_length（结构变异长度，用于"最长"类查询）
   - a.name as query_genome（查询基因组）
   - ra.name as reference_genome（参考基因组）
2. **严禁**只返回单个字段如 `RETURN sv_type` 或 `RETURN reference_genome`
3. 即使用户只问"类型是什么"或"参考基因组是什么"，也必须返回完整的5个字段

🚫🚫🚫 统计类查询约束（Run5关键修复）🚫🚫🚫
1. 如果问题是“数量统计/各类型数量/多少种结构变异/分类统计”（未指定具体类型），**必须**按类型分组返回：
   - `WITH sv.SVTYPE AS sv_type, count(sv) AS sv_count RETURN sv_type, sv_count`
2. **严禁**只返回总数（例如 `RETURN count(sv) AS sv_count` 或 `RETURN total_variants`）来回答“分类统计/多少种”问题
3. 只有当问题明确指定了某个类型（如“缺失类型数量/INS数量/其他类型SV数量”）时，才允许只返回 `sv_count`

Fine Tuning:
- 基因的名称存储在 Gene 节点的 "name" 属性中
- 当查询染色体时，需将数字编号转换为Chr01格式（例如查询6号染色体应写为："MATCH (c:Chromosome {{name: 'Chr06'}})"）
- 结构变异类型（SVTYPE）转换规则：倒位->INV, 缺失->DEL, 其他->OTH, 易位->TRA, 插入->INS

Cypher 语句示例：

**示例1：根据基因名查询该基因区域内的所有结构变异**
问题：OsKeNa_01g0001150的基因组区域是否发现过结构变异？
```
MATCH (g:Gene) -[:in_this_region]-> (sv:Structural_Variations) 
WHERE g.name = 'OsKeNa_01g0001150' 
MATCH (sv)-[:query_genome]->(a:Accession)
MATCH (sv)-[:reference_genome]->(ra:Accession)
RETURN DISTINCT sv.name as sv_name, sv.SVTYPE as sv_type, sv.SVLENGTH as sv_length, a.name as query_genome, ra.name as reference_genome
```

**示例2：根据基因名查询特定类型的结构变异**
问题：OsPr106_01g0000730是否存在缺失类型的结构变异？
```
MATCH (g:Gene) -[:in_this_region]-> (sv:Structural_Variations) 
WHERE g.name = 'OsPr106_01g0000730' AND sv.SVTYPE = 'DEL'
MATCH (sv)-[:query_genome]->(a:Accession)
MATCH (sv)-[:reference_genome]->(ra:Accession)
RETURN DISTINCT sv.name as sv_name, sv.SVTYPE as sv_type, sv.SVLENGTH as sv_length, a.name as query_genome, ra.name as reference_genome
```

**示例3：查找种质品种的染色体指定范围内的结构变异**
问题：DG的一号染色体50kb至70kb区间内发现了哪些SV？
```
MATCH (a:Accession {{name: 'DG'}})
MATCH (c:Chromosome {{name: 'Chr01'}})
MATCH (sv:Structural_Variations)-[:chromosome_no]->(c)
WHERE (sv)-[:query_genome]->(a) 
MATCH (sv)-[:query_start_pos]->(start:Position), (sv)-[:query_end_pos]->(end:Position)
WHERE start.name >= 50000 AND end.name <= 70000
MATCH (sv) -[:reference_genome]-> (ra:Accession)
RETURN DISTINCT sv.name as sv_name, sv.SVTYPE as sv_type, sv.SVLENGTH as sv_length, a.name as query_genome, ra.name as reference_genome
```

**示例4：查询某范围内最长的结构变异**
问题：G46的染色体五号在300kb到500kb范围内最长的结构变异是什么？
```
MATCH (a:Accession {{name: 'G46'}})
MATCH (c:Chromosome {{name: 'Chr05'}})
MATCH (sv:Structural_Variations)-[:chromosome_no]->(c)
WHERE (sv)-[:query_genome]->(a)
MATCH (sv)-[:query_start_pos]->(start:Position), (sv)-[:query_end_pos]->(end:Position)
WHERE start.name >= 300000 AND end.name <= 500000
WITH sv, a
ORDER BY sv.SVLENGTH DESC
LIMIT 1
MATCH (sv)-[:reference_genome]->(ra:Accession)
RETURN sv.name as sv_name, sv.SVTYPE as sv_type, sv.SVLENGTH as sv_length, a.name as query_genome, ra.name as reference_genome
```

**示例5：统计某范围内各类型结构变异的数量**
问题：II32的Chr09在400kb到600kb区域的结构变异分类统计结果？
```
MATCH (a:Accession {{name: 'II32'}})
MATCH (c:Chromosome {{name: 'Chr09'}})
MATCH (sv:Structural_Variations)-[:chromosome_no]->(c)
WHERE (sv)-[:query_genome]->(a)
MATCH (sv)-[:query_start_pos]->(start:Position), (sv)-[:query_end_pos]->(end:Position)
WHERE start.name >= 400000 AND end.name <= 600000
WITH DISTINCT sv
WITH sv.SVTYPE as sv_type, count(sv) as sv_count
RETURN sv_type, sv_count
```

**示例6：统计某范围内特定类型结构变异的数量**
问题：Y3551品种Chr08上1.2Mb-1.5Mb区域检测到多少个插入类型SV？
```
MATCH (a:Accession {{name: 'Y3551'}})
MATCH (c:Chromosome {{name: 'Chr08'}})
MATCH (sv:Structural_Variations {{SVTYPE: 'INS'}})-[:chromosome_no]->(c)
WHERE (sv)-[:query_genome]->(a)
MATCH (sv)-[:query_start_pos]->(start:Position), (sv)-[:query_end_pos]->(end:Position)
WHERE start.name >= 1200000 AND end.name <= 1500000
RETURN count(DISTINCT sv) as sv_count
```

**示例7：查询某范围内最长的特定类型结构变异（必须返回完整信息）**
问题：DG的Chr03在650kb到900kb范围内最长的结构变异类型？
⚠️ 对于"最长"类的查询，必须返回 sv_name, sv_type, sv_length, query_genome, reference_genome
```
MATCH (a:Accession {{name: 'DG'}})
MATCH (c:Chromosome {{name: 'Chr03'}})
MATCH (sv:Structural_Variations)-[:chromosome_no]->(c)
WHERE (sv)-[:query_genome]->(a)
MATCH (sv)-[:query_start_pos]->(start:Position), (sv)-[:query_end_pos]->(end:Position)
WHERE start.name >= 650000 AND end.name <= 900000
WITH sv, a
ORDER BY sv.SVLENGTH DESC
LIMIT 1
MATCH (sv)-[:reference_genome]->(ra:Accession)
RETURN sv.name as sv_name, sv.SVTYPE as sv_type, sv.SVLENGTH as sv_length, a.name as query_genome, ra.name as reference_genome
```

**示例8：查询某范围内最长的插入类型结构变异**
问题：Y3551品种Chr08上1.2Mb-1.5Mb区域中跨度最大的INS类型SV是哪个？
⚠️ 注意：过滤特定类型时，在 Structural_Variations 节点添加 SVTYPE 条件
```
MATCH (a:Accession {{name: 'Y3551'}})
MATCH (c:Chromosome {{name: 'Chr08'}})
MATCH (sv:Structural_Variations {{SVTYPE: 'INS'}})-[:chromosome_no]->(c)
WHERE (sv)-[:query_genome]->(a)
MATCH (sv)-[:query_start_pos]->(start:Position), (sv)-[:query_end_pos]->(end:Position)
WHERE start.name >= 1200000 AND end.name <= 1500000
WITH sv, a
ORDER BY sv.SVLENGTH DESC
LIMIT 1
MATCH (sv)-[:reference_genome]->(ra:Accession)
RETURN sv.name as sv_name, sv.SVTYPE as sv_type, sv.SVLENGTH as sv_length, a.name as query_genome, ra.name as reference_genome
```

**示例9：查询某范围内最长的缺失类型结构变异（只问参考基因组）**
问题：G8的Chr11在150kb-300kb之间最长的deletion类型结构变异参考基因组是？
⚠️ 即使只问参考基因组，也必须返回完整信息以便渲染
```
MATCH (a:Accession {{name: 'G8'}})
MATCH (c:Chromosome {{name: 'Chr11'}})
MATCH (sv:Structural_Variations {{SVTYPE: 'DEL'}})-[:chromosome_no]->(c)
WHERE (sv)-[:query_genome]->(a)
MATCH (sv)-[:query_start_pos]->(start:Position), (sv)-[:query_end_pos]->(end:Position)
WHERE start.name >= 150000 AND end.name <= 300000
WITH sv, a
ORDER BY sv.SVLENGTH DESC
LIMIT 1
MATCH (sv)-[:reference_genome]->(ra:Accession)
RETURN sv.name as sv_name, sv.SVTYPE as sv_type, sv.SVLENGTH as sv_length, a.name as query_genome, ra.name as reference_genome
```

Schema:
{schema}

Question:
{question}
"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

structural_variation_locator_query = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    return_direct=True,
    allow_dangerous_requests=True,
    top_k=1000,
)
