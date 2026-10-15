#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔌 统一配置中心 - Configuration Center

所有端口和连接参数集中管理，支持环境变量覆盖。
换端口/模型只需要改这里（或设置环境变量）。

核心配置:
- NEO4J_URI: Neo4j Bolt 连接地址 (默认 7689)
- LLM_PROVIDER: LLM 提供商 (ollama/openai/anthropic/google)
- LLM_API_BASE: LLM API 地址 (支持 OpenAI 兼容接口)

支持的 LLM 提供商:
- ollama: 本地 Ollama (Qwen, Llama, etc.)
- openai: OpenAI GPT-4 / GPT-3.5
- deepseek: DeepSeek (使用 openai 协议)
- moonshot: 月之暗面 Kimi (使用 openai 协议)
- anthropic: Anthropic Claude
- google: Google Gemini

切换模型示例:
    # 使用本地 Ollama
    export LLM_PROVIDER=ollama
    export OLLAMA_BASE_URL=http://127.0.0.1:11501
    export LLM_MODEL_NAME=qwen3:14b
    
    # 使用 DeepSeek
    export LLM_PROVIDER=openai
    export LLM_API_BASE=https://api.deepseek.com
    export LLM_API_KEY=sk-xxx
    export LLM_MODEL_NAME=deepseek-chat
    
    # 使用 Claude
    export LLM_PROVIDER=anthropic
    export LLM_API_KEY=sk-ant-xxx
    export LLM_MODEL_NAME=claude-3-5-sonnet-20241022

@author: jingwen.wu
@Time: 2025/12
"""
import os
from typing import Optional


class Config:
    """
    配置类 - 优先从环境变量读取，否则使用默认值
    
    ⚠️ 重要: 端口必须与你的实际服务匹配！
    - Neo4j Bolt: 7689 (不是默认的 7687)
    - Ollama API: 11501 (不是默认的 11434)
    """

# ============== Neo4j 配置 ==============
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7689")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
    
    # ============== 通用 LLM 配置（工厂模式） ==============
    # 支持: ollama, openai, anthropic, google
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    
    # 模型名称（根据 provider 不同而不同）
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", os.getenv("OLLAMA_MODEL", "qwen3:14b"))
    
    # API 密钥（云端 LLM 需要）
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    
    # API 基础地址（用于 OpenAI 兼容接口，如 DeepSeek, Moonshot, vLLM）
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", os.getenv("OPENAI_API_BASE", ""))
    
    # 温度参数
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", os.getenv("OLLAMA_TEMPERATURE", "0.4")))
    
    # ============== Ollama 特定配置（向后兼容） ==============
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11501")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.4"))

    # ============== 后端服务配置 ==============
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:11500")
    
    # ============== 超时配置 ==============
    NEO4J_TIMEOUT: int = int(os.getenv("NEO4J_TIMEOUT", "30"))  # 秒
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "120"))  # 秒
    
    # ============== 调试配置 ==============
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # ============== 预设的 API 地址（便捷切换） ==============
    PRESET_API_BASES = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com",
        "moonshot": "https://api.moonshot.cn/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "siliconflow": "https://api.siliconflow.cn/v1",
    }
    
    @classmethod
    def get_neo4j_config(cls) -> tuple:
        """获取 Neo4j 连接配置"""
        return (cls.NEO4J_URI, cls.NEO4J_USERNAME, cls.NEO4J_PASSWORD)
    
    @classmethod
    def get_llm_config(cls) -> dict:
        """
        获取 LLM 配置字典（工厂模式核心）
        
        Returns:
            {
                "provider": "ollama" | "openai" | "anthropic" | "google",
                "model": "qwen3:14b" | "gpt-4" | "claude-3-5-sonnet-20241022",
                "api_key": "sk-xxx",
                "api_base": "https://api.xxx.com",
                "temperature": 0.4
            }
        """
        return {
            "provider": cls.LLM_PROVIDER.lower(),
            "model": cls.LLM_MODEL_NAME,
            "api_key": cls.LLM_API_KEY,
            "api_base": cls.LLM_API_BASE or cls.PRESET_API_BASES.get(cls.LLM_PROVIDER.lower(), ""),
            "temperature": cls.LLM_TEMPERATURE,
            # Ollama 特定
            "ollama_base_url": cls.OLLAMA_BASE_URL,
        }
    
    @classmethod
    def get_ollama_config(cls) -> dict:
        """获取 Ollama 配置字典（向后兼容）"""
        return {
            "base_url": cls.OLLAMA_BASE_URL,
            "model": cls.OLLAMA_MODEL,
            "temperature": cls.OLLAMA_TEMPERATURE
        }
    
    @classmethod
    def print_config(cls):
        """打印当前配置（用于调试）"""
        print("\n" + "=" * 60)
        print("🔌 Configuration Center")
        print("=" * 60)
        print(f"📊 NEO4J_URI:       {cls.NEO4J_URI}")
        print(f"📊 NEO4J_USERNAME:  {cls.NEO4J_USERNAME}")
        print(f"📊 NEO4J_PASSWORD:  {'*' * len(cls.NEO4J_PASSWORD)}")
        print("-" * 60)
        print(f"🤖 LLM_PROVIDER:    {cls.LLM_PROVIDER}")
        print(f"🤖 LLM_MODEL_NAME:  {cls.LLM_MODEL_NAME}")
        print(f"🤖 LLM_API_BASE:    {cls.LLM_API_BASE or '(default)'}")
        print(f"🤖 LLM_API_KEY:     {'*' * 8 if cls.LLM_API_KEY else '(not set)'}")
        print(f"🤖 LLM_TEMPERATURE: {cls.LLM_TEMPERATURE}")
        print("-" * 60)
        print(f"🏠 OLLAMA_BASE_URL: {cls.OLLAMA_BASE_URL}")
        print(f"🌐 BACKEND_URL:     {cls.BACKEND_URL}")
        print("=" * 60 + "\n")
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置是否合理"""
        # 基础配置
        if not all([cls.NEO4J_URI, cls.NEO4J_USERNAME, cls.NEO4J_PASSWORD]):
            return False
        
        # LLM 配置
        provider = cls.LLM_PROVIDER.lower()
        if provider == "ollama":
            return bool(cls.OLLAMA_BASE_URL and cls.LLM_MODEL_NAME)
        elif provider in ["openai", "anthropic", "google"]:
            return bool(cls.LLM_API_KEY and cls.LLM_MODEL_NAME)
        
        return True
    
    @classmethod
    def quick_switch(cls, provider: str, model: str = None, api_key: str = None):
        """
        快速切换 LLM 提供商（运行时）
        
        Args:
            provider: ollama, openai, deepseek, moonshot, anthropic, google
            model: 模型名称（可选）
            api_key: API 密钥（可选）
        
        Example:
            Config.quick_switch("deepseek", "deepseek-chat", "sk-xxx")
        """
        cls.LLM_PROVIDER = provider
        
        if model:
            cls.LLM_MODEL_NAME = model
        
        if api_key:
            cls.LLM_API_KEY = api_key
        
        # 设置预设 API 地址
        if provider.lower() in cls.PRESET_API_BASES:
            cls.LLM_API_BASE = cls.PRESET_API_BASES[provider.lower()]
        
        print(f"✓ Switched to {provider}: {cls.LLM_MODEL_NAME}")


