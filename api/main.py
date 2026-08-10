"""
Mako — AI Career Intelligence System — FastAPI 入口

启动时打印小猫咪图案。
所有核心组件在 lifespan 中初始化，通过环境变量配置。
"""
import asyncio
import logging
import os
import pathlib
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional


_ROOT = str(pathlib.Path(__file__).parent.parent.resolve())
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request as FastAPIRequest, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, ValidationError, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.security import cors_origins, env_bool, require_admin_key, validate_identifier
from core.config import env_int_with_legacy, env_with_legacy

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BANNER = r"""
    ฅ^•ﻌ•^ฅ       ฅ^•ﻌ•^ฅ       ฅ^•ﻌ•^ฅ  
   ╔════════════════════════════════════╗
   ║           Mako  v1.3.0             ║
   ║     AI Multi-Agent 求职辅助系统     ║
   ║           求职助手已启动            ║
   ╚════════════════════════════════════╝
    ฅ^•ﻌ•^ฅ       ฅ^•ﻌ•^ฅ       ฅ^•ﻌ•^ฅ
"""

# ── 全局组件（lifespan 中初始化）─────────────────────────────────────────────
_orchestrator = None
_memory       = None
_tool_manager = None
_monitor      = None
_evaluator    = None
_skill_manager = None

def _anthropic_cfg() -> Dict[str, Any]:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("未设置 ANTHROPIC_API_KEY")
    cfg: Dict[str, Any] = {
        "api_key":  key,
        "model":    os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip(),
    }
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip()
    if base_url:
        cfg["base_url"] = base_url
    return cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator, _memory, _tool_manager, _monitor, _evaluator, _skill_manager

    print(BANNER, flush=True)

    from agents.agent_orchestrator import AgentOrchestrator, Request
    from core.intent_recognizer import IntentRecognizer
    from evaluation.evaluator import EndToEndEvaluator
    from mcp.knowledge_base import KnowledgeBase
    from mcp.tool_manager import MCPToolManager, Tool
    from memory.conversation_memory import MemoryManager
    from monitor.performance_monitor import PerformanceMonitor
    from core.skill_loader import SkillManager

    cfg = _anthropic_cfg()
    logger.info(f"模型: {cfg['model']}  base_url: {cfg.get('base_url', '(官方)')}")

    # 意图识别器（Orchestrator 内部也会创建，这里单独暴露给 Evaluator）
    recognizer = IntentRecognizer(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )

    # Skills：启动时从目录加载业务能力说明，并在 Agent 调用 LLM 时动态注入。
    skills_dir = env_with_legacy(
        "MAKO_SKILLS_DIR",
        "ECHOMIND_SKILLS_DIR",
        str(pathlib.Path(_ROOT) / "skills"),
    )
    _skill_manager = SkillManager(
        root_dir=skills_dir,
        max_prompt_chars=env_int_with_legacy(
            "MAKO_SKILLS_MAX_PROMPT_CHARS",
            "ECHOMIND_SKILLS_MAX_PROMPT_CHARS",
            18000,
        ),
    )
    _skill_manager.load()

    # Agent 编排器
    _orchestrator = AgentOrchestrator(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        skill_manager=_skill_manager,
    )

    # 记忆管理器（Redis 工作记忆 + ChromaDB 情景记忆/用户画像）
    _memory = MemoryManager(
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        chroma_host=os.getenv("CHROMA_HOST", "chromadb"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/app/data/chroma"),
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )

    # MCP 工具管理器 + RAG 知识库（基于 ChromaDB 的真实检索）
    _tool_manager = MCPToolManager(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )
    kb = KnowledgeBase(
        chroma_host=os.getenv("CHROMA_HOST", "chromadb"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/app/data/chroma"),
    )
    logger.info(f"知识库已加载: {kb.doc_count} 个文档片段")

    def knowledge_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str):
        query = params.get("query", "")
        return [{
            "title": "知识库降级结果",
            "content": f"知识库暂时不可用，未能完成对“{query}”的语义检索。请稍后重试，或基于当前已提供的信息继续分析。",
            "score": 0.0,
            "fallback": True,
            "error": error,
        }]

    _tool_manager.register(Tool(
        name="knowledge_search",
        description="搜索知识库（基于 ChromaDB 向量检索）",
        handler=kb.search_handler,
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
        },
        cache_ttl=300.0,
        supports_rerank=True,
        fallback=knowledge_fallback,
    ))

    # 性能监控（可选启动 Prometheus）
    prom_port = int(os.getenv("PROMETHEUS_PORT", "0")) or None
    _monitor = PerformanceMonitor(
        orchestrator=_orchestrator,
        tool_manager=_tool_manager,
        interval_s=float(os.getenv("MONITOR_INTERVAL", "10")),
        webhook_url=os.getenv("ALERT_WEBHOOK_URL") or None,
        prometheus_port=prom_port,
    )
    await _monitor.start()

    # 评测器
    _evaluator = EndToEndEvaluator(
        orchestrator=_orchestrator,
        recognizer=recognizer,
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        baseline_path=os.getenv("EVAL_BASELINE_PATH", "/app/data/eval/baseline.json"),
    )

    logger.info("Mako 已就绪")
    yield

    await _monitor.stop()
    logger.info("Mako 已关闭")


