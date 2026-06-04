# 🎨 TitritAI — Spécification de design (analyse des maquettes)

> Généré le **2026-05-26** · Basé sur `website-design-template.png` + `website-design-template66.png`.
> **Aucun code à ce stade** — c'est un rapport d'analyse + plan. Couleurs échantillonnées au pixel sur les maquettes.

---

## 1. Résumé & méthode

Les deux maquettes montrent **le même design system** décliné :
- `website-design-template.png` : vue d'ensemble (hero + admin).
- `website-design-template66.png` : **version complète et de référence** — montre tous les écrans (home, liste articles, article, services, contact, 404, dashboard admin, footer).

**Style global** : thème **sombre** « AI/tech premium », **RTL arabe**, accents **violet + bleu** avec dégradés, illustrations néon (cerveau lumineux au-dessus d'une skyline marocaine au coucher de soleil), mascotte robot, ambiance « SaaS futuriste ». Très proche de l'ADN actuel du site (sombre, RTL, Tajawal) — c'est un **restylage + nouveaux composants visuels**, pas une refonte technique.

---

## 2. Au sujet de « Claude design »

Pour être transparent : il n'existe pas d'outil séparé « Claude design » que je peux lancer pour générer automatiquement la maquette en site. **Mais c'est moi (Claude) qui vais reproduire ce design directement en code** (Tailwind/CSS) à partir de cette spec + des maquettes. Le résultat sera **très proche** du visuel.

La seule limite pour un rendu **pixel-identique** : les **illustrations sur mesure** (cerveau+ville, mascotte, astronaute 404) — voir §7. C'est le point qui demande une décision de ta part.

---

## 3. Identité visuelle

### 3.1 Palette de couleurs (échantillonnée sur les maquettes)

| Rôle | Hex | Usage |
|---|---|---|
| **Fond principal** | `#060914` → `#020617` | Body, sections (presque noir bleuté) |
| **Fond surélevé / cartes** | `#0e162a` / `#0d1324` | Cards articles, panneaux, header |
| **Fond carte alt** | `#111a2e` | Cartes services, dashboard |
| **Bordure / séparateur** | `#1e2940` (ou blanc 6–8%) | Contours de cartes, lignes |
| **Violet primaire** | `#7c3aed` (famille `#642cac`/`#562593`) | Boutons CTA, liens actifs, surbrillances |
| **Violet foncé (hover)** | `#6d28d9` | États hover des boutons |
| **Bleu secondaire** | `#2563eb` (famille `#204387`/`#07227b`) | Dégradés, lueur cerveau |
| **Dégradé hero** | violet → bleu → magenta | Cerveau néon, halos |
| **Dégradé bannière CTA** | `#6d28d9` → `#4f46e5` (violet→indigo) | Bannière « جاهز لتحويل... » |
| **Ambre / or** | `#f59e0b` | Icônes de la section Services |
| **Cyan (highlights)** | `#22d3ee` | Reflets du cerveau, accents data |
| **Texte principal** | `#f1f5f9` / blanc | Titres |
| **Texte atténué** | `#94a3b8` (échantillonné `#717597`/`#6871a3`) | Paragraphes, métadonnées |
| **Vert (positif)** | `#22c55e` | Stats dashboard (+x%) |

> Ces valeurs deviendront des **tokens CSS** (`--color-bg`, `--color-primary`, etc.) dans `globals.css` / config Tailwind.

### 3.2 Typographie
- **Arabe RTL** — police géométrique moderne. Le projet utilise déjà **Tajawal** (proche du rendu maquette) → on la garde. Alternative très fidèle : **Cairo** ou **IBM Plex Sans Arabic** si tu veux coller davantage.
- Hiérarchie : titres très **gras** (700/800), corps en poids normal, interlignage aéré.
- Chiffres/termes latins (AI, GPT-5…) en police latine (Inter) via `<bdi>` — déjà en place.

### 3.3 Effets visuels signature
- **Lueurs (glow)** violet/bleu derrière les éléments clés (cerveau, boutons, cartes au hover).
- **Dégradés** subtils sur fonds de section et bannières.
- **Cartes** : coins arrondis (~12–16px), fond sombre, bordure fine, ombre douce + glow au hover.
- **Glassmorphism** léger sur le header (fond semi-transparent flouté).
- Motif/texture discrète possible (zellige/points) déjà présent dans le site actuel.

---

## 4. Structure globale

### Header (RTL)
Logo **« DarijaAI »** (→ à renommer **TitritAI**) avec petite icône, à droite. Menu horizontal : الرئيسية · المقالات · الخدمات · من نحن · تواصل معنا. Bouton CTA violet à gauche. Header sombre semi-transparent, sticky.

### Footer
Fond sombre/violet profond, multi-colonnes : à propos + liens rapides + catégories + **newsletter (champ email + bouton)** + icônes réseaux sociaux. Mention copyright.

---

## 5. Pages & sections (d'après `template66`)

### 5.1 Accueil
1. **Hero** : grand titre « الذكاء الاصطناعي بالدارجة، للمغرب وللعالم » + sous-texte, 2 boutons (violet plein + outline), à droite l'**illustration cerveau néon sur skyline marrakchie**. En dessous : **bande de stats** (`+2,500` / `+50K` / `+120` / `+15` avec libellés).
2. **أحدث الأخبار** (Derniers articles) : grille de **4 cartes** (image + titre + meta).
3. **خدمات الذكاء الاصطناعي** (Services) : **4 cartes** à **icônes ambre** (titre + description courte).
4. **Bannière CTA** : dégradé violet, texte « جاهز لتحويل عملك بالذكاء الاصطناعي؟ » + **mascotte robot** + bouton.
5. **ماذا يقول عملاؤنا** (Témoignages) : **3 cartes** avatar + nom + citation, avec pagination à points.
6. **Footer**.

### 5.2 Liste des articles (صفحة الأخبار)
En-tête de page + **liste verticale d'articles** (vignette + titre + extrait + meta) + **pagination** numérotée.

### 5.3 Détail article (صفحة المقال)
Titre, **auteur + avatar** (ex. « Ahmed Bensaid »), date, **image hero** (cerveau), corps de l'article (RTL, titres H2, listes), **icônes de partage** (WhatsApp, X, LinkedIn…), tags, articles liés.

### 5.4 Services (صفحة الخدمات)
Grille de **cartes services** à icônes ambre (plus détaillée que la home).

### 5.5 Contact (تواصل معنا)
**Formulaire** (nom, email, message + bouton violet) à côté d'un panneau **infos de contact** (email, tél, réseaux).

### 5.6 404
Grand **« 404 »** + **illustration astronaute**, texte « الصفحة غير موجودة » + bouton retour. *(On a déjà une page 404 brandée — à restyler selon ce visuel.)*

### 5.7 Dashboard admin (لوحة الإدارة)
Sidebar de navigation + **4 cartes de stats** (`1,248` / `320K` / `25.6K` / `8,430` avec +%) + **graphe en courbe** + **donut chart** + liste d'éléments récents. *(L'admin actuel est fonctionnel mais au style différent → restylage.)*

