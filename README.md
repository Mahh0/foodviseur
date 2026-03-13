# 🥗 FoodViseur

Application web progressive (PWA) de suivi nutritionnel auto-hébergée.
Remplace Foodvisor par une solution sans tracking, optimisée mobile, livrée en une seule image Docker.

## Fonctionnalités

- 📊 **Dashboard** — cercles de progression animés (Calories, Protéines, Glucides, Lipides)
- 🔍 **Recherche hybride** — CIQUAL 2025 en priorité (3484 aliments français), complétée par Open Food Facts
- 📷 **Scanner** — code-barres via caméra avec relance automatique après chaque ajout
- 📋 **Journal** — 4 repas (Petit-déjeuner, Déjeuner, Dîner, En-cas), navigation par jour
- ⭐ **Aliments récents** — les 8 derniers aliments ajoutés, avec dernière quantité pré-remplie
- ✏️ **Aliments personnalisés** — saisis manuellement, sauvegardés et réutilisables
- ⚙️ **Réglages** — objectifs quotidiens personnalisables
- 📱 **PWA installable** — fonctionne hors-ligne, ajout à l'écran d'accueil

## Démarrage rapide

### 1. Builder l'image

```bash
git clone https://github.com/Mahh0/foodviseur.git
cd foodviseur
docker build -t foodviseur:latest .
```

Le build ne nécessite aucun argument. L'image est générique et portable.

### 2. Configurer et lancer

Modifier `PUID`, `PGID` et `OFF_USER_AGENT` dans le `docker-compose.yml`, puis :

```bash
docker compose up -d
```

> ⚠️ **Premier démarrage : 2-5 minutes.** Alembic télécharge et importe automatiquement la base CIQUAL 2025 (~68 Mo). Les redémarrages suivants sont instantanés.

L'app est disponible sur **http://localhost:8000**

## Gestion des permissions (PUID / PGID)

