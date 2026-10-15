#!/usr/bin/env python3
"""直接查询 Neo4j 诊断数据是否存在"""
import os
import sys

# 从 dataset.csv 取几个失败的基因名直接查
TEST_GENES = [
    # type2 - gene_basic_info (Strand)
    ("Os02428G0380001552.01", "strand"),
    ("OsYX1G0926018000.01", "strand"),
    
    # type3 - gene_basic_info (Transcript)
    ("OsN22_01G017170", "transcript"),
    ("OsR498G0917308900.01", "transcript"),
    
    # type7 - gene_mutant_info
    ("OsMH63_03G0194400", "mutant"),
    ("OsDHX2G0304534500.01", "mutant"),
    
    # type9 - ogi_info
    ("OsARC_01g0045410", "ogi"),
    ("LOC_Os04g40530", "ogi"),
    
    # type10 - gene_function
    ("LOC_Os03g08010", "function"),
]

def main():
    # 连接 Neo4j
    from neo4j import GraphDatabase
    
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7689")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    
    print(f"连接 Neo4j: {uri}")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    with driver.session() as session:
        # 1. 统计总数
        print("\n=== 节点统计 ===")
        for label in ["Gene", "Mutant", "OGI", "Transcript", "Function", "Chromosome", "Position"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as c")
            count = result.single()["c"]
            print(f"{label:15s}: {count:>10,}")
        
        # 2. 统计关系
        print("\n=== 关系统计 ===")
        rels = [
            ("Gene-[:chromosome_no]->Chromosome", "MATCH ()-[:chromosome_no]->() RETURN count(*) as c"),
            ("Gene-[:start_pos]->Position", "MATCH ()-[:start_pos]->() RETURN count(*) as c"),
            ("Gene-[:has_a_mutant]->Mutant", "MATCH ()-[:has_a_mutant]->() RETURN count(*) as c"),
            ("OGI-[:has_a_gene]->Gene", "MATCH ()-[:has_a_gene]->() RETURN count(*) as c"),
            ("Gene-[:has_transcript]->Transcript", "MATCH ()-[:has_transcript]->() RETURN count(*) as c"),
            ("Gene-[:has_function]->Function", "MATCH ()-[:has_function]->() RETURN count(*) as c"),
        ]
        for name, q in rels:
            result = session.run(q)
            count = result.single()["c"]
            status = "✅" if count > 0 else "❌"
            print(f"{status} {name:40s}: {count:>10,}")
        
        # 3. 测试具体基因
        print("\n=== 测试 dataset.csv 中的基因 ===")
        for gene_name, check_type in TEST_GENES:
            # 先检查基因是否存在
            result = session.run("MATCH (g:Gene {name: $name}) RETURN g.name as n", name=gene_name)
            record = result.single()
            
            if not record:
                print(f"❌ {gene_name:30s} - 基因不存在!")
                continue
            
            # 根据类型检查关系
            if check_type == "strand":
                # strand 需要通过 start_pos 和 end_pos 比较
                q = """
                MATCH (g:Gene {name: $name})-[:start_pos]->(sp:Position)
                MATCH (g)-[:end_pos]->(ep:Position)
                RETURN sp.name as start, ep.name as end
                """
                result = session.run(q, name=gene_name)
                rec = result.single()
                if rec:
                    start, end = rec["start"], rec["end"]
                    strand = "+" if int(start) < int(end) else "-"
                    print(f"✅ {gene_name:30s} - strand={strand} (start={start}, end={end})")
                else:
                    print(f"❌ {gene_name:30s} - 无位置信息，无法判断strand")
                    
            elif check_type == "transcript":
                q = "MATCH (g:Gene {name: $name})-[:has_transcript]->(t:Transcript) RETURN t.name as t"
                result = session.run(q, name=gene_name)
                transcripts = [r["t"] for r in result]
                if transcripts:
                    print(f"✅ {gene_name:30s} - transcripts: {transcripts[:3]}")
                else:
                    print(f"❌ {gene_name:30s} - 无转录本关系")
                    
            elif check_type == "mutant":
                q = "MATCH (g:Gene {name: $name})-[:has_a_mutant]->(m:Mutant) RETURN m.name as m"
                result = session.run(q, name=gene_name)
                mutants = [r["m"] for r in result]
                if mutants:
                    print(f"✅ {gene_name:30s} - mutants: {mutants[:3]}")
                else:
                    print(f"❌ {gene_name:30s} - 无突变体关系")
                    
            elif check_type == "ogi":
                q = "MATCH (o:OGI)-[:has_a_gene]->(g:Gene {name: $name}) RETURN o.name as o"
                result = session.run(q, name=gene_name)
                ogis = [r["o"] for r in result]
                if ogis:
                    print(f"✅ {gene_name:30s} - OGI: {ogis[:3]}")
                else:
                    print(f"❌ {gene_name:30s} - 无OGI关系")
                    
            elif check_type == "function":
                q = "MATCH (g:Gene {name: $name})-[:has_function]->(f:Function) RETURN f.name as f"
                result = session.run(q, name=gene_name)
                funcs = [r["f"] for r in result]
                if funcs:
                    print(f"✅ {gene_name:30s} - function: {funcs[:3]}")
                else:
                    print(f"❌ {gene_name:30s} - 无功能关系")
    
    driver.close()
    print("\n诊断完成。如果大量 ❌，说明数据库缺少数据，需要联系学长导入。")

if __name__ == "__main__":
    main()