---

## 6. Composants réutilisables à créer/restyler
- **Bouton** : variantes `primary` (violet plein), `outline`, `ghost`, tailles sm/md/lg, état hover avec glow.
- **Carte article** (3 formats : featured, compact, liste).
- **Carte service** (icône ambre + titre + texte).
- **Carte témoignage** (avatar + citation).
- **Stat counter** (chiffre + libellé, variante dashboard avec delta %).
- **Badge / tag** (catégories).
- **Bannière CTA** (dégradé + mascotte).
- **Header** + **Footer** + **Newsletter inline**.
- **Pagination**.
- **Composants dashboard** : stat card, line chart, donut chart (lib : `recharts` ou `chart.js` — à décider).

---

## 7. ⚠️ Assets visuels requis (LE point clé pour « les mêmes images »)

Le design repose sur **3 illustrations sur mesure** :
1. **Cerveau néon + skyline marrakchie** (hero) — l'élément signature.
2. **Mascotte robot** (bannière CTA).
3. **Astronaute** (404).

Les maquettes sont des images composites en **600px** → **impossible d'en extraire ces illustrations en qualité utilisable**. Pour avoir « les mêmes images », il faut choisir :

| Option | Résultat | Effort |
|---|---|---|
| **A. Tu fournis les fichiers source** (PNG/SVG haute résolution du designer) | **Identique** ✅ | Tu les récupères |
| **B. Régénération via le pipeline Flux** (déjà en place dans le projet) | **Très proche**, pas identique | Je génère + on itère |
| **C. Banque d'images / IA tierce** (Midjourney…) puis intégration | Proche | Manuel |

