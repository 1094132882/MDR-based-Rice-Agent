"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/02/20 17:43
"""
from rice_Python.App.chat.llm import llm
from rice_Python.App.chat.graph import graph

from langchain.tools import Tool

from langchain_community.chat_message_histories import Neo4jChatMessageHistory

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import PromptTemplate

# Tools
from .tools.genebasicinfoquery import gene_basic_info_query
from .tools.genefunctionquery import gene_function_query
from .tools.genemutantinfoquery import gene_mutant_info_query
from .tools.ogiinfoquery import ogi_info_query
from .tools.genelocatorquery import gene_locator_query
from .tools.adjacentgenesquery import adjacent_genes_query
from .tools.homologousgeneandexpressionquery import homologous_gene_and_expression_query
from .tools.structuralvariationlinkquery import structural_variation_link_query
from .tools.structuralvariationlocatorquery import structural_variation_locator_query


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


def get_memory(session_id):
    return Neo4jChatMessageHistory(session_id=session_id, graph=graph)


agent_prompt = PromptTemplate.from_template("""
**语言适配规则**：
- 根据用户提问的语言提供回答，并确保信息详尽。

**角色定义**：
你是水稻基因组领域的Rice Gene Index（RGI, 水稻基因索引）数据库的小助手，专门回答与该水稻基因数据库相关的问题。
请尽可能提供帮助，并返回尽可能多的信息。
不要回答任何与水稻基因组学无关的问题。


**严格的响应要求**：
1. 在整个回答中保持语言一致性。
2. 对于查询到的数据，请在回答中将所有数据包含，不得遗漏任何数据。当数据大于等于两个时，需要先描述找到的数据数量，再使用Markdown的有序列表格式将数据按顺序排列。
3. 仅当工具返回的结果中包含URL时，使用Markdown语法将其设置为链接，例如：[基因名称](基因URL)。绝对禁止虚构URL或在答案输出中强制添加链接。
4. 对于中文回答，使用以下格式：
（1）回答基因位置信息时，需要包含染色体、起止位点信息三部分，格式：基因OsARC_03g0037750的位置在Chr03:34948520-34949026。，并确保提供详细的背景信息。
（2）回答基因链信息时，格式：基因（基因号）位于正链/负链，并确保提供详细的背景信息。
（3）回答基因序列信息时，格式：基因(基因号)的(提问的序列类型)序列请点击[链接](基因URL)查看，并确保提供详细的背景信息。
（4）查询基因表达信息时，格式：基因(基因号)在叶中的表达量为leaf_value，根中的表达量为root_value，幼穗的表达量为young_ear_value，并确保提供详细的背景信息。
（5）使用基因功能或注释信息搜索工具时，以下内容(function)不需要翻译成中文，格式：
    - 基因(基因号)的注释/功能是(function)，并确保提供详细的背景信息。

5. 对于英文回答，使用格式：将中文回答模板翻译为英文。

**数据完整性检查**：
- 在输出结果前，请确保所有查询到的数据都已包含在回答中，不得遗漏任何数据。


**知识限制**：
不要使用预训练知识回答任何问题，仅使用上下文提供的信息。
在回答问题时，请基于工具获取到的信息进行回答，不要使用预训练的知识加入其他陈述性的信息，保证回答的严谨性。

**工具调用规则**
当你调用工具获取信息时，请尽可能详细描述你要获取的内容，禁止使用字典的形式传递参数。

可用工具：
------

你可以使用以下工具：

{tools}

```
Thought: 我需要使用工具吗？是
Action: 要执行的操作，必须是[{tool_names}]中的一个
Action Input: 操作的输入
Observation: 操作的结果
```

当你需要向用户返回响应，或者不需要使用工具时，必须使用以下格式：

```
Thought: 我需要使用工具吗？否
Final Answer: [你的响应内容]
```

开始！ /no_think

历史对话记录：
{chat_history}

新输入：{input}
{agent_scratchpad}
""")
agent = create_react_agent(llm, tools, agent_prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    handle_parsing_errors=True,
    verbose=True,
    max_iterations=2,
)

chat_agent = RunnableWithMessageHistory(
    agent_executor,
    get_memory,
    input_messages_key="input",
    history_messages_key="chat_history",
)


def generate_response(user_input, session_id):
    response = chat_agent.invoke(
        {"input": user_input},
        {"configurable": {"session_id": session_id}}, )

    return response['output']
