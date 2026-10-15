# -*- coding: utf-8 -*-
from __future__ import annotations

# 你自己的 llm 和 neo4j graph
from .llm import llm
from .graph import graph

# 你那 9 个工具
from .tools.genebasicinfoquery import gene_basic_info_query
from .tools.genefunctionquery import gene_function_query
from .tools.genemutantinfoquery import gene_mutant_info_query
from .tools.ogiinfoquery import ogi_info_query
from .tools.genelocatorquery import gene_locator_query
from .tools.adjacentgenesquery import adjacent_genes_query
from .tools.homologousgeneandexpressionquery import homologous_gene_and_expression_query
from .tools.structuralvariationlinkquery import structural_variation_link_query
from .tools.structuralvariationlocatorquery import structural_variation_locator_query

from langchain_core.tools import Tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

tools = [
    Tool.from_function(
        name="Gene Basic Info Query",
        description="使用Cypher提供水稻基因的基本信息。",
        func=gene_basic_info_query,
    ),
    Tool.from_function(
        name="Gene Function Query",
        description="使用Cypher查询基因功能/注释。",
        func=gene_function_query,
    ),
    Tool.from_function(
        name="Gene Mutant Info Query",
        description="使用Cypher查询水稻基因的突变体信息。",
        func=gene_mutant_info_query,
    ),
    Tool.from_function(
        name="OGI Info Query",
        description="使用Cypher查询OGI相关信息。",
        func=ogi_info_query,
    ),
    Tool.from_function(
        name="Gene Locator Query",
        description="查询某个品种指定染色体区间内的基因。",
        func=gene_locator_query,
    ),
    Tool.from_function(
        name="Adjacent Genes Query",
        description="查询某个基因的上下游基因。",
        func=adjacent_genes_query,
    ),
    Tool.from_function(
        name="Homologous Gene and Expression Query",
        description="查询基因的同源基因和表达信息。",
        func=homologous_gene_and_expression_query,
    ),
    Tool.from_function(
        name="Structural Variation Link Query",
        description="查询结构变异与基因的联系以及转座元件信息。",
        func=structural_variation_link_query,
    ),
    Tool.from_function(
        name="Structural Variation Locator Query",
        description="查询某个品种指定染色体区间内存在的结构变异。",
        func=structural_variation_locator_query,
    ),
]

SYSTEM_PROMPT = """
你是水稻基因组领域的 RGI 数据库小助手，只回答与 RGI / 水稻基因图谱相关的问题。
回答要和用户语言一致，如果用户使用英语，你最后回答的结果也需要使用英语；有多条结果要说一共有几条，再用有序列表列出；只有工具真的给了 URL 才能产出链接；不要编造外部知识。
"""

memory = MemorySaver()

# 注意这里：用 model=llm，而不是 llm=llm
agent = create_react_agent(
    model=llm,
    tools=tools,
    checkpointer=memory,
)

def generate_response(user_input: str, session_id: str) -> str:
    messages = [
        ("system", SYSTEM_PROMPT.strip()),
        ("user", user_input),
    ]

    result = agent.invoke(
        {"messages": messages},
        config={"configurable": {"thread_id": session_id}},
    )

    final_msg = result["messages"][-1]
    content = getattr(final_msg, "content", None)
    if content is None and isinstance(final_msg, dict):
        content = final_msg.get("content", "")
    return content
