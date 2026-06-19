# Editorial Ranking Engine — MVP v1 (STRICTEMENT DÉTERMINISTE)

> **Statut : SPÉC DE DÉCISION — non implémenté.** Aucun code, aucune PR, aucune migration, aucune modif prod.
> Companion de `docs/EDITORIAL_RANKING_ENGINE.md` (vision complète). Ce document = le **premier incrément**, volontairement minimal.
> Créé : 2026-06-16 · **Rév. v1.1** : importance dominante (35) / source abaissée (15) ; ajout du **rapport éditorial quotidien** (§8b). Owner : Yassine (TitritAI).

## Décisions verrouillées (cadre de ce MVP)
- Objectif : **10-15 articles premium/jour max** (qualité > volume).
- **Classer AVANT de localiser** (validé) — n'investir la localisation que sur les sélectionnés.
- **ZÉRO LLM dans ce MVP.** Signaux 100 % déterministes. On mesure d'abord ce que le déterministe apporte ; le scoreur LLM est une décision **ultérieure**, conditionnée aux données.
- **Catégories > auteurs** (chantier SEO séparé, hors de cette spec).
- **Simple, mesurable, réversible.** Minimum de changements, maximum d'observabilité.

---

## 1. Principes directeurs
1. **Déterministe** : score reproductible à partir de métadonnées + mots-clés. Aucun appel modèle.
2. **Réversible** : derrière **feature flags** ; rollback instantané = on/off, sans migration destructive.
3. **Mesurable d'abord (Shadow)** : on calcule scores + décisions **sans changer le comportement prod** pendant les premiers jours, puis on active le gating.
4. **Additif** : on **insère** une étape ; on ne réécrit ni le pré-filtre V8, ni le SpendGuard, ni le retry-fix, ni le Localizer/Proofreader.

---

## 2. Architecture minimale

```
RSS → Pré-filtre V8 → raw_articles 'pending' (editorial_decision='unranked')
        │
        ▼  [NOUVEAU] job rank_pending (cron périodique)
   score déterministe /100  +  quotas  →  editorial_decision = 'selected' | 'deferred'
        │
        ▼
   process_pending :  si ENFORCE → WHERE editorial_decision='selected'
                      sinon       → comportement actuel (tous les 'pending')   ← rollback
        │
        ▼
   Localizer + FrenchLocalizer + Proofreader   [INCHANGÉ]  → draft (revue humaine)
```

Trois briques seulement : **un job de scoring**, **deux flags**, **un filtre conditionnel** dans `process_pending`.

---

## 3. Signaux déterministes & score /100  *(révisé — importance dominante)*

> **Décision de rééquilibrage** : l'**importance de l'actualité est le signal DOMINANT (35)** ; la **qualité de source est abaissée (25 → 15)**. Objectif : qu'un article **important d'une source moyenne batte** un article banal d'une grande source. Source = signal de *support*, pas de *décision*.

| Signal | Plage | Calcul (100 % déterministe) |
|---|---:|---|
| **Importance de l'actualité** *(DOMINANT)* | **0-35** | Composite déterministe : **(a) Type d'événement 0-15** (lancement/release, M&A/rachat, levée, régulation/loi, percée/recherche, partenariat — le type le plus fort prime) · **(b) Magnitude business 0-12** (plus gros montant extrait : `milliards`→12, centaines de M→9, dizaines→6, M→3) · **(c) Acteurs majeurs 0-8** (labo frontière OpenAI/Anthropic/DeepMind/Meta/Microsoft/Nvidia = 8 ; autre big-tech = 5) |
| **Pertinence IA/Tech** | 0-22 | Densité de hits du **lexique V8** (titre+corps), normalisée |
| **Impact MENA** | 0-16 | Entités/géo MENA (Maroc, Afrique, CEDEAO, UEMOA, Yassir, InstaDeep, Casablanca…) |
| **Source quality** | **0-15** | `sources.name` → tier en **config** (A=15, B=10, C=5, inconnu=4). Pas de colonne DB. |
| **Fraîcheur** | 0-12 | f(`published_at`) : max si < 6 h, décroissance linéaire → 0 à 48 h (fallback `fetched_at`) |
| **TOTAL** | **/100** | |

