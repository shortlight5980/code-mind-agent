# 04. Agent 核心逻辑

Agent 核心模块是整个系统的大脑，负责：
1. 创建和配置 Agent
2. 运行 Agent 并处理工具调用循环
3. 集成总结模块
4. 支持流式输出和非流式输出

在本文档中，我们还会详细讲解 **LangChain 1.0 API 的迁移**！

---

## 完整代码解析

### 头部导入

```python
"""
Agent 核心模块

负责创建和运行 CodeMind Agent，集成工具调用和总结模块。
支持流式输出和非流式输出两种模式。
"""
from typing import List, Any, Dict, Generator, Optional
from langchain.agents import create_agent  # 只需这一个导入！
from langchain_core.tools import Tool
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from utils.config import Config
from utils.summarizer import build_context, summarize_context
from agent.tools import ReadFile, SearchCode, RunCommand

logger = get_logger("agent.core")
```

**关键变化！**

旧版（LangChain < 1.0）：
```python
from langchain.agents import AgentExecutor, create_react_agent  # 两个导入
```

新版（LangChain 1.0+）：
```python
from langchain.agents import create_agent  # 只需一个！
```

---

### 一、获取工具列表

```python
def get_tools() -> List[Tool]:
    """
    获取所有可用的 Agent 工具列表。

    Returns:
        工具对象列表
    """
    return [ReadFile, SearchCode, RunCommand]
```

很简单，就是把三个工具组装成列表。

---

### 二、加载系统提示词

```python
def load_system_prompts() -> str:
    """
    加载 Agent 系统提示词。

    Returns:
        系统提示词字符串
    """
    return """你是 CodeMind Agent，一个专业的代码仓库智能助手。你的任务是基于提供的上下文信息和可用工具，帮助用户分析和理解代码仓库。

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
5. 请用中文回答"""
```

---

### 三、CodeMindAgent 类

这是新增的核心类，封装了所有 Agent 功能！

```python
class CodeMindAgent:
    """
    CodeMind Agent 封装类

    提供统一的接口来执行 Agent 任务，支持流式输出和非流式输出。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        """
        初始化 CodeMind Agent。

        Args:
            model: 模型名称，默认从配置读取
            temperature: 温度参数，默认从配置读取
        """
        if model is None:
            model = Config.get("agent.model", "qwen-max")
        if temperature is None:
            temperature = Config.get("agent.temperature", 0.1)

        logger.info(f"Initializing CodeMindAgent: model={model}, temperature={temperature}")

        # 初始化 LLM
        self.chat_model = ChatTongyi(
            model=model,
            temperature=temperature,
        )

        # 获取工具列表
        self.tools = get_tools()

        # 加载系统提示词
        self.system_prompt = load_system_prompts()

        # 创建 Agent（LangChain 1.0 新 API）
        self.agent = create_agent(
            model=self.chat_model,
            system_prompt=self.system_prompt,
            tools=self.tools
        )

        logger.info("CodeMindAgent initialized successfully")
```

#### 使用示例

```python
# 创建 Agent 实例
agent = CodeMindAgent()

# 非流式执行
result = agent.execute("介绍一下项目结构")

# 流式执行
for chunk in agent.execute_stream("介绍一下项目结构"):
    print(chunk, end="")
```

---

### 四、非流式执行：execute()

