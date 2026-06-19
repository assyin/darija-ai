# Editorial Shadow Observation Report — Step 6

> **Mode : SHADOW · READ-ONLY · flag `editorial_ranking_shadow_enabled` = OFF (prod inchangée).**
> Le ranker déterministe (Étapes 3-5) a été exécuté **localement** sur un **export lecture-seule** des articles `pending` réels. **Aucune écriture en base** (pas même les colonnes shadow), **aucun changement de `processing_status`**, aucune publication, aucun rejet, aucun LLM, aucune modification du pipeline.
>
> **Preuves obligatoires :**
> - `processing_status` **identique avant/après** : snapshots `pending=322 · processing=1475 · rejected=132 · translated=358` (strictement inchangés).
> - **Aucune écriture prod** (analyse 100 % locale sur export ; la seule écriture *prévue* serait les colonnes shadow, et même celles-ci ne sont **pas** touchées ici).
> - **Aucun appel LLM** (ranker 100 % déterministe).
> - **Aucun code touché** → ruff/format/mypy/tests non requis (réutilisation des modules déjà validés aux Étapes 3-5).
>
> Créé : 2026-06-18. Owner : Yassine (TitritAI). Objectif : mesurer ce que le ranker AURAIT sélectionné, **avant** toute décision d'enforce.

---

## 1. Résumé
- **Total analysé : 322** articles `pending` réels (seuil=55, mode SHADOW, lecture seule).
- **Shadow selected : 44 (13.7%)** · **deferred : 278**.

## 2. Distribution des scores
| bande | count |
|--|--|
| <40 | 207 |
| 40-54 | 71 |
| 55-69 | 41 |
| 70-84 | 3 |
| 85+ | 0 |

## 3. Cadence quotidienne (test ~10-15/jour)
| jour (fetched) | candidats | shadow-selected |
|--|--|--|
| 2026-06-15 | 56 | 2 |
| 2026-06-16 | 128 | 18 |
| 2026-06-17 | 97 | 18 |
| 2026-06-18 | 41 | 6 |

**Moyenne ≈ 11.0 selected/jour sur 4 jours** → dans la cible **10-15** (pics à 18 → le quota /15 les capperait).

## 4. Répartition par source
| source | tier | candidats | selected |
|--|--|--|--|
| TechCrunch AI | A | 34 | 16 |
| Siècle Digital | A | 13 | 7 |
| ZDNet FR | B | 37 | 7 |
| Maddyness | B | 16 | 4 |
| Numerama | C | 38 | 4 |
| ICT Journal | B | 10 | 2 |
| Hugging Face Blog | A | 2 | 1 |
| Journal du Net | C | 48 | 1 |
| Wamda | A | 6 | 1 |
| Datanews FR | C | 5 | 1 |
| Yabiladi | C | 1 | 0 |
| Les Numériques | C | 56 | 0 |
| Financial Afrik | C | 12 | 0 |
| Le Devoir | C | 6 | 0 |
| Le Temps | C | 18 | 0 |
| La Presse Techno | C | 6 | 0 |
| Frenchweb | B | 13 | 0 |
| CIO Mag | B | 1 | 0 |

## 5. Répartition par langue (proxy source)
| langue | candidats | selected | taux |
|--|--|--|--|
| FR | 280 | 26 | 9% |
| EN | 42 | 18 | 43% |

## 6. Répartition par fraîcheur (âge fetched_at)
| âge | candidats | selected |
|--|--|--|
| <6h | 36 | 6 |
| 6-24h | 69 | 12 |
| 24-48h | 101 | 17 |
| >48h | 116 | 9 |

