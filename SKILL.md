---
name: alibabacloud-docs-search
description: |
  Alibaba Cloud Documentation Search & Retrieval Skill.
  Search, fetch, and retrieve content from help.aliyun.com documentation site.
  Supports product search, keyword search, category filtering, and full-page content extraction.
  Also supports searching Alibaba Cloud announcements/notices from aliyun.com/notice/.
  Can extract model lists with pricing from Model Studio models page (with region switching).
  Can parse API directory tree with individual endpoint details.
  Can search within documentation sidebar directory tree.
  Triggers: "阿里云文档", "文档搜索", "doc search", "help.aliyun", "百炼文档", "model studio docs",
  "qwen docs", "产品文档", "API文档", "文档检索", "documentation", "阿里云帮助", "how to use 百炼",
  "how to call qwen api", "model studio what is", "RAG知识库", "知识库API",
  "阿里云公告", "notice search", "阿里云通知", "公告搜索", "announcement",
  "模型列表", "model list", "模型价格", "model pricing", "API目录", "api directory",
  "文档目录", "doc tree", "sidebar search", "模型广场", "model market", "百炼模型",
  "bailian model", "model detail", "模型详情"
compatibility:
  - Search Alibaba Cloud documentation by keyword or product
  - Fetch and parse full documentation page content
  - Filter by documentation category (开始使用/模型/应用/API参考 etc.)
  - Specifically optimized for 百炼 (Model Studio) documentation
  - Support JSON-formatted search results for programmatic use
  - Search and retrieve Alibaba Cloud announcements/notices from aliyun.com/notice/
  - Filter announcements by category (备案公告/升级公告/安全公告/其他)
  - Search announcements by keyword with pagination support
  - Extract model lists with pricing from Model Studio models page (region switching)
  - Parse API directory tree with individual endpoint details
  - Search within documentation sidebar directory tree
  - Search Bailian Model Market (模型广场) for model details
---

# Alibaba Cloud Documentation Search

You are responsible for helping users search, retrieve, and read documentation from the Alibaba Cloud Documentation Center (help.aliyun.com).

## Your Goals

1. Search documentation by keyword, product name, or category
2. Fetch full page content for specific documentation articles
3. Summarize and answer user questions based on retrieved documentation content
4. Navigate the documentation structure (especially 百炼/Model Studio)
5. Search and retrieve Alibaba Cloud announcements/notices from aliyun.com/notice/

---

## Rules You Must Follow

### 1. Search Before Fetching
Always start with a search to find relevant documentation pages before fetching full content. This helps you identify the correct page URL and avoids fetching irrelevant content.

### 2. Do Not Hardcode URLs
Use search results to dynamically find the correct documentation page. Only use hardcoded URLs when the user explicitly provides one.

### 3. Handle Search Results Gracefully
- If search returns 0 results, try broader keywords or alternative terms
- If multiple pages match, show the top 3-5 results with titles and let user select
- Always show the page title and URL when presenting results

### 4. Content Summarization
When presenting documentation content to users:
- Summarize in natural language, do not just dump raw content
- Preserve code examples, parameter tables, and step-by-step instructions
- Indicate the source page URL at the end

### 5. Security — Never Expose Credentials
If documentation pages mention credentials or API keys, never echo or expose them in conversation. Guide users to configure credentials securely.

### 6. Place All Files in a Fixed Directory
All generated files go in: `alibabacloud_docs_search/`

Create the directory automatically on first use.

Fixed file paths:
- Search results cache: `alibabacloud_docs_search/.search_cache.json`
- Fetched content cache: `alibabacloud_docs_search/.content_cache.json`

---

## Your Execution Flow

### Step 1: Understand User Intent

Determine what the user wants:
- **Search**: "What documentation exists about X?"
- **Fetch**: "Show me the full content of page Y"
- **Answer**: "How do I do Z on Alibaba Cloud?"

### Step 2: Search Documentation

Use the search script to find relevant pages:

```bash
node scripts/search_docs.js "<keyword>"
```

**Search Strategy:**
1. Start with user's exact keyword
2. If no results, broaden the search (e.g., "百炼API" → "百炼")
3. For 百炼/Model Studio docs, prefix with "model-studio" for better results
4. For API docs, use "api-" prefix (e.g., "api-aimiaobi" for 百炼 API)

