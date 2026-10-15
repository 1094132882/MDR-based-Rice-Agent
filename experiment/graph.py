#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j Graph Connection Module

统一的 Neo4j 连接模块，使用 config.py 的配置。
⚠️ 端口已统一为 7689（不是默认的 7687）

使用方式:
    from experiment.graph import graph
    result = graph.query("MATCH (n) RETURN n LIMIT 5")

@author: jingwen.wu
"""
import os
import sys
import time
from pathlib import Path

# 添加项目路径，确保能导入 config
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "methods" / "s_cot_raps"))

# 导入统一配置
try:
    from methods.s_cot_raps.config import Config
except ImportError:
    # 如果直接运行此文件，尝试相对导入
    sys.path.insert(0, str(Path(__file__).parent.parent / "methods" / "s_cot_raps"))
    from config import Config

# 兼容性导入：优先使用 langchain_neo4j，回退到 langchain_community
try:
    from langchain_neo4j import Neo4jGraph
except ImportError:
    try:
        from langchain_community.graphs import Neo4jGraph
    except ImportError:
        raise ImportError(
            "Neither langchain_neo4j nor langchain_community.graphs is available. "
            "Install with: pip install langchain-neo4j or pip install langchain-community"
        )


def get_neo4j_config():
    """
    获取 Neo4j 连接配置
    
    优先级:
    1. 环境变量
    2. config.py 中的默认值
    3. Streamlit secrets（仅 Web 应用）
    
    Returns:
        (uri, username, password)
    """
    # 使用 Config 类获取配置（已处理环境变量）
    uri = Config.NEO4J_URI
    username = Config.NEO4J_USERNAME
    password = Config.NEO4J_PASSWORD
    
    if uri and username and password:
        return uri, username, password
    
    # 回退到 streamlit secrets（仅在 Web 应用中使用）
    try:
        import streamlit as st
        return st.secrets["NEO4J_URI"], st.secrets["NEO4J_USERNAME"], st.secrets["NEO4J_PASSWORD"]
    except:
        pass
    
    raise RuntimeError("Set NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD before connecting")


def create_graph_connection(max_retries: int = 3, retry_delay: float = 2.0):
    """
    创建 Neo4j Graph 连接（带重试）
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
    
    Returns:
        Neo4jGraph 实例
    
    Raises:
        ConnectionError: 无法连接到 Neo4j
    """
    uri, username, password = get_neo4j_config()
    
    for attempt in range(max_retries):
        try:
            print(f"🔌 [Neo4j] Connecting to {uri}...")
            _graph = Neo4jGraph(
                url=uri,
                username=username,
                password=password,
                refresh_schema=False,
            )
            # 测试连接
            _graph.query("RETURN 1 as test")
            print(f"✓ [Neo4j] Successfully connected to {uri}")
            return _graph
        except Exception as e:
            print(f"⚠️ [Neo4j] Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                print(f"   Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    raise ConnectionError(f"Failed to connect to Neo4j at {uri} after {max_retries} attempts")


# ============== 创建全局 Graph 实例 ==============
start = time.time()
print("Loading graph...")
uri, username, password = get_neo4j_config()

try:
    graph = Neo4jGraph(
        url=uri,
        username=username,
        password=password,
        refresh_schema=False,
    )
    end_time = time.time()
    elapsed_time_minutes = (end_time - start) / 60
    print(f"✓ Graph loaded from {uri} in {elapsed_time_minutes:.2f} minutes")
except Exception as e:
    print(f"⚠️ Warning: Failed to load graph: {e}")
    print(f"   Using URI: {uri}")
    # 创建一个空的占位符（避免导入失败）
    graph = None


if __name__ == "__main__":
    # 测试连接
    Config.print_config()
    
    print("\n=== Testing Neo4j Connection ===")
    if graph:
        result = graph.query("RETURN 1 as test")
        print(f"✓ Connection test passed: {result}")
        
        # 测试查询
        print("\n=== Sample Query ===")
        result = graph.query("MATCH (n) RETURN labels(n) as labels, count(*) as count LIMIT 10")
        for r in result:
            print(f"  {r}")
    else:
        print("✗ Graph is not connected")
