"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/03/02 14:11
"""
from py2neo import Graph, Node
from dotenv import load_dotenv
import os
from typing import Optional, Union
import json
from .models import Gene, Chromosome, Position, Strand, Accession, OGI, Mutant, StructuralVariations, \
    BasicInfo, Function, Transcript, ExpressionInfo, Expression, HomologuesInfo, StructuralVariationInfo

load_dotenv()


class GraphService:
    def __init__(self):
        self.graph = Graph(os.getenv("NEO4J_URI"),
                           user=os.getenv("NEO4J_USER"),
                           password=os.getenv("NEO4J_PASSWORD"))

    def _convert_node(self, cls, node_data: Union[Node, dict]):
        """通用节点转换方法"""
        if not node_data:
            return None
        try:
            # 处理 py2neo.Node 类型
            if isinstance(node_data, Node):
                data = dict(node_data)
            else:
                data = node_data

            # StructuralVariations 特殊处理
            if cls == StructuralVariations:
                return StructuralVariations(
                    ID=data.get("ID"),
                    name=data.get("name"),
                    SVLENGTH=data.get("SVLENGTH"),
                    SVTYPE=data.get("SVTYPE")
                )

            # 通用处理逻辑
            return cls(
                ID=data.get("ID"),
                **{k: v for k, v in data.items() if k != "ID"}
            )
        except Exception as e:
            print(f"转换 {cls.__name__} 失败: {str(e)}")
            return None

    def get_gene_info(self, gene_id: str) -> Optional[BasicInfo]:
        cypher = """
           MATCH (g:Gene {name: $name})
           OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
           OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
           OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
           OPTIONAL MATCH (g)-[:strand_info]->(s:Strand)
           OPTIONAL MATCH (g)-[:type]->(a:Accession)
           OPTIONAL MATCH (g)<-[:has_a_gene]-(o:OGI)
           OPTIONAL MATCH (g)-[:has_a_mutant]->(m:Mutant)
           OPTIONAL MATCH (g)-[:in_this_region]->(sv:Structural_Variations)
           OPTIONAL MATCH (g)-[:has_a_function]->(f:Function)
           OPTIONAL MATCH (g)-[:has_a_transcript]->(t:mRNA)
           RETURN g, c, sp, ep, s, a, o, 
                  COLLECT(DISTINCT m) AS mutants,
                  COLLECT(DISTINCT sv) AS structural_variations,
                  COLLECT(DISTINCT t) AS transcripts
           LIMIT 1
           """
        result = self.graph.run(cypher, name=gene_id).data()
        if not result:
            return None

        record = result[0]
        info = BasicInfo()

        # 主节点转换
        info.gene = self._convert_node(Gene, record.get("g"))
        info.chromosome = self._convert_node(Chromosome, record.get("c"))
        info.start_pos = self._convert_node(Position, record.get("sp"))
        info.end_pos = self._convert_node(Position, record.get("ep"))
        info.strand = self._convert_node(Strand, record.get("s"))
        info.accession = self._convert_node(Accession, record.get("a"))
        info.ogi = self._convert_node(OGI, record.get("o"))
        info.function = self._convert_node(Function, record.get("f"))

        # 处理集合字段
        info.mutants = [
            self._convert_node(Mutant, m)
            for m in record.get("mutants", [])
        ]
        info.structural_variations = [
            self._convert_node(StructuralVariations, sv)
            for sv in record.get("structural_variations", [])
        ]
        info.transcripts = [
            self._convert_node(Transcript, t)
            for t in record.get("transcripts", [])
        ]

        return info

    def get_expression_info(self, gene_id: str) -> Optional[ExpressionInfo]:
        cypher = """
        MATCH (n:Gene)-[:measures_gene_expression]->(e:Expression)
        WHERE n.name = $name
        RETURN n, e
        LIMIT 1
        """
        result = self.graph.run(cypher, name=gene_id).data()
        if not result:
            return None
        record = result[0]
        info = ExpressionInfo()

        info.gene = self._convert_node(Gene, record.get("n"))
        info.expression = self._convert_node(Expression, record.get("e"))
        info.init_all_data()

        return info

    def get_homologous_info(self, gene_name: str) -> Optional[HomologuesInfo]:
        cypher = """
        MATCH (g1:Gene {name: $name}) -[r1:SBH|RBH]-> (g2:Gene)
        OPTIONAL MATCH (g2) -[:measures_gene_expression]-> (e:Expression)
        RETURN 
          g1,
          COLLECT({
            gene: g2, 
            relation: type(r1), 
            expression: e
          }) AS homologous_data
        """
        result = self.graph.run(cypher, name=gene_name).data()
        if not result:
            return None

        record = result[0]
        homology_info = HomologuesInfo()
        homology_info.source_gene = self._convert_node(Gene, record["g1"])

        for item in record["homologous_data"]:
            relation_type = item["relation"]
            expression_info = ExpressionInfo()
            expression_info.gene = self._convert_node(Gene, item["gene"])
            if item["expression"]:
                expression_info.expression = self._convert_node(Expression, item["expression"])
                expression_info.init_all_data()
            homology_info.add_homology(relation_type, expression_info)
        return homology_info

    def get_sv_info(self, sv_id: str) -> Optional[StructuralVariationInfo]:
        cypher = """
        match(sv:Structural_Variations {name: $sv_id}) -[:reference_genome]-> (RefA:Accession) 
        match(sv) -[:query_genome]-> (QueA:Accession) 
        match(sv) -[:reference_start_pos]-> (RefSP:Position) 
        match(sv) -[:reference_end_pos]-> (RefEP:Position) 
        match(sv) -[:query_start_pos]-> (QueSP:Position) 
        match(sv) -[:query_end_pos]-> (QueEP:Position) 
        match(sv) -[:chromosome_no]-> (c:Chromosome) 
        return sv,RefA, QueA, RefSP, RefEP, QueSP, QueEP, c 
        """
        result = self.graph.run(cypher, sv_id=sv_id).data()
        if not result:
            return None
        record = result[0]
        sv_info = StructuralVariationInfo()
        sv_info.structural_variation = self._convert_node(StructuralVariations, record.get("sv"))
        sv_info.ref_genome = self._convert_node(Accession, record.get("RefA"))
        sv_info.query_genome = self._convert_node(Accession, record.get("QueA"))
        sv_info.ref_start = self._convert_node(Position, record.get("RefSP"))
        sv_info.ref_end = self._convert_node(Position, record.get("RefEP"))
        sv_info.query_start = self._convert_node(Position, record.get("QueSP"))
        sv_info.query_end = self._convert_node(Position, record.get("QueEP"))
        sv_info.chromosome = self._convert_node(Chromosome, record.get("c"))
        return sv_info


if __name__ == '__main__':
    service = GraphService()
    # data = service.get_gene_info("OsZS97_01G0008500")
    data1 = service.get_expression_info("OsMH63_03G0194400")
    data2 = service.get_homologous_info("OsMH63_03G0194400")

    # if data:
    #     print(json.dumps(data.to_graph_data(), indent=2, ensure_ascii=False))
    #     print(data.to_table_data())

    # if data1:
    #     print(json.dumps(data1.to_graph_data(), indent=2, ensure_ascii=False))

    if data2:
        # print(data2.to_graph_data())
        print(json.dumps(data2.to_graph_data(), indent=2, ensure_ascii=False))