## 7. Top 30 shadow-selected
| id | score | dec | source | imp | rel | mena | src | fresh | titre |
|--|--|--|--|--|--|--|--|--|--|
| 2203 | 72 | selected | Siècle Digital | 35 | 15 | 0 | 15(A) | 7 | French Tech 120 2026 : la nouvelle sélection révèle les futurs |
| 2264 | 72 | selected | Maddyness | 35 | 15 | 0 | 10(B) | 12 | Les mythes de l’IA et de la tech – Debunk #4 : « Plus gros mod |
| 2236 | 71 | selected | TechCrunch AI | 32 | 15 | 0 | 15(A) | 9 | World model maker Odyssey nabs $1.45B valuation backed by Amaz |
| 1992 | 68 | selected | TechCrunch AI | 35 | 18 | 0 | 15(A) | 0 | Sarvam becomes India’s newest AI unicorn with $234 million fun |
| 2198 | 66 | selected | TechCrunch AI | 35 | 9 | 0 | 15(A) | 7 | Canadian pension giant joins race to fund India’s AI-fueled da |
| 2271 | 66 | selected | ZDNet FR | 35 | 9 | 0 | 10(B) | 12 | ZDNET Morning 18/06/2026 : Métro parisien : pourquoi le paieme |
| 2039 | 65 | selected | TechCrunch AI | 35 | 15 | 0 | 15(A) | 0 | Malaysia’s AI agent-powered messaging app Respond.io raises $6 |
| 2151 | 65 | selected | TechCrunch AI | 35 | 12 | 0 | 15(A) | 3 | Anthropic’s latest feud with the Trump admin may actually help |
| 2238 | 65 | selected | TechCrunch AI | 35 | 6 | 0 | 15(A) | 9 | Anthropic becomes first AI startup to join the Frontier carbon |
| 2262 | 65 | selected | ZDNet FR | 28 | 15 | 0 | 10(B) | 12 | ZD Tech : accord historique à 920 millions de dollars... par m |
| 2193 | 63 | selected | TechCrunch AI | 23 | 18 | 0 | 15(A) | 7 | Pinterest launches an experimental AI shopping app called ‘Ask |
| 2202 | 63 | selected | Siècle Digital | 35 | 6 | 0 | 15(A) | 7 | SpaceX rachète Cursor pour 60 milliards de dollars et s’offre  |
| 2217 | 63 | selected | Numerama | 35 | 15 | 0 | 5(C) | 8 | Le timing est cruel : la Chine dévoile GLM-5.2, un modèle grat |
| 2229 | 63 | selected | ZDNet FR | 35 | 12 | 0 | 10(B) | 6 | SpaceX s'empare de Cursor pour 60 milliards de dollars : le jo |
| 2066 | 62 | selected | Siècle Digital | 35 | 12 | 0 | 15(A) | 0 | Ce nouveau moteur de recherche IA sur Facebook pourrait génére |
| 2134 | 61 | selected | Maddyness | 32 | 18 | 0 | 10(B) | 1 | Genesis AI dévoile son premier robot généraliste pour les usin |
| 2174 | 61 | selected | ZDNet FR | 35 | 9 | 0 | 10(B) | 7 | ZDNET Morning 17/06/2026 : IA d'entreprise : Anthropic s'empar |
| 2185 | 61 | selected | ICT Journal | 35 | 9 | 0 | 10(B) | 7 | SpaceX rachète l’assistant de programmation IA Cursor pour 60  |
| 2194 | 61 | selected | TechCrunch AI | 21 | 18 | 0 | 15(A) | 7 | DeepL acquires Mixhalo for live-event audio streaming and tran |
| 2102 | 60 | selected | TechCrunch AI | 35 | 9 | 0 | 15(A) | 1 | SpaceX passes Amazon as valuation balloons to $2.7T |
| 2142 | 60 | selected | Numerama | 35 | 18 | 0 | 5(C) | 2 | De 1 à 14 milliards de commits par an : comment GitHub et l’IA |
| 2272 | 60 | selected | Maddyness | 35 | 3 | 0 | 10(B) | 12 | VivaTech : la French Tech dresse le bilan des 10 ans de Macron |
| 2068 | 59 | selected | Siècle Digital | 35 | 9 | 0 | 15(A) | 0 | Salesforce rachète Intercom, spécialiste du support client par |
| 2145 | 59 | selected | TechCrunch AI | 35 | 6 | 0 | 15(A) | 3 | SpaceX valuation balloons to $2.6T, briefly passes Amazon |
| 2181 | 59 | selected | Hugging Face Blo | 15 | 22 | 0 | 15(A) | 7 | From the Hugging Face Hub to robot hardware with Strands Agent |
| 2286 | 59 | selected | ICT Journal | 23 | 6 | 8 | 10(B) | 12 | Des garde-fous pour les mineurs, un cap pour l’IA: les priorit |
| 2172 | 58 | selected | Numerama | 35 | 12 | 0 | 5(C) | 6 | « On s’est retrouvés sous les projecteurs » : Mistral AI profi |
| 2173 | 58 | selected | Numerama | 35 | 12 | 0 | 5(C) | 6 | Arrêtez d’utiliser ChatGPT : OpenAI mise tout sur Codex |
| 1986 | 57 | selected | TechCrunch AI | 24 | 18 | 0 | 15(A) | 0 | As AI agents become employees, NewCore emerges with $66M to gi |
| 2089 | 57 | selected | ZDNet FR | 35 | 12 | 0 | 10(B) | 0 | ZDNET Morning 16/06/2026 : Telcos et quantique : entre miracle |

