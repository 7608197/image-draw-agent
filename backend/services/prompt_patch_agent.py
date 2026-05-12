"""
补丁生成和应用 Agent（改进版）。

这个模块是整个“Agent 可控编辑”方案的核心：
- 它不让大模型直接输出最终的 StructuredPrompt；
- 而是让大模型先输出一个结构化补丁（StructuredPatch）；
- 再由后端把补丁解析、补全，并严格按字段级规则应用到对象上。

这种设计相比“直接生成最终结果”有三个明显优点：
1. 可解释：每个修改都是一条显式操作；
2. 可控：前端可以逐条展示并让用户确认；
3. 可复用：同一套补丁既可直接应用，也可用于审查和日志记录。
"""

import os
import copy
import json
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional, Tuple

import requests
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser

try:
    from ..schemas_patch import PatchOperation, StructuredPatch
    from ..schemas import StructuredPrompt
except ImportError:
    from schemas_patch import PatchOperation, StructuredPatch
    from schemas import StructuredPrompt


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class PromptPatchAgent:
    """
    补丁生成 Agent（对象版本）。

    类的职责可以概括为两部分：
    1. 生成补丁：把“用户请求 + 当前 StructuredPrompt”转换成 `StructuredPatch`；
    2. 应用补丁：把 `StructuredPatch` 按顺序作用到 `StructuredPrompt` 对象上。

    换句话说，这里实现的是一个“对象级编辑器”，而不是简单的字符串替换器。
    它直接理解各个 block（subject / scene / style / tech / negative / params）
    及其字段含义，并对不同类型字段执行不同的修改规则。
    """

    def __init__(self):
        """初始化 Agent。"""

        # 代理模型服务的连接参数。
        # 当前实现通过 requests 直接请求中转站，而不是完全依赖 LangChain，
        # 目的是更精细地兼容不同接口格式和回退逻辑。
        self.base_url = os.getenv("CLIPROXY_BASE_URL")
        self.api_key = os.getenv("CLIPROXY_API_KEY")
        self.model = os.getenv("CLIPROXY_MODEL", "gpt-5.4")

        print("=" * 70)
        print("初始化 PromptPatchAgent（对象版本）")
        print("=" * 70)
        print(f"Base URL: {self.base_url}")
        print(f"Model: {self.model}")
        print()

        # 使用 PydanticOutputParser 约束模型输出结构。
        # 这样模型即便是自然语言生成，也必须最终落到 `StructuredPatch` schema 上。
        self.parser = PydanticOutputParser(pydantic_object=StructuredPatch)

        print("PromptPatchAgent 初始化完成\n")

    def _extract_json_object(self, text: str) -> str:
        """
        从模型返回文本中提取第一个完整 JSON 对象。

        模型有时不会只返回纯 JSON，可能会夹带解释文字、Markdown 代码块或前后缀说明。
        因此这里不能直接 `json.loads(text)`，而是采用“括号配对”的方式：
        - 从第一个 `{` 开始；
        - 逐字符统计 `{` / `}` 深度；
        - 当深度回到 0 时，说明拿到了一个完整 JSON 对象。

        这样可以最大程度兼容“文本中嵌了 JSON”的返回形式。
        """
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object found in model response")
        depth = 0
        for idx in range(start, len(text)):
            ch = text[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]
        raise ValueError("Incomplete JSON object in model response")

    def _extract_responses_text(self, data: Dict[str, Any]) -> str:
        """
        从 `/responses` 非流式返回中提取文本内容。

        中转服务的 `/responses` 接口可能返回多种结构：
        - 顶层直接有 `output_text`；
        - 或者 `output -> content -> text/output_text` 的分段结构。

        该方法的目标是屏蔽返回结构差异，尽可能提取出“最终可解析文本”。
        """
        if not isinstance(data, dict):
            return ""
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text:
            return output_text
        output = data.get("output", [])
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    content = item.get("content", [])
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict):
                                if part.get("type") in {"output_text", "text"}:
                                    text = part.get("text") or part.get("output_text")
                                    if text:
                                        return text
        return ""

    def _load_json_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        把 HTTP 响应稳定解码为 JSON 对象。

        这里显式指定 UTF-8，并在解码时允许替换非法字符，
        目的是减少由于代理层编码不一致导致的 JSON 解析失败。
        """
        response.encoding = "utf-8"
        return json.loads(response.content.decode("utf-8", errors="replace"))

    def _extract_responses_stream_text(self, response: requests.Response) -> str:
        """
        从 `/responses` 的流式 SSE 返回中拼接最终文本。

        当非流式 `/responses` 没有直接给出可用文本时，
        当前实现会退回到 `stream=True` 再请求一次。

        流式事件里主要关心两类消息：
        - `response.output_text.delta`：增量文本片段；
        - `response.output_text.done`：完整文本收尾。

        如果收到了 done 文本，优先使用 done；否则退化为拼接 delta。
        """
        response.encoding = "utf-8"
        text_parts: List[str] = []
        done_text = ""
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data: "):
                continue
            payload_text = raw_line[6:]
            try:
                event = json.loads(payload_text)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            if event_type == "response.output_text.delta":
                delta = event.get("delta")
                if isinstance(delta, str):
                    text_parts.append(delta)
            elif event_type == "response.output_text.done":
                text = event.get("text")
                if isinstance(text, str) and text:
                    done_text = text
        if done_text:
            return done_text
        return "".join(text_parts).strip()

    def _extract_chat_text(self, data: Dict[str, Any]) -> str:
        """
        从 `/chat/completions` 风格的返回中提取消息文本。

        当前代理服务并不保证所有模型都稳定支持 `/responses`，
        因此这里保留了对传统 chat/completions 格式的兼容提取逻辑。
        """
        if not isinstance(data, dict):
            return ""
        message = data.get("choices", [{}])[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    part_text = part.get("text") or part.get("content")
                    if part_text:
                        text_parts.append(part_text)
            return "\n".join(text_parts).strip()
        refusal = message.get("refusal")
        if refusal:
            raise RuntimeError(f"chat refusal: {refusal}")
        return ""

    def _call_proxy_for_patch(self, prompt_text: str) -> str:
        """
        调用代理模型，获取补丁生成结果文本。

        这里实现了一个“多级回退”策略：
        1. 优先调用 `/responses` 非流式接口；
        2. 如果状态码成功但没有提取到有效文本，则尝试 `/responses` 流式接口；
        3. 如果仍失败，则退回 `/chat/completions`。

        之所以这样设计，是因为不同模型 / 不同代理实现对 OpenAI 兼容接口的支持度不完全一致。
        通过多级回退，可以显著提高补丁生成链路的可用性。
        """
        if not self.base_url:
            raise ValueError("CLIPROXY_BASE_URL is not set")
        if not self.api_key:
            raise ValueError("CLIPROXY_API_KEY is not set")

        base_url = self.base_url.rstrip("/")
        responses_endpoint = base_url + "/responses"
        chat_endpoint = base_url + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        responses_payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt_text},
                    ],
                }
            ],
        }

        response = requests.post(responses_endpoint, headers=headers, json=responses_payload, timeout=120)
        if response.status_code == 200:
            data = self._load_json_response(response)
            content = self._extract_responses_text(data)
            if not content:
                stream_response = requests.post(
                    responses_endpoint,
                    headers=headers,
                    json={**responses_payload, "stream": True},
                    timeout=120,
                    stream=True,
                )
                if stream_response.status_code == 200:
                    content = self._extract_responses_stream_text(stream_response)
            if content:
                return content

        chat_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_text,
                }
            ],
        }
        chat_response = requests.post(chat_endpoint, headers=headers, json=chat_payload, timeout=120)
        if chat_response.status_code != 200:
            raise RuntimeError(f"patch chat: {chat_response.status_code} {chat_response.text}")

        data = self._load_json_response(chat_response)
        content = self._extract_chat_text(data)
        if content:
            return content

        raise RuntimeError(f"patch proxy returned no text: {data}")

    def generate_patch_from_object(
        self,
        user_input: str,
        current_prompt: StructuredPrompt,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> StructuredPatch:
        """
        根据用户请求生成补丁（接收对象版本）。

        该方法是“自然语言 -> 结构化补丁”的核心入口。
        执行链路如下：
        1. 先把当前 `StructuredPrompt` 转成字典，便于注入提示词；
        2. 再拼接 schema 说明、当前对象内容和用户请求；
        3. 调用模型生成文本形式的补丁；
        4. 从返回中提取 JSON，并解析成 `StructuredPatch`；
        5. 最后补全每个操作的 before / after / description。

        参数：
            user_input: 用户的修改请求
            current_prompt: StructuredPrompt 对象（不是 JSON）

        返回：
            StructuredPatch 对象
        """

        current_dict = self._object_to_dict(current_prompt)
        format_instructions = self.parser.get_format_instructions()
        schema_description = self._get_schema_description()

        # 这里构造给模型的提示词。
        # 提示词同时提供：
        # - 当前对象长什么样；
        # - 允许修改哪些字段；
        # - 支持哪些操作类型；
        # - 输出必须满足什么 JSON 结构。
        #
        # 这样模型的任务就从“直接输出最终对象”转变为“输出一份可执行的修改计划”。
        prompt_text = f"""
