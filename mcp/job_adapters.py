"""Adapters for normalizing structured data from official career pages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Mapping, Optional, Type

from core.job_posting import JobPosting, RecruitmentType
from mcp.knowledge_source_catalog import OFFICIAL_CAREER_SOURCES_CN
from mcp.knowledge_sources import validate_source_url


class JobAdapterError(ValueError):
    """Raised when an official page cannot be normalized safely."""


@dataclass(frozen=True)
class JobAdapterContext:
    source_id: str
    company_name: str
    official_domain: str
    delegated_domains: tuple[str, ...] = ()
    fetched_at: Optional[datetime] = None

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        return (self.official_domain, *self.delegated_domains)


@dataclass(frozen=True)
class JobAdapterResult:
    postings: List[JobPosting]
    page_number: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    complete_snapshot: bool = False


class _JsonLdExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._capturing = False
        self._parts: List[str] = []
        self.blocks: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        if tag.lower() != "script":
            return
        attributes = {str(key).lower(): str(value).lower() for key, value in attrs if value}
        if attributes.get("type", "").split(";", 1)[0].strip() == "application/ld+json":
            self._capturing = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capturing:
            self.blocks.append("".join(self._parts))
            self._capturing = False
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)


class _VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if clean:
            self.parts.append(clean)


def _visible_text(value: Any) -> str:
    parser = _VisibleTextExtractor()
    parser.feed(unescape(str(value or "")))
    return " ".join(parser.parts)


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _iter_job_nodes(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _iter_job_nodes(item)
        return
    if not isinstance(value, dict):
        return
    raw_type = value.get("@type")
    types = raw_type if isinstance(raw_type, list) else [raw_type]
    if any(str(item).casefold() == "jobposting" for item in types):
        yield value
    for key, child in value.items():
        if key != "@context":
            yield from _iter_job_nodes(child)


def _identifier(node: Mapping[str, Any], source_url: str) -> str:
    value = node.get("identifier")
    if isinstance(value, dict):
        value = value.get("value") or value.get("name")
    if value:
        return str(value).strip()
    page_url = str(node.get("url") or source_url).strip()
    seed = f"{page_url}\n{node.get('title', '')}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _locations(node: Mapping[str, Any]) -> List[str]:
    raw = node.get("jobLocation") or []
    raw = raw if isinstance(raw, list) else [raw]
    result: List[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        address = item.get("address", item)
        if isinstance(address, str):
            result.append(address)
            continue
        if isinstance(address, dict):
            parts = [
                address.get("addressCountry"),
                address.get("addressRegion"),
                address.get("addressLocality"),
                address.get("streetAddress"),
            ]
            result.append(" ".join(str(part).strip() for part in parts if part))
    return result


def _recruitment_type(node: Mapping[str, Any]) -> RecruitmentType:
    text = " ".join(
        str(node.get(key) or "")
        for key in ("title", "employmentType", "description")
    ).casefold()
    if any(token in text for token in ("实习", "intern")):
        return RecruitmentType.INTERNSHIP
    if any(token in text for token in ("校园", "校招", "campus")):
        return RecruitmentType.CAMPUS
    if any(token in text for token in ("应届", "graduate")):
        return RecruitmentType.GRADUATE
    if any(token in text for token in ("社会招聘", "社招", "experienced")):
        return RecruitmentType.EXPERIENCED
    return RecruitmentType.OTHER


class JsonLdJobAdapter:
    """Normalize Schema.org JobPosting blocks embedded by an official site."""

    source_id: Optional[str] = None

    def parse(
        self,
        *,
        html: str,
        source_url: str,
        context: JobAdapterContext,
    ) -> List[JobPosting]:
        return self.parse_page(
            html=html,
            source_url=source_url,
            context=context,
        ).postings

    def parse_page(
        self,
        *,
        html: str,
        source_url: str,
        context: JobAdapterContext,
    ) -> JobAdapterResult:
        if self.source_id and context.source_id != self.source_id:
            raise JobAdapterError("adapter does not match the registered source")
        validate_source_url(source_url, context.allowed_domains)
        parser = _JsonLdExtractor()
        parser.feed(html)
        fetched_at = context.fetched_at or datetime.now(timezone.utc)
        postings: List[JobPosting] = []
        for block in parser.blocks:
            try:
                payload = json.loads(unescape(block).strip())
            except (json.JSONDecodeError, TypeError):
                continue
            for node in _iter_job_nodes(payload):
                title = _visible_text(node.get("title"))
                if not title:
                    continue
                node_url = str(node.get("url") or source_url)
                validate_source_url(node_url, context.allowed_domains)
                postings.append(
                    JobPosting(
                        source_id=context.source_id,
                        external_id=_identifier(node, node_url),
                        company_name=context.company_name,
                        title=title,
                        department=_visible_text(node.get("occupationalCategory")) or None,
                        job_category=_visible_text(node.get("industry")) or None,
                        recruitment_type=_recruitment_type(node),
                        employment_type=_visible_text(node.get("employmentType")) or None,
                        locations=_locations(node),
                        description=_visible_text(node.get("description")),
                        published_at=node.get("datePosted"),
                        valid_through=node.get("validThrough"),
                        source_url=node_url,
                        fetched_at=fetched_at,
                    )
                )
        return JobAdapterResult(postings=postings)


class TencentJobAdapter(JsonLdJobAdapter):
    source_id = "src_cn_tencent"


class HuaweiJobAdapter(JsonLdJobAdapter):
    source_id = "src_cn_huawei"


class ByteDanceJobAdapter(JsonLdJobAdapter):
    source_id = "src_cn_bytedance"


class MeituanJobAdapter(JsonLdJobAdapter):
    source_id = "src_cn_meituan"


def _extract_assigned_object(html: str, marker: str) -> Optional[str]:
    marker_index = html.find(marker)
    if marker_index < 0:
        return None
    start = html.find("{", marker_index + len(marker))
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(html)):
        char = html[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[start : index + 1]
    return None


def _replace_bare_undefined(value: str) -> str:
    output: List[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(value):
        char = value[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if value.startswith("undefined", index):
            before = value[index - 1] if index else ""
            after_index = index + len("undefined")
            after = value[after_index] if after_index < len(value) else ""
            if before in ":,[ \t\r\n" and after in ",}] \t\r\n":
                output.append("null")
                index = after_index
                continue
        output.append(char)
        index += 1
    return "".join(output)


def _split_job_text(value: Any) -> List[str]:
    text = unescape(str(value or "")).replace("\r", "\n")
    parts = re.split(r"\n+|(?<![A-Za-z0-9])[-•·]\s*", text)
    return [" ".join(part.split()) for part in parts if " ".join(part.split())]


def _baidu_recruitment_type(node: Mapping[str, Any], container_type: Any) -> RecruitmentType:
    text = " ".join(
        str(item or "")
        for item in (
            container_type,
            node.get("projectType"),
            node.get("projectTypeCode"),
        )
    ).casefold()
    if "intern" in text or "实习" in text or "-1" in text:
        return RecruitmentType.INTERNSHIP
    if "social" in text or "社招" in text or "社会招聘" in text:
        return RecruitmentType.EXPERIENCED
    if "graduate" in text or "应届" in text:
        return RecruitmentType.GRADUATE
    if "campus" in text or "校招" in text or text.strip() == "1":
        return RecruitmentType.CAMPUS
    return RecruitmentType.OTHER


class BaiduJobAdapter(JsonLdJobAdapter):
    source_id = "src_cn_baidu"

    def parse_page(
        self,
        *,
        html: str,
        source_url: str,
        context: JobAdapterContext,
    ) -> JobAdapterResult:
        if context.source_id != self.source_id:
            raise JobAdapterError("adapter does not match the registered source")
        validate_source_url(source_url, context.allowed_domains)
        raw = _extract_assigned_object(html, "window.__INITIAL_DATA__")
        if not raw:
            return super().parse_page(html=html, source_url=source_url, context=context)
        try:
            data = json.loads(_replace_bare_undefined(raw))
        except (json.JSONDecodeError, TypeError) as exc:
            raise JobAdapterError("Baidu page contains invalid initial job data") from exc

        list_data = data.get("listData") if isinstance(data, dict) else None
        detail_data = data.get("detailData") if isinstance(data, dict) else None
        nodes: List[Mapping[str, Any]] = []
        container_type: Any = None
        page_number: Optional[int] = None
        page_size: Optional[int] = None
        total: Optional[int] = None
        if isinstance(list_data, dict):
            candidates = list_data.get("listDetailData") or []
            if isinstance(candidates, list):
                nodes.extend(node for node in candidates if isinstance(node, dict))
            container_type = list_data.get("recruitType") or list_data.get("projectType")
            page_number = _optional_int(list_data.get("pageNum"))
            page_size = _optional_int(list_data.get("pageSize"))
            total = _optional_int(list_data.get("total"))
        if not nodes and isinstance(detail_data, dict) and detail_data.get("isValid") is not False:
            detail = detail_data.get("postInfo")
            if isinstance(detail, dict):
                nodes.append(detail)
                container_type = detail_data.get("recruitType") or container_type

        postings: List[JobPosting] = []
        seen = set()
        for node in nodes:
            external_id = str(node.get("postId") or node.get("jobId") or "").strip()
            title = _visible_text(node.get("name"))
            if not external_id or not title or external_id in seen:
                continue
            responsibilities = _split_job_text(node.get("workContent"))
            requirements = _split_job_text(node.get("serviceCondition"))
            locations = re.split(r"[,，、;/]+", str(node.get("workPlace") or ""))
            postings.append(
                JobPosting(
                    source_id=context.source_id,
                    external_id=external_id,
                    company_name=context.company_name,
                    title=title,
                    department=_visible_text(node.get("orgName") or node.get("bgShortName")) or None,
                    job_category=_visible_text(node.get("postType")) or None,
                    recruitment_type=_baidu_recruitment_type(node, container_type),
                    locations=locations,
                    responsibilities=responsibilities,
                    requirements=requirements,
                    description="\n".join([*responsibilities, *requirements]),
                    published_at=node.get("publishDate") or None,
                    source_updated_at=node.get("updateDate") or None,
                    source_url=source_url,
                    fetched_at=context.fetched_at or datetime.now(timezone.utc),
                )
            )
            seen.add(external_id)
        complete = bool(total is not None and total == len(postings) and total <= (page_size or total))
        return JobAdapterResult(
            postings=postings,
            page_number=page_number,
            page_size=page_size,
            total=total,
            complete_snapshot=complete,
        )


ADAPTER_TYPES: Dict[str, Type[JsonLdJobAdapter]] = {
    adapter.source_id: adapter
    for adapter in (
        TencentJobAdapter,
        HuaweiJobAdapter,
        ByteDanceJobAdapter,
        MeituanJobAdapter,
        BaiduJobAdapter,
    )
}


def adapter_for_source(source_id: str) -> JsonLdJobAdapter:
    try:
        return ADAPTER_TYPES[source_id]()
    except KeyError as exc:
        raise JobAdapterError("no job adapter is registered for this source") from exc


def context_for_source(source_id: str, *, fetched_at: Optional[datetime] = None) -> JobAdapterContext:
    for source in OFFICIAL_CAREER_SOURCES_CN:
        if source["source_id"] == source_id:
            return JobAdapterContext(
                source_id=source_id,
                company_name=source["company_name"],
                official_domain=source["official_domain"],
                delegated_domains=tuple(source.get("delegated_domains", [])),
                fetched_at=fetched_at,
            )
    raise JobAdapterError("source is not present in the official career catalog")