## 8. Near-misses (score 50-54)
| id | score | dec | source | imp | rel | mena | src | fresh | titre |
|--|--|--|--|--|--|--|--|--|--|
| 2000 | 54 | deferred | TechCrunch AI | 27 | 12 | 0 | 15(A) | 0 | Salesforce acquires AI customer service platform Fin for $3.6  |
| 2214 | 54 | deferred | Numerama | 23 | 18 | 0 | 5(C) | 8 | Google dévoile l’Open Knowledge Format, sa réponse au casse-tê |
| 2219 | 54 | deferred | ICT Journal | 21 | 15 | 0 | 10(B) | 8 | L’IA pousse lastminute.com à réduire ses effectifs de 25% |
| 2268 | 54 | deferred | ZDNet FR | 32 | 0 | 0 | 10(B) | 12 | SpaceX enregistre sa première baisse en bourse : la frénésie d |
| 2288 | 54 | deferred | Yabiladi | 15 | 6 | 16 | 5(C) | 12 | Les FAR concluent un accord avec un MRE pour la production de  |
| 2195 | 53 | deferred | Wamda | 21 | 9 | 0 | 15(A) | 8 | Pickappo secures $530,000 to expand on-demand delivery infrast |
| 2221 | 52 | deferred | TechCrunch AI | 14 | 15 | 0 | 15(A) | 8 | Collecting robot training data is dirty, unglamorous work. Som |
| 2261 | 52 | deferred | Les Numériques | 26 | 9 | 0 | 5(C) | 12 | Actualité : Votre prochaine voiture pourrait ne plus avoir de  |
| 2119 | 51 | deferred | TechCrunch AI | 32 | 3 | 0 | 15(A) | 1 | SpaceX is public: Everything you need to know post-IPO |
| 2213 | 51 | deferred | Wamda | 15 | 12 | 0 | 15(A) | 9 | WakeCap acquires Frontline as it builds an end-to-end construc |
| 2226 | 51 | deferred | Maddyness | 27 | 6 | 0 | 10(B) | 8 | Green-Got lève 8 millions d’euros en 52 minutes pour bâtir sa  |
| 2282 | 51 | deferred | ZDNet FR | 27 | 3 | 0 | 10(B) | 11 | Les grands groupes flèchent 2Mds€ vers la French Tech |
| 2283 | 51 | deferred | ZDNet FR | 20 | 9 | 0 | 10(B) | 12 | Pénurie de puces : même Apple annonce des hausses de prix |
| 1996 | 50 | deferred | Les Numériques | 23 | 22 | 0 | 5(C) | 0 | Actualité : Windows 11 : Microsoft va enfin mettre à contribut |
| 2017 | 50 | deferred | TechCrunch AI | 32 | 3 | 0 | 15(A) | 0 | SpaceX is public: Everything you need to know post-IPO |

## 9. Exemples faibles (<40)
| id | score | dec | source | imp | rel | mena | src | fresh | titre |
|--|--|--|--|--|--|--|--|--|--|
| 2012 | 39 | deferred | ZDNet FR | 23 | 6 | 0 | 10(B) | 0 | Voici pourquoi Anthropic a soudainement retiré Fable 5 et Myth |
| 2080 | 39 | deferred | Les Numériques | 15 | 3 | 16 | 5(C) | 0 | Actualité : France-Sénégal : comment voir le match de la Coupe |
| 2087 | 39 | deferred | Frenchweb | 23 | 6 | 0 | 10(B) | 0 | SEO et GEO : comment l’IA redéfinit les règles de l’acquisitio |
| 2098 | 39 | deferred | ZDNet FR | 23 | 6 | 0 | 10(B) | 0 | Le sous-système Windows pour Linux offre aux développeurs une  |
| 2117 | 39 | deferred | ZDNet FR | 23 | 6 | 0 | 10(B) | 0 | Android dispose déjà de ces 4 fonctionnalités d'iOS 27, mais j |
| 2225 | 39 | deferred | Hugging Face Blo | 8 | 12 | 0 | 15(A) | 4 | Agentic Resource Discovery: Let agents search |
| 2280 | 39 | deferred | Les Numériques | 19 | 3 | 0 | 5(C) | 12 | Actualité : Netflix annule la série des créateurs de Stranger  |
| 2056 | 38 | deferred | Journal du Net | 24 | 9 | 0 | 5(C) | 0 | France 2030 : Sébastien Lecornu annonce 655 millions d'euros s |
| 2097 | 38 | deferred | Les Numériques | 23 | 9 | 0 | 5(C) | 1 | Actualité : Surface Laptop et Pro : Microsoft renouvelle sa ga |
| 2101 | 38 | deferred | La Presse Techno | 23 | 9 | 0 | 5(C) | 1 | Intelligence artificielle / Après Cohere, Québec s’entend avec |

