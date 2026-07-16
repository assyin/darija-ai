# Production Health Dashboard (READ-ONLY)

> Mission P2-01 (fondation) + P2-01B (durcissement UX/observabilité).
> Une page admin unique — `/admin/health` — qui répond d'un coup d'œil : *« est-ce que
> toute la plateforme fonctionne, et si non, où est-ce bloqué ? »*. **Elle ne fait
> qu'observer** : aucune action, aucun contrôle, aucune écriture.

## Garanties (contraintes de la mission)

- **Strictement read-only.** Chaque requête est un `SELECT` ; le bloc SpendGuard réutilise
  le lecteur read-only existant (`dashboard_service.ere_spendguard`) et n'appelle jamais
  `allow()` / `trip_*()` / `clear()`.
- **Aucun changement de comportement** : pas de worker, scheduler, SpendGuard, ERE,
  Human Audit ou publication modifiés. Aucune migration. Aucune nouvelle dépendance.
  Aucun nouveau feature flag.
- **Aucune action / bouton / contrôle** côté UI — que des cartes et des liens de navigation.
- Le service ne fait **que des agrégations**, sans dupliquer la logique métier.

## Sections de la page

| Section | Contenu |
|---|---|
| **Global Status Banner** | Bannière `Production Healthy` / `Attention Required` / `Production Incident`, dérivée du **pire** état d'étape, + explication + horodatage du snapshot. |
| **Pipeline Flow** | Flux visuel RSS Fetch → Pending → AI Processing → Translation → Editorial Ranking → Human Audit → Draft → Published, chaque nœud portant son compteur/signal (légende explicite). |
| **Pipeline Status** | 7 cartes (les 6 étapes + SpendGuard) avec état + raison de dégradation. |
| **Queue Trends (24 h)** | Tendances honnêtes (débit horodaté) : current / previous / delta / direction (↑ ↓ =). |
| **Last Activity** | Dernière activité + temps écoulé (« 22 days ago »). |
| **SpendGuard Status** | Current State, Today/Month Spend, Daily/Monthly Cap, Pause Reason, Next Auto Resume. |
| **Processing Queues** | Compteurs : Pending / Processing / Failed / Rejected / Draft / Published. |
| **Recent Error** | Dernière erreur structurée (ai_logs), sanitizée — ou « No recent structured error available ». |
| **Quick Navigation** | Liens lecture seule : ERE, Human Audit, Articles/Drafts, AI Costs, Settings. |

## Règles de santé

La santé d'une étape est le **pire** de deux signaux :

1. **Activity-age** — fraîcheur du dernier événement (temps). `healthy` frais → `warning`
   seuil doux → `critical` seuil dur ; jamais-vu (`None`) → `warning` (pas de faux
   `critical` sur base vide).
2. **Queue-health** — la file elle-même est-elle engorgée / bloquée (compteurs). Applied
   à l'étape **AI Processing**.

### Seuils (un seul endroit documenté : `services/monitoring/health_service.py`)

**Activity-age** (warning / critical) :

| Étape | Warning | Critical |
|---|---|---|
| RSS Fetch | 2 h | 24 h |
| AI Processing | 12 h | 2 j |
| Translation | 3 j | 14 j |
| Editorial Ranking | 1 j | 3 j |
| Human Audit | 7 j | 30 j |
| Publication | 2 j | 4 j |

**Queue-health** (dégrade AI Processing) :

| Règle | Warning | Critical |
|---|---|---|
| Pending | > 500 | > 1000 |
| Failed | > 20 | > 100 |
| Processing bloqué (ancienneté) | > 24 h | > 5 j |
| SpendGuard | budget pause → warning | emergency/legacy pause → critical |

L'état final d'une étape = `worst(activity-age, queue-health)`. La bannière globale =
`worst(toutes les étapes)`.

## Sources de données & limites d'honnêteté

