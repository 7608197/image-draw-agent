"""
Agent 工具（对象版本）。

这个模块的定位是“把底层对象操作能力包装成 LangChain 可调用工具”。
也就是说：
- `prompt_patch_agent.py` 负责真正生成和应用补丁；
- 本文件负责把这些能力暴露成工具函数，供 Agent 在推理过程中调用；
- 每个工具都以字符串输入 / 字符串输出为主，方便与大模型工具调用协议对接。

这些工具共同组成了一个最小闭环：
1. 查看 schema（让模型知道结构长什么样）；
2. 修改结构化提示词；
3. 校验结果是否合法；
4. 编译成最终正向 / 负向 prompt。
"""

import json
from langchain_core.tools import tool
from typing import Dict, Any

try:
    from ..schemas import StructuredPrompt
except ImportError:
    from schemas import StructuredPrompt


@tool
def modify_structured_prompt_object(
    user_request: str,
    current_prompt_json: str
) -> str:
    """
    根据用户请求修改结构化提示词（对象版本）。

    这个工具是 Agent 最核心的“执行修改”工具。
    它的完整链路如下：
    1. 把 JSON 字符串反序列化为 `StructuredPrompt` 对象；
    2. 根据用户自然语言请求生成结构化补丁；
    3. 将补丁应用到对象；
    4. 再把修改后的对象序列化回 JSON 字符串返回给 Agent。

    之所以采用“JSON -> 对象 -> 补丁 -> 对象 -> JSON”的往返方式，
    是因为 Agent 工具协议更适合传字符串，而核心编辑逻辑更适合操作强类型对象。

    参数：
        user_request: 用户的自然语言修改请求
        current_prompt_json: 当前提示词的 JSON 字符串

    返回：
        修改后的提示词 JSON 字符串；
        如果中途失败，则返回带 `error` 字段的 JSON 字符串。
    """

    from .prompt_patch_agent import patch_agent

    try:
        # 1. JSON -> 对象
        # 这里显式构造每个 block，而不是直接把整段 JSON 塞进 StructuredPrompt，
        # 目的是让 Pydantic 在每个子块上完成字段级校验，并在格式不对时尽早报错。
        prompt_dict = json.loads(current_prompt_json)
        from ..schemas import SubjectBlock, SceneBlock, StyleBlock, TechBlock, NegativeBlock, ParamsBlock

        prompt = StructuredPrompt(
            subject=SubjectBlock(**prompt_dict.get("subject", {})),
            scene=SceneBlock(**prompt_dict.get("scene", {})),
            style=StyleBlock(**prompt_dict.get("style", {})),
            tech=TechBlock(**prompt_dict.get("tech", {})),
            negative=NegativeBlock(**prompt_dict.get("negative", {})),
            params=ParamsBlock(**prompt_dict.get("params", {})),
        )
    except Exception as e:
        return json.dumps({"error": f"Invalid prompt object: {str(e)}"}, ensure_ascii=False)

    try:
        # 2. 生成补丁
        # 这里不是让模型直接返回最终对象，而是先生成结构化补丁，
        # 这样后续既可以直接应用，也可以在别的场景中用于确认、审查和逐条筛选。
        print(f"[Tool] 生成补丁（对象版本）...")
        patch = patch_agent.generate_patch_from_object(user_request, prompt)
        print(f"[Tool] 补丁生成成功")
    except Exception as e:
        return json.dumps({"error": f"Failed to generate patch: {str(e)}"}, ensure_ascii=False)

    try:
        # 3. 应用补丁到对象
        # 补丁应用发生在强类型对象上，而不是自由文本上，
        # 这样可以把修改语义限制为字段级 set / add / remove / replace 操作。
        print(f"[Tool] 应用补丁到对象...")
        modified = patch_agent.apply_patch_to_object(prompt, patch)
        print(f"[Tool] 补丁应用成功")
    except Exception as e:
        return json.dumps({"error": f"Failed to apply patch: {str(e)}"}, ensure_ascii=False)

    # 4. 对象 -> JSON
    # 返回给 Agent 的仍然是字符串形式，便于继续作为工具调用结果参与后续推理。
    result_dict = patch_agent._object_to_dict(modified)
    result_json = json.dumps(result_dict, ensure_ascii=False)

    return result_json