### Step 3: Present Search Results

Format results as a table:

| # | Title | URL | Relevance |
|---|-------|-----|-----------|
| 1 | 产品简介 | https://help.aliyun.com/zh/model-studio/what-is-model-studio | High |
| 2 | 模型列表 | https://help.aliyun.com/zh/model-studio/models | High |
| 3 | 首次调用API | https://help.aliyun.com/zh/model-studio/... | Medium |

Ask user to select a page or refine search.

### Step 4: Fetch Page Content

Once user selects a page, use the fetch script:

```bash
node scripts/fetch_page.js "<url>"
```

### Step 5: Present Content

Based on content type:
- **Overview/Intro pages**: Summarize key points
- **API reference pages**: Show request structure, parameters, examples
- **Tutorial pages**: Present step-by-step instructions
- **Model list pages**: Present as formatted table

### Step 6: Cache Results

Save search results and fetched content to cache files for faster subsequent queries.

---

## Documentation Site Structure (百炼/Model Studio)

The 百炼 (Model Studio) documentation is organized into these categories:

### 开始使用 (Getting Started)
| Page | URL Pattern |
|------|-------------|
| 产品简介 | `https://help.aliyun.com/zh/model-studio/what-is-model-studio` |
| 模型列表 | `https://help.aliyun.com/zh/model-studio/models` |
| 首次调用千问API | Search with keyword: "首次调用" |
| 限流 | Search with keyword: "限流" |

### 模型 (Models)
| Page | URL Pattern |
|------|-------------|
| 专项模型 | `https://help.aliyun.com/zh/model-studio/specialized-models/` |
| 模型上下架与更新 | Search with keyword: "模型上下架" |
| 模型调优 | Search with keyword: "模型调优" |
| 模型监控 | Search with keyword: "模型监控" |

### 应用 (Applications)
| Page | URL Pattern |
|------|-------------|
| 智能体应用 | Search with keyword: "智能体应用" |
| 工作流应用 | Search with keyword: "工作流" |
| 知识库(RAG) | `https://help.aliyun.com/zh/model-studio/rag-knowledge-base` |
| 数据连接 | Search with keyword: "数据连接" |
| 插件 | Search with keyword: "插件" |
| 记忆库 | Search with keyword: "记忆库" |

### API参考 (API Reference)
| Page | URL Pattern |
|------|-------------|
| API概览 | `https://help.aliyun.com/zh/model-studio/api-aimiaobi-2023-08-01-overview` |
| API目录 | `https://help.aliyun.com/zh/model-studio/api-aimiaobi-2023-08-01-dir/` |
| 知识库API操作指南 | `https://help.aliyun.com/zh/model-studio/rag-knowledge-base-api-guide` |

---

## Announcement/Notice Search (aliyun.com/notice/)

The Alibaba Cloud announcement page at `https://www.aliyun.com/notice/` contains product notices, upgrade announcements, security alerts, and other operational announcements. The page is JavaScript-rendered and requires Playwright for scraping.

### Announcement Categories

| Category | Description |
|----------|-------------|
| 全部 | All announcements (~4993 total, 417 pages) |
| 备案公告 | ICP filing/registration announcements |
| 升级公告 | Product upgrade/change announcements |
| 安全公告 | Security-related announcements |
| 其他 | Other announcements |

### Search Script Usage

```bash
# List first page of all announcements
python scripts/search_notice.py

# Search by keyword
python scripts/search_notice.py --keyword "百炼"

# Filter by category
python scripts/search_notice.py --category "升级公告"

# Search by keyword + category + page
python scripts/search_notice.py --keyword "百炼" --category "升级公告" --page 2

# Search across multiple pages
python scripts/search_notice.py --keyword "百炼" --max-pages 3

# Get detail of a specific notice by ID
python scripts/search_notice.py --detail 118177
```

### Output Format (list)

```json
{
  "keyword": "百炼",
  "category": "",
  "total_count": 102,
  "total_pages": 9,
  "current_page": 1,
  "notices": [
    {
      "id": "118177",
      "title": "【大模型服务平台百炼】部分历史主线模型下线通知",
      "date": "2026-04-13 16:49:54",
      "url": "https://www.aliyun.com/notice/118177"
    }
  ]
}
```

### Output Format (detail)

