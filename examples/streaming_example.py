"""
CodeMind Agent 流式输出示例

演示如何使用 CodeMindAgent 类的流式输出功能。
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from utils.logger import get_logger
from agent.agent import CodeMindAgent

logger = get_logger("examples.streaming")


def main():
    """主函数：演示流式输出"""
    print("=" * 80)
    print("CodeMind Agent 流式输出示例")
    print("=" * 80)

    # 加载配置
    Config.load()

    # 初始化 Agent
    print("\n[1/3] 初始化 CodeMindAgent...")
    agent = CodeMindAgent()
    print("✓ Agent 初始化完成")

    # 示例问题
    question = "请介绍一下这个项目的结构和主要功能"
    print(f"\n[2/3] 问题: {question}")

    # 流式执行
    print("\n[3/3] 流式输出回答:")
    print("-" * 80)

    try:
        # 调用流式输出方法
        for chunk in agent.execute_stream(question):
            print(chunk, end="", flush=True)
    except KeyboardInterrupt:
        print("\n\n用户中断了执行")
    except Exception as e:
        print(f"\n\n执行出错: {e}")
        logger.error(f"Stream execution failed: {e}", exc_info=True)

    print("\n" + "-" * 80)
    print("✓ 流式输出完成")


def non_streaming_example():
    """非流式输出示例"""
    print("\n" + "=" * 80)
    print("非流式输出示例")
    print("=" * 80)

    Config.load()
    agent = CodeMindAgent()

    question = "这个项目使用了哪些技术栈？"
    print(f"\n问题: {question}")
    print("\n正在获取回答...")

    result = agent.execute(question)
    print("\n回答:")
    print("-" * 80)
    print(result["answer"])
    print("-" * 80)


if __name__ == "__main__":
    # 运行流式示例
    main()

    # 如果想运行非流式示例，取消下面的注释
    # non_streaming_example()