| Signal | Source (read-only) | Note |
|---|---|---|
| Last RSS Fetch | `MAX(raw_articles.fetched_at)` | — |
| Last AI Processing | `MAX(articles.created_at)` | un article créé = une localisation réussie |
| Last Translation | `MAX(articles.updated_at) WHERE content_fr IS NOT NULL` | **approx.** : `updated_at` bouge aussi à l'édition |
| Last Editorial Score | `MAX(score_breakdown->>'computed_at')` | pas de colonne dédiée |
| Last Human Audit | `MAX(editorial_audits.updated_at)` | — |
| Last Publication | `MAX(articles.published_at)` | — |
| Compteurs de file | `count(*) FILTER (…)` | point-in-time |
| Processing bloqué | `MIN(fetched_at) WHERE status='processing'` | **proxy** : pas d'horodatage de changement de statut |
| Recent Error | `ai_logs (success=false)` | **seule** source d'erreur structurée fiable |
| SpendGuard | `ere_spendguard` (ai_logs + Redis) | réutilisé |

### ⚠️ Limitation — tendances des profondeurs de file

Les compteurs `pending`, `processing`, `failed`, `rejected`, `draft` sont des **profondeurs
instantanées**. Le schéma ne conserve **aucun historique de changement de statut**, donc une
valeur « il y a 24 h » **ne peut pas être dérivée honnêtement** sans une nouvelle table de
snapshots (hors périmètre : aucune migration ici). Ces compteurs sont donc listés dans
`trends_unavailable` et **aucun delta trompeur n'est affiché**.

Les **tendances publiées** ne concernent que le **débit horodaté** (honnête) :

| Trend | Basis |
|---|---|
| Récupérés (RSS) | `raw_articles.fetched_at` |
| Traités (IA) | `articles.created_at` |
| Publiés | `articles.published_at` |
| Audités | `editorial_audits.created_at` |

Fenêtre : `[now-24h, now)` vs `[now-48h, now-24h)`, bornée sur l'horloge de l'appelant
(déterministe et testable).

### Sanitisation des erreurs

`sanitize_error()` : première ligne seulement (pas de stack trace), secrets **redigés**
(`sk-…`, `r8_…`, `Bearer …`, clés AWS `AKIA…`, `api_key=…`/`token=…`, longs hex),
tronquée à 200 caractères. Ne fuit jamais de token, payload, ou config sensible.

## API

`GET /api/v1/admin/health` — admin-gated (`require_admin`), renvoie `ProductionHealth`
(`app/schemas/health_dashboard.py`). Aucune route d'écriture n'existe dans ce module.

## Fichiers

- Backend : `app/schemas/health_dashboard.py`, `app/services/monitoring/health_service.py`,
  `app/api/v1/health_dashboard.py`, enregistré dans `app/main.py`.
- Frontend : `app/(admin)/admin/health/page.tsx`, entrée Sidebar (`components/admin/sidebar.tsx`).
- Tests : `tests/unit/services/monitoring/test_health_rules.py` (règles pures : banner,
  seuils queue, direction, sanitize) + `tests/integration/test_health_dashboard_api.py`
  (auth, forme, flow, trends, erreur sanitizée, read-only).

## Design

Même Design System que le dashboard ERE : cartes slate claires, `Card`/`Badge` partagés,
responsive, sections cohérentes. États **accessibles** : label texte + icône (`Healthy` /
`Warning` / `Critical`, ↑ ↓ =), jamais couleur seule. *Note : la surface admin utilise
volontairement le thème clair (le thème « AI premium » dark est limité au public via
`.theme-public` dans `globals.css`), donc on reprend la palette slate du ERE plutôt que
d'introduire des variantes `dark:` qui divergeraient de ce Design System.*

## Future Admin Landing Page — changement de routing (HORS de cette PR)

`/admin/health` est conçue pour devenir la **Home Admin**. Aujourd'hui l'index admin
(`frontend/app/(admin)/admin/page.tsx`) redirige vers `/admin/articles` :

```tsx
export default function AdminIndex() {
  redirect("/admin/articles");
}
```

Pour faire de la santé la page d'accueil, il suffira de **remplacer** la cible :

```tsx
redirect("/admin/health");
```

C'est un one-liner trivial et sans risque, mais il **reste volontairement hors de cette PR**
tant qu'il n'est pas explicitement approuvé (la mission demande de ne pas changer la route
par défaut ici).

## Hors périmètre (phases futures)

Alertes proactives (« pipeline en pause depuis N h », « aucune publication depuis N j »),
graphiques de tendance riches, table de snapshots pour l'historique des profondeurs de file,
et toute action (résoudre une pause, relancer une file) — hors de cette fondation read-only.
