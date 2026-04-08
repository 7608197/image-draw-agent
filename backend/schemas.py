"""  # 模块文档字符串开始：描述整个文件用途
Pydantic 数据模型（Schema）定义文件。  # 说明本文件是数据结构定义
  # 空行用于增强可读性
作用：  # 下面列出这个文件的核心职责
1) 约束接口入参/出参的数据结构  # 定义字段有哪些、叫什么
2) 自动做类型校验（例如 int/float/list）  # 自动检查类型是否正确
3) 约束字段范围（例如权重、步数、置信度）  # 自动检查数值上下限
  # 空行
你可以把它理解成：后端接口的“数据合同”。  # 前后端/服务间约定的格式规范
"""  # 模块文档字符串结束
from typing import List, Optional, Dict, Any, Union, Literal  # 导入类型标注工具
from pydantic import BaseModel, Field  # 导入 Pydantic 的基类和字段配置工具
  # 空行
  # 定义“带权重的负向词”结构
class WeightedTerm(BaseModel):  # 继承 BaseModel，获得校验/序列化能力
    """负向词条 + 单独权重。"""  # 类说明：用于 negative.term_weights
    # 示例：{"term": "blurry", "weight": 1.2}  # 典型数据形态
    term: str = Field(..., description="Negative prompt term")  # 必填字符串；... 表示必填
    weight: float = Field(1.0, ge=0.1, le=2.0, description="Weight for this term")  # 默认1.0；范围0.1~2.0
  # 空行
  # 定义“主体块”结构
class SubjectBlock(BaseModel):  # 主体信息（人/物/对象）
    """主体信息块：识别到的主体、属性、数量、权重。"""  # 类说明
    # 对应结构化提示词中的 subject 节点  # 和 reverse 输出结构一致
    entities: List[str] = Field(default_factory=list, description="Detected entities")  # 主体实体词列表；默认空列表
    label: str = Field("", description="Main subject label")  # 主体主标签；默认空字符串
    attributes: Union[Dict[str, str], List[str]] = Field(  # 属性支持两种形态：键值对 或 字符串列表
        default_factory=dict,  # 默认空字典
        description="Attributes for subject"  # 字段说明
    )  # Field 定义结束
    count: Optional[int] = Field(None, ge=1, description="Entity count")  # 可选整数；若有值必须>=1
    weight: Optional[float] = Field(None, ge=0.8, le=1.2, description="Subject weight")  # 可选浮点；范围0.8~1.2
  # 空行
  # 定义“场景块”结构
class SceneBlock(BaseModel):  # 场景相关信息
    """场景信息块：环境、背景、时间天气、构图。"""  # 类说明
    environment: List[str] = Field(default_factory=list)  # 环境词（如 indoor/outdoor）
    background: List[str] = Field(default_factory=list)  # 背景词
    time_weather: List[str] = Field(default_factory=list)  # 时间/天气词
    composition: List[str] = Field(default_factory=list)  # 构图词（如 close-up, wide shot）
  # 空行
  # 定义“风格块”结构
class StyleBlock(BaseModel):  # 风格与审美相关信息
    """风格信息块：媒介、画风、美学、质量词。"""  # 类说明
    medium: List[str] = Field(default_factory=list)  # 媒介（digital art/oil painting等）
    artist_style: List[str] = Field(default_factory=list)  # 艺术家风格词
    aesthetic: List[str] = Field(default_factory=list)  # 审美词（cinematic等）
    quality: List[str] = Field(default_factory=list)  # 质量词（masterpiece等）
  # 空行
  # 定义“技术块”结构
class TechBlock(BaseModel):  # 技术细节信息
    """技术信息块：光照、镜头、色调、渲染相关词。"""  # 类说明
    lighting: List[str] = Field(default_factory=list)  # 光照相关词
    camera: List[str] = Field(default_factory=list)  # 镜头/相机参数词
    color_tone: List[str] = Field(default_factory=list)  # 色调词
    render: List[str] = Field(default_factory=list)  # 渲染词（8k, unreal engine等）
  # 空行
  # 定义“负向块”结构
class NegativeBlock(BaseModel):  # 负向提示词信息
    """负向信息块：负向词、强度等级、每个词的权重。"""  # 类说明
    # severity 只能是 weak/medium/strong（由 Literal 约束）  # 固定可选值
    terms: List[str] = Field(default_factory=list)  # 普通负向词列表
    severity: Literal["weak", "medium", "strong"] = Field("medium")  # 负向强度等级；默认medium
    term_weights: List[WeightedTerm] = Field(default_factory=list)  # 带单项权重的负向词列表
  # 空行
  # 定义“推荐参数块”结构
