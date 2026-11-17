"""Short background diagnosis contract and seven-day, workspace-bound receipts."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TTL = 7 * 24 * 60 * 60
LABELS = {"career_match": "方向匹配", "career_jd": "JD 分析", "career_resume": "简历优化",
          "career_interview": "面试准备", "career_planning": "行动规划", "clarify": "补充信息"}


class DiagnosisBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    priority: str = Field(min_length=1, max_length=60)
    reasons: list[str] = Field(min_length=1, max_length=2)
    next_intent: Literal["career_match", "career_jd", "career_resume", "career_interview", "career_planning", "clarify"]
    next_step: str = Field(min_length=1, max_length=60)
    details: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def concise(self):
        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("diagnosis reasons must not be blank")
        if len(self.priority + ''.join(self.reasons) + self.next_step + LABELS[self.next_intent]) > 150:
            raise ValueError("diagnosis summary exceeds 150 characters")
        return self

    def markdown(self) -> str:
        return (f"## 优先检查\n{self.priority}\n\n" + '\n'.join(f"- {item}" for item in self.reasons)
                + f"\n\n## 下一步：{LABELS[self.next_intent]}\n{self.next_step}\n\n## 判断依据与边界\n{self.details}")


CONTRACT = """[服务端首次诊断输出契约 v1]
本次使用 career_profile 的简短初步诊断模式，替代完整七段长报告。只基于实际提供的材料，
不把缺少回应归因为简历或方向，不把未提及的能力视为缺失；无 JD 必须说明无法确认岗位匹配。
一次返回 JSON 对象，不加其他正文：
{"priority":"一句优先检查问题","reasons":["一条材料依据","必要的不确定性"],
"next_intent":"career_resume","next_step":"一个具体用途","details":"按需展开的证据与边界"}
priority、最多两条 reasons、next_step 与推荐工具中文名合计不超过 150 字；details 不超过 2000 字。
next_intent 仅可选 career_match/career_jd/career_resume/career_interview/career_planning/clarify，
依据不足应选 clarify（补充信息），不可默认推荐简历优化。不得再调用模型概括或改写。
"""


def parse_brief(text: str) -> DiagnosisBrief:
    text = text.strip()
    if text.startswith('```json\n') and text.endswith('```'):
        text = text[8:-3].strip()
    return DiagnosisBrief.model_validate_json(text)


def _key(path: Path, *, create: bool) -> bytes:
    """Atomic key installation, no user content stored; replacement revokes v1 receipts."""
    if not path.exists() and create:
        fd, name = tempfile.mkstemp(prefix='.diagnosis-key-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(name, path)
            except FileExistsError:
                pass
        finally:
            os.unlink(name)
    secret = path.read_bytes()
    if len(secret) != 32:
        raise ValueError('诊断结果凭据不可验证，请保留可查看内容')
    return secret


def seal(payload: dict, path: Path, *, now: int | None = None) -> str:
    issued = int(time.time()) if now is None else now
    data = {**payload, 'version': 1, 'workspace': 'local-default', 'issued': issued, 'expires': issued + TTL}
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
    encoded = base64.urlsafe_b64encode(raw).decode()
    signature = hmac.new(_key(path, create=True), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + '.' + signature


def unseal(token: str, path: Path, *, now: int | None = None) -> dict:
    try:
        if not isinstance(token, str) or len(token) > 60000:
            raise ValueError()
        encoded, signature = token.rsplit('.', 1)
        expected = hmac.new(_key(path, create=False), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError()
        data = json.loads(base64.b64decode(encoded, altchars=b'-_', validate=True))
        current = int(time.time()) if now is None else now
        if (data['version'] != 1 or data['workspace'] != 'local-default'
                or not data['issued'] <= current < data['expires']
                or data['expires'] - data['issued'] != TTL):
            raise ValueError()
        DiagnosisBrief.model_validate(data['brief'])
        return data
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise ValueError('诊断结果已过期或无法验证；原内容仍可查看，请重新诊断后保存') from exc
