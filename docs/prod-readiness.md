# 🚀 DarijaAI — Rapport de préparation Production

> Généré le **2026-05-25** · Branche `main` · Analyse basée sur `project-roadmap.md` + état réel du code + task-memory.
> Légende : ✅ fait · 🟡 partiel/scaffold · 🔲 à faire · 🚫 bloqué

---

## 📊 Synthèse exécutive

| Domaine | Avancement | Verdict |
|---|---|---|
| **Backend API** (public + admin) | ✅ ~95% | Production-ready MVP |
| **Auth & sécurité admin** | ✅ ~90% | OK MVP (hashing password à faire) |
| **Pipeline AI** (localisation, image, quality gate) | ✅ ~90% | Fonctionnel en one-shot |
| **Worker / Scheduler** (automatisation) | 🔲 ~5% | **Bloquant prod — non implémenté** |
| **Frontend public** | ✅ ~85% | Vérifié E2E, 3 fixes medium restants |
| **Frontend admin** | 🟡 ~40% | Scaffold + mock data, non câblé à l'API |
| **SEO** | 🟡 ~50% | JSON-LD OK, sitemap/robots/feed manquants |
| **Observabilité / coûts** | 🟡 ~30% | Sentry câblé mais DSN absent |
| **CI/CD + environnements** | 🔲 0% | **Bloquant prod — rien en place** |
| **Distribution** (newsletter, social) | 🔲 0% | Post-lancement |

**État global : MVP démo-ready, PAS prod-ready.** Trois chantiers bloquent réellement le passage en production :
1. 🚫 **Automatisation** (worker/scheduler) — l'ingestion dépend encore de commandes manuelles.
2. 🚫 **CI/CD + déploiement** — aucun pipeline ni environnement provisionné.
3. 🚫 **Admin câblé** — l'éditeur de drafts tourne sur des données mock, donc le workflow de review humain (obligatoire avant publication) n'existe pas réellement en bout-en-bout.

---

## ✅ Ce qui est IMPLÉMENTÉ et vérifié

### Phase 0 — Sécuriser l'état actuel ✅
- [x] Tests existants verts (36 tests unitaires + intégration)
- [x] Backend committé (API, schemas, migration, tests)
- [x] Frontend skeleton committé séparément
- [x] Fichiers contexte corrigés + task-memory à jour

### Phase 1 — Sécurité admin ✅ (90%)
- [x] `backend/app/core/security.py` créé — JWT HS256
- [x] `require_admin` dependency
- [x] Toutes les routes admin protégées (10 handlers)
- [x] Tests : sans token refusé / token invalide refusé / token valide accepté
- [x] Routes publiques restent accessibles
- [x] **Bonus** : rate limiting IP sur `/auth/token` (5 req / 10 min, Redis, fail-open)
- [ ] 🔲 Hashing password (bcrypt) — différé MVP, requis avant 1er collaborateur externe

### Phase 2 — Pipeline article 🟡 (logique OK, refactor à faire)
- [x] Fetch RSS + dedup (`rss_fetcher.py`, `ingestion.py`)
- [x] Relevance filter (`relevance_filter.py`)
- [x] Localisation Haiku 4.5 (`localizer.py`) + caching Redis
- [x] Quality gate 6 checks (`quality_gate.py`)
- [x] Génération image Flux Schnell + R2 (`image_generator.py`, `r2_storage.py`)
- [x] Save draft + cost logging (`ai_logs`)
- [ ] 🔲 **Refactor `process_article.py` (23KB god-script) → jobs découpés** (REFACTOR-01)
- [ ] 🔲 États clairs par étape (pending/processing/localized/.../failed) non formalisés
- [ ] 🔲 Retry propre par étape