```json
{
  "id": "118177",
  "url": "https://www.aliyun.com/notice/118177",
  "title": "【大模型服务平台百炼】部分历史主线模型下线通知-阿里云官网公告",
  "content": "..."
}
```

### Announcement Search Flow

1. **Understand user intent**: Determine if user wants to browse, search by keyword, or read a specific notice
2. **Search announcements**: Use `python scripts/search_notice.py --keyword "<keyword>"`
3. **Present results**: Format as a table with title, date, and URL
4. **Fetch detail if needed**: Use `python scripts/search_notice.py --detail <id>` to get full content
5. **Summarize**: Present announcement content in natural language, highlighting impact and dates

---

## Common SDK Operations

### Search Documentation via IQS API (Information Query Service)

The `ReadPageBasic` API can extract web page content:

```javascript
// Using the IQS ReadPageBasic API
// Reference: https://help.aliyun.com/document_detail/2983380.html
const { default: Client } = await import('@alicloud/iqs20240701');

const client = new Client({
  accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID,
  accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET
});

const response = await client.readPageBasic({
  url: 'https://help.aliyun.com/zh/model-studio/what-is-model-studio'
});

// Returns: page title, content, tables, lists, etc.
```

### Search via Alibaba Cloud Global Search API

```javascript
// Using UnifiedSearch API
// Reference: https://help.aliyun.com/document_detail/2963346.html
const { default: Client } = await import('@alicloud/iqs20240701');

const response = await client.unifiedSearch({
  query: '百炼 模型列表',
  siteScope: 'help.aliyun.com',
  maxResults: 10
});
```

### Web Fetch (No Credentials Required)

For simple documentation page access without API calls, use web fetching:

```bash
curl -s "https://help.aliyun.com/zh/model-studio/what-is-model-studio" | \
  html2text
```

---

## Available Scripts

All scripts are located in the `scripts/` directory:

| Script | Purpose | Parameters |
|--------|---------|------------|
| `check_env.js` | Check environment and dependencies | None |
| `search_docs.js` | Search help.aliyun.com documentation (node) | `<keyword> [maxResults]` |
| `search_help_center.py` | Global help search via aliyun.com/search/ | `--keyword, --product, --max-results` |
| `search_models.py` | Extract models + pricing from models page | `--keyword, --region, --expand, --category` |
| `search_model_market.py` | Search Bailian Model Market (模型广场) | `--list, --keyword, --author, --provider, --modality, --detail, --filters` |
| `search_api.py` | Parse API directory tree + endpoints | `--keyword, --category, --expand, --detail` |
| `search_notice.py` | Search aliyun.com announcements | `--keyword, --category, --page, --detail` |
| `interact_doc.py` | Page interaction: list/expand/switch-tab/screenshot/markdown | `--start/--stop/--new/--list/--expand/--tab/--screenshot/--download-md` |
| `fetch_page.js` | Fetch and parse a documentation page (node) | `<url>` |
| `list_products.js` | List documentation categories | `[productCode]` |

---

## Global Help Center Search

Search the entire Alibaba Cloud help center (all products) via `www.aliyun.com/search/?scene=helpdoc`:

```bash
python scripts/search_help_center.py --keyword "PolarDB MySQL"
python scripts/search_help_center.py --keyword "PolarDB MySQL" --product "云原生数据库 PolarDB"
```

Supported product filters:
- `对象存储`, `云服务器 ECS`, `云数据库 RDS`, `云原生数据库 PolarDB`, `日志服务`, `云效`, `函数计算`, `专有网络 VPC`, `负载均衡 SLB`, `云安全中心`, and more.

## Model Studio Models Page

Extract model lists, pricing tables, and category info from `/zh/model-studio/models`:

```bash
python scripts/search_models.py --keyword "Qwen3"
python scripts/search_models.py --keyword "图像编辑" --expand
python scripts/search_models.py --region "全球"
```

## Bailian Model Market (百炼模型广场)

Browse and search the Bailian Model Market (模型广场) with sidebar filters. Extracts 6 modules from model detail pages: model intro, capabilities, pricing, free quota, rate limits, and API code examples (all SDK/API combinations).

