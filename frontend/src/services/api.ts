import axios from 'axios';
import type { ReverseResponse, GenerateResponse, ParamsBlock, AgentChatRequest, AgentChatResponse, StructuredPrompt, AgentConfirmPayload, AgentConfirmRequest, AgentOperationProposal } from '../types/reverse';

// 从环境变量读取 API 基础地址
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 120000, // 120秒超时
});

/**
 * 图生文接口：上传图片，获取描述和提示词
 * @param imageFile - 图片文件
 * @returns Promise<ReverseResponse>
 */
export async function reverseImage(imageFile: File): Promise<ReverseResponse> {
  const formData = new FormData();
  formData.append('image', imageFile);

  try {
    const response = await apiClient.post<ReverseResponse>('/reverse', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      // 处理 axios 错误
      const message = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败';
      throw new Error(message);
    }
    throw error;
  }
}

export interface TextReverseOptions {
  params?: ParamsBlock;
}

export interface GenerateOptions {
  mode?: 'sd' | 'gemini' | 'proxy' | 'default';
  style_preset?: 'photoreal' | 'anime' | 'watercolor' | 'cyberpunk' | 'ink';
  seed?: number;
  steps?: number;
  cfg?: number;
  sampler?: string;
  size?: string;
  negative_prompt?: string;
  strict_json?: boolean;
}

export async function reverseText(text: string, options?: TextReverseOptions): Promise<ReverseResponse> {
  try {
    const response = await apiClient.post<ReverseResponse>('/reverse/text', {
      text,
      ...(options?.params ? { params: options.params } : {}),
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败';
      throw new Error(message);
    }
    throw error;
  }
}

export async function generateImage(jsonFile: File, options?: GenerateOptions): Promise<GenerateResponse> {
  const formData = new FormData();
  formData.append('json', jsonFile);

  if (options) {
    (Object.entries(options) as Array<[keyof GenerateOptions, GenerateOptions[keyof GenerateOptions]]>).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== 'default') {
        formData.append(String(key), String(value));
      }
    });
  }

  try {
    const response = await apiClient.post<GenerateResponse>('/generate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 0,
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败';
      throw new Error(message);
    }
    throw error;
  }
}

export async function agentChat(payload: AgentChatRequest): Promise<AgentChatResponse> {
  try {
    const response = await apiClient.post<AgentChatResponse>('/agent/chat', payload);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败';
      throw new Error(message);
    }
    throw error;
  }
}

export async function agentChatConfirm(
  payload: AgentConfirmRequest,
  handlers: AgentChatStreamHandlers,
): Promise<void> {
  const response = await fetch(`${BASE_URL}/agent/chat/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMessage = '请求失败';
    try {
      const data = await response.json() as { detail?: string; message?: string };
      errorMessage = data.detail || data.message || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应');
  }

  await consumeAgentStream(response, handlers);
}

export interface AgentChatStreamHandlers {
  onStatus?: (message: string) => void;
  onResult?: (result: AgentChatResponse) => void;
  onConfirm?: (payload: AgentConfirmPayload) => void;
  onError?: (message: string) => void;
}

function parseAgentResult(data: Record<string, unknown>): AgentChatResponse {
  return {
    message: typeof data.message === 'string' ? data.message : '',
    updated_prompt: data.updated_prompt as StructuredPrompt,
    prompt: typeof data.prompt === 'string' || data.prompt === null ? data.prompt as string | null : undefined,
    negative_prompt: typeof data.negative_prompt === 'string' || data.negative_prompt === null ? data.negative_prompt as string | null : undefined,
  };
}

async function consumeAgentStream(response: Response, handlers: AgentChatStreamHandlers): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('浏览器不支持流式响应');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() || '';

    for (const chunk of chunks) {
      const line = chunk
        .split('\n')
        .find((entry) => entry.startsWith('data: '));
      if (!line) continue;

      const raw = line.slice(6);
      const event = JSON.parse(raw) as Record<string, unknown> & { type?: string };
      if (event.type === 'status' && typeof event.message === 'string') {
        handlers.onStatus?.(event.message);
      } else if (event.type === 'confirm') {
        handlers.onConfirm?.({
          confirmation_id: typeof event.confirmation_id === 'string' ? event.confirmation_id : '',
          message: typeof event.message === 'string' ? event.message : '',
          summary: typeof event.summary === 'string' ? event.summary : '',
          reasoning: typeof event.reasoning === 'string' ? event.reasoning : undefined,
          operations: Array.isArray(event.operations)
            ? event.operations
                .filter((operation): operation is AgentOperationProposal => !!operation && typeof operation === 'object' && typeof operation.path === 'string' && typeof operation.operation === 'string')
                .map((operation) => ({
                  path: operation.path,
                  operation: operation.operation,
                  value: operation.value,
                  description: typeof operation.description === 'string' ? operation.description : undefined,
                  before: operation.before,
                  after: operation.after,
                }))
            : [],
          options: Array.isArray(event.options)
            ? event.options
                .filter((option): option is { id: string; label: string } => (
                  !!option && typeof option === 'object' && typeof option.id === 'string' && typeof option.label === 'string'
                ))
                .map((option) => ({ id: option.id, label: option.label }))
            : [],
        });
      } else if (event.type === 'result') {
        handlers.onResult?.(parseAgentResult(event));
      } else if (event.type === 'error' && typeof event.message === 'string') {
        handlers.onError?.(event.message);
      }
    }

    if (done) {
      break;
    }
  }
}

export async function agentChatStream(
  payload: AgentChatRequest,
  handlers: AgentChatStreamHandlers,
): Promise<void> {
  const response = await fetch(`${BASE_URL}/agent/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMessage = '请求失败';
    try {
      const data = await response.json() as { detail?: string; message?: string };
      errorMessage = data.detail || data.message || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应');
  }

  await consumeAgentStream(response, handlers);
}

export { BASE_URL };
