# myai-llm-python 模块说明

## 模块定位

`myai-llm-python/` 是 MyAI 项目的智能体层，主要负责：

- 聊天回复生成
- 带上下文的会话支持
- 长期记忆写入与检索
- 个人知识库文件解析、向量检索与 RAG
- 任务识别、规划、工具调用与多步任务编排
- 大模型与 embedding 的使用

它是整个项目的智能核心。

## 主要目录

```text
myai-llm-python/
├─ app/api/        # 对外接口
├─ app/context/    # 短期上下文管理
├─ app/core/       # 对话主流程
├─ app/knowledge/  # 个人知识库模块
├─ app/memory/     # 长期记忆模块
├─ app/model/      # 模型与 embedding 配置
├─ app/prompt/     # Prompt 构建
├─ app/schemas/    # 请求与响应模型
├─ app/task/       # 任务规划与工具执行模块
└─ tests/          # Python 测试
```

## 子模块说明

### 1. `api/`

对外暴露 FastAPI 接口：

- `/chat`
- `/memory/write`
- `/memory/query`
- `/memory/list/{user_id}`
- `/memory/{user_id}/{memory_id}`
- `/knowledge/upload`
- `/knowledge/query`
- `/knowledge/files/{user_id}`
- `/knowledge/files/{user_id}/{file_id}`
- `/task`

作用：

- 接收 Java 侧转发来的请求
- 把请求分发到聊天、记忆、知识库、任务四个能力模块

### 2. `core/`

定义聊天主流程。

当前流程包括：

1. 接收用户输入
2. 装载传入的历史会话消息
3. 判断是否需要任务工具
4. 写入长期记忆
5. 检索相关长期记忆
6. 检索相关知识库片段
7. 读取短期上下文
8. 构建 Prompt
9. 调用聊天模型生成回复
10. 将用户消息和助手回复写回短期上下文

这意味着各模块已经融合进聊天主链路；同时，旧会话也可以通过历史消息恢复对话上下文。

### 3. `context/`

负责短期上下文管理。

当前实现特点：

- 以内存方式保存会话
- 支持按 `user_id:conversation_id` 区分不同会话上下文
- 支持装载 Java 侧传入的历史消息
- 同时保存 `user` 和 `assistant` 双边消息
- 支持按轮次裁剪上下文

### 4. `memory/`

负责长期记忆的完整生命周期。

包含能力：

- 记忆候选筛选
- 记忆写入
- 向量化表示
- Chroma 向量存储
- 相似检索
- 去重、衰减、冲突处理
- 记忆列表获取
- 记忆删除

当前已支持：

- 中文与英文规则抽取
- Stub 与真实 embedding 可切换
- 不同 embedding 配置对应不同 Chroma collection
- 在上层页面中按类型组织为“记忆画像”

### 5. `knowledge/`

负责个人知识库 / RAG。

主要能力：

- 文件解析
  - `TXT`
  - `PDF`
  - `DOCX`
- 文本切块
- chunk 向量化
- Chroma 向量入库
- 用户级文件索引管理
- 摘要生成
- 语义检索
- 按文件筛选检索

实现方式：

- `parser.py` 负责不同文件格式的文本提取
- `chunker.py` 负责把长文本切分为适合检索的 chunk
- `service.py` 负责上传、索引、查询、删除等主流程

知识库既可以单独使用，也可以通过 `core/` 融合进聊天回答。

### 6. `task/`

负责任务识别、规划、执行、统计与多步编排。

主要组件：

- `tool/`：工具抽象与注册
- `tools/`：具体工具实现
- `plan/`：规划、校验、恢复、执行计划结构
- `service/`：任务调度与步骤执行
- `stats/`：任务决策记录与统计

当前特点：

- 支持单步任务工具调用
- 支持规则型多步任务模板
- 支持 LLM 输出多步 `steps`
- 支持步骤顺序执行
- 支持前一步结果写入上下文并传递给后一步
- 支持最终汇总输出