# ── FastAPI ───────────────────────────────────────────────────────────────────
_swagger_enabled = env_bool("ENABLE_SWAGGER_UI", default=False)

app = FastAPI(
    title="Mako — AI Career Intelligence System",
    version="1.3.0",
    lifespan=lifespan,
    docs_url="/docs" if _swagger_enabled else None,
    redoc_url="/redoc" if _swagger_enabled else None,
    openapi_url="/openapi.json" if _swagger_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    allow_credentials=False,
)


def _http_request_id(request: FastAPIRequest) -> str:
    """Return the validated request ID created by middleware."""
    return getattr(request.state, "request_id", uuid.uuid4().hex)


def _error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        413: "payload_too_large",
        415: "unsupported_media_type",
        422: "validation_error",
        503: "service_unavailable",
    }.get(status_code, "http_error")


@app.middleware("http")
async def attach_request_id(request: FastAPIRequest, call_next):
    supplied = request.headers.get("X-Request-ID", "").strip()
    try:
        request_id = validate_identifier(supplied, "X-Request-ID") if supplied else uuid.uuid4().hex
    except ValueError:
        request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error_response(request: FastAPIRequest, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": _error_code(exc.status_code),
                "message": message,
                "request_id": _http_request_id(request),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_response(request: FastAPIRequest, exc: RequestValidationError):
    details = [
        {
            "field": ".".join(str(part) for part in error.get("loc", ())[1:]),
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "请求参数不符合接口约束",
                "request_id": _http_request_id(request),
                "details": details,
            }
        },
    )


@app.exception_handler(Exception)
async def internal_error_response(request: FastAPIRequest, exc: Exception):
    logger.error("请求处理失败: request_id=%s error_type=%s", _http_request_id(request), type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "服务暂时无法完成请求",
                "request_id": _http_request_id(request),
            }
        },
    )


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message:     str = Field(min_length=1, max_length=20000)
    user_id:     str = Field(default="anonymous", max_length=128)
    conv_id:     Optional[str] = Field(default=None, max_length=128)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return validate_identifier(value, "user_id")

    @field_validator("conv_id")
    @classmethod
    def validate_conv_id(cls, value: Optional[str]) -> Optional[str]:
        return validate_identifier(value, "conv_id") if value is not None else None


class ChatResponse(BaseModel):
    request_id:  str
    conv_id:     str
    response:    str
    intent:      str
    agent_type:  str
    review_required: bool
    latency_ms:  float
    knowledge_used: bool = False
    response_complete: bool = True
    continuation_used: bool = False
    quality_flags: List[str] = Field(default_factory=list)


# ── 路由 ──────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    if _orchestrator is None:
        raise HTTPException(503, "服务未就绪")
    return {"status": "ok", "agents": _orchestrator.get_stats()}


@app.get("/skills", tags=["Skills"], dependencies=[Depends(require_admin_key)])
async def skills_summary():
    """查看当前已加载的 Skills，便于确认热加载结果和排查解析错误。"""
    if _skill_manager is None:
        raise HTTPException(503, "Skills 未初始化")
    return _skill_manager.summary()


