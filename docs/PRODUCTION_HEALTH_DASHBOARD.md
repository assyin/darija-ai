# Production Health Dashboard — Phase 1 (fondation, READ-ONLY)

> Mission P2-01. Nouvelle phase du projet : passer de l'ajout de fonctionnalités IA à
> l'**observabilité et la fiabilité de la production**. Cette première PR est **uniquement
> la fondation** : elle ne fait qu'**observer**, sans aucune action, aucun contrôle,
> aucune écriture.

## Objet

Une page admin unique — `/admin/health` — qui répond d'un coup d'œil à : *« est-ce que
toute la plateforme fonctionne normalement en ce moment ? »*. Elle agrège l'état déjà
existant (aucune nouvelle source de vérité) et le présente en quatre sections.

Cette page est pensée comme la future **Home Admin** : les dashboards spécialisés (ERE,
Human Audit, SpendGuard/Coûts) restent séparés ; celui-ci donne la **santé globale**.

## Garanties (contraintes de la mission)

- **Strictement read-only.** Chaque requête est un `SELECT`. Le bloc SpendGuard réutilise
  le lecteur read-only existant (`dashboard_service.ere_spendguard`) et n'appelle jamais
  `allow()` / `trip_*()` / `clear()`.
- **Aucun changement de comportement** : pas de worker, pas de scheduler, pas de SpendGuard,
  pas d'ERE, pas de publication modifiés. Aucune migration. Aucune nouvelle dépendance.
- **Aucune action, aucun bouton, aucun contrôle** côté UI — que des cartes.
- Le service ne fait **que des agrégations**, sans dupliquer la logique métier.

## Les 4 sections

| # | Section | Contenu |
|---|---|---|
| 1 | **Pipeline Status** | Une carte par étape (RSS Fetch, AI Processing, Translation, Editorial Ranking, Human Audit, Publication, SpendGuard) avec état `healthy` / `warning` / `critical`, icône, description courte. |
| 2 | **Last Activity** | Dernière activité de chaque étape + temps écoulé (« 3 minutes ago », « 22 days ago »), coloré selon l'état. |
| 3 | **SpendGuard Status** | Current State, Today/Month Spend, Daily/Monthly Cap, Pause Reason, Next Auto Resume. Lecture seule. |
| 4 | **Processing Queues** | Compteurs bruts : Pending, Processing, Failed, Rejected, Draft, Published. |

## Sources de données (agrégations)

| Signal | Source (read-only) |
|---|---|
| Last RSS Fetch | `MAX(raw_articles.fetched_at)` |
| Last AI Processing | `MAX(articles.created_at)` (un article créé = une localisation réussie) |
| Last Translation | `MAX(articles.updated_at) WHERE content_fr IS NOT NULL` *(approx. : `updated_at` bouge aussi à l'édition)* |
| Last Editorial Score | `MAX(raw_articles.score_breakdown->>'computed_at') WHERE editorial_score IS NOT NULL` |
| Last Human Audit | `MAX(editorial_audits.updated_at)` |
| Last Publication | `MAX(articles.published_at) WHERE is_published = true` |
| Pending / Processing / Failed / Rejected | `count(*) FILTER (…)` sur `raw_articles.processing_status` |
| Draft / Published | `count(*) FILTER (…)` sur `articles` (hors soft-delete) |
| SpendGuard | réutilise `dashboard_service.ere_spendguard` (spend `ai_logs` + flags Redis) |

## Règle de santé (traffic-light)

Dérivée **uniquement de l'âge** du signal (aucun calcul compliqué) :

- `healthy` tant que frais · `warning` au-delà d'un seuil doux · `critical` au-delà d'un seuil dur.
- Un signal **jamais vu** (`None`) → `warning` (inconnu), **pas** `critical` — une base fraîche/vide
  ne doit pas ressembler à une panne.

Seuils (soft / hard), définis dans `app/services/monitoring/health_service.py` :

| Étape | Warning | Critical |
|---|---|---|
| RSS Fetch | 2 h | 24 h |
| AI Processing | 12 h | 2 j |
| Translation | 3 j | 14 j |
| Editorial Ranking | 1 j | 3 j |
| Human Audit | 7 j | 30 j |
| Publication | 2 j | 4 j |
| SpendGuard | budget pause → warning | emergency/legacy pause → critical |

## API

`GET /api/v1/admin/health` — admin-gated (`require_admin`), renvoie `ProductionHealth`
(`app/schemas/health_dashboard.py`). Aucune route d'écriture n'existe dans ce module.

## Fichiers

- Backend : `app/schemas/health_dashboard.py`, `app/services/monitoring/health_service.py`,
  `app/api/v1/health_dashboard.py`, enregistré dans `app/main.py`.
- Frontend : `app/(admin)/admin/health/page.tsx`, entrée Sidebar (`components/admin/sidebar.tsx`).
- Tests : `tests/integration/test_health_dashboard_api.py` (auth, forme, compteurs, read-only).

## Design

Même Design System que le dashboard ERE : cartes slate claires, `Card`/`Badge` partagés,
responsive, sections identiques. *Note : la surface admin utilise volontairement le thème
clair (le thème « AI premium » dark est limité au public via `.theme-public` dans
`globals.css`), donc on reprend la palette slate du ERE plutôt que d'introduire des variantes
`dark:` qui divergeraient de ce Design System.*

## Hors périmètre (phases futures)

Cette Phase 1 n'affiche que de l'information. Les évolutions envisagées (non incluses ici) :
alertes proactives (« pipeline en pause depuis N h », « aucune publication depuis N j »),
graphiques de tendance, et actions (résoudre une pause, relancer une file) — toutes hors de
cette fondation read-only.
