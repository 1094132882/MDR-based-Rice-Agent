"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/05/08 17:41
"""
# ⚠️ 必须最先导入：应用 langchain 兼容性补丁
import tools._langchain_patch

from llm import llm
from langchain_core.tools import Tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import tiktoken
# Tools
from tools.genebasicinfoquery import gene_basic_info_query
from tools.genefunctionquery import gene_function_query
from tools.genemutantinfoquery import gene_mutant_info_query
from tools.ogiinfoquery import ogi_info_query
from tools.genelocatorquery import gene_locator_query
from tools.adjacentgenesquery import adjacent_genes_query
from tools.homologousgeneandexpressionquery import homologous_gene_and_expression_query
from tools.structuralvariationlinkquery import structural_variation_link_query
from tools.structuralvariationlocatorquery import structural_variation_locator_query
import json

tools = [
    Tool.from_function(
        name="Gene_Basic_Info_Query",
        description="使用Cypher提供水稻基因的基本信息。"
                    "包括位置信息（染色体、起始/终止位点）、转录本（mRNA）、蛋白质序列、DNA序列、CDS序列等。"
                    "输入为自然语言描述的问题。",
        func=gene_basic_info_query
    ),
    Tool.from_function(
        name="Gene_Function_Query",
        description="使用Cypher查询给定基因ID的功能或注释信息。"
                    "输入为自然语言描述的问题。",
        func=gene_function_query
    ),
    Tool.from_function(
        name="Gene_Mutant_Info_Query",
        description="使用Cypher查询水稻基因的突变体信息。"
                    "输入为自然语言描述的问题。",
        func=gene_mutant_info_query
    ),
    Tool.from_function(
        name="OGI_Info_Query",
        description="使用Cypher查询OGI（Ortholog Gene Index，直系同源基因索引）的相关信息。"
                    "输入为自然语言描述的问题。",
        func=ogi_info_query
    ),
    Tool.from_function(
        name="Gene_Locator_Query",
        description="使用Cypher查询某个水稻种质（品种）的指定染色体的特定范围内存在的基因。"
                    "输入为自然语言描述的问题。",
        func=gene_locator_query
    ),
    Tool.from_function(
        name="Adjacent_Genes_Query",
        description="使用Cypher查询某个基因的上下游基因。"
                    "输入为自然语言描述的问题。",
        func=adjacent_genes_query
    ),
    Tool.from_function(
        name="Homologous_Gene_and_Expression_Query",
        description="使用Cypher查询基因的同源基因和表达信息。"
                    "输入为自然语言描述的问题。",
        func=homologous_gene_and_expression_query
    ),
    Tool.from_function(
        name="Structural_Variation_Link_Query",
        description="使用Cypher查询询结构变异(SV)与基因的联系以及结构变异的转座元件信息。"
                    "输入为自然语言描述的问题。",
        func=structural_variation_link_query
    ),
    Tool.from_function(
        name="Structural_Variation_Locator_Query",
        description="使用Cypher查询某个水稻种质（品种）的指定染色体的特定范围内存在的结构变异。"
                    "输入为自然语言描述的问题。",
        func=structural_variation_locator_query
    )
]

memory = MemorySaver()

agent_prompt = """
**语言适配规则**：
- 根据用户提问的语言提供回答，并确保信息详尽。

**角色定义**：
你是水稻基因组领域的Rice Gene Index（RGI, 水稻基因索引）数据库的小助手，专门回答与该水稻基因数据库相关的问题。
请尽可能提供帮助，并返回尽可能多的信息。
不要回答任何与水稻基因组学无关的问题。


**严格的响应要求**：
1. 在整个回答中保持语言一致性。
2. 对于查询到的数据，请在回答中将所有数据包含，不得遗漏任何数据。当数据大于等于两个时，需要先描述找到的数据的数量，再使用Markdown的有序列表格式将数据按顺序排列。
3. 仅当工具返回的结果中包含URL时，使用Markdown语法将其设置为链接，例如：[基因名称](基因URL)。绝对禁止虚构URL或在答案输出中强制添加链接。
4. 对于中文回答，使用以下格式：
（1）回答基因位置信息时，需要包含染色体、起止位点信息三部分，格式：基因OsARC_03g0037750的位置在Chr03:34948520-34949026。，并确保提供详细的背景信息。
（2）回答基因链正负向信息时，格式：基因（基因号）位于正链/负链，并确保提供详细的背景信息。
（3）回答基因序列信息时，格式：基因(基因号)的(提问的序列类型)序列请点击[链接](基因URL)查看，并确保提供详细的背景信息。
（4）查询基因表达信息时，格式：基因(基因号)在叶中的表达量为leaf_value，根中的表达量为root_value，幼穗的表达量为young_ear_value，并确保提供详细的背景信息。
（5）使用基因功能或注释信息搜索工具时，以下内容(function)不需要翻译成中文，格式：基因(基因号)的注释/功能是(function)。
5. 用中文回答问题。

**数据完整性检查**：
- 在输出结果前，请确保所有查询到的数据都已包含在回答中，不得遗漏任何数据。


**知识限制**：
不要使用预训练知识回答任何问题，仅使用上下文提供的信息。
在回答问题时，请基于工具获取到的信息进行回答，不要使用预训练的知识加入其他陈述性的信息，保证回答的严谨性。

**工具调用规则**
当你调用工具获取信息时，请尽可能详细描述你要获取的内容，禁止使用字典的形式传递参数。
当数据大于等于两个时，需要先描述找到的数据的数量，再使用Markdown的有序列表格式将数据按顺序排列。
/no_think
"""

graph = create_react_agent(llm, tools=tools, checkpointer=memory, prompt=agent_prompt)  # langgraph 1.0+


def print_stream(stream):
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()


def save_dict_to_txt_file(data, file_path):
    """
    Save a dictionary to a text file.
    :param data:
    :param file_path:
    :return:
    """
    print("Saving data to file: " + file_path)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(str(data))



def print_response(response):
    for message in response:
        print(message)


def generate_response(user_input, session_id):
    inputs = {"messages": [("user", user_input)]}
    config = {"configurable": {"thread_id": session_id}}
    response = graph.invoke(inputs, config=config)
    save_dict_to_txt_file(response, "response.txt")
    print("memory:", memory)
    content = response.get("messages")[-1].content
    encoder = tiktoken.get_encoding("cl100k_base")
    input_tokens = len(encoder.encode(user_input))
    output_tokens = len(encoder.encode(content))
    total_tokens = input_tokens + output_tokens
    return content, total_tokens
