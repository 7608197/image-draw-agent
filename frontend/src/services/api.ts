import axios from 'axios';
import type { ReverseResponse, GenerateResponse } from '../types/reverse';

// 从环境变量读取 API 基础地址
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 60000, // 60秒超时
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

export async function generateImage(jsonFile: File): Promise<GenerateResponse> {
  const formData = new FormData();
  formData.append('json', jsonFile);

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

export { BASE_URL };
