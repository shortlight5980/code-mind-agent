"""
BM25 关键词检索索引模块

本模块实现了 BM25 检索算法，用于关键词匹配检索。
支持两种后端：
1. rank-bm25 库（优先，性能更好）
2. SimpleBM25Okapi（降级，纯 Python 实现）

主要特性：
- 支持中文、英文、数字、下划线的 tokenize
- 支持驼峰命名、下划线命名的拆分
- 支持按 metadata 的 type 字段过滤（code/doc）
- 支持持久化保存/加载
"""
import math
import os
import pickle
import re
from collections import Counter
from typing import Any

# 尝试导入 rank-bm25 库，如果不可用则使用纯 Python 实现
try:
    from rank_bm25 import BM25Okapi as RankBM25Okapi
except ImportError:
    RankBM25Okapi = None


# Tokenize 正则：匹配标识符（字母数字下划线）或中文字符
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """
    对文本进行分词，支持代码标识符和中文混合场景。

    分词策略：
    1. 按正则提取 token（标识符或中文字符）
    2. 对每个 token 做小写化
    3. 对下划线命名进行拆分（如 user_id → user, id）
    4. 对驼峰命名进行拆分（如 UserService → User, Service）

    Args:
        text: 待分词的文本

    Returns:
        分词后的 token 列表
    """
    tokens = []
    for token in TOKEN_PATTERN.findall(text or ""):
        lowered = token.lower()
        tokens.append(lowered)

        # 拆分下划线命名（如 user_id → user, id）
        if "_" in token:
            tokens.extend(part.lower() for part in token.split("_") if part)

        # 拆分驼峰命名（如 UserService → User, Service）
        tokens.extend(
            part.lower()
            for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|[0-9]+", token)
            if part.lower() != lowered
        )
    return tokens


class SimpleBM25Okapi:
    """
    纯 Python 实现的 BM25 Okapi 算法，作为 rank-bm25 库的降级方案。

    BM25 是一种基于概率的检索模型，核心公式：
    score(D, Q) = sum( IDF(q) * (f(q,D) * (k1 + 1)) / (f(q,D) + k1 * (1 - b + b * |D| / avgdl)) )

    其中：
    - IDF(q): 查询词 q 的逆文档频率
    - f(q,D): 查询词 q 在文档 D 中的词频
    - |D|: 文档 D 的长度
    - avgdl: 平均文档长度
    - k1, b: 可调参数（通常 k1=1.5, b=0.75）
    """

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        """
        初始化 BM25 索引。

        Args:
            corpus: 语料库，每个文档是已经分词的 token 列表
            k1: BM25 参数 k1（控制词频饱和度，默认 1.5）
            b: BM25 参数 b（控制文档长度归一化，默认 0.75）
        """
        self.corpus = corpus
        self.k1 = k1
        self.b = b

        # 预计算每个文档的词频
        self.doc_freqs = [Counter(document) for document in corpus]
        # 预计算每个文档的长度
        self.doc_len = [len(document) for document in corpus]
        # 预计算平均文档长度
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        # 预计算每个词的 IDF
        self.idf = self._calculate_idf()

    def _calculate_idf(self) -> dict[str, float]:
        """
        计算每个 token 的逆文档频率（IDF）。

        IDF 公式：log(1 + (N - n + 0.5) / (n + 0.5))
        其中 N 是文档总数，n 是包含该 token 的文档数。

        Returns:
            token -> IDF 值的字典
        """
        document_count = len(self.corpus)
        frequencies: Counter[str] = Counter()

        # 统计每个 token 出现在多少文档中
        for document in self.corpus:
            frequencies.update(set(document))

        # 计算 IDF
        return {
            token: math.log(1 + (document_count - freq + 0.5) / (freq + 0.5))
            for token, freq in frequencies.items()
        }

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        """
        计算查询与每个文档的 BM25 相似度分数。

        Args:
            query_tokens: 已经分词的查询 token 列表

        Returns:
            每个文档的分数列表，顺序与 corpus 一致
        """
        scores = []
        for index, freqs in enumerate(self.doc_freqs):
            score = 0.0
            doc_len = self.doc_len[index]

            # 对查询中的每个 token 计算贡献
            for token in query_tokens:
                token_freq = freqs.get(token, 0)
                if token_freq == 0:
                    continue

                # BM25 核心公式
                denominator = token_freq + self.k1 * (
                    1 - self.b + self.b * doc_len / (self.avgdl or 1)
                )
                score += self.idf.get(token, 0.0) * (
                    token_freq * (self.k1 + 1) / denominator
                )
            scores.append(score)
        return scores


