# 🛠️ DarijaAI — Plan d'implémentation vers la Production

> Généré le **2026-05-25** · Complément de `PROD-READINESS.md`.
> Ordonné par priorité d'exécution. Chaque lot = objectif + tâches + fichiers + critères d'acceptation.
> Priorités : **P0** bloquant prod · **P1** requis avant lancement public · **P2** post-lancement.

---

## ⚙️ ÉTAPE 0 — Décisions à trancher AVANT de coder

Deux décisions débloquent l'essentiel du travail. À acter en premier :

| # | Décision | Recommandation | Impact |
|---|---|---|---|
| D1 | **Worker** : `arq` (queue) vs `APScheduler` seul | **arq pour les jobs + APScheduler pour le déclenchement périodique** (déjà la direction roadmap, arq est installé) | Débloque tout le lot P0-A |
| D2 | **Token storage frontend** : cookie vs localStorage | **Cookie `httpOnly` Secure SameSite=Lax** (résiste au XSS, compatible RSC) | Débloque le lot P0-C (admin) |

> `frontend/lib/auth.ts` existe déjà — vérifier ce qu'il contient avant d'implémenter D2.

---

# 🔴 P0 — BLOQUANT PRODUCTION

> Sans ces trois lots, pas de mise en prod : l'ingestion reste manuelle, le review humain n'existe pas E2E, et il n'y a aucun déploiement.

## P0-A · Worker + Scheduler (Phase 3 roadmap · REFACTOR-01)
**Objectif** : automatiser l'ingestion et rendre le pipeline schedulable/retryable.
**Pré-requis** : D1 tranchée.

1. Découper `app/scripts/process_article.py` (god-script 23KB) en jobs unitaires :
   - `app/workers/jobs/fetch_articles.py` — fetch RSS + dedup
   - `app/workers/jobs/process_articles.py` — relevance → localize → quality gate → image → save draft
   - `app/workers/jobs/retry_failed.py`
2. Formaliser l'**état par étape** sur le modèle article (enum VARCHAR + CHECK, pas de booléens) :
   `pending → processing → localized → image_ready → draft → rejected → failed`
   - ⚠️ Migration Alembic dédiée (jamais éditer une migration mergée).
3. `app/workers/scheduler.py` — entrypoint APScheduler : fetch RSS / 30 min, process pending, retry failed.
4. `app/workers/main.py` — entrypoint worker arq.
5. Retry propre par étape (tenacity + timeout, déjà la convention backend) + logs structurés `structlog` par étape.
6. Garder `process_article.py` uniquement comme wrapper one-shot temporaire.
7. Commandes (créer le **Makefile manquant**) : `make worker`, `make fetch-articles`, `make process-pending`.

**Tests** : intégration worker (Postgres + Redis réels), 1 happy path + 1 retry/failed path par job.
**Acceptation** : un article passe `pending → draft` sans intervention manuelle ; un échec transitoire est retryé ; le scheduler tourne en continu.

## P0-B · Admin câblé à l'API réelle (Phase 6 · REFACTOR-02 Phase B)
**Objectif** : rendre opérationnel le workflow de review humain (obligatoire avant toute publication).
**Pré-requis** : D2 tranchée.