@tool
def validate_structured_prompt_object(prompt_json: str) -> str:
    """
    验证结构化提示词对象是否合法。

    这里的“验证”本质上是：
    - 先把 JSON 解析成 Python 字典；
    - 再尝试构造 `StructuredPrompt` 及其各个子块；
    - 如果构造成功，说明数据至少满足当前 schema 的类型和字段要求。

    该工具不负责更复杂的业务语义检查，重点是 schema 级别的结构正确性。
    """

    from ..schemas import SubjectBlock, SceneBlock, StyleBlock, TechBlock, NegativeBlock, ParamsBlock

    try:
        data = json.loads(prompt_json)
    except json.JSONDecodeError as e:
        return json.dumps({
            "is_valid": False,
            "errors": [f"JSON format error: {str(e)}"]
        }, ensure_ascii=False)

    try:
        print("[Tool] 验证提示词对象...")

        # 通过构造 Pydantic 对象来完成验证。
        # 如果字段缺失、类型不匹配或嵌套结构不符合要求，这里会直接抛异常。
        prompt = StructuredPrompt(
            subject=SubjectBlock(**data.get("subject", {})),
            scene=SceneBlock(**data.get("scene", {})),
            style=StyleBlock(**data.get("style", {})),
            tech=TechBlock(**data.get("tech", {})),
            negative=NegativeBlock(**data.get("negative", {})),
            params=ParamsBlock(**data.get("params", {})),
        )

        print("[Tool] 验证成功")
        return json.dumps({
            "is_valid": True,
            "errors": []
        }, ensure_ascii=False)

    except Exception as e:
        print(f"[Tool] 验证失败：{str(e)}")
        return json.dumps({
            "is_valid": False,
            "errors": [str(e)]
        }, ensure_ascii=False)


@tool
def compile_prompt_object(prompt_json: str) -> str:
    """
    将结构化提示词对象编译为最终正向和负向 prompt。

    该工具本身不直接实现编译规则，而是复用 `reverse_service` 中已经存在的
    `compile_structured_prompt` 逻辑，确保：
    - 逆向生成得到的结构化对象；
    - Agent 编辑后的结构化对象；
    - 最终用于文生图的 prompt 编译结果；
    三者遵循同一套规则，避免不同模块各自实现一套拼接逻辑。
    """

    from .reverse_service import reverse_service
    from ..schemas import SubjectBlock, SceneBlock, StyleBlock, TechBlock, NegativeBlock, ParamsBlock

    try:
        data = json.loads(prompt_json)
    except json.JSONDecodeError as e:
        return json.dumps({
            "error": f"JSON format error: {str(e)}"
        }, ensure_ascii=False)

    try:
        print("[Tool] 编译提示词对象...")

        # 先把 JSON 恢复成 StructuredPrompt 对象，
        # 再交给统一的编译器产出 positive / negative prompt。
        prompt = StructuredPrompt(
            subject=SubjectBlock(**data.get("subject", {})),
            scene=SceneBlock(**data.get("scene", {})),
            style=StyleBlock(**data.get("style", {})),
            tech=TechBlock(**data.get("tech", {})),
            negative=NegativeBlock(**data.get("negative", {})),
            params=ParamsBlock(**data.get("params", {})),
        )

        compiled = reverse_service.compile_structured_prompt(prompt)

        print(f"[Tool] 编译成功")

        return json.dumps({
            "positive": compiled.get("positive", ""),
            "negative": compiled.get("negative", "")
        }, ensure_ascii=False)

    except Exception as e:
        print(f"[Tool] 编译失败：{str(e)}")
        return json.dumps({
            "error": f"Compilation failed: {str(e)}"
        }, ensure_ascii=False)


@tool
def get_prompt_schema_object() -> str:
    """
    获取 `StructuredPrompt` 的简要 schema 描述。

    这个工具的作用不是返回完整 Pydantic schema，
    而是给 Agent 一个“足够理解字段结构”的轻量说明，
    便于其在生成修改建议时知道有哪些块、每个块大致负责什么。
    """

    print("[Tool] 获取 Schema...")

    schema_info = {
        "StructuredPrompt": {
            "description": "完整的结构化提示词对象",
            "fields": {
                "subject": "SubjectBlock - 主体信息",
                "scene": "SceneBlock - 场景信息",
                "style": "StyleBlock - 风格信息",
                "tech": "TechBlock - 技术信息",
                "negative": "NegativeBlock - 负向词信息",
                "params": "ParamsBlock - 生成参数"
            }
        },
        "operations": {
            "set": "直接设置对象属性的值",
            "add": "添加元素到列表属性",
            "remove": "从列表属性中删除元素",
            "replace": "替换整个列表属性"
        }
    }

    print("[Tool] Schema 已获取")
    return json.dumps(schema_info, ensure_ascii=False, indent=2)
