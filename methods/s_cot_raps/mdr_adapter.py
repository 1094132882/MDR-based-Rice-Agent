#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔌 MDR Schema Adapter - 动态 Schema 管理器

核心改进：
1. ❌ 不再从静态 JSON 文件读取
2. ✅ 直接从 Neo4j 动态获取 MDR 元数据
3. ✅ 使用 config.py 的端口配置（7689）
4. ✅ 提供缓存机制避免重复查询
5. ✅ 为 prompt_builder 提供统一接口

使用方式:
    from mdr_adapter import MDRSchemaAdapter
    
    adapter = MDRSchemaAdapter()
    constraints = adapter.get_constraints("gene_basic_info")

@author: jingwen.wu
@Time: 2025/12
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from functools import lru_cache

# 确保能导入 config
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入统一配置
from methods.s_cot_raps.config import Config

# 导入动态 Schema 导出器
from methods.s_cot_raps.export_schema import MDRSchemaExporter, get_mdr_schema, get_tool_constraints, load_mdr_schema


class MDRSchemaAdapter:
    """
    MDR Schema 适配器 - 动态版本
    
    核心功能：
    1. 从 Neo4j 动态获取 DEC/VD/MPS
    2. 提供工具级别的约束查询
    3. 缓存机制提高性能
    
    用法:
        adapter = MDRSchemaAdapter()
        
        # 获取完整 schema
        schema = adapter.get_full_schema()
        
        # 获取特定工具的约束
        constraints = adapter.get_constraints("gene_basic_info")
        
        # 获取别名映射
        mappings = adapter.get_mappings("gene_basic_info")
    """
    
    def __init__(self, use_cache: bool = True):
        """
        初始化适配器
        
        Args:
            use_cache: 是否使用缓存（默认 True）
        """
        self.use_cache = use_cache
        self._exporter = None
        self._schema_cache = None
    
    @property
    def exporter(self) -> MDRSchemaExporter:
        """懒加载 Schema 导出器"""
        if self._exporter is None:
            self._exporter = MDRSchemaExporter()
        return self._exporter
    
    def get_full_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取完整的 MDR Schema
        
        Args:
            force_refresh: 是否强制刷新
        
        Returns:
            {
                "DEC": [...],
                "VD": {...},
                "MPS": {...},
                "Tools": {...}
            }
        """
        if self._schema_cache is None or force_refresh or not self.use_cache:
            self._schema_cache = self.exporter.export_all()
        return self._schema_cache
    
    def get_constraints(self, tool_name: str) -> Dict[str, Any]:
        """
        获取指定工具的值域约束
        
        Args:
            tool_name: 工具名（如 "gene_basic_info"）
        
        Returns:
            {
                "vd_constraints": {
                    "Strand": ["+", "-"],
                    "Chromosome": ["Chr01", ..., "Chr12"]
                },
                ...
            }
        """
        return self.exporter.get_constraints_for_tool(tool_name)
    
    def get_mappings(self, tool_name: str = None) -> Dict[str, str]:
        """
        获取别名映射
        
        Args:
            tool_name: 工具名（可选，不传则返回全部映射）
        
        Returns:
            {
                "正链": "+",
                "负链": "-",
                ...
            }
        """
        schema = self.get_full_schema()
        return schema.get("MPS", {})
    
    def get_value_domain(self, field_name: str) -> Optional[List[str]]:
        """
        获取指定字段的值域
        
        Args:
            field_name: 字段名（如 "Strand"）
        
        Returns:
            可允许值列表
        """
        return self.exporter.get_vd_for_field(field_name)
    
    def get_dec_list(self) -> List[str]:
        """获取数据元概念列表"""
        schema = self.get_full_schema()
        return schema.get("DEC", [])
    
    def get_value_domains(self) -> Dict[str, List[str]]:
        """获取所有值域"""
        schema = self.get_full_schema()
        return schema.get("VD", {})
    
    def get_schema_for_tool(self, tool_name: str, use_dynamic: bool = True) -> Dict[str, Any]:
        """
        获取工具相关的 Schema（兼容旧接口）
        
        Args:
            tool_name: 工具名
            use_dynamic: 是否使用动态 Schema（总是 True）
        
        Returns:
            包含 DEC/VD/MPS 的字典
        """
        constraints = self.get_constraints(tool_name)
        schema = self.get_full_schema()
        
        return {
            "DEC": schema.get("DEC", []),
            "VD": constraints.get("vd_constraints", {}),
            "MPS": schema.get("MPS", {}),
            "tool": tool_name,
            "description": constraints.get("description", ""),
            "input_fields": constraints.get("input_fields", []),
            "output_fields": constraints.get("output_fields", [])
        }
    
    def validate_value(self, field_name: str, value: Any) -> tuple:
        """
        验证值是否在值域内
        
        Args:
            field_name: 字段名
            value: 待验证的值
        
        Returns:
            (is_valid: bool, error_msg: str)
        """
        vd = self.get_value_domain(field_name)
        
        if vd is None:
            # 没有值域约束，视为有效
            return True, ""
        
        if value in vd:
            return True, ""
        
        # 尝试别名映射
        mappings = self.get_mappings()
        canonical = mappings.get(str(value))
        if canonical and canonical in vd:
            return True, ""
        
        return False, f"Value '{value}' not in allowed list {vd[:10]}{'...' if len(vd) > 10 else ''}"
    
    def normalize_value(self, field_name: str, value: Any) -> Any:
        """
        将值标准化（应用别名映射）
        
        Args:
            field_name: 字段名
            value: 原始值
        
        Returns:
            标准化后的值
        """
        mappings = self.get_mappings()
        return mappings.get(str(value), value)


# ============================================================
# 兼容旧接口：保持与原 mdr_adapter.py 相同的函数签名
# ============================================================

# 全局单例
_adapter_instance = None

def get_adapter() -> MDRSchemaAdapter:
    """获取适配器单例"""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = MDRSchemaAdapter()
    return _adapter_instance


def get_dec_list() -> List[str]:
    """获取 DEC 列表（兼容旧接口）"""
    return get_adapter().get_dec_list()


def get_value_domains() -> Dict[str, List[str]]:
    """获取所有值域（兼容旧接口）"""
    return get_adapter().get_value_domains()


def get_mappings() -> Dict[str, str]:
    """获取别名映射（兼容旧接口）"""
    return get_adapter().get_mappings()


if __name__ == "__main__":
    # 测试
    print("=== MDR Schema Adapter Test ===\n")
    
    adapter = MDRSchemaAdapter()
    
    # 测试获取 schema
    schema = adapter.get_full_schema()
    print(f"DEC: {len(schema['DEC'])} items")
    print(f"VD: {len(schema['VD'])} domains")
    print(f"MPS: {len(schema['MPS'])} mappings")
    
    # 测试工具约束
    print("\n--- gene_basic_info constraints ---")
    constraints = adapter.get_constraints("gene_basic_info")
    print(f"VD Constraints: {constraints.get('vd_constraints', {})}")
    
    # 测试值验证
    print("\n--- Value Validation ---")
    is_valid, msg = adapter.validate_value("Strand", "+")
    print(f"Strand='+': valid={is_valid}")
    
    is_valid, msg = adapter.validate_value("Strand", "正链")
    print(f"Strand='正链': valid={is_valid}, msg={msg}")
    
    # 测试值标准化
    print("\n--- Value Normalization ---")
    normalized = adapter.normalize_value("Strand", "正链")
    print(f"'正链' -> '{normalized}'")
