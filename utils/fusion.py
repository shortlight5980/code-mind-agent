"""
结果融合模块

本模块实现了 Reciprocal Rank Fusion (RRF) 算法，用于融合多个检索器的结果。

RRF 是一种无监督的结果融合方法，核心思想：
- 对每个检索结果列表，按排名分配分数：1 / (k + rank)
- 同一文档在不同列表中的分数相加
- 按最终分数重新排序

主要特性：
- 支持多种结果格式（LangChain Document、dict、tuple）
- 支持按 (source, content_hash) 去重
- 可选标识符匹配增强功能
"""
import hashlib
import re
from typing import Any


# 标识符正则：匹配变量名、函数名等标识符
IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def result_key(result: Any) -> tuple[str, str]:
    """
    生成结果的唯一键，用于去重。

    键的组成：(source_path, content_sha1)
    这样可以识别：
    - 同一文件的同一内容（完全相同）
    - 同一文件的不同版本（content_sha1 不同）
    - 不同文件的相同内容（source 不同）

    Args:
        result: 检索结果对象

    Returns:
        (source, content_sha1) 元组
    """
    content = _content(result)
    metadata = _metadata(result)
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()
    return str(metadata.get("source", "")), digest


def extract_identifiers(query: str) -> set[str]:
    """
    从查询中提取标识符，并拆分驼峰和下划线命名。

    例如：
    "findUserById" → {"finduserbyid", "find", "user", "by", "id"}
    "user_service" → {"user_service", "user", "service"}

    Args:
        query: 查询字符串

    Returns:
        标识符集合（小写）
    """
    identifiers = set()
    for token in IDENTIFIER_PATTERN.findall(query or ""):
        identifiers.add(token.lower())

        # 拆分驼峰和下划线命名，增加匹配机会
        for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|[0-9]+", token):
            identifiers.add(part.lower())
    return identifiers


def rrf_fuse(
    ranked_lists: list[list[Any]],
    rrf_k: int = 60,
    identifier_query: str | None = None,
    identifier_boost: float = 0.0,
) -> list[dict[str, Any]]:
    """
    使用 Reciprocal Rank Fusion (RRF) 算法融合多个检索结果列表。

    融合流程：
    1. 对每个结果列表，按排名计算 RRF 分数：1 / (k + rank)
    2. 同一文档的分数累加
    3. （可选）如果文档包含查询中的标识符，加分
    4. 按最终分数重新排序

    设计说明：
    - rrf_k 通常设为 60，这是一个经验值
    - 去重使用 (source, content_hash) 作为键
    - 标识符增强可以提升精确匹配的权重

    Args:
        ranked_lists: 检索结果列表的列表，每个子列表是一个检索器的结果
        rrf_k: RRF 参数 k（默认 60）
        identifier_query: 用于标识符增强的查询字符串（可选）
        identifier_boost: 标识符匹配的加分权重（默认 0.0，不启用）

    Returns:
        融合后的结果列表，每个元素是 {"content": ..., "metadata": ..., "score": ..., "raw": ...}
    """
    # 用于去重和累加分数的字典：key -> item
    fused: dict[tuple[str, str], dict[str, Any]] = {}

    # 提取查询中的标识符（如果需要增强）
    identifiers = extract_identifiers(identifier_query or "")

    # 遍历所有检索结果列表
    for ranked_list in ranked_lists:
        for rank, raw_result in enumerate(ranked_list, start=1):
            key = result_key(raw_result)
            # 计算 RRF 分数：1 / (k + rank)
            score = 1.0 / (rrf_k + rank)

            existing = fused.get(key)
            if existing is None:
                # 第一次见到这个结果，创建新条目
                existing = {
                    "content": _content(raw_result),
                    "metadata": dict(_metadata(raw_result)),
                    "score": 0.0,
                    "raw": raw_result,
                }
                fused[key] = existing

            # 累加分数
            existing["score"] += score

    # 标识符增强：如果文档内容包含查询中的标识符，加分
    if identifiers and identifier_boost:
        for item in fused.values():
            content_tokens = extract_identifiers(item["content"])
            if identifiers & content_tokens:  # 有交集
                item["score"] += identifier_boost

    # 按最终分数降序排列
    return sorted(fused.values(), key=lambda item: item["score"], reverse=True)


def _content(result: Any) -> str:
    """
    从各种可能的结果格式中提取内容字符串。

    支持的格式：
    - dict: 使用 "content" 键
    - tuple: 使用第一个元素
    - LangChain Document: 使用 page_content 属性

    Args:
        result: 检索结果对象

    Returns:
        内容字符串
    """
    if isinstance(result, dict):
        return str(result.get("content", ""))
    if isinstance(result, tuple):
        return str(result[0])
    return str(getattr(result, "page_content", ""))


def _metadata(result: Any) -> dict[str, Any]:
    """
    从各种可能的结果格式中提取 metadata 字典。

    支持的格式：
    - dict: 使用 "metadata" 键
    - tuple: 使用第二个元素
    - LangChain Document: 使用 metadata 属性

    Args:
        result: 检索结果对象

    Returns:
        metadata 字典
    """
    if isinstance(result, dict):
        return dict(result.get("metadata", {}))
    if isinstance(result, tuple) and len(result) > 1:
        return dict(result[1])
    return dict(getattr(result, "metadata", {}) or {})
