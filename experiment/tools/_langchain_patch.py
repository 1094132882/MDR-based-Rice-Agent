"""
Langchain 兼容性补丁
修复 langchain-core 1.0+ 中 PipelinePromptTemplate 缺失问题
"""
import sys

def apply_patch():
    """在导入其他模块前调用此函数"""
    # 检查是否需要补丁
    try:
        from langchain_core.prompts import PipelinePromptTemplate
        return  # 已存在，不需要补丁
    except ImportError:
        pass
    
    # 创建一个简单的 PipelinePromptTemplate 替代品
    from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
    
    class PipelinePromptTemplate(PromptTemplate):
        """
        简化版 PipelinePromptTemplate
        用于兼容旧版 langchain 代码
        """
        pipeline_prompts: list = []
        final_prompt: PromptTemplate = None
        
        def __init__(self, pipeline_prompts=None, final_prompt=None, **kwargs):
            if final_prompt:
                super().__init__(
                    template=final_prompt.template if hasattr(final_prompt, 'template') else str(final_prompt),
                    input_variables=final_prompt.input_variables if hasattr(final_prompt, 'input_variables') else [],
                    **kwargs
                )
            else:
                super().__init__(template="", input_variables=[], **kwargs)
            self.pipeline_prompts = pipeline_prompts or []
            self.final_prompt = final_prompt
        
        def format(self, **kwargs):
            # 简化实现：直接使用 final_prompt
            if self.final_prompt:
                return self.final_prompt.format(**kwargs)
            return super().format(**kwargs)
    
    # 注入到 langchain_core.prompts
    import langchain_core.prompts
    langchain_core.prompts.PipelinePromptTemplate = PipelinePromptTemplate
    
    # 也注入到 langchain_core.prompts 的 __init__ 导出
    if hasattr(langchain_core.prompts, '__all__'):
        if 'PipelinePromptTemplate' not in langchain_core.prompts.__all__:
            # __all__ 可能是 tuple，需要转换
            try:
                langchain_core.prompts.__all__ = list(langchain_core.prompts.__all__) + ['PipelinePromptTemplate']
            except:
                pass  # 忽略错误，注入主类已经够用了
    
    print("✓ Langchain compatibility patch applied")

# 自动应用补丁
apply_patch()

