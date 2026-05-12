import os
import json
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from ..schemas import StructuredPrompt
    from ..schemas_patch import StructuredPatch
except ImportError:
    from schemas import StructuredPrompt
    from schemas_patch import StructuredPatch

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .prompt_tools import (
    modify_structured_prompt_object,
    validate_structured_prompt_object,
    compile_prompt_object,
    get_prompt_schema_object,
)


class PromptEditAgent:
    """
    完整的提示词编辑 Agent（对象版本）。

    这个类是“自然语言编辑结构化提示词”能力的总入口，主要负责四件事：
    1. 初始化底层大模型与 LangChain Agent；
    2. 挂载可调用的工具（修改 / 校验 / 编译 / 查看 schema）；
    3. 提供“生成补丁”和“应用补丁”两个分阶段能力；
    4. 对外暴露一个简化入口，让上层可以直接完成整次修改流程。

    从系统分层上看，它更像是“编排层”：
    - 真正的补丁生成与补丁应用逻辑在 `prompt_patch_agent.py`；
    - 真正暴露给 LangChain 调用的工具在 `prompt_tools.py`；
    - 本类负责把这些能力组织成可直接被接口层使用的调用链路。
    """

    def __init__(self):
        """初始化 Agent。"""

        # 这里读取代理服务地址、鉴权信息和模型名。
        # 这些配置会被传给 ChatOpenAI，使其通过兼容 OpenAI 的接口访问中转模型服务。
        base_url = os.getenv("CLIPROXY_BASE_URL")
        api_key = os.getenv("CLIPROXY_API_KEY")
        model = os.getenv("CLIPROXY_MODEL", "gpt-5.4")

        print("=" * 70)
        print("初始化 PromptEditAgent（对象版本）")
        print("=" * 70)
        print(f"Base URL: {base_url}")
        print(f"Model: {model}")
        print()

        # LangChain LLM 封装。
        # `use_responses_api=False` 表示这里沿用 chat/completions 兼容调用方式，
        # 与当前代理服务的接口行为保持一致。
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.3,
            max_tokens=2000,
            use_responses_api=False,
        )

        # Agent 可调用的工具集合。
        # 这些工具覆盖了完整编辑闭环：
        # - modify: 根据自然语言生成补丁并应用；
        # - validate: 检查结构化提示词是否满足 schema；
        # - compile: 编译出最终正向 / 负向 prompt；
        # - schema: 告诉模型当前结构化对象长什么样。
        self.tools = [
            modify_structured_prompt_object,
            validate_structured_prompt_object,
            compile_prompt_object,
            get_prompt_schema_object,
        ]

        # 创建 LangChain Agent。
        # 这里的 system_prompt 强调“优先使用工具”，目的是避免模型直接自由发挥，
        # 而是显式走工具链来修改、校验和编译结构化对象，提高输出可控性。
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=(
                "你是一个专业的结构化提示词编辑助手。"
                "优先使用可用工具来修改、验证、编译 StructuredPrompt 对象。"
                "当用户请求修改提示词时，先调用 modify 工具；"
                "需要检查结构时调用 validate 工具；"
                "需要生成正向/负向 prompt 时调用 compile 工具。"
            ),
            debug=True,
            name="prompt_edit_agent",
        )

        print("PromptEditAgent 初始化成功\n")

    def _extract_output_text(self, result: dict) -> str:
        """
        从 `create_agent` 的返回结构中提取最终文本。

        LangChain Agent 的返回结果并不总是一个单纯字符串，常见情况包括：
        1. `messages[-1].content` 直接就是字符串；
        2. `content` 是一个分段列表，每段可能是带 `type=text` 的字典；
        3. 某些情况下最后只剩一个对象，需要退化为 `str(...)`。

        这里统一做一层兼容处理，保证上层调用者总能拿到一个普通字符串，
        不需要关心 Agent 内部消息格式的细节。
        """

        messages = result.get("messages", [])
        if not messages:
            return str(result)

        content = getattr(messages[-1], "content", messages[-1])
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)

        return str(content)

    def run(
        self,
        user_input: str,
        current_prompt: StructuredPrompt,
    ) -> str:
        """
        运行完整 Agent 并返回最终文本结果。

        该方法用于“让 Agent 自己决定调用哪些工具并给出回复”。
        它和 `prepare_patch` / `apply_patch` 的区别是：
        - `run` 返回的是 Agent 的最终文本输出；
        - `prepare_patch` / `apply_patch` 返回的是更可控的结构化中间结果。

        参数：
            user_input: 用户的自然语言请求
            current_prompt: 当前的 StructuredPrompt 对象

        返回：
            Agent 的最终文本结果
        """

        from .prompt_patch_agent import patch_agent

        # 先把对象形式的 StructuredPrompt 转成 JSON 文本。
        # 这样做有两个目的：
        # 1. 便于把“当前状态”完整、稳定地提供给 Agent；
        # 2. 让 Agent 工具可以直接复用 JSON 输入输出，而不要求工具直接处理 Python 对象。
        prompt_json = json.dumps(
            patch_agent._object_to_dict(current_prompt),
            ensure_ascii=False,
        )

        # 这里构造给 LangChain Agent 的用户消息。
        # 消息中同时包含“用户请求”和“当前提示词状态”，
        # 让 Agent 能基于上下文决定下一步调用哪个工具。
        agent_input = f"""
【用户请求】
{user_input}

【当前提示词（JSON）】
{prompt_json}

请完成用户的请求。
"""

        print("=" * 70)
        print("Agent 运行中（对象版本）...")
        print("=" * 70)
        print()

        # 调用 LangChain Agent。
        # Agent 会根据 system prompt 和 tools 自主决定是否先修改、再校验、再编译。
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": agent_input}]}
        )
        output = self._extract_output_text(result)

        print()
        print("=" * 70)
        print("Agent 执行完成")
        print("=" * 70)

        return output

    def prepare_patch(
        self,
        user_input: str,
        current_prompt: StructuredPrompt,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> StructuredPatch:
        """
        生成“待确认”的结构化补丁，但不立即修改对象。

        这是确认式交互中的第一阶段：
        1. 根据用户请求和当前对象生成补丁；
        2. 把补丁返回给上层（通常是接口层或前端）用于展示和确认；
        3. 等用户确认后，再由 `apply_patch` 真正落到对象上。

        这种两阶段设计比“模型直接修改最终对象”更可控，
        也更适合前端逐条展示修改项。
        """

        from .prompt_patch_agent import patch_agent

        print("=" * 70)
        print("生成待确认补丁（对象版本）")
        print("=" * 70)
        print()

        if progress_callback:
            progress_callback("正在准备当前结构化提示词")

        patch = patch_agent.generate_patch_from_object(
            user_input,
            current_prompt,
            progress_callback=progress_callback,
        )

        if progress_callback:
            progress_callback("补丁已生成，等待确认")

        print("\n补丁生成成功！")
        print(f"摘要：{patch.summary}")
        return patch

    def apply_patch(
        self,
        current_prompt: StructuredPrompt,
        patch: StructuredPatch,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> StructuredPrompt:
        """
        将已确认的补丁应用到结构化提示词对象上。

        这里默认认为 `patch` 已经通过了上层确认流程，
        因此本方法只负责“执行补丁”，不负责再次向模型询问。
        这样可以把“生成修改方案”和“真正落地修改”明确拆开。
        """

        from .prompt_patch_agent import patch_agent

        modified = patch_agent.apply_patch_to_object(
            current_prompt,
            patch,
            progress_callback=progress_callback,
        )

        if progress_callback:
            progress_callback("补丁应用完成")

        return modified

    def run_simple(
        self,
        user_input: str,
        current_prompt: StructuredPrompt,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> StructuredPrompt:
        """
        简化模式：直接完成“生成补丁 + 应用补丁”并返回修改后的对象。

        适用于不需要人工确认补丁明细的场景。
        它内部仍然沿用与确认模式一致的补丁机制，
        只是把两个阶段串联执行：
        1. `prepare_patch` 先生成结构化补丁；
        2. `apply_patch` 再把补丁应用到当前对象。

        这样做的好处是：
        - 内部逻辑保持统一；
        - 即使将来切换回确认式交互，也无需重写底层编辑能力。
        """

        print("=" * 70)
        print("简化模式（对象版本）")
        print("=" * 70)
        print()

        try:
            patch = self.prepare_patch(
                user_input,
                current_prompt,
                progress_callback=progress_callback,
            )
            modified = self.apply_patch(
                current_prompt,
                patch,
                progress_callback=progress_callback,
            )

            print("\n修改成功！")
            print("摘要已生成")

            return modified

        except Exception as e:
            print(f"\n修改失败：{str(e)}")
            raise


prompt_agent = PromptEditAgent()
