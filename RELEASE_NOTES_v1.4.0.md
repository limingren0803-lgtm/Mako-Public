# Mako v1.4.0 Release Notes

Release date: 2026-08-10

## Overview

Mako v1.4.0 adds lifecycle management for career knowledge while preserving the existing Career Skills, CareerProfile behavior, Memory behavior, and API paths.

## Knowledge lifecycle

- A SQLite registry records official sources, documents, versions, and lifecycle events.
- Stable document identifiers and content hashes prevent unchanged material from creating duplicate versions.
- Updates, status changes, and rollbacks keep registry metadata and ChromaDB retrieval data aligned.
- Successful changes clear related knowledge-search cache entries.
- Version and audit responses expose metadata without returning stored document text.

## Official recruitment sources

The initial catalog contains the official recruitment domains for Tencent, Huawei, ByteDance, Meituan, and Baidu. It does not include social platforms, recruitment aggregators, forums, or unverified sources.

Catalog registration does not fetch website content. Automated retrieval remains disabled until an administrator reviews the source policy. Retrieval checks HTTPS and registered domains, DNS and peer addresses, redirects, robots policies, content type, response size, and common instruction-injection patterns.

## Retrieval boundary

External knowledge is supplied to the Agent as untrusted factual context. It cannot change Agent identity, system rules, tool permissions, or output requirements. Material that is missing, conflicting, or potentially outdated is not treated as an instruction.

## Persistence and compatibility

- The knowledge registry uses the `mako_knowledge-registry-data` Docker volume and is included in persistence backups.
- Existing Redis keys, ChromaDB collections, CareerProfile fields, API routes, and data paths remain unchanged.
- Existing Redis, ChromaDB, Prometheus, and Nginx volume names remain pinned for upgrade compatibility.
