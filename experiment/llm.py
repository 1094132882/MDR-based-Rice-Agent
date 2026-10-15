#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔌 Universal LLM Factory - 万能 LLM 工厂

支持通过环境变量无缝切换任何 LLM 提供商：
- ollama: 本地 Ollama (Qwen, Llama, Mistral, etc.)
- openai: OpenAI GPT-4 / GPT-3.5 / o1
- deepseek: DeepSeek V3 (OpenAI 兼容)
- moonshot: 月之暗面 Kimi (OpenAI 兼容)
- qwen: 阿里通义千问 (OpenAI 兼容)
- zhipu: 智谱 GLM (OpenAI 兼容)
- anthropic: Anthropic Claude 3.5
- google: Google Gemini

设计模式: Factory Pattern (工厂模式)
- 可插拔 LLM 接口
- 零代码切换模型
- 高扩展性与可复现性

切换示例:
    # 本地 Ollama
    export LLM_PROVIDER=ollama
    export LLM_MODEL_NAME=qwen3:14b
    
    # DeepSeek
    export LLM_PROVIDER=openai
    export LLM_API_BASE=https://api.deepseek.com
    export LLM_API_KEY=sk-xxx
    export LLM_MODEL_NAME=deepseek-chat
    
    # Claude
    export LLM_PROVIDER=anthropic
    export LLM_API_KEY=sk-ant-xxx
    export LLM_MODEL_NAME=claude-3-5-sonnet-20241022

@author: jingwen.wu
@Time: 2025/12
"""
import os
import sys
from pathlib import Path
from typing import Optional, Any

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "methods" / "s_cot_raps"))

# 导入统一配置
from methods.s_cot_raps.config import Config


class LLMFactory:
    """
    🔌 LLM 工厂类 - 根据配置创建对应的 LLM 实例
    
    支持的提供商:
    - ollama: 本地 Ollama
    - openai: OpenAI / OpenAI 兼容 API (DeepSeek, Moonshot, vLLM, etc.)
    - anthropic: Anthropic Claude
    - google: Google Gemini
    
    Usage:
        llm = LLMFactory.create()  # 自动根据 Config 创建
        llm = LLMFactory.create_ollama()  # 强制使用 Ollama
        llm = LLMFactory.create_openai(api_key="sk-xxx", base_url="https://api.deepseek.com")
    """
    
    # 支持的提供商列表
    SUPPORTED_PROVIDERS = ["ollama", "openai", "anthropic", "google"]
    
    # OpenAI 兼容的提供商（使用 openai 协议）
    OPENAI_COMPATIBLE = ["openai", "deepseek", "moonshot", "qwen", "zhipu", "siliconflow", "vllm"]
    
    @classmethod
    def create(cls, provider: str = None, **kwargs) -> Any:
        """
        创建 LLM 实例（核心工厂方法）
        
        Args:
            provider: LLM 提供商（不传则从 Config 读取）
            **kwargs: 额外参数（覆盖默认配置）
        
        Returns:
            LangChain ChatModel 实例
        
        Raises:
            ValueError: 不支持的提供商
            ImportError: 缺少依赖包
        """
        _provider = (provider or Config.LLM_PROVIDER).lower()
        
        print(f"🤖 [LLM Factory] Creating {_provider} instance...")
        
        # 1. Ollama (本地)
        if _provider == "ollama":
            return cls.create_ollama(**kwargs)
        
        # 2. OpenAI & 兼容 API (DeepSeek, Moonshot, vLLM, etc.)
        elif _provider in cls.OPENAI_COMPATIBLE or _provider == "openai":
            return cls.create_openai(**kwargs)
        
        # 3. Anthropic (Claude)
        elif _provider == "anthropic":
            return cls.create_anthropic(**kwargs)
        
        # 4. Google (Gemini)
        elif _provider == "google":
            return cls.create_google(**kwargs)
        
        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: {_provider}\n"
                f"Supported providers: {cls.SUPPORTED_PROVIDERS + cls.OPENAI_COMPATIBLE}"
            )
    
    @classmethod
    def create_ollama(
        cls,
        base_url: str = None,
        model: str = None,
        temperature: float = None,
        **kwargs
    ) -> Any:
        """
        创建 Ollama LLM 实例
        
        Args:
            base_url: Ollama API 地址 (默认 http://127.0.0.1:11501)
            model: 模型名称 (默认 qwen3:14b)
            temperature: 温度参数 (默认 0.4)
        
        Returns:
            ChatOllama 实例
        """
        # 兼容性导入：优先使用 langchain_ollama，回退到 langchain_community
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOllama
            except ImportError:
                raise ImportError(
                    "Neither langchain_ollama nor langchain_community is available.\n"
                    "Install with: pip install langchain-ollama or pip install langchain-community"
                )
        
        _base_url = base_url or Config.OLLAMA_BASE_URL
        _model = model or Config.LLM_MODEL_NAME or Config.OLLAMA_MODEL
        _temperature = temperature if temperature is not None else Config.LLM_TEMPERATURE
        
        # 确保 URL 末尾有斜杠
        if not _base_url.endswith('/'):
            _base_url = _base_url + '/'
        
        print(f"   📍 Base URL: {_base_url}")
        print(f"   📍 Model: {_model}")
        
        return ChatOllama(
            base_url=_base_url,
            model=_model,
            temperature=_temperature,
            **kwargs
        )
    
    @classmethod
    def create_openai(
        cls,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        temperature: float = None,
        **kwargs
    ) -> Any:
        """
        创建 OpenAI / OpenAI 兼容 LLM 实例
        
        支持: OpenAI, DeepSeek, Moonshot, Qwen-Cloud, 智谱, SiliconFlow, vLLM
        
        Args:
            api_key: API 密钥
            base_url: API 地址 (留空使用 OpenAI 官方)
            model: 模型名称
            temperature: 温度参数
        
        Returns:
            ChatOpenAI 实例
        """
        from langchain_openai import ChatOpenAI
        
        _api_key = api_key or Config.LLM_API_KEY
        _base_url = base_url or Config.LLM_API_BASE or None  # None = OpenAI 官方
        _model = model or Config.LLM_MODEL_NAME
        _temperature = temperature if temperature is not None else Config.LLM_TEMPERATURE
        
        if not _api_key:
            raise ValueError(
                "LLM_API_KEY is required for OpenAI/compatible providers.\n"
                "Set it via: export LLM_API_KEY=sk-xxx"
            )
        
        print(f"   📍 Base URL: {_base_url or 'https://api.openai.com/v1'}")
        print(f"   📍 Model: {_model}")
        
        return ChatOpenAI(
            model=_model,
            api_key=_api_key,
            base_url=_base_url,
            temperature=_temperature,
            **kwargs
        )
    
    @classmethod
    def create_anthropic(
        cls,
        api_key: str = None,
        model: str = None,
        temperature: float = None,
        **kwargs
    ) -> Any:
        """
        创建 Anthropic Claude LLM 实例
        
        Args:
            api_key: Anthropic API 密钥
            model: 模型名称 (如 claude-3-5-sonnet-20241022)
            temperature: 温度参数
        
        Returns:
            ChatAnthropic 实例
        
        Raises:
            ImportError: 未安装 langchain-anthropic
        """
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic is not installed.\n"
                "Install with: pip install langchain-anthropic"
            )
        
        _api_key = api_key or Config.LLM_API_KEY
        _model = model or Config.LLM_MODEL_NAME or "claude-3-5-sonnet-20241022"
        _temperature = temperature if temperature is not None else Config.LLM_TEMPERATURE
        
        if not _api_key:
            raise ValueError(
                "LLM_API_KEY is required for Anthropic.\n"
                "Set it via: export LLM_API_KEY=sk-ant-xxx"
            )
        
        print(f"   📍 Model: {_model}")
        
        return ChatAnthropic(
            model=_model,
            api_key=_api_key,
            temperature=_temperature,
            **kwargs
        )
    
    @classmethod
    def create_google(
        cls,
        api_key: str = None,
        model: str = None,
        temperature: float = None,
        **kwargs
    ) -> Any:
        """
        创建 Google Gemini LLM 实例
        
        Args:
            api_key: Google AI API 密钥
            model: 模型名称 (如 gemini-1.5-pro)
            temperature: 温度参数
        
        Returns:
            ChatGoogleGenerativeAI 实例
        
        Raises:
            ImportError: 未安装 langchain-google-genai
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai is not installed.\n"
                "Install with: pip install langchain-google-genai"
            )
        
        _api_key = api_key or Config.LLM_API_KEY
        _model = model or Config.LLM_MODEL_NAME or "gemini-1.5-pro"
        _temperature = temperature if temperature is not None else Config.LLM_TEMPERATURE
        
        if not _api_key:
            raise ValueError(
                "LLM_API_KEY is required for Google.\n"
                "Set it via: export LLM_API_KEY=xxx"
            )
        
        print(f"   📍 Model: {_model}")
        
        return ChatGoogleGenerativeAI(
            model=_model,
            google_api_key=_api_key,
            temperature=_temperature,
            **kwargs
        )