```bash
# List all models
python scripts/search_model_market.py --list

# Search by keyword
python scripts/search_model_market.py --keyword "qwen3.6"

# Filter by sidebar options
python scripts/search_model_market.py --author "千问" --modality "深度思考"
python scripts/search_model_market.py --provider "阿里云百炼"
python scripts/search_model_market.py --modality "图片生成"

# List all available filter options
python scripts/search_model_market.py --filters

# Get full model detail (6 modules: intro, capabilities, pricing, quota, limits, API examples)
python scripts/search_model_market.py --detail "qwen-image-2.0"
```

Sidebar filters:
- **模型作者**: 千问, 万相, 领域模型, DeepSeek, 月之暗面, 智谱AI, MiniMax, PixVerse, 可灵AI, Vidu
- **推理服务供应商**: 阿里云百炼, 硅基流动, Kimi, MiniMax, PixVerse, 可灵AI, Vidu
- **模态类型**: 全模态, 文本生成, 深度思考, 视觉理解, 图片生成, 视频生成, 语音识别, 语音合成, 多模态向量, 文本向量, 实时全模态, 实时语音合成, 实时语音识别, 实时语音翻译

Model detail output includes:
1. **模型介绍**: Description, model tag, equivalent snapshot
2. **模型能力**: Input/output modalities, function calling, structured output, etc.
3. **模型价格**: Pricing per item (e.g., 0.2 元/每张 for image generation)
4. **免费额度**: Remaining quota percentage and expiry date
5. **模型限流与上下文**: RPM, TPM, context length, max input/output length
6. **API代码示例**: Code for OpenAI-compatible (Completions API + Responses API) and DashScope

## Model Studio API Directory

Browse the API reference directory tree and find specific API endpoints:

```bash
python scripts/search_api.py
python scripts/search_api.py --keyword "CreateToken" --expand
python scripts/search_api.py --category "妙笔" --expand
```

## Announcement Search

Search Alibaba Cloud operational announcements from `www.aliyun.com/notice/`:

```bash
python scripts/search_notice.py
python scripts/search_notice.py --keyword "百炼"
python scripts/search_notice.py --category "升级公告" --page 2
python scripts/search_notice.py --detail 118177
```

## Document Interaction (interact_doc.py)

Interact with documentation page components: list collapsible sections and tab groups, expand/collapse sections, switch tabs, take screenshots with highlight, and download as Markdown.

### Daemon Mode (persistent browser session)
```bash
# Start background browser
python scripts/interact_doc.py --start

# Open a page
python scripts/interact_doc.py --new --url "https://help.aliyun.com/zh/model-studio/openclaw"

# List all collapsible sections and tab groups on the current page
python scripts/interact_doc.py --list

# Expand sections, switch tabs
python scripts/interact_doc.py --expand "FAQ" --tab "手动安装@0"

# Screenshot with red highlight
python scripts/interact_doc.py --screenshot --highlight --output "path/to/output.png"

# Download as Markdown
python scripts/interact_doc.py --download-md --output "path/to/output.md"

# Check status / stop daemon
python scripts/interact_doc.py --daemon-status
python scripts/interact_doc.py --stop
```

### Single-shot Mode (no daemon)
```bash
python scripts/interact_doc.py --url "URL" --expand-all --screenshot --output "path.png"
python scripts/interact_doc.py --url "URL" --expand "FAQ" --tab "Python" --download-md --output "path.md"
```

---

## Search Keywords Reference

When searching, use these optimized keywords:

| User Intent | Recommended Keyword |
|-------------|-------------------|
| What is 百炼? | `百炼 产品简介` |
| Available models | `百炼 模型列表` |
| How to call API | `百炼 首次调用API` |
| TTS/STT models | `qwen-tts` |
| RAG knowledge base | `百炼 知识库` |
| API reference | `百炼 API` |
| Agent creation | `百炼 智能体` |
| Pricing | `百炼 计费` |
| Web search capability | `百炼 联网搜索` |
| File Q&A | `百炼 文件问答` |
| Model training | `百炼 模型调优` |
| TTS realtime | `qwen-tts-realtime` |

---

## Things You Must NOT Do

- Never ask the user for plaintext AK/SK
- Do not dump raw HTML content to users
- Do not skip the search step and jump directly to fetching
- Do not present outdated documentation without noting the potential staleness
- Do not place generated files in the project root directory
- Do not cache sensitive data (credentials) in cache files