```python
    def execute(
        self,
        question: str,
        raw_docs: Optional[List[Any]] = None,
        summarizer_llm: Optional[ChatTongyi] = None
    ) -> Dict[str, Any]:
        """
        非流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）
            summarizer_llm: 总结模型实例（可选，提供 raw_docs 时必须提供）

        Returns:
            包含回答和来源的字典
        """
        logger.info(f"Executing agent (non-streaming) for question: {question}")

        summarized_context = ""
        if raw_docs is not None and summarizer_llm is not None:
            # 步骤 1：从检索文档构建原始上下文
            raw_context = build_context(raw_docs)
            logger.debug("原始上下文已构建")

            # 步骤 2：使用总结模块进行总结
            logger.info("Summarizing retrieved context...")
            summarized_context = summarize_context(question, raw_context, summarizer_llm)
            logger.debug("上下文总结完成")

        # 步骤 3：构建用户消息内容
        user_message_content = self._build_user_message(question, summarized_context)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息:")
        logger.debug(user_message_content)
        logger.debug("=" * 80)

        # 步骤 4：运行 Agent
        logger.info("Invoking agent...")
        try:
            response = self.agent.invoke({
                "messages": [
                    {"role": "user", "content": user_message_content}
                ]
            })

            logger.info("Agent execution completed")

            # Debug: 输出 Agent 的完整返回结果
            logger.debug("=" * 80)
            logger.debug("🤖 Agent 完整返回结果:")
            for i, msg in enumerate(response["messages"]):
                role = msg.get("role", "unknown") if isinstance(msg, dict) else getattr(msg, "role", "unknown")
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                logger.debug(f"  [{i+1}] 角色: {role}")
                logger.debug(f"  内容:\n{content}")
                logger.debug("-" * 60)
            logger.debug("=" * 80)

            # 获取最终回答：messages 列表的最后一条
            answer = response["messages"][-1].content

            # Info: 输出最终答案
            logger.info("=" * 80)
            logger.info("✅ Agent 最终答案:")
            logger.info(answer)
            logger.info("=" * 80)

            result = {
                "answer": answer,
                "summarized_context": summarized_context
            }

            if raw_docs is not None:
                result["sources"] = [
                    {
                        "source": doc.metadata.get("source", "unknown"),
                        "content": doc.page_content
                    }
                    for doc in raw_docs
                ]

            return result
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            # 降级方案：如果 Agent 失败，使用总结后的上下文直接回答
            logger.info("Falling back to summarized context...")

            result = {
                "answer": f"Agent 执行遇到问题，以下是基于检索结果的总结：\n\n{summarized_context}",
                "summarized_context": summarized_context,
                "error": str(e)
            }

            if raw_docs is not None:
                result["sources"] = [
                    {
                        "source": doc.metadata.get("source", "unknown"),
                        "content": doc.page_content
                    }
                    for doc in raw_docs
                ]

            return result
```

---

### 五、流式执行：execute_stream()

这是新增的核心功能！

```python
    def execute_stream(
        self,
        question: str,
        raw_docs: Optional[List[Any]] = None,
        summarizer_llm: Optional[ChatTongyi] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Generator[str, None, None]:
        """
        流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）
            summarizer_llm: 总结模型实例（可选，提供 raw_docs 时必须提供）
            context: 附加上下文参数（可选）

        Yields:
            流式输出的内容片段
        """
        logger.info(f"Executing agent (streaming) for question: {question}")

        summarized_context = ""
        if raw_docs is not None and summarizer_llm is not None:
            # 步骤 1：从检索文档构建原始上下文
            raw_context = build_context(raw_docs)
            logger.debug("原始上下文已构建")

            # 步骤 2：使用总结模块进行总结
            logger.info("Summarizing retrieved context...")
            summarized_context = summarize_context(question, raw_context, summarizer_llm)
            logger.debug("上下文总结完成")

        # 步骤 3：构建用户消息内容
        user_message_content = self._build_user_message(question, summarized_context)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息 (streaming):")
        logger.debug(user_message_content)
        logger.debug("=" * 80)

        # 步骤 4：流式运行 Agent
        logger.info("Starting agent stream...")
        try:
            input_dict = {
                "messages": [
                    {"role": "user", "content": user_message_content}
                ]
            }

            stream_context = context if context is not None else {}

            for chunk in self.agent.stream(input_dict, stream_mode="values", context=stream_context):
                last_message = chunk["messages"][-1]
                if last_message.content:
                    content = last_message.content.strip()
                    if content:
                        logger.debug(f"Stream chunk: {content[:50]}...")
                        yield content + "\n"

            logger.info("Agent stream completed")

        except Exception as e:
            logger.error(f"Agent stream execution failed: {e}")
            # 降级方案：如果流式执行失败，返回错误信息
            error_msg = f"Agent 流式执行遇到问题：{str(e)}"
            if summarized_context:
                error_msg += f"\n\n以下是基于检索结果的总结：\n\n{summarized_context}"
            yield error_msg + "\n"
```

---

### 六、辅助方法：_build_user_message()

```python
    def _build_user_message(self, question: str, summarized_context: str) -> str:
        """
        构建用户消息内容，将上下文和问题组合。

        Args:
            question: 用户问题
            summarized_context: 总结后的上下文

        Returns:
            组合后的用户消息
        """
        return f"""## 上下文信息
{summarized_context}

## 用户问题
{question}"""
```

---

### 七、向后兼容的函数

为了保持向后兼容，我们保留了原有的函数：

