# -*- coding: utf-8 -*-
# App/chat/llm.py

from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os

load_dotenv()
llm = ChatOllama(
    base_url="http://127.0.0.1:11501",  # 你说的固定端口
    model="qwen3:14b",                   # 换成你服务器上真的有的模型名
    temperature=0.4,
)

