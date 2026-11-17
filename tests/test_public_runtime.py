import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

from agents.agent_orchestrator import AgentOrchestrator, AgentResponse, AgentType, Request
from api import main as api_main
from core.intent_recognizer import IntentCategory
from monitor.performance_monitor import PerformanceMonitor


class PublicRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_alerts_merge_recover_and_stay_bounded(self):
        monitor = PerformanceMonitor(Mock(), Mock())
        with patch("monitor.performance_monitor.logger"):
            for _ in range(2000):
                monitor._check_threshold("agent_avg_ms", 4000, "career")
            self.assertEqual(len(monitor._alerts), 1)
            monitor._check_threshold("agent_avg_ms", 3000, "career")
            self.assertEqual(monitor.summary()["active_alerts"], [])
            for i in range(1200):
                monitor._check_threshold("agent_avg_ms", 4000, str(i))
            self.assertEqual(len(monitor._alerts), monitor.MAX_ALERTS)

    def test_multiworker_configuration_has_a_warning(self):
        with patch.dict(os.environ, {"WEB_CONCURRENCY": "2"}, clear=True), patch(
            "api.main.sys.argv", ["uvicorn", "api.main:app"]
        ), patch("api.main.logger") as logger:
            api_main._warn_worker_configuration()
            logger.warning.assert_called_once()

    async def test_career_route_does_not_automatically_fan_out(self):
        orch = AgentOrchestrator.__new__(AgentOrchestrator)
        orch._pool = {kind: [Mock()] for kind in AgentType}
        orch._execute = AsyncMock(return_value=AgentResponse(AgentType.CAREER, "example", True))
        orch.run_parallel = AsyncMock()
        result = await orch.run(Request("JD includes error 500", "example", "example", intent=IntentCategory.CAREER_JD))
        self.assertEqual(result.agent_type, AgentType.CAREER)
        orch._execute.assert_awaited_once()
        orch.run_parallel.assert_not_awaited()