class ParamsBlock(BaseModel):  # 生成参数建议
    """推荐生成参数：分辨率、步数、CFG、采样器、随机种子。"""  # 类说明
    size: str = Field("512x512", description="Image dimensions WxH")  # 图像尺寸字符串
    steps: int = Field(30, ge=1, le=150)  # 采样步数；默认30；范围1~150
    cfg: float = Field(7.0, ge=1.0, le=30.0)  # CFG引导强度；默认7.0；范围1~30
    sampler: str = Field("DPM++ 2M Karras", description="Recommended sampler")  # 采样器名称
    seed: Optional[int] = Field(None, description="Suggested seed")  # 可选随机种子；None表示不固定
  # 空行
  # 定义“结构化提示词主对象”
class StructuredPrompt(BaseModel):  # 聚合6个子块
    """结构化提示词主对象：由 6 个信息块组成。"""  # 类说明
    # 这就是 reverse 服务产出的核心结构  # 下游可据此编译成最终prompt
    subject: SubjectBlock  # 主体块
    scene: SceneBlock  # 场景块
    style: StyleBlock  # 风格块
    tech: TechBlock  # 技术块
    negative: NegativeBlock  # 负向块
    params: ParamsBlock  # 参数块
  # 空行
  # 定义“反推过程元数据”
class ReverseMeta(BaseModel):  # reverse 的附加信息
    """反推过程元信息：模型名、置信度、耗时。"""  # 类说明
    model_used: str = Field(..., description="Model used for image analysis")  # 必填：使用了哪个视觉模型
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")  # 必填：置信度0~1
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")  # 必填：处理耗时毫秒
  # 空行
  # 定义“/reverse 接口响应”
class ReverseResponse(BaseModel):  # 完整的 reverse 返回体
    """POST /reverse 的完整响应结构。"""  # 类说明
    # 前端主要消费这个对象  # 前端展示/回填通常基于此对象
    schema_version: str = Field("2.0.0", description="API schema version")  # 响应schema版本
    id: str = Field(..., description="Unique identifier (SHA256 of image)")  # 必填：图片哈希ID
    caption: str = Field(..., description="Natural language description of the image")  # 必填：自然语言描述
    structured: StructuredPrompt = Field(  # 必填：结构化提示词对象
        ...,  # ... 表示必填
        description="Structured prompt blocks"  # 字段说明
    )  # Field 定义结束
    prompt: str = Field(..., description="Compiled prompt ready for SD/MJ")  # 必填：编译后的正向提示词字符串
    meta: ReverseMeta = Field(..., description="Processing metadata")  # 必填：元数据
    raw: Optional[Dict[str, Any]] = Field(None, description="Raw model output for debugging")  # 可选：原始模型返回，便于调试
  # 空行
  # 定义“/generate 接口请求”
class GenerateRequest(BaseModel):  # 生成接口入参
    """POST /generate 的请求结构。"""  # 类说明
    schema_version: Optional[str] = Field("1.0.0", description="Request schema version")  # 可选请求版本；默认1.0.0
    prompt: Optional[str] = Field(None, description="Positive prompt for generation")  # 可选：直接给正向词
    caption: Optional[str] = Field(None, description="Fallback caption for generation")  # 可选：当prompt缺失时可用caption回退
  # 空行
  # 定义“生成过程元数据”
class GenerateMeta(BaseModel):  # generate 的附加信息
    """文生图/图生图过程的元信息。"""  # 类说明
    model_used: str = Field(..., description="Model or backend used")  # 必填：使用的模型或后端
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")  # 必填：耗时毫秒
    mode: Optional[str] = Field(None, description="Generation mode: sd/gemini/proxy")  # 可选：生成模式
    reproducibility: Optional[str] = Field(None, description="Reproducibility level: strong|best_effort")  # 可选：可复现级别
    style_applied: Optional[str] = Field(None, description="Applied style preset name")  # 可选：应用的风格预设
    effective_params: Optional[Dict[str, Any]] = Field(None, description="Effective generation parameters after merge")  # 可选：最终生效参数
    prompt_source: Optional[str] = Field(None, description="Prompt source: structured/legacy/json_spec")  # 可选：prompt来源
  # 空行
  # 定义“/generate 接口响应”
class GenerateResponse(BaseModel):  # 完整的 generate 返回体
    """POST /generate 的响应结构。"""  # 类说明
    schema_version: str = Field("1.0.0", description="API schema version")  # 响应schema版本
    id: str = Field(..., description="Unique identifier for the generation")  # 必填：生成任务ID
    prompt: str = Field(..., description="Prompt used for generation")  # 必填：实际用于生成的prompt
    image_url: str = Field(..., description="Public URL for generated image")  # 必填：生成图片URL
    meta: GenerateMeta = Field(..., description="Generation metadata")  # 必填：元数据
    raw: Optional[Dict[str, Any]] = Field(None, description="Raw model output for debugging")  # 可选：原始模型结果
  # 空行
  # 定义“统一错误响应”
class ErrorResponse(BaseModel):  # 错误返回结构
    """统一错误响应结构。"""  # 类说明
    detail: str  # 错误详情（给人看的信息）
    error_code: Optional[str] = None  # 可选：机器可读错误码
