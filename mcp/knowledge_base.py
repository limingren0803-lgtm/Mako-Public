"""
RAG 知识库 —— 基于 ChromaDB 的真实检索实现。

功能：
  1. 文档导入：将文本切片后存入 ChromaDB（自动生成 Embedding）
  2. 语义检索：根据 query 从知识库中检索最相关的文档片段
  3. 与 MCP 工具框架集成：作为 knowledge_search 工具的真实 handler

ChromaDB 在这里的角色：
  - memory/ 中用于存储对话记忆（情景记忆 + 用户画像）
  - 这里用于存储知识库文档（RAG 检索）
  两者是不同的 collection，互不干扰。
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional

import chromadb

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    基于 ChromaDB 的 RAG 知识库。

    ChromaDB 内置了 Embedding 模型（all-MiniLM-L6-v2），
    调用 add() 时自动生成向量，query() 时自动做语义匹配。
    不需要额外调用 Anthropic Embeddings API。
    """

    COLLECTION_NAME = "knowledge_base"

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        chroma_path: str = "./data/chroma",
    ):
        # 优先连接独立 ChromaDB 服务（服务端内置 embedding 模型，客户端无需下载）
        self._use_server = False
        try:
            # HttpClient 默认也会初始化 ChromaDB telemetry；显式关闭避免 posthog 兼容性错误日志。
            self._client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
            self._client.heartbeat()
            self._use_server = True
            logger.info(f"知识库 ChromaDB 已连接: {chroma_host}:{chroma_port}")
        except Exception:
            logger.info(f"知识库 ChromaDB 服务不可用，使用本地模式: {chroma_path}")
            self._client = chromadb.PersistentClient(
                path=chroma_path,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )

        # 使用服务端时不传 embedding_function，让服务端处理
        # 本地模式时也不传，使用 ChromaDB 默认的（会触发模型下载）
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Mako RAG 知识库"},
        )

        # 如果知识库为空，导入默认文档
        if self._collection.count() == 0:
            self._load_default_docs()

    # ── 文档管理 ──────────────────────────────────────────────────────────────

    def add_documents(self, documents: List[Dict[str, str]]) -> int:
        """
        批量导入文档到知识库。

        documents 格式: [{"title": "...", "content": "..."}, ...]
        长文档会自动切片（每片 500 字）。
        """
        ids, docs, metas = [], [], []

        for doc in documents:
            title   = doc.get("title", "")
            content = doc.get("content", "")
            chunks  = self._chunk_text(content, chunk_size=500)

            for i, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{title}_{i}_{chunk[:50]}".encode()).hexdigest()
                ids.append(doc_id)
                docs.append(chunk)
                metas.append({"title": title, "chunk_index": i, "total_chunks": len(chunks)})

        if ids:
            # ChromaDB 会自动生成 Embedding
            self._collection.add(ids=ids, documents=docs, metadatas=metas)
            logger.info(f"知识库导入 {len(ids)} 个文档片段")

        return len(ids)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        语义检索：根据 query 返回最相关的文档片段。

        ChromaDB 内部自动将 query 转为向量，与存储的文档向量做余弦相似度匹配。
        """
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        items = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                items.append({
                    "title":    meta.get("title", ""),
                    "content":  doc,
                    "score":    round(1.0 - dist, 4),  # ChromaDB 返回距离，转为相似度
                    "chunk":    meta.get("chunk_index", 0),
                })

        return items

    @property
    def doc_count(self) -> int:
        return self._collection.count()

    # ── MCP 工具 handler ─────────────────────────────────────────────────────

    async def search_handler(self, params: Dict[str, Any], context: Any) -> List[Dict]:
        """
        作为 MCP 工具的 handler 注册。

        MCPToolManager.register(Tool(
            name="knowledge_search",
            handler=kb.search_handler,
            ...
        ))
        """
        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        return self.search(query, top_k=top_k)

    # ── 内部方法 ──────────────────────────────────────────────────────────────

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """将长文本按 chunk_size 切片，保留语义完整性（按句号/换行切分）。"""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        current = ""
        # 按句子切分
        sentences = text.replace("\n", "。").split("。")
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(current) + len(sent) + 1 > chunk_size:
                if current:
                    chunks.append(current)
                current = sent
            else:
                current = f"{current}。{sent}" if current else sent

        if current:
            chunks.append(current)

        return chunks

    def _load_default_docs(self) -> None:
        """导入默认知识库文档（职业求职场景）。"""
        default_docs = [
            {
                "title": "JD 分析原则",
                "content": (
                    "JD 分析应优先识别岗位的核心职责、硬性要求、加分项和潜在风险。"
                    "需要区分明确写出的要求与基于岗位语境推测出的能力要求。"
                    "对于学历、毕业时间、工作地点、经验年限、专业背景等硬性条件，应单独标记，避免与一般能力要求混在一起。"
                    "如果岗位要求表述模糊，应明确说明不确定性，不应擅自补充企业未写明的要求。"
                ),
            },
            {
                "title": "岗位匹配分析原则",
                "content": (
                    "岗位匹配分析应基于用户已确认的教育背景、经历、技能和求职偏好进行。"
                    "分析时可将结果区分为直接匹配、可迁移能力、能力缺口和需要确认的信息。"
                    "对于缺乏直接经历但存在相关项目、实习或校园经历的情况，可以识别可迁移能力，但不应将其描述为用户已经具备同等岗位经验。"
                    "对于毕业时间、工作地点、语言要求等硬性条件，如果信息不足，应优先提示确认。"
                ),
            },
            {
                "title": "简历优化原则",
                "content": (
                    "简历优化应基于用户真实经历，不应新增用户未提供的项目、职责、成果、数据或技能。"
                    "优化重点包括突出与目标岗位相关的职责、行动和结果，减少与岗位无关的信息，并提升表达的清晰度和结构性。"
                    "可以对已有事实进行重新组织和专业化表达，但不能为了提高匹配度而虚构经历。"
                    "如果缺少可量化结果，应保留事实表达，不应擅自编造数字。"
                ),
            },
            {
                "title": "经历证据与能力判断",
                "content": (
                    "能力判断应尽可能绑定真实经历证据。"
                    "例如，跨团队沟通能力应通过用户实际承担的协调、沟通或推进任务来支持，而不是仅根据主观自我评价得出。"
                    "当某项能力只有间接证据时，应标记为可迁移能力或待确认，而不是直接认定为强项。"
                    "在生成简历和岗位匹配结论时，应优先使用有明确经历支撑的信息。"
                ),
            },
            {
                "title": "职业画像信息使用规则",
                "content": (
                    "职业画像中的信息应区分已确认信息、待确认信息和系统推断。"
                    "用户明确提供或确认的信息可以作为后续分析的重要依据。"
                    "系统推断只能用于辅助分析，不应直接写入简历或作为硬性事实使用。"
                    "当新信息与旧信息冲突时，应优先提示用户确认，而不是自动选择其中一个版本。"
                ),
            },
            {
                "title": "面试准备原则",
                "content": (
                    "面试准备应围绕目标岗位要求和用户真实经历展开。"
                    "问题可以包括岗位动机、行为面试、经历追问、能力证明和岗位场景题。"
                    "回答建议应优先帮助用户从真实经历中提取行动、判断和结果，而不是生成无法被用户解释或证明的故事。"
                    "如果用户缺乏某项能力的直接经历，可以准备如何说明学习能力、可迁移能力和补足计划。"
                ),
            },
            {
                "title": "求职规划原则",
                "content": (
                    "求职规划应根据目标岗位、当前能力、时间限制和求职阶段制定。"
                    "行动建议应尽量具体，包括需要完成的任务、优先级和下一步行动。"
                    "对于影响岗位资格的重要信息，如毕业时间、工作地点、签证或工作资格等，应优先确认。"
                    "规划应避免一次性安排过多任务，应优先处理对投递和面试结果影响最大的事项。"
                ),
            },
        ]
        self.add_documents(default_docs)
        logger.info(f"已导入默认知识库: {len(default_docs)} 篇文档")
