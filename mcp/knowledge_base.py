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
import os
from typing import Any, Dict, List, Optional

import chromadb

from mcp.knowledge_registry import KnowledgeRegistry
from mcp.knowledge_source_catalog import OFFICIAL_CAREER_SOURCES_CN

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
        registry_path: Optional[str] = None,
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

        self._registry = KnowledgeRegistry(
            registry_path
            or os.getenv("MAKO_KNOWLEDGE_REGISTRY_PATH", "./data/knowledge/registry.sqlite3")
        )
        for source in OFFICIAL_CAREER_SOURCES_CN:
            self._registry.ensure_source(**source)

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
        from mcp.knowledge_sources import find_instruction_injection

        prepared = []
        for doc in documents:
            title = doc.get("title", "").strip()
            content = doc.get("content", "").strip()
            if not title or not content:
                continue
            flags = find_instruction_injection(content)
            if flags:
                raise ValueError(
                    "document failed instruction isolation checks: " + ",".join(flags)
                )
            prepared.append((doc, title, content))

        added_chunks = 0
        for doc, title, content in prepared:
            stable_id = f"doc_manual_{hashlib.sha256(title.encode('utf-8')).hexdigest()[:16]}"
            result = self.publish_document(
                document_id=stable_id,
                title=title,
                content=content,
                source_url=doc.get("source_url"),
            )
            added_chunks += int(result.get("added_chunks", 0))
        if added_chunks:
            logger.info("知识库导入 %s 个文档片段", added_chunks)
        return added_chunks

    def publish_document(
        self,
        *,
        title: str,
        content: str,
        document_id: Optional[str] = None,
        source_id: Optional[str] = None,
        external_id: Optional[str] = None,
        source_url: Optional[str] = None,
        validation_notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Stage and publish one validated document while retaining version history."""
        title = title.strip()
        content = content.strip()
        if not title or not content:
            raise ValueError("title and content are required")
        from mcp.knowledge_sources import find_instruction_injection, validate_source_url

        injection_flags = find_instruction_injection(content)
        if injection_flags:
            raise ValueError(
                "document failed instruction isolation checks: " + ",".join(injection_flags)
            )
        if source_id:
            source = self._registry.get_source(source_id)
            if not source:
                raise ValueError("registered source does not exist")
            source_url = source_url or source["source_url"]
            validate_source_url(
                source_url,
                [source["official_domain"], *source.get("delegated_domains", [])],
            )

        document = self._registry.ensure_document(
            title=title,
            source_id=source_id,
            external_id=external_id,
            document_id=document_id,
        )
        document_id = document["document_id"]
        previous_version_id = document.get("current_version_id")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        version = self._registry.stage_version(
            document_id=document_id,
            content=content,
            content_hash=content_hash,
            source_url=source_url,
            validation_notes=validation_notes,
        )
        version_id = version["version_id"]
        if (
            version.get("duplicate")
            and version_id == previous_version_id
            and document.get("status") == "active"
        ):
            return {
                "document_id": document_id,
                "version_id": version_id,
                "changed": False,
                "added_chunks": 0,
            }

        chunks = self._chunk_text(content, chunk_size=500)
        ids = [f"{document_id}:{version_id}:{index}" for index in range(len(chunks))]
        metadatas = [
            {
                "title": title,
                "chunk_index": index,
                "total_chunks": len(chunks),
                "document_id": document_id,
                "version_id": version_id,
                "source_id": source_id or "manual",
                "source_url": source_url or "",
                "content_hash": content_hash,
                "status": "active",
            }
            for index in range(len(chunks))
        ]

        activated = False
        try:
            if ids:
                self._collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
            self._registry.activate_version(document_id, version_id)
            activated = True
            if previous_version_id and previous_version_id != version_id:
                self._delete_version_chunks(document_id, previous_version_id)
        except Exception:
            recovery_error: Optional[Exception] = None
            try:
                if activated and previous_version_id and previous_version_id != version_id:
                    previous_version = self._registry.get_version(previous_version_id)
                    if previous_version:
                        previous_chunks = self._chunk_text(
                            previous_version["content"], chunk_size=500
                        )
                        previous_ids = [
                            f"{document_id}:{previous_version_id}:{index}"
                            for index in range(len(previous_chunks))
                        ]
                        previous_metadatas = [
                            {
                                "title": document["title"],
                                "chunk_index": index,
                                "total_chunks": len(previous_chunks),
                                "document_id": document_id,
                                "version_id": previous_version_id,
                                "source_id": document.get("source_id") or "manual",
                                "source_url": previous_version.get("source_url") or "",
                                "content_hash": previous_version["content_hash"],
                                "status": "active",
                            }
                            for index in range(len(previous_chunks))
                        ]
                        if previous_ids:
                            self._collection.upsert(
                                ids=previous_ids,
                                documents=previous_chunks,
                                metadatas=previous_metadatas,
                            )
                        self._registry.activate_version(document_id, previous_version_id)
            except Exception as exc:
                recovery_error = exc
            if ids:
                try:
                    self._collection.delete(ids=ids)
                except Exception:
                    pass
            self._registry.record_event(
                "version_publish",
                "document",
                document_id,
                "failed",
                {"version_id": version_id},
            )
            if recovery_error:
                raise RuntimeError("knowledge version recovery failed") from recovery_error
            raise

        return {
            "document_id": document_id,
            "version_id": version_id,
            "changed": True,
            "added_chunks": len(ids),
        }

    def list_documents(
        self,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._registry.list_documents(source_id=source_id, status=status)

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        return self._registry.get_document(document_id)

    def list_versions(self, document_id: str) -> List[Dict[str, Any]]:
        return self._registry.list_versions(document_id)

    def deactivate_document(self, document_id: str, status: str = "inactive") -> Dict[str, Any]:
        document = self._registry.get_document(document_id)
        if not document:
            raise KeyError(document_id)
        version_id = document.get("current_version_id")
        if version_id:
            self._delete_version_chunks(document_id, version_id)
        return self._registry.set_document_status(document_id, status)

    def rollback_document(self, document_id: str, version_id: str) -> Dict[str, Any]:
        document = self._registry.get_document(document_id)
        version = self._registry.get_version(version_id)
        if not document or not version or version.get("document_id") != document_id:
            raise KeyError(version_id)
        previous_version_id = document.get("current_version_id")
        result = self.publish_document(
            document_id=document_id,
            title=document["title"],
            content=version["content"],
            source_id=document.get("source_id"),
            external_id=document.get("external_id"),
            source_url=version.get("source_url"),
            validation_notes=["rollback"],
        )
        if previous_version_id and previous_version_id != result["version_id"]:
            self._delete_version_chunks(document_id, previous_version_id)
        return self._registry.get_document(document_id) or {}

    def register_source(self, **kwargs: Any) -> Dict[str, Any]:
        from mcp.knowledge_sources import validate_source_url

        allowed_domains = [kwargs["official_domain"], *kwargs.get("delegated_domains", [])]
        validate_source_url(
            kwargs["source_url"],
            allowed_domains,
        )
        if kwargs.get("job_source_url"):
            validate_source_url(kwargs["job_source_url"], allowed_domains)
        if kwargs.get("policy_url"):
            validate_source_url(kwargs["policy_url"], allowed_domains)
        return self._registry.register_source(**kwargs)

    def list_sources(
        self,
        status: Optional[str] = None,
        *,
        industry: Optional[str] = None,
        support_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._registry.list_sources(
            status=status,
            industry=industry,
            support_level=support_level,
        )

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self._registry.get_source(source_id)

    def get_job_source_availability(
        self,
        *,
        source_ids: Optional[List[str]] = None,
        max_age_days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        return self._registry.get_job_source_availability(
            source_ids=source_ids,
            max_age_days=max_age_days,
        )

    def set_source_status(self, source_id: str, status: str) -> Dict[str, Any]:
        return self._registry.set_source_status(source_id, status)

    def set_source_policy(self, source_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self._registry.set_source_policy(source_id, **kwargs)

    def record_event(
        self,
        action: str,
        target_type: str,
        target_id: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._registry.record_event(action, target_type, target_id, outcome, details)

    def list_events(
        self,
        target_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._registry.list_events(target_id=target_id, limit=limit)

    def list_job_postings(
        self,
        *,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._registry.list_job_postings(
            source_id=source_id,
            status=status,
            limit=limit,
        )

    def list_pending_job_versions(
        self,
        *,
        source_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._registry.list_pending_job_versions(source_id=source_id, limit=limit)

    def review_job_version(
        self,
        *,
        job_id: str,
        version_id: str,
        decision: str,
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._registry.review_job_version(
            job_id=job_id,
            version_id=version_id,
            decision=decision,
            notes=notes,
        )

    def review_job_versions_batch(
        self, reviews: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return self._registry.review_job_versions_batch(reviews)

    def update_job_freshness(self) -> Dict[str, int]:
        return self._registry.update_job_freshness()

    def create_job_refresh_task(self, **kwargs: Any) -> Dict[str, Any]:
        return self._registry.create_job_refresh_task(**kwargs)

    def list_job_refresh_tasks(
        self,
        *,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._registry.list_job_refresh_tasks(
            source_id=source_id, status=status, limit=limit
        )

    async def run_job_refresh_task(self, task_id: str) -> Dict[str, Any]:
        from mcp.job_pipeline import run_job_refresh_task

        return await run_job_refresh_task(registry=self._registry, task_id=task_id)

    def retry_job_refresh_task(self, task_id: str) -> Dict[str, Any]:
        return self._registry.retry_job_refresh_task(task_id)

    async def refresh_job_source(self, source_id: str) -> Dict[str, Any]:
        from mcp.job_pipeline import refresh_job_source

        return await refresh_job_source(registry=self._registry, source_id=source_id)

    async def import_job_url(self, source_id: str, source_url: str) -> Dict[str, Any]:
        from mcp.job_pipeline import import_job_url

        return await import_job_url(
            registry=self._registry,
            source_id=source_id,
            source_url=source_url,
        )

    def import_job_posting(self, source_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from mcp.job_pipeline import import_job_posting

        return import_job_posting(
            registry=self._registry,
            source_id=source_id,
            payload=payload,
        )

    def import_job_posting_batch(
        self, source_id: str, payloads: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        from mcp.job_pipeline import import_job_posting_batch

        return import_job_posting_batch(
            registry=self._registry,
            source_id=source_id,
            payloads=payloads,
        )

    def search_job_postings(
        self,
        query: str,
        *,
        limit: int = 5,
        max_age_days: int = 30,
        source_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self._registry.search_job_postings(
            query,
            limit=limit,
            max_age_days=max_age_days,
            source_ids=source_ids,
        )

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
                    "document_id": meta.get("document_id"),
                    "version_id": meta.get("version_id"),
                    "source_id": meta.get("source_id"),
                    "source_url": meta.get("source_url"),
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

    def _delete_version_chunks(self, document_id: str, version_id: str) -> None:
        version = self._registry.get_version(version_id)
        if not version:
            return
        chunk_count = len(self._chunk_text(version["content"], chunk_size=500))
        ids = [f"{document_id}:{version_id}:{index}" for index in range(chunk_count)]
        if ids:
            self._collection.delete(ids=ids)

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