当前已实现的多步任务示例：

- 获取时间 -> 计算距离晚上 8 点还有多久
- 文本统计 -> 估算阅读时间
- 获取系统信息 -> 汇总输出

### 7. `model/`

负责生成模型与 embedding 配置工厂。

当前支持：

- `StubLLM`
- `VolcengineLLM`
- 本地 `OpenAICompatibleLLM`（适配 Ollama、vLLM、LM Studio 等兼容端点）
- `StubEmbedding`
- 火山引擎与本地 OpenAI-compatible embedding 客户端

实现方式：

- 环境变量读取配置
- 工厂统一创建实例
- 支持 `chat`、`task`、`embedding` 使用不同 provider / model_id

## 记忆画像设计

记忆画像在当前项目中采用“复用记忆底层、增加管理接口与可视化层”的设计：

- 不新增新的画像存储
- 直接复用现有长期记忆数据
- 通过记忆列表接口获取当前有效记忆
- 按记忆类型组织成偏好、事实、计划、观点、其他
- 提供删除接口实现用户可控记忆管理

这样设计的好处是：

- 与现有写入、查询流程自然衔接
- 不会破坏原有记忆模块结构
- 更适合在前端直接做画像可视化展示

## 多步任务链设计

多步任务链在当前项目中采用“兼容单步、扩展多步”的设计：

- 原有单步 `tool_name + tool_args` 仍然保留
- 新增 `steps` 数组表示多步任务计划
- 每个 step 包含：
  - `step_id`
  - `description`
  - `tool_name`
  - `tool_args`
  - `output_key`
  - `extract_path`

执行时：

1. 规划器生成单步或多步计划
2. 校验器检查每一步工具和参数是否合法
3. 调度器顺序执行每一个 step
4. 执行结果写入上下文
5. 后续 step 通过占位符引用中间结果
6. 最终生成 `summary`

这套设计保证了：

- 不破坏原有单步工具调用
- 便于后续扩展更多规则模板
- 便于接入更强的 LLM 多步规划
- 便于前端可视化展示执行过程

## 对话历史协同设计

对话历史功能采用“Java 负责持久化，Python 负责上下文恢复”的协同方式：

- Java 侧在 MySQL 中保存 `conversation` 与 `chat_message`
- Java 侧在发起聊天请求时附带最近历史消息
- Python 侧通过 `chat_request.history` 接收历史内容
- `context/` 将历史消息加载到当前会话上下文
- 新生成的用户消息和助手回复继续写回对应会话上下文

这样设计的好处是：

- 会话历史作为业务数据长期保存
- Python 不需要独立维护永久会话存储
- 旧会话重新打开时仍能保持较好的上下文连续性

## 当前模型配置

### 生成模型

通过 `.env` 控制：

- `MYAI_CHAT_PROVIDER`
- `MYAI_TASK_PROVIDER`
- `MYAI_MEMORY_PROVIDER`
- `MYAI_CHAT_MODEL_ID`
- `MYAI_TASK_MODEL_ID`
- `MYAI_MEMORY_MODEL_ID`

### 记忆 LLM 抽取

通过 `.env` 控制：

- `MYAI_MEMORY_LLM_EXTRACTOR_ENABLED`
- `MYAI_MEMORY_PROVIDER`
- `MYAI_MEMORY_MODEL_ID`

默认关闭。开启后，记忆写入会先走规则抽取；规则未命中时，再调用 memory 角色模型进行结构化记忆抽取。

启用真实 memory 模型后，可以运行校准集：

```powershell
.\.venv\Scripts\python.exe -m app.memory.evaluation.calibrate --output .\calibration-report.json
```

使用 `--strict` 可以在任意校准案例失败时返回非零退出码。

### Embedding 模型

通过 `.env` 控制：

