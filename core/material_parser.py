"""Bounded, network-free parsing for personal career materials."""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import PurePosixPath, PureWindowsPath

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from core.personal_knowledge import (
    ExtractedMaterial,
    ExtractedSection,
    LocatorType,
    MaterialFileType,
)


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARACTERS = 1_000_000
MAX_PDF_PAGES = 200
MAX_DOCX_ENTRIES = 2_000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
PREVIEW_EXCERPT_CHARACTERS = 500


class MaterialParseError(ValueError):
    status_code = 422
    code = "material_parse_error"


class MaterialTooLargeError(MaterialParseError):
    status_code = 413
    code = "material_too_large"


class UnsupportedMaterialError(MaterialParseError):
    status_code = 415
    code = "unsupported_material"


class InvalidMaterialError(MaterialParseError):
    status_code = 400
    code = "invalid_material"


def _basename(filename: str) -> str:
    name = PureWindowsPath(filename or "").name
    name = PurePosixPath(name).name.strip()
    if not name or name in {".", ".."} or len(name) > 255:
        raise InvalidMaterialError("invalid filename")
    return name


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _finalize(
    *, filename: str, file_type: MaterialFileType, content: bytes,
    sections: list[ExtractedSection], warnings: list[str] | None = None,
) -> ExtractedMaterial:
    sections = [section for section in sections if section.text.strip()]
    if not sections:
        raise MaterialParseError("document contains no extractable text")
    normalized = "\n\n".join(section.text for section in sections)
    if len(normalized) > MAX_TEXT_CHARACTERS:
        raise MaterialTooLargeError("parsed text exceeds 1000000 characters")
    return ExtractedMaterial(
        original_filename=filename,
        file_type=file_type,
        content_sha256=hashlib.sha256(content).hexdigest(),
        text_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        byte_size=len(content),
        character_count=len(normalized),
        sections=sections,
        warnings=warnings or [],
    )


def _parse_text(filename: str, content: bytes, *, markdown: bool) -> ExtractedMaterial:
    if content.startswith((b"%PDF-", b"PK\x03\x04")) or b"\x00" in content:
        raise UnsupportedMaterialError("file content does not match its extension")
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise InvalidMaterialError("text files must use UTF-8") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[ExtractedSection] = []
    start = 0
    buffer: list[str] = []

    def flush(end: int) -> None:
        nonlocal buffer, start
        clean = _normalize_text("\n".join(buffer))
        if clean:
            heading = buffer[0].lstrip().startswith("#") if markdown and buffer else False
            label = f"第 {start + 1}-{end} 行" if end > start + 1 else f"第 {start + 1} 行"
            sections.append(ExtractedSection(
                ordinal=len(sections),
                locator_type=LocatorType.HEADING if heading else LocatorType.LINE,
                locator_label=label,
                text=clean,
            ))
        buffer = []

    for index, line in enumerate(lines):
        if not buffer and line.strip():
            start = index
        if not line.strip():
            flush(index)
        else:
            buffer.append(line)
    flush(len(lines))
    return _finalize(
        filename=filename,
        file_type=MaterialFileType.MARKDOWN if markdown else MaterialFileType.TXT,
        content=content,
        sections=sections,
    )


def _parse_pdf(filename: str, content: bytes) -> ExtractedMaterial:
    if not content.startswith(b"%PDF-"):
        raise UnsupportedMaterialError("file content is not a PDF")
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise UnsupportedMaterialError("password-protected PDF files are not supported")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise MaterialTooLargeError("PDF exceeds 200 pages")
        sections = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = _normalize_text(page.extract_text() or "")
            if text:
                sections.append(ExtractedSection(
                    ordinal=len(sections),
                    locator_type=LocatorType.PAGE,
                    locator_label=f"第 {page_number} 页",
                    text=text,
                ))
    except MaterialParseError:
        raise
    except Exception as exc:
        raise InvalidMaterialError("PDF could not be parsed safely") from exc
    return _finalize(filename=filename, file_type=MaterialFileType.PDF, content=content, sections=sections)


def _check_docx_archive(content: bytes) -> None:
    if not content.startswith(b"PK\x03\x04"):
        raise UnsupportedMaterialError("file content is not a DOCX archive")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            names = {member.filename for member in members}
            if len(members) > MAX_DOCX_ENTRIES:
                raise MaterialTooLargeError("DOCX contains too many archive entries")
            if sum(member.file_size for member in members) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise MaterialTooLargeError("DOCX expanded content is too large")
            for member in members:
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                    raise InvalidMaterialError("DOCX contains an unsafe archive path")
            if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                raise InvalidMaterialError("DOCX is missing required document parts")
            if any(name.casefold().endswith("vbaproject.bin") for name in names):
                raise UnsupportedMaterialError("macro-enabled documents are not supported")
    except MaterialParseError:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise InvalidMaterialError("DOCX archive is invalid") from exc


def _parse_docx(filename: str, content: bytes) -> ExtractedMaterial:
    _check_docx_archive(content)
    try:
        document = Document(io.BytesIO(content))
        sections: list[ExtractedSection] = []
        paragraph_number = 0
        table_number = 0
        textbox_number = 0
        mc = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                paragraph_number += 1
                text = _normalize_text(block.text)
                if text:
                    style = (block.style.name if block.style else "").casefold()
                    heading = style.startswith("heading")
                    sections.append(ExtractedSection(
                        ordinal=len(sections),
                        locator_type=LocatorType.HEADING if heading else LocatorType.PARAGRAPH,
                        locator_label=text[:200] if heading else f"段落 {paragraph_number}",
                        text=text,
                    ))
            elif isinstance(block, Table):
                table_number += 1
                rows = [" | ".join(_normalize_text(cell.text) for cell in row.cells) for row in block.rows]
                text = _normalize_text("\n".join(row for row in rows if row.strip(" |")))
                if text:
                    sections.append(ExtractedSection(
                        ordinal=len(sections),
                        locator_type=LocatorType.TABLE,
                        locator_label=f"表格 {table_number}",
                        text=text,
                    ))
            for box in block._element.xpath(".//w:txbxContent"):
                alternate = next(box.iterancestors(f"{mc}AlternateContent"), None)
                if alternate is not None:
                    chosen = next((
                        child for child in alternate
                        if child.tag == f"{mc}Choice"
                        and next(child.iter(qn("w:txbxContent")), None) is not None
                    ), None)
                    if chosen is None:
                        chosen = next((child for child in alternate if child.tag == f"{mc}Fallback"), None)
                    if chosen not in box.iterancestors():
                        continue
                textbox_number += 1
                for number, paragraph in enumerate(box.iter(qn("w:p")), start=1):
                    text = _normalize_text(Paragraph(paragraph, document._body).text)
                    if text:
                        sections.append(ExtractedSection(
                            ordinal=len(sections),
                            locator_type=LocatorType.PARAGRAPH,
                            locator_label=f"文本框 {textbox_number} · 段落 {number}",
                            text=text,
                        ))
    except MaterialParseError:
        raise
    except Exception as exc:
        raise InvalidMaterialError("DOCX could not be parsed safely") from exc
    return _finalize(filename=filename, file_type=MaterialFileType.DOCX, content=content, sections=sections)


def parse_material(filename: str, content: bytes) -> ExtractedMaterial:
    """Parse one already bounded upload without writing files or using the network."""
    name = _basename(filename)
    if not content:
        raise InvalidMaterialError("file is empty")
    if len(content) > MAX_FILE_BYTES:
        raise MaterialTooLargeError("file exceeds 10 MB")
    suffix = PurePosixPath(name.casefold()).suffix
    if suffix == ".txt":
        return _parse_text(name, content, markdown=False)
    if suffix in {".md", ".markdown"}:
        return _parse_text(name, content, markdown=True)
    if suffix == ".pdf":
        return _parse_pdf(name, content)
    if suffix == ".docx":
        return _parse_docx(name, content)
    raise UnsupportedMaterialError("supported file types are TXT, Markdown, PDF, and DOCX")