```python
def create_codemind_agent(
    model: str = None,
    temperature: float = None
):
    """
    创建并配置 CodeMind Agent（向后兼容）。

    Args:
        model: 模型名称，默认从配置读取
        temperature: 温度参数，默认从配置读取

    Returns:
        配置好的 Agent 实例（可直接调用 invoke/stream）
    """
    agent_instance = CodeMindAgent(model=model, temperature=temperature)
    return agent_instance.agent


def run_agent_with_summary(
    question: str,
    agent,
    raw_docs: List[Any],
    summarizer_llm: ChatTongyi
) -> Dict[str, Any]:
    """
    运行 Agent，先对检索结果进行总结，再执行 Agent（向后兼容）。

    注意：此函数保留向后兼容性，新代码建议使用 CodeMindAgent 类。

    Args:
        question: 用户问题
        agent: Agent 实例（来自 create_codemind_agent）
        raw_docs: 向量检索返回的原始文档列表
        summarizer_llm: 总结模型实例

    Returns:
        包含回答和来源的字典
    """
    # 创建 CodeMindAgent 实例并复用传入的 agent 对象
    temp_agent = CodeMindAgent()
    # 替换内部的 agent 为传入的实例（保持向后兼容）
    temp_agent.agent = agent

    return temp_agent.execute(
        question=question,
        raw_docs=raw_docs,
        summarizer_llm=summarizer_llm
    )
```

---

## 新旧 API 对比总结

| 项目 | 旧版（< 1.0） | 新版（1.0+） |
|------|--------------|-------------|
| **导入** | `AgentExecutor, create_react_agent` | `create_agent` |
| **创建** | 先 `create_react_agent`，再 `AgentExecutor` | 只需 `create_agent` |
| **提示词** | `prompt=CODEMIND_AGENT_PROMPT` (PromptTemplate) | `system_prompt="..."` (纯文本) |
| **返回值** | `AgentExecutor` 实例 | 可直接 invoke 的 agent |
| **调用** | `agent_executor.invoke({"question": "..."})` | `agent.invoke({"messages": [...]})` |
| **封装** | 独立函数 | `CodeMindAgent` 类 |
| **流式输出** | ❌ 不支持 | ✅ `execute_stream()` |

---

## 降级方案设计

注意这段代码：

```python
except Exception as e:
    logger.error(f"Agent execution failed: {e}")
    # 降级方案：如果 Agent 失败，使用总结后的上下文直接回答
    logger.info("Falling back to summarized context...")
    return {
        "answer": f"Agent 执行遇到问题，以下是基于检索结果的总结：\n\n{summarized_context}",
        # ...
    }
```

**为什么需要降级方案？**

Agent 可能会失败的情况：
- LLM 解析工具调用失败
- 工具执行出错
- 网络问题
- LangChain API 变更

有了降级方案，即使 Agent 挂了，系统仍然能返回一个可用的回答！

---

## 完整的迁移指南

### 1. 更新依赖

确保 `requirements.txt` 中有：
```txt
langchain>=1.0.0
langchain-community>=0.3.0
langchain-core>=1.0.0
```

### 2. 更新导入

```python
# ❌ 旧版
from langchain.agents import AgentExecutor, create_react_agent

# ✅ 新版
from langchain.agents import create_agent
```

### 3. 更新提示词

```python
# ❌ 旧版：用 PromptTemplate
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=CODEMIND_AGENT_PROMPT,  # PromptTemplate 对象
)

# ✅ 新版：用纯文本
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="你是一个有用的助手",  # 纯文本字符串
)
```

### 4. 更新调用方式

```python
# ❌ 旧版
agent_executor = AgentExecutor(agent=agent, tools=tools, ...)
result = agent_executor.invoke({"question": "..."})
answer = result["output"]

# ✅ 新版（使用 CodeMindAgent 类）
agent = CodeMindAgent()

# 非流式
result = agent.execute("...")
answer = result["answer"]

# 流式
for chunk in agent.execute_stream("..."):
    print(chunk, end="")
```

---

## 关键设计决策总结

| 决策 | 说明 |
|------|------|
| **先总结再 Agent** | 减少 Token 消耗，提高效率 |
| **降级方案** | Agent 失败时仍能返回回答 |
| **详细日志** | Debug 级别记录完整交互，Info 级别记录关键步骤 |
| **纯文本 system_prompt** | 适配 LangChain 1.0 新 API |
| **CodeMindAgent 类** | 统一封装，支持流式和非流式 |
| **向后兼容** | 保留原有函数，平滑迁移 |

---

## 下一步

现在你理解了 Agent 核心逻辑，接下来阅读 [05-完整集成与测试.md](./05-完整集成与测试.md)，学习如何将 Agent 集成到 app.py 中！