- `MYAI_EMBEDDING_PROVIDER`
- `MYAI_EMBEDDING_MODEL_ID`

### 本地 OpenAI-compatible 模型

将对应 provider 设置为 `openai_compatible`，并指定服务端实际加载的模型名：

```dotenv
MYAI_CHAT_PROVIDER=openai_compatible
MYAI_TASK_PROVIDER=openai_compatible
MYAI_MEMORY_PROVIDER=openai_compatible
MYAI_EMBEDDING_PROVIDER=openai_compatible
MYAI_CHAT_MODEL_ID=qwen2.5:7b
MYAI_TASK_MODEL_ID=qwen2.5:7b
MYAI_MEMORY_MODEL_ID=qwen2.5:7b
MYAI_EMBEDDING_MODEL_ID=nomic-embed-text
MYAI_OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:11434/v1
MYAI_OPENAI_COMPATIBLE_EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
MYAI_EMBEDDING_EXPECTED_DIMENSIONS=768
```

API key 对本地服务是可选的。默认地址仅绑定回环接口，若显式配置远程地址，应同时配置传输安全和访问凭证。

为了让毕业设计实验暴露真实失败而不是静默使用 Stub，应固定以下参数并关闭降级：

```dotenv
MYAI_LLM_FALLBACK_TO_STUB=false
MYAI_LLM_TEMPERATURE=0
MYAI_LLM_SEED=42
MYAI_LLM_MAX_TOKENS=512
MYAI_LLM_REQUEST_TIMEOUT_SECONDS=30
MYAI_LLM_MAX_RETRIES=0
MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS=30
MYAI_EMBEDDING_MAX_RETRIES=0
```

`MYAI_EMBEDDING_EXPECTED_DIMENSIONS` 大于 0 时，系统会拒绝空向量、NaN/Infinity 和维度不匹配的响应，避免污染长期索引。

真实 embedding provider 始终采用 fail-closed（状态接口显示为 `real_fail_closed`）：请求失败会直接报错，不会把 Stub 向量写入真实模型的持久化 collection。只有显式设置 `MYAI_EMBEDDING_PROVIDER=stub` 时才使用 StubEmbedding，并应为它保留独立、可丢弃的索引。

### 密钥

- `ARK_API_KEY`
- `MYAI_OPENAI_COMPATIBLE_API_KEY`（本地服务通常可留空）

示例文件：

- `.env.example`

## 运行说明

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

## 测试说明

当前已有 Python 接口测试，覆盖：

- 聊天接口
- 记忆写入与查询
- 记忆列表与删除
- 知识库上传与检索
- 单步任务工具调用
- 规则型多步任务链
- LLM 多步计划解析

测试文件：

- `tests/test_api.py`

运行命令：

```bash
python -m unittest tests.test_api -v
```

## 在整体系统中的作用

`myai-llm-python` 模块是 MyAI 的“智能核心”。

它决定了系统是否具备：

- 大模型对话能力
- 会话历史恢复后的连续对话能力
- 长期记忆能力 （记忆画像与记忆可控删除能力）
- 个人知识库问答与 RAG 能力
- 任务规划与工具执行能力
- 后续扩展更复杂 Agent 能力的基础

---

# myai-llm-python Module Guide

## Module Positioning

`myai-llm-python/` is the agent and intelligence layer of the MyAI project. It is mainly responsible for:

- Chat response generation
- Context-aware conversation support
- Long-term memory writing and retrieval
- Personal knowledge base parsing, vector retrieval, and RAG
- Task recognition, planning, tool calling, and multi-step orchestration
- LLM and embedding model integration

It is the intelligence core of the whole system.

## Main Directories

```text
myai-llm-python/
├─ app/api/        # External API endpoints
├─ app/context/    # Short-term context management
├─ app/core/       # Main chat workflow
├─ app/knowledge/  # Personal knowledge base module
├─ app/memory/     # Long-term memory module
├─ app/model/      # LLM and embedding configuration
├─ app/prompt/     # Prompt construction
├─ app/schemas/    # Request and response schemas
├─ app/task/       # Task planning and tool execution
└─ tests/          # Python tests
```

