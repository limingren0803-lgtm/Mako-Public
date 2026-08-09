"""
亮点：多 Agent 路由与编排

核心问题：多 Agent 情况下如何做 Routing？

路由策略（三层决策）：
  1. 意图路由 —— 根据 IntentCategory 直接映射到专属 Agent
  2. 性能路由 —— 同类 Agent 有多个时，选成功率最高、延迟最低的
  3. 降级路由 —— 专属 Agent 不可用时，自动降级到 GeneralAgent

并行协作：
  - 复杂问题（如"技术问题 + 账单问题"）可同时派发给多个 Agent
  - 结果由 Orchestrator 合并后返回

升级机制：
  - Agent 置信度不足或信息不完整 → 返回明确的限制说明或确认请求
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from core.intent_recognizer import IntentCategory, IntentRecognizer, TimeSensitivity
from core.llm_utils import extract_text_content

logger = logging.getLogger(__name__)

CAREER_MAX_TOKENS = 4096


# ── 数据结构 ──────────────────────────────────────────────────────────────────

class AgentType(Enum):
    GENERAL   = "general"    # 通用请求处理
    TECHNICAL = "technical"  # 技术支持
    CAREER    = "career"     # 求职与职业决策支持


@dataclass
class AgentStats:
    """Agent 运行时统计，供 Monitor 和路由决策使用。"""
    total:     int   = 0
    success:   int   = 0
    total_ms:  float = 0.0
    monitor_penalty: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.success / self.total if self.total else 1.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.total if self.total else 0.0

    def routing_score(self) -> float:
        """路由评分：成功率高、延迟低的 Agent 得分高。"""
        latency_score = 1.0 / (1.0 + self.avg_ms / 1000)
        base_score = self.success_rate * 0.7 + latency_score * 0.3
        return base_score * max(0.0, 1.0 - self.monitor_penalty)


@dataclass
class AgentResponse:
    agent_type:  AgentType
    content:     str
    success:     bool
    confidence:  float = 1.0
    latency_ms:  float = 0.0
    needs_review: bool = False


@dataclass
class Request:
    message:     str
    user_id:     str
    conv_id:     str
    context:     str = ""        # 来自 MemoryManager 的格式化上下文
    history:     Optional[List[Dict[str, str]]] = None  # 对话历史，传给意图识别
    intent:      Optional[IntentCategory] = None
    time_sensitivity: Optional[TimeSensitivity] = None
    request_id:  str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class OrchestratorResult:
    request_id:  str
    response:    str
    agent_type:  AgentType
    intent:      Optional[IntentCategory]
    review_required: bool = False
    latency_ms:  float = 0.0


# ── 基础 Agent ────────────────────────────────────────────────────────────────

class BaseAgent:
    """所有 Agent 的基类，封装 LLM 调用和统计。"""

    agent_type: AgentType
    system_prompt: str

    def __init__(self, client: AsyncAnthropic, model: str, skill_manager: Optional[Any] = None):
        self._client = client
        self._model  = model
        self._skill_manager = skill_manager
        self.stats   = AgentStats()

    async def handle(self, req: Request) -> AgentResponse:
        t0 = time.monotonic()
        self.stats.total += 1
        try:
            content = await self._call_llm(req)
            ms = (time.monotonic() - t0) * 1000
            self.stats.success += 1
            self.stats.total_ms += ms
            needs_review = self._needs_review(content)
            return AgentResponse(
                agent_type=self.agent_type,
                content=content,
                success=True,
                latency_ms=ms,
                needs_review=needs_review,
            )
        except Exception as ex:
            ms = (time.monotonic() - t0) * 1000
            self.stats.total_ms += ms
            logger.error(f"{self.agent_type.value} 处理失败: {ex}")
            return AgentResponse(
                agent_type=self.agent_type,
                content="抱歉，处理您的请求时出现问题，请稍后重试。",
                success=False,
                latency_ms=ms,
            )

    async def _call_llm(self, req: Request) -> str:
        def _clean(s: str) -> str:
            return s.encode("utf-8", errors="ignore").decode("utf-8")

        messages = []
        if req.context:
            messages.append({"role": "user", "content": f"[背景信息]\n{_clean(req.context)}"})
            messages.append({"role": "assistant", "content": "好的，我已了解背景信息。"})
        messages.append({"role": "user", "content": _clean(req.message)})

        max_tokens = CAREER_MAX_TOKENS if self.agent_type == AgentType.CAREER else 1024

        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=self._build_system_prompt(req),
            messages=messages,
        )
        return extract_text_content(resp.content)

    def _build_system_prompt(self, req: Request) -> str:
        """把动态加载的 Skills 拼入 system prompt，让业务规则随请求生效。"""
        if self._skill_manager is None:
            return self.system_prompt
        intent = req.intent.value if req.intent else None
        skill_prompt = self._skill_manager.prompt_for(
            req.message,
            self.agent_type.value,
            intent=intent,
        )
        if not skill_prompt:
            return self.system_prompt
        return f"{self.system_prompt}\n\n[动态 Skills]\n{skill_prompt}"

    def _needs_review(self, content: str) -> bool:
        """检测 Agent 是否明确建议人工升级或人工介入。"""
        keywords = [
            "需要人工审核",
            "建议人工审核",
            "需要人工确认",
            "建议人工确认",
            "需要升级处理",
            "建议升级处理",
            "需要人工介入",
            "建议人工介入",
        ]
        return any(kw in content for kw in keywords)


class GeneralAgent(BaseAgent):
    agent_type    = AgentType.GENERAL
    system_prompt = (
        "你是 Mako 通用 AI 助手。请友好、简洁、准确地回答用户问题。"
        "如果问题属于职业求职或技术支持等专业领域，应明确交由对应的专业 Agent 处理；如果信息不足，请说明需要补充的信息。"
    )


class TechnicalAgent(BaseAgent):
    agent_type    = AgentType.TECHNICAL
    system_prompt = (
        "你是技术支持专家。专注于：故障排查、错误诊断、系统配置。"
        "提供清晰的步骤化解决方案。遇到需要后台操作的问题，说明需要升级处理。"
    )



class CareerAgent(BaseAgent):
    agent_type = AgentType.CAREER
    system_prompt = (
        "你是一名面向求职者的职业决策支持助手，重点服务海外背景学生、应届毕业生及处于求职准备阶段的用户。"
        "你需要基于用户真实提供的学历、专业、实习、项目、技能、"
        "求职目标和岗位信息进行分析。"
        "不得虚构用户没有提供的经历、技能、证书、成果或招聘信息。"
        "不得只给笼统鼓励，也不得保证录取或面试结果。"
        "当信息不足时，应先说明缺少哪些关键信息，"
        "再给出有限、带条件的判断。"
        "回答应客观、结构清晰，并优先提供能够直接执行的建议。"
    )


# ── 编排器 ────────────────────────────────────────────────────────────────────

class AgentOrchestrator:
    """
    多 Agent 编排器。

    路由逻辑（三层）：
      1. 意图 → Agent 类型映射
      2. 同类多实例时按 routing_score() 选最优
      3. 专属 Agent 失败时降级到 GeneralAgent
    """

    # 意图 → Agent 类型的静态映射（路由表）
    _INTENT_ROUTING: Dict[IntentCategory, AgentType] = {
        IntentCategory.TECHNICAL:  AgentType.TECHNICAL,
        IntentCategory.CAREER_PROFILE:   AgentType.CAREER,
        IntentCategory.CAREER_MATCH:     AgentType.CAREER,
        IntentCategory.CAREER_JD:        AgentType.CAREER,
        IntentCategory.CAREER_RESUME:    AgentType.CAREER,
        IntentCategory.CAREER_INTERVIEW: AgentType.CAREER,
        IntentCategory.CAREER_PLANNING:  AgentType.CAREER,
        # 其余意图 → GENERAL（默认）
    }

    def __init__(
        self,
        api_key:  str,
        base_url: Optional[str] = None,
        model:    str = "claude-3-5-sonnet-20241022",
        skill_manager: Optional[Any] = None,
    ):
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncAnthropic(**kwargs)

        self._intent_recognizer = IntentRecognizer(api_key=api_key, base_url=base_url, model=model)
        self._skill_manager = skill_manager

        # Agent 池：每种类型可有多个实例（水平扩展）
        self._pool: Dict[AgentType, List[BaseAgent]] = {
            AgentType.GENERAL:   [GeneralAgent(client, model, skill_manager)],
            AgentType.TECHNICAL: [TechnicalAgent(client, model, skill_manager)],
            AgentType.CAREER:    [CareerAgent(client, model, skill_manager)],
        }

    def set_skill_manager(self, skill_manager: Optional[Any]) -> None:
        """更新 SkillManager 引用，供运行时重载或测试替换使用。"""
        self._skill_manager = skill_manager
        for agents in self._pool.values():
            for agent in agents:
                agent._skill_manager = skill_manager

    # ── 主入口 ────────────────────────────────────────────────────────────────

    async def run(self, req: Request) -> OrchestratorResult:
        """
        处理一次请求的完整流程：
          意图识别 → 路由选 Agent → 执行 → 检查升级 → 返回结果
        """
        t0 = time.monotonic()

        # 1. 意图识别（如果调用方已识别则跳过）
        if req.intent is None:
            intent_result = await self._intent_recognizer.recognize(req.message, history=req.history)
            req.intent  = intent_result.intent
            req.time_sensitivity = intent_result.time_sensitivity

        # 复杂职业任务可结合多个能力模块处理，例如先分析岗位 JD，再结合职业画像进行岗位匹配。
        collaboration = self._collaboration_targets(req)
        if len(collaboration) > 1:
            return await self.run_parallel(req, collaboration)

        # 2. 路由：选择 Agent 类型
        agent_type = self._route(req.intent)

        # 3. 执行（含降级）
        response = await self._execute(req, agent_type)

        # 4. 结果状态
        review_required = bool(response.needs_review)

        return OrchestratorResult(
            request_id=req.request_id,
            response=response.content,
            agent_type=response.agent_type,
            intent=req.intent,
            review_required=review_required,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    async def run_parallel(self, req: Request, agent_types: List[AgentType]) -> OrchestratorResult:
        """
        并行派发给多个 Agent，合并结果。
        适用于需要多个能力模块协同处理的复杂任务，
        例如先分析岗位 JD，再结合职业画像判断匹配度。
        """
        t0 = time.monotonic()
        tasks = [self._execute(req, at) for at in agent_types]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并：拼接所有成功响应
        parts = []
        for r in responses:
            if isinstance(r, AgentResponse) and r.success:
                parts.append(f"[{r.agent_type.value}]\n{r.content}")

        combined = "\n\n".join(parts) if parts else "抱歉，所有 Agent 均处理失败。"
        review_required = any(isinstance(r, AgentResponse) and r.needs_review for r in responses)

        return OrchestratorResult(
            request_id=req.request_id,
            response=combined,
            agent_type=agent_types[0],
            intent=req.intent,
            review_required=review_required,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    # ── 路由逻辑 ──────────────────────────────────────────────────────────────

    def _route(self, intent: Optional[IntentCategory]) -> AgentType:
        """
        路由决策：
          1. 根据意图映射到对应 Agent
          2. 目标 Agent 不可用时回退 GENERAL
        """

        if intent and intent in self._INTENT_ROUTING:
            target = self._INTENT_ROUTING[intent]
            # 如果目标类型有可用实例则使用，否则降级
            if target in self._pool and self._pool[target]:
                return target

        return AgentType.GENERAL

    def _collaboration_targets(self, req: Request) -> List[AgentType]:
        """
        判断是否需要多个 Agent 并行协作。

        意图识别通常只返回一个主意图；这里用领域关键词补充检测复合问题，
        例如“先分析目标岗位 JD，再结合职业画像判断匹配度”属于需要组合多个职业能力模块处理的复杂任务。
        """
        msg = req.message.lower()
        targets: List[AgentType] = []

        technical_kws = ["崩溃", "报错", "error", "crash", "无法登录", "登录失败", "500", "401"]

        if req.intent == IntentCategory.TECHNICAL or any(kw in msg for kw in technical_kws):
            targets.append(AgentType.TECHNICAL)

        # 保持顺序去重，并只返回当前有实例的 Agent 类型。
        deduped = list(dict.fromkeys(targets))
        return [agent_type for agent_type in deduped if self._pool.get(agent_type)]

    def _best_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """
        性能路由：从同类 Agent 中选 routing_score() 最高的。
        这是"基于在线表现动态调整路由"的核心。
        """
        agents = self._pool.get(agent_type, [])
        if not agents:
            return None
        return max(agents, key=lambda a: a.stats.routing_score())

    async def _execute(self, req: Request, agent_type: AgentType) -> AgentResponse:
        """执行 Agent，失败时降级到 GeneralAgent。"""
        agent = self._best_agent(agent_type)
        if agent is None:
            agent = self._best_agent(AgentType.GENERAL)
        if agent is None:
            return AgentResponse(
                agent_type=AgentType.GENERAL,
                content="服务暂时不可用，请稍后重试。",
                success=False,
            )

        response = await agent.handle(req)

        # 专属 Agent 失败时降级到 GeneralAgent
        if not response.success and agent_type != AgentType.GENERAL:
            logger.warning(f"{agent_type.value} 失败，降级到 GeneralAgent")
            fallback = self._best_agent(AgentType.GENERAL)
            if fallback:
                response = await fallback.handle(req)

        return response

    # ── 统计（供 Monitor 读取）────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        result = {}
        for agent_type, agents in self._pool.items():
            for i, agent in enumerate(agents):
                key = f"{agent_type.value}_{i}"
                result[key] = {
                    "total":        agent.stats.total,
                    "success_rate": round(agent.stats.success_rate, 3),
                    "avg_ms":       round(agent.stats.avg_ms, 1),
                    "monitor_penalty": round(agent.stats.monitor_penalty, 3),
                    "routing_score": round(agent.stats.routing_score(), 3),
                }
        return result

    def update_routing_penalties(self, penalties: Dict[str, float]) -> None:
        """
        接收 Monitor 的在线表现反馈，动态调整路由惩罚项。

        penalties 的 key 使用 get_stats() 中的 agent key，例如 technical_0。
        """
        for agent_type, agents in self._pool.items():
            for i, agent in enumerate(agents):
                key = f"{agent_type.value}_{i}"
                penalty = penalties.get(key, 0.0)
                agent.stats.monitor_penalty = min(max(penalty, 0.0), 0.9)