FoodViseur utilise le **pattern PUID/PGID** popularisé par [linuxserver.io](https://docs.linuxserver.io/general/understanding-puid-and-pgid/).

### Fonctionnement

Le conteneur démarre en `root`, puis `start.sh` :
1. Crée dynamiquement un utilisateur `appuser` avec l'UID/GID demandés
2. Applique les permissions sur le volume `/data`
3. Drop les privilèges via `su-exec` avant de lancer l'application

Le code dans `/app` reste en lecture seule (appartient à `root`). Seul `/data` (base SQLite + cache CIQUAL) est accessible en écriture par l'utilisateur applicatif.

### Configuration

Dans `docker-compose.yml`, modifier :

```yaml
environment:
  - PUID=1000   # votre UID
  - PGID=1000   # votre GID
```

Pour connaître votre UID:GID :
```bash
id
# uid=1000(monuser) gid=1000(monuser) ...
```

### Dans Portainer

Dans la section **Environment variables** de la stack, ajouter :

| Variable | Valeur |
|----------|--------|
| `PUID` | `1000` *(votre UID)* |
| `PGID` | `1000` *(votre GID)* |
| `OFF_USER_AGENT` | `FoodViseur/1.0 (votre@email.com)` |

## Déploiement avec Portainer

### Depuis une image buildée localement

```bash
# Sur le serveur
git clone https://github.com/Mahh0/foodviseur.git
cd foodviseur
docker build -t foodviseur:latest .
```

Puis dans Portainer → **Stacks** → **Add stack** → **Web editor**, coller le `docker-compose.yml` en remplaçant la section `build:` par `image: foodviseur:latest`.

### Depuis Git (build automatique)

1. Portainer → **Stacks** → **Add stack** → **Repository**
2. **Repository URL** : `https://github.com/Mahh0/foodviseur`
3. **Compose path** : `docker-compose.yml`
4. Ajouter `PUID`, `PGID`, `OFF_USER_AGENT` dans les variables d'environnement
5. **Deploy the stack**

### Mettre à jour

```bash
cd foodviseur && git pull
docker build -t foodviseur:latest .
```
Puis dans Portainer : stack foodviseur → **Redeploy**.

## Sources de données alimentaires

### CIQUAL 2025 (prioritaire)

3484 aliments français importés au premier démarrage depuis [data.gouv.fr](https://entrepot.recherche.data.gouv.fr/dataset.xhtml?persistentId=doi:10.57745/RDMHWY). Les résultats dont le nom commence par le terme recherché remontent en tête.

> Anses. 2025. Table de composition nutritionnelle des aliments Ciqual — Licence Ouverte

### Open Food Facts (complémentaire)

Utilisé si CIQUAL renvoie moins de 3 résultats, ou manuellement via "Voir aussi sur Open Food Facts".

> Open Food Facts — Licence ODbL

### Logique de recherche

```
Requête → CIQUAL (début de mot en priorité)
    ≥ 3 résultats  → affiche CIQUAL
    < 3 résultats  → complète avec OFF automatiquement
    Bouton OFF     → force une recherche OFF complète
```

### Forcer un reimport CIQUAL

```bash
docker exec foodviseur sqlite3 /data/foodviseur.db \
  "DELETE FROM alembic_version WHERE version_num='0003';"
docker exec foodviseur sqlite3 /data/foodviseur.db \
  "DROP TABLE IF EXISTS ciqual_foods;"
docker exec foodviseur sh -c \
  "rm -f /data/ciqual_alim.xml /data/ciqual_const.xml /data/ciqual_compo.xml"
docker compose restart
```

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `PUID` | `1000` | UID de l'utilisateur applicatif |
| `PGID` | `1000` | GID de l'utilisateur applicatif |
| `DATABASE_URL` | `sqlite:////data/foodviseur.db` | Chemin de la base SQLite |
| `LOG_LEVEL` | `info` | Niveau de log (debug, info, warning, error) |
| `OFF_USER_AGENT` | `FoodViseur/1.0 (self-hosted)` | User-Agent Open Food Facts |
| `RECENT_FOODS_LIMIT` | `8` | Nombre d'aliments récents affichés |

## Migrations Alembic

Appliquées automatiquement au démarrage.

| Migration | Description |
|-----------|-------------|
| `0001_initial` | Schéma initial |
| `0002_meal_type_and_100g` | Ajout meal_type et colonnes /100g |
| `0003_ciqual_seed` | Import CIQUAL 2025 |
| `0004_food_cache_is_custom` | Aliments personnalisés |

Développement local :
```bash
pip install -r requirements.txt
DATABASE_URL=sqlite:////tmp/fv.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/fv.db uvicorn app.main:app --reload
```

## Traefik + BasicAuth

1. Décommenter les labels Traefik dans `docker-compose.yml`
2. Générer les credentials :
   ```bash
   htpasswd -nb user motdepasse
   # Doubler les $ dans les labels : $ → $$
   ```
3. Adapter le hostname, supprimer le mapping `ports:`

## Ajouter à l'écran d'accueil

**Android (Chrome) :** Menu ⋮ → "Ajouter à l'écran d'accueil"

**iOS (Safari) :** Bouton partage ↑ → "Sur l'écran d'accueil"

## API

Swagger disponible sur `/api/docs`.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/PUT | `/api/goals/` | Objectifs nutritionnels |
| GET | `/api/meals/today` | Résumé du jour |
| GET | `/api/meals/summary/{date}` | Résumé par date |
| POST | `/api/meals/` | Ajouter un repas |
| PATCH | `/api/meals/{id}` | Modifier un repas |
| DELETE | `/api/meals/{id}` | Supprimer un repas |
| GET | `/api/food/search?q=...` | Recherche hybride |
| GET | `/api/food/search?q=...&source=off` | Forcer OFF |
| GET | `/api/food/recent` | Aliments récents |
| GET/POST | `/api/food/custom` | Aliments personnalisés |
| DELETE | `/api/food/custom/{id}` | Supprimer un aliment perso |
| GET | `/api/food/barcode/{code}` | Recherche par code-barres |
| GET | `/api/food/ciqual-status` | Statut base CIQUAL |

## Architecture

```
Navigateur ←→ FastAPI (Uvicorn :8000)
               ├── /api/*     → Routers Python
               └── /static/*  → Alpine.js SPA

SQLite (/data/foodviseur.db)
├── goals         → Objectifs quotidiens
├── food_cache    → Cache OFF + aliments personnalisés
├── meal_entries  → Journal des repas
└── ciqual_foods  → CIQUAL 2025 (3484 aliments)

/data/              ← volume Docker persistant (chown PUID:PGID au démarrage)
├── foodviseur.db
├── ciqual_alim.xml
├── ciqual_compo.xml
└── ciqual_const.xml
```

---

*FoodViseur — Auto-hébergé, sans tracking, respect de votre vie privée.*
