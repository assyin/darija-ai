# Infrastructure Context — DarijaAI

> Load this file when: infra changes, environment variables, service configuration, cost analysis.

---

## Service map

| Service | Provider | Plan | Purpose |
|---|---|---|---|
| Frontend | Vercel | Hobby (free) | Next.js hosting, ISR |
| Backend | Railway | Hobby ($5/mo) | FastAPI + worker |
| Database | Neon | Free (3GB) | PostgreSQL 16 |
| Cache/Queue | Upstash | Free (10K cmd/day) | Redis — job queue + response cache |
| Object Storage | Cloudflare R2 | Free (10GB) | Generated images |
| CDN | Cloudflare | Free | DNS + CDN |
| Email | Resend | Free (3K/mo) | Magic link auth + newsletter |
| Error tracking | Sentry | Free | Errors + performance traces |
| Monitoring | Uptime Robot | Free | Availability pings |
| Secrets | Doppler | Free dev tier | Secret management |

## Local dev

```
infra/docker-compose.yml  → postgres + redis (local only)
```

Run with: `docker compose -f infra/docker-compose.yml up -d`

## Environment variables

Three `.env.example` files:
- Root `.env.example` — minimal (rarely used)
- `backend/.env.example` — backend config (DB, Redis, API keys, R2)
- `frontend/.env.example` — Next.js public vars + backend URL

Secrets managed via Doppler in dev/staging/prod. `.env` files are git-ignored.

## AI costs (monthly estimate)

- Claude Haiku 4.5: ~$5/mo at 4 articles/day
- Replicate Flux Schnell: ~$0.003/image → ~$0.36/mo
- Total AI: ~$5.36/mo

Alert: Sentry fires if daily Claude spend > $5.

## R2 storage

Bucket: `darija-ai-images`. Public read enabled. Hash-based filenames (immutable, CDN-cacheable forever).
Images are always 1024×576 (16:9). Served via Cloudflare CDN.

## Rate limits

| Endpoint | Limit |
|---|---|
| Public API | 60 req/min/IP (Upstash Ratelimit) |
| Admin API | 600 req/min/user |
| Newsletter signup | 5/hour/IP |
| AI endpoints | 10/min/user |
