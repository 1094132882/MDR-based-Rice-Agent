"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/02/20 17:39
"""
from langchain_neo4j import Neo4jGraph
import time
from dotenv import load_dotenv
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 增强的配置加载：从多个位置查找 .env 文件
# ---------------------------------------------------------------------------
def find_and_load_dotenv():
    """
    智能查找并加载 .env 文件
    优先级：
    1. 当前工作目录的 .env
    2. 脚本所在目录往上找到的项目根目录的 .env
    3. 项目根目录（包含 rice_Python 文件夹）的 .env
    """
    # 尝试多个可能的 .env 位置
    search_paths = []
    
    # 1. 当前工作目录
    search_paths.append(Path.cwd() / ".env")
    
    # 2. 从当前文件往上找项目根（包含 rice_Python 的目录）
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "rice_Python").is_dir():
            search_paths.append(parent / ".env")
            break
    
    # 3. 尝试 rice_Python 的父目录
    rice_python_parent = Path(__file__).resolve().parent.parent.parent.parent
    search_paths.append(rice_python_parent / ".env")
    
    # 尝试加载找到的第一个 .env 文件
    for env_path in search_paths:
        if env_path.exists():
            load_dotenv(env_path)
            return str(env_path)
    
    # 如果都没找到，至少调用一次 load_dotenv()，它会从环境变量中读取
    load_dotenv()
    return None

# 加载配置
env_file = find_and_load_dotenv()

# ---------------------------------------------------------------------------
# 验证配置并提供友好的错误提示
# ---------------------------------------------------------------------------
def validate_neo4j_config():
    """验证 Neo4j 配置是否完整"""
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    
    missing = []
    if not neo4j_uri:
        missing.append("NEO4J_URI")
    if not neo4j_password:
        missing.append("NEO4J_PASSWORD")
    
    if missing:
        error_msg = f"""
╔════════════════════════════════════════════════════════════════╗
║  Neo4j Configuration Error                                     ║
╚════════════════════════════════════════════════════════════════╝

Missing required environment variables: {', '.join(missing)}

Current configuration:
  - .env file: {env_file or 'NOT FOUND'}
  - NEO4J_URI: {neo4j_uri or 'NOT SET'}
  - NEO4J_USERNAME: {neo4j_user}
  - NEO4J_PASSWORD: {'SET' if neo4j_password else 'NOT SET'}

To fix this issue:

1. Create a .env file in your project root directory with:
   
   NEO4J_URI=bolt://localhost:7689
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password_here

2. Or set environment variables before running:
   
   export NEO4J_URI=bolt://localhost:7689
   export NEO4J_USERNAME=neo4j
   export NEO4J_PASSWORD=your_password_here

3. Or use the setup helper:
   
   python methods/s_cot_raps/setup_env.py

╚════════════════════════════════════════════════════════════════╝
"""
        print(error_msg, file=sys.stderr)
        raise ValueError(f"Missing Neo4j configuration: {', '.join(missing)}")
    
    return neo4j_uri, neo4j_user, neo4j_password

# 验证配置
neo4j_uri, neo4j_user, neo4j_password = validate_neo4j_config()

# ---------------------------------------------------------------------------
# 连接 Neo4j 数据库
# ---------------------------------------------------------------------------
start = time.time()
print("Loading graph...")

try:
    graph = Neo4jGraph(
        url=neo4j_uri,
        username=neo4j_user,
        password=neo4j_password,
        refresh_schema=False,
    )
    
    end_time = time.time()
    elapsed_time_minutes = (end_time - start) / 60
    print(f"Graph loaded in {elapsed_time_minutes:.2f} minutes")
    
except Exception as e:
    error_msg = f"""
╔════════════════════════════════════════════════════════════════╗
║  Neo4j Connection Error                                        ║
╚════════════════════════════════════════════════════════════════╝

Failed to connect to Neo4j database.

Error: {str(e)}

Configuration used:
  - URI: {neo4j_uri}
  - Username: {neo4j_user}
  - Password: {'*' * len(neo4j_password) if neo4j_password else 'NOT SET'}

Please verify:
  1. Neo4j is running: neo4j status
  2. The URI, username, and password are correct
  3. The database is accessible from this machine

If authentication failed multiple times, you may need to:
  - Restart Neo4j: neo4j restart
  - Wait a few minutes for rate limit to reset

╚════════════════════════════════════════════════════════════════╝
"""
    print(error_msg, file=sys.stderr)
    raise
