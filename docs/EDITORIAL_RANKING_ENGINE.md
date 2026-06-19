# Editorial Ranking Engine (ERE) — Design Document

> **Statut : DESIGN / SPÉCIFICATION — non implémenté.**
> Aucun code, aucune PR, aucune migration, aucune modification production.
> Document de référence hors ligne (non commité tant que non décidé).
> Créé : 2026-06-13. Owner : Yassine (TitritAI).

---

## 0. Contexte & décision produit

DarijaAI passe de **« pipeline de publication »** (publier tout ce qui est traduisible) à **« système éditorial orienté qualité »**.

Décision produit validée :
- **Objectif : 10 à 15 articles maximum / jour.**
- Priorité : **qualité éditoriale, importance, pertinence** — pas le volume.
- **Ne plus localiser tous les articles** qui passent le pré-filtre.
- **Classer les articles AVANT localisation** ; localiser **uniquement les sélectionnés**.
- **Backlog historique (~1465 `processing`) gelé et hors scope.**
- Ne pas devenir un agrégateur RSS publiant 50-100 articles/jour.

État système de référence (déjà en prod, à préserver) :
- Pré-filtre V8 (off-topic bloqué avant Claude) — OK.
- SpendGuard (plafond dur $2/jour, arrêt préventif) — OK.
- Rejets-modèle terminaux (fuite retry éliminée) — OK.
- Coût sous contrôle.

---

## 1. Thèse architecturale (le pivot)

Le système actuel **localise tout** ce qui passe le pré-filtre (~$0.06/article), **puis** le Proofreader note la *sortie*. Pour publier seulement 10-15 articles/jour à forte valeur, on inverse :

> **Classer AVANT de localiser.** On note les articles **bruts (EN)**, on sélectionne le top quotidien, on ne localise QUE les sélectionnés.

Trois gains simultanés :
1. **Qualité** — sélection éditoriale, pas volume.
2. **Coût** — localiser ~12 au lieu de ~85 → ~$0.9/jour au lieu de ~$2.
3. **Séparation des préoccupations** — *« vaut-il d'être publié ? »* (ranking, sur EN brut) ≠ *« la traduction est-elle bonne ? »* (Proofreader, sur la sortie).

Deux couches de scoring DISTINCTES :

| Couche | Quand | Sur quoi | Existe ? |
|---|---|---|---|
| **Editorial score** (importance) | **avant** Localizer | titre + extrait EN | ❌ à construire (cet ERE) |
| **Proofread score** (qualité trad.) | **après** Localizer | sortie Darija/FR | ✅ existe déjà |

---

## 2. Editorial Ranking Engine — vue d'ensemble

Service de **sélection quotidienne** inséré entre l'ingestion et la localisation, en **2 étages cost-aware** :

- **Étage 1 — Pré-score déterministe (zéro LLM)** : métadonnées du `raw_article` — qualité de source, fraîcheur, densité IA/Tech, entités MENA. Coût nul.
- **Étage 2 — Scoreur LLM (Haiku, bon marché)** : pour les **top-K survivants** (~30-40), **un seul appel Haiku sur titre + extrait** (~$0.002/candidat) → sous-scores *importance / impact business / intérêt lecteur / pertinence affinée / pertinence MENA* en sortie JSON structurée.

**Cycle de sélection** (job périodique) :
```
candidats (raw 'pending', filtrés V8)
  → Étage 1 : pré-score déterministe
  → Dédup par sujet (clustering) → boost de corroboration multi-source
  → Étage 2 : scoreur LLM sur top-K
  → Score global /100 + classification en tier
  → Sélection quota-aware → top N "selected", reste "deferred"
```

---

## 3. Signaux de scoring — calcul de chacun

