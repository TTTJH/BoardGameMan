# Board Game Rulebook AI Assistant 项目实现讲解

这份文档按“用户操作之后系统内部发生了什么”的顺序，解释当前项目的主要业务逻辑和技术实现流程。

## 整体定位

这个项目是一个“桌游规则书 AI 助手”。

用户主要操作流程：

1. 创建一个桌游条目。
2. 上传该桌游的 PDF 规则书。
3. 系统解析 PDF，把规则书切成可检索的小段。
4. 用户提问。
5. 系统先从规则书里找相关片段，再把这些片段交给大模型回答。
6. 前端展示 AI 回答和对应来源。

它本质上是一个典型的 RAG 应用：Retrieval-Augmented Generation，检索增强生成。

## 技术栈

前端目录：

```text
D:\Code\boardGameMan\frontend
```

前端主要技术：

- React
- Vite
- Zustand 做前端状态管理
- Axios 请求后端
- Tailwind/CSS 做 UI

后端目录：

```text
D:\Code\boardGameMan\backend
```

后端主要技术：

- FastAPI
- SQLite 数据库
- PDF 解析使用 `pdfplumber` / `PyPDF2`
- 文本切块和检索逻辑主要由项目自己实现
- OpenAI-compatible API 调用大模型
- Pillow 用于生成默认封面图

## 核心数据表

数据库初始化逻辑在：

```text
D:\Code\boardGameMan\backend\app\database.py
```

主要表：

- `games`
  存桌游条目，包括名称、描述、封面 URL。

- `documents`
  存上传的 PDF 文件信息，包括文件名、文件路径、页数、状态。

- `chunks`
  存 PDF 被切出来的文本片段。AI 回答不是直接读整个 PDF，而是先检索这些 chunk。

- `chunk_embeddings`
  如果配置了 embedding，会存每个 chunk 的向量，用于语义检索。

- `chat_history`
  存用户问题、AI 回答、引用来源。

- `app_settings`
  存模型配置，比如 chat model、embedding model、API key、API base。

## 创建桌游流程

前端入口：

```text
D:\Code\boardGameMan\frontend\src\components\GameList.jsx
```

用户点击 `Add Game` 后：

1. 前端调用 `gamesAPI.create`。
2. API 定义在：

```text
D:\Code\boardGameMan\frontend\src\api\client.js
```

3. 请求到后端：

```text
POST /api/games/
```

对应文件：

```text
D:\Code\boardGameMan\backend\app\routes\games.py
```

4. 后端往 `games` 表插入一条记录。
5. 同时为该游戏创建一个向量集合，或者在当前 fallback 模式下跳过 Chroma 集合创建。
6. 返回新的 game。
7. 前端 Zustand store 把它放进 `games` 列表。

前端全局状态在：

```text
D:\Code\boardGameMan\frontend\src\store\index.js
```

## 上传 PDF 流程

前端组件：

```text
D:\Code\boardGameMan\frontend\src\components\DocumentUpload.jsx
```

用户上传 PDF 后：

1. 前端调用 `documentsAPI.upload(gameId, file)`。
2. 后端进入：

```text
POST /api/documents/{game_id}/upload
```

对应文件：

```text
D:\Code\boardGameMan\backend\app\routes\documents.py
```

3. 后端检查 game 是否存在。
4. 检查文件是不是 PDF。
5. 把 PDF 保存到：

```text
D:\Code\boardGameMan\backend\uploads
```

6. 调用 PDF 解析服务：

```text
D:\Code\boardGameMan\backend\app\services\pdf_processor.py
```

7. 用 `TextChunker.clean_text` 清理 PDF 噪声。
8. 用 `TextChunker.chunk_text` 按页面、标题、段落切成 chunks。
9. 把 PDF 信息写入 `documents` 表。
10. 把 chunks 写入 `chunks` 表。
11. 如果 embedding 配置可用，把 chunks 写入向量存储。
12. 如果该游戏还没有封面，调用默认封面生成器：

```text
D:\Code\boardGameMan\backend\app\services\cover_generator.py
```

13. 返回文档信息。
14. 前端再拉一次 `gamesAPI.get(gameId)`，刷新封面。

关键点：PDF 不是每次问问题时重新解析。上传时已经解析并切块，之后提问只查数据库里的 chunks。

## AI 问答流程

用户提问发生在：

```text
D:\Code\boardGameMan\frontend\src\components\ChatBox.jsx
```

流程：

1. 前端调用 `chatAPI.ask(gameId, message)`。
2. 后端进入：

```text
POST /api/chat/{game_id}/ask
```

对应文件：

```text
D:\Code\boardGameMan\backend\app\routes\chat.py
```

