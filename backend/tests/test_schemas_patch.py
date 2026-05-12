"""
验证 schemas_patch 是否正确定义
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from schemas_patch import PatchOperation, StructuredPatch

print("=" * 60)
print("成功导入 StructuredPatch！")
print("=" * 60)

# 创建一个示例补丁
operation = PatchOperation(
    path="subject.label",
    operation="set",
    value="tiger"
)

patch = StructuredPatch(
    summary="将主体从猫改为老虎",
    operations=[operation],
    reasoning="用户要求把猫改为老虎"
)

print(f"补丁总结：{patch.summary}")
print(f"操作数：{len(patch.operations)}")
print(f"第一个操作：{patch.operations[0].path} ({patch.operations[0].operation})")
print("\n所有验证通过！")