| Signal | Méthode | Source |
|---|---|---|
| **Pertinence IA/Tech** | Étage 1 (densité du lexique V8 en score continu) + Étage 2 (topic-fit) | corpus + LLM |
| **Importance de l'actualité** | Étage 2 (lancement, levée, M&A, percée, régulation vs incrémental) + **corroboration multi-source** | LLM + dédup |
| **Potentiel d'intérêt lecteur** | Étage 2 (un lecteur francophone/marocain tech cliquerait-il ? nouveauté, « talkability ») | LLM |
| **Impact business** | Étage 2 (montants de levée, M&A, adoption entreprise, market-moving) | LLM |
| **Impact MENA/Afrique/Maroc** | Étage 1 (entités : Yassir, InstaDeep, Maroc, CEDEAO… + géo) + Étage 2 (pertinence régionale) | entités + LLM |
| **Qualité de la source** | Étage 1 **déterministe** : `sources.editorial_tier` curé manuellement | config |
| **Fraîcheur** | Étage 1 **déterministe** : décroissance sur `published_at` | métadonnée |

Le scoreur LLM renvoie les sous-scores 1/2/3/4/5 en **un seul appel** (JSON structuré), combinés aux signaux déterministes 6/7. Prompt versionné (`prompts/editorial_scorer_v1.md`), **garde anti-ancrage** (leçon Proofreader v4) pour éviter la convergence des scores.

---

## 4. Pondérations proposées (score /100)

| Signal | Poids | Rationale |
|---|---:|---|
| Pertinence IA/Tech | **22** | Cœur : doit être on-topic pour mériter un slot |
| Importance de l'actualité | **20** | Événement majeur vs incrémental |
| Potentiel d'intérêt lecteur | **16** | Différenciateur vs agrégateur générique |
| Impact business | **12** | Levées, M&A, adoption |
| Impact MENA/Afrique/Maroc | **12** | Cible audience (francophone/marocain) |
| Qualité de la source | **10** | Crédibilité |
| Fraîcheur | **8** | Pénalise le vieux sans dominer |
| **Total** | **100** | |

`score_global = Σ (signal_i × poids_i) / 100`.

**Ce sont des points de départ « à dire d'expert »**, à calibrer contre un baseline éditorial humain (cf. §11 et critères GO/NO-GO).

---

## 5. Quotas éditoriaux

| Quota | Valeur proposée | But |
|---|---|---|
| Max articles/jour | cible **12**, plafond dur **15** | Volume maîtrisé |
| Max/source/jour | **3** | Anti-monoculture |
| Max/catégorie/jour | **4** | Diversité |
| Anti-duplication de sujet | **clustering** | 1 article par événement |

**Anti-duplication** : regrouper les `raw_articles` du même événement (ex. « OpenAI lance X » vu par 5 sources) :
- **V1** : heuristique — n-grammes de titre + entités communes + URL canonique.
- **V2** : similarité cosinus d'**embeddings** (seuil).
- On garde **1 par cluster** (mieux scoré, meilleure source). La **corroboration** multi-source **booste** le signal *Importance* du gardé.

---

## 6. Tiering : breaking / important / secondaire / bruit

| Tier | Critère | Traitement |
|---|---|---|
| **Breaking majeur** | score ≥ 85 ET importance haute ET frais ET (corroboration OU source top-tier) | **Fast-lane** : localisé immédiatement, hors batch, +1-2 slots tolérés. Rare. |
| **Important** | score 70-84 | **Cœur des 10-15**, par rang jusqu'au quota |
| **Secondaire** | score 50-69 | Remplit les slots restants *si dispo* ; sinon **deferred** |
| **Bruit** | score < 50 | **Abandonné** (jamais localisé) |

→ Même avec 85 articles post-pré-filtre, seuls ~12 sont localisés/publiés. Le reste = secondaire/bruit, non publié.

---

## 7. Workflow proposé

