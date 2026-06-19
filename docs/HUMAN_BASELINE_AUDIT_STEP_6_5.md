# Human Baseline Audit — Step 6.5

> **Mode : READ-ONLY · aucune écriture DB · aucun changement de statut · aucun quota · aucun enforce · aucun LLM · aucun changement de code · aucun recalcul du ranker** (scores déterministes **identiques** à l'Étape 6, ré-extraits via le ranker inchangé — pas de recalibration).
>
> **Preuves :** `processing_status` **identique avant/après** : `pending=325 · processing=1475 · rejected=132 · translated=358`. Analyse 100 % **locale** sur export lecture-seule.
>
> **But :** mesurer la qualité RÉELLE du ranker contre le jugement humain. Échantillon : **25 shadow-selected + 25 deferred** (orienté frontière) + **audit MENA (23 articles)**.
>
> **Statut :** ✅ **COMPLÉTÉ** — colonnes `HUMAN_DECISION` remplies avec les décisions éditoriales du propriétaire (règle KEEP/REJECT documentée §6). Métriques calculées §3. Verdict humain §5.

---

## 1. Échantillon SHADOW-SELECTED (25) — jugé : KEEP si bon choix de publication, REJECT sinon
| id | shadow | score | imp(e/m/a) | rel | mena | src(tier) | fresh | source | titre (lien) | HUMAN_DECISION | HUMAN_COMMENT |
|--|--|--|--|--|--|--|--|--|--|--|--|
| 2203 | selected | 72 | 35(15/12/8) | 15 | 0 | 15(A) | 7 | Siècle Digital | [French Tech 120 2026 : la nouvelle sélection révèle les](https://siecledigital.fr/2026/06/17/french-tech-120-2026-la-nouvelle-selection-revele-les-futurs-geants-francais-de-la-tech) | **KEEP** | Écosystème startups FR, pertinent francophonie |
| 2264 | selected | 72 | 35(15/12/8) | 15 | 0 | 10(B) | 12 | Maddyness | [Les mythes de l’IA et de la tech – Debunk #4 : « Plus g](https://www.maddyness.com/2026/06/18/les-mythes-de-lia-et-de-la-tech-debunk-4-plus-gros-modele-meilleurs-resultats) | **KEEP** | Analyse IA, bon angle éditorial |
| 1992 | selected | 68 | 35(15/12/8) | 18 | 0 | 15(A) | 0 | TechCrunch AI | [Sarvam becomes India’s newest AI unicorn with $234 mill](https://techcrunch.com/2026/06/15/sarvam-becomes-indias-newest-ai-unicorn-with-234-million-funding-round-led-by-hcltech) | **KEEP** | Levée IA majeure (unicorn) |
| 2271 | selected | 66 | 35(15/12/8) | 9 | 0 | 10(B) | 12 | ZDNet FR | [ZDNET Morning 18/06/2026 : Métro parisien : pourquoi le](https://www.zdnet.fr/actualites/zdnet-morning-18-06-2026-metro-parisien-pourquoi-le-paiement-par-cb-sera-plus-cher-lordinateur-quantique-commercial-dici-5-ans-premier-repli-boursier-pour-spacex-497186.htm) | **REJECT** | Digest « Morning », sujets mélangés |
| 2151 | selected | 65 | 35(15/12/8) | 12 | 0 | 15(A) | 3 | TechCrunch AI | [Anthropic’s latest feud with the Trump admin may actual](https://techcrunch.com/2026/06/16/anthropics-latest-feud-with-the-trump-admin-may-actually-help-it-sales-data-suggests) | **KEEP** | Anthropic, business/régulation IA |
| 2262 | selected | 65 | 28(8/12/8) | 15 | 0 | 10(B) | 12 | ZDNet FR | [ZD Tech : accord historique à 920 millions de dollars..](https://www.zdnet.fr/actualites/zd-tech-accord-historique-a-920-millions-de-dollars-par-mois-entre-google-et-spacex-497075.htm) | **KEEP** | Accord Big Tech majeur (Google) |
| 2193 | selected | 63 | 23(15/0/8) | 18 | 0 | 15(A) | 7 | TechCrunch AI | [Pinterest launches an experimental AI shopping app call](https://techcrunch.com/2026/06/17/pinterest-launches-an-experimental-ai-shopping-app-called-ask-pinterest) | **REJECT** | Shopping/consumer, faible valeur |
| 2217 | selected | 63 | 35(15/12/8) | 15 | 0 | 5(C) | 8 | Numerama | [Le timing est cruel : la Chine dévoile GLM-5.2, un modè](https://www.numerama.com/tech/2278511-le-timing-est-cruel-la-chine-devoile-glm-5-2-un-modele-gratuit-qui-rivalise-avec-claude-opus-4-8-et-gpt-5-5.html) | **KEEP** | Modèle IA frontier (concurrence Claude/GPT) |
| 2066 | selected | 62 | 35(15/12/8) | 12 | 0 | 15(A) | 0 | Siècle Digital | [Ce nouveau moteur de recherche IA sur Facebook pourrait](https://siecledigital.fr/2026/06/16/ce-nouveau-moteur-de-recherche-ia-sur-facebook-pourrait-generer-10-milliards-de-dollars-par-an) | **REJECT** | Consumer/gros chiffre, faible valeur stratégique |
| 2134 | selected | 61 | 32(15/9/8) | 18 | 0 | 10(B) | 1 | Maddyness | [Genesis AI dévoile son premier robot généraliste pour l](https://www.maddyness.com/2026/06/16/genesis-ai-devoile-son-premier-robot-generaliste-pour-les-usines-et-les-hopitaux) | **KEEP** | Robotique IA, innovation |
| 2185 | selected | 61 | 35(15/12/8) | 9 | 0 | 10(B) | 7 | ICT Journal | [SpaceX rachète l’assistant de programmation IA Cursor p](https://www.ictjournal.ch/news/2026-06-17/spacex-rachete-lassistant-de-programmation-ia-cursor-pour-60-milliards) | **KEEP** | Acquisition IA majeure (Cursor) — version canonique |
| 2102 | selected | 60 | 35(15/12/8) | 9 | 0 | 15(A) | 1 | TechCrunch AI | [SpaceX passes Amazon as valuation balloons to $2.7T](https://techcrunch.com/2026/06/16/spacex-passes-amazon-as-valuation-balloons-to-2-7t) | **REJECT** | Doublon SpaceX valorisation |
| 2272 | selected | 60 | 35(15/12/8) | 3 | 0 | 10(B) | 12 | Maddyness | [VivaTech : la French Tech dresse le bilan des 10 ans de](https://www.maddyness.com/2026/06/18/vivatech-la-french-tech-dresse-le-bilan-des-10-ans-de-macron-a-lelysee) | **REJECT** | Trop politique, faible IA |
| 2181 | selected | 59 | 15(15/0/0) | 22 | 0 | 15(A) | 7 | Hugging Face B | [From the Hugging Face Hub to robot hardware with Strand](https://huggingface.co/blog/amazon/strands-lerobot-hub-to-hardware) | **REJECT** | Trop technique/niche pour slot premium |
| 2145 | selected | 59 | 35(15/12/8) | 6 | 0 | 15(A) | 3 | TechCrunch AI | [SpaceX valuation balloons to $2.6T, briefly passes Amaz](https://techcrunch.com/2026/06/16/spacex-valuation-balloons-to-2-6t-briefly-passes-amazon) | **REJECT** | Doublon SpaceX valorisation |
| 2172 | selected | 58 | 35(15/12/8) | 12 | 0 | 5(C) | 6 | Numerama | [« On s’est retrouvés sous les projecteurs » : Mistral A](https://www.numerama.com/tech/2277867-on-sest-retrouves-sous-les-projecteurs-mistral-ai-profite-de-lattention-pour-devoiler-ses-cartes-et-un-nouveau-modele-des-cet-ete.html) | **KEEP** | Mistral, IA souveraine européenne |
| 1986 | selected | 57 | 24(15/9/0) | 18 | 0 | 15(A) | 0 | TechCrunch AI | [As AI agents become employees, NewCore emerges with $66](https://techcrunch.com/2026/06/15/ai-agents-are-becoming-employees-newcore-emerges-with-66m-to-give-them-identities) | **KEEP** | Levée IA (agents), pertinent |
| 2089 | selected | 57 | 35(15/12/8) | 12 | 0 | 10(B) | 0 | ZDNet FR | [ZDNET Morning 16/06/2026 : Telcos et quantique : entre ](https://www.zdnet.fr/actualites/zdnet-morning-16-06-2026-telcos-et-quantique-entre-miracle-et-peril-cybersecurite-et-sous-traitants-nouveau-revers-judiciaire-pour-elon-musk-497003.htm) | **REJECT** | Digest « Morning », sujets mélangés |
| 2200 | selected | 57 | 35(15/12/8) | 0 | 0 | 15(A) | 7 | Siècle Digital | [Snap lance ses lunettes de réalité augmentée à 2 200 do](https://siecledigital.fr/2026/06/17/snap-lance-ses-lunettes-de-realite-augmentee-a-2-200-dollars-et-mise-sur-lapres-smartphone) | **REJECT** | Gadget consumer, hors positionnement |
| 2064 | selected | 56 | 32(15/9/8) | 9 | 0 | 15(A) | 0 | Siècle Digital | [Sébastien Lecornu annonce 655 millions d’euros suppléme](https://siecledigital.fr/2026/06/16/sebastien-lecornu-annonce-655-millions-deuros-supplementaires-pour-faire-entrer-lia-dans-letat) | **KEEP** | Souveraineté/business IA publique FR |
| 2086 | selected | 56 | 35(15/12/8) | 6 | 0 | 15(A) | 0 | TechCrunch AI | [SpaceX to acquire Cursor for $60B in stock, days after ](https://techcrunch.com/2026/06/16/spacex-to-acquire-cursor-for-60b-in-stock-days-after-blockbuster-ipo) | **REJECT** | Doublon SpaceX/Cursor (cf. 2185) |
| 2133 | selected | 56 | 35(15/12/8) | 6 | 0 | 15(A) | 0 | TechCrunch AI | [ChatGPT’s market share slips below 50% for first time](https://techcrunch.com/2026/06/16/chatgpts-market-share-slips-below-50-for-first-time) | **KEEP** | Signal marché IA stratégique |
| 2231 | selected | 56 | 23(15/0/8) | 15 | 0 | 10(B) | 8 | Maddyness | [VivaTech : Yann LeCun livre un plaidoyer en faveur d'un](https://www.maddyness.com/2026/06/17/vivatech-yann-lecun-livre-un-plaidoyer-en-faveur-dune-ia-souveraine-pour-chaque-etat) | **KEEP** | IA souveraine, angle stratégique |
| 2094 | selected | 55 | 21(15/6/0) | 18 | 0 | 15(A) | 1 | TechCrunch AI | [Probably raises $9M to build a more reliable kind of AI](https://techcrunch.com/2026/06/16/probably-raises-9m-to-build-a-more-reliable-kind-of-ai) | **KEEP** | Levée IA (fiabilité modèles) |
| 2167 | selected | 55 | 23(15/0/8) | 15 | 0 | 10(B) | 7 | ZDNet FR | [Anthropic dépasse OpenAI sur le marché des abonnements ](https://www.zdnet.fr/actualites/anthropic-depasse-openai-sur-le-marche-des-abonnements-ia-en-entreprise-497093.htm) | **KEEP** | Anthropic business IA, stratégique |

**§1 — bilan : 15 KEEP (TP) / 10 REJECT (FP).** Les FP sont quasi tous des **doublons SpaceX** (2102, 2145, 2086), des **digests « Morning »** (2271, 2089), ou du **consumer/shopping/politique** (2193, 2066, 2200, 2272, 2181). → le ranker sur-crédite les gros chiffres événementiels sans valeur éditoriale réelle.

## 2. Échantillon DEFERRED (25) — jugé : KEEP si on AURAIT DÛ le publier (= faux négatif), REJECT si rejet correct
*(échantillon orienté frontière : near-misses 45-54 + sources premium déférées + quelques faibles)*
| id | shadow | score | imp(e/m/a) | rel | mena | src(tier) | fresh | source | titre (lien) | HUMAN_DECISION | HUMAN_COMMENT |
|--|--|--|--|--|--|--|--|--|--|--|--|
| 2000 | deferred | 54 | 27(15/12/0) | 12 | 0 | 15(A) | 0 | TechCrunch AI | [Salesforce acquires AI customer service platform Fin fo](https://techcrunch.com/2026/06/15/salesforce-acquires-ai-customer-service-platform-fin-for-3-6b) | **KEEP** | FN : acquisition AI majeure (Salesforce $3.6B) |
| 2214 | deferred | 54 | 23(15/0/8) | 18 | 0 | 5(C) | 8 | Numerama | [Google dévoile l’Open Knowledge Format, sa réponse au c](https://www.numerama.com/tech/2278019-google-devoile-lopen-knowledge-format-sa-reponse-au-casse-tete-du-contexte-pour-les-agents-ia.html) | **KEEP** | FN : infra IA Google (agents) |
| 2219 | deferred | 54 | 21(15/6/0) | 15 | 0 | 10(B) | 8 | ICT Journal | [L’IA pousse lastminute.com à réduire ses effectifs de 2](https://www.ictjournal.ch/news/2026-06-17/lia-pousse-lastminutecom-a-reduire-ses-effectifs-de-25) | **KEEP** | FN : impact emploi IA, business |
| 2268 | deferred | 54 | 32(15/9/8) | 0 | 0 | 10(B) | 12 | ZDNet FR | [SpaceX enregistre sa première baisse en bourse : la fré](https://www.zdnet.fr/actualites/spacex-enregistre-sa-premiere-baisse-en-bourse-la-frenesie-des-investisseurs-particuliers-marque-le-pas-497170.htm) | **REJECT** | Doublon SpaceX bourse |
| 2288 | deferred | 54 | 15(15/0/0) | 6 | 16 | 5(C) | 12 | Yabiladi | [Les FAR concluent un accord avec un MRE pour la product](https://www.yabiladi.com/articles/details/196913/concluent-accord-avec-pour-production.html) | **REJECT** | Hors positionnement IA/tech (défense) |
| 2195 | deferred | 53 | 21(15/6/0) | 9 | 0 | 15(A) | 8 | Wamda | [Pickappo secures $530,000 to expand on-demand delivery ](http://wamda.com/2026/06/pickappo-secures-530000-expand-demand-delivery-infrastructure) | **KEEP** | FN MENA : startup levée région (mena=0 raté) |
| 2221 | deferred | 52 | 14(0/6/8) | 15 | 0 | 15(A) | 8 | TechCrunch AI | [Collecting robot training data is dirty, unglamorous wo](https://techcrunch.com/2026/06/17/collecting-robot-training-data-is-dirty-unglamorous-work-some-ai-labs-are-already-paying-xdof-to-do-it) | **KEEP** | FN : IA infra/data, angle intéressant |
| 2261 | deferred | 52 | 26(15/6/5) | 9 | 0 | 5(C) | 12 | Les Numériques | [Actualité : Votre prochaine voiture pourrait ne plus av](https://www.lesnumeriques.com/voiture/votre-prochaine-voiture-pourrait-ne-plus-avoir-de-radio-fm-apres-tesla-de-plus-en-plus-de-constructeurs-s-y-mettent-n257718.html) | **REJECT** | Consumer auto, hors sujet IA |
| 2119 | deferred | 51 | 32(15/12/5) | 3 | 0 | 15(A) | 1 | TechCrunch AI | [SpaceX is public: Everything you need to know post-IPO](https://techcrunch.com/2026/06/16/spacex-is-public-everything-you-need-to-know-post-ipo) | **REJECT** | Doublon SpaceX IPO |
| 2213 | deferred | 51 | 15(15/0/0) | 12 | 0 | 15(A) | 9 | Wamda | [WakeCap acquires Frontline as it builds an end-to-end c](http://wamda.com/2026/06/wakecap-acquires-frontline-builds-end-end-construction-intelligence-platform) | **KEEP** | FN MENA : M&A construction intelligence (mena=0 raté) |
| 2226 | deferred | 51 | 27(15/12/0) | 6 | 0 | 10(B) | 8 | Maddyness | [Green-Got lève 8 millions d’euros en 52 minutes pour bâ](https://www.maddyness.com/2026/06/17/green-got-leve-8-millions-deuros-en-52-minutes-pour-batir-sa-banque-durable) | **REJECT** | Fintech verte, hors IA core |
| 2283 | deferred | 51 | 20(15/0/5) | 9 | 0 | 10(B) | 12 | ZDNet FR | [Pénurie de puces : même Apple annonce des hausses de pr](https://www.zdnet.fr/actualites/penurie-de-puces-meme-apple-annonce-des-hausses-de-prix-497191.htm) | **REJECT** | Consumer/supply, faible IA |
| 2282 | deferred | 51 | 27(15/12/0) | 3 | 0 | 10(B) | 11 | ZDNet FR | [Les grands groupes flèchent 2Mds€ vers la French Tech](https://www.zdnet.fr/actualites/les-grands-groupes-flechent-2mdse-vers-la-french-tech-497188.htm) | **REJECT** | Doublon financement French Tech |
| 2017 | deferred | 50 | 32(15/12/5) | 3 | 0 | 15(A) | 0 | TechCrunch AI | [SpaceX is public: Everything you need to know post-IPO](https://techcrunch.com/2026/06/15/spacex-is-public-everything-you-need-to-know-post-ipo) | **REJECT** | Doublon SpaceX IPO |
| 2042 | deferred | 50 | 21(15/6/0) | 6 | 8 | 15(A) | 0 | Wamda | [Sovra lands $2 million+ pre-seed led by Pharsalus Capit](http://wamda.com/2026/06/sovra-lands-2-million-pre-seed-led-pharsalus-capital) | **KEEP** | FN MENA : levée startup région |
| 2157 | deferred | 50 | 23(15/0/8) | 12 | 0 | 10(B) | 5 | Maddyness | [VivaTech : Aive s’associe à Nvidia pour améliorer le ré](https://www.maddyness.com/2026/06/17/vivatech-aive-sassocie-a-nvidia-pour-ameliorer-le-referencement-de-la-video-par-les-ia) | **KEEP** | FN : partenariat Nvidia, IA vidéo |
| 2178 | deferred | 50 | 23(15/0/8) | 6 | 0 | 15(A) | 6 | Siècle Digital | [Claude va vous demander vos papiers d’identité pour con](https://siecledigital.fr/2026/06/17/claude-va-vous-demander-vos-papiers-didentite-pour-continuer-a-utiliser-certaines-fonctions) | **KEEP** | FN : Anthropic/Claude, produit majeur |
| 2187 | deferred | 50 | 24(15/9/0) | 3 | 0 | 15(A) | 8 | Wamda | [ISSF backs Endeavor Catalyst V to strengthen Jordan&#03](http://wamda.com/2026/06/issf-backs-endeavor-catalyst-v-strengthen-jordans-venture-capital-ecosystem) | **KEEP** | FN MENA : écosystème VC Jordanie (mena=0 raté) |
| 2188 | deferred | 49 | 23(15/0/8) | 9 | 0 | 10(B) | 7 | Maddyness | [VivaTech : une 10e édition sous le prisme de l'IA et de](https://www.maddyness.com/2026/06/17/vivatech-une-10e-edition-sous-le-prisme-de-lia-et-de-la-souverainete) | **KEEP** | FN : IA souveraine, angle stratégique |
| 2168 | deferred | 49 | 29(15/6/8) | 3 | 0 | 10(B) | 7 | ZDNet FR | [Snap lance Specs à 2 200 dollars, ses premières lunette](https://www.zdnet.fr/actualites/snap-lance-specs-a-2-200-dollars-ses-premieres-lunettes-ar-autonomes-pour-le-grand-public-497086.htm) | **REJECT** | Gadget consumer (doublon 2200) |
| 2082 | deferred | 17 | 6(0/6/0) | 6 | 0 | 5(C) | 0 | Journal du Net | [La cybersécurité des citoyens : le grand angle mort](https://www.journaldunet.com/cybersecurite/1551353-la-cybersecurite-des-citoyens-le-grand-angle-mort) | **REJECT** | Faible, généraliste |
| 2156 | deferred | 36 | 21(15/6/0) | 0 | 0 | 10(B) | 5 | Frenchweb | [LIGHTBRINGER lève 8,6 millions d’euros : les brevets vo](https://www.frenchweb.fr/lightbringer-leve-86-millions-deuros-les-brevets-vont-il-devenir-une-commodite/462407) | **REJECT** | Niche brevets, faible IA |
| 2233 | deferred | 39 | 20(8/12/0) | 6 | 0 | 5(C) | 8 | Les Numériques | [Actualité : Coupe du monde 2026 : j'ai épluché les tech](https://www.lesnumeriques.com/intelligence-artificielle/coupe-du-monde-2026-j-ai-epluche-les-technologies-du-mondial-et-le-vrai-arbitre-cette-annee-c-est-l-ia-n257692.html) | **REJECT** | Sport/consumer, faible valeur |
| 2024 | deferred | 13 | 5(0/0/5) | 3 | 0 | 5(C) | 0 | Les Numériques | [Actualité : Bon plan – Les écouteurs sans fil Apple Air](https://www.lesnumeriques.com/ecouteurs-sans-fil/bon-plan-les-ecouteurs-sans-fil-apple-airpods-pro-3-5-etoiles-a-188-10-12-n257579.html) | **REJECT** | Bon plan shopping, hors sujet |
| 2276 | deferred | 31 | 8(0/0/8) | 6 | 0 | 5(C) | 12 | Les Numériques | [Actualité : Le vidéoprojecteur TCL C1 profite d'une rem](https://www.lesnumeriques.com/videoprojecteur/le-videoprojecteur-tcl-c1-profite-d-une-remise-de-50-chez-amazon-n257727.html) | **REJECT** | Bon plan shopping, hors sujet |

**§2 — bilan : 11 KEEP (FN) / 14 REJECT (TN).** Les FN sont les **vrais ratés stratégiques** : M&A IA (Salesforce 2000), infra IA (Google Open Knowledge 2214, robot-data 2221), Anthropic/Claude (2178), Nvidia (2157), IA souveraine (2188), et **4 startups MENA Wamda** (2195, 2213, 2042, 2187) — dont 3 avec `mena=0` (détection MENA ratée). Les TN sont corrects (doublons SpaceX, bons plans shopping, consumer).

## 3. Métriques — ✅ CALCULÉES
> Conventions : **shadow_selected** = positif du ranker ; **HUMAN KEEP** = positif humain. Échantillon = 50 (25 selected + 25 deferred).

| Quantité | Définition | Compte |
|--|--|--|
| **TP** | selected ∧ KEEP | **15** |
| **FP** (faux positifs) | selected ∧ REJECT | **10** |
| **FN** (faux négatifs) | deferred ∧ KEEP | **11** |
| **TN** | deferred ∧ REJECT | **14** |

```
Precision            = TP / (TP + FP) = 15 / 25  = 0.60   → 60 %
Recall (estimé)      = TP / (TP + FN) = 15 / 26  = 0.577  → 57.7 %
Accord humain/ranker = (TP + TN) / 50 = 29 / 50  = 0.58   → 58 %
```

| Métrique | Valeur |
|--|--|
| TP | **15** |
| FP | **10** |
| FN | **11** |
| TN | **14** |
| **Precision** | **60 %** |
| **Recall estimé** | **57.7 %** |
| **Accord humain/ranker** | **58 %** |

**Lecture :** 1 article « selected » sur 2,5 est un mauvais choix (FP), et le ranker **rate ~42 % des bons articles** (FN). Accord global 58 % → à peine au-dessus du hasard sur cet échantillon frontière. **Insuffisant pour enforce.**

## 4. Audit MENA spécifique — 23 articles (+ décision humaine)
**Ranker : 2/23 sélectionnés. Humain : 8 KEEP / 15 REJECT.**
| id | source | tier | score | shadow | mena | imp | rel | fresh | raison du score | HUMAN | titre |
|--|--|--|--|--|--|--|--|--|--|--|--|
| 2286 | ICT Journal | B | 59 | selected | 8 | 23 | 6 | 12 | mena>0 + importance/source suffisants → selected | **REJECT** | Des garde-fous pour les mineurs, un cap pour l’IA: les  |
| 2126 | Wamda | A | 55 | selected | 8 | 21 | 9 | 2 | mena>0 + importance/source suffisants → selected | **KEEP** | CNTXT AI closes $60 million Series A to deploy secure A |
| 2288 | Yabiladi | C | 54 | deferred | 16 | 15 | 6 | 12 | mena=16 mais importance faible (imp=15) → total<55 | **REJECT** | Les FAR concluent un accord avec un MRE pour la product |
| 2195 | Wamda | A | 53 | deferred | 0 | 21 | 9 | 8 | mena=0 → aucune entite MENA detectee dans le texte | **KEEP** | Pickappo secures $530,000 to expand on-demand delivery  |
| 2213 | Wamda | A | 51 | deferred | 0 | 15 | 12 | 9 | mena=0 → aucune entite MENA detectee dans le texte | **KEEP** | WakeCap acquires Frontline as it builds an end-to-end c |
| 2042 | Wamda | A | 50 | deferred | 8 | 21 | 6 | 0 | mena=8 mais importance faible (imp=21) → total<55 | **KEEP** | Sovra lands $2 million+ pre-seed led by Pharsalus Capit |
| 2187 | Wamda | A | 50 | deferred | 0 | 24 | 3 | 8 | mena=0 → aucune entite MENA detectee dans le texte | **KEEP** | ISSF backs Endeavor Catalyst V to strengthen Jordan&#03 |
| 2240 | Financial Afri | C | 49 | deferred | 8 | 27 | 0 | 9 | mena=8 mais importance faible (imp=27) → total<55 | **REJECT** | Le Burkina lève 44 milliards de FCFA au niveau du march |
| 2250 | Wamda | A | 47 | deferred | 0 | 15 | 6 | 11 | mena=0 → aucune entite MENA detectee dans le texte | **KEEP** | Syrian healthtech Moadna raises $50,000 in early-stage  |
| 2080 | Les Numériques | C | 39 | deferred | 16 | 15 | 3 | 0 | mena=16 mais importance faible (imp=15) → total<55 | **REJECT** | Actualité : France-Sénégal : comment voir le match de l |
| 2208 | Financial Afri | C | 38 | deferred | 16 | 9 | 0 | 8 | mena=16 mais importance faible (imp=9) → total<55 | **REJECT** | La BIDC injecte plus de 75 millions USD et 105 millions |
| 2139 | Les Numériques | C | 36 | deferred | 8 | 12 | 9 | 2 | mena=8 mais importance faible (imp=12) → total<55 | **REJECT** | Actualité : L’ONU alerte : en 2030, la consommation d'e |
| 2079 | Financial Afri | C | 33 | deferred | 16 | 12 | 0 | 0 | mena=16 mais importance faible (imp=12) → total<55 | **REJECT** | Au sommaire de Financial Afrik n°131 (Télécharger) |
| 2148 | CIO Mag | B | 33 | deferred | 8 | 0 | 12 | 3 | mena=8 mais importance faible (imp=0) → total<55 | **KEEP** | L’IA Jugaad : quand l’IA frugale devient stratégie |
| 2152 | Financial Afri | C | 33 | deferred | 8 | 14 | 3 | 3 | mena=8 mais importance faible (imp=14) → total<55 | **REJECT** | Les deux-roues et trois-roues électriques peuvent-ils t |
| 2245 | Financial Afri | C | 33 | deferred | 16 | 0 | 3 | 9 | mena=16 mais importance faible (imp=0) → total<55 | **REJECT** | Dakar accueille le premier Forum International de la Pr |
| 2023 | Financial Afri | C | 27 | deferred | 16 | 6 | 0 | 0 | mena=16 mais importance faible (imp=6) → total<55 | **REJECT** | De Interview exclusive – Thierno Habib Hann, CEO de She |
| 2146 | Financial Afri | C | 27 | deferred | 16 | 0 | 3 | 3 | mena=16 mais importance faible (imp=0) → total<55 | **REJECT** | Repenser le financement du développement au Sénégal |
| 2248 | Financial Afri | C | 27 | deferred | 0 | 12 | 0 | 10 | mena=0 → aucune entite MENA detectee dans le texte | **REJECT** | SIACE : 1,9 milliard de dollars mobilisés en 2025 pour  |
| 2001 | Financial Afri | C | 21 | deferred | 8 | 8 | 0 | 0 | mena=8 mais importance faible (imp=8) → total<55 | **REJECT** | Du financement aux résultats : la nouvelle équation du  |
| 2223 | Financial Afri | C | 21 | deferred | 8 | 0 | 0 | 8 | mena=8 mais importance faible (imp=0) → total<55 | **REJECT** | L’UEMOA mise sur trois filières pour relancer sa puissa |
| 2057 | Financial Afri | C | 16 | deferred | 8 | 0 | 3 | 0 | mena=8 mais importance faible (imp=0) → total<55 | **KEEP** | Une souveraineté numérique au pied d’argile : le vrai d |
| 2103 | Financial Afri | C | 14 | deferred | 8 | 0 | 0 | 1 | mena=8 mais importance faible (imp=0) → total<55 | **REJECT** | CEMAC : la BDEAC mise sur les marchés financiers intern |

**§4 — bilan MENA : 8 KEEP humain, le ranker n'en a attrapé qu'1 (2126).** → **Recall MENA = 1/8 = 12.5 %** (catastrophique).
- **Wamda sous-sélectionné** : 6 articles Wamda (tier A) jugés KEEP (2126, 2195, 2213, 2042, 2187, 2250), 1 seul sélectionné. **4 sur 6 ont `mena=0`** (2195, 2213, 2187, 2250) — la **détection d'entité MENA rate les startups Golfe/Jordanie/Syrie** dont le texte ne contient pas les mots-clés région attendus.
- **Financial Afrik = bruit confirmé** : 11/12 Financial Afrik jugés REJECT (dév./finance régionale hors tech IA). Seule exception KEEP : 2057 (souveraineté numérique). → l'intuition « Financial Afrik majoritairement bruit sauf souveraineté/tech réelle » est **validée**.
- **2286 (ICT Journal) sélectionné mais REJECT humain** : régulation mineurs, pas le bon angle premium → 1 des 10 FP.

---

## 5. Verdict humain — Étape 6.5 (confirmé par données)

### 5.1 Le ranker est-il GO tel quel ?
**❌ NON.** Precision 60 %, Recall 57.7 %, Accord 58 % sur l'échantillon frontière, et **Recall MENA 12.5 %**. En enforce, il publierait ~40 % de mauvais choix (doublons SpaceX, digests, shopping) **et** raterait ~40 % des bons (M&A IA, infra IA, startups MENA). **Reste en SHADOW.**

### 5.2 Faut-il recalibrer ?
**✅ OUI**, avant tout enforce. Les erreurs ne sont pas aléatoires — elles sont **systématiques et corrigeables** (doublons, digests, détection MENA, importance non-événementielle). C'est encourageant : un ranker déterministe peut adresser ces 4 patterns sans LLM.

### 5.3 Les 3 corrections prioritaires
1. **Dé-duplication + pénalité « digest »** *(corrige ~6 des 10 FP)*. Les doublons SpaceX (valorisation/IPO/Cursor : 2102/2145/2086/2119/2017/2268) et les digests « ZDNET Morning » (2271/2089) inondent le selected. → regrouper par entité/événement (garder 1 article par story) + pénaliser les titres « Morning/ZD Tech/digest ». **Gain Precision le plus rapide.**
2. **Enrichir la détection d'importance au-delà de l'événementiel** *(corrige le gros des FN)*. L'importance actuelle = mots-clés levée/M&A/launch ; elle rate l'**infra/plateforme IA** (Google Open Knowledge, robot-data), les **signaux marché** (ChatGPT <50 %), les **acquisitions hors-pattern** (Salesforce/Fin), et l'**écosystème/analyse**. → ajouter un axe « importance structurelle » (infra, modèles, acteurs frontier, M&A même sans mot-clé exact).
3. **Réparer la détection d'entité MENA + relever sa pondération** *(corrige le Recall MENA 12.5 %)*. 4 startups Wamda KEEP ont `mena=0` : le lexique MENA rate Golfe/Jordanie/Syrie/villes/acteurs régionaux hors « Maroc/MENA » littéral. → élargir le lexique d'entités (pays GCC, villes, fonds régionaux, Wamda comme signal de source) **et** monter le poids MENA pour que `mena>0 + startup` franchisse le seuil. **Garder Financial Afrik fortement pénalisé** (bruit dév./finance).

### 5.4 Le seuil 55 est-il bon ?
**🟡 Globalement oui pour le VOLUME (~11/jour), mais ce n'est PAS le levier.** Les erreurs sont des deux côtés du seuil **pour de mauvaises raisons** : des FP scorent haut (gros chiffres SpaceX) et des FN scorent juste sous 55 (Salesforce 54, Google 54, Wamda 50-53). Bouger le seuil ne ferait qu'échanger des FP contre des FN. → **garder ~55** et corriger d'abord l'importance + la dé-duplication + MENA. Re-mesurer le seuil **après** recalibration.

### 5.5 Importance, MENA, ou sources ?
| Cause | Verdict humain | Preuve (données §1-§4) |
|---|---|---|
| **Détection d'importance** | 🔴 **CAUSE PRINCIPALE — défaut dans LES DEUX SENS** | Sur-crédite les gros chiffres événementiels → 10 FP (SpaceX, digests). Sous-crédite l'infra/marché/M&A non-événementiels → la majorité des 11 FN (Salesforce, Google, robot-data, ChatGPT-share). |
| **MENA (détection + poids)** | 🟠 **CAUSE SECONDAIRE FORTE** | Recall MENA 12.5 %. 4 Wamda KEEP avec `mena=0` (détection ratée) ; poids 16 trop bas pour franchir 55 même quand détecté. |
| **Sources** | 🟢 **PAS le problème** | Pondération source correcte : Financial Afrik (C) justement pénalisé = bruit confirmé (11/12 REJECT) ; Wamda (A) bien noté en source, le problème est ailleurs (détection MENA + importance). |

**Conclusion :** le problème vient **d'abord de l'importance** (mal calibrée dans les deux sens : doublons/gros-chiffres sur-sélectionnés, valeur structurelle sous-sélectionnée), **ensuite du MENA** (détection d'entité défaillante + poids trop faible). **Les sources ne sont pas en cause** — la hiérarchie A/B/C est validée par le jugement humain. Le préliminaire §ancien (« importance trop étroite ») est confirmé **et complété** : le défaut d'importance est **bidirectionnel**, pas seulement une cécité aux contenus « soft ».

---

> Dossier de revue SHADOW complété — décisions humaines intégrées, métriques calculées, verdict rendu. **Aucune écriture DB, aucun recalcul du ranker, aucun changement de code/score, aucun LLM, aucun enforce, aucune calibration automatique appliquée.** Les 3 corrections §5.3 sont des recommandations à valider/planifier séparément.

## 6. Règle éditoriale appliquée (référence)
**KEEP** si utile pour DarijaAI (média IA/Tech orienté Maroc/Afrique/MENA/francophonie) : IA majeure · Big Tech (OpenAI/Anthropic/Google/Nvidia/Meta) · startup/levée MENA-Afrique · souveraineté IA · business AI · régulation IA · impact stratégique.
**REJECT** si : shopping/gadget/bon plan · digest « Morning » multi-sujets · trop politique · consumer tech faible · doublon SpaceX répétitif · hors-positionnement · trop faible pour un slot premium.