# ============== 便捷导出（向后兼容） ==============
NEO4J_URI = Config.NEO4J_URI
NEO4J_USERNAME = Config.NEO4J_USERNAME
NEO4J_PASSWORD = Config.NEO4J_PASSWORD
NEO4J_USER = Config.NEO4J_USERNAME

OLLAMA_BASE_URL = Config.OLLAMA_BASE_URL
OLLAMA_MODEL = Config.OLLAMA_MODEL

LLM_PROVIDER = Config.LLM_PROVIDER
LLM_MODEL_NAME = Config.LLM_MODEL_NAME
LLM_API_KEY = Config.LLM_API_KEY
LLM_API_BASE = Config.LLM_API_BASE

BACKEND_URL = Config.BACKEND_URL


# ============== 自动设置环境变量 ==============
def setup_env():
    """设置环境变量，确保所有模块都能读取到统一配置"""
    os.environ.setdefault('NEO4J_URI', Config.NEO4J_URI)
    os.environ.setdefault('NEO4J_USERNAME', Config.NEO4J_USERNAME)
    os.environ.setdefault('NEO4J_PASSWORD', Config.NEO4J_PASSWORD)
    os.environ.setdefault('NEO4J_USER', Config.NEO4J_USERNAME)
    
    os.environ.setdefault('OLLAMA_BASE_URL', Config.OLLAMA_BASE_URL)
    os.environ.setdefault('OLLAMA_MODEL', Config.OLLAMA_MODEL)
    
    os.environ.setdefault('LLM_PROVIDER', Config.LLM_PROVIDER)
    os.environ.setdefault('LLM_MODEL_NAME', Config.LLM_MODEL_NAME)
    
    os.environ.setdefault('BACKEND_URL', Config.BACKEND_URL)


# 导入时自动设置环境变量
setup_env()


# ============== 测试代码 ==============
if __name__ == "__main__":
    Config.print_config()
    
    print("Testing configuration validation...")
    is_valid = Config.validate()
    print(f"✓ Configuration valid: {is_valid}")
    
    print("\nTesting get_llm_config()...")
    llm_cfg = Config.get_llm_config()
    print(f"  Provider: {llm_cfg['provider']}")
    print(f"  Model: {llm_cfg['model']}")
    print(f"  API Base: {llm_cfg['api_base'] or '(not set)'}")
    
    print("\n📋 Preset API Bases:")
    for name, url in Config.PRESET_API_BASES.items():
        print(f"  - {name}: {url}")
