/**
 * 图生文接口返回类型定义
 */

export interface WeightedTerm {
  term: string;
  weight: number;
}

export interface SubjectBlock {
  entities: string[];
  label: string;
  attributes: Record<string, string> | string[];
  count?: number;
  weight?: number;
}

export interface SceneBlock {
  environment: string[];
  background: string[];
  time_weather: string[];
  composition: string[];
}

export interface StyleBlock {
  medium: string[];
  artist_style: string[];
  aesthetic: string[];
  quality: string[];
}

export interface TechBlock {
  lighting: string[];
  camera: string[];
  color_tone: string[];
  render: string[];
}

export interface NegativeBlock {
  terms: string[];
  severity: 'weak' | 'medium' | 'strong';
  term_weights: WeightedTerm[];
}

export interface ParamsBlock {
  size: string;
  steps: number;
  cfg: number;
  sampler: string;
  seed?: number | null;
}

// 结构化提示词
export interface StructuredPrompt {
  subject: SubjectBlock;
  scene: SceneBlock;
  style: StyleBlock;
  tech: TechBlock;
  negative: NegativeBlock;
  params: ParamsBlock;
}

// 元数据
export interface ReverseMetadata {
  model_used: string;
  confidence: number;
  processing_time_ms: number;
}

// 后端接口返回结果
export interface ReverseResponse {
  schema_version: string;
  id: string;
  caption: string;
  prompt: string;
  structured: StructuredPrompt;
  meta: ReverseMetadata;
  raw?: Record<string, unknown>;
}

export interface GenerateRequest {
  prompt?: string;
  caption?: string;
}

export interface GenerateMeta {
  model_used: string;
  processing_time_ms: number;
  mode?: 'sd' | 'gemini' | 'proxy';
  requested_mode?: 'sd' | 'gemini' | 'proxy';
  fallback_used?: boolean;
  fallback_from?: 'sd' | 'gemini' | 'proxy';
  reproducibility?: 'strong' | 'best_effort';
  style_applied?: string | null;
  prompt_source?: 'structured' | 'legacy' | 'json_spec' | string;
  effective_params?: {
    mode?: 'sd' | 'gemini' | 'proxy';
    size?: string;
    steps?: number;
    cfg?: number;
    sampler?: string;
    seed?: number | null;
    has_negative_prompt?: boolean;
  };
}

export interface GenerateResponse {
  schema_version: string;
  id: string;
  prompt: string;
  image_url: string;
  meta: GenerateMeta;
  raw?: Record<string, unknown>;
}

export interface AgentMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  ts: number;
}

export interface AgentConfirmOption {
  id: string;
  label: string;
}

export interface AgentOperationProposal {
  path: string;
  operation: string;
  value?: unknown;
  description?: string | null;
  before?: unknown;
  after?: unknown;
}

export type AgentOperationDecision = 'yes' | 'no';

export interface AgentConfirmPayload {
  confirmation_id: string;
  message: string;
  summary: string;
  reasoning?: string | null;
  operations: AgentOperationProposal[];
  options: AgentConfirmOption[];
}

export interface AgentConfirmRequest {
  confirmation_id: string;
  choice: string;
  mode?: 'accept_all' | 'multi' | 'custom_prompt' | 'cancel';
  selected_operation_indexes?: number[];
  custom_text?: string;
}

export interface AgentChatRequest {
  user_input: string;
  current_prompt: StructuredPrompt;
}

export interface AgentChatResponse {
  message: string;
  updated_prompt: StructuredPrompt;
  prompt?: string | null;
  negative_prompt?: string | null;
}

// 历史记录项
export interface HistoryItem {
  id: string;                           // 唯一标识
  imageUrl: string;                     // 图片预览 URL
  result: ReverseResponse;              // 识别结果
  timestamp: number;                    // 记录时间戳
}

// 编译后的 Prompt（用于复制）
export interface CompiledPrompt {
  positive: string;   // 正向 prompt
  negative: string;   // 负向 prompt
}
