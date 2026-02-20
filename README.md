# Electruc Portal

Electruc Portal est une application web pédagogique Django simulant un portail client de fournisseur d'énergie (Belgique).

## Reprise rapide
Pour une reprise de développement (humaine ou IA), lire en priorité:
- `docs/HANDOVER.md`
- `docs/TASKS.md`
- `docs/SPEC.md`

## Démarrage local
```bash
python manage.py migrate
python manage.py runserver
```

## Tests
```bash
python manage.py test
```

## Déploiement Docker (VPS + cloudflared)
Fichiers:
- `docker-compose.prod.yml`
- `.env.prod.example`

### 1) Préparer les variables
```bash
cp .env.prod.example .env.prod
```

Renseigner au minimum:
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `SITE_URL`

### 2) Lancer
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

### 3) Notes cloudflared
- Garder `SECURE_PROXY_SSL_HEADER=1` si `X-Forwarded-Proto` est transmis
- En cas de boucle HTTPS:
  - `SECURE_PROXY_SSL_HEADER=0`
  - `SECURE_SSL_REDIRECT=0`

## Licence
Voir `LICENSE`.