@app.post("/skills/reload", tags=["Skills"], dependencies=[Depends(require_admin_key)])
async def reload_skills():
    """运行时重新扫描 Skill 目录，不需要重启服务。"""
    if _skill_manager is None:
        raise HTTPException(503, "Skills 未初始化")
    _skill_manager.reload()
    if _orchestrator is not None:
        _orchestrator.set_skill_manager(_skill_manager)
    return _skill_manager.summary()


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, http_request: FastAPIRequest):
    """
    主对话接口。完整流程：
      记忆读取 → 意图识别 → Agent 路由 → 执行 → 记忆写入
    """
    if _orchestrator is None or _memory is None:
        raise HTTPException(503, "服务未就绪")

    from agents.agent_orchestrator import Request as OrcReq
    from memory.conversation_memory import MsgRole

    conv_id = req.conv_id or str(uuid.uuid4())

    # 1. 读取记忆上下文
    mem_ctx = await _memory.get_context(req.user_id, conv_id, query=req.message)

    # 2. 构建编排请求（含对话历史，用于意图识别上下文）
    history = [
        {"role": m.role.value, "content": m.content}
        for m in mem_ctx.recent_messages[-5:]
    ] if mem_ctx.recent_messages else None

    knowledge_text, knowledge_used = await _build_knowledge_context(req.message)
    context_parts = [mem_ctx.to_prompt_text()]
    if knowledge_text:
        context_parts.append(knowledge_text)
    full_context = "\n\n".join(part for part in context_parts if part)

    orch_req = OrcReq(
        message=req.message,
        user_id=req.user_id,
        conv_id=conv_id,
        context=full_context,
        history=history,
        request_id=_http_request_id(http_request),
    )

    # 3. 执行
    result = await _orchestrator.run(orch_req)

    # 4. 写入记忆
    await _memory.add_message(req.user_id, conv_id, MsgRole.USER, req.message)
    await _memory.add_message(req.user_id, conv_id, MsgRole.ASSISTANT, result.response)

    # 5. 仅当检测到新的职业信息时更新用户画像（不阻塞响应）
    if _should_update_career_profile(req.message):
        asyncio.create_task(
            _memory.update_profile(req.user_id, conv_id)
        )

    return ChatResponse(
        request_id=result.request_id,
        conv_id=conv_id,
        response=result.response,
        intent=result.intent.value if result.intent else "other",
        agent_type=result.agent_type.value,
        review_required=result.review_required,
        latency_ms=round(result.latency_ms, 1),
        knowledge_used=knowledge_used,
        response_complete=result.response_complete,
        continuation_used=result.continuation_used,
        quality_flags=result.quality_flags,
    )


async def _build_knowledge_context(message: str, top_k: int = 3) -> tuple[str, bool]:
    """
    为 /chat 主链路构建 RAG 知识上下文。

    这里复用 MCPToolManager 的查询改写、并行召回、重排、fallback 能力。
    """
    if _tool_manager is None:
        return "", False
    if not _should_use_knowledge(message):
        return "", False
    try:
        result = await _tool_manager.search_with_rewrite("knowledge_search", message, top_k=top_k)
        if not result.success or not isinstance(result.data, list) or not result.data:
            return "", False

        parts = ["[知识库检索结果]"]
        used = False
        for i, item in enumerate(result.data[:top_k], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "未命名文档"))
            content = str(item.get("content", "")).strip()
            score = item.get("score", "")
            if not content:
                continue
            used = True
            parts.append(f"{i}. 标题: {title}\n   相关度: {score}\n   内容: {content[:600]}")

        if not used:
            return "", False
        parts.append("请优先依据以上知识库内容回答；如果知识库信息不足，请明确说明，并仅结合已知上下文提供职业求职相关分析，不要编造用户经历或岗位事实。")
        return "\n".join(parts), True
    except Exception as ex:
        logger.warning("构建知识库上下文失败: error_type=%s", type(ex).__name__)
        return "", False


def _should_use_knowledge(message: str) -> bool:
    """仅在明确需要职业知识支持时检索知识库，避免无关 RAG 干扰回复。"""
    msg = (message or "").strip().lower()

    if not msg:
        return False

    greetings = {"你好", "您好", "嗨", "hi", "hello", "hey", "早上好", "晚上好"}
    if msg in greetings:
        return False

    career_keywords = [
        "产品运营", "简历", "求职", "面试", "岗位", "职责", "要求", "jd",
        "能力", "技能", "经验", "项目", "成果", "优化", "匹配", "经历",
        "职业", "招聘", "校招", "秋招", "春招", "实习", "投递",
        "岗位分析", "职业规划", "求职规划", "职业方向"
    ]

    return any(kw in msg for kw in career_keywords)


def _should_update_career_profile(message: str) -> bool:
    """判断当前用户消息是否包含值得写入 CareerProfile 的新职业信息。"""
    msg = (message or "").strip().lower()

    if not msg:
        return False

    trivial_messages = {
        "谢谢", "好的", "好", "嗯", "可以", "继续",
        "ok", "okay", "thanks", "thank you"
    }
    if msg in trivial_messages:
        return False

    profile_keywords = [
        "毕业", "学历", "本科", "硕士", "博士", "专业", "学校",
        "实习", "工作经历", "项目经历", "校园经历",
        "技能", "excel", "sql", "python", "ppt",
        "求职方向", "目标岗位", "想投", "想做", "岗位方向",
        "城市", "上海", "北京", "深圳", "广州", "苏州",
        "杭州", "南京", "成都", "重庆", "武汉", "西安",
        "薪资", "行业", "证书", "工作地点",
        "稳定", "出差", "加班", "销售", "轮岗"
    ]

    return any(keyword in msg for keyword in profile_keywords)


@app.get("/monitor", dependencies=[Depends(require_admin_key)])
async def monitor_summary():
    """实时监控摘要：Agent 成功率、工具统计、告警、优化建议。"""
    if _monitor is None:
        raise HTTPException(503, "服务未就绪")
    return _monitor.summary()

@app.get("/debug/profile/{user_id}", dependencies=[Depends(require_admin_key)])
async def debug_profile(user_id: str):
    """只读查看指定用户当前保存的用户画像。"""
    if _memory is None:
        raise HTTPException(503, "服务未就绪")

    try:
        user_id = validate_identifier(user_id, "user_id")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await _memory._get_profile(user_id)

@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus 指标入口。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/search")
async def search(
    query: str = Query(min_length=1, max_length=20000),
    top_k: int = Query(default=5, ge=1, le=20),
):
    """
    演示检索优化链路：查询改写 → 并行召回 → 重排 → Top-K。
    展示 MCP 工具调用的核心亮点。
    """
    if _tool_manager is None:
        raise HTTPException(503, "服务未就绪")
    result = await _tool_manager.search_with_rewrite("knowledge_search", query, top_k=top_k)
    return {"query": query, "results": result.data, "reranked": result.reranked}


class DocInput(BaseModel):
    """单篇文档输入。"""
    title:   str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=1_000_000)


class BatchDocInput(BaseModel):
    """批量文档导入请求体。"""
    documents: List[DocInput] = Field(min_length=1, max_length=100)


class EvalIntentInput(BaseModel):
    """意图识别评测用例。"""
    message: str
    expected_intent: str
    context: Optional[Dict[str, Any]] = None


class EvalDialogInput(BaseModel):
    """对话质量评测用例。question 单轮，turns 多轮。"""
    question: Optional[str] = None
    turns: Optional[List[str]] = None
    user_id: Optional[str] = None
    conv_id: Optional[str] = None


class EvalRunInput(BaseModel):
    """评测请求。为空时使用内置默认用例。"""
    intent_cases: Optional[List[EvalIntentInput]] = None
    dialog_cases: Optional[List[EvalDialogInput]] = None


@app.post("/knowledge/add", tags=["知识库"], dependencies=[Depends(require_admin_key)])
async def add_knowledge(body: BatchDocInput):
    """
    批量导入文档到知识库。

    文档会自动切片（每片 500 字）并存入 ChromaDB，ChromaDB 内置 Embedding 模型自动向量化。

    示例请求体：
    ```json
    {
      "documents": [
        {"title": "产品运营岗位能力要求", "content": "产品运营岗位通常要求用户需求分析、数据分析、跨部门协作、项目推进等能力。"},
        {"title": "简历优化原则", "content": "简历应围绕目标岗位突出相关经历、项目成果和可迁移能力。"}
      ]
    }
    ```
    """
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    kb = tool.handler.__self__
    count = kb.add_documents([{"title": d.title, "content": d.content} for d in body.documents])
    return {"message": f"成功导入 {count} 个文档片段", "added_chunks": count, "total_chunks": kb.doc_count}


@app.post("/knowledge/upload", tags=["知识库"], dependencies=[Depends(require_admin_key)])
async def upload_knowledge(file: UploadFile = File(...)):
    """
    上传文件导入知识库。

    支持格式：
    - `.txt` / `.md`：整个文件作为一篇文档，文件名作为标题
    - `.json`：JSON 数组格式 `[{"title": "...", "content": "..."}, ...]`

    文件大小限制：10MB
    """
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    kb = tool.handler.__self__

    filename = pathlib.Path(file.filename or "unknown").name
    suffix = pathlib.Path(filename).suffix.lower()
    if suffix not in {".txt", ".md", ".json"}:
        raise HTTPException(415, "仅支持 .txt、.md 和 .json 文件")

    max_bytes = 10 * 1024 * 1024
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise HTTPException(413, "文件大小超过 10MB 限制")

    try:
        text = bytes(content).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "文件必须使用 UTF-8 编码") from exc

    if suffix == ".json":
        import json as _json
        try:
            docs = _json.loads(text)
            if not isinstance(docs, list):
                raise HTTPException(400, "JSON 文件应为数组格式: [{title, content}, ...]")
            validated = BatchDocInput(documents=docs)
            docs = [doc.model_dump() for doc in validated.documents]
        except _json.JSONDecodeError as e:
            raise HTTPException(400, f"JSON 解析失败: {e}")
        except ValidationError as exc:
            raise HTTPException(422, "JSON 文档不符合导入限制") from exc
    else:
        # txt / md：整个文件作为一篇文档
        title = filename.rsplit(".", 1)[0] if "." in filename else filename
        try:
            validated = BatchDocInput(documents=[{"title": title, "content": text}])
            docs = [doc.model_dump() for doc in validated.documents]
        except ValidationError as exc:
            raise HTTPException(422, "文件标题或内容不符合导入限制") from exc

    count = kb.add_documents(docs)
    return {
        "message": f"文件 {filename} 导入成功",
        "added_chunks": count,
        "total_chunks": kb.doc_count,
    }


@app.get("/knowledge/stats", tags=["知识库"], dependencies=[Depends(require_admin_key)])
async def knowledge_stats():
    """查看知识库统计信息（文档片段总数）。"""
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    kb = tool.handler.__self__
    return {"total_chunks": kb.doc_count}


@app.post("/eval/run", dependencies=[Depends(require_admin_key)])
async def run_eval(body: Optional[EvalRunInput] = None):
    """运行内置评测用例，返回评测报告。"""
    if _evaluator is None:
        raise HTTPException(503, "服务未就绪")
    from evaluation.evaluator import DEFAULT_DIALOG_CASES, DEFAULT_INTENT_CASES, IntentTestCase

    if body and body.intent_cases is not None:
        intent_cases = [
            IntentTestCase(
                message=c.message,
                expected_intent=c.expected_intent,
                context=c.context,
            )
            for c in body.intent_cases
        ]
    else:
        intent_cases = DEFAULT_INTENT_CASES

    if body and body.dialog_cases is not None:
        dialog_cases = [
            c.model_dump(exclude_none=True)
            for c in body.dialog_cases
        ]
    else:
        dialog_cases = DEFAULT_DIALOG_CASES

    report = await _evaluator.run(
        intent_cases=intent_cases,
        dialog_cases=dialog_cases,
    )
    return {
        "pass_rate":       report.pass_rate,
        "total":           report.total,
        "passed":          report.passed,
        "avg_scores":      report.avg_scores,
        "regressions":     report.regressions,
        "recommendations": report.recommendations,
        "results": [
            {
                "test_id": r.test_id,
                "passed": r.passed,
                "scores": r.scores,
                "detail": r.detail,
                "metadata": r.metadata,
            }
            for r in report.results
        ],
    }


# ── 交互式 CLI ────────────────────────────────────────────────────────────────
async def _cli():
    print(BANNER)
    print("Mako CLI — 输入 quit 退出\n")

    from agents.agent_orchestrator import AgentOrchestrator, Request
    from memory.conversation_memory import MemoryManager, MsgRole
    from core.skill_loader import SkillManager

    cfg = _anthropic_cfg()
    skill_manager = SkillManager(
        root_dir=env_with_legacy(
            "MAKO_SKILLS_DIR",
            "ECHOMIND_SKILLS_DIR",
            str(pathlib.Path(_ROOT) / "skills"),
        ),
        max_prompt_chars=env_int_with_legacy(
            "MAKO_SKILLS_MAX_PROMPT_CHARS",
            "ECHOMIND_SKILLS_MAX_PROMPT_CHARS",
            18000,
        ),
    )
    skill_manager.load()
    orch = AgentOrchestrator(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        skill_manager=skill_manager,
    )
    mem  = MemoryManager(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        chroma_host=os.getenv("CHROMA_HOST", "localhost"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/tmp/chroma"),
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )

    user_id, conv_id = "cli_user", str(uuid.uuid4())

    while True:
        try:
            msg = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见 ฅ^•ﻌ•^ฅ")
            break
        if not msg or msg.lower() in ("quit", "exit", "退出"):
            print("再见 ฅ^•ﻌ•^ฅ")
            break

        ctx = await mem.get_context(user_id, conv_id, query=msg)
        history = [
            {"role": m.role.value, "content": m.content}
            for m in ctx.recent_messages[-5:]
        ] if ctx.recent_messages else None
        req = Request(message=msg, user_id=user_id, conv_id=conv_id, context=ctx.to_prompt_text(), history=history)
        result = await orch.run(req)

        await mem.add_message(user_id, conv_id, MsgRole.USER, msg)
        await mem.add_message(user_id, conv_id, MsgRole.ASSISTANT, result.response)

        print(f"\nMako [{result.agent_type.value}]: {result.response}\n")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        asyncio.run(_cli())
    else:
        uvicorn.run(
            "api.main:app",
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            reload=os.getenv("APP_ENV") == "development",
        )