class BM25Index:
    """
    BM25 检索索引的高级封装，提供易用的 API。

    主要功能：
    - fit: 从文档列表构建索引
    - search: 按关键词检索，支持过滤
    - save/load: 持久化支持
    """

    def __init__(self):
        self.bm25: Any = None  # BM25 实例（RankBM25Okapi 或 SimpleBM25Okapi）
        self.documents: list[str] = []  # 原始文档内容列表
        self.metadatas: list[dict[str, Any]] = []  # 文档 metadata 列表
        self._tokenized_documents: list[list[str]] = []  # 缓存的分词结果

    def fit(self, documents: list[str], metadatas: list[dict[str, Any]]):
        """
        构建 BM25 索引。

        Args:
            documents: 文档内容列表
            metadatas: 文档 metadata 列表，长度必须与 documents 一致

        Returns:
            self（支持链式调用）
        """
        if len(documents) != len(metadatas):
            raise ValueError("documents and metadatas must have the same length")

        self.documents = list(documents)
        self.metadatas = [dict(metadata) for metadata in metadatas]
        self._tokenized_documents = [tokenize(document) for document in self.documents]

        # 优先使用 rank-bm25 库，否则用纯 Python 实现
        bm25_class = RankBM25Okapi or SimpleBM25Okapi
        self.bm25 = bm25_class(self._tokenized_documents)
        return self

    def delete_by_sources(self, sources: list[str] | set[str]) -> int:
        """
        按 metadata.source 删除文档并重建索引。

        Args:
            sources: 要删除的 source 路径集合

        Returns:
            实际删除的 chunk 数量
        """
        normalized_sources = {source.replace("\\", "/") for source in sources}
        kept_documents = []
        kept_metadatas = []
        removed_count = 0

        for document, metadata in zip(self.documents, self.metadatas):
            source = str(metadata.get("source", "")).replace("\\", "/")
            if source in normalized_sources:
                removed_count += 1
                continue
            kept_documents.append(document)
            kept_metadatas.append(metadata)

        self.fit(kept_documents, kept_metadatas)
        return removed_count

    def search(
        self,
        query: str,
        k: int = 10,
        filter_type: str | None = None,
    ) -> list[tuple[str, dict[str, Any], float]]:
        """
        检索最相关的文档。

        Args:
            query: 查询字符串
            k: 返回的最大结果数
            filter_type: 如果提供，只返回 metadata["type"] == filter_type 的文档

        Returns:
            结果列表，每个元素是 (document_content, metadata, score) 元组，按分数降序排列
        """
        if self.bm25 is None:
            return []

        # 对查询进行分词
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # 计算所有文档的分数
        scores = self.bm25.get_scores(query_tokens)

        # 过滤和排序
        candidates = []
        for index, score in enumerate(scores):
            metadata = self.metadatas[index]

            # 按 type 过滤（如果指定）
            if filter_type and metadata.get("type") != filter_type:
                continue

            # 忽略分数 <= 0 的结果
            if score <= 0:
                score = self._lexical_overlap_score(query_tokens, index)

            if score <= 0:
                continue

            candidates.append((self.documents[index], metadata, float(score)))

        # 按分数降序排列，取 top-k
        candidates.sort(key=lambda item: item[2], reverse=True)
        return candidates[:k]

    def _lexical_overlap_score(self, query_tokens: list[str], index: int) -> float:
        """Return a fallback score for exact token matches when BM25 IDF is zero."""
        if index >= len(self._tokenized_documents):
            return 0.0

        frequencies = Counter(self._tokenized_documents[index])
        return float(sum(frequencies.get(token, 0) for token in query_tokens))

    def save(self, path: str):
        """
        保存索引到文件。

        设计说明：只保存原始文档和 metadata，不保存 BM25 的中间计算结果。
        这样做的好处：
        1. 节省磁盘空间
        2. 向前兼容（如果 BM25 实现变更，旧数据仍可加载）
        3. 加载时可以自动应用最新的 tokenize 逻辑

        Args:
            path: 保存路径
        """
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(path, "wb") as file:
            pickle.dump(
                {
                    "documents": self.documents,
                    "metadatas": self.metadatas,
                },
                file,
            )

    @classmethod
    def load(cls, path: str) -> "BM25Index":
        """
        从文件加载索引。

        加载后会自动重新 fit，重建 BM25 的内部结构。

        Args:
            path: 加载路径

        Returns:
            重建的 BM25Index 实例
        """
        with open(path, "rb") as file:
            payload = pickle.load(file)

        index = cls()
        index.fit(payload["documents"], payload["metadatas"])
        return index