```
RSS fetch (cron 30min)
  └─ Pré-filtre V8           [INCHANGÉ]   → off-topic/junk éliminés
       └─ raw_articles 'pending'  = POOL DE CANDIDATS
            └─ ★ EDITORIAL RANKING ENGINE  [NOUVEAU — job périodique]
                 a) pré-score déterministe (source, fraîcheur, IA, MENA)
                 b) dédup par sujet → boost corroboration
                 c) scoreur LLM Haiku (titre+extrait) sur top-K
                 d) score /100 + tier
                 e) sélection quota-aware → 'selected' / 'deferred'
                      └─ Localizer + FrenchLocalizer  [INCHANGÉ, seulement 'selected']
                           └─ QualityGate + Proofreader  [INCHANGÉ — garde qualité finale]
                                └─ Publication (is_published=False, revue humaine)  [INCHANGÉ]

   ↘ Breaking fast-lane : court-circuite le batch → localisation immédiate
```

Le Proofreader reste la **garde qualité finale post-localisation** ; `proofread_ready_to_publish` devient un input à la décision de publier, **pas** la sélection éditoriale.

---

## 8. Modifications minimales (ancrées dans le schéma réel)

| # | Élément | Changement | Type |
|---|---|---|---|
| A | `sources` | + `editorial_tier` (ou `quality_weight` 0-100) | migration |
| B | `raw_articles` | + `editorial_score` (int), `score_breakdown` (JSONB), `news_tier` (varchar+CHECK), `topic_cluster_id`, `editorial_decision` (enum: `unranked`/`selected`/`deferred`/`breaking`) | migration |
| C | `services/editorial/ranking_engine.py` | **nouveau** : SignalScorer + Selector + quotas (logique pure, testable) | code |
| D | `services/editorial/topic_dedup.py` | **nouveau** : clustering (V1 heuristique → V2 embeddings) | code |
| E | `services/ai/prompts/editorial_scorer_v1.md` | **nouveau** : prompt du scoreur LLM | prompt |
| F | `workers/jobs/rank_pending.py` | **nouveau** : cron (2-4h ou 1×/jour) → score, dédup, sélectionne top N | code |
| G | `workers/jobs/process_articles.py` | **1 ligne** : `process_pending` filtre `WHERE editorial_decision='selected'` | code |
| H | `core/config.py` | quota/jour, caps source/catégorie, seuils de tier, poids | config |
| I | Admin (frontend) | exposer score/tier/décision (pourquoi sélectionné/différé) | code |

**Découplage clé** : `editorial_decision` (sélection) est **séparé** de `processing_status` (cycle de localisation) → aucun conflit avec SpendGuard, retry-fix, pré-filtre. On **insère** une étape, on ne réécrit rien.

**Inchangé** : pré-filtre V8, SpendGuard, retry-fix, Localizer, FrenchLocalizer, Proofreader, QualityGate, backlog gelé.

---

## 9. Roadmap MVP → V2 → V3

| Phase | Contenu | Objectif |
|---|---|---|
| **MVP (V1)** | Scoring **Étage 1 déterministe seul** (source-tier + fraîcheur + densité IA + entités MENA) · quotas · dédup **heuristique** · job de sélection quotidien · `process_pending` gated `selected`. **Pas de LLM.** | Valider la réduction de volume + la mécanique de quotas, à coût ~nul. Poids calibrés manuellement. |
| **V2** | + **Scoreur LLM Haiku** (importance/business/intérêt) · dédup par **embeddings** · **fast-lane breaking** · scores visibles dans l'admin · calibrage des poids contre échantillon labellisé. | Sélection « intelligente ». |
| **V3** | **Boucle d'apprentissage** : décisions approuver/rejeter/publier de l'owner → auto-ajustement des poids (ou ranker appris) · signaux d'**engagement** (`views_count`) · quotas dynamiques par catégorie. | Système éditorial auto-apprenant. |

---

## 10. Impact coût (estimé)

