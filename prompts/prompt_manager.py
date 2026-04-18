"""
提示词管理模块
提供提示词版本管理、多语言支持、不同场景模板
"""
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate

from utils.logger import get_logger

logger = get_logger("prompt_manager")


class PromptScenario(Enum):
    """提示词场景枚举"""
    CODE_EXPLANATION = "code_explanation"
    BUG_FIX = "bug_fix"
    ARCHITECTURE_DESIGN = "architecture_design"
    CODE_REVIEW = "code_review"
    GENERAL_QA = "general_qa"
    AGENT_SYSTEM = "agent_system"      # Agent 系统提示词
    SUMMARIZATION = "summarization"    # 总结提示词


class PromptLanguage(Enum):
    """提示词语言枚举"""
    ZH_CN = "zh-CN"
    EN_US = "en-US"


@dataclass
class PromptVersion:
    """提示词版本信息"""
    version: str
    scenario: PromptScenario
    language: PromptLanguage
    template: str
    input_variables: list
    description: str
    created_at: str


class PromptManager:
    """提示词管理器"""

    # 单例实例
    _instance: Optional['PromptManager'] = None

    # 提示词存储
    _prompts: Dict[str, PromptVersion] = {}

    # 当前版本
    _current_version: str = "1.0.0"

    def __new__(cls) -> 'PromptManager':
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_default_prompts()
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'PromptManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize_default_prompts(self) -> None:
        """初始化默认提示词模板"""
        logger.info("初始化默认提示词模板...")

        # 中文通用问答提示词
        self._register_prompt(PromptVersion(
            version="1.0.0",
            scenario=PromptScenario.GENERAL_QA,
            language=PromptLanguage.ZH_CN,
            template="""你是一个专业的代码助手，精通软件工程和代码分析。请根据提供的代码上下文，准确、详细地回答用户的问题。

## 上下文信息
{context}

## 用户问题
{question}

## 回答要求
1. 如果答案在上下文中，请直接引用相关代码片段并提供详细解释
2. 如果上下文不足，请根据现有信息提供合理的分析和建议
3. 回答应该条理清晰，分点说明
4. 对于代码相关问题，提供具体的代码示例或修改建议
5. 请用中文回答

现在开始回答：""",
            input_variables=["context", "question"],
            description="通用代码问答提示词（中文）",
            created_at="2024-01-01"
        ))

        # 英文通用问答提示词
        self._register_prompt(PromptVersion(
            version="1.0.0",
            scenario=PromptScenario.GENERAL_QA,
            language=PromptLanguage.EN_US,
            template="""You are a professional code assistant, proficient in software engineering and code analysis. Please answer the user's questions accurately and in detail based on the provided code context.

## Context Information
{context}

## User Question
{question}

## Answer Requirements
1. If the answer is in the context, please directly quote the relevant code snippets and provide detailed explanations
2. If the context is insufficient, please provide reasonable analysis and suggestions based on existing information
3. The answer should be well-organized and explained in points
4. For code-related questions, provide specific code examples or modification suggestions
5. Please answer in English

Now begin answering:""",
            input_variables=["context", "question"],
            description="General code Q&A prompt (English)",
            created_at="2024-01-01"
        ))

        # 中文代码解释提示词
        self._register_prompt(PromptVersion(
            version="1.0.0",
            scenario=PromptScenario.CODE_EXPLANATION,
            language=PromptLanguage.ZH_CN,
            template="""你是一个专业的代码讲解员。请详细解释以下代码的功能、结构和关键点。

## 代码上下文
{context}

## 用户问题
{question}

## 解释要求
1. 代码的整体功能是什么？
2. 核心类/函数的作用是什么？
3. 关键算法或逻辑的工作原理
4. 代码的优缺点分析
5. 请用中文回答

请开始解释：""",
            input_variables=["context", "question"],
            description="代码解释提示词（中文）",
            created_at="2024-01-01"
        ))

        # 中文Bug修复提示词
        self._register_prompt(PromptVersion(
            version="1.0.0",
            scenario=PromptScenario.BUG_FIX,
            language=PromptLanguage.ZH_CN,
            template="""你是一个专业的调试专家。请分析以下代码，找出问题并提供修复方案。

## 代码上下文
{context}

## 问题描述
{question}

## 分析要求
1. 问题的根本原因是什么？
2. 提供具体的修复代码
3. 解释修复的原理
4. 可能的副作用或注意事项
5. 请用中文回答

请开始分析：""",
            input_variables=["context", "question"],
            description="Bug修复提示词（中文）",
            created_at="2024-01-01"
        ))

        # 中文架构设计提示词
        self._register_prompt(PromptVersion(
            version="1.0.0",
            scenario=PromptScenario.ARCHITECTURE_DESIGN,
            language=PromptLanguage.ZH_CN,
            template="""你是一个软件架构师。请基于代码库分析架构设计并回答相关问题。

## 代码上下文
{context}

## 架构问题
{question}

## 分析要求
1. 当前架构的概述
2. 关键设计模式的使用
3. 模块间的依赖关系
4. 改进建议或优化方案
5. 请用中文回答

请开始分析：""",
            input_variables=["context", "question"],
            description="架构设计提示词（中文）",
            created_at="2024-01-01"
        ))

        # 中文Agent系统提示词
        self._register_prompt(PromptVersion(
            version="1.0.0",
            scenario=PromptScenario.AGENT_SYSTEM,
            language=PromptLanguage.ZH_CN,
            template="""你是 CodeMind Agent，一个专业的代码仓库智能助手。你的任务是基于提供的上下文信息和可用工具，帮助用户分析和理解代码仓库。

## 可用工具
你可以使用以下工具来帮助完成任务：
1. ReadFile - 读取指定文件内容，支持行号范围
2. SearchCode - 在代码库中搜索关键词或正则表达式
3. RunCommand - 执行只读 shell 命令（如 ls, cat, grep, git 等）

## 回答要求
1. 如果答案在上下文中，请直接引用相关代码片段并给出详细解释
2. 如果需要更多信息，可以使用工具来获取
3. 回答要条理清晰，分点说明
4. 对于代码相关问题，给出具体的代码示例或修改建议
5. 请用中文回答""",
            input_variables=[],  # 系统提示词，无输入变量
            description="Agent系统提示词（中文）",
            created_at="2024-01-01"
        ))

        # 中文总结提示词
        self._register_prompt(PromptVersion(
            version="1.0.0",
            scenario=PromptScenario.SUMMARIZATION,
            language=PromptLanguage.ZH_CN,
            template="""你是专注于"基于参考资料总结"的AI助手，需结合用户提问和向量检索到的参考资料，生成简洁准确的概括回答。

### 输入信息
1. 用户提问：{input}
2. 参考资料(在下一个###之前内容均为参考资料)：{context}

### 严格遵守以下约束（违反将导致回答无效）
1. 内容合规：禁止包含违法、侵权、攻击性信息；
2. 事实准确：回答必须完全基于参考资料中的信息，不编造、不添加未提及的内容，不做主观推断；
3. 语言要求：仅用中文回答，语气客观、简洁，不冗余；
4. 聚焦提问：严格围绕用户原始提问总结，不扩充问题范围、不额外追问、不构造新query；
5. 格式要求：仅输出概括内容本身，以纯文本字符串形式呈现，不封装为字典、列表、JSON等任何结构，不附带额外说明。""",
            input_variables=["input", "context"],
            description="总结提示词（中文）",
            created_at="2024-01-01"
        ))

        logger.info("默认提示词模板初始化完成")

    def _register_prompt(self, prompt_version: PromptVersion) -> None:
        """
        注册提示词模板

        Args:
            prompt_version: 提示词版本信息
        """
        key = self._get_prompt_key(
            prompt_version.scenario,
            prompt_version.language,
            prompt_version.version
        )
        self._prompts[key] = prompt_version
        logger.debug(f"注册提示词: {key}")

    def _get_prompt_key(
        self,
        scenario: PromptScenario,
        language: PromptLanguage,
        version: Optional[str] = None
    ) -> str:
        """
        生成提示词存储键

        Args:
            scenario: 场景
            language: 语言
            version: 版本（可选，默认使用当前版本）

        Returns:
            提示词键
        """
        if version is None:
            version = self._current_version
        return f"{scenario.value}:{language.value}:{version}"

    def get_prompt(
        self,
        scenario: PromptScenario = PromptScenario.GENERAL_QA,
        language: PromptLanguage = PromptLanguage.ZH_CN,
        version: Optional[str] = None
    ) -> LangChainPromptTemplate:
        """
        获取提示词模板

        Args:
            scenario: 场景
            language: 语言
            version: 版本（可选）

        Returns:
            LangChain 提示词模板
        """
        key = self._get_prompt_key(scenario, language, version)

        if key not in self._prompts:
            logger.warning(f"提示词不存在: {key}，尝试使用通用问答提示词")
            # 回退到通用问答
            fallback_key = self._get_prompt_key(
                PromptScenario.GENERAL_QA,
                language,
                version
            )
            if fallback_key not in self._prompts:
                # 回退到中文通用问答
                fallback_key = self._get_prompt_key(
                    PromptScenario.GENERAL_QA,
                    PromptLanguage.ZH_CN,
                    "1.0.0"
                )
            # 使用回退的key
            key = fallback_key

        prompt_version = self._prompts[key]
        logger.debug(f"使用提示词: {key}")

        return LangChainPromptTemplate(
            input_variables=prompt_version.input_variables,
            template=prompt_version.template
        )

    def add_custom_prompt(
        self,
        scenario: str,
        language: str,
        version: str,
        template: str,
        input_variables: list,
        description: str
    ) -> None:
        """
        添加自定义提示词

        Args:
            scenario: 场景名称
            language: 语言代码
            version: 版本号
            template: 提示词模板
            input_variables: 输入变量列表
            description: 描述
        """
        prompt_version = PromptVersion(
            version=version,
            scenario=PromptScenario(scenario),
            language=PromptLanguage(language),
            template=template,
            input_variables=input_variables,
            description=description,
            created_at="custom"
        )
        self._register_prompt(prompt_version)
        logger.info(f"添加自定义提示词: {scenario}:{language}:{version}")

    def set_current_version(self, version: str) -> None:
        """
        设置当前使用的提示词版本

        Args:
            version: 版本号
        """
        self._current_version = version
        logger.info(f"当前提示词版本已设置为: {version}")

    def list_available_prompts(self) -> Dict[str, PromptVersion]:
        """
        列出所有可用的提示词

        Returns:
            提示词字典
        """
        return self._prompts.copy()
