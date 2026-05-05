from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult, ChatGeneration
from langsmith import Client


class DashscopeTokenHandler(BaseCallbackHandler):
    """自动为 DashScope 调用补充 token 用量和模型信息"""

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        run_id = kwargs.get("run_id")
        if not run_id:
            return

        generation = response.generations[0][0] if response.generations else None
        if not generation or not generation.generation_info or "token_usage" not in generation.generation_info:
            return

        usage = generation.generation_info["token_usage"]

        client = Client()
        client.update_run(
            run_id=run_id,
            usage_metadata={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            extra={"metadata": {
                "ls_provider": "dashscope",
                "ls_model_name": "qwen-max",
            }},
        )