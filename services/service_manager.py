"""
服务单例管理模块
负责所有服务对象（vectordb、llm、summarizer_llm、agent）的创建、配置和生命周期管理
"""
from typing import Dict, Any, Optional
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from utils.config import Config
from utils.summarizer import create_summarizer
from agent.agent import CodeMindAgent

logger = get_logger("service_manager")


class ServiceManager:
    """服务单例管理器"""

    # 单例实例
    _instance: Optional['ServiceManager'] = None

    # 服务存储
    _services: Dict[str, Any] = {}

    # 初始化标志
    _initialized: bool = False

    def __new__(cls) -> 'ServiceManager':
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'ServiceManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self) -> None:
        """
        初始化所有服务
        包括：向量数据库、LLM、摘要器、Agent
        """
        if self._initialized:
            logger.warning("服务已经初始化过，跳过重复初始化")
            return

        logger.info("开始初始化服务...")
        Config.load()

        # 初始化向量数据库
        self._init_vectordb()

        # 初始化主LLM
        self._init_llm()

        # 初始化摘要LLM
        self._init_summarizer_llm()

        # 初始化Agent
        self._init_agent()

        self._initialized = True
        logger.info("所有服务初始化完成")

    def _init_vectordb(self) -> None:
        """初始化向量数据库"""
        persist_dir = Config.get("chroma.persist_dir", "./chroma_db")
        embedding_model = Config.get("embeddings.model", "text-embedding-v3")
        retrieval_k = Config.get("chroma.retrieval_k", 7)

        logger.info(f"加载向量数据库: {persist_dir}")

        # 初始化embeddings
        embeddings = DashScopeEmbeddings(
            model=embedding_model,
        )

        # 加载向量数据库
        vectordb = Chroma(
            persist_directory=persist_dir,
            embedding_function=embeddings
        )

        self._services["vectordb"] = vectordb
        self._services["retrieval_k"] = retrieval_k
        logger.info("向量数据库初始化完成")

    def _init_llm(self) -> None:
        """初始化主LLM"""
        llm_model = Config.get("llm.model", "qwen-max")
        llm_temperature = Config.get("llm.temperature", 0.1)

        logger.info(f"初始化主LLM: {llm_model}")

        llm = ChatTongyi(
            model=llm_model,
            temperature=llm_temperature,
        )

        self._services["llm"] = llm
        logger.info("主LLM初始化完成")

    def _init_summarizer_llm(self) -> None:
        """初始化摘要LLM"""
        summarizer_model = Config.get("summarizer.model", "qwen-max")
        summarizer_temperature = Config.get("summarizer.temperature", 0.1)

        logger.info(f"初始化摘要LLM: {summarizer_model}")

        summarizer_llm = create_summarizer(
            model=summarizer_model,
            temperature=summarizer_temperature
        )

        self._services["summarizer_llm"] = summarizer_llm
        logger.info("摘要LLM初始化完成")

    def _init_agent(self) -> None:
        """初始化CodeMind Agent"""
        agent_enabled = Config.get("agent.enabled", True)

        if agent_enabled:
            logger.info("初始化CodeMind Agent...")
            try:
                agent = CodeMindAgent()
                self._services["agent"] = agent
                self._services["agent_enabled"] = True
                logger.info("CodeMind Agent初始化成功")
            except Exception as e:
                logger.error(f"Agent初始化失败: {e}")
                self._services["agent_enabled"] = False
        else:
            self._services["agent_enabled"] = False
            logger.info("Agent在配置中已禁用")

    def get(self, service_name: str, default: Any = None) -> Any:
        """
        获取服务

        Args:
            service_name: 服务名称
            default: 默认值

        Returns:
            服务实例
        """
        return self._services.get(service_name, default)

    def __getitem__(self, key: str) -> Any:
        """字典风格的服务访问"""
        return self._services[key]

    def __contains__(self, key: str) -> bool:
        """检查服务是否存在"""
        return key in self._services

    def cleanup(self) -> None:
        """清理所有服务"""
        logger.info("清理服务...")
        self._services.clear()
        self._initialized = False
        logger.info("服务清理完成")

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    @property
    def vectordb(self) -> Optional[Chroma]:
        """向量数据库服务"""
        return self._services.get("vectordb")

    @property
    def llm(self) -> Optional[ChatTongyi]:
        """主LLM服务"""
        return self._services.get("llm")

    @property
    def summarizer_llm(self) -> Optional[ChatTongyi]:
        """摘要LLM服务"""
        return self._services.get("summarizer_llm")

    @property
    def agent(self) -> Optional[CodeMindAgent]:
        """Agent服务"""
        return self._services.get("agent")

    @property
    def agent_enabled(self) -> bool:
        """Agent是否启用"""
        return self._services.get("agent_enabled", False)

    @property
    def retrieval_k(self) -> int:
        """检索数量配置"""
        return self._services.get("retrieval_k", 7)
