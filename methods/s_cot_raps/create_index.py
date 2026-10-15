#!/usr/bin/env python3
"""为 Neo4j 创建必要的索引，大幅提升查询速度"""
import os
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7689")
AUTH = (os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))

def create_indexes():
    print(f"连接数据库: {URI}")
    
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session() as session:
            print("\n=== 创建索引 ===")
            
            indexes = [
                # 核心节点索引
                ("Gene", "name", "gene_name_idx"),
                ("Chromosome", "name", "chr_name_idx"),
                ("Position", "name", "pos_name_idx"),
                ("OGI", "name", "ogi_name_idx"),
                ("Mutant", "name", "mutant_name_idx"),
                ("Accession", "name", "accession_name_idx"),
                ("Function", "name", "function_name_idx"),
                ("Expression", "name", "expression_name_idx"),
                # SV 相关
                ("Structural_Variations", "name", "sv_name_idx"),
                ("Structural_Variations", "SVTYPE", "sv_type_idx"),
            ]
            
            for label, prop, idx_name in indexes:
                try:
                    # 先检查索引是否存在
                    result = session.run(f"SHOW INDEXES WHERE name = '{idx_name}'")
                    if result.single():
                        print(f"  ⏭ {idx_name} 已存在，跳过")
                        continue
                    
                    session.run(f"CREATE INDEX {idx_name} IF NOT EXISTS FOR (n:{label}) ON (n.{prop})")
                    print(f"  ✓ {idx_name} ({label}.{prop}) 创建成功")
                except Exception as e:
                    print(f"  ⚠ {idx_name}: {e}")
            
            print("\n=== 检查当前索引 ===")
            result = session.run("SHOW INDEXES")
            for record in result:
                print(f"  - {record['name']}: {record['labelsOrTypes']} ({record['state']})")
            
            print("\n✅ 索引创建完成！")
            print("现在重新运行测试，速度应该会大幅提升。")

if __name__ == "__main__":
    create_indexes()

