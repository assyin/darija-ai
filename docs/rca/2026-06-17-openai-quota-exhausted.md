# RCA — Épuisement du quota OpenAI (Proofreader)

**Date** : 2026-06-17 · **Sévérité** : faible (incident latent, impact nul) · **Statut** : documenté, compris.

## Résumé
Le quota OpenAI (utilisé par le **Proofreader** de scoring qualité, `gpt-4o-mini`) est épuisé
(`429 insufficient_quota`). Découvert le 2026-06-17 lors d'un diagnostic manuel.

## Timeline
- Dernier appel OpenAI réussi : **2026-06-15 12:31:25 UTC**.
- OpenAI fonctionnait normalement du 7 au 15 juin (0 échec).
- Quota épuisé après le 15/06. Premier échec observé : 2026-06-17 (test de diagnostic).

## Impact : **NUL**
- **0 article impacté.** Le pipeline était **en pause** (disjoncteur + reprise manuelle) sur
  toute la fenêtre OpenAI-down → aucun article à scorer pendant la panne.
- Les 5 articles sans score (ids 1, 11, 16, 23, 43, créés 26/05→03/06) sont des cas **legacy**
  antérieurs à la fonctionnalité de scoring — **sans rapport** avec ce quota.

## Cause racine
Quota/crédit OpenAI épuisé (problème opérationnel/facturation, comme le crédit Claude antérieurement).
Échec à `proofreader.py` → appel `chat.completions.create` → `429 insufficient_quota`.

## Comportement du système (correct)
Le pipeline gère l'échec en **fail-soft** : `_proofread_or_skip()` capture l'exception, le score
reste `NULL`, `proofread_ready_to_publish=False`, et `process()` continue (status `translated`).
**Pas de crash, pas de blocage, pas de coût (429 non facturé), pas de boucle retry.**

## Lacune identifiée (le vrai problème)
**Aucune alerte proactive** sur l'épuisement du quota OpenAI. Contrairement au crédit Claude
(détection `billing_error_detected` + Sentry + SpendGuard), l'épuisement OpenAI n'émet qu'un log
discret `proofreader.openai_failed`. On a été **chanceux** que la pause du pipeline masque la panne.

## Effet de bord latent (à la reprise)
Si le pipeline reprend **avant** la recharge OpenAI : les nouveaux articles seraient produits
**sans score qualité** (fail-soft) → l'owner perd le badge « ready ». Le draft est créé normalement.

## Recommandation de reprise
**Recharger OpenAI AVANT de reprendre le pipeline** (séquence propre, zéro article non noté).
Sinon : reprendre puis backfill-scorer le gap après recharge.

## Action future (backlog — NON planifiée)
→ Voir `project-roadmap.md` § Backlog opérationnel : **détection auto `insufficient_quota` OpenAI
+ alerte proactive** sur le modèle de la détection billing Claude.