### Phase 4 — API publique + admin ✅ (95%)
- [x] Endpoints publics : liste articles, détail par slug, settings
- [x] Endpoints admin : list drafts, PATCH, publish/unpublish, regenerate-image, settings
- [x] Pagination cursor-based standardisée
- [x] Erreurs standardisées (manque `request_id` — voir FIX-S5)
- [x] Router câblé dans `main.py`

### Phase 5 — Frontend public branché ✅ (85%, vérifié E2E 2026-05-06)
- [x] `frontend/lib/api-client.ts` (`publicApi.getArticles` / `getArticle`)
- [x] Pages home / liste articles / détail article branchées API réelle
- [x] Loading/error/empty states gérés
- [x] RTL vérifié, locale `ar-MA`, font Tajawal
- [x] Pages statiques about / contact / services

---

## 🔲 Ce qui RESTE pour passer en PROD

### 🚫 BLOQUANT — à faire impérativement avant prod

#### Phase 3 — Worker + Scheduler (automatisation) 🔲
> `backend/app/workers/jobs/` contient seulement un `.gitkeep` — **rien n'est implémenté**.
- [ ] Trancher la décision : `arq` (jobs async) + `APScheduler` (déclenchement périodique) — **décision HIGH ouverte**
- [ ] Créer le worker entrypoint
- [ ] Scheduler : fetch RSS / 30 min, process pending, retry failed
- [ ] Commandes Makefile : `make worker`, `make fetch-articles`, `make process-pending`
- [ ] Tests d'intégration worker

#### Phase 6 — Admin review workflow (REFACTOR-02 Phase B) 🟡 → 🔲
> Pages admin scaffoldées mais sur **données mock**, login non câblé. Le review humain obligatoire avant publication n'est pas opérationnel E2E.
- [ ] **Décision token storage : cookie vs localStorage** (bloque le démarrage — `frontend/lib/auth.ts` existe déjà, à valider)
- [ ] Login page → `POST /api/v1/auth/token`
- [ ] Câbler : liste drafts, détail draft, éditeur, settings, sources sur l'API réelle
- [ ] Page review draft : source + version Darija + image + résultat quality gate + coût AI
- [ ] Actions : éditer / rejeter / régénérer image / republier Sonnet (flagship) / publier
- [ ] Bloquer publication si quality gate failed (sauf override explicite)

#### Phase 9 — CI/CD + environnements 🔲
> `.github/workflows/` contient seulement un `.gitkeep` — **aucun pipeline**.
- [ ] GitHub Actions : lint · typecheck · tests · build front · build back
- [ ] Provisionner : Railway (backend) · Vercel (frontend) · Neon (DB) · Upstash (Redis) · R2 (images)
- [ ] Configurer les secrets repo (Doppler prod)
- [ ] Environnement **staging** avant production (décision Railway preview vs manuel — ouverte)
- [ ] Migration automatique contrôlée

### ⚠️ IMPORTANT — fortement recommandé avant lancement public

#### Phase 7 — SEO + contenu public 🟡 (50%)
- [x] JSON-LD `NewsArticle` sur pages article (vérifié E2E)
- [ ] 🔲 `sitemap.ts` (absent)
- [ ] 🔲 `robots.ts` (absent)
- [ ] 🔲 `feed.xml` (absent)
- [ ] 🔲 `generateMetadata()` sur home `/` et `/articles` (FIX-S1)
- [ ] 🔲 Pages legal : privacy, terms
- [ ] 🔲 Lighthouse mobile ≥ 95 (non mesuré)

#### Phase 8 — Observabilité + coûts 🟡 (30%)
- [x] Sentry **câblé** dans `main.py` (`_init_sentry` + `FastApiIntegration`)
- [ ] 🔲 Définir `SENTRY_DSN` (actuellement inactif — gated sur DSN absent)
- [ ] 🔲 Alerte coût Claude/Replicate > $5/jour
- [ ] 🔲 Dashboard admin : articles traités / drafts / rejected / coût journalier / queue depth
- [ ] 🔲 Alertes : backend down, error rate, scraping silencieux 24h
- [ ] 🔲 Uptime Robot

