from pathlib import Path
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断 Neo4j Schema 问题
找出为什么 LLM 生成错误的 Cypher 查询
"""
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rice_Python.App.chat.graph import graph
from neo4j import GraphDatabase

print("=" * 80)
print("Neo4j Schema 诊断报告")
print("=" * 80)
print()

# 1. GraphCypherQAChain 看到的 schema
print("【1】 GraphCypherQAChain 看到的 Schema")
print("-" * 80)
try:
    schema_str = graph.get_schema
    print(schema_str)
except Exception as e:
    print(f"错误: {e}")
print()

# 2. 实际数据库信息
print("=" * 80)
print("【2】 实际数据库结构")
print("-" * 80)

driver = GraphDatabase.driver('bolt://localhost:7689', auth=('neo4j', ''))

with driver.session() as session:
    # 2.1 所有关系类型
    print("\n【2.1】 所有关系类型:")
    result = session.run('CALL db.relationshipTypes()')
    rels = sorted([record[0] for record in result])
    for rel in rels:
        print(f"  :{rel}")
    
    # 2.2 所有节点标签
    print("\n【2.2】 所有节点标签:")
    result = session.run('CALL db.labels()')
    labels = sorted([record[0] for record in result])
    for label in labels:
        print(f"  :{label}")
    
    # 2.3 Gene 节点属性
    print("\n【2.3】 Gene 节点属性:")
    result = session.run('MATCH (g:Gene) WITH g LIMIT 1 RETURN keys(g) AS props')
    for record in result:
        props = sorted(record['props'])
        for prop in props:
            print(f"  g.{prop}")
    
    # 2.4 Position 节点属性
    print("\n【2.4】 Position 节点属性:")
    result = session.run('MATCH (p:Position) WITH p LIMIT 1 RETURN keys(p) AS props')
    for record in result:
        props = sorted(record['props'])
        for prop in props:
            print(f"  p.{prop}")
    
    # 2.5 Chromosome 节点属性
    print("\n【2.5】 Chromosome 节点属性:")
    result = session.run('MATCH (c:Chromosome) WITH c LIMIT 1 RETURN keys(c) AS props')
    for record in result:
        props = sorted(record['props'])
        for prop in props:
            print(f"  c.{prop}")
    
    # 2.6 Gene 的所有出边关系
    print("\n【2.6】 Gene 节点的出边关系 (示例):")
    result = session.run('''
        MATCH (g:Gene)-[r]->()
        RETURN DISTINCT type(r) AS rel_type, labels(endNode(r))[0] AS target_label
        ORDER BY rel_type
        LIMIT 20
    ''')
    for record in result:
        print(f"  (Gene)-[:{record['rel_type']}]->({record['target_label']})")
    
    # 2.7 测试查询一个基因
    print("\n【2.7】 测试查询: LOC_Os08g02050")
    result = session.run('''
        MATCH (g:Gene {name: 'LOC_Os08g02050'})
        OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
        OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
        OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
        RETURN g.name AS gene, c.name AS chr, sp.name AS start, ep.name AS end
    ''')
    record = result.single()
    if record:
        print(f"  基因: {record['gene']}")
        print(f"  染色体: {record['chr']}")
        print(f"  起始位置: {record['start']}")
        print(f"  终止位置: {record['end']}")
    else:
        print("  未找到该基因")
    
    # 2.8 检查是否有 strand 相关信息
    print("\n【2.8】 检查链性信息存储方式:")
    # 检查是否有 strand 属性
    result = session.run('''
        MATCH (g:Gene)
        WHERE exists(g.strand)
        RETURN count(g) AS count_with_strand
    ''')
    count = result.single()['count_with_strand']
    print(f"  有 strand 属性的基因数量: {count}")
    
    # 检查是否通过位置判断
    result = session.run('''
        MATCH (g:Gene)-[:start_pos]->(sp:Position)
        MATCH (g)-[:end_pos]->(ep:Position)
        WHERE toInteger(sp.name) < toInteger(ep.name)
        RETURN count(g) AS forward_genes
        LIMIT 1
    ''')
    try:
        count = result.single()['forward_genes']
        print(f"  起始 < 终止 的基因数量（正链）: {count}")
        print("  提示: 链性信息需通过比较 start_pos 和 end_pos 来判断")
    except Exception as e:
        print(f"  无法判断: {e}")

driver.close()

print()
print("=" * 80)
print("【3】 问题分析")
print("-" * 80)
print()
print("根据以上信息，检查：")
print("  1. LLM 看到的 schema 是否包含正确的关系类型？")
print("  2. schema 中是否误导 LLM 使用了不存在的关系（如 :position）？")
print("  3. schema 中是否说明 Gene 没有 strand 属性？")
print()
print("=" * 80)

