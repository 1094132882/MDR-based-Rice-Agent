#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境配置辅助工具
帮助快速创建 .env 文件

用法:
  python methods/s_cot_raps/setup_env.py
  
  或指定输出路径:
  python methods/s_cot_raps/setup_env.py --output /path/to/.env
"""
import os
import sys
from pathlib import Path
import argparse


DEFAULT_CONFIG = {
    "NEO4J_URI": "bolt://localhost:7689",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11501",
    "OLLAMA_MODEL": "qwen3_q_32b",
}


def find_project_root() -> Path:
    """查找项目根目录（包含 rice_Python 的目录）"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "rice_Python").is_dir():
            return parent
    # 默认返回当前工作目录
    return Path.cwd()


def check_existing_env(env_path: Path) -> dict:
    """检查现有 .env 文件的配置"""
    if not env_path.exists():
        return {}
    
    existing = {}
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Failed to read existing .env file: {e}")
    
    return existing


def prompt_for_value(key: str, default: str, existing: str = None) -> str:
    """交互式提示用户输入配置值"""
    if existing:
        prompt = f"{key} (current: {existing}, default: {default}): "
    else:
        prompt = f"{key} (default: {default}): "
    
    value = input(prompt).strip()
    
    if not value:
        # 如果用户直接回车，优先使用现有值，否则用默认值
        return existing if existing else default
    
    return value


def create_env_file(output_path: Path, config: dict, interactive: bool = True):
    """创建或更新 .env 文件"""
    print("\n" + "="*60)
    print("Neo4j + Ollama Environment Setup")
    print("="*60 + "\n")
    
    # 检查现有配置
    existing = check_existing_env(output_path)
    
    if existing:
        print(f"Found existing .env file at: {output_path}")
        if interactive:
            response = input("Do you want to update it? (y/n, default: y): ").strip().lower()
            if response and response != 'y':
                print("Aborted.")
                return
    else:
        print(f"Creating new .env file at: {output_path}")
    
    print("\nPlease provide the following configuration values:")
    print("(Press Enter to use the default or existing value)\n")
    
    # 收集配置
    final_config = {}
    for key, default_value in DEFAULT_CONFIG.items():
        if interactive:
            final_config[key] = prompt_for_value(
                key,
                default_value,
                existing.get(key)
            )
        else:
            # 非交互模式：保留现有值或使用默认值
            final_config[key] = existing.get(key, default_value)
    
    # 写入文件
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Neo4j Configuration\n")
            f.write(f"NEO4J_URI={final_config['NEO4J_URI']}\n")
            f.write(f"NEO4J_USERNAME={final_config['NEO4J_USERNAME']}\n")
            f.write(f"NEO4J_PASSWORD={final_config['NEO4J_PASSWORD']}\n")
            f.write("\n")
            f.write("# Ollama Configuration\n")
            f.write(f"OLLAMA_BASE_URL={final_config['OLLAMA_BASE_URL']}\n")
            f.write(f"OLLAMA_MODEL={final_config['OLLAMA_MODEL']}\n")
        
        print("\n" + "="*60)
        print("✓ Configuration saved successfully!")
        print("="*60)
        print(f"\nFile location: {output_path}")
        print("\nConfiguration:")
        for key, value in final_config.items():
            display_value = '*' * 8 if 'PASSWORD' in key else value
            print(f"  {key} = {display_value}")
        
        print("\n" + "="*60)
        print("Next steps:")
        print("="*60)
        print("\n1. Verify Neo4j is running:")
        print("   neo4j status")
        print("\n2. Test Neo4j connection:")
        print(f"   cypher-shell -a {final_config['NEO4J_URI']} \\")
        print(f"     -u {final_config['NEO4J_USERNAME']} \\")
        print(f"     -p {final_config['NEO4J_PASSWORD']} \\")
        print('     "RETURN 1"')
        print("\n3. Verify Ollama is running:")
        print(f"   curl {final_config['OLLAMA_BASE_URL']}/api/tags")
        print("\n4. Run the evaluation:")
        print("   python methods/s_cot_raps/run.py \\")
        print("     --engine py \\")
        print("     --method ground_truth \\")
        print("     --input methods/s_cot_raps/dataset.csv \\")
        print("     --out methods/s_cot_raps/runs/test.jsonl \\")
        print("     --max 5")
        print("\n" + "="*60 + "\n")
        
    except Exception as e:
        print(f"\n✗ Failed to write .env file: {e}", file=sys.stderr)
        sys.exit(1)


def verify_config(env_path: Path):
    """验证配置文件"""
    if not env_path.exists():
        print(f"✗ .env file not found at: {env_path}")
        return False
    
    print(f"\n{'='*60}")
    print("Configuration Verification")
    print('='*60 + "\n")
    
    # 加载配置
    from dotenv import load_dotenv
    load_dotenv(env_path)
    
    all_ok = True
    for key in DEFAULT_CONFIG.keys():
        value = os.getenv(key)
        if value:
            display_value = '*' * 8 if 'PASSWORD' in key else value
            print(f"  ✓ {key} = {display_value}")
        else:
            print(f"  ✗ {key} = NOT SET")
            all_ok = False
    
    print("\n" + "="*60)
    
    if all_ok:
        print("✓ All required variables are set")
        
        # 测试 Neo4j 连接
        print("\nTesting Neo4j connection...")
        try:
            from py2neo import Graph
            neo4j_uri = os.getenv("NEO4J_URI")
            neo4j_user = os.getenv("NEO4J_USERNAME")
            neo4j_pass = os.getenv("NEO4J_PASSWORD")
            
            graph = Graph(neo4j_uri, auth=(neo4j_user, neo4j_pass))
            result = graph.run("RETURN 1 as test").data()
            
            if result:
                print(f"  ✓ Successfully connected to {neo4j_uri}")
            else:
                print(f"  ✗ Query failed")
                all_ok = False
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
            all_ok = False
    else:
        print("✗ Some required variables are missing")
    
    print("="*60 + "\n")
    
    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Setup .env file for Rice MDR project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive setup (recommended)
  python methods/s_cot_raps/setup_env.py
  
  # Non-interactive with custom output path
  python methods/s_cot_raps/setup_env.py --output /path/to/.env --no-interactive
  
  # Verify existing configuration
  python methods/s_cot_raps/setup_env.py --verify
"""
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output path for .env file (default: project root/.env)'
    )
    
    parser.add_argument(
        '--no-interactive',
        action='store_true',
        help='Non-interactive mode (use defaults or existing values)'
    )
    
    parser.add_argument(
        '--verify', '-v',
        action='store_true',
        help='Verify existing configuration without modifying'
    )
    
    args = parser.parse_args()
    
    # 确定输出路径
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        project_root = find_project_root()
        output_path = project_root / ".env"
    
    # 验证模式
    if args.verify:
        success = verify_config(output_path)
        sys.exit(0 if success else 1)
    
    # 创建/更新配置
    create_env_file(
        output_path,
        DEFAULT_CONFIG,
        interactive=not args.no_interactive
    )


if __name__ == "__main__":
    main()