- Scoring : ~85 candidats × ~$0.002 (Haiku titre+extrait) ≈ **$0.17/jour**.
- Localisation : ~12 sélectionnés × ~$0.06 ≈ **$0.72/jour**.
- **Total ≈ ~$0.9/jour ≈ ~$27/mo** — sous le cap $50, **inférieur à l'actuel** (~$2/jour), avec **qualité supérieure**. **SpendGuard reste le backstop.**

---

## 11. Risques

| Risque | Mitigation |
|---|---|
| Poids/seuils non calibrés | Baseline éditorial humain (owner note ~30-50 articles) avant de figer |
| Scoreur LLM incohérent/ancré | Garde anti-ancrage (leçon Proofreader v4) ; sortie structurée |
| Dédup fusionne des sujets distincts | Démarrer **conservateur** (seuil haut) ; mesurer faux-merges |
| Breaking raté (recall) ou latence | Fast-lane plus fréquent que le batch ; corroboration multi-source |
| MVP déterministe trop grossier | Acceptable pour *réduire le volume* ; l'intelligence arrive en V2 |
| Sélection nécessite trop d'override manuel | Signal de NO-GO (cf. §12) — revoir poids/signaux |
| Interaction quota × SpendGuard | Le ranking rend la dépense **prédictible** ; SpendGuard = filet |

---

## 12. Critères GO / NO-GO

### Gate 0 — GO pour construire le MVP
**GO si** : (1) baseline éditorial humain établi (~30-50 articles notés par l'owner) ; (2) poids §4 et quotas §5 validés ; (3) découplage `editorial_decision` confirmé non-cassant pour l'existant ; (4) liste de sources + `editorial_tier` initiale rédigée.
**NO-GO si** : pas de baseline humain → on construirait à l'aveugle.

### Gate 1 — GO du MVP vers V2
**GO si**, sur ≥ 5 jours d'observation :
- volume publié **stabilisé à 10-15/jour** (plafond jamais franchi) ;
- **recall des « majeures »** : ≤ 1 actualité majeure manquée / semaine (vérifié vs jugement owner) ;
- **coût** sous budget, SpendGuard non déclenché par le flux normal ;
- **0 régression** du pipeline existant (pré-filtre/SpendGuard/retry/localisation) ;
- taux d'**override manuel** de la sélection < 30 %.

**NO-GO si** : le déterministe rate trop de majeures (recall faible) OU override > 50 % → V2 (LLM) requis avant d'élargir, ou revoir signaux.

### Gate 2 — GO de V2 vers V3
**GO si** :
- la sélection V2 **égale ou dépasse** le jugement éditorial humain sur un set de validation (précision/recall sur « publier vs différer ») ;
- dédup embeddings : faux-merges < 5 % ;
- données d'engagement (`views_count`) disponibles et exploitables ;
- override manuel < 15 %.

**NO-GO si** : scoreur LLM incohérent/ancré, ou pas assez de données d'engagement pour apprendre.

### Critères de succès globaux (la cible business)
- **Volume** : 10-15 articles/jour, jamais plus.
- **Qualité** : qualité éditoriale moyenne perçue en hausse nette (jugement owner + engagement).
- **Couverture** : rester à jour sur les actualités IA/Tech/Innovation majeures (peu de ratés).
- **Coût** : sous $50/mo, prévisible, borné par SpendGuard.
- **Confiance** : l'owner override rarement la sélection (le système « pense » comme lui).

---

## 13. Questions ouvertes / prochaines étapes (hors implémentation)
1. Définir la **table des sources + `editorial_tier`** (curation manuelle initiale).
2. Constituer le **baseline éditorial** (échantillon labellisé owner) pour calibrer §4.
3. Décider la **cadence** du job de ranking (batch quotidien + fast-lane breaking ?).
4. Choisir le **modèle d'embeddings** pour la dédup V2 (coût/qualité).
5. Spécifier le **prompt exact** du scoreur LLM (`editorial_scorer_v1.md`) + schéma de sortie.

> Rien de ce document n'est implémenté. Toute construction est conditionnée aux gates GO/NO-GO ci-dessus.
