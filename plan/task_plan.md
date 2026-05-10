# 方案一：RRF融合 - 实施计划

## 目标
快速添加BM25检索并使用RRF（Reciprocal Rank Fusion）算法融合向量检索和BM25检索结果，验证混合检索的效果。

## 核心原理
- RRF公式：`score(d) = sum(1 / (k + rank_i(d)))`，通常 k=60
- Code和Doc分别进行混合检索后再汇总
- 可选：对匹配查询标识符的代码块进行加分

## 阶段划分

### 阶段1：创建BM25索引模块
**状态**: pending
**文件**: `utils/bm25_index.py`

创建BM25索引类，功能包括：
- 使用`rank_bm25`库构建索引
- 支持持久化到磁盘（pickle格式）
- 支持按metadata filter（type=code/doc）检索
- 代码和文档分开检索

### 阶段2：创建融合算法模块
**状态**: pending
**文件**: `utils/fusion.py`

创建融合算法：
- RRF融合实现
- 结果去重（基于source + content hash）
- 标识符提取和加分逻辑

### 阶段3：更新索引脚本
**状态**: pending
**文件**: `scripts/index_repo.py`

修改索引脚本：
- 在构建Chroma索引的同时构建BM25索引
- BM25索引与Chroma索引使用相同的chunks
- BM25索引保存路径配置化

### 阶段4：更新服务管理器
**状态**: pending
**文件**: `services/service_manager.py`

更新ServiceManager：
- 添加BM25索引加载
- 添加融合策略配置
- 暴露BM25检索接口

### 阶段5：更新检索工具
**状态**: pending
**文件**: `agent/tools/retrieve_and_summarize.py`

修改检索工具：
- 同时执行向量检索和BM25检索
- 使用RRF融合结果
- 保持code/doc分开检索的逻辑
- 替换TODO注释

### 阶段6：更新配置文件
**状态**: pending
**文件**: `config.yml`

添加新配置项：
- BM25索引路径
- 检索k值配置（向量和BM25）
- RRF参数
- 开关控制（可切换纯向量/混合检索）

### 阶段7：添加依赖
**状态**: pending
**文件**: `requirements.txt`

添加：
- `rank-bm25>=0.2.2`

### 阶段8：测试验证
**状态**: pending

验证功能：
- 索引构建正常
- BM25检索结果有意义
- 混合检索结果优于纯向量
- 无性能回退

## 架构设计

### 新增文件
```
utils/
├── bm25_index.py    # BM25索引类
└── fusion.py        # 融合算法

# 配置新增
bm25:
  persist_dir: "./bm25_index"
  retrieval_k:
    docs: 10
    codes: 20
retrieval:
  mode: "hybrid"  # vector / bm25 / hybrid
  fusion: "rrf"
  rrf_k: 60
```

### BM25Index类设计
```python
class BM25Index:
    def __init__(self):
        self.bm25: BM25Okapi = None
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        
    def fit(self, documents: list[str], metadatas: list[dict]):
        """构建BM25索引"""
        
    def search(self, query: str, k: int = 10, filter_type: str = None) -> list[tuple]:
        """检索，返回(doc, metadata, score)"""
        
    def save(self, path: str):
        """持久化"""
        
    def load(self, path: str):
        """加载"""
```

### RRF融合流程
```
1. 向量检索: docs_vec (k=5), code_vec (k=10)
2. BM25检索: docs_bm25 (k=10), code_bm25 (k=20)
3. 分别融合:
   docs = rrf_fuse(docs_vec, docs_bm25)[:5]
   codes = rrf_fuse(code_vec, code_bm25)[:10]
4. 合并: final_docs = docs + codes
```

## 注意事项

1. **索引同步**: Chroma和BM25必须使用相同的chunks
2. **去重策略**: 基于source + content hash去重
3. **向后兼容**: 配置默认可关闭混合检索
4. **分词策略**: 代码直接按空格分词，文档可考虑中文分词
5. **性能考量**: BM25检索很快，不会显著增加延迟
