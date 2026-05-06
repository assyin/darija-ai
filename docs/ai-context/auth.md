# Auth Context — DarijaAI

> Load this file when: authentication, authorization, admin panel, JWT, rate limiting, CORS.

---

## Auth model

**Public site**: No auth. Fully public read access.

**Admin panel** (`/admin/*`): NextAuth.js with email magic link via Resend.
- Single admin user initially (the owner).
- Session stored in cookie, JWT-signed.

**Backend admin endpoints**: `Authorization: Bearer <admin_jwt>` header required.
- JWT: HS256, 1h expiry.
- Refresh tokens: 30 days.
- Rotate JWT secret quarterly.

## FastAPI dependency pattern

```python
user: AdminUser = Depends(require_admin)  # protects any admin route
```

All admin route handlers use `require_admin` dependency. Zero exceptions.

## CORS

- `allow_origins`: frontend origin only. Never `"*"` in production.
- Specific methods only — not `["*"]`.

## Security rules

- Secrets via Doppler only. Never in code, logs, or commits.
- `gitleaks` pre-commit hook enforces no-secrets-in-git.
- HTML: `bleach` on backend, `rehype-sanitize` on frontend.
- SQLAlchemy parameterized queries only. No raw SQL outside Alembic migrations.

## Rate limiting

| Endpoint | Limit | Mechanism |
|---|---|---|
| Public API | 60 req/min/IP | Upstash Ratelimit |
| Admin API | 600 req/min/user | Upstash Ratelimit |
| Newsletter | 5/hour/IP | Upstash Ratelimit |
| AI endpoints | 10/min/user | Upstash Ratelimit |

## Status

NextAuth magic-link flow is scaffolded in frontend. Backend JWT validation is in `backend/app/core/security.py`.
Full auth wiring (login → session → protected routes) is pending integration.
