# tools_loader.py
import os
import importlib

from langchain.tools import Tool
from .tools.genebasicinfoquery import gene_basic_info_query
from .tools.genefunctionquery import gene_function_query
from .tools.genemutantinfoquery import gene_mutant_info_query
from .tools.ogiinfoquery import ogi_info_query
from .tools.genelocatorquery import gene_locator_query
from .tools.adjacentgenesquery import adjacent_genes_query
from .tools.homologousgeneandexpressionquery import homologous_gene_and_expression_query
from .tools.structuralvariationlinkquery import structural_variation_link_query
from .tools.structuralvariationlocatorquery import structural_variation_locator_query


# 将工具放入一个列表
tools = [
    Tool.from_function(
        name="Gene Basic Info Query",
        description="使用Cypher提供水稻基因的基本信息。"
                    "包括位置信息（染色体、起始/终止位点）、转录本（mRNA）、蛋白质序列、DNA序列、CDS序列等。"
                    "输入为自然语言描述的问题。",
        func=gene_basic_info_query
    ),
    Tool.from_function(
        name="Gene Function Query",
        description="使用Cypher查询给定基因ID的功能或注释信息。"
                    "输入为自然语言描述的问题。",
        func=gene_function_query
    ),
    Tool.from_function(
        name="Gene Mutant Info Query",
        description="使用Cypher查询水稻基因的突变体信息。"
                    "输入为自然语言描述的问题。",
        func=gene_mutant_info_query
    ),
    Tool.from_function(
        name="OGI Info Query",
        description="使用Cypher查询OGI（Ortholog Gene Index，直系同源基因索引）的相关信息。"
                    "输入为自然语言描述的问题。",
        func=ogi_info_query
    ),
    Tool.from_function(
        name="Gene Locator Query",
        description="使用Cypher查询某个水稻种质（品种）的指定染色体的特定范围内存在的基因。"
                    "输入为自然语言描述的问题。",
        func=gene_locator_query
    ),
    Tool.from_function(
        name="Adjacent Genes Query",
        description="使用Cypher查询某个基因的上下游基因。"
                    "输入为自然语言描述的问题。",
        func=adjacent_genes_query
    ),
    Tool.from_function(
        name="Homologous Gene and Expression Query",
        description="使用Cypher查询基因的同源基因和表达信息。"
                    "输入为自然语言描述的问题。",
        func=homologous_gene_and_expression_query
    ),
    Tool.from_function(
        name="Structural Variation Link Query",
        description="使用Cypher查询询结构变异(SV)与基因的联系以及结构变异的转座元件信息。"
                    "输入为自然语言描述的问题。",
        func=structural_variation_link_query
    ),
    Tool.from_function(
        name="Structural Variation Locator Query",
        description="使用Cypher查询某个水稻种质（品种）的指定染色体的特定范围内存在的结构变异。"
                    "输入为自然语言描述的问题。",
        func=structural_variation_locator_query
    )
]

# 打印工具列表
print(tools)