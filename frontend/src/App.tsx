import { useState } from 'react';
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
} from 'antd';
import {
  CopyOutlined,
  DeleteOutlined,
  FileImageOutlined,
  ReloadOutlined,
  DownloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { reverseImage, generateImage, BASE_URL } from './services/api';
import type { GenerateOptions } from './services/api';
import type { ReverseResponse, HistoryItem, GenerateResponse } from './types/reverse';
import { compileStructuredPrompt, copyToClipboard } from './utils/prompt';

const { Header, Content } = Layout;
const { Title, Paragraph, Text } = Typography;
const { Dragger } = Upload;

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
  const [genMode, setGenMode] = useState<'sd' | 'gemini' | 'proxy'>('proxy');
  const [genStylePreset, setGenStylePreset] = useState<'photoreal' | 'anime' | 'watercolor' | 'cyberpunk' | 'ink' | undefined>(undefined);
  const [genSeedLocked, setGenSeedLocked] = useState(false);
  const [genSeed, setGenSeed] = useState<number | null>(null);
  const [genSteps, setGenSteps] = useState<number>(30);
  const [genCfg, setGenCfg] = useState<number>(7);
  const [genSize, setGenSize] = useState<string>('512x512');
  const [genSampler, setGenSampler] = useState<string>('DPM++ 2M Karras');
  const [genNegativePrompt, setGenNegativePrompt] = useState<string>('');
  const [genStrictJson, setGenStrictJson] = useState<boolean>(false);

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
    if (!result?.structured) return;

    const compiled = compileStructuredPrompt(result.structured);
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
    if (!result) return;
    handleDownload(JSON.stringify(result, null, 2), `reverse-${result.id}.json`, 'application/json');
  };

  const handleDownloadTxt = () => {
    if (!result?.structured) return;
    const compiled = compileStructuredPrompt(result.structured);
    const text = compiled.negative
      ? `Positive prompt:\n${compiled.positive}\n\nNegative prompt:\n${compiled.negative}`
      : `Positive prompt:\n${compiled.positive}`;
    handleDownload(text, `reverse-${result.id}.txt`);
  };

  const handleDownloadGenJson = () => {
    if (!genResult) return;
    handleDownload(JSON.stringify(genResult, null, 2), `generate-${genResult.id}.json`, 'application/json');
  };

  // 查看历史记录
  const handleViewHistory = (item: HistoryItem) => {
    setImagePreviewUrl(item.imageUrl);
    setResult(item.result);
    message.info('已加载历史记录');
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
        <Tabs
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

                  <Row gutter={24}>
                    <Col xs={24} lg={10}>
                      <Card title="图片上传" bordered={false}>
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
                          </div>
                        )}
                      </Card>
                    </Col>

                    <Col xs={24} lg={14}>
                      <Card title="识别结果" bordered={false}>
                        {loading && (
                          <div style={{ textAlign: 'center', padding: '48px' }}>
                            <Spin size="large" />
                            <Paragraph style={{ marginTop: '16px' }}>正在识别中，请稍候...</Paragraph>
                          </div>
                        )}

                        {!loading && !result && (
                          <Alert
                            message="等待识别"
                            description="请上传图片并点击'开始反推/识别'按钮"
                            type="warning"
                            showIcon
                          />
                        )}

                        {!loading && result && (
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

                            {result.prompt && (
                              <Card
                                type="inner"
                                title="推荐 Prompt"
                                extra={
                                  <Button
                                    type="link"
                                    icon={<CopyOutlined />}
                                    onClick={() => handleCopy(result.prompt!, 'Prompt')}
                                  >
                                    复制
                                  </Button>
                                }
                              >
                                <Paragraph style={{ fontFamily: 'monospace' }}>{result.prompt}</Paragraph>
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
                                </Space>
                              </Card>
                            )}

                            {result.structured && (
                              <Card
                                type="inner"
                                title="结构化提示词 (Structured)"
                                extra={
                                  <Button
                                    type="link"
                                    icon={<CopyOutlined />}
                                    onClick={handleCopyStructured}
                                  >
                                    复制全部
                                  </Button>
                                }
                              >
                                <Tabs
                                  items={[
                                    {
                                      key: 'subject',
                                      label: 'Subject (主体)',
                                      children: (
                                        <div>
                                          <Space direction="vertical">
                                            <div>
                                              <Text strong>Label:</Text>{' '}
                                              {result.structured.subject.label || '无'}
                                              {result.structured.subject.weight && (
                                                <Text type="secondary"> (weight: {result.structured.subject.weight.toFixed(1)})</Text>
                                              )}
                                            </div>
                                            <div>
                                              <Text strong>Entities:</Text>{' '}
                                              {result.structured.subject.entities?.length ? (
                                                result.structured.subject.entities.map((tag, idx) => (
                                                  <Tag key={idx} color="blue" style={{ margin: '4px' }}>
                                                    {tag}
                                                  </Tag>
                                                ))
                                              ) : (
                                                <Text type="secondary">无</Text>
                                              )}
                                            </div>
                                            <div>
                                              <Text strong>Attributes:</Text>{' '}
                                              {Array.isArray(result.structured.subject.attributes) ? (
                                                result.structured.subject.attributes.length ? (
                                                  result.structured.subject.attributes.map((tag, idx) => (
                                                    <Tag key={idx} color="cyan" style={{ margin: '4px' }}>
                                                      {tag}
                                                    </Tag>
                                                  ))
                                                ) : (
                                                  <Text type="secondary">无</Text>
                                                )
                                              ) : (
                                                Object.keys(result.structured.subject.attributes || {}).length ? (
                                                  Object.entries(result.structured.subject.attributes as Record<string, string>).map(([key, value]) => (
                                                    <Tag key={key} color="cyan" style={{ margin: '4px' }}>
                                                      {key} {value}
                                                    </Tag>
                                                  ))
                                                ) : (
                                                  <Text type="secondary">无</Text>
                                                )
                                              )}
                                            </div>
                                            <div>
                                              <Text strong>Count:</Text>{' '}
                                              {result.structured.subject.count ?? '无'}
                                            </div>
                                          </Space>
                                        </div>
                                      ),
                                    },
                                    {
                                      key: 'scene',
                                      label: 'Scene (场景)',
                                      children: (
                                        <Space direction="vertical">
                                          <div>
                                            <Text strong>Environment:</Text>{' '}
                                            {result.structured.scene.environment.length ? (
                                              result.structured.scene.environment.map((tag, idx) => (
                                                <Tag key={idx} color="green" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Background:</Text>{' '}
                                            {result.structured.scene.background.length ? (
                                              result.structured.scene.background.map((tag, idx) => (
                                                <Tag key={idx} color="green" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Time/Weather:</Text>{' '}
                                            {result.structured.scene.time_weather.length ? (
                                              result.structured.scene.time_weather.map((tag, idx) => (
                                                <Tag key={idx} color="green" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Composition:</Text>{' '}
                                            {result.structured.scene.composition.length ? (
                                              result.structured.scene.composition.map((tag, idx) => (
                                                <Tag key={idx} color="green" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                        </Space>
                                      ),
                                    },
                                    {
                                      key: 'style',
                                      label: 'Style (风格)',
                                      children: (
                                        <Space direction="vertical">
                                          <div>
                                            <Text strong>Medium:</Text>{' '}
                                            {result.structured.style.medium.length ? (
                                              result.structured.style.medium.map((tag, idx) => (
                                                <Tag key={idx} color="purple" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Artist Style:</Text>{' '}
                                            {result.structured.style.artist_style.length ? (
                                              result.structured.style.artist_style.map((tag, idx) => (
                                                <Tag key={idx} color="purple" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Aesthetic:</Text>{' '}
                                            {result.structured.style.aesthetic.length ? (
                                              result.structured.style.aesthetic.map((tag, idx) => (
                                                <Tag key={idx} color="purple" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Quality:</Text>{' '}
                                            {result.structured.style.quality.length ? (
                                              result.structured.style.quality.map((tag, idx) => (
                                                <Tag key={idx} color="purple" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                        </Space>
                                      ),
                                    },
                                    {
                                      key: 'tech',
                                      label: 'Tech (技术)',
                                      children: (
                                        <Space direction="vertical">
                                          <div>
                                            <Text strong>Lighting:</Text>{' '}
                                            {result.structured.tech.lighting.length ? (
                                              result.structured.tech.lighting.map((tag, idx) => (
                                                <Tag key={idx} color="orange" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Camera:</Text>{' '}
                                            {result.structured.tech.camera.length ? (
                                              result.structured.tech.camera.map((tag, idx) => (
                                                <Tag key={idx} color="orange" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Color Tone:</Text>{' '}
                                            {result.structured.tech.color_tone.length ? (
                                              result.structured.tech.color_tone.map((tag, idx) => (
                                                <Tag key={idx} color="orange" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Render:</Text>{' '}
                                            {result.structured.tech.render.length ? (
                                              result.structured.tech.render.map((tag, idx) => (
                                                <Tag key={idx} color="orange" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                        </Space>
                                      ),
                                    },
                                    {
                                      key: 'negative',
                                      label: 'Negative (负面)',
                                      children: (
                                        <Space direction="vertical">
                                          <div>
                                            <Text strong>Severity:</Text> {result.structured.negative.severity || 'medium'}
                                          </div>
                                          <div>
                                            <Text strong>Term Weights:</Text>{' '}
                                            {result.structured.negative.term_weights.length ? (
                                              result.structured.negative.term_weights.map((item, idx) => (
                                                <Tag key={idx} color="red" style={{ margin: '4px' }}>
                                                  {item.term} ({item.weight.toFixed(1)})
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                          <div>
                                            <Text strong>Terms:</Text>{' '}
                                            {result.structured.negative.terms.length ? (
                                              result.structured.negative.terms.map((tag, idx) => (
                                                <Tag key={idx} color="red" style={{ margin: '4px' }}>
                                                  {tag}
                                                </Tag>
                                              ))
                                            ) : (
                                              <Text type="secondary">无</Text>
                                            )}
                                          </div>
                                        </Space>
                                      ),
                                    },
                                    {
                                      key: 'params',
                                      label: 'Params (参数)',
                                      children: (
                                        <Space direction="vertical">
                                          <div>
                                            <Text strong>Size:</Text> {result.structured.params.size}
                                          </div>
                                          <div>
                                            <Text strong>Steps:</Text> {result.structured.params.steps}
                                          </div>
                                          <div>
                                            <Text strong>CFG:</Text> {result.structured.params.cfg}
                                          </div>
                                          <div>
                                            <Text strong>Sampler:</Text> {result.structured.params.sampler}
                                          </div>
                                          <div>
                                            <Text strong>Seed:</Text> {result.structured.params.seed ?? '无'}
                                          </div>
                                        </Space>
                                      ),
                                    },
                                  ]}
                                />
                              </Card>
                            )}

                            <Collapse
                              items={[
                                {
                                  key: '1',
                                  label: '原始 JSON（调试用）',
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
                                      {JSON.stringify(result, null, 2)}
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

                  <Row gutter={24}>
                    <Col xs={24} lg={10}>
                      <Card title="输入" bordered={false}>
                        <Space direction="vertical" style={{ width: '100%' }} size="middle">
                          <Upload {...genUploadProps} showUploadList={false}>
                            <Button icon={<UploadOutlined />}>上传 JSON</Button>
                          </Upload>
                          {genJsonFile && (
                            <Alert
                              type="success"
                              message={`已选择：${genJsonFile.name}`}
                              showIcon
                            />
                          )}

                          <Form layout="vertical" size="small">
                            <Row gutter={12}>
                              <Col span={12}>
                                <Form.Item label="生成模式">
                                  <Select
                                    value={genMode}
                                    onChange={(value) => setGenMode(value)}
                                    options={[
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
                                        padding: '12px',
                                        borderRadius: '4px',
                                        overflow: 'auto',
                                        maxHeight: '200px',
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
                            >
                              开始生成
                            </Button>
                            <Button icon={<DeleteOutlined />} onClick={handleGenClear} disabled={genLoading}>
                              清空
                            </Button>
                          </Space>
                        </Space>
                      </Card>
                    </Col>

                    <Col xs={24} lg={14}>
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
                          />
                        )}

                        {!genLoading && genResult && (
                          <Space direction="vertical" style={{ width: '100%' }} size="large">
                            <Card type="inner" title="生成图片">
                              <img
                                src={`${BASE_URL}${genResult.image_url}`}
                                alt="生成结果"
                                style={{ width: '100%', maxHeight: '420px', objectFit: 'contain' }}
                              />
                            </Card>
                            <Card type="inner" title="生成信息">
                              <Space direction="vertical">
                                <Text>Prompt: {genResult.prompt}</Text>
                                <Text>Model: {genResult.meta.model_used}</Text>
                                <Text>Mode: {genResult.meta.mode ?? 'unknown'}</Text>
                                <Text>复现等级: {genResult.meta.reproducibility ?? 'best_effort'}</Text>
                                <Text>风格预设: {genResult.meta.style_applied ?? '无'}</Text>
                                <Text>Prompt 来源: {genResult.meta.prompt_source ?? 'legacy'}</Text>
                                <Text>耗时: {genResult.meta.processing_time_ms} ms</Text>
                                {genResult.meta.effective_params && (
                                  <Text>
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
                                        padding: '12px',
                                        borderRadius: '4px',
                                        overflow: 'auto',
                                        maxHeight: '300px',
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
              renderItem={(item) => (
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
