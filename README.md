# CodeMind Agent - 第一阶段 MVP

基于 RAG 的代码仓库智能问答系统。

## 快速开始

### 1. 环境准备

```bash
conda activate AI

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的阿里云百炼 API Key
# DASHSCOPE_API_KEY=sk-...
```

### 3. 配置仓库路径

在 `config.yml` 中设置要索引的仓库路径：

```yaml
repo:
  path: "/path/to/your/git/repo"  # 或使用 "." 索引本项目
```

### 4. 索引代码仓库

```bash
# 使用 config.yml 中配置的 repo.path
python scripts/index_repo.py

# 或者直接指定路径（覆盖 config 中的配置）
python scripts/index_repo.py /path/to/your/git/repo
```

### 5. 启动服务

### 6. 启动服务

```bash
python app.py
```

或使用 uvicorn：

```bash
uvicorn app:app --reload
```

### 7. API 调用

服务默认运行在 `http://localhost:8000`

#### 方式一：Swagger UI（推荐）

浏览器打开: http://localhost:8000/docs

- 点击 `/chat` 接口
- 点击 "Try it out"
- 输入请求体：
  ```json
  {
    "question": "这个项目的主要功能是什么？"
  }
  ```
- 点击 "Execute" 查看响应

#### 方式二：curl 命令

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "这个项目的主要功能是什么？"}'
```

#### 方式三：Python requests

```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={"question": "这个项目的主要功能是什么？"}
)
result = response.json()
print("回答:", result["answer"])
print("来源:", [s["source"] for s in result["sources"]])
```

#### 方式四：JavaScript (fetch)

```javascript
fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question: '这个项目的主要功能是什么？' })
})
  .then(res => res.json())
  .then(data => {
    console.log('回答:', data.answer);
    console.log('来源:', data.sources.map(s => s.source));
  });
```

### API 响应格式

```json
{
  "answer": "这是AI生成的回答...",
  "sources": [
    {
      "source": "C:\\path\\to\\file.py",
      "content": "相关代码片段内容..."
    }
  ]
}
```

### 其他接口

- `GET /health` - 健康检查