你是一个专业的 AI 提示词编辑助手。根据用户的自然语言请求，
生成一份结构化补丁，描述如何修改结构化提示词对象。

【结构化提示词的详细说明】
{schema_description}

【当前的结构化提示词（对象表示）】
{current_dict}

【用户的修改请求】
{user_input}

【你的任务】
1. 理解用户的需求
2. 生成一个补丁，包含所有必要的修改操作
3. 每个操作指定：path（字段路径）、operation（操作类型）、value（新值）
4. 为每个操作写清楚 description，描述“为什么改、改什么”

【操作类型说明】
- set: 直接设置值
- add: 添加到列表
- remove: 从列表删除
- replace: 完全替换列表

【输出格式】
{format_instructions}
"""

        print("[PromptPatchAgent] 生成补丁（对象版本）...")
        print(f"  用户请求：{user_input}")
        if progress_callback:
            progress_callback("正在调用模型生成补丁")

        response_text = self._call_proxy_for_patch(prompt_text)
        if progress_callback:
            progress_callback("模型返回完成，正在解析补丁")

        json_text = self._extract_json_object(response_text)
        patch = self.parser.parse(json_text)

        # 模型返回的补丁通常已经有 summary / operations / reasoning，
        # 但未必稳定包含 before / after / description 等便于前端确认的细节。
        # 因此这里再做一次“工程化补全”。
        patch = self.enrich_patch_details(current_prompt, patch)

        if progress_callback:
            progress_callback(f"补丁解析完成，共 {len(patch.operations)} 个操作")
        print(f"  补丁生成成功，操作数：{len(patch.operations)}")
        return patch

    def apply_patch_to_object(
        self,
        prompt: StructuredPrompt,
        patch: StructuredPatch,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> StructuredPrompt:
        """
        直接在 `StructuredPrompt` 对象上应用补丁。

        这里不会原地修改传入的 `prompt`，而是先做深拷贝，
        再把补丁依次作用到副本上并返回。

        这样做有两个好处：
        1. 调用方仍可保留原始对象，用于对比、撤销或重新生成补丁；
        2. 可以避免复杂交互中出现“上一次编辑污染当前状态”的问题。
        """

        print("[PromptPatchAgent] 应用补丁到对象...")
        print("  Patch summary ready")
        print(f"  Operation count: {len(patch.operations)}")
        if progress_callback:
            progress_callback("正在应用补丁到结构化提示词")

        result = copy.deepcopy(prompt)

        # 按顺序执行补丁操作。
        # 顺序之所以重要，是因为前一个操作可能影响后一个操作看到的状态。
        for i, operation in enumerate(patch.operations, 1):
            print(f"\n  操作 {i}：")
            if progress_callback:
                progress_callback(f"应用操作 {i}/{len(patch.operations)}：{operation.path}")
            self._apply_operation_to_object(result, operation)

        if progress_callback:
            progress_callback("补丁应用完成")
        print(f"\n  补丁应用完成")
        return result

    def _apply_operation_to_object(
        self,
        prompt: StructuredPrompt,
        op: PatchOperation,
    ) -> None:
        """
        将单个 `PatchOperation` 应用到对象。

        `path` 采用 `block.field` 两段式写法，例如：
        - `subject.label`
        - `style.medium`
        - `negative.terms`

        当前实现支持四类操作：
        - `set`：设置单值或整段字段；
        - `add`：向列表追加，或在个别兼容场景下转成设置；
        - `remove`：从列表中删除指定元素；
        - `replace`：整个列表替换。

        注意：这里的逻辑是“结构感知”的。
        它不是简单地对字符串做替换，而是先找到 block 和字段，再根据字段当前值类型决定如何修改。
        """
        path_parts = op.path.split(".")
        block_name = path_parts[0]

        # 先根据路径第一段定位到具体 block。
        # 这样后续修改时，可以通过 getattr/setattr 直接作用在对象字段上。
        if block_name == "subject":
            block = prompt.subject
        elif block_name == "scene":
            block = prompt.scene
        elif block_name == "style":
            block = prompt.style
        elif block_name == "tech":
            block = prompt.tech
        elif block_name == "negative":
            block = prompt.negative
        elif block_name == "params":
            block = prompt.params
        else:
            print(f"    [WARN] 未知的块：{block_name}")
            return

        if len(path_parts) < 2:
            print(f"    [WARN] 路径不完整：{op.path}")
            return

        field_name = path_parts[1]

        if op.operation == "set":
            old_value = getattr(block, field_name, None)
            new_value = op.value

            # 如果旧值是列表，而新值是单个值，则自动包装成列表，
            # 避免把原本的列表字段写成标量。
            if isinstance(old_value, list) and not isinstance(new_value, list):
                new_value = [] if new_value is None else [new_value]
            # `attributes` 允许多种表示形式，因此这里对字符串做兼容归一化。
            elif field_name == "attributes" and isinstance(new_value, str):
                new_value = [new_value] if new_value else []
            setattr(block, field_name, new_value)
            print(f"    SET {op.path}")
            print(f"      Old value: {old_value}")
            print(f"      New value: {new_value}")

        elif op.operation == "add":
            field_value = getattr(block, field_name, None)
            if isinstance(field_value, list):
                # 对列表字段执行追加。
                # 如果 value 本身也是列表，则 extend；否则 append。
                if isinstance(op.value, list):
                    field_value.extend(op.value)
                else:
                    field_value.append(op.value)
                print(f"    ADD to {op.path}: {op.value}")
            elif field_name == "attributes":
                # `attributes` 是一个历史上兼容性较强的字段：
                # 可能表现为 dict，也可能表现为 list。
                # 因此这里根据当前值和新值类型做不同归一化处理。
                if isinstance(field_value, dict) and isinstance(op.value, dict):
                    field_value.update(op.value)
                    print(f"    ADD to {op.path}: {op.value}")
                else:
                    new_value = op.value if isinstance(op.value, list) else ([] if op.value is None else [op.value])
                    setattr(block, field_name, new_value)
                    print(f"    ADD (normalize) {op.path}: {new_value}")
            else:
                # 对于非列表字段，`add` 没有天然语义，
                # 这里退化为“直接设置”，以尽量兼容模型输出。
                setattr(block, field_name, op.value)
                print(f"    ADD (set) {op.path}: {op.value}")

        elif op.operation == "remove":
            field_value = getattr(block, field_name, None)
            if isinstance(field_value, list):
                if isinstance(op.value, list):
                    before = field_value.copy()
                    new_list = [x for x in field_value if x not in op.value]
                    setattr(block, field_name, new_list)
                    print(f"    REMOVE from {op.path}: {op.value}")
                    print(f"      Before: {before}")
                    print(f"      After: {new_list}")
                else:
                    if op.value in field_value:
                        field_value.remove(op.value)
                    print(f"    REMOVE from {op.path}: {op.value}")
            else:
                print(f"    [WARN] {op.path} 不是列表，跳过")

        elif op.operation == "replace":
            old_value = getattr(block, field_name, None)
            # `replace` 语义上针对列表，因此这里把单值也统一包装成列表。
            new_value = op.value if isinstance(op.value, list) else [op.value]
            setattr(block, field_name, new_value)
            print(f"    REPLACE {op.path}")
            print(f"      Old value: {old_value}")
            print(f"      New value: {new_value}")

        else:
            print(f"    [WARN] 未知操作：{op.operation}")

    def _get_block_and_field(self, prompt: StructuredPrompt, path: str) -> Tuple[Any, str]:
        """
        根据路径字符串解析出目标 block 和字段名。

        这个辅助函数主要服务于 `enrich_patch_details`，
        用来在“不真正修改最终对象”的前提下，读取某个操作对应的当前值。
        """
        path_parts = path.split(".")
        block_name = path_parts[0] if path_parts else ""
        field_name = path_parts[1] if len(path_parts) > 1 else ""

        if block_name == "subject":
            block = prompt.subject
        elif block_name == "scene":
            block = prompt.scene
        elif block_name == "style":
            block = prompt.style
        elif block_name == "tech":
            block = prompt.tech
        elif block_name == "negative":
            block = prompt.negative
        elif block_name == "params":
            block = prompt.params
        else:
            raise ValueError(f"Unknown path: {path}")

        return block, field_name

    def _normalize_after_value(self, old_value: Any, field_name: str, operation: str, value: Any) -> Any:
        """
        根据“旧值 + 操作类型 + 新值”推导操作后的结果。

        这个函数并不真正修改对象，而是纯粹用于推导 `after` 字段，
        让前端在用户确认补丁前就能看到“改完会变成什么”。

        其规则需要与 `_apply_operation_to_object` 保持一致，
        否则用户看到的预览和最终实际应用结果就会不一致。
        """
        if operation == "set":
            if isinstance(old_value, list) and not isinstance(value, list):
                return [] if value is None else [value]
            if field_name == "attributes" and isinstance(value, str):
                return [value] if value else []
            return value

        if operation == "add":
            if isinstance(old_value, list):
                next_items = list(old_value)
                if isinstance(value, list):
                    next_items.extend(value)
                else:
                    next_items.append(value)
                return next_items
            if field_name == "attributes" and isinstance(old_value, dict) and isinstance(value, dict):
                next_dict = dict(old_value)
                next_dict.update(value)
                return next_dict
            if field_name == "attributes":
                return value if isinstance(value, list) else ([] if value is None else [value])
            return value

        if operation == "remove":
            if isinstance(old_value, list):
                remove_values = value if isinstance(value, list) else [value]
                return [item for item in old_value if item not in remove_values]
            return old_value

        if operation == "replace":
            return value if isinstance(value, list) else [value]

        return value

    def _default_operation_description(self, op: PatchOperation) -> str:
        """
        当模型没有给某条操作写说明时，自动生成一个基础描述。

        该描述不追求自然语言润色，而是优先保证：
        - 信息完整；
        - 能直接看出路径、修改前值和修改后值；
        - 适合在前端确认框中兜底展示。
        """
        after_text = json.dumps(op.after, ensure_ascii=False) if op.after is not None else "null"
        before_text = json.dumps(op.before, ensure_ascii=False) if op.before is not None else "null"
        return f"将 {op.path} 从 {before_text} 调整为 {after_text}"

    def enrich_patch_details(self, prompt: StructuredPrompt, patch: StructuredPatch) -> StructuredPatch:
        """
        为补丁补全工程化细节：`before`、`after` 和兜底 `description`。

        模型生成补丁时，重点通常放在“改哪里、怎么改”，
        但为了让前端更容易展示、也为了让用户更容易确认，
        后端会补出以下信息：
        - `before`: 当前值是什么；
        - `after`: 应用操作后预计会变成什么；
        - `description`: 若模型未提供，则自动生成一条可读说明。

        实现上，这里维护了一个 `working_prompt` 副本：
        - 每处理完一条操作，就把它应用到副本上；
        - 下一条操作计算 before/after 时，看到的是“前面操作已经生效后的状态”。

        这样可以保证多操作补丁的预览结果与实际执行顺序一致。
        """
        enriched_operations: List[PatchOperation] = []
        working_prompt = copy.deepcopy(prompt)

        for operation in patch.operations:
            try:
                block, field_name = self._get_block_and_field(working_prompt, operation.path)
                before = copy.deepcopy(getattr(block, field_name, None))
                after = self._normalize_after_value(before, field_name, operation.operation, operation.value)
            except Exception:
                before = operation.before
                after = operation.after if operation.after is not None else operation.value

            enriched_operation = operation.model_copy(update={
                "before": before,
                "after": after,
                "description": operation.description or self._default_operation_description(operation.model_copy(update={"before": before, "after": after})),
            })
            enriched_operations.append(enriched_operation)

            try:
                self._apply_operation_to_object(working_prompt, enriched_operation)
            except Exception:
                pass

        return patch.model_copy(update={"operations": enriched_operations})

    def _object_to_dict(self, prompt: StructuredPrompt) -> Dict[str, Any]:
        """
        把 `StructuredPrompt` 对象转换为普通字典。

        该方法主要用于两类场景：
        1. 把当前对象内容塞进提示词，提供给模型理解当前状态；
        2. 把修改后的对象转换为 JSON 可序列化结构，供接口层或工具层返回。

        这里显式列出每个字段，而不是直接依赖通用序列化，
        目的是让补丁生成链路拿到一个稳定、可控、字段顺序清晰的对象表示。
        """
        return {
            "subject": {
                "label": prompt.subject.label,
                "entities": prompt.subject.entities,
                "attributes": prompt.subject.attributes,
                "count": prompt.subject.count,
                "weight": prompt.subject.weight,
            },
            "scene": {
                "environment": prompt.scene.environment,
                "background": prompt.scene.background,
                "time_weather": prompt.scene.time_weather,
                "composition": prompt.scene.composition,
            },
            "style": {
                "medium": prompt.style.medium,
                "artist_style": prompt.style.artist_style,
                "aesthetic": prompt.style.aesthetic,
                "quality": prompt.style.quality,
            },
            "tech": {
                "lighting": prompt.tech.lighting,
                "camera": prompt.tech.camera,
                "color_tone": prompt.tech.color_tone,
                "render": prompt.tech.render,
            },
            "negative": {
                "terms": prompt.negative.terms,
                "severity": prompt.negative.severity,
                "term_weights": [
                    {"term": wt.term, "weight": wt.weight}
                    for wt in prompt.negative.term_weights
                ],
            },
            "params": {
                "size": prompt.params.size,
                "steps": prompt.params.steps,
                "cfg": prompt.params.cfg,
                "sampler": prompt.params.sampler,
                "seed": prompt.params.seed,
            },
        }

    def _get_schema_description(self) -> str:
        """
        返回给模型看的结构说明文本。

        它的作用不是替代完整 schema 校验，而是为模型提供一个“足够明确的字段语义说明”，
        帮助模型知道：
        - 有哪些 block；
        - 每个 block 包含哪些字段；
        - 哪些字段是列表、哪些是标量；
        - 参数字段大致表示什么含义。
        """
        return """