## 10. Source PREMIUM (A/B) mais score FAIBLE (<55) — 94 cas
| id | score | dec | source | imp | rel | mena | src | fresh | titre |
|--|--|--|--|--|--|--|--|--|--|
| 2000 | 54 | deferred | TechCrunch AI | 27 | 12 | 0 | 15(A) | 0 | Salesforce acquires AI customer service platform Fin for $3.6  |
| 2219 | 54 | deferred | ICT Journal | 21 | 15 | 0 | 10(B) | 8 | L’IA pousse lastminute.com à réduire ses effectifs de 25% |
| 2268 | 54 | deferred | ZDNet FR | 32 | 0 | 0 | 10(B) | 12 | SpaceX enregistre sa première baisse en bourse : la frénésie d |
| 2195 | 53 | deferred | Wamda | 21 | 9 | 0 | 15(A) | 8 | Pickappo secures $530,000 to expand on-demand delivery infrast |
| 2221 | 52 | deferred | TechCrunch AI | 14 | 15 | 0 | 15(A) | 8 | Collecting robot training data is dirty, unglamorous work. Som |
| 2119 | 51 | deferred | TechCrunch AI | 32 | 3 | 0 | 15(A) | 1 | SpaceX is public: Everything you need to know post-IPO |
| 2213 | 51 | deferred | Wamda | 15 | 12 | 0 | 15(A) | 9 | WakeCap acquires Frontline as it builds an end-to-end construc |
| 2226 | 51 | deferred | Maddyness | 27 | 6 | 0 | 10(B) | 8 | Green-Got lève 8 millions d’euros en 52 minutes pour bâtir sa  |
| 2282 | 51 | deferred | ZDNet FR | 27 | 3 | 0 | 10(B) | 11 | Les grands groupes flèchent 2Mds€ vers la French Tech |
| 2283 | 51 | deferred | ZDNet FR | 20 | 9 | 0 | 10(B) | 12 | Pénurie de puces : même Apple annonce des hausses de prix |
| 2017 | 50 | deferred | TechCrunch AI | 32 | 3 | 0 | 15(A) | 0 | SpaceX is public: Everything you need to know post-IPO |
| 2042 | 50 | deferred | Wamda | 21 | 6 | 8 | 15(A) | 0 | Sovra lands $2 million+ pre-seed led by Pharsalus Capital |

## 11. Source FAIBLE (C) mais article IMPORTANT (≥55) — 6 cas
| id | score | dec | source | imp | rel | mena | src | fresh | titre |
|--|--|--|--|--|--|--|--|--|--|
| 2217 | 63 | selected | Numerama | 35 | 15 | 0 | 5(C) | 8 | Le timing est cruel : la Chine dévoile GLM-5.2, un modèle grat |
| 2142 | 60 | selected | Numerama | 35 | 18 | 0 | 5(C) | 2 | De 1 à 14 milliards de commits par an : comment GitHub et l’IA |
| 2172 | 58 | selected | Numerama | 35 | 12 | 0 | 5(C) | 6 | « On s’est retrouvés sous les projecteurs » : Mistral AI profi |
| 2173 | 58 | selected | Numerama | 35 | 12 | 0 | 5(C) | 6 | Arrêtez d’utiliser ChatGPT : OpenAI mise tout sur Codex |
| 2073 | 55 | selected | Journal du Net | 35 | 15 | 0 | 5(C) | 0 | IA en entreprise : ce n'est pas l'outil qui manque, c'est le b |
| 2285 | 55 | selected | Datanews FR | 35 | 3 | 0 | 5(C) | 12 | Anthropic, première entreprise d’IA à rejoindre la coalition c |

