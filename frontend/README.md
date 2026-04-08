# 图生文（提示词反推）前端项目

这是一个基于 **React + TypeScript + Vite + Ant Design** 的图像描述生成前端应用，用于毕业设计。

## 功能特性

✅ **图片上传**：支持拖拽上传和点击选择（JPG/PNG/WEBP，≤ 10MB）
✅ **实时预览**：上传后立即显示图片预览
✅ **智能识别**：调用后端 `/reverse` 接口获取图像描述和结构化提示词
✅ **结构化展示**：分类展示 Subject/Scene/Style/Tech/Negative
✅ **一键复制**：支持复制 Caption、Prompt、结构化提示词
✅ **历史记录**：保存最近 10 次识别记录，可快速回看
✅ **容错处理**：字段缺失不会报错，优雅降级展示

---

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 配置后端地址

编辑 `.env` 文件（如果没有则创建）：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

**说明**：
- 如果后端运行在其他地址（如 `http://<YOUR_SERVER_IP>:8000`），请修改此配置
- 也可以创建 `.env.local` 覆盖默认配置

### 3. 启动开发服务器

```bash
npm run dev
```

浏览器会自动打开 `http://localhost:3000`

### 4. 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录，可部署到任意静态服务器。

---

## 项目结构

```
frontend/
├── src/
│   ├── types/
│   │   └── reverse.ts           # 接口类型定义
│   ├── services/
│   │   └── api.ts               # API 封装（reverseImage 方法）
│   ├── utils/
│   │   └── prompt.ts            # 工具函数（编译 prompt、复制）
│   ├── App.tsx                  # 主组件
│   ├── main.tsx                 # 入口文件
│   └── vite-env.d.ts            # 环境变量类型
├── .env                         # 环境变量配置
├── package.json                 # 依赖配置
├── tsconfig.json                # TypeScript 配置
├── vite.config.ts               # Vite 配置
└── index.html                   # HTML 模板
```

---

## 后端接口约定

### 请求

- **URL**: `POST /reverse`
- **Content-Type**: `multipart/form-data`
- **字段**: `image` (File)

### 响应示例

```json
{
  "caption": "一个可爱的机器人手持香蕉，赛博朋克风格，霓虹粉色和青色调",
  "prompt": "cyberpunk cute robot holding banana, neon pink teal, detailed",
  "structured": {
    "subject": ["cute robot", "holding banana"],
    "scene": ["rain-soaked city", "night"],
    "style": ["cyberpunk", "neon aesthetic"],
    "tech": ["high contrast", "rim light"],
    "negative": ["blurry", "low quality"]
  },
  "tags": ["robot", "cyberpunk", "banana"],
  "meta": {
    "duration": 2.35,
    "model": "gemini-vision-pro"
  }
}
```

**字段说明**：
- `caption` (必须): 自然语言描述
- `prompt` (可选): 推荐的 prompt 文本
- `structured` (可选): 结构化提示词对象
- `tags` (可选): 标签列表
- `meta` (可选): 元数据（耗时、模型名等）

---

## 使用说明

### 1. 上传图片

- 点击上传区域或拖拽图片到虚线框
- 支持格式：JPG、PNG、WEBP
- 大小限制：10MB

### 2. 开始识别

- 上传成功后，点击"开始反推/识别"按钮
- 等待后端处理（通常 2-10 秒）
- 右侧将显示识别结果

### 3. 查看结果

- **Caption**：自然语言描述，适合阅读理解
- **Prompt**：推荐的完整 prompt，可直接用于文生图
- **Structured**：分类展示（Subject/Scene/Style/Tech/Negative）
  - 每个词以彩色 Tag 显示
  - 点击"复制全部"会自动编译为正向+负向 prompt
- **原始 JSON**：折叠面板，便于调试

### 4. 一键复制

- 每个卡片右上角都有"复制"按钮
- 结构化提示词的"复制全部"会生成格式化文本：
  ```
  正向提示词：
  cute robot, holding banana, rain-soaked city, cyberpunk, neon aesthetic, high contrast, rim light

  负向提示词：
  blurry, low quality
  ```

### 5. 历史记录

- 自动保存最近 10 次识别结果
- 点击缩略图可快速加载历史记录

---

## 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite 5** - 快速构建工具
- **Ant Design 5** - UI 组件库
- **Axios** - HTTP 请求

---

## 常见问题

### Q1: 启动报错 "Cannot find module 'antd'"
**A**: 请先运行 `npm install` 安装依赖

### Q2: 提示"请求失败"或"网络错误"
**A**: 检查以下几点：
1. 后端服务是否已启动（如 `python backend/main.py`）
2. `.env` 中的 `VITE_API_BASE_URL` 是否正确
3. 后端接口路径是否为 `/reverse`
4. 检查浏览器控制台 Network 标签查看详细错误

### Q3: 如何修改上传限制（大小、格式）
**A**: 编辑 `src/App.tsx` 中的 `uploadProps` 配置：
```tsx
accept: 'image/jpeg,image/png,image/webp',  // 修改允许的格式
const isLt10M = file.size / 1024 / 1024 < 10;  // 修改大小限制（单位 MB）
```

### Q4: 后端返回的字段和约定不一致怎么办？
**A**: 代码已做容错处理，缺失字段会显示"未返回该字段"或"无"，不会崩溃。如需适配，修改 `src/types/reverse.ts` 中的类型定义即可。

---

## 部署建议

### 开发环境
```bash
npm run dev
```

### 生产环境
1. 构建：`npm run build`
2. 部署 `dist/` 目录到 Nginx/Apache/CDN
3. 配置反向代理避免 CORS（推荐）：
   ```nginx
   location /api {
       proxy_pass http://127.0.0.1:8000;
   }
   ```
4. 修改 `.env.production` 设置生产环境的后端地址

---

## 作者

毕业设计项目 - 图生文功能前端实现
技术栈：React + TypeScript + Ant Design

如有问题，请检查：
1. 后端是否正常运行
2. 网络连接是否畅通
3. 浏览器控制台是否有报错

---

## License

MIT