**Pourquoi ce rééquilibrage règle ta préoccupation** : importance (35) > 2× source (15). Ex. — un article *important* (30/35) d'une source C (5/15) bat un article *banal* (8/35) d'une source A (15/15) : l'avantage d'importance (+22) écrase l'avantage de source (+10). La source ne peut plus « sauver » un article sans intérêt.

- `score = Σ sous-scores`. **Poids = points de départ, tunables en config** ; calibrés sur les données réelles du Shadow.
- Sous-scores **persistés** (`score_breakdown` JSONB) → le rapport éditorial (§8b) les exploite.
- Lexiques (tech, Big Tech, business, MENA, types d'événement, magnitude) = **regex/mots-clés**, en grande partie déjà présents dans le pré-filtre V8 → réutilisation.

> **Limite honnête** : sans LLM, « importance » reste un **proxy** (type d'événement + magnitude + acteurs). C'est plus riche et plus juste que le tier de source seul, mais le **recall des majeures** (§8 / §11) reste LA métrique qui dira si ce proxy suffit.
> **Levier déterministe optionnel** (activable pendant le Shadow si l'importance semble faible, sinon laissé OFF pour la simplicité) : **corroboration multi-source** — si le même sujet apparaît dans N sources du pool (match titre/entité, sans LLM), bonus d'importance. C'est le meilleur proxy déterministe d'importance et il **réduit encore** la dépendance à la source. Hors MVP de base, mesurable en option.

---

## 4. Quotas & seuil (config)

| Paramètre | Valeur initiale | Rôle |
|---|---|---|
| `max_articles_per_day` | **15** | Plafond dur de volume |
| `max_per_source_per_day` | **3** | Anti-monoculture |
| `max_per_category_per_day` | **désactivé au MVP** | (dépend d'une taxonomie normalisée — reporté) |
| `min_score_threshold` | **55** (à calibrer) | Barre de qualité minimale |

**Règle de sélection** (greedy, ordonnée par score décroissant) :
> `selected` SI `score ≥ min_score_threshold` ET quota jour < 15 ET quota source < 3 ; sinon `deferred`.

→ Publie **entre 0 et 15/jour**, **uniquement** au-dessus de la barre. **On ne remplit pas 15 slots avec du médiocre** (qualité > quota).

---

## 5. Modifications minimales (base + config + flags)

### Base — 1 seule migration additive (réversible)
`raw_articles` :
- `editorial_score` SMALLINT NULL
- `editorial_decision` VARCHAR(12) NOT NULL DEFAULT `'unranked'` + CHECK ∈ {`unranked`,`selected`,`deferred`}
- `score_breakdown` JSONB NULL

> **Découplé** de `processing_status` (cycle de localisation) → zéro conflit avec l'existant. Colonnes nullable/défaut → downgrade trivial.
> **Pas** de colonne sur `sources` : le tier vit en **config** (plus réversible).

### Config (`core/config.py`) — aucune migration
- Map `SOURCE_TIERS` (name → A/B/C)
- Poids des signaux, `min_score_threshold`, quotas
- **2 flags** :
  - `EDITORIAL_RANKING_ENABLED` (calcule scores + décisions = **Shadow**)
  - `EDITORIAL_RANKING_ENFORCE` (process_pending filtre sur `selected` = **gating**)

### Code (pour mémoire — non implémenté ici)
- `services/editorial/deterministic_ranker.py` : scorer + sélecteur (fonctions pures, testables)
- `workers/jobs/rank_pending.py` : cron (toutes les 2 h)
- `process_pending` : **1 ligne** conditionnelle au flag ENFORCE
- (optionnel) requête admin pour la **revue quotidienne** des selected/deferred

---

## 6. Workflow complet (cycle quotidien)

1. **Ingestion** (inchangée) : RSS → V8 → `pending` (`editorial_decision='unranked'`).
2. **Ranking** (`rank_pending`, toutes les 2 h) :
   - charge les `pending` `unranked` ;
   - calcule le score /100 + `score_breakdown` ;
   - lit l'état des quotas du jour (selected par total/source) ;
   - marque `selected` (greedy, score≥seuil, quotas OK) / `deferred` ;
   - persiste `editorial_score`, `editorial_decision`, `score_breakdown`.
3. **Localisation** : `process_pending`
   - **ENFORCE off** (Shadow) → tous les `pending` comme aujourd'hui (aucun changement) ;
   - **ENFORCE on** → seulement `editorial_decision='selected'`.
4. **Reste inchangé** : Localizer + FrenchLocalizer + Proofreader → draft `is_published=False` (revue humaine). SpendGuard reste le backstop.

---

## 7. Mode SHADOW (clé de la réversibilité & de la mesure)
**Phase A** = `ENABLED=on`, `ENFORCE=off`. Le ranker **calcule et stocke** scores + décisions, mais **process_pending ignore ces décisions** → **comportement prod identique à aujourd'hui, zéro risque**. On peut ainsi **mesurer ce que le ranker AURAIT sélectionné** avant de lui donner le contrôle.

**Phase B** = `ENFORCE=on` → le ranker pilote réellement la localisation.

**Rollback** = `ENFORCE=off` (retour instantané au comportement actuel ; scores continuent d'être calculés, inoffensifs) ou `ENABLED=off` (stop total).

---

## 8. Métriques de succès (observables)

| Métrique | Cible / lecture |
|---|---|
| **Volume sélectionné/jour** | ≤ 15 ; mesurer la valeur réelle |
| **Taux de sélection** | selected / pending (doit chuter fortement vs ~tout aujourd'hui) |
| **Distribution des scores** | selected vs deferred (séparation nette attendue) |
| **Coût Claude/jour** | doit **baisser** (localiser ~12-15, pas ~85) |
| **Recall des majeures** *(clé qualité)* | # actualités IA majeures **ratées** vs spot-check humain quotidien |
| **Diversité** | répartition par source/catégorie des sélectionnés |
| **Taux d'override** *(si revue humaine)* | % de désaccord owner vs sélection |
| **Réversibilité** | `ENFORCE=off` restaure le comportement actuel (vérifié) |

---

## 8b. Rapport éditorial quotidien *(ajouté au MVP)*

> But : juger la **qualité éditoriale réelle** de la sélection — pas seulement les métriques techniques. Après 7 jours, l'owner doit pouvoir dire « le système choisit bien » avec des **exemples concrets**, pas des moyennes.

**Nature** : rapport **déterministe, en lecture seule**, généré 1×/jour (fin de journée UTC). Source = `raw_articles` (`editorial_score`, `editorial_decision`, `score_breakdown`, `source_id`, `categories`, `published_at`) + `ai_logs` (coût). **Aucune donnée nouvelle** au-delà des 3 colonnes du MVP.

### Contenu (sections)

1. **En-tête / résumé du jour**
   - date · mode (Shadow / Enforce) · # candidats rankés · # `selected` · # `deferred`
   - volume vs quota (**X / 15**) · coût Claude du jour · # localisés réellement

2. **Top Selected** (les sélectionnés, triés par score ↓)
   - rang · **titre** · **source** · **score /100** · breakdown (import./pertin./MENA/source/frais.) · catégorie · âge (h)
   - → « voici ce que le système a jugé digne de publication »

3. **Top Deferred — « near misses »** (les `deferred` au score le plus élevé)
   - titre · source · score · breakdown · **RAISON du defer** : `sous_seuil` / `quota_jour_plein` / `quota_source_plein`
   - → **section la plus importante pour juger les FAUX NÉGATIFS** : « a-t-on écarté quelque chose qu'on aurait dû publier ? »

4. **Distribution des scores** (toutes les candidatures du jour)
   - bandes : `<40` / `40-54` / `55-69` / `70-84` / `85+` × (count selected / count deferred)
   - → la séparation selected/deferred est-elle **nette** ? (sinon le scoring ne discrimine pas)

5. **Répartition par source**
   - par source : # candidats · # selected · (cap source mordu ?)
   - → une source **domine-t-elle** la sélection ? le cap 3/source agit-il ?

6. **Bornes de la frontière de sélection**
   - **plus haute note sélectionnée** · **plus basse note sélectionnée** (= la barre effective du jour) · **plus haute note deferred** (= le meilleur raté)
   - 🔑 **Signal-clé : écart « plus basse selected » vs « plus haute deferred »** — si un `deferred` score **plus haut** qu'un `selected`, c'est qu'un **quota** (source/jour) a écarté un meilleur article → cas à examiner manuellement (faux négatif potentiel).

7. **(Shadow uniquement) Vue comparative ranker vs production réelle**
   - ce que le ranker **aurait** sélectionné (≤15) vs ce qui a été **réellement** localisé (tous les pending aujourd'hui)
   - overlap, divergences → mesure l'impact AVANT la bascule, sans aucun risque.

8. **Alertes éditoriales automatiques** (heuristiques déterministes)
   - ⚠️ une source > 50 % des selected (monoculture)
   - ⚠️ plus haute deferred > plus basse selected de +X pts (quota a écarté un meilleur article)
   - ⚠️ 0 contenu MENA aujourd'hui (cible audience non servie)
   - ⚠️ volume < 5 (barre trop haute ?) ou = 15 plafonné plusieurs jours (barre trop basse ?)

### Livraison (choisir le plus simple — décision séparée)
- **(a) Rapport généré (Markdown/fichier ou log structuré)** — zéro UI, le plus simple. **Recommandé pour le MVP.**
- (b) Page admin dédiée — plus tard.
- (c) Digest email quotidien (connecteur Gmail / SMTP) — si tu préfères le push.

### Pourquoi c'est central
C'est le rapport qui transforme le Shadow en **expérience décisionnelle** : à J7, le GO/NO-GO (§11) se juge sur des **exemples réels** (top selected/deferred, near-misses, frontière) — pas seulement sur « le volume a baissé ».

---

## 9. Risques & mitigations

| Risque | Mitigation MVP |
|---|---|
| Le déterministe est un **proxy d'importance** (pas le vrai signal) → rate du « réellement important d'une source moyenne » | **Recall spot-check humain quotidien** = la métrique qui décide si un LLM devient nécessaire |
| **Early-bird bias** : un meilleur article arrivé tard est `deferred` (quota plein) | Mesurer la fréquence ; possible « réserve » de slots en V2 (hors MVP) |
| Poids/seuil non calibrés | Phase Shadow + 7 jours de données → calibrer avant/pendant enforce |
| Catégories incohérentes (générées par le modèle) | **Quota catégorie désactivé au MVP** (réactivé après normalisation taxonomie) |
| Sur-restriction (publie trop peu) | `min_score_threshold` tunable en config (sans migration) |

---

## 10. Plan de validation sur 7 jours

| Jour | Phase | Action | Sortie |
|---|---|---|---|
| **J0** | Setup | Déploiement avec `ENABLED=on`, `ENFORCE=off` (**Shadow**) | Ranker calcule/stocke, prod inchangée |
| **J1-J3** | **Shadow** | Chaque jour : comparer la liste `selected` du ranker vs ce qui a été réellement localisé ; owner spot-check « aurais-je publié ça ? » + repérer les **majeures ratées** | Tableau quotidien : volume, distribution scores, recall, diversité |
| **J3** | Revue | Calibrer poids/seuil sur les données Shadow | Config ajustée |
| **J4** | **Bascule** | `ENFORCE=on` → le ranker pilote la localisation | Volume réel borné, coût en baisse |
| **J4-J7** | **Enforce** | Suivi quotidien : volume ≤15, coût, recall, override, stabilité (SpendGuard/retry inchangés) | Rapport quotidien |
| **J7** | **GO/NO-GO** | Décision (cf. §11) | Conserver / ajuster / conclure « LLM requis » |

---

## 11. Critères GO / NO-GO (à J7)

**GO (conserver le MVP déterministe)** si :
- volume publié **stabilisé ≤ 15/jour** sans franchissement ;
- **recall** : ≤ 1 actualité IA majeure ratée / semaine (spot-check) ;
- **coût Claude en baisse** nette, SpendGuard non déclenché par le flux normal ;
- **0 régression** (V8 / SpendGuard / retry / localisation) ;
- override humain de la sélection **< 30 %**.

**NO-GO / réviser** si :
- recall faible (majeures ratées) OU override > 50 % → **signal que le déterministe ne suffit pas** → rouvrir la décision « scoreur LLM minimal » (la prochaine itération possible) ;
- distribution des scores non discriminante (tout au même niveau) → revoir signaux/poids.

> Ce MVP est précisément **l'expérience qui tranche** la question « le déterministe suffit-il, ou faut-il un LLM ? » — avec des données réelles, pas une opinion.

---

## 12. Explicitement HORS scope (anti-complexité prématurée)
- ❌ Aucun LLM (ni scoreur, ni embeddings).
- ❌ Pas de dédup par embeddings (dédup heuristique = V2).
- ❌ Pas de fast-lane breaking (V2).
- ❌ Pas de boucle d'apprentissage (V3).
- ❌ Pas de quota par catégorie (attend la normalisation de taxonomie).
- ❌ Aucune récupération du backlog historique gelé.
- ❌ Aucune modification du pré-filtre V8, SpendGuard, retry-fix, Localizer, Proofreader.

> Rien de ce document n'est implémenté. Construction conditionnée à ta validation explicite.

---

# Annexe A — Table de référence stratégique des sources (v2, 3 axes) — **GELÉE 2026-06-16**

> Référence pour le signal **Source quality** du MVP (config `SOURCE_TIERS`) + état opérationnel.
> **3 axes décorrélés** : *Editorial Tier* (qualité intrinsèque) ≠ *Flux Status* (santé RSS) ≠ *Pipeline Fit* (compatibilité V8, `produced/raw`).
> ⚠️ **Aucune désactivation, aucune réparation de flux, aucune action prod.** Référence stratégique uniquement.

## A.1 — Top 10 stratégiques (validé)
*Positionnement : média IA **francophone** orienté **Maroc / Afrique / MENA** — pas « les meilleures en général ».*

| # | Source | Rôle stratégique | Flux |
|---|---|---|---|
| 1 | **Wamda** | LE média tech/startups MENA — différenciateur irremplaçable | ✅ |
| 2 | **TechCrunch AI** | Colonne vertébrale actu IA mondiale | ✅ |
| 3 | **Anthropic News** | Source primaire labo frontière + halo Claude | 🔧 cassé |
| 4 | **Médias24** | Réf. business/économie numérique Maroc | 🔧 cassé |
| 5 | **Hugging Face Blog** | Autorité ML/IA, source primaire | ✅ |
| 6 | **Menabytes** | Tech/startups MENA (2e pilier) | ✅ |
| 7 | **CIO Mag** | Numérique/IT Afrique | ✅ |
| 8 | **Jeune Afrique** | Autorité panafricaine + halo marque | 🔧 cassé |
| 9 | **Siècle Digital** | Meilleur quotidien tech francophone | ✅ |
| 10 | **Frenchweb** | Startups/levées francophones (business-IA) | ✅ |

## A.2 — Quatre catégories d'action

### 🟢 STRATÉGIQUES — garder (cœur du dispositif)
| Source | Editorial | Flux | Fit |
|---|---|---|---|
| Wamda | A | Healthy | High |
| TechCrunch AI | A | Healthy | High |
| Hugging Face Blog | A | Healthy | High |
| Menabytes | A | Healthy | High |
| Siècle Digital | A | Healthy | High |
| CIO Mag | B | Healthy | High |
| Frenchweb | B | Healthy | Medium |
| Maddyness | B | Healthy | Medium |
| ICT Journal | B | Healthy | High |

### 🔧 À RÉPARER — valeur éditoriale haute, flux cassé/dégradé (NE PAS désactiver)
| Source | Editorial | Flux | Priorité |
|---|---|---|---|
| **Anthropic News** | A | Broken | **P1** (Top 10 #3) |
| **Médias24** | B | Broken | **P1** (Top 10 #4) |
| **Jeune Afrique** | B | Broken | **P2** (Top 10 #8) |
| VentureBeat AI | A | Degraded (raw=7) | P2 (vérifier flux) |
| Unite.AI | B | Broken | P3 |
| Les Affaires | B | Broken | P3 (sinon désactiver) |

### 👁 À SURVEILLER — fit faible ou signal régional (probation)
| Source | Editorial | Flux | Fit | Raison de maintien |
|---|---|---|---|---|
| ZDNet FR | B | Healthy | Medium | Tech FR mixte |
| Numerama | C | Healthy | Low (11%) | Tech FR très bruyant |
| Journal du Net | B | Healthy | Medium (19%) | Business/tech bruyant |
| Maroc.ma | C | Healthy | Low | **Signal Maroc** officiel |
| Yabiladi | C | Healthy | Low | **Signal Maroc** |
| Bladi | C | Healthy | Low | **Signal Maroc** |
| Financial Afrik | C | Healthy | Low | **Signal Afrique** (cause de faux positifs) |
| TelQuel | C | Broken | — | Maroc — réparer seulement si angle tech |
| Les Numériques | C | Healthy | Low (12%) | Bruit shopping, **aucun signal régional** |
| La Presse Techno | C | Healthy | Medium | Québec, hors positionnement |
| Datanews FR | C | Healthy | Low (3%) | Belgique, bas rendement |

### 🔴 CANDIDATES À DÉSACTIVATION — généralistes sans valeur stratégique
| Source | Editorial | Flux | Fit | Justification |
|---|---|---|---|---|
| Le Temps | C | Healthy | Low (4.5%) | Généraliste CH, gros volume / yield nul |
| Le Devoir | C | Healthy | Low (1.4%) | Généraliste Québec |
| Radio-Canada Techno | C | Healthy | Low (1.5%) | Mal étiqueté, produit du sport |
| Asharq Al-Awsat EN | C | Healthy | Low (5%) | Actu arabe générale/politique |
| La Libre | C | Degraded (raw=3) | Low (0%) | Généraliste belge |
| Afrik.com | C | Broken | — | Généraliste Afrique + flux cassé |

## A.3 — Config `SOURCE_TIERS` (référence machine — non implémentée)
> Mapping `nom → tier` pour le signal source (A=15 / B=10 / C=5 / inconnu=4 pts). Les statuts flux/fit sont **opérationnels**, pas dans le score.

- **Tier A** : TechCrunch AI · Anthropic News · Hugging Face Blog · Wamda · Siècle Digital · VentureBeat AI · Menabytes
- **Tier B** : Médias24 · Jeune Afrique · CIO Mag · Maddyness · Frenchweb · ICT Journal · ZDNet FR · Unite.AI · Les Affaires
- **Tier C** : Maroc.ma · TelQuel · Yabiladi · Bladi · Financial Afrik · Afrik.com · Numerama · Journal du Net · Les Numériques · La Presse Techno · Datanews FR · Le Temps · Le Devoir · Radio-Canada Techno · Asharq Al-Awsat EN · La Libre

## A.4 — Insight de la décorrélation
> **3 des 10 sources les plus stratégiques (Anthropic, Médias24, Jeune Afrique) ont un flux CASSÉ.** L'ancienne méthode (ratio seul) les rétrogradait à tort. **Réparer ces 3 flux = la plus grosse victoire stratégique immédiate** — mais **différée**, hors scope actuel (aucune action prod).

> Cette annexe est une **référence gelée**. Aucune désactivation, aucune réparation, aucun code — uniquement la base de décision pour le futur signal Source du MVP et les priorités opérationnelles à venir.