def get_llm_instance(**kwargs) -> Any:
    """
    获取 LLM 实例（便捷函数）
    
    根据 Config.LLM_PROVIDER 自动创建对应的 LLM 实例。
    
    Returns:
        LangChain ChatModel 实例
    """
    return LLMFactory.create(**kwargs)


# ============== 创建默认 LLM 实例 ==============
# 根据 Config 自动选择提供商
try:
    llm = LLMFactory.create()
    print(f"✓ [LLM] Initialized: {Config.LLM_PROVIDER} / {Config.LLM_MODEL_NAME}")
except Exception as e:
    print(f"⚠️ [LLM] Failed to initialize: {e}")
    print("   Falling back to Ollama...")
    try:
        llm = LLMFactory.create_ollama()
    except Exception as e2:
        print(f"⚠️ [LLM] Fallback also failed: {e2}")
        llm = None


# ============== 测试代码 ==============
if __name__ == "__main__":
    Config.print_config()
    
    print("\n=== Testing LLM Factory ===\n")
    
    print("Supported providers:")
    print(f"  Core: {LLMFactory.SUPPORTED_PROVIDERS}")
    print(f"  OpenAI-compatible: {LLMFactory.OPENAI_COMPATIBLE}")
    
    print("\n--- Testing current config ---")
    try:
        test_llm = LLMFactory.create()
        print(f"✓ LLM created successfully!")
        
        # 简单测试
        print("\nTesting inference...")
        response = test_llm.invoke("你好，请用一句话介绍自己。")
        print(f"Response: {response.content[:200]}...")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n--- Provider switching examples ---")
    print("""
    # 切换到 DeepSeek:
    export LLM_PROVIDER=openai
    export LLM_API_BASE=https://api.deepseek.com
    export LLM_API_KEY=sk-xxx
    export LLM_MODEL_NAME=deepseek-chat
    
    # 切换到 Claude:
    export LLM_PROVIDER=anthropic
    export LLM_API_KEY=sk-ant-xxx
    export LLM_MODEL_NAME=claude-3-5-sonnet-20241022
    
    # 切换到本地 Ollama:
    export LLM_PROVIDER=ollama
    export OLLAMA_BASE_URL=http://127.0.0.1:11501
    export LLM_MODEL_NAME=qwen3:14b
    """)