## Submodules

### 1. `api/`

This package exposes FastAPI endpoints:

- `/chat`
- `/memory/write`
- `/memory/query`
- `/memory/list/{user_id}`
- `/memory/{user_id}/{memory_id}`
- `/knowledge/upload`
- `/knowledge/query`
- `/knowledge/files/{user_id}`
- `/knowledge/files/{user_id}/{file_id}`
- `/task`

Responsibilities:

- Receive requests forwarded from the Java service
- Dispatch requests to chat, memory, knowledge base, and task modules

### 2. `core/`

This package defines the main chat workflow.

The current workflow includes:

1. Receive user input
2. Load conversation history passed from the Java service
3. Determine whether task tools are needed
4. Write long-term memory
5. Retrieve relevant long-term memories
6. Retrieve relevant knowledge base fragments
7. Read short-term context
8. Build the prompt
9. Call the chat model to generate a reply
10. Write the user message and assistant reply back to short-term context

This means memory, knowledge retrieval, task detection, and context management are all integrated into the chat path. Old conversations can also recover useful context through history messages.

### 3. `context/`

This package manages short-term conversation context.

Current characteristics:

- Stores conversations in memory
- Separates contexts by `user_id:conversation_id`
- Loads history messages passed from the Java service
- Stores both `user` and `assistant` messages
- Supports trimming by recent turns

### 4. `memory/`

This package manages the full lifecycle of long-term memory.

Capabilities:

- Memory candidate filtering
- Memory writing
- Vector representation
- Chroma vector storage
- Similarity retrieval
- Deduplication, decay, and conflict handling
- Memory list retrieval
- Memory deletion

Currently supported:

- Chinese and English rule-based extraction
- Switchable stub and real embedding providers
- Separate Chroma collections for different embedding configurations
- Memory profile display grouped by type in the upper Web layer

### 5. `knowledge/`

This package implements the personal knowledge base and RAG workflow.

Main capabilities:

- File parsing for `TXT`, `PDF`, and `DOCX`
- Text chunking
- Chunk embedding
- Chroma vector indexing
- User-level file index management
- Summary generation
- Semantic retrieval
- Retrieval filtered by file

Implementation:

- `parser.py` extracts text from different file formats
- `chunker.py` splits long text into retrieval-friendly chunks
- `service.py` handles upload, indexing, query, and deletion workflows

The knowledge base can be used independently or integrated into chat responses through `core/`.

### 6. `task/`

This package handles task recognition, planning, execution, statistics, and multi-step orchestration.

Main components:

- `tool/`: tool abstraction and registry
- `tools/`: concrete tool implementations
- `plan/`: planning, validation, recovery, and execution plan structures
- `service/`: task dispatching and step execution
- `stats/`: task decision records and statistics

Current characteristics:

- Supports single-step tool calls
- Supports rule-based multi-step task templates
- Supports LLM-generated multi-step `steps`
- Executes steps sequentially
- Passes previous step results through context
- Produces a final summary

Example multi-step tasks:

- Get current time -> calculate how long until 8 PM
- Count text -> estimate reading time
- Get system information -> summarize the result

### 7. `model/`

This package provides factories and configuration for generation models and embedding models.

Currently supported:

- `StubLLM`
- `VolcengineLLM`
- Local `OpenAICompatibleLLM` for Ollama, vLLM, LM Studio, and compatible servers
- `StubEmbedding`
- Volcengine and local OpenAI-compatible embedding clients

Implementation:

- Reads configuration from environment variables
- Creates model instances through factories
- Allows `chat`, `task`, and `embedding` to use different providers and model IDs

## Memory Profile Design

The memory profile reuses the existing memory layer and adds management and visualization on top:

