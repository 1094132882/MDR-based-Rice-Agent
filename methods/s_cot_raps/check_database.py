#!/usr/bin/env python3
"""
数据库完整性诊断脚本
直接查询 Neo4j 确认各种数据是否存在
"""
import os
import sys

# 添加路径
rice_mdr1_path = os.path.expanduser("~/xrb/rice_mdr1")
rice_python_path = os.path.join(rice_mdr1_path, "rice_Python")
sys.path.insert(0, rice_mdr1_path)
sys.path.insert(0, rice_python_path)

from neo4j import GraphDatabase

# Neo4j 连接配置
NEO4J_URI = "bolt://127.0.0.1:7689"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = ""

def check_database():
    """检查数据库各类数据的存在情况"""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    checks = [
        # 1. 基因总数
        ("基因总数", "MATCH (g:Gene) RETURN count(g) as count"),
        
        # 2. 染色体信息
        ("染色体总数", "MATCH (c:Chromosome) RETURN count(c) as count"),
        
        # 3. 位置信息 (gene_locator 需要)
        ("基因-染色体关系", "MATCH (g:Gene)-[:chromosome_no]->(c:Chromosome) RETURN count(*) as count"),
        ("基因-起始位置关系", "MATCH (g:Gene)-[:start_pos]->(p:Position) RETURN count(*) as count"),
        ("基因-终止位置关系", "MATCH (g:Gene)-[:end_pos]->(p:Position) RETURN count(*) as count"),
        
        # 4. 突变体信息 (gene_mutant_info 需要)
        ("突变体总数", "MATCH (m:Mutant) RETURN count(m) as count"),
        ("基因-突变体关系", "MATCH (g:Gene)-[:has_a_mutant]->(m:Mutant) RETURN count(*) as count"),
        
        # 5. OGI信息 (ogi_info 需要)
        ("OGI总数", "MATCH (o:OGI) RETURN count(o) as count"),
        ("OGI-基因关系", "MATCH (o:OGI)-[:has_a_gene]->(g:Gene) RETURN count(*) as count"),
        
        # 6. 转录本信息 (gene_basic_info 需要)
        ("转录本总数", "MATCH (t:Transcript) RETURN count(t) as count"),
        ("基因-转录本关系", "MATCH (g:Gene)-[:has_transcript]->(t:Transcript) RETURN count(*) as count"),
        
        # 7. 功能信息 (gene_function 需要)
        ("功能注释节点", "MATCH (f:Function) RETURN count(f) as count"),
        ("基因-功能关系", "MATCH (g:Gene)-[:has_function]->(f:Function) RETURN count(*) as count"),
        
        # 8. 同源基因信息 (homologous_gene_and_expression 需要)
        ("同源基因关系", "MATCH (g1:Gene)-[:homologous_to]->(g2:Gene) RETURN count(*) as count"),
        
        # 9. 表达信息
        ("表达数据节点", "MATCH (e:Expression) RETURN count(e) as count"),
    ]
    
    print("=" * 60)
    print("数据库完整性检查")
    print("=" * 60)
    
    with driver.session() as session:
        for name, query in checks:
            try:
                result = session.run(query)
                count = result.single()["count"]
                status = "✅" if count > 0 else "❌"
                print(f"{status} {name:30s}: {count:>10,}")
            except Exception as e:
                print(f"❌ {name:30s}: ERROR - {e}")
    
    print("=" * 60)
    
    # 检查 dataset.csv 中的具体基因
    print("\n检查 dataset.csv 中的示例基因:")
    print("=" * 60)
    
    test_genes = [
        ("Os02428G0380001552.01", "type2", "gene_basic_info"),
        ("OsN22_01G017170", "type3", "gene_basic_info - transcript"),
        ("OsMH63_03G0194400", "type7", "gene_mutant_info"),
        ("OsARC_01g0045410", "type9", "ogi_info"),
        ("LOC_Os03g08010", "type10", "gene_function"),
    ]
    
    with driver.session() as session:
        for gene_name, type_id, tool in test_genes:
            query = f"MATCH (g:Gene {{name: '{gene_name}'}}) RETURN g.name as name"
            result = session.run(query)
            record = result.single()
            
            if record:
                print(f"✅ {gene_name:30s} ({type_id:6s}, {tool}): 存在")
                
                # 检查相关关系
                if "mutant" in tool:
                    rel_query = f"MATCH (g:Gene {{name: '{gene_name}'}})-[:has_a_mutant]->(m:Mutant) RETURN count(m) as count"
                    rel_result = session.run(rel_query)
                    rel_count = rel_result.single()["count"]
                    print(f"    └─ 突变体数量: {rel_count}")
                
                if "ogi" in tool:
                    rel_query = f"MATCH (o:OGI)-[:has_a_gene]->(g:Gene {{name: '{gene_name}'}}) RETURN o.name as ogi"
                    rel_result = session.run(rel_query)
                    ogi_records = list(rel_result)
                    if ogi_records:
                        print(f"    └─ OGI: {ogi_records[0]['ogi']}")
                    else:
                        print(f"    └─ OGI: 无")
                
                if "basic_info" in tool:
                    rel_query = f"MATCH (g:Gene {{name: '{gene_name}'}})-[:has_transcript]->(t:Transcript) RETURN count(t) as count"
                    rel_result = session.run(rel_query)
                    rel_count = rel_result.single()["count"]
                    print(f"    └─ 转录本数量: {rel_count}")
            else:
                print(f"❌ {gene_name:30s} ({type_id:6s}, {tool}): 不存在")
    
    print("=" * 60)
    driver.close()

if __name__ == "__main__":
    check_database()

