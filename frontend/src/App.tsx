import { useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import {
  Layout,
  Typography,
  Row,
  Col,
  Card,
  Upload,
  Button,
  message,
  Alert,
  Spin,
  Tag,
  Collapse,
  Tabs,
  List,
  Space,
  Divider,
  Form,
  Select,
  InputNumber,
  Input,
  Switch,
  Modal,
  Slider,
} from 'antd';
import {
  CopyOutlined,
  DeleteOutlined,
  FileImageOutlined,
  ReloadOutlined,
  DownloadOutlined,
  UploadOutlined,
  PlusOutlined,
  UpOutlined,
  DownOutlined,
  EditOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { reverseImage, reverseText, generateImage, agentChatStream, agentChatConfirm, BASE_URL } from './services/api';
import type { GenerateOptions, TextReverseOptions } from './services/api';
import type { ReverseResponse, HistoryItem, GenerateResponse, StructuredPrompt, AgentMessage, AgentConfirmPayload, AgentOperationDecision } from './types/reverse';
import { compileStructuredPrompt, copyToClipboard } from './utils/prompt';

const { Header, Content } = Layout;
const { Title, Paragraph, Text } = Typography;
const { Dragger } = Upload;

function cloneStructuredPrompt(structured: StructuredPrompt): StructuredPrompt {
  const cloned = JSON.parse(JSON.stringify(structured)) as StructuredPrompt & {
    subject: {
      attributes: StructuredPrompt['subject']['attributes'] | string | null;
    };
  };

  const attributes = cloned.subject.attributes;
  if (typeof attributes === 'string') {
    cloned.subject.attributes = attributes.trim() ? [attributes] : [];
  } else if (!Array.isArray(attributes) && (!attributes || typeof attributes !== 'object')) {
    cloned.subject.attributes = [];
  }

  return cloned as StructuredPrompt;
}

function createAgentMessage(role: AgentMessage['role'], content: string): AgentMessage {
  return {
    role,
    content,
    ts: Date.now(),
  };
}

function appendAgentMessage(setter: Dispatch<SetStateAction<AgentMessage[]>>, role: AgentMessage['role'], content: string) {
  setter((current) => [...current, createAgentMessage(role, content)]);
}

function formatPreviewValue(value: unknown): string {
  if (value === undefined) return '未提供';
  if (value === null) return 'null';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function App() {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReverseResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  const [genJsonFile, setGenJsonFile] = useState<File | null>(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genResult, setGenResult] = useState<GenerateResponse | null>(null);
  const [genJsonPreview, setGenJsonPreview] = useState<string>('');
  const [genMode, setGenMode] = useState<'sd' | 'gemini' | 'proxy' | 'default'>('default');
  const [genScreenshotMode, setGenScreenshotMode] = useState(false);
  const [genStylePreset, setGenStylePreset] = useState<'photoreal' | 'anime' | 'watercolor' | 'cyberpunk' | 'ink' | undefined>(undefined);
  const [genSeedLocked, setGenSeedLocked] = useState(false);
  const [genSeed, setGenSeed] = useState<number | null>(null);
  const [genSteps, setGenSteps] = useState<number>(30);
  const [genCfg, setGenCfg] = useState<number>(7);
  const [genSize, setGenSize] = useState<string>('512x512');
  const [genSampler, setGenSampler] = useState<string>('DPM++ 2M Karras');
  const [genNegativePrompt, setGenNegativePrompt] = useState<string>('');
  const [genStrictJson, setGenStrictJson] = useState<boolean>(false);
  const [textReverseOpen, setTextReverseOpen] = useState(false);
  const [textReverseLoading, setTextReverseLoading] = useState(false);
  const [textReverseInput, setTextReverseInput] = useState('');
  const [activeTab, setActiveTab] = useState<'reverse' | 'generate'>('reverse');
  const [editableStructured, setEditableStructured] = useState<StructuredPrompt | null>(null);
  const [structuredEditMode, setStructuredEditMode] = useState(false);
  const [agentMessages, setAgentMessages] = useState<AgentMessage[]>([]);
  const [agentInput, setAgentInput] = useState('');
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState('');
  const [agentPendingConfirm, setAgentPendingConfirm] = useState<AgentConfirmPayload | null>(null);
  const [agentConfirmLoading, setAgentConfirmLoading] = useState(false);
  const [agentOperationDecisions, setAgentOperationDecisions] = useState<Record<number, AgentOperationDecision>>({});
  const [agentOtherInput, setAgentOtherInput] = useState('');
  const [agentUndoStack, setAgentUndoStack] = useState<StructuredPrompt[]>([]);
  const [agentInitialStructured, setAgentInitialStructured] = useState<StructuredPrompt | null>(null);

  // 上传配置
  const uploadProps: UploadProps = {
    name: 'image',
    multiple: false,
    accept: 'image/jpeg,image/png,image/webp',
    maxCount: 1,
    beforeUpload: (file) => {
      const isValidType = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type);
      if (!isValidType) {
        message.error('只支持 JPG/PNG/WEBP 格式的图片！');
        return Upload.LIST_IGNORE;
      }
      const isLt10M = file.size / 1024 / 1024 < 10;
      if (!isLt10M) {
        message.error('图片大小不能超过 10MB！');
        return Upload.LIST_IGNORE;
      }

      // 保存文件
      setImageFile(file);

      // 生成预览 URL
      const url = URL.createObjectURL(file);
      setImagePreviewUrl(url);

      // 清空之前的结果
      setResult(null);
      setEditableStructured(null);
      setStructuredEditMode(false);
      setAgentMessages([]);
      setAgentInput('');
      setAgentError('');
      setAgentPendingConfirm(null);
      setAgentConfirmLoading(false);
      setAgentOperationDecisions({});
      setAgentOtherInput('');
      setAgentUndoStack([]);
      setAgentInitialStructured(null);

      message.success(`已选择图片：${file.name}`);

      // 阻止自动上传
      return false;
    },
    onRemove: () => {
      handleClear();
    },
  };

  const genUploadProps: UploadProps = {
    name: 'json',
    multiple: false,
    accept: 'application/json',
    maxCount: 1,
    beforeUpload: async (file) => {
      if (!file.name.toLowerCase().endsWith('.json')) {
        message.error('只支持 JSON 文件');
        return Upload.LIST_IGNORE;
      }

      setGenJsonFile(file);
      setGenResult(null);

      try {
        const text = await file.text();
        setGenJsonPreview(text);
        message.success(`已选择 JSON：${file.name}`);
      } catch (error) {
        message.error('读取 JSON 失败');
      }

      return false;
    },
    onRemove: () => {
      setGenJsonFile(null);
      setGenJsonPreview('');
      setGenResult(null);
    },
  };

  // 清空选择
  const handleClear = () => {
    setImageFile(null);
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
    }
    setImagePreviewUrl('');
    setResult(null);
    setEditableStructured(null);
    setStructuredEditMode(false);
    setAgentMessages([]);
    setAgentInput('');
    setAgentError('');
    setAgentPendingConfirm(null);
    setAgentConfirmLoading(false);
    setAgentOperationDecisions({});
    setAgentOtherInput('');
    setAgentUndoStack([]);
    setAgentInitialStructured(null);
    setAgentLoading(false);
  };

  const handleGenClear = () => {
    setGenJsonFile(null);
    setGenJsonPreview('');
    setGenResult(null);
    setGenSeedLocked(false);
    setGenSeed(null);
    setGenNegativePrompt('');
  };

  // 开始反推
  const handleReverse = async () => {
    if (!imageFile) {
      message.warning('请先选择一张图片！');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const data = await reverseImage(imageFile);
      setResult(data);
      setEditableStructured(cloneStructuredPrompt(data.structured));
      setStructuredEditMode(false);
      setAgentInitialStructured(cloneStructuredPrompt(data.structured));
      setAgentUndoStack([]);
      setAgentMessages([
        createAgentMessage('system', '已载入当前图片的结构化提示词，你可以直接描述想修改的内容。'),
      ]);
      setAgentError('');
      setAgentPendingConfirm(null);
      setAgentConfirmLoading(false);
      setAgentOperationDecisions({});
      setAgentOtherInput('');
      message.success('识别成功！');

      // 添加到历史记录
      const historyItem: HistoryItem = {
        id: `${Date.now()}-${Math.random()}`,
        imageUrl: imagePreviewUrl,
        result: data,
        timestamp: Date.now(),
      };

      setHistory((prev) => [historyItem, ...prev].slice(0, 10)); // 只保留最近 10 条
    } catch (error) {
      message.error(`识别失败：${error instanceof Error ? error.message : '未知错误'}`);
      console.error('识别错误:', error);
    } finally {
      setLoading(false);
    }
  };

  const parseGenerateJson = (text: string) => {
    let payload: { prompt?: string; caption?: string; structured?: unknown };
    try {
      payload = JSON.parse(text) as { prompt?: string; caption?: string; structured?: unknown };
    } catch (error) {
      throw new Error('JSON 解析失败，请检查格式');
    }

    if (!payload.prompt && !payload.caption && !payload.structured) {
      throw new Error('JSON 中必须包含 prompt、caption 或 structured 字段');
    }

    return payload;
  };

  const handleGenerate = async () => {
    if (!genJsonFile) {
      message.warning('请上传 JSON 文件');
      return;
    }

    setGenLoading(true);
    setGenResult(null);

    try {
      const text = genJsonPreview || (await genJsonFile.text());
      parseGenerateJson(text);

      const options: GenerateOptions = {
        mode: genMode,
        style_preset: genStylePreset,
        steps: genSteps,
        cfg: genCfg,
        size: genSize,
        sampler: genSampler,
        strict_json: genStrictJson,
      };
      if (genSeedLocked && genSeed !== null) {
        options.seed = genSeed;
      }
      if (genNegativePrompt.trim()) {
        options.negative_prompt = genNegativePrompt.trim();
      }

      const data = await generateImage(genJsonFile, options);
      setGenResult(data);
      message.success('生成成功！');
    } catch (error) {
      message.error(`生成失败：${error instanceof Error ? error.message : '未知错误'}`);
      console.error('生成错误:', error);
    } finally {
      setGenLoading(false);
    }
  };

  const handleTextReverse = async () => {
    const normalizedInput = textReverseInput.trim();
    if (!normalizedInput) {
      message.warning('请输入自然语言描述');
      return;
    }

    setTextReverseOpen(false);
    setTextReverseLoading(true);
    setResult(null);

    try {
      const options: TextReverseOptions = {
        params: {
          size: genSize,
          steps: genSteps,
          cfg: genCfg,
          sampler: genSampler,
          seed: genSeedLocked ? genSeed : null,
        },
      };
      const data = await reverseText(normalizedInput, options);
      setResult(data);
      setEditableStructured(cloneStructuredPrompt(data.structured));
      setStructuredEditMode(false);
      setAgentInitialStructured(cloneStructuredPrompt(data.structured));
      setAgentUndoStack([]);
      setAgentMessages([
        createAgentMessage('system', '已载入结构化提示词，你可以继续通过 Agent 修改内容。'),
      ]);
      setAgentError('');
      setAgentPendingConfirm(null);
      setAgentConfirmLoading(false);
      setAgentOperationDecisions({});
      setAgentOtherInput('');
      const payload = {
        caption: data.caption,
        prompt: data.prompt,
        structured: data.structured,
      };
      const text = JSON.stringify(payload, null, 2);
      const file = new File([text], `reverse-${data.id}.json`, { type: 'application/json' });
      setGenJsonFile(file);
      setGenJsonPreview(text);
      setTextReverseInput('');
      message.success('结构化成功！');
    } catch (error) {
      setTextReverseOpen(true);
      message.error(`结构化失败：${error instanceof Error ? error.message : '未知错误'}`);
      console.error('文本结构化错误:', error);
    } finally {
      setTextReverseLoading(false);
    }
  };

  const handleUseForGenerate = async () => {
    if (!result) return;
    const structured = editableStructured ?? result.structured;
    const compiled = compileStructuredPrompt(structured);
    const payload = {
      caption: result.caption,
      prompt: compiled.positive,
      structured,
    };
    const text = JSON.stringify(payload, null, 2);
    const file = new File([text], `reverse-${result.id}.json`, { type: 'application/json' });
    setGenJsonFile(file);
    setGenJsonPreview(text);
    message.success('已回填到生成流程，请切换到“文生图”继续生成');
  };

  // 复制文本
  const handleCopy = async (text: string, label: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      message.success(`${label} 已复制到剪贴板`);
    } else {
      message.error('复制失败，请手动复制');
    }
  };

  // 复制结构化 prompt
  const handleCopyStructured = async () => {
    const structured = editableStructured ?? result?.structured;
    if (!structured) return;

    const compiled = compileStructuredPrompt(structured);
    const text = compiled.negative
      ? `正向提示词：\n${compiled.positive}\n\n负向提示词：\n${compiled.negative}`
      : compiled.positive;

    await handleCopy(text, '结构化提示词');
  };

  const handleDownload = (content: string, filename: string, type = 'text/plain') => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleDownloadJson = () => {
    const structured = editableStructured ?? result?.structured;
    if (!result || !structured) return;
    const compiled = compileStructuredPrompt(structured);
    const payload = {
      ...result,
      prompt: compiled.positive,
      structured,
    };
    handleDownload(JSON.stringify(payload, null, 2), `reverse-${result.id}.json`, 'application/json');
  };

  const handleDownloadTxt = () => {
    const structured = editableStructured ?? result?.structured;
    if (!result || !structured) return;
    const compiled = compileStructuredPrompt(structured);
    const text = [
      `Caption:\n${result.caption}`,
      `\nPositive prompt:\n${compiled.positive}`,
      `\nNegative prompt:\n${compiled.negative || '无'}`,
      `\nStructured JSON:\n${JSON.stringify(structured, null, 2)}`,
    ].join('\n');
    handleDownload(text, `reverse-${result.id}.txt`);
  };

  const handleDownloadGenJson = () => {
    if (!genResult) return;
    handleDownload(JSON.stringify(genResult, null, 2), `generate-${genResult.id}.json`, 'application/json');
  };

  const updateEditableStructured = (updater: (current: StructuredPrompt) => StructuredPrompt) => {
    setEditableStructured((current) => {
      if (!current) return current;
      return updater(cloneStructuredPrompt(current));
    });
  };

  const moveListItem = <T,>(items: T[], index: number, direction: -1 | 1) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= items.length) return items;
    const nextItems = [...items];
    const [item] = nextItems.splice(index, 1);
    nextItems.splice(nextIndex, 0, item);
    return nextItems;
  };

  const updateStringList = (section: 'scene' | 'style' | 'tech', field: string, nextItems: string[]) => {
    updateEditableStructured((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [field]: nextItems,
      },
    }));
  };

  const updateSubjectEntities = (nextItems: string[]) => {
    updateEditableStructured((current) => ({
      ...current,
      subject: {
        ...current.subject,
        entities: nextItems,
      },
    }));
  };

  const updateSubjectAttributeList = (nextItems: string[]) => {
    updateEditableStructured((current) => ({
      ...current,
      subject: {
        ...current.subject,
        attributes: nextItems,
      },
    }));
  };

  const updateSubjectAttributeMap = (key: string, value: string, nextKey?: string) => {
    updateEditableStructured((current) => {
      const source = Array.isArray(current.subject.attributes) ? {} : current.subject.attributes;
      const entries = Object.entries(source as Record<string, string>);
      const updated = Object.fromEntries(
        entries.map(([entryKey, entryValue]) => {
          if (entryKey !== key) return [entryKey, entryValue];
          return [nextKey ?? key, value];
        }),
      );
      return {
        ...current,
        subject: {
          ...current.subject,
          attributes: updated,
        },
      };
    });
  };

  const addSubjectAttributeMap = () => {
    updateEditableStructured((current) => {
      const source = Array.isArray(current.subject.attributes) ? {} : current.subject.attributes;
      return {
        ...current,
        subject: {
          ...current.subject,
          attributes: {
            ...(source as Record<string, string>),
            [`attribute_${Date.now()}`]: '',
          },
        },
      };
    });
  };

  const removeSubjectAttributeMap = (key: string) => {
    updateEditableStructured((current) => {
      const source = Array.isArray(current.subject.attributes) ? {} : current.subject.attributes;
      const nextEntries = Object.entries(source as Record<string, string>).filter(([entryKey]) => entryKey !== key);
      return {
        ...current,
        subject: {
          ...current.subject,
          attributes: Object.fromEntries(nextEntries),
        },
      };
    });
  };

  const updateNegativeTerms = (nextItems: string[]) => {
    updateEditableStructured((current) => ({
      ...current,
      negative: {
        ...current.negative,
        terms: nextItems,
      },
    }));
  };

  const updateNegativeTermWeights = (updater: (items: Array<{ term: string; weight: number }>) => Array<{ term: string; weight: number }>) => {
    updateEditableStructured((current) => ({
      ...current,
      negative: {
        ...current.negative,
        term_weights: updater([...current.negative.term_weights]),
      },
    }));
  };

  const renderStringListEditor = (
    label: string,
    items: string[],
    onChange: (nextItems: string[]) => void,
    color?: string,
  ) => (
    <Card type="inner" size="small" title={label}>
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {items.map((item, index) => (
          <Space key={`${label}-${index}`} style={{ width: '100%' }} align="start">
            <Input
              value={item}
              onChange={(e) => {
                const nextItems = [...items];
                nextItems[index] = e.target.value;
                onChange(nextItems);
              }}
              placeholder={`输入${label}`}
            />
            <Button icon={<UpOutlined />} onClick={() => onChange(moveListItem(items, index, -1))} disabled={index === 0} />
            <Button icon={<DownOutlined />} onClick={() => onChange(moveListItem(items, index, 1))} disabled={index === items.length - 1} />
            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}
            />
          </Space>
        ))}
        <Space wrap>
          {items.length ? items.map((item, index) => <Tag key={`${label}-tag-${index}`} color={color}>{item}</Tag>) : <Text type="secondary">暂无词条</Text>}
        </Space>
        <Button type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...items, ''])}>
          添加{label}
        </Button>
      </Space>
    </Card>
  );

  const compiledStructuredPrompt = compileStructuredPrompt(editableStructured ?? result?.structured);

  const handleAgentUndo = () => {
    const previousPrompt = agentUndoStack[agentUndoStack.length - 1];
    if (!previousPrompt) {
      message.info('没有可撤销的修改');
      return;
    }

    setEditableStructured(cloneStructuredPrompt(previousPrompt));
    setAgentUndoStack((current) => current.slice(0, -1));
    appendAgentMessage(setAgentMessages, 'system', '已撤销上一步 Agent 修改。');
  };

  const handleAgentRestoreInitial = () => {
    if (!agentInitialStructured) {
      message.info('当前没有可恢复的初始状态');
      return;
    }

    setEditableStructured(cloneStructuredPrompt(agentInitialStructured));
    setAgentUndoStack([]);
    appendAgentMessage(setAgentMessages, 'system', '已恢复到初始结构化提示词。');
  };

  // 查看历史记录
  const handleViewHistory = (item: HistoryItem) => {
    setImagePreviewUrl(item.imageUrl);
    setResult(item.result);
    setEditableStructured(cloneStructuredPrompt(item.result.structured));
    setAgentInitialStructured(cloneStructuredPrompt(item.result.structured));
    setAgentUndoStack([]);
    setStructuredEditMode(false);
    setAgentMessages([
      createAgentMessage('system', '已载入历史记录，你可以继续修改当前结构化提示词。'),
    ]);
    setAgentInput('');
    setAgentError('');
    setAgentPendingConfirm(null);
    setAgentConfirmLoading(false);
    message.info('已加载历史记录');
  };

  const handleAgentSubmit = async () => {
    if (agentLoading || agentConfirmLoading || agentPendingConfirm) {
      return;
    }

    const userInput = agentInput.trim();
    const currentPrompt = editableStructured ?? result?.structured;

    if (!userInput) {
      message.warning('请输入要修改的内容');
      return;
    }

    if (!currentPrompt) {
      message.warning('请先完成图片识别或文本结构化');
      return;
    }

    appendAgentMessage(setAgentMessages, 'user', userInput);
    setAgentInput('');
    setAgentLoading(true);
    setAgentError('');
    setAgentPendingConfirm(null);

    try {
      await agentChatStream(
        {
          user_input: userInput,
          current_prompt: currentPrompt,
        },
        {
          onStatus: (statusMessage) => {
            appendAgentMessage(setAgentMessages, 'system', statusMessage);
          },
          onConfirm: (payload) => {
            setAgentPendingConfirm(payload);
            setAgentOperationDecisions(Object.fromEntries(payload.operations.map((_, index) => [index, 'yes'])) as Record<number, AgentOperationDecision>);
            setAgentOtherInput('');
            appendAgentMessage(setAgentMessages, 'assistant', `${payload.message}\n修改摘要：${payload.summary}`);
          },
          onResult: (response) => {
            setEditableStructured(cloneStructuredPrompt(response.updated_prompt));
            setAgentPendingConfirm(null);
            appendAgentMessage(setAgentMessages, 'assistant', response.message);
          },
          onError: (errorMessage) => {
            setAgentError(errorMessage);
            setAgentPendingConfirm(null);
            appendAgentMessage(setAgentMessages, 'system', `请求失败：${errorMessage}`);
          },
        },
      );
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setAgentError(errorMessage);
      setAgentPendingConfirm(null);
      appendAgentMessage(setAgentMessages, 'system', `请求失败：${errorMessage}`);
      message.error(`Agent 请求失败：${errorMessage}`);
    } finally {
      setAgentLoading(false);
    }
  };

  const handleAgentConfirm = async (choice: 'accept_all' | 'submit_selection' | 'other' | 'cancel') => {
    if (!agentPendingConfirm || agentConfirmLoading) {
      return;
    }

    const selectedOption = agentPendingConfirm.options.find((option) => option.id === choice);
    const label = selectedOption?.label || choice;
    const currentPrompt = editableStructured ?? result?.structured;
    if (!currentPrompt) {
      message.warning('当前没有可操作的结构化提示词');
      return;
    }

    const selectedOperationIndexes = Object.entries(agentOperationDecisions)
      .filter(([, decision]) => decision === 'yes')
      .map(([index]) => Number(index))
      .sort((a, b) => a - b);

    const payload = choice === 'accept_all'
      ? {
          confirmation_id: agentPendingConfirm.confirmation_id,
          choice,
          mode: 'accept_all' as const,
        }
      : choice === 'submit_selection'
        ? {
            confirmation_id: agentPendingConfirm.confirmation_id,
            choice,
            mode: 'multi' as const,
            selected_operation_indexes: selectedOperationIndexes,
          }
        : choice === 'other'
          ? {
              confirmation_id: agentPendingConfirm.confirmation_id,
              choice,
              mode: 'custom_prompt' as const,
              custom_text: agentOtherInput.trim(),
            }
          : {
              confirmation_id: agentPendingConfirm.confirmation_id,
              choice,
              mode: 'cancel' as const,
            };

    appendAgentMessage(setAgentMessages, 'user', `选择：${label}`);
    setAgentConfirmLoading(true);
    setAgentError('');

    try {
      await agentChatConfirm(payload, {
        onStatus: (statusMessage) => {
          appendAgentMessage(setAgentMessages, 'system', statusMessage);
        },
        onConfirm: (nextPayload) => {
          setAgentPendingConfirm(nextPayload);
          setAgentOperationDecisions(Object.fromEntries(nextPayload.operations.map((_, index) => [index, 'yes'])) as Record<number, AgentOperationDecision>);
          setAgentOtherInput('');
          appendAgentMessage(setAgentMessages, 'assistant', `${nextPayload.message}\n修改摘要：${nextPayload.summary}`);
        },
        onResult: (response) => {
          if (choice !== 'cancel') {
            setAgentUndoStack((current) => [...current, cloneStructuredPrompt(currentPrompt)]);
          }
          setEditableStructured(cloneStructuredPrompt(response.updated_prompt));
          setAgentPendingConfirm(null);
          setAgentOperationDecisions({});
          setAgentOtherInput('');
          appendAgentMessage(setAgentMessages, 'assistant', response.message);
        },
        onError: (errorMessage) => {
          setAgentError(errorMessage);
          setAgentPendingConfirm(null);
          appendAgentMessage(setAgentMessages, 'system', `确认失败：${errorMessage}`);
        },
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setAgentError(errorMessage);
      setAgentPendingConfirm(null);
      appendAgentMessage(setAgentMessages, 'system', `确认失败：${errorMessage}`);
      message.error(`确认失败：${errorMessage}`);
    } finally {
      setAgentConfirmLoading(false);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      {/* 顶部标题 */}
      <Header style={{ background: '#fff', padding: '0 24px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <Title level={2} style={{ margin: '16px 0' }}>
          图像服务（图生文 / 文生图）
        </Title>
      </Header>

      <Content style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', width: '100%' }}>
        <Modal
          title="自然语言结构化提示词"
          open={textReverseOpen}
          onOk={handleTextReverse}
          onCancel={() => setTextReverseOpen(false)}
          confirmLoading={textReverseLoading}
          okText="开始结构化"
          cancelText="取消"
        >
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Paragraph type="secondary">
              输入自然语言描述，系统会先规范文本，再生成结构化提示词对象。
            </Paragraph>
            <Input.TextArea
              rows={6}
              value={textReverseInput}
              onChange={(e) => setTextReverseInput(e.target.value)}
              placeholder="例如：一个站在雨夜街头的赛博朋克少女，霓虹灯，电影感，近景，高清细节"
            />
          </Space>
        </Modal>

        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'reverse' | 'generate')}
          items={[
            {
              key: 'reverse',
              label: '图生文（提示词反推）',
              children: (
                <>
                  <Alert
                    message="功能说明"
                    description="上传图片后，系统将自动分析图像内容，生成自然语言描述和结构化提示词，可直接用于文生图模型。"
                    type="info"
                    showIcon
                    style={{ marginBottom: '24px' }}
                  />

                  <Row gutter={genScreenshotMode ? 16 : 24}>
                    <Col xs={24} lg={genScreenshotMode ? 9 : 10}>
                      <Card title="图片上传" bordered={false}>
                        <Space style={{ width: '100%', marginBottom: '16px' }} wrap>
                          <Button type="dashed" onClick={() => setTextReverseOpen(true)}>
                            自然语言结构化
                          </Button>
                        </Space>

                        <Dragger {...uploadProps} showUploadList={false}>
                          <p className="ant-upload-drag-icon">
                            <FileImageOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
                          </p>
                          <p className="ant-upload-text">点击或拖拽图片到此区域上传</p>
                          <p className="ant-upload-hint">
                            支持 JPG、PNG、WEBP 格式，大小不超过 10MB
                          </p>
                        </Dragger>

                        {imagePreviewUrl && (
                          <div style={{ marginTop: '16px' }}>
                            <Divider>图片预览</Divider>
                            <img
                              src={imagePreviewUrl}
                              alt="预览"
                              style={{
                                width: '100%',
                                maxHeight: '400px',
                                objectFit: 'contain',
                                borderRadius: '8px',
                                border: '1px solid #d9d9d9',
                              }}
                            />
                            <Space style={{ marginTop: '12px', width: '100%' }}>
                              <Button
                                type="primary"
                                icon={<ReloadOutlined />}
                                onClick={handleReverse}
                                loading={loading}
                                block
                              >
                                开始反推/识别
                              </Button>
                              <Button
                                icon={<DeleteOutlined />}
                                onClick={handleClear}
                                disabled={loading}
                              >
                                清空
                              </Button>
                            </Space>

                            <Card
                              type="inner"
                              title="Agent CLI"
                              size="small"
                              style={{
                                marginTop: '16px',
                                background: '#f7fbff',
                                borderColor: '#d6e4ff',
                                boxShadow: '0 6px 18px rgba(24, 144, 255, 0.08)',
                              }}
                              headStyle={{
                                background: 'linear-gradient(90deg, #e6f4ff 0%, #f7fbff 100%)',
                                color: '#1677ff',
                                borderBottomColor: '#d6e4ff',
                                fontFamily: 'monospace',
                                fontWeight: 600,
                              }}
                              bodyStyle={{ padding: '12px' }}
                            >
                              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                                <div
                                  style={{
                                    minHeight: '180px',
                                    maxHeight: '280px',
                                    overflowY: 'auto',
                                    padding: '12px',
                                    borderRadius: '8px',
                                    background: '#ffffff',
                                    border: '1px solid #d6e4ff',
                                  }}
                                >
                                  {agentMessages.length ? (
                                    <List
                                      dataSource={agentMessages}
                                      split={false}
                                      renderItem={(item) => {
                                        const roleColor = item.role === 'user'
                                          ? '#1677ff'
                                          : item.role === 'assistant'
                                            ? '#52c41a'
                                            : '#fa8c16';
                                        const badgeBackground = item.role === 'user'
                                          ? '#e6f4ff'
                                          : item.role === 'assistant'
                                            ? '#f6ffed'
                                            : '#fff7e6';
                                        return (
                                          <List.Item style={{ display: 'block', padding: '0 0 12px', border: 'none' }}>
                                            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                                              <span
                                                style={{
                                                  minWidth: '72px',
                                                  padding: '2px 8px',
                                                  borderRadius: '999px',
                                                  background: badgeBackground,
                                                  color: roleColor,
                                                  fontFamily: 'monospace',
                                                  fontSize: '12px',
                                                  textAlign: 'center',
                                                }}
                                              >
                                                {item.role}
                                              </span>
                                              <div
                                                style={{
                                                  flex: 1,
                                                  fontFamily: 'monospace',
                                                  color: '#262626',
                                                  whiteSpace: 'pre-wrap',
                                                  wordBreak: 'break-word',
                                                  lineHeight: 1.6,
                                                }}
                                              >
                                                {item.content}
                                              </div>
                                            </div>
                                          </List.Item>
                                        );
                                      }}
                                    />
                                  ) : (
                                    <Text style={{ color: '#8c8c8c', fontFamily: 'monospace' }}>
                                      等待识别结果后，可在这里输入自然语言修改指令。
                                    </Text>
                                  )}
                                </div>

                                {agentPendingConfirm && (
                                  <Card
                                    type="inner"
                                    size="small"
                                    title="需要确认"
                                    styles={{ body: { padding: '12px' } }}
                                  >
                                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                                      <Text style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                        {agentPendingConfirm.message}
                                      </Text>
                                      <Text type="secondary" style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                        修改摘要：{agentPendingConfirm.summary}
                                        {agentPendingConfirm.reasoning ? `\n思考：${agentPendingConfirm.reasoning}` : ''}
                                      </Text>
                                      <Space direction="vertical" style={{ width: '100%' }} size="small">
                                        {agentPendingConfirm.operations.map((operation, index) => (
                                          <Card key={`${operation.path}-${index}`} size="small" type="inner">
                                            <Space direction="vertical" style={{ width: '100%' }} size="small">
                                              <Text strong style={{ fontFamily: 'monospace' }}>
                                                {index + 1}. {operation.path} ({operation.operation})
                                              </Text>
                                              <Text style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                                {operation.description || '未提供详细说明'}
                                              </Text>
                                              <Text type="secondary" style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                                Before:\n{formatPreviewValue(operation.before)}
                                              </Text>
                                              <Text type="secondary" style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                                After:\n{formatPreviewValue(operation.after)}
                                              </Text>
                                              <Space wrap>
                                                <Button
                                                  type={agentOperationDecisions[index] !== 'no' ? 'primary' : 'default'}
                                                  size="small"
                                                  onClick={() => setAgentOperationDecisions((current) => ({ ...current, [index]: 'yes' }))}
                                                  disabled={agentConfirmLoading}
                                                >
                                                  Yes
                                                </Button>
                                                <Button
                                                  type={agentOperationDecisions[index] === 'no' ? 'primary' : 'default'}
                                                  danger={agentOperationDecisions[index] === 'no'}
                                                  size="small"
                                                  onClick={() => setAgentOperationDecisions((current) => ({ ...current, [index]: 'no' }))}
                                                  disabled={agentConfirmLoading}
                                                >
                                                  No
                                                </Button>
                                              </Space>
                                            </Space>
                                          </Card>
                                        ))}
                                      </Space>
                                      <Input.TextArea
                                        value={agentOtherInput}
                                        onChange={(e) => setAgentOtherInput(e.target.value)}
                                        placeholder="Other：输入补充要求，重新生成一版修改方案"
                                        autoSize={{ minRows: 2, maxRows: 4 }}
                                        disabled={agentConfirmLoading}
                                        style={{ fontFamily: 'monospace' }}
                                      />
                                      <Space wrap>
                                        <Button
                                          type="primary"
                                          onClick={() => void handleAgentConfirm('accept_all')}
                                          loading={agentConfirmLoading}
                                          disabled={agentConfirmLoading}
                                        >
                                          Accept all
                                        </Button>
                                        <Button
                                          onClick={() => void handleAgentConfirm('submit_selection')}
                                          loading={agentConfirmLoading}
                                          disabled={agentConfirmLoading}
                                        >
                                          提交选择
                                        </Button>
                                        <Button
                                          onClick={() => void handleAgentConfirm('other')}
                                          loading={agentConfirmLoading}
                                          disabled={agentConfirmLoading || !agentOtherInput.trim()}
                                        >
                                          Other
                                        </Button>
                                        <Button
                                          danger
                                          onClick={() => void handleAgentConfirm('cancel')}
                                          loading={agentConfirmLoading}
                                          disabled={agentConfirmLoading}
                                        >
                                          Cancel
                                        </Button>
                                      </Space>
                                    </Space>
                                  </Card>
                                )}

                                {agentError && (
                                  <Alert
                                    message="Agent 错误"
                                    description={agentError}
                                    type="error"
                                    showIcon
                                  />
                                )}

                                <Input.TextArea
                                  value={agentInput}
                                  onChange={(e) => setAgentInput(e.target.value)}
                                  placeholder="例如：把主体改成老虎，风格更偏油画"
                                  autoSize={{ minRows: 3, maxRows: 6 }}
                                  disabled={agentLoading || agentConfirmLoading || !!agentPendingConfirm || loading || textReverseLoading || !(editableStructured ?? result?.structured)}
                                  style={{
                                    fontFamily: 'monospace',
                                    background: '#ffffff',
                                    color: '#262626',
                                    borderColor: '#91caff',
                                  }}
                                  onPressEnter={(e) => {
                                    if (!e.shiftKey) {
                                      e.preventDefault();
                                      void handleAgentSubmit();
                                    }
                                  }}
                                />

                                <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
                                  <Text
                                    style={{
                                      color: agentLoading || agentConfirmLoading || agentPendingConfirm ? '#1677ff' : '#8c8c8c',
                                      fontFamily: 'monospace',
                                    }}
                                  >
                                    {agentConfirmLoading
                                      ? '正在提交确认请求'
                                      : agentPendingConfirm
                                        ? '等待你的确认'
                                        : editableStructured ?? result?.structured
                                          ? '当前结构化提示词已就绪'
                                          : '请先完成识别'}
                                  </Text>
                                  <Space wrap>
                                    <Button
                                      icon={<UndoOutlined />}
                                      onClick={handleAgentUndo}
                                      disabled={!agentUndoStack.length || agentLoading || agentConfirmLoading}
                                    >
                                      撤销上一步
                                    </Button>
                                    <Button
                                      onClick={handleAgentRestoreInitial}
                                      disabled={!agentInitialStructured || agentLoading || agentConfirmLoading}
                                    >
                                      恢复初始
                                    </Button>
                                    <Button
                                      type="primary"
                                      onClick={handleAgentSubmit}
                                      loading={agentLoading}
                                      disabled={agentLoading || agentConfirmLoading || !!agentPendingConfirm || loading || textReverseLoading || !(editableStructured ?? result?.structured)}
                                    >
                                      发送
                                    </Button>
                                  </Space>
                                </Space>
                              </Space>
                            </Card>
                          </div>
                        )}
                      </Card>
                    </Col>

                    <Col xs={24} lg={14}>
                      <Card title="识别结果" bordered={false}>
                        {(loading || textReverseLoading) && (
                          <div style={{ textAlign: 'center', padding: '48px' }}>
                            <Spin size="large" />
                            <Paragraph style={{ marginTop: '16px' }}>
                              {textReverseLoading ? '正在结构化中，请稍候...' : '正在识别中，请稍候...'}
                            </Paragraph>
                          </div>
                        )}

                        {!loading && !textReverseLoading && !result && (
                          <Alert
                            message="等待识别"
                            description="请上传图片并点击'开始反推/识别'按钮"
                            type="warning"
                            showIcon
                          />
                        )}

                        {!loading && !textReverseLoading && result && (
                          <Space direction="vertical" style={{ width: '100%' }} size="large">
                            <Card
                              type="inner"
                              title="自然语言描述 (Caption)"
                              extra={
                                <Button
                                  type="link"
                                  icon={<CopyOutlined />}
                                  onClick={() => handleCopy(result.caption, 'Caption')}
                                >
                                  复制
                                </Button>
                              }
                            >
                              <Paragraph>{result.caption || '未返回该字段'}</Paragraph>
                            </Card>

                            {(result.prompt || compiledStructuredPrompt.positive) && (
                              <Card
                                type="inner"
                                title="推荐 Prompt"
                                extra={
                                  <Button
                                    type="link"
                                    icon={<CopyOutlined />}
                                    onClick={() => handleCopy(compiledStructuredPrompt.positive || result.prompt, 'Prompt')}
                                  >
                                    复制
                                  </Button>
                                }
                              >
                                <Paragraph style={{ fontFamily: 'monospace' }}>
                                  {compiledStructuredPrompt.positive || result.prompt}
                                </Paragraph>
                                {compiledStructuredPrompt.negative && (
                                  <Paragraph style={{ fontFamily: 'monospace', marginBottom: 0 }}>
                                    <Text strong>Negative:</Text> {compiledStructuredPrompt.negative}
                                  </Paragraph>
                                )}
                              </Card>
                            )}

                            {result && (
                              <Card type="inner" title="下载结果">
                                <Space wrap>
                                  <Button icon={<DownloadOutlined />} onClick={handleDownloadJson}>
                                    下载 JSON
                                  </Button>
                                  <Button icon={<DownloadOutlined />} onClick={handleDownloadTxt}>
                                    下载 TXT
                                  </Button>
                                  <Button type="primary" onClick={handleUseForGenerate}>
                                    用于生成
                                  </Button>
                                </Space>
                              </Card>
                            )}

                            {result.structured && editableStructured && (
                              <Card
                                type="inner"
                                title="结构化提示词 (Structured)"
                                extra={
                                  <Space wrap>
                                    <Button
                                      type={structuredEditMode ? 'primary' : 'default'}
                                      icon={<EditOutlined />}
                                      onClick={() => setStructuredEditMode((current) => !current)}
                                    >
                                      {structuredEditMode ? '退出编辑' : '编辑模式'}
                                    </Button>
                                    <Button
                                      icon={<UndoOutlined />}
                                      onClick={() => {
                                        setEditableStructured(cloneStructuredPrompt(result.structured));
                                        message.success('已重置为反推结果');
                                      }}
                                    >
                                      重置
                                    </Button>
                                    <Button
                                      type="link"
                                      icon={<CopyOutlined />}
                                      onClick={handleCopyStructured}
                                    >
                                      复制全部
                                    </Button>
                                  </Space>
                                }
                              >
                                <Space direction="vertical" style={{ width: '100%' }} size="large">
                                  <Card type="inner" size="small" title="Prompt 实时预览">
                                    <Space direction="vertical" style={{ width: '100%' }}>
                                      <div>
                                        <Text strong>Positive:</Text>
                                        <Paragraph style={{ fontFamily: 'monospace', marginBottom: 8 }}>
                                          {compiledStructuredPrompt.positive || '暂无内容'}
                                        </Paragraph>
                                      </div>
                                      <div>
                                        <Text strong>Negative:</Text>
                                        <Paragraph style={{ fontFamily: 'monospace', marginBottom: 0 }}>
                                          {compiledStructuredPrompt.negative || '无'}
                                        </Paragraph>
                                      </div>
                                    </Space>
                                  </Card>
                                  <Tabs
                                    items={[
                                      {
                                        key: 'subject',
                                        label: 'Subject (主体)',
                                        children: structuredEditMode ? (
                                          <Space direction="vertical" style={{ width: '100%' }} size="middle">
                                            <Card type="inner" size="small" title="主体信息">
                                              <Space direction="vertical" style={{ width: '100%' }}>
                                                <div>
                                                  <Text strong>Label</Text>
                                                  <Input
                                                    value={editableStructured.subject.label}
                                                    onChange={(e) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      subject: {
                                                        ...current.subject,
                                                        label: e.target.value,
                                                      },
                                                    }))}
                                                    placeholder="主体标签"
                                                  />
                                                </div>
                                                <div>
                                                  <Text strong>Count</Text>
                                                  <InputNumber
                                                    min={1}
                                                    value={editableStructured.subject.count}
                                                    onChange={(value) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      subject: {
                                                        ...current.subject,
                                                        count: value ?? undefined,
                                                      },
                                                    }))}
                                                    style={{ width: '100%' }}
                                                    placeholder="主体数量"
                                                  />
                                                </div>
                                                <div>
                                                  <Text strong>Weight</Text>
                                                  <Space style={{ width: '100%' }} direction="vertical">
                                                    <Slider
                                                      min={0.8}
                                                      max={1.2}
                                                      step={0.1}
                                                      value={editableStructured.subject.weight ?? 1}
                                                      onChange={(value) => updateEditableStructured((current) => ({
                                                        ...current,
                                                        subject: {
                                                          ...current.subject,
                                                          weight: Array.isArray(value) ? value[0] : value,
                                                        },
                                                      }))}
                                                    />
                                                    <InputNumber
                                                      min={0.8}
                                                      max={1.2}
                                                      step={0.1}
                                                      value={editableStructured.subject.weight ?? 1}
                                                      onChange={(value) => updateEditableStructured((current) => ({
                                                        ...current,
                                                        subject: {
                                                          ...current.subject,
                                                          weight: value ?? undefined,
                                                        },
                                                      }))}
                                                    />
                                                  </Space>
                                                </div>
                                              </Space>
                                            </Card>
                                            {renderStringListEditor('Entities', editableStructured.subject.entities, updateSubjectEntities, 'blue')}
                                            {Array.isArray(editableStructured.subject.attributes) ? (
                                              renderStringListEditor('Attributes', editableStructured.subject.attributes, updateSubjectAttributeList, 'cyan')
                                            ) : (
                                              <Card type="inner" size="small" title="Attributes">
                                                <Space direction="vertical" style={{ width: '100%' }} size="small">
                                                  {Object.entries(editableStructured.subject.attributes).map(([key, value]) => (
                                                    <Space key={key} style={{ width: '100%' }} align="start">
                                                      <Input
                                                        value={key}
                                                        onChange={(e) => updateSubjectAttributeMap(key, value, e.target.value)}
                                                        placeholder="属性名"
                                                      />
                                                      <Input
                                                        value={value}
                                                        onChange={(e) => updateSubjectAttributeMap(key, e.target.value)}
                                                        placeholder="属性值"
                                                      />
                                                      <Button danger icon={<DeleteOutlined />} onClick={() => removeSubjectAttributeMap(key)} />
                                                    </Space>
                                                  ))}
                                                  <Button type="dashed" icon={<PlusOutlined />} onClick={addSubjectAttributeMap}>
                                                    添加属性
                                                  </Button>
                                                </Space>
                                              </Card>
                                            )}
                                          </Space>
                                        ) : (
                                          <Space direction="vertical">
                                            <div>
                                              <Text strong>Label:</Text> {editableStructured.subject.label || '无'}
                                              {editableStructured.subject.weight && (
                                                <Text type="secondary"> (weight: {editableStructured.subject.weight.toFixed(1)})</Text>
                                              )}
                                            </div>
                                            <div>
                                              <Text strong>Entities:</Text>{' '}
                                              {editableStructured.subject.entities.length ? editableStructured.subject.entities.map((tag, idx) => <Tag key={idx} color="blue">{tag}</Tag>) : <Text type="secondary">无</Text>}
                                            </div>
                                            <div>
                                              <Text strong>Attributes:</Text>{' '}
                                              {Array.isArray(editableStructured.subject.attributes)
                                                ? (editableStructured.subject.attributes.length ? editableStructured.subject.attributes.map((tag, idx) => <Tag key={idx} color="cyan">{tag}</Tag>) : <Text type="secondary">无</Text>)
                                                : (Object.keys(editableStructured.subject.attributes).length
                                                  ? Object.entries(editableStructured.subject.attributes).map(([key, value]) => <Tag key={key} color="cyan">{key} {value}</Tag>)
                                                  : <Text type="secondary">无</Text>)}
                                            </div>
                                            <div>
                                              <Text strong>Count:</Text> {editableStructured.subject.count ?? '无'}
                                            </div>
                                          </Space>
                                        ),
                                      },
                                      {
                                        key: 'scene',
                                        label: 'Scene (场景)',
                                        children: structuredEditMode ? (
                                          <Space direction="vertical" style={{ width: '100%' }} size="middle">
                                            {renderStringListEditor('Environment', editableStructured.scene.environment, (nextItems) => updateStringList('scene', 'environment', nextItems), 'green')}
                                            {renderStringListEditor('Background', editableStructured.scene.background, (nextItems) => updateStringList('scene', 'background', nextItems), 'green')}
                                            {renderStringListEditor('Time/Weather', editableStructured.scene.time_weather, (nextItems) => updateStringList('scene', 'time_weather', nextItems), 'green')}
                                            {renderStringListEditor('Composition', editableStructured.scene.composition, (nextItems) => updateStringList('scene', 'composition', nextItems), 'green')}
                                          </Space>
                                        ) : (
                                          <Space direction="vertical">
                                            <div><Text strong>Environment:</Text> {editableStructured.scene.environment.length ? editableStructured.scene.environment.map((tag, idx) => <Tag key={idx} color="green">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Background:</Text> {editableStructured.scene.background.length ? editableStructured.scene.background.map((tag, idx) => <Tag key={idx} color="green">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Time/Weather:</Text> {editableStructured.scene.time_weather.length ? editableStructured.scene.time_weather.map((tag, idx) => <Tag key={idx} color="green">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Composition:</Text> {editableStructured.scene.composition.length ? editableStructured.scene.composition.map((tag, idx) => <Tag key={idx} color="green">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                          </Space>
                                        ),
                                      },
                                      {
                                        key: 'style',
                                        label: 'Style (风格)',
                                        children: structuredEditMode ? (
                                          <Space direction="vertical" style={{ width: '100%' }} size="middle">
                                            {renderStringListEditor('Medium', editableStructured.style.medium, (nextItems) => updateStringList('style', 'medium', nextItems), 'purple')}
                                            {renderStringListEditor('Artist Style', editableStructured.style.artist_style, (nextItems) => updateStringList('style', 'artist_style', nextItems), 'purple')}
                                            {renderStringListEditor('Aesthetic', editableStructured.style.aesthetic, (nextItems) => updateStringList('style', 'aesthetic', nextItems), 'purple')}
                                            {renderStringListEditor('Quality', editableStructured.style.quality, (nextItems) => updateStringList('style', 'quality', nextItems), 'purple')}
                                          </Space>
                                        ) : (
                                          <Space direction="vertical">
                                            <div><Text strong>Medium:</Text> {editableStructured.style.medium.length ? editableStructured.style.medium.map((tag, idx) => <Tag key={idx} color="purple">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Artist Style:</Text> {editableStructured.style.artist_style.length ? editableStructured.style.artist_style.map((tag, idx) => <Tag key={idx} color="purple">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Aesthetic:</Text> {editableStructured.style.aesthetic.length ? editableStructured.style.aesthetic.map((tag, idx) => <Tag key={idx} color="purple">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Quality:</Text> {editableStructured.style.quality.length ? editableStructured.style.quality.map((tag, idx) => <Tag key={idx} color="purple">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                          </Space>
                                        ),
                                      },
                                      {
                                        key: 'tech',
                                        label: 'Tech (技术)',
                                        children: structuredEditMode ? (
                                          <Space direction="vertical" style={{ width: '100%' }} size="middle">
                                            {renderStringListEditor('Lighting', editableStructured.tech.lighting, (nextItems) => updateStringList('tech', 'lighting', nextItems), 'orange')}
                                            {renderStringListEditor('Camera', editableStructured.tech.camera, (nextItems) => updateStringList('tech', 'camera', nextItems), 'orange')}
                                            {renderStringListEditor('Color Tone', editableStructured.tech.color_tone, (nextItems) => updateStringList('tech', 'color_tone', nextItems), 'orange')}
                                            {renderStringListEditor('Render', editableStructured.tech.render, (nextItems) => updateStringList('tech', 'render', nextItems), 'orange')}
                                          </Space>
                                        ) : (
                                          <Space direction="vertical">
                                            <div><Text strong>Lighting:</Text> {editableStructured.tech.lighting.length ? editableStructured.tech.lighting.map((tag, idx) => <Tag key={idx} color="orange">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Camera:</Text> {editableStructured.tech.camera.length ? editableStructured.tech.camera.map((tag, idx) => <Tag key={idx} color="orange">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Color Tone:</Text> {editableStructured.tech.color_tone.length ? editableStructured.tech.color_tone.map((tag, idx) => <Tag key={idx} color="orange">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Render:</Text> {editableStructured.tech.render.length ? editableStructured.tech.render.map((tag, idx) => <Tag key={idx} color="orange">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                          </Space>
                                        ),
                                      },
                                      {
                                        key: 'negative',
                                        label: 'Negative (负面)',
                                        children: structuredEditMode ? (
                                          <Space direction="vertical" style={{ width: '100%' }} size="middle">
                                            <Card type="inner" size="small" title="Negative 设置">
                                              <Space direction="vertical" style={{ width: '100%' }}>
                                                <div>
                                                  <Text strong>Severity</Text>
                                                  <Select
                                                    value={editableStructured.negative.severity}
                                                    onChange={(value) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      negative: {
                                                        ...current.negative,
                                                        severity: value,
                                                      },
                                                    }))}
                                                    options={[
                                                      { value: 'weak', label: 'weak' },
                                                      { value: 'medium', label: 'medium' },
                                                      { value: 'strong', label: 'strong' },
                                                    ]}
                                                    style={{ width: '100%' }}
                                                  />
                                                </div>
                                              </Space>
                                            </Card>
                                            <Card type="inner" size="small" title="Term Weights">
                                              <Space direction="vertical" style={{ width: '100%' }} size="small">
                                                {editableStructured.negative.term_weights.map((item, index) => (
                                                  <Space key={`negative-weight-${index}`} style={{ width: '100%' }} align="start">
                                                    <Input
                                                      value={item.term}
                                                      onChange={(e) => updateNegativeTermWeights((items) => items.map((entry, itemIndex) => itemIndex === index ? { ...entry, term: e.target.value } : entry))}
                                                      placeholder="负向词"
                                                    />
                                                    <InputNumber
                                                      min={0.1}
                                                      max={2}
                                                      step={0.1}
                                                      value={item.weight}
                                                      onChange={(value) => updateNegativeTermWeights((items) => items.map((entry, itemIndex) => itemIndex === index ? { ...entry, weight: value ?? 1 } : entry))}
                                                    />
                                                    <Button icon={<UpOutlined />} onClick={() => updateNegativeTermWeights((items) => moveListItem(items, index, -1))} disabled={index === 0} />
                                                    <Button icon={<DownOutlined />} onClick={() => updateNegativeTermWeights((items) => moveListItem(items, index, 1))} disabled={index === editableStructured.negative.term_weights.length - 1} />
                                                    <Button danger icon={<DeleteOutlined />} onClick={() => updateNegativeTermWeights((items) => items.filter((_, itemIndex) => itemIndex !== index))} />
                                                  </Space>
                                                ))}
                                                <Button
                                                  type="dashed"
                                                  icon={<PlusOutlined />}
                                                  onClick={() => updateNegativeTermWeights((items) => [...items, { term: '', weight: 1 }])}
                                                >
                                                  添加加权负向词
                                                </Button>
                                              </Space>
                                            </Card>
                                            {renderStringListEditor('Negative Terms', editableStructured.negative.terms, updateNegativeTerms, 'red')}
                                          </Space>
                                        ) : (
                                          <Space direction="vertical">
                                            <div><Text strong>Severity:</Text> {editableStructured.negative.severity || 'medium'}</div>
                                            <div><Text strong>Term Weights:</Text> {editableStructured.negative.term_weights.length ? editableStructured.negative.term_weights.map((item, idx) => <Tag key={idx} color="red">{item.term} ({item.weight.toFixed(1)})</Tag>) : <Text type="secondary">无</Text>}</div>
                                            <div><Text strong>Terms:</Text> {editableStructured.negative.terms.length ? editableStructured.negative.terms.map((tag, idx) => <Tag key={idx} color="red">{tag}</Tag>) : <Text type="secondary">无</Text>}</div>
                                          </Space>
                                        ),
                                      },
                                      {
                                        key: 'params',
                                        label: 'Params (参数)',
                                        children: structuredEditMode ? (
                                          <Form layout="vertical" size={genScreenshotMode ? 'middle' : 'small'}>
                                            <Row gutter={12}>
                                              <Col span={12}>
                                                <Form.Item label="Size">
                                                  <Input
                                                    value={editableStructured.params.size}
                                                    onChange={(e) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      params: {
                                                        ...current.params,
                                                        size: e.target.value,
                                                      },
                                                    }))}
                                                  />
                                                </Form.Item>
                                              </Col>
                                              <Col span={12}>
                                                <Form.Item label="Sampler">
                                                  <Input
                                                    value={editableStructured.params.sampler}
                                                    onChange={(e) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      params: {
                                                        ...current.params,
                                                        sampler: e.target.value,
                                                      },
                                                    }))}
                                                  />
                                                </Form.Item>
                                              </Col>
                                            </Row>
                                            <Row gutter={12}>
                                              <Col span={8}>
                                                <Form.Item label="Steps">
                                                  <InputNumber
                                                    min={1}
                                                    max={150}
                                                    value={editableStructured.params.steps}
                                                    onChange={(value) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      params: {
                                                        ...current.params,
                                                        steps: value ?? current.params.steps,
                                                      },
                                                    }))}
                                                    style={{ width: '100%' }}
                                                  />
                                                </Form.Item>
                                              </Col>
                                              <Col span={8}>
                                                <Form.Item label="CFG">
                                                  <InputNumber
                                                    min={1}
                                                    max={30}
                                                    step={0.5}
                                                    value={editableStructured.params.cfg}
                                                    onChange={(value) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      params: {
                                                        ...current.params,
                                                        cfg: value ?? current.params.cfg,
                                                      },
                                                    }))}
                                                    style={{ width: '100%' }}
                                                  />
                                                </Form.Item>
                                              </Col>
                                              <Col span={8}>
                                                <Form.Item label="Seed">
                                                  <InputNumber
                                                    min={0}
                                                    max={4294967295}
                                                    value={editableStructured.params.seed ?? null}
                                                    onChange={(value) => updateEditableStructured((current) => ({
                                                      ...current,
                                                      params: {
                                                        ...current.params,
                                                        seed: value ?? null,
                                                      },
                                                    }))}
                                                    style={{ width: '100%' }}
                                                  />
                                                </Form.Item>
                                              </Col>
                                            </Row>
                                          </Form>
                                        ) : (
                                          <Space direction="vertical">
                                            <div><Text strong>Size:</Text> {editableStructured.params.size}</div>
                                            <div><Text strong>Steps:</Text> {editableStructured.params.steps}</div>
                                            <div><Text strong>CFG:</Text> {editableStructured.params.cfg}</div>
                                            <div><Text strong>Sampler:</Text> {editableStructured.params.sampler}</div>
                                            <div><Text strong>Seed:</Text> {editableStructured.params.seed ?? '无'}</div>
                                          </Space>
                                        ),
                                      },
                                    ]}
                                  />
                                </Space>
                              </Card>
                            )}

                            <Collapse
                              items={[
                                {
                                  key: '1',
                                  label: '完整结果 JSON（当前可下载版本）',
                                  children: (
                                    <pre
                                      style={{
                                        background: '#f5f5f5',
                                        padding: '12px',
                                        borderRadius: '4px',
                                        overflow: 'auto',
                                        maxHeight: '300px',
                                      }}
                                    >
                                      {JSON.stringify({
                                        ...result,
                                        prompt: compiledStructuredPrompt.positive,
                                        structured: editableStructured ?? result.structured,
                                      }, null, 2)}
                                    </pre>
                                  ),
                                },
                                {
                                  key: '2',
                                  label: '结构化提示词对象（详细可视化）',
                                  children: (
                                    <pre
                                      style={{
                                        background: '#f5f5f5',
                                        padding: '12px',
                                        borderRadius: '4px',
                                        overflow: 'auto',
                                        maxHeight: '300px',
                                      }}
                                    >
                                      {JSON.stringify(editableStructured ?? result.structured, null, 2)}
                                    </pre>
                                  ),
                                },
                              ]}
                            />

                            {result.meta && (
                              <Card type="inner" title="元数据 (Metadata)" size="small">
                                <Space wrap>
                                  <Text>模型: {result.meta.model_used}</Text>
                                  <Text>置信度: {result.meta.confidence.toFixed(2)}</Text>
                                  <Text>耗时: {result.meta.processing_time_ms} ms</Text>
                                </Space>
                              </Card>
                            )}
                          </Space>
                        )}
                      </Card>
                    </Col>
                  </Row>
                </>
              ),
            },
            {
              key: 'generate',
              label: '文生图（JSON 上传）',
              children: (
                <>
                  <Alert
                    message="功能说明"
                    description="上传图生文输出的 JSON 后生成图片。"
                    type="info"
                    showIcon
                    style={{ marginBottom: '24px' }}
                  />

                  <Row gutter={genScreenshotMode ? 16 : 24}>
                    <Col xs={24} lg={genScreenshotMode ? 9 : 10}>
                      <Card title="输入" bordered={false}>
                        <Space direction="vertical" style={{ width: '100%' }} size={genScreenshotMode ? 'large' : 'middle'}>
                          <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
                            <Upload {...genUploadProps} showUploadList={false}>
                              <Button icon={<UploadOutlined />} size={genScreenshotMode ? 'large' : 'middle'}>上传 JSON</Button>
                            </Upload>
                            <Space>
                              <Text strong style={genScreenshotMode ? { fontSize: 16 } : undefined}>截图模式</Text>
                              <Switch checked={genScreenshotMode} onChange={setGenScreenshotMode} />
                            </Space>
                          </Space>
                          {genJsonFile && (
                            <Alert
                              type="success"
                              message={`已选择：${genJsonFile.name}`}
                              showIcon
                            />
                          )}

                          <Form layout="vertical" size={genScreenshotMode ? 'middle' : 'small'}>
                            <Row gutter={12}>
                              <Col span={12}>
                                <Form.Item label="生成模式">
                                  <Select
                                    value={genMode}
                                    onChange={(value) => setGenMode(value)}
                                    options={[
                                      { value: 'default', label: '默认（跟随后端）' },
                                      { value: 'proxy', label: 'proxy（远程）' },
                                      { value: 'sd', label: 'sd（本地）' },
                                      { value: 'gemini', label: 'gemini（云端）' },
                                    ]}
                                  />
                                </Form.Item>
                              </Col>
                              <Col span={12}>
                                <Form.Item label="风格预设">
                                  <Select
                                    allowClear
                                    placeholder="可选"
                                    value={genStylePreset}
                                    onChange={(value) => setGenStylePreset(value)}
                                    options={[
                                      { value: 'photoreal', label: 'photoreal' },
                                      { value: 'anime', label: 'anime' },
                                      { value: 'watercolor', label: 'watercolor' },
                                      { value: 'cyberpunk', label: 'cyberpunk' },
                                      { value: 'ink', label: 'ink' },
                                    ]}
                                  />
                                </Form.Item>
                              </Col>
                            </Row>

                            <Row gutter={12}>
                              <Col span={12}>
                                <Form.Item label="尺寸 (WxH)">
                                  <Input
                                    value={genSize}
                                    onChange={(e) => setGenSize(e.target.value)}
                                    placeholder="512x512"
                                  />
                                </Form.Item>
                              </Col>
                              <Col span={12}>
                                <Form.Item label="Sampler">
                                  <Input
                                    value={genSampler}
                                    onChange={(e) => setGenSampler(e.target.value)}
                                    placeholder="DPM++ 2M Karras"
                                  />
                                </Form.Item>
                              </Col>
                            </Row>

                            <Row gutter={12}>
                              <Col span={12}>
                                <Form.Item label="Steps">
                                  <InputNumber
                                    min={1}
                                    max={150}
                                    value={genSteps}
                                    onChange={(value) => setGenSteps(value ?? 30)}
                                    style={{ width: '100%' }}
                                  />
                                </Form.Item>
                              </Col>
                              <Col span={12}>
                                <Form.Item label="CFG">
                                  <InputNumber
                                    min={1}
                                    max={30}
                                    step={0.5}
                                    value={genCfg}
                                    onChange={(value) => setGenCfg(value ?? 7)}
                                    style={{ width: '100%' }}
                                  />
                                </Form.Item>
                              </Col>
                            </Row>

                            <Form.Item label="固定 Seed（开启后可复现）">
                              <Space>
                                <Switch checked={genSeedLocked} onChange={setGenSeedLocked} />
                                <InputNumber
                                  disabled={!genSeedLocked}
                                  min={0}
                                  max={4294967295}
                                  value={genSeed}
                                  onChange={(value) => setGenSeed(value ?? null)}
                                  placeholder="例如 123456"
                                  style={{ width: 180 }}
                                />
                              </Space>
                            </Form.Item>

                            <Form.Item label="负向提示词（可选）">
                              <Input
                                value={genNegativePrompt}
                                onChange={(e) => setGenNegativePrompt(e.target.value)}
                                placeholder="blurry, low quality"
                              />
                            </Form.Item>

                            <Form.Item label="Strict JSON">
                              <Switch checked={genStrictJson} onChange={setGenStrictJson} />
                            </Form.Item>
                          </Form>

                          {genJsonPreview && (
                            <Collapse
                              items={[
                                {
                                  key: '1',
                                  label: 'JSON 预览',
                                  children: (
                                    <pre
                                      style={{
                                        background: '#f5f5f5',
                                        padding: genScreenshotMode ? '16px' : '12px',
                                        borderRadius: '4px',
                                        overflow: 'auto',
                                        maxHeight: genScreenshotMode ? '260px' : '200px',
                                        fontSize: genScreenshotMode ? '15px' : '13px',
                                        lineHeight: 1.7,
                                      }}
                                    >
                                      {genJsonPreview}
                                    </pre>
                                  ),
                                },
                              ]}
                            />
                          )}
                          <Space>
                            <Button
                              type="primary"
                              icon={<ReloadOutlined />}
                              onClick={handleGenerate}
                              loading={genLoading}
                              size={genScreenshotMode ? 'large' : 'middle'}
                            >
                              开始生成
                            </Button>
                            <Button icon={<DeleteOutlined />} onClick={handleGenClear} disabled={genLoading} size={genScreenshotMode ? 'large' : 'middle'}>
                              清空
                            </Button>
                          </Space>
                        </Space>
                      </Card>
                    </Col>

                    <Col xs={24} lg={genScreenshotMode ? 15 : 14}>
                      <Card title="生成结果" bordered={false}>
                        {genLoading && (
                          <div style={{ textAlign: 'center', padding: '48px' }}>
                            <Spin size="large" />
                            <Paragraph style={{ marginTop: '16px' }}>正在生成中，请稍候...</Paragraph>
                          </div>
                        )}

                        {!genLoading && !genResult && (
                          <Alert
                            message="等待生成"
                            description="上传图生文输出的 JSON 后点击开始生成"
                            type="warning"
                            showIcon
                            style={genScreenshotMode ? { fontSize: 16, lineHeight: 1.7 } : undefined}
                          />
                        )}

                        {!genLoading && genResult && (
                          <Space direction="vertical" style={{ width: '100%' }} size="large">
                            <Card type="inner" title="生成图片">
                              <img
                                src={`${BASE_URL}${genResult.image_url}`}
                                alt="生成结果"
                                style={{ width: '100%', maxHeight: genScreenshotMode ? '280px' : '420px', objectFit: 'contain' }}
                              />
                            </Card>
                            <Card type="inner" title="生成信息">
                              <Space direction="vertical" size={genScreenshotMode ? 'middle' : 'small'}>
                                <Text style={genScreenshotMode ? { fontSize: 16, lineHeight: 1.7 } : undefined}>Prompt: {genResult.prompt}</Text>
                                <Text style={genScreenshotMode ? { fontSize: 16 } : undefined}>Model: {genResult.meta.model_used}</Text>
                                <Text style={genScreenshotMode ? { fontSize: 16 } : undefined}>Mode: {genResult.meta.mode ?? 'unknown'}</Text>
                                <Text style={genScreenshotMode ? { fontSize: 16 } : undefined}>复现等级: {genResult.meta.reproducibility ?? 'best_effort'}</Text>
                                <Text style={genScreenshotMode ? { fontSize: 16 } : undefined}>风格预设: {genResult.meta.style_applied ?? '无'}</Text>
                                <Text style={genScreenshotMode ? { fontSize: 16 } : undefined}>Prompt 来源: {genResult.meta.prompt_source ?? 'legacy'}</Text>
                                <Text style={genScreenshotMode ? { fontSize: 16 } : undefined}>耗时: {genResult.meta.processing_time_ms} ms</Text>
                                {genResult.meta.effective_params && (
                                  <Text style={genScreenshotMode ? { fontSize: 16, lineHeight: 1.7 } : undefined}>
                                    生效参数: {JSON.stringify(genResult.meta.effective_params)}
                                  </Text>
                                )}
                              </Space>
                            </Card>
                            <Card type="inner" title="下载结果">
                              <Space wrap>
                                <Button
                                  icon={<DownloadOutlined />}
                                  onClick={handleDownloadGenJson}
                                >
                                  下载 JSON
                                </Button>
                                <Button
                                  icon={<DownloadOutlined />}
                                  onClick={() => handleDownload(`${BASE_URL}${genResult.image_url}`, `generate-${genResult.id}.url`)}
                                >
                                  下载 URL
                                </Button>
                              </Space>
                            </Card>
                            <Collapse
                              items={[
                                {
                                  key: '1',
                                  label: '原始 JSON（调试用）',
                                  children: (
                                    <pre
                                      style={{
                                        background: '#f5f5f5',
                                        padding: genScreenshotMode ? '16px' : '12px',
                                        borderRadius: '4px',
                                        overflow: 'auto',
                                        maxHeight: genScreenshotMode ? '360px' : '300px',
                                        fontSize: genScreenshotMode ? '15px' : '13px',
                                        lineHeight: 1.7,
                                      }}
                                    >
                                      {JSON.stringify(genResult, null, 2)}
                                    </pre>
                                  ),
                                },
                              ]}
                            />
                          </Space>
                        )}
                      </Card>
                    </Col>
                  </Row>
                </>
              ),
            },
          ]}
        />

        {/* 历史记录 */}
        {history.length > 0 && (
          <Card
            title="📚 历史记录（最近 10 条）"
            bordered={false}
            style={{ marginTop: '24px' }}
          >
            <List
              grid={{ gutter: 16, xs: 2, sm: 3, md: 4, lg: 5, xl: 5, xxl: 6 }}
              dataSource={history}
              renderItem={(item: HistoryItem) => (
                <List.Item>
                  <Card
                    hoverable
                    cover={
                      <img
                        alt="历史图片"
                        src={item.imageUrl}
                        style={{ height: '120px', objectFit: 'cover' }}
                      />
                    }
                    onClick={() => handleViewHistory(item)}
                    size="small"
                  >
                    <Card.Meta
                      description={new Date(item.timestamp).toLocaleString('zh-CN')}
                    />
                  </Card>
                </List.Item>
              )}
            />
          </Card>
        )}

        {/* 底部信息 */}
        <div style={{ textAlign: 'center', marginTop: '32px', color: '#999' }}>
          <Text type="secondary">
            当前后端地址: <Text code>{BASE_URL}</Text> | 可在 .env 文件中配置 VITE_API_BASE_URL
          </Text>
        </div>
      </Content>
    </Layout>
  );
}

export default App;
