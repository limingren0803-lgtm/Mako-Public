"""Safe retrieval and validation for registered public knowledge sources."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Iterable, List
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx


USER_AGENT = "MakoKnowledgeBot/1.0"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/json",
)


class SourceSecurityError(ValueError):
    """Raised when a source violates the configured network or content boundary."""


@dataclass(frozen=True)
class FetchedSource:
    final_url: str
    content_type: str
    title: str
    text: str
    content_hash: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._title_depth = 0
        self.parts: List[str] = []
        self.title_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._skip_depth += 1
        if tag == "title":
            self._title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title" and self._title_depth:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        self.parts.append(clean)
        if self._title_depth:
            self.title_parts.append(clean)


def _normalized_domain(value: str) -> str:
    return value.strip().lower().rstrip(".")


def _host_allowed(host: str, allowed_domains: Iterable[str]) -> bool:
    host = _normalized_domain(host)
    for domain in allowed_domains:
        domain = _normalized_domain(domain)
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False


def validate_source_url(url: str, allowed_domains: Iterable[str]) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SourceSecurityError("knowledge sources must use HTTPS")
    if parsed.username or parsed.password:
        raise SourceSecurityError("source URLs must not contain credentials")
    if not parsed.hostname or not _host_allowed(parsed.hostname, allowed_domains):
        raise SourceSecurityError("source domain is not registered")
    if parsed.port not in (None, 443):
        raise SourceSecurityError("source URL uses an unapproved port")
    return url


def _is_non_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


async def _assert_public_dns(hostname: str) -> None:
    def _resolve() -> list[tuple]:
        return socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)

    try:
        addresses = await asyncio.to_thread(_resolve)
    except socket.gaierror as exc:
        raise SourceSecurityError("source domain could not be resolved") from exc
    if not addresses:
        raise SourceSecurityError("source domain did not resolve to an address")
    for item in addresses:
        if _is_non_public_address(item[4][0]):
            raise SourceSecurityError("source domain resolves to a non-public address")


def _assert_public_peer(response: httpx.Response) -> None:
    """Verify the connected peer when the HTTP transport exposes its socket address."""
    stream = getattr(response, "extensions", {}).get("network_stream")
    if stream is None or not hasattr(stream, "get_extra_info"):
        return
    peer = stream.get_extra_info("server_addr") or stream.get_extra_info("peername")
    if not peer:
        return
    address = peer[0] if isinstance(peer, tuple) else str(peer)
    if _is_non_public_address(address):
        raise SourceSecurityError("source connection reached a non-public address")


def _extract_text(body: bytes, content_type: str) -> tuple[str, str]:
    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceSecurityError("source content must be UTF-8") from exc
    if content_type.startswith("text/html"):
        parser = _TextExtractor()
        parser.feed(decoded)
        text = "\n".join(parser.parts)
        title = " ".join(parser.title_parts).strip()
    else:
        text = decoded
        title = ""
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 80:
        raise SourceSecurityError("source content is too short to publish")
    return title[:300], text


def find_instruction_injection(text: str) -> List[str]:
    patterns = {
        "ignore_instructions": r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        "system_prompt": r"\bsystem\s+prompt\b",
        "developer_message": r"\bdeveloper\s+message\b",
        "assistant_impersonation": r"\byou\s+are\s+(chatgpt|an?\s+ai\s+assistant)\b",
        "prompt_override_cn": r"忽略.{0,12}(之前|以上|先前).{0,8}(指令|要求)",
        "system_prompt_cn": r"系统提示词|开发者消息",
    }
    lowered = text.lower()
    return [name for name, pattern in patterns.items() if re.search(pattern, lowered, re.IGNORECASE)]


async def fetch_registered_source(source: dict) -> FetchedSource:
    allowed_domains = [source["official_domain"], *source.get("delegated_domains", [])]
    current_url = validate_source_url(source["source_url"], allowed_domains)
    timeout = httpx.Timeout(15.0, connect=5.0)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json"},
    ) as client:
        final_url = current_url
        final_content_type = ""
        final_body = b""
        robots_policies: dict[str, RobotFileParser | None] = {}
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlparse(current_url)
            await _assert_public_dns(parsed.hostname or "")
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in robots_policies:
                robots_url = f"{origin}/robots.txt"
                await _assert_public_dns(parsed.hostname or "")
                parser: RobotFileParser | None = None
                try:
                    async with client.stream("GET", robots_url) as robots_response:
                        _assert_public_peer(robots_response)
                        if robots_response.status_code == 200:
                            robots_body = bytearray()
                            async for chunk in robots_response.aiter_bytes():
                                robots_body.extend(chunk)
                                if len(robots_body) > 512_000:
                                    robots_body.clear()
                                    break
                            if robots_body:
                                parser = RobotFileParser()
                                parser.set_url(robots_url)
                                parser.parse(
                                    bytes(robots_body)
                                    .decode("utf-8", errors="ignore")
                                    .splitlines()
                                )
                except httpx.HTTPError:
                    parser = None
                robots_policies[origin] = parser
            robots_policy = robots_policies[origin]
            if robots_policy and not robots_policy.can_fetch(USER_AGENT, current_url):
                raise SourceSecurityError("source robots policy does not allow retrieval")
            async with client.stream("GET", current_url) as response:
                _assert_public_peer(response)
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise SourceSecurityError("source returned an invalid redirect")
                    current_url = validate_source_url(urljoin(current_url, location), allowed_domains)
                    continue
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > MAX_RESPONSE_BYTES:
                            raise SourceSecurityError("source content exceeds the size limit")
                    except ValueError:
                        pass
                final_content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if not any(final_content_type.startswith(item) for item in ALLOWED_CONTENT_TYPES):
                    raise SourceSecurityError("source returned an unsupported content type")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise SourceSecurityError("source content exceeds the size limit")
                final_body = bytes(body)
                final_url = str(response.url)
                break
        else:
            raise SourceSecurityError("source exceeded the redirect limit")

        title, text = _extract_text(final_body, final_content_type)
        flags = find_instruction_injection(text)
        if flags:
            raise SourceSecurityError(f"source content failed instruction isolation checks: {','.join(flags)}")

        return FetchedSource(
            final_url=final_url,
            content_type=final_content_type,
            title=title,
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
