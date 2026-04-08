# 前端快速参考指南 (Frontend Quick Reference)

## 1. 快速启动 (Quick Start)

### Windows
```cmd
cd G:\Dev\repos\bishe\frontend
npm install
npm run dev
```

### Linux/Mac
```bash
cd /path/to/bishe/frontend
npm install
npm run dev
```

**访问地址**: http://localhost:5173

---

## 2. 核心文件位置 (Core Files)

| 文件 | 路径 | 作用 |
|------|------|------|
| 主组件 | `src/App.tsx` | UI 布局、上传、结果展示 |
| API 封装 | `src/services/api.ts` | reverseImage() 方法 |
| 类型定义 | `src/types/reverse.ts` | TypeScript 接口 |
| 工具函数 | `src/utils/prompt.ts` | 编译 prompt、复制功能 |
| 环境配置 | `.env` | 后端地址配置 |
| 依赖管理 | `package.json` | 项目依赖 |

---

## 3. 关键 API (Key APIs)

### reverseImage() - 图片识别

```typescript
import { reverseImage } from './services/api';

const result = await reverseImage(imageFile);
// result: ReverseResponse
```

### compileStructuredPrompt() - 编译提示词

```typescript
import { compileStructuredPrompt } from './utils/prompt';

const { positive, negative } = compileStructuredPrompt(result.structured);
// positive: "cute robot, holding banana, ..."
// negative: "blurry, low quality"
```

### copyToClipboard() - 复制到剪贴板

```typescript
import { copyToClipboard } from './utils/prompt';

const success = await copyToClipboard(text);
// success: true/false
```

---

## 4. 响应结构 (Response Structure)

### 完整示例

```typescript
interface ReverseResponse {
  caption: string;                 // 必需
  prompt?: string;                 // 可选
  structured?: {
    subject?: string[];            // 主体
    scene?: string[];              // 场景
    style?: string[];              // 风格
    tech?: string[];               // 技术
    negative?: string[];           // 负面
  };
  tags?: string[];                 // 标签
  meta?: {
    duration?: number;             // 耗时
    model?: string;                // 模型
    timestamp?: string;            // 时间戳
  };
}
```

### 最小响应

```json
{
  "caption": "一只可爱的猫"
}
```

---

## 5. 配置修改 (Configuration)

### 修改后端地址

编辑 `.env`:
```env
VITE_API_BASE_URL=http://192.168.1.110:8000
```

### 修改上传限制

编辑 `src/App.tsx` 的 `uploadProps`:

```typescript
// 修改格式
accept: 'image/jpeg,image/png,image/webp,image/gif',

// 修改大小（20MB）
const isLt20M = file.size / 1024 / 1024 < 20;
```

### 修改超时时间

编辑 `src/services/api.ts`:
```typescript
const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 120000, // 120 秒
});
```

---

## 6. 常用命令 (Common Commands)

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 清除缓存并重装
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

---

## 7. 故障排查 (Troubleshooting)

### 问题: 请求失败 / 网络错误

**检查步骤**:
1. 后端是否运行: `curl http://127.0.0.1:8000/health`
2. `.env` 中 `VITE_API_BASE_URL` 是否正确
3. 浏览器控制台 Network 标签查看详细错误

### 问题: CORS 跨域错误

**解决方案**: 在后端添加 CORS 中间件

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 问题: 页面空白

**检查步骤**:
1. 浏览器控制台是否有报错
2. `main.tsx` 是否正确引入 `App.tsx`
3. 清除浏览器缓存重试

---

## 8. 目录结构速查 (Directory Structure)

```
frontend/
├── src/
│   ├── types/reverse.ts          # 类型定义
│   ├── services/api.ts           # API 封装
│   ├── utils/prompt.ts           # 工具函数
│   ├── App.tsx                   # 主组件
│   └── main.tsx                  # 入口
├── .env                          # 环境变量
├── package.json                  # 依赖管理
└── vite.config.ts                # 构建配置
```

---

## 9. 依赖清单 (Dependencies)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "antd": "^5.12.0",
    "axios": "^1.6.0",
    "@ant-design/icons": "^5.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.2.2",
    "vite": "^5.0.8"
  }
}
```

---

## 10. 测试检查清单 (Testing Checklist)

- [ ] 依赖安装成功 (`npm install`)
- [ ] 开发服务器启动 (`npm run dev`)
- [ ] 页面正常显示，无报错
- [ ] 上传图片功能正常
- [ ] 格式/大小校验生效
- [ ] 图片预览显示正确
- [ ] 点击"开始反推/识别"发送请求
- [ ] Loading 状态正确显示
- [ ] 识别结果正确展示
- [ ] Caption 显示正确
- [ ] Structured Tags 分类显示
- [ ] 复制功能正常工作
- [ ] 历史记录自动保存
- [ ] 点击历史记录回显结果
- [ ] 清空功能正常
- [ ] 字段缺失时优雅降级

---

## 11. 代码片段 (Code Snippets)

### 添加新的卡片展示字段

```tsx
// 在 App.tsx 的结果展示区域添加
{result.yourNewField && (
  <Card type="inner" title="新字段标题">
    <Paragraph>{result.yourNewField}</Paragraph>
  </Card>
)}
```

### 修改结构化 Tag 颜色

```tsx
// 在 Tabs items 中修改
<Tag key={idx} color="cyan" style={{ margin: '4px' }}>
  {tag}
</Tag>
```

### 添加新的 Tab

```tsx
{
  key: 'quality',
  label: 'Quality (质量)',
  children: (
    <div>
      {result.structured.quality && result.structured.quality.length > 0 ? (
        result.structured.quality.map((tag, idx) => (
          <Tag key={idx} color="gold" style={{ margin: '4px' }}>
            {tag}
          </Tag>
        ))
      ) : (
        <Text type="secondary">无</Text>
      )}
    </div>
  ),
}
```

---

## 12. 环境要求 (Requirements)

- Node.js: >= 18.0.0
- npm: >= 9.0.0
- 浏览器: 支持 ES6+ (Chrome/Firefox/Edge/Safari 最新版)
- 后端: FastAPI 服务运行在 8000 端口（默认）

---

## 13. 相关文档 (Related Docs)

- **详细实现文档**: `docs/frontend-image-to-text-implementation.md`
- **前端 README**: `frontend/README.md`
- **Agent Memory**: `.claude/agent-memory/bishe-agent/MEMORY.md`

---

**版本**: v1.0
**日期**: 2024-02-08
