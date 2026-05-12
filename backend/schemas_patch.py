"""
补丁相关的 Pydantic 数据模型定义

这个文件定义了 LangChain Agent 输出的数据结构，
确保 AI 生成的补丁符合预期的格式。

关键模型：
1. PatchOperation - 单个修改操作
2. StructuredPatch - 完整的结构化补丁
"""

from pydantic import BaseModel, Field
from typing import List, Any, Optional, Literal


# ================================================================
# 数据模型1：单个修改操作
# ================================================================

class PatchOperation(BaseModel):
    """
    单个修改操作

    描述对结��化提示词的一个原子修改操作。
    每个操作指定：
    - 修改什么（path）
    - 怎么修改（operation）
    - 修改成什么（value）

    例子：
    {
      "path": "subject.label",
      "operation": "set",
      "value": "tiger"
    }

    或：
    {
      "path": "style.medium",
      "operation": "add",
      "value": ["oil painting"]
    }
    """

    path: str = Field(
        ...,
        description="""
        JSON 路径，用点号分隔。
        
        指定要修改的字段位置。
        
        例子：
        - "subject.label" → 修改 obj.subject.label
        - "style.medium" → 修改 obj.style.medium
        - "negative.terms" → 修改 obj.negative.terms
        - "params.size" → 修改 obj.params.size
        """,
        example="subject.label"
    )

    operation: str = Field(
        ...,
        description="""
        操作类型，必须是以下之一：
        
        1. "set" - 直接设置值
           用于替换单个值（字符串、数字等）
           例子：{"path": "subject.label", "operation": "set", "value": "tiger"}
        
        2. "add" - 添加到列表末尾
           用于向列表中添加元素
           例子：{"path": "style.medium", "operation": "add", "value": ["oil painting"]}
           如果 value 是列表，会使用 extend；如果是单个值，会 append
        
        3. "remove" - 从列表中删除
           用于删除列表中的元素
           例子：{"path": "style.artist_style", "operation": "remove", "value": ["anime"]}
           会删除所有匹配的元素
        
        4. "replace" - 完全替换列表
           用于完全替换整个列表的内容
           例子：{"path": "negative.terms", "operation": "replace", "value": ["blurry", "low quality"]}
           会将整个列表替换为新值
        """,
        example="set"
    )

    value: Optional[Any] = Field(
        None,
        description="""
        新值，数据类型取决于操作类型：

        - set: 任何值（字符串、数字、列表、字典等）
          例子：value: "tiger"
                value: 1024
                value: 7.5

        - add: 单个值或列表
          例子：value: "oil painting"
                value: ["oil painting", "digital art"]

        - remove: 单个值或列表（要删除的元素）
          例子：value: "anime"
                value: ["anime", "cartoon"]

        - replace: 列表（新的列表内容）
          例子：value: ["blurry", "low quality", "distorted"]

        对于某些操作可以为 None。
        """,
        example="tiger"
    )
    description: Optional[str] = Field(None, description="对该操作的人类可读描述")
    before: Optional[Any] = Field(None, description="操作前的值")
    after: Optional[Any] = Field(None, description="操作后的值")

    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True


# ================================================================
# 数据模型2：完整的结构化补丁
# ================================================================

class StructuredPatch(BaseModel):
    """
    完整的结构化补丁

    LangChain Agent 根据用户输入生成这个对象。
    它包含：
    1. 补丁的总结（一句话说明要做什么）
    2. 具体的修改操作列表
    3. 详细的推理过程

    例子：
    {
      "summary": "将主体从猫改为老虎，并增强油画风格",
      "operations": [
        {
          "path": "subject.label",
          "operation": "set",
          "value": "tiger"
        },
        {
          "path": "style.medium",
          "operation": "add",
          "value": ["oil painting"]
        }
      ],
      "reasoning": "用户明确要求将猫替换为老虎，这是主体标签的直接替换。
                   同时用户要求加强油画风格，所以在 style.medium 中添加了 'oil painting'。
                   这两个修改都能满足用户的需求。"
    }
    """

    summary: str = Field(
        ...,
        description="""
        用一句话总结这个补丁的作用。
        
        这个字段应该清晰、简洁地描述补丁将做什么。
        
        例子：
        - "将主体从猫改为老虎，并增油画风格"
        - "删除所有动画相关的风格，改为现实主义"
        - "提高图片的质量和分辨率"
        - "添加更多细节和光影效果"
        - "改变场景从室内改为户外，同时增强自然光"
        """,
        example="将主体从猫改为老虎，并增强油画风格"
    )

    operations: List[PatchOperation] = Field(
        ...,
        description="""
        修改操作列表。
        
        包含所有需要应用的修改操作，按顺序执行。
        
        关键点：
        1. 操作会按列表顺序依次应用
        2. 每个操作都应该有明确的 path 和合理的 value
        3. 可以有 0 个、1 个或多个操作
        4. 同一个 path 不要出现多个冲突的操作
        
        例子：
        operations: [
          {
            "path": "subject.label",
            "operation": "set",
            "value": "tiger"
          },
          {
            "path": "style.medium",
            "operation": "add",
            "value": ["oil painting"]
          },
          {
            "path": "style.artist_style",
            "operation": "remove",
            "value": ["anime"]
          }
        ]
        """,
        example=[
            {
                "path": "subject.label",
                "operation": "set",
                "value": "tiger"
            }
        ]
    )

    reasoning: str = Field(
        ...,
        description="""
        详细解释为什么要做这些修改。
        
        这个字段应该：
        1. 解释用户的需求是什么
        2. 说明选择这些操作的理由
        3. 说明这些操作如何满足用户的需求
        4. 可选：说明有什么其他考虑或建议
        
        例子：
        "用户明确要求将猫替换为老虎。为了实现这一点，我修改了 subject.label
        从 'cat' 改为 'tiger'。
        
        用户还要求加强油画风格。为了实现这一点，我在 style.medium 列表中添加了 
        'oil painting'，这样可以将生成的图片风格��导向油画方向。
        
        同时，我删除了 'anime' 这个艺术风格标签，因为油画风格通常与动画风格不兼容，
        用户的需求是强调油画而不是动画。
        
        这些修改综合起来能够满足用户的所有需求。"
        """,
        example="""用户明确要求将猫替换为老虎，这是主体标签的直接替换。
同时用户要求加强油画风格，所以在 style.medium 中添加了 'oil painting'。
这两个修改都能满足用户的需求。"""
    )

    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
        validate_assignment = True