- No separate profile storage is introduced
- Existing long-term memory data is reused directly
- The memory list API returns all active memories for the current user
- Memories are grouped by type, such as preference, fact, plan, opinion, and other
- Users can delete unwanted or incorrect memories

Benefits:

- Naturally fits the existing write and retrieval workflow
- Does not break the existing memory module structure
- Makes it easy for the frontend to present a visual memory profile

## Multi-Step Task Chain Design

The multi-step task chain extends the original single-step tool calling design while keeping it compatible.

- The original `tool_name + tool_args` format is preserved
- A new `steps` array represents a multi-step task plan
- Each step contains:
  - `step_id`
  - `description`
  - `tool_name`
  - `tool_args`
  - `output_key`
  - `extract_path`

Execution process:

1. The planner generates a single-step or multi-step plan
2. The validator checks whether each tool and its arguments are valid
3. The dispatcher executes each step in order
4. Step results are written into context
5. Later steps can reference previous results through placeholders
6. A final `summary` is generated

This design:

- Preserves compatibility with existing single-step tool calls
- Makes it easy to add more rule-based templates
- Makes it possible to integrate stronger LLM-based planning later
- Allows the frontend to visualize the execution process

## Conversation History Collaboration Design

Conversation history uses a collaborative design: Java handles persistence, while Python handles context recovery.

- The Java side stores `conversation` and `chat_message` in MySQL
- The Java side attaches recent history messages when sending chat requests
- The Python side receives history through `chat_request.history`
- `context/` loads history into the current conversation context
- Newly generated user messages and assistant replies are written back into the corresponding context

Benefits:

- Conversation history is persisted as business data
- Python does not need a separate permanent conversation database
- Reopened conversations can still maintain useful contextual continuity

## Current Model Configuration

### Generation Models

Configured through `.env`:

- `MYAI_CHAT_PROVIDER`
- `MYAI_TASK_PROVIDER`
- `MYAI_CHAT_MODEL_ID`
- `MYAI_TASK_MODEL_ID`

### Embedding Models

Configured through `.env`:

- `MYAI_EMBEDDING_PROVIDER`
- `MYAI_EMBEDDING_MODEL_ID`

### Local OpenAI-compatible Models

Set the relevant providers to `openai_compatible`. The default endpoint is
`http://127.0.0.1:11434/v1`; a local API key is optional. Configure
`MYAI_LLM_SEED`, `MYAI_LLM_MAX_TOKENS`, request timeouts, and
`MYAI_EMBEDDING_EXPECTED_DIMENSIONS` explicitly for reproducible experiments.
Set `MYAI_LLM_FALLBACK_TO_STUB=false` so experiment failures are recorded rather
than silently replaced by Stub output.
Real embedding providers always fail closed (`effective_mode=real_fail_closed`)
regardless of that LLM setting; select
`MYAI_EMBEDDING_PROVIDER=stub` explicitly only for a separate disposable index.

### Secrets

- `ARK_API_KEY`
- `MYAI_OPENAI_COMPATIBLE_API_KEY` (usually optional for a local server)

Example file:

- `.env.example`

## Run

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Start the Service

```bash
uvicorn app.main:app --reload --port 8000
```

## Tests

The existing Python API tests cover:

- Chat endpoint
- Memory writing and querying
- Memory list and deletion
- Knowledge base upload and retrieval
- Single-step task tool calls
- Rule-based multi-step task chains
- LLM multi-step plan parsing

Test file:

- `tests/test_api.py`

Run:

```bash
python -m unittest tests.test_api -v
```

## Role in the Whole System

`myai-llm-python` is the intelligence core of MyAI.

It provides the foundation for:

- LLM-based chat
- Continuous conversation after history recovery
- Long-term memory, including memory profile and controllable deletion
- Personal knowledge base Q&A and RAG
- Task planning and tool execution
- Future expansion into more complex agent capabilities

