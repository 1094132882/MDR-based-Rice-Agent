"""
langchain 版本兼容层
适配 langchain-neo4j 0.6.0 + langchain-core 1.0.4
"""
import sys

# 修复 PromptTemplate 导入
try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    from langchain.prompts.prompt import PromptTemplate

# 修复 GraphCypherQAChain 导入
try:
    from langchain_neo4j import GraphCypherQAChain
except ImportError:
    try:
        from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
    except ImportError:
        from langchain.chains.graph_qa.cypher import GraphCypherQAChain

# 导出
__all__ = ['PromptTemplate', 'GraphCypherQAChain']