3. 后端先查这个 game 是否存在。
4. 调用检索服务：

```text
D:\Code\boardGameMan\backend\app\services\vector_store.py
```

核心方法：

```python
search(game_id, query, top_k=8)
```

5. 检索出最相关的规则书片段。
6. 把这些片段交给 AI 服务：

```text
D:\Code\boardGameMan\backend\app\services\ai_service.py
```

7. `AIService.generate_response` 组装 system prompt。
8. 调用大模型生成回答。
9. 从回答里识别 `Document N` 引用。
10. 把问答和 sources 写入 `chat_history`。
11. 返回给前端展示。

也就是说，AI 并不是直接“知道规则”。它回答前会先拿到类似这样的上下文：

```text
[Document 1]
[Page 8] ...
Whenever a player places the final tile...

[Document 2]
[Page 8] ...
The first player who manages to completely cover all spaces...
```

然后大模型基于这些片段回答。

## 检索为什么重要

勃艮第规则问题的错误，本质就是检索层的问题。

如果用户问：

```text
填满某一种颜色的所有板块奖励是什么？
```

系统需要把中文问题映射到英文规则书里的关键词：

```text
complete
completed area
colored area
all spaces of one color
duchy
large bonus tile
small bonus tile
victory points
```

如果检索没把正确页面找出来，或者找出来但排在后面，模型就容易基于错误片段回答。

所以 `vector_store.py` 是后端最关键的业务逻辑之一。它负责：

- 中文关键词扩展
- 英文关键词匹配
- BM25 风格文本评分
- embedding 语义相似度评分
- 两种分数合并
- 根据问题类型重新排序
- 把命中的 chunk 和相邻 chunk 拼起来，给模型更多上下文

## 当前检索实现

目前项目支持两种模式：

1. ChromaDB 可用时，用 Chroma 做向量数据库。
2. ChromaDB 不可用时，用 SQLite fallback。

当前日志里有：

```text
ChromaDB is not installed; using SQLite hybrid search fallback
```

所以现在主要走 SQLite fallback。

SQLite fallback 大概是：

1. 从 `chunks` 表取出某个游戏的所有 chunk。
2. 对用户问题做 query expansion。
3. 用 BM25 风格算法算关键词分。
4. 如果有 embedding，就算向量相似度。
5. 合并关键词分和向量分。
6. 根据问题类型加减分。
7. 取 top results。
8. 给每个命中 chunk 加上前后相邻 chunk，避免上下文断裂。

## 封面生成流程

封面生成器：

```text
D:\Code\boardGameMan\backend\app\services\cover_generator.py
```

它不是 AI 绘图模型，而是本地程序生成。

流程：

1. PDF 上传完成后，拿解析出的文本。
2. 根据关键词判断规则书主题，比如：
   - Fantasy Adventure
   - Dark Fantasy
   - Science Fiction
   - Mystery
   - Historical Strategy
   - Economic Strategy
3. 再判断机制，比如：
   - Cooperative
   - Campaign
   - Deck Building
   - Area Control
   - Exploration
4. 根据主题选择色板和图形元素。
5. 用 Pillow 画背景、纹理、边框、图形、标题。
6. 保存成 PNG。
7. 写入 `games.cover_url`。

## 前端状态流

前端状态集中在：

```text
D:\Code\boardGameMan\frontend\src\store\index.js
```

主要有三个 store：

- `useGameStore`
  管游戏列表、当前游戏、更新游戏封面等。

- `useDocumentStore`
  管当前游戏上传过的 PDF 列表。

- `useChatStore`
  管聊天消息。

比如上传 PDF 后，前端会：

```js
setDocuments([response.data, ...documents])
const gameResponse = await gamesAPI.get(gameId)
updateGame(gameResponse.data)
```

这样自动生成的封面才能马上显示出来。

## 整体流程图

```text
PDF
 -> 文本解析
 -> 清洗
 -> 切块
 -> 入库
 -> 用户提问
 -> 检索相关 chunk
 -> 把 chunk 塞给大模型
 -> 大模型基于 chunk 回答
 -> 展示 sources
```

## 最容易出错的地方

1. PDF 解析质量不好

   比如文字顺序乱、表格混杂、页边说明插进正文。

2. 检索没找准

   比如中文问题没映射到英文规则词，或者泛词太多导致错误片段排前面。

3. 模型推理混淆

   比如两个规则同时触发，模型只说了一个，还否定另一个。

勃艮第那个问题就是第 2 和第 3 类问题叠加：正确规则片段在 PDF 中存在，但检索和回答提示没有足够稳定地区分“完成一个区域”和“填满某一种颜色全部空格”这两个相关但不同的规则对象。
