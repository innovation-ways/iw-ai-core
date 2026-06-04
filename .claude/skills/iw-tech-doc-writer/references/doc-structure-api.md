# API Document Structure Reference

## Purpose

Detailed section breakdown for API documentation. The `iw-tech-doc-writer` skill references this file when generating API docs.

---

## Document Structure

```
1. Document Header
   - Title: "{System} — API Reference"
   - Version, Date, Status
   - Audience: Frontend Developers, Integration Partners, Backend Developers
   - Base URL and versioning scheme

2. Table of Contents

3. Overview (200-300 words)
   - What the API does
   - Base URL: https://api.example.com/v1
   - Versioning strategy (URL path, header, or query param)
   - Rate limiting overview
   - Request/response format (JSON)

4. Authentication (300-500 words)
   - Auth method (JWT, API key, OAuth2)
   - Authentication flow diagram (sequence)
   - Token format and lifetime
   - Code example: how to authenticate
   - Error responses for auth failures (401, 403)

5. Common Patterns (200-400 words)
   - Pagination (offset/limit or cursor)
   - Filtering and sorting
   - Error response format
   - Date/time format (ISO 8601)
   - Common headers

6. Endpoints by Resource (800-2,000 words)
   - Group endpoints by resource (e.g., Podcasts, Episodes, Users)
   - Each resource section (H3):
     - Resource description (1-2 sentences)
     - Endpoints table (Method | Path | Description)
     - Detailed endpoint docs (H4):
       - Method + Path
       - Description
       - Request parameters (path, query, body)
       - Request body schema (with example)
       - Response schema (with example)
       - Error responses
       - Code example (curl or Python httpx)

7. Webhooks (if applicable) (200-400 words)
   - Event types
   - Payload format
   - Signature verification
   - Retry policy

8. Error Reference (200-300 words)
   - Error code table (Code | Message | Description | Resolution)
   - Common HTTP status codes used

9. SDKs and Libraries (100-200 words, optional)
   - Available client libraries
   - Installation instructions
   - Quick start example

10. Changelog (100-200 words)
    - Recent API changes
    - Deprecation notices
```

## Required Diagrams

| # | Diagram | Type | Complexity |
|---|---------|------|------------|
| 1 | Authentication flow | Sequence diagram | 3-4 participants |
| 2 | Request lifecycle | Flowchart | 6-8 nodes |
| 3 | Webhook delivery flow | Sequence diagram (if applicable) | 3-4 participants |

Minimum: 2 diagrams. Target: 3-4.

## Tables to Include

- Endpoints by resource (Method | Path | Description)
- Request/response parameters (Field | Type | Required | Description)
- Error codes reference
- Rate limits per endpoint
- Authentication header format

## Code Examples

Every endpoint should have at least one code example. Prefer:
1. `curl` for universal accessibility
2. Python `httpx` for async examples
3. TypeScript `fetch` for frontend consumers

Show both request and response:
```
Request:
  curl -X POST https://api.example.com/v1/podcasts \
    -H "Authorization: Bearer {token}" \
    -H "Content-Type: application/json" \
    -d '{"title": "My Podcast", "description": "..."}'

Response (201):
  {
    "id": 42,
    "title": "My Podcast",
    "created_at": "2026-02-01T10:00:00Z"
  }
```

## Audience Expectations

- **Frontend developers**: Want request/response schemas, auth setup, and code examples
- **Integration partners**: Want authentication, rate limits, and error handling
- **Backend developers**: Want endpoint contracts for service-to-service communication