【StructuredPrompt 对象的详细说明】

StructuredPrompt 有 6 个属性：

1. subject (SubjectBlock) - 主体
   - label: str - 主体标签，如 \"cat\", \"tiger\"
   - entities: List[str] - 主体实体列表
   - attributes: Union[Dict[str, str], List[str]] - 属性
   - count: Optional[int] - 数量
   - weight: Optional[float] - 权重（0.8-1.2）

2. scene (SceneBlock) - 场景
   - environment: List[str] - 环境词
   - background: List[str] - 背景词
   - time_weather: List[str] - 时间/天气词
   - composition: List[str] - 构图词

3. style (StyleBlock) - 风格
   - medium: List[str] - 媒介词
   - artist_style: List[str] - 艺术家风格词
   - aesthetic: List[str] - 美学词
   - quality: List[str] - 质量词

4. tech (TechBlock) - 技术
   - lighting: List[str] - 光照词
   - camera: List[str] - 镜头词
   - color_tone: List[str] - 色调词
   - render: List[str] - 渲染词

5. negative (NegativeBlock) - 负向词
   - terms: List[str] - 负向词列表
   - severity: str - 强度等级 (weak/medium/strong)
   - term_weights: List[WeightedTerm] - 带权重的词

6. params (ParamsBlock) - 参数
   - size: str - 分辨率
   - steps: int - 采样步数
   - cfg: float - CFG 强度
   - sampler: str - 采样器
   - seed: Optional[int] - 随机种子
"""


patch_agent = PromptPatchAgent()