---

## 12. Comparaison shadow vs pipeline actuel
- **Pipeline actuel** : `process_pending` prend **TOUS** les pending → localiserait les **322** (≈ $15-20 Claude, ~79 % rejetés au stade modèle).
- **Shadow (seuil 55, sans quota)** : sélectionnerait **44** (13.7 %) ; avec le **quota /15-jour + /3-source**, ≈ **11-15/jour**.
- → Le ranker **couperait ~86 %** de la localisation tout en gardant les articles premium. Gain coût + qualité majeur, cohérent avec l'objectif. *(Comparaison faite sans modifier le pipeline.)*

## 13. Problèmes de calibration identifiés (NON corrigés)
1. **🔴 Biais EN > FR/MENA.** EN sélectionne à **43 %** (18/42) vs FR **9 %** (26/280). Le top est dominé par **TechCrunch (16/44)** = actu IA mondiale traduite. **Le différenciateur Maroc/Afrique/MENA ne ressort quasi PAS** (mena=0 sur presque tout le Top 30). → Risque : DarijaAI publierait surtout du global-AI traduit, pas son angle régional.
2. **🟡 Articles vieux sélectionnés.** `>48h` : 9 selected (fresh=0) — des articles importants de 2-5 jours passent quand même (importance+source+relevance ≥ 55 sans fraîcheur). Risque de **staleness** pour un média « actu ».
3. **🟡 94 articles premium (A/B) sous 55.** Beaucoup de bonnes sources sont deferred (faible importance/relevance déterministe). Comportement voulu (importance domine la source), mais certains sont des **analyses/interviews/dossiers** de valeur que le déterministe ne « voit » pas (pas de mot-clé événement/magnitude).
4. **🟡 Concentration TechCrunch (36 % des selected).** Le quota /3-source/jour le capperait, mais signale une dépendance forte.
5. **🟢 6 articles tier-C importants élevés** (GLM-5.2, GitHub 14B commits, Mistral, OpenAI Codex…) — **le design fonctionne** : des articles importants de sources faibles (Numerama C) sont correctement remontés.

## 14. Le seuil 55 donne-t-il ~10-15/jour ?
**✅ Oui.** Moyenne **11/jour** sur 4 jours (06-15:2 · 06-16:18 · 06-17:18 · 06-18:6 partiel). Avec le quota /15, les pics à 18 seraient cappés → **10-15 premium/jour**. **Le seuil 55 est bien calibré pour le volume** (ne pas l'optimiser maintenant, comme demandé).

## 15. Verdict

**Le ranker est-il assez propre pour envisager un enforce plus tard ?**
→ **OUI, conditionnellement.** Sur le **volume** (~11-15/jour) et la **séparation premium/bruit** (207 sous 40 ; Top 30 = vrais articles IA/levées/M&A majeurs), le déterministe est **étonnamment correct** et **prêt pour un enforce prudent** — **mais pas avant d'avoir tranché la calibration MENA (#1)**, qui touche au cœur du positionnement.

**Risques restants :**
- **Biais EN/global au détriment du différenciateur MENA/FR** (le plus important).
- **Staleness** (articles vieux sélectionnés).
- **Valeur éditoriale invisible** au déterministe (essais/dossiers premium deferred).
- **Dépendance TechCrunch**.

**Données qui manquent pour décider :**
- Un **baseline éditorial humain** : toi notant ~30-50 de ces selected/deferred (publish/defer) → pour mesurer le **vrai** taux de faux positifs/négatifs (pas juste « ça a l'air bien »).
- L'effet du **quota /source + /jour** appliqué (le shadow ici est seuil-seul, sans quota).
- Une comparaison sur **plusieurs jours pleins** (06-18 est partiel).

**Recommandation :** rester en SHADOW · constituer le baseline humain sur ce rapport · trancher la pondération MENA · **puis** envisager un enforce prudent (quota d'abord, seuil ensuite). **Aucun enforce maintenant.**

---

> Rapport d'observation SHADOW — aucune sélection réelle, aucun quota réel, aucun rejet réel, aucune écriture prod. Reste SHADOW jusqu'à décision explicite.