1. Login `frontend/app/admin` → `POST /api/v1/auth/token` ; stockage token selon D2 ; helper d'auth (`lib/auth.ts`) + intercepteur `Authorization: Bearer`.
2. Remplacer les **mock data** par l'API réelle sur : liste drafts, détail draft, éditeur markdown, settings, sources.
3. **Page review draft** affichant : article source · version Darija · image générée · résultat quality gate · coût AI.
4. Actions : éditer · rejeter · régénérer image · republier avec Sonnet (flagship) · publier.
5. **Bloquer la publication si quality gate failed** sauf override explicite (règle CLAUDE.md — human review mandatory, jamais d'auto-publish).
6. Historique minimal des changements.

**Acceptation** : login réel → liste des drafts depuis la DB → édition → publication → l'article apparaît sur le site public. Aucune donnée mock restante.

## P0-C · CI/CD + Environnements (Phase 9 roadmap)
**Objectif** : déploiement fiable et reproductible.

1. `.github/workflows/ci.yml` : lint (`ruff`) · typecheck (`mypy --strict` + `pnpm tsc`) · tests (`pytest` + front) · build front · build back.
2. Provisionner : **Railway** (backend) · **Vercel** (frontend) · **Neon** (Postgres) · **Upstash** (Redis) · **R2** (images).
3. Secrets via **Doppler** (jamais en clair) ; configurer les secrets repo GitHub.
4. **Staging** avant prod (décision Railway preview vs manuel — à trancher).
5. Migration Alembic automatique mais contrôlée (étape déploiement dédiée, jamais destructive).
6. CORS = origine frontend uniquement (pas de wildcard en prod).

**Acceptation** : push sur `main` → CI verte → déploiement staging auto → promotion prod manuelle ; migrations appliquées proprement.

---

# 🟠 P1 — REQUIS AVANT LANCEMENT PUBLIC

## P1-A · SEO complet (Phase 7 roadmap)
1. `frontend/app/sitemap.ts` · `robots.ts` · `feed.xml` (RSS).
2. `generateMetadata()` sur **home `/`** et **`/articles`** (FIX-S1) via `getSiteSettings()`.
3. Pages legal : `privacy`, `terms` (about/contact/services déjà faits).
4. OG image 1200×630 (voir FIX-M3) · canonical URL · JSON-LD déjà OK sur articles.
5. Cible **Lighthouse mobile ≥ 95** (mesurer + corriger).

## P1-B · Observabilité + coûts (Phase 8 roadmap · REFACTOR-04)
> Sentry est déjà **câblé** dans `main.py` (`_init_sentry` + `FastApiIntegration`), seul le DSN manque.
1. Définir `SENTRY_DSN` (backend + frontend) → active error tracking + tracing.
2. Alerte coût Claude/Replicate **> $5/jour** (table `ai_logs` déjà alimentée).
3. Dashboard admin : articles traités · drafts · rejected · coût journalier · queue depth.
4. Alertes : backend down · error rate · scraping silencieux 24h.
5. **Uptime Robot** sur `/health` (déjà opérationnel : DB + Redis checks).

## P1-C · Fixes E2E rapides (lot « quick wins », ~2h cumulées)
| ID | Fix | Fichier | Effort |
|---|---|---|---|
| FIX-M2 | `not-found.tsx` brandé Darija + RTL | `frontend/app/[locale]/not-found.tsx` | 20 min |
| FIX-M3 | OG dims 1200×630 (ou doc déviation flux-schnell 1024×576) | `articles/[slug]/page.tsx:42` | 10–30 min |
| FIX-M1 | `calendly_url` réel ou retirer le lien du CTA | `seed_site_settings.py` | 5 min |
| FIX-S5 | `request_id` dans le body d'erreur | `core/exceptions.py` | 30 min |
| FIX-S4 | Pluriel arabe ICU `{count, plural, ...}` | `messages/ar-MA.json` | 15 min |
| FIX-S2 | `dateModified = updated_at` (+ exposer `updated_at` au public) | `articles/[slug]/page.tsx:86` + schema | 20 min |
| — | Hashing password admin (bcrypt/passlib) avant tout accès externe | `core/security.py` | 30 min |
| — | Rate limiting routes publiques (60 req/min/IP) | middleware public | 30 min |

## P1-D · Couverture de tests
- Tests unitaires backend manquants : `localizer`, `scraping` (cible 80% sur `services/`).
- **REFACTOR-05** : suite frontend Vitest + Testing Library + 3 parcours Playwright (home→article, login→publish, newsletter signup).

---

# 🟢 P2 — POST-LANCEMENT

## P2-A · Distribution (Phase 10)
- Newsletter **Resend** + page newsletter + capture email + tracking source trafic.
- LinkedIn auto-draft (publication manuelle au début) · Instagram/Facebook plus tard.
- Service de logging social (modèle DB existe déjà).

## P2-B · Beta privée (Phase 11)
- Publier 30–50 articles · tester SEO · partager audience tech marocaine · collecter feedback (qualité Darija, sujets, lisibilité mobile, confiance).

## P2-C · Lancement public (Phase 12)
- 100 articles · pipeline stable · admin stable · SEO complet · monitoring actif · newsletter active · plan de contenu hebdo.

## P2-D · Dette technique (LOW)
- REFACTOR-06 : isoler/archiver le code AI non-prod (`cross_model_pipeline.py`, `openai_client.py`, `critic_editor.py`).
- REFACTOR-07 : discipline `localizer_v1.md` figé → toute évolution = `localizer_v2.md`.

---

## 🧭 Séquencement recommandé

```
ÉTAPE 0  : trancher D1 (worker) + D2 (token storage)        ← prérequis
   │
   ├─ P0-A  Worker + Scheduler        (~1–2 sessions, inclut REFACTOR-01)
   ├─ P0-B  Admin câblé               (~1 session)   [dépend de D2]
   └─ P0-C  CI/CD + infra             (~1–2 sessions)
        │
        ▼  (en parallèle des fixes rapides P1-C dès maintenant)
   P1-A SEO  +  P1-B Observabilité  +  P1-D Tests   (~2 sessions)
        │
        ▼   ════════ GATE PRODUCTION ════════
   P2  Distribution → Beta → Lancement public
```

**Estimation chemin critique (P0 + P1)** : ~5–7 sessions de travail avant un déploiement prod propre.
**Conseil** : les fixes rapides P1-C (sauf ceux liés au backend schema) peuvent être faits dès maintenant en parallèle, sans attendre les décisions D1/D2.

---

*Référence état réel : `PROD-READINESS.md` · task-memory `docs/ai-context/task-memory/`.*