# ================================================================
# 数据验证辅助函数
# ================================================================

def validate_patch_operation(op: PatchOperation) -> bool:
    """
    验证单个 PatchOperation 是否有效。

    检查：
    1. path 不为空
    2. operation 是有效的类型（set/add/remove/replace）
    3. value 的类型与 operation 匹配

    参��：
        op: 要验证的操作

    返回：
        True 表示有效，False 表示无效

    例子：
        >>> op = PatchOperation(path="subject.label", operation="set", value="tiger")
        >>> validate_patch_operation(op)
        True
    """

    # 检查 path
    if not op.path or not isinstance(op.path, str):
        print(f"错误：path 必须是非空字符串，得到 {op.path}")
        return False

    # 检查 path 格式
    if "." not in op.path:
        print(f"错误：path 必须包含点号（如 'subject.label'），得到 {op.path}")
        return False

    # 检查 operation
    valid_operations = {"set", "add", "remove", "replace"}
    if op.operation not in valid_operations:
        print(f"错误：operation 必须是 {valid_operations} 之一，得到 {op.operation}")
        return False

    # 检查 value
    if op.operation in {"add", "remove", "replace"} and op.value is None:
        print(f"错误：{op.operation} 操作需要提供 value")
        return False

    return True


def validate_patch(patch: StructuredPatch) -> bool:
    """
    验证完整的 StructuredPatch 是否有效。

    检查：
    1. summary 不为空
    2. operations 列表不为空
    3. 每个 operation 都是有效的
    4. reasoning 不为空

    参数：
        patch: 要验证的补丁

    返回：
        True 表示有效，False 表示无效

    例子：
        >>> patch = StructuredPatch(
        ...     summary="...",
        ...     operations=[...],
        ...     reasoning="..."
        ... )
        >>> validate_patch(patch)
        True
    """

    # 检查 summary
    if not patch.summary or not isinstance(patch.summary, str):
        print("错误：summary 必须是非空字符串")
        return False

    # 检查 operations
    if not isinstance(patch.operations, list):
        print("错误：operations 必须是列表")
        return False

    if len(patch.operations) == 0:
        print("警告：operations 列表为空，没有修改操作")

    # 验证每个操作
    for i, op in enumerate(patch.operations):
        if not validate_patch_operation(op):
            print(f"错误：第 {i} 个操作验证失败")
            return False

    # 检查 reasoning
    if not patch.reasoning or not isinstance(patch.reasoning, str):
        print("错误：reasoning 必须是非空字符串")
        return False

    return True


# ================================================================
# 测试代码
# ================================================================

if __name__ == "__main__":
    """
    测试 schemas_patch 模块
    """

    print("=" * 70)
    print("测试 schemas_patch 模块")
    print("=" * 70)
    print()

    # 创建示例操作
    op1 = PatchOperation(
        path="subject.label",
        operation="set",
        value="tiger"
    )

    op2 = PatchOperation(
        path="style.medium",
        operation="add",
        value=["oil painting"]
    )

    op3 = PatchOperation(
        path="style.artist_style",
        operation="remove",
        value=["anime"]
    )

    print("✓ 创建 PatchOperation 成功")
    print()

    # 创建示例补丁
    patch = StructuredPatch(
        summary="将主体从猫改为老虎，并增强油画风格",
        operations=[op1, op2, op3],
        reasoning="""
用户明确要求将猫替换为老虎。为了实现这一点，我修改了 subject.label 从 'cat' 改为 'tiger'。

用户还要求加强油画风格。为了实现这一点，我在 style.medium 列表中添加了 'oil painting'。

同时，我删除了 'anime' 这个艺术风格标签，因为油画风格与动画风格通常不兼容。

这些修改综合起来能够满足用户的所有需求。
        """
    )

    print("✓ 创建 StructuredPatch 成功")
    print()

    # 验证补丁
    if validate_patch(patch):
        print("✓ 补丁验证成功")
    else:
        print("✗ 补丁验证失败")

    print()

    # 打印补丁信息
    print("【补丁摘要】")
    print(f"  {patch.summary}")
    print()

    print("【修改操作】")
    for i, op in enumerate(patch.operations, 1):
        print(f"  {i}. {op.path} ({op.operation}) → {op.value}")
    print()

    print("【推理过程】")
    print(f"  {patch.reasoning}")
    print()

    print("=" * 70)
    print("测试完成")
    print("=" * 70)