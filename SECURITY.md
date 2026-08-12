# Mako Security Guide

This guide covers the management-key, network, official-source, and job-intelligence controls available in Mako v1.5.0. It does not replace authentication at an application or identity-provider layer.

## Management API key

The following operational endpoints require an `X-Admin-Key` request header:

- `GET /skills`
- `POST /skills/reload`
- `GET /monitor`
- `GET /debug/profile/{user_id}`
- `POST /knowledge/add`
- `POST /knowledge/upload`
- `GET /knowledge/stats`
- `/knowledge/sources*`
- `/knowledge/documents*`
- `GET /knowledge/audit`
- `POST /jobs/sources/{source_id}/refresh`
- `GET /jobs`
- `POST /eval/run`

Set `MAKO_ADMIN_API_KEY` to a random value of at least 32 characters. When the variable is missing or too short, these endpoints remain unavailable. Keep the value in `.env`; do not commit it.

One way to generate a local value is:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Requests to protected endpoints include the key in the header:

```bash
curl -H "X-Admin-Key: <your-admin-key>" http://localhost:8000/skills
```

Use this header only over localhost or HTTPS. Plain HTTP does not protect header values in transit.

## Network exposure

Docker Compose binds the direct application, Redis, ChromaDB, and Prometheus ports to `127.0.0.1`. Containers communicate through `mako-network`. Redis, ChromaDB, Prometheus, Nginx, and the knowledge registry use explicit compatibility names so upgrades reuse existing data. Nginx remains the externally exposed HTTP entry point on port 80.

`REDIS_PASSWORD` is required when Compose resolves its configuration. Existing deployments can keep their current password; new deployments should use a long random value.

## Browser access and API documentation

`MAKO_CORS_ALLOW_ORIGINS` accepts a comma-separated list of trusted origins. Its default permits only common `localhost` and `127.0.0.1` development origins. Avoid `*` on an internet-facing deployment.

Swagger UI, ReDoc, and the OpenAPI document follow `ENABLE_SWAGGER_UI`. The example configuration disables them. They can be enabled for local development or a trusted administration network.

## Upload and log handling

Knowledge uploads accept UTF-8 `.txt`, `.md`, and `.json` files up to 10 MB. The application reads uploads in bounded chunks, validates document counts and field sizes, and removes path components from supplied filenames.

Career profile contents and raw intent-learning messages are not written to application logs. User and conversation identifiers used for operational correlation are represented by short one-way hashes.

## Official recruitment sources

The built-in catalog covers 23 verified company recruitment domains across internet platforms, telecommunications, smart hardware, automotive, new-energy, software, industrial manufacturing, consumer goods, professional services, and financial services. Baidu, SAP, and Microsoft are representative page-level adapter cases; catalog coverage and page-level retrieval remain separate capabilities, and each company is evaluated against its own official site structure and access boundaries. Social platforms, recruitment aggregators, forums, and unverified domains are not included.

Registering a source does not fetch it. Automated retrieval starts disabled and requires an authenticated policy change. Operators are responsible for confirming company ownership before registering another domain. Retrieval is limited to the registered HTTPS domain and approved delegated domains, with checks for DNS and peer addresses, redirects, robots policies, response type, response size, and common instruction-injection patterns.

Retrieved text is treated as untrusted factual context. It cannot modify Agent identity, system rules, tool permissions, or output requirements.

## Job-intelligence boundary

Job refresh uses the existing approved-source registry. The adapter and storage layers both validate source identity, company name, and job-link domain. An empty or incomplete parse cannot deactivate stored jobs; reconciliation requires an explicitly complete source snapshot.

Chat requests do not fetch recruitment sites. `career_match` and `career_jd` can read active, non-expired records from the local registry, while other intents do not receive job context. The response identifies whether job data was used and returns its official source links.

Sites that require login, CAPTCHA bypass, restricted static assets, or an unverified dynamic endpoint are not automatically parsed.

## Remaining boundary

`POST /chat` and `POST /search` are product-facing endpoints and do not implement end-user authentication in this release. Nginx applies request and connection limits when traffic enters through port 80. A public multi-user deployment should place Mako behind an identity layer and TLS termination, then set explicit CORS origins for that deployment.

## Dependency audit

CI runs `pip-audit` against the pinned Python dependency set. Dependency updates should pass the public regression suite and a clean audit before release.
