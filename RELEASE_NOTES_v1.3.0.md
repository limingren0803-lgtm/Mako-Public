# Mako v1.3.0 Release Notes

Release date: 2026-08-10

## Scope

Mako v1.3.0 improves response reliability, API consistency, and deployment behavior. The six Career Skills, CareerProfile Schema, Memory behavior, and existing API paths are unchanged.

## Response reliability

- Provider stop reasons and response structure are checked for token limits, empty output, unclosed code fences, and clearly unfinished endings.
- A likely truncated answer receives one bounded continuation request. A second incomplete result is returned with an explicit quality state instead of another retry.
- `/chat` responses include `request_id`, `response_complete`, `continuation_used`, and `quality_flags`.
- End-to-end evaluation treats an incomplete answer as a failed case even when its LLM quality score is otherwise above the threshold.

## API contract

- Successful and failed requests return `X-Request-ID`; callers may provide a valid request ID or let Mako generate one.
- API errors use a consistent `error.code`, `error.message`, and `error.request_id` envelope.
- Validation errors identify the affected field without echoing the rejected input value.

## Runtime and deployment

- `MAKO_SKILLS_DIR` and `MAKO_SKILLS_MAX_PROMPT_CHARS` are the primary Skill settings.
- Legacy Skill environment aliases remain accepted for existing deployments.
- Compose resources, Nginx upstreams, Prometheus labels, and the non-root image user follow a consistent naming scheme.
- The four existing Docker volume names remain explicit so upgrades reuse Redis, ChromaDB, Prometheus, and Nginx data. New installations create the same named volumes automatically.

## Verification

- Python syntax/import checks passed.
- The deterministic regression suite passed 62/62.
- Docker Compose configuration validation passed.
- All five Mako containers rebuilt and reached healthy state.
- Live health, structured validation error, request ID, GeneralAgent chat, and management-boundary checks passed.
- The protected online evaluation passed 16/16 with pass rate 1.0, no regressions, and no incomplete responses.
- Redis retained 26 keys, the knowledge base retained 7 chunks, and all four persistent volumes remained mounted at their original destinations.
- The existing persistence backup passed manifest and checksum validation before the container migration.

## Compatibility

The following interfaces remain unchanged:

- `/chat`, `/monitor`, `/debug/profile`, knowledge, Skills, and evaluation routes;
- CareerProfile fields and conservative merge behavior;
- Redis keys and ChromaDB collection names;
- the four persisted Docker volume names;
- the six Career intents and Skills.

The first v1.3 startup on an upgraded installation may report that a named volume was created by the previous Compose project. This warning is expected; the volume is reused and is not copied or cleared.