➡️ **Recommandé : Option A si tu as accès aux sources** (résultat pixel-identique). Sinon **Option B** (je génère des illustrations proches avec Flux, on ajuste les prompts). Le reste du design (couleurs, layout, composants) sera **fidèle** quoi qu'il arrive.

---

## 8. Écart avec le site actuel (gap analysis)

| Élément | Actuel | Maquette | Action |
|---|---|---|---|
| Thème sombre + RTL + Tajawal | ✅ déjà en place | ✅ | Conserver, réaccorder les tokens |
| Palette violet/bleu + glow | partielle | signature forte | **Restyler** les tokens + effets |
| Hero avec illustration | basique | cerveau néon + stats | **Refaire** (asset + layout) |
| Sections home (services, témoignages, CTA, stats) | partielles/absentes | complètes | **Ajouter** |
| Cartes articles | existantes | restylées (glow, format) | Restyler |
| Page article / liste | fonctionnelles | restylées | Restyler |
| Services / Contact | statiques basiques | maquettées | Restyler |
| 404 | brandée (Darija) | astronaute | Restyler |
| Admin dashboard | fonctionnel, style sobre | dashboard riche (charts) | Restyler + ajouter charts |

**Bonne nouvelle** : la base technique (Next.js 15, RTL, Tajawal, composants shadcn) est compatible — c'est essentiellement du **CSS/Tailwind + nouveaux composants + assets**, pas une reconstruction.

---

## 9. Plan d'implémentation proposé (quand tu donneras le GO)

1. **Tokens & fondations** : définir la palette/effets dans `globals.css` + config Tailwind ; police ; utilitaires glow/gradient.
2. **Composants de base** : Button, Card, Badge, StatCounter, Section wrappers, Header, Footer.
3. **Home** : hero + stats + derniers articles + services + CTA + témoignages.
4. **Pages publiques** : liste articles, détail article, services, contact, 404.
5. **Admin** : restyle + dashboard (stats + charts).
6. **Assets** : intégrer les illustrations (Option A ou B) + OG images.
7. **QA** : RTL, responsive mobile (375px), perf (LCP/CLS), accessibilité contraste.

> Chaque étape sera vérifiable en local puis déployée via le pipeline « push-to-deploy » déjà en place.

---

## 10. Décisions / questions pour toi

1. **Illustrations (§7)** : tu as les fichiers source (Option A) ? Sinon on part sur Flux (Option B) ?
2. **Nom de marque affiché** : on remplace « DarijaAI » par **« TitritAI »** dans le header/footer/logo ? (réglage `business_name`, déjà éditable)
3. **Police arabe** : on garde **Tajawal** (déjà en place, proche) ou on vise **Cairo / IBM Plex Sans Arabic** pour coller davantage ?
4. **Sections « entreprise »** (services, témoignages, stats clients, contact, dashboard riche) : on les implémente toutes, ou on priorise d'abord le **public éditorial** (home + articles) et l'admin plus tard ?
5. **Charts dashboard** : librairie `recharts` (React, simple) OK pour toi ?

---

*Sources : maquettes `website-design-template*.png` · couleurs échantillonnées via Pillow · base technique : `frontend/` (Next.js 15, Tailwind v4, RTL).*
