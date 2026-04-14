# 百炼 (Model Studio) Documentation Structure

Reference guide for navigating the 百炼/Model Studio documentation on help.aliyun.com.

## URL Patterns

All 百炼 documentation follows this URL pattern:
```
https://help.aliyun.com/zh/model-studio/<page-name>
```

## Documentation Categories

### 开始使用 (Getting Started)

| Page | URL | Description |
|------|-----|-------------|
| 产品简介 | `https://help.aliyun.com/zh/model-studio/what-is-model-studio` | Platform overview and features |
| 模型列表 | `https://help.aliyun.com/zh/model-studio/models` | All available models |
| 首次调用千问API | Search: "首次调用" | Quick start guide |
| 限流 | Search: "限流" | Rate limiting rules |
| 选择地域 | Search: "地域" | Region selection |

### 产品计费 (Pricing)

| Page | Description |
|------|-------------|
| 新人免费额度 | Free tier for new users |
| 模型调用计费 | Per-model pricing |
| 模型训练与部署计费 | Training and deployment costs |
| Coding Plan | Coding plan subscription details |

### 模型 (Models)

| Page | Search Keyword | Description |
|------|---------------|-------------|
| 模型上下架与更新 | "模型上下架" | Model lifecycle management |
| 专项模型 | "专项模型" or "specialized" | Specialized model capabilities |
| - Qwen-Long | "qwen-long" | Long context understanding |
| - Qwen-Coder | "qwen-coder" | Code generation |
| - Qwen-MT | "qwen-mt" | Translation |
| - Qwen-Character | "qwen-character" | Role-playing |
| - Qwen-Doc | "qwen-doc" | Document mining |
| - Qwen-Deep | "qwen-deep" | Deep research |
| - GUI Plus | "gui" | GUI automation |
| 模型导入 | "模型导入" | Import LoRA models from OSS |
| 模型调优简介 | "模型调优" | SFT fine-tuning |
| 模型数据 | "训练集" | Training and evaluation datasets |
| 模型监控 | "模型监控" | Model monitoring |

### 应用 (Applications)

| Page | Search Keyword | Description |
|------|---------------|-------------|
| 智能体应用 | "智能体" | Create and configure agents |
| 工作流应用 | "工作流" | Workflow orchestration |
| 知识库(RAG) | "知识库" or "rag-knowledge-base" | RAG knowledge base |
| 数据连接 | "数据连接" | External data sources |
| 插件 | "插件" | Tool calling / plugins |
| 记忆库 | "记忆库" | Long-term memory |
| 文件问答 | "文件问答" | File/document Q&A |
| 指令列表 | "指令" | System prompts |
| 自定义指令 | "自定义指令" | Custom instructions |

### API参考 (API Reference)

| Page | URL | Description |
|------|-----|-------------|
| API概览 | `.../api-aimiaobi-2023-08-01-overview` | API overview |
| API目录 | `.../api-aimiaobi-2023-08-01-dir/` | Full API directory |
| 通用接口 | Search: "通用接口" | Universal API endpoints |
| deepsearch API | `.../deepsearch-api-overview` | Deep search capabilities |
| 知识库API操作指南 | `.../rag-knowledge-base-api-guide` | Knowledge base API |
| 长期记忆开放接口 | Search: "长期记忆" | Long-term memory API |

### 解决方案类 (Solutions)

| Page | Search Keyword | Description |
|------|---------------|-------------|
| 妙笔-创作文章 | "妙笔" or "创作文章" | Article generation |
| 妙笔-文体仿写 | "文体仿写" | Style imitation |
| 妙笔-视频审校 | "视频审校" | Video review |
| 妙笔-文章审校 | "文章审校" | Article review |
| 妙策API | "妙策" | Miaoce API |
| 析言GBI | "析言" or "GBI" | Analytical GBI |

### 其他 (Other)

| Page | Description |
|------|-------------|
| 联网搜索 | Web search capability |
| 文件上传下载 | File upload/download API |
| 异步任务管理 | Async task management |
| 常见问题(FAQ) | Frequently asked questions |

## Search Tips

1. **For model-specific docs**: Use `qwen-` prefix (e.g., `qwen-tts`, `qwen-omni`)
2. **For API docs**: Use `api-aimiaobi` as base URL pattern
3. **For feature docs**: Chinese keywords usually work better (e.g., "知识库" vs "knowledge base")
4. **For TTS/STT**: Search with `qwen-tts` or `qwen-tts-realtime`