### 🐛 Fixes medium identifiés en vérification E2E (rapides)

| ID | Problème | Fichier | Effort |
|---|---|---|---|
| FIX-M2 | Pas de `not-found.tsx` → 404 anglais non-brandé, perd RTL | `frontend/app/[locale]/not-found.tsx` (absent) | ~20 min |
| FIX-M3 | OG image 1024×576 au lieu de 1200×630 | `articles/[slug]/page.tsx:42` | ~10–30 min |
| FIX-M1 | Calendly `href=""` → CTA se ré-navigue | `seed_site_settings.py` (`calendly_url` vide) | ~5 min |
| FIX-S5 | `request_id` manquant dans le body d'erreur 404 | `core/exceptions.py` | ~30 min |
| FIX-S4 | Pluriel arabe "1 مقالات" au lieu de "1 مقال" | `messages/ar-MA.json` | ~15 min |
| FIX-S1 | `generateMetadata` absent sur home/articles | `page.tsx`, `articles/page.tsx` | ~30 min |
| FIX-S2 | `dateModified` = `datePublished` en JSON-LD | `articles/[slug]/page.tsx:86` | ~20 min |

---

## 🎯 POST-LANCEMENT (non bloquant prod)

### Phase 10 — Distribution 🔲
- [ ] Newsletter Resend + page newsletter + capture email
- [ ] LinkedIn auto-draft · Instagram/Facebook plus tard
- [ ] Tracking source trafic
- [ ] (Modèle DB social existe, service non construit)

### Phase 11 — Beta privée 🔲
- [ ] Publier 30–50 articles · tester SEO · partager audience tech marocaine · collecter feedback

### Phase 12 — Lancement public 🔲
- [ ] 100 articles · pipeline stable · admin stable · SEO complet · monitoring actif · newsletter active

### Dette technique restante (LOW)
- [ ] REFACTOR-04 : configurer Sentry (DSN + alerte coût) — ~2h
- [ ] REFACTOR-05 : suite de tests frontend (Vitest + Playwright, 0 test actuellement) — ~1 session
- [ ] REFACTOR-06 : isoler/archiver le code AI non-prod (`cross_model_pipeline.py`, `openai_client.py`, etc.)
- [ ] Tests unitaires backend manquants : `localizer`, `scraping`
- [ ] Rate limiting sur routes publiques (60 req/min/IP — non intégré)

---

## 🧭 Chemin critique recommandé vers la PROD

```
1. Décisions à trancher d'abord (débloque le reste)
   ├─ Worker entrypoint : arq + APScheduler   [HIGH]
   └─ Token storage frontend : cookie vs localStorage   [MEDIUM]

2. Phase 3 — Worker + Scheduler              (automatise l'ingestion)
3. Phase 6 / REFACTOR-02 B — Admin câblé     (active le review humain réel)
   └─ inclut REFACTOR-01 (découpe process_article.py)
4. Fixes rapides E2E                          (M1/M2/M3 + S1/S4/S5)
5. Phase 7 — SEO (sitemap/robots/feed/metadata + legal pages)
6. Phase 8 — Observabilité (Sentry DSN + alertes coûts)
7. Phase 9 — CI/CD + staging + déploiement prod
   └─ GATE FINAL : passage en production
```

**Estimation des chantiers bloquants** : Worker (~1 session) + Admin Phase B (~1 session) + REFACTOR-01 (~1 session) + CI/CD & infra (~1–2 sessions) + SEO/observabilité (~1 session) ≈ **5–6 sessions de travail** avant un déploiement prod propre.

---

*Sources : `project-roadmap.md`, `docs/ai-context/task-memory/{implementation-status,pending-refactors,current-focus,recent-decisions}.md`, état réel du filesystem (workers/, .github/, main.py) au 2026-05-25.*
