Roadmap d’exécution DarijaAI
Phase 0 — Sécuriser l’état actuel

Objectif : ne rien perdre et corriger le contexte projet.

Lancer les tests existants.
Committer le backend API, schemas, migration, tests.
Committer le frontend skeleton séparément.
Corriger les fichiers contexte :
mauvais path current-focus.md
active-tasks.md stale
fausse mention que security.py existe
Mettre à jour task-memory.

Résultat attendu : projet propre, contexte fiable, zéro travail important non committé.

Phase 1 — Sécurité admin

Objectif : empêcher tout accès public dangereux.

Créer backend/app/core/security.py.
Implémenter JWT HS256.
Ajouter require_admin.
Protéger toutes les routes admin.
Ajouter tests :
accès sans token refusé
token invalide refusé
token valide accepté
Vérifier que les routes publiques restent accessibles.

Résultat attendu : backend déployable sans exposer l’admin.

Phase 2 — Refactor du pipeline article

Objectif : remplacer le gros script fragile process_article.py.

Découper le pipeline en services/jobs :
fetch raw article
relevance filter
localization
quality gate
image generation
save draft
Ajouter état clair par étape :
pending
processing
localized
image_ready
draft
rejected
failed
Ajouter retry propre.
Ajouter logs structurés par étape.
Garder le script one-shot seulement comme wrapper temporaire.

Résultat attendu : pipeline robuste, testable, schedulable.

Phase 3 — Worker + scheduler

Objectif : automatiser l’ingestion sans dépendre de commandes manuelles.

Décider officiellement :
arq pour jobs async
APScheduler uniquement pour déclencher les tâches périodiques
Créer worker entrypoint.
Scheduler :
fetch RSS chaque 30 min
process pending articles
retry failed jobs
Ajouter commandes Makefile :
make worker
make fetch-articles
make process-pending
Ajouter tests d’intégration worker.

Résultat attendu : système automatique backend complet.

Phase 4 — API publique + admin stable

Objectif : finaliser l’API consommable par le frontend.

Finaliser endpoints publics :
liste articles publiés
détail article par slug
catégories
recherche simple
Finaliser endpoints admin :
liste drafts
détail draft
éditer article
publish/unpublish
settings
sources RSS
Standardiser pagination cursor-based.
Standardiser erreurs.
Générer/mettre à jour types OpenAPI.

Résultat attendu : contrat API stable.

Phase 5 — Frontend branché à l’API réelle

Objectif : supprimer les mock data progressivement.

Créer frontend/lib/api.ts.
Brancher pages publiques :
home
liste articles
détail article
catégorie
Brancher admin :
login
dashboard
liste drafts
editor article
settings
Gérer loading/error/empty states.
Vérifier RTL, mobile 375px, SEO.

Résultat attendu : premier vrai produit utilisable end-to-end.

Phase 6 — Admin review workflow

Objectif : rendre la publication humaine fluide.

Page admin article draft.
Afficher :
article source
version Darija
image générée
quality gate result
AI cost
Actions :
éditer
rejeter
régénérer image
republier avec Sonnet si flagship
publier
Historique minimal des changements.
Empêcher publication si quality gate failed sauf override explicite.

Résultat attendu : workflow éditorial réel.

Phase 7 — SEO + contenu public

Objectif : préparer Google indexation.

sitemap.ts
robots.ts
feed.xml
metadata par page
JSON-LD NewsArticle
Open Graph image
canonical URL
pages :
about
contact
privacy
terms
Lighthouse mobile ≥95.

Résultat attendu : plateforme prête pour trafic organique.

Phase 8 — Observabilité + coûts

Objectif : surveiller production.

Configurer Sentry DSN.
Logger coûts Claude/Replicate.
Dashboard admin :
articles traités
drafts
rejected
coût journalier
queue depth
Alertes :
backend down
error rate
AI cost > seuil
scraping silent 24h
Uptime Robot.

Résultat attendu : production surveillée.

Phase 9 — CI/CD + environnements

Objectif : déployer proprement.

GitHub Actions :
lint
typecheck
tests
build frontend
build backend
Railway backend.
Vercel frontend.
Neon DB.
Upstash Redis.
R2 storage.
Staging avant production.
Migration automatique contrôlée.

Résultat attendu : déploiement fiable.

Phase 10 — Distribution

Objectif : transformer le média en canal d’acquisition.

Newsletter Resend.
LinkedIn auto-draft.
Instagram/Facebook later.
Page newsletter.
Capture email.
Tracking source trafic.
Publication manuelle au début, auto-draft seulement.

Résultat attendu : début de croissance audience.

Phase 11 — Beta privée

Objectif : tester avec vrais utilisateurs.

Publier 30–50 articles.
Tester SEO.
Partager avec audience marocaine tech.
Collecter feedback :
qualité Darija
sujets préférés
lisibilité mobile
confiance
Corriger UX/contenu.

Résultat attendu : validation marché initiale.

Phase 12 — Lancement public

Objectif : passer de projet à plateforme.

100 articles publiés.
Pipeline stable.
Admin stable.
SEO complet.
Monitoring actif.
Newsletter active.
Plan de contenu hebdomadaire.
Lancement LinkedIn + groupes tech marocains.

Résultat attendu : DarijaAI live officiellement.

---

## Backlog opérationnel — Améliorations futures (non planifiées)

> Items identifiés, à prioriser ultérieurement. Pas de chantier ouvert.

- **Détection automatique `insufficient_quota` OpenAI + alerte proactive.**
  Sur le modèle de la détection billing Claude (`billing_error_detected` + Sentry + SpendGuard).
  Aujourd'hui l'épuisement OpenAI (Proofreader) n'émet qu'un log discret `proofreader.openai_failed`,
  sans alerte. Découvert via l'incident 2026-06-17 (cf. `docs/rca/2026-06-17-openai-quota-exhausted.md`),
  impact nul à ce jour mais lacune réelle de monitoring. *(Origine : RCA 2026-06-17.)*