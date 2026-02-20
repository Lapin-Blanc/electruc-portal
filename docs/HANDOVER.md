# Handover Technique - Electruc Portal

## 1) Objectif du projet
Electruc Portal est un portail client pédagogique (fictif) pour un fournisseur d'énergie en Belgique.
Le projet est conçu pour des ateliers (seniors/adultes en formation), avec un flux réaliste mais simplifié.

## 2) Stack et structure
- Backend: Django 5.x
- Templates: Django server-side + Bootstrap
- DB: SQLite (local et prod actuelle)
- Déploiement: Docker Compose (dev + prod), cloudflared côté VPS
- App principale: `portal`

Fichiers centraux:
- Config Django: `electruc/settings.py`
- URL racine: `electruc/urls.py`
- Métier: `portal/models.py`
- Admin métier: `portal/admin.py`
- Vues: `portal/views.py`
- Formulaires: `portal/forms.py`
- Templates: `templates/` et `portal/templates/`

## 3) Fonctionnalités implémentées (état actuel)
### Pages publiques
- Accueil, Services, FAQ, Contact

### Espace client (auth requis)
- Dashboard (graphique consommation 5 mois)
- Profil
- Contrat (PDF)
- Factures (liste + PDF)
- Relevés
- Demandes support + pièces jointes
- Domiciliation (formulaire PDF modifiable + upload document)

### Flux d'inscription par invitation
- Admin génère une invitation par point de fourniture (EAN)
- Courrier d'invitation imprimable avec:
  - EAN
  - code d'activation unique
  - URL d'inscription
- Inscription client via `/inscription/`
- Compte créé inactif (`is_active=False`)
- Activation via email (`/activation/<uidb64>/<token>/`)
- Après activation: invitation marquée utilisée

### Résilience email activation
- Si l'email d'activation n'arrive pas, l'utilisateur peut relancer la même inscription (même EAN + code + email)
- Pas besoin de régénérer une invitation tant que le compte n'est pas activé

### Import atelier (CSV)
- Import CSV vers `MeterPoint` (pas de création de user)
- Génération automatique d'historique fictif 5 mois (`MeterPointHistory`)
- Import robuste encodage: UTF-8 / UTF-8 BOM / CP1252 / Latin-1

### Atelier / réinitialisation
Depuis admin `MeterPoint`:
- Import CSV manuel
- Import CSV par défaut (env `TRAINING_CUSTOMERS_CSV_PATH`)
- Réinitialiser comptes en ligne
- Réinitialiser atelier complet
- Génération invitations PDF multi-pages (multi-sélection)

## 4) Modèle de données (résumé)
### Noyau inscription
- `MeterPoint`: point de fourniture (EAN unique, immuable)
- `Invitation`: invitation liée à `MeterPoint`
  - secret hashé
  - expiration
  - used_by / used_at
  - anti brute force (failed attempts + lock)

### Client
- `Contract`: contrat utilisateur
  - type de tarification: `fixed` ou `variable`
  - abonnement fixe (`standing_charge_eur`)
  - prix fixe au kWh (`fixed_unit_price_eur_kwh`)
- `Invoice`: facture
  - période
  - consommation (kWh)
  - prix unitaire appliqué
  - abonnement appliqué
  - montant total
- `MeterReading`: relevés utilisateur
- `CustomerProfile`: données administratives client

### Historique avant inscription
- `MeterPointHistory`:
  - période mensuelle
  - consommation
  - montant fictif
- Lors de l'inscription: matérialisation en `Invoice` + `MeterReading`

## 5) Logique de facturation (simple et réaliste)
Dans `Contract`:
- Offre fixe: prix kWh constant (`fixed_unit_price_eur_kwh`)
- Offre variable: prix kWh mensuel (table simplifiée dans le code)

Montant facture:
- total = abonnement + (consommation_kwh * prix_unitaire)

Le PDF facture affiche ces composants.

## 6) Variables d'environnement clés
### Commun
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `SITE_URL`
- `DEFAULT_FROM_EMAIL`

### Email SMTP
- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `EMAIL_TIMEOUT`

### Atelier
- `TRAINING_CUSTOMERS_CSV_PATH`

### Prod hardening
- `SECURE_PROXY_SSL_HEADER`
- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`

### DB SQLite en conteneur
- `SQLITE_PATH=/app/data/db.sqlite3`

## 7) Commandes utiles
### Local
```bash
python manage.py migrate
python manage.py runserver
python manage.py createsuperuser
python manage.py test
```

### Seed démo
```bash
python manage.py seed_demo
```

### Docker prod-like local
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

### Logs
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f web
```

## 8) Points sensibles connus
- Sans `reportlab`, fallback PDF minimal utilisé (document lisible, moins riche)
- Livraison email: SPF/DKIM/DMARC requis pour éviter spam
- En local, éviter de mélanger `localhost` et `127.0.0.1` pour limiter les soucis CSRF

## 9) Règles métier importantes
- Secret invitation jamais stocké en clair
- Code d'activation unique visible uniquement au moment de la génération courrier
- Invitation bloquée temporairement après trop d'échecs
- Suppression `CustomerProfile` en admin supprime aussi le user et ses données associées

## 10) Reprise rapide pour une IA / nouveau dev
1. Lire ce fichier + `docs/TASKS.md`
2. Vérifier env (`.env` ou `.env.prod`)
3. Lancer `python manage.py check` et `python manage.py test`
4. Tester manuellement flux critique:
   - admin: import meter points + génération invitations
   - client: inscription + activation + login
   - factures/contrat/relevés/dashboard

## 11) Backlog suggéré
- Externaliser l'index mensuel du tarif variable en modèle adminisable
- Ajouter tests unitaires dédiés au calcul tarifaire
- Internationalisation (fr/nl/en) plus systématique
- Normaliser les textes restants sans accents
