"""Isolated ChromaDB index for user-confirmed personal career materials."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from core.chroma_client import connect_chroma
from core.personal_knowledge import MaterialSearchHit, MaterialSection, PersonalMaterial
from core.personal_knowledge_registry import PersonalKnowledgeRegistry


PERSONAL_COLLECTION_NAME = "personal_career_knowledge"
PERSONAL_INDEX_SCHEMA_VERSION = 1
MAX_CHUNK_CHARACTERS = 1_200
CHUNK_OVERLAP_CHARACTERS = 120
INDEX_BATCH_SIZE = 128
MAX_RELEVANCE_DISTANCE = 0.45


def _chunks(text: str) -> Iterable[tuple[int, str]]:
    if len(text) <= MAX_CHUNK_CHARACTERS:
        yield 0, text
        return
    start = 0
    index = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_CHARACTERS, len(text))
        yield index, text[start:end]
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP_CHARACTERS
        index += 1


class PersonalKnowledgeIndex:
    def __init__(
        self, *, chroma_host: str, chroma_port: int, chroma_path: str,
        allow_local_chroma_fallback: bool,
    ):
        self._client, self._use_server = connect_chroma(
            host=chroma_host,
            port=chroma_port,
            local_path=chroma_path,
            allow_local_fallback=allow_local_chroma_fallback,
        )
        self._collection = self._client.get_or_create_collection(
            name=PERSONAL_COLLECTION_NAME,
            metadata={
                "description": "Mako personal career knowledge",
                "hnsw:space": "cosine",
                "schema_version": PERSONAL_INDEX_SCHEMA_VERSION,
            },
        )

    def index_material(
        self, material: PersonalMaterial, sections: list[MaterialSection],
    ) -> int:
        self.delete_material(material.material_id)
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for section in sections:
            for chunk_number, text in _chunks(section.text):
                ids.append(f"{material.material_id}_{section.ordinal}_{chunk_number}")
                documents.append(text)
                metadatas.append({
                    "material_id": material.material_id,
                    "title": material.title,
                    "category": material.category.value,
                    "section_id": section.section_id,
                    "locator_type": section.locator_type.value,
                    "locator_label": section.locator_label,
                    "chunk_number": chunk_number,
                    "content_sha256": material.content_sha256,
                    "schema_version": PERSONAL_INDEX_SCHEMA_VERSION,
                })
        for start in range(0, len(ids), INDEX_BATCH_SIZE):
            end = start + INDEX_BATCH_SIZE
            self._collection.upsert(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
        return len(ids)

    def delete_material(self, material_id: str) -> None:
        self._collection.delete(where={"material_id": material_id})

    def count_material(self, material_id: str) -> int:
        result = self._collection.get(where={"material_id": material_id}, include=[])
        return len(result.get("ids") or [])

    def search(
        self, query: str, *, registry: PersonalKnowledgeRegistry,
        material_ids: Optional[list[str]] = None, top_k: int = 5,
        max_distance: float = MAX_RELEVANCE_DISTANCE,
    ) -> list[MaterialSearchHit]:
        clean = " ".join(query.split())
        if not clean:
            return []
        allowed = {
            material.material_id: material
            for material in registry.list_materials(limit=None)
            if material.status.value == "active"
            and material.index_status.value == "ready"
            and (material_ids is None or material.material_id in material_ids)
        }
        if not allowed:
            return []
        allowed_ids = [item for item in (material_ids or sorted(allowed)) if item in allowed]
        if material_ids and len(allowed_ids) > 1:
            per_material = [
                self._query_hits(clean, allowed, [material_id], top_k, max_distance)
                for material_id in allowed_ids
            ]
            primary = [hits[0] for hits in per_material if hits]
            extras = sorted(
                (hit for hits in per_material for hit in hits[1:]),
                key=lambda hit: (hit.distance, hit.material_id, hit.section_id),
            )
            return primary + extras[:max(0, top_k - len(primary))]
        return self._query_hits(clean, allowed, allowed_ids, top_k, max_distance)[:top_k]

    def _query_hits(
        self, query: str, allowed: dict[str, PersonalMaterial], allowed_ids: list[str],
        top_k: int, max_distance: float,
    ) -> list[MaterialSearchHit]:
        requested = min(max(top_k * 4, top_k), 40)
        where = (
            {"material_id": allowed_ids[0]}
            if len(allowed_ids) == 1
            else {"material_id": {"$in": allowed_ids}}
        )
        result = self._collection.query(
            query_texts=[query],
            n_results=requested,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[MaterialSearchHit] = []
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        for section_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            material_id = str(metadata.get("material_id", ""))
            material = allowed.get(material_id)
            if not material or float(distance) > max_distance:
                continue
            hits.append(MaterialSearchHit(
                material_id=material_id,
                title=material.title,
                category=material.category,
                section_id=str(metadata.get("section_id") or section_id),
                locator_type=str(metadata.get("locator_type")),
                locator_label=str(metadata.get("locator_label")),
                excerpt=str(document)[:500],
                distance=float(distance),
            ))
        return hits
