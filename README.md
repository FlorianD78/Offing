# Offing

*Same wind. Your race.*

Jeu de course au large en 3D dans le navigateur. Le Défi du jour a un classement en ligne : le chrono est vérifié par rejeu côté serveur.

- **Front** : `public/index.html`, un seul fichier (Three.js r128 via CDN), servi en statique par Vercel.
- **API** : fonctions Node dans `api/`. Elles chargent le moteur du jeu (le même `index.html`) dans une sandbox `vm` et rejouent le journal d'ordres du joueur.
- **Base** : Supabase Postgres (tables `players` et `bests`). Elle n'est accessible que par l'API, avec la clé secrète ; RLS est activée sans policy.

## Flux d'un défi

0. Le tirage du jour (2 parcours × 2 classes) est calculé par la date de Paris, à l'identique côté jeu et côté serveur (`dailyPick`).
1. `GET /api/ghosts` charge les fantômes :
   - premier essai du jour : le top 10 (mis en cache 60 s par le CDN) ;
   - ensuite : les 10 meilleurs temps les plus proches du tien.
2. Le client court à pas fixe d'1 s, avec la graine du jour (date de Paris + parcours) et le même hasard pour tous. Il enregistre les ordres du joueur.
3. À l'arrivée, `POST /api/submit` envoie le journal (~15 à 70 Ko).
4. Le serveur vérifie le jeton du joueur, le jour, la version du moteur (`ENGINE_VER`) et un quota de 40 envois par jour et par défi.
5. Le serveur rejoue la course, compte le chrono rejoué et génère la trace du fantôme. Le chrono envoyé par le client est ignoré.
6. La fonction SQL `submit_best` garde le meilleur temps par joueur, jour, parcours et classe. La réponse contient le rang et le top 10.

## Mise en place (≈ 15 min)

### 1. Supabase

1. Crée un projet sur supabase.com (région Europe, par exemple Paris `eu-west-3`).
2. Ouvre **SQL Editor > New query**, colle `supabase/migrations/0001_init.sql`, puis **Run**.
3. Dans **Project Settings > API Keys**, note l'**URL du projet** et une **Secret key** (`sb_secret_…`). Sur un projet ancien, la clé `service_role` fonctionne aussi.

### 2. GitHub

```bash
git init && git add . && git commit -m "Offing : défi du jour en ligne"
git branch -M main
git remote add origin git@github.com:<toi>/offing.git
git push -u origin main
```

### 3. Vercel (déploiement synchronisé avec GitHub)

1. **Add New > Project**, puis importe le dépôt GitHub. Framework : **Other**. Garde le reste par défaut, `vercel.json` s'en charge.
2. Dans **Settings > Environment Variables** (Production et Preview), ajoute :

   | Variable | Valeur |
   |---|---|
   | `SUPABASE_URL` | `https://xxxx.supabase.co` |
   | `SUPABASE_SECRET_KEY` | `sb_secret_…` |
   | `CRON_SECRET` | une chaîne aléatoire (`openssl rand -hex 32`) |
   | `IP_SALT` | une chaîne aléatoire |

3. Lance **Deploy**, puis **Redeploy** si tu as ajouté les variables après le premier déploiement.
4. Ensuite, chaque push sur `main` déploie en production et chaque pull request reçoit une URL de preview. La CI GitHub (`npm test`) tourne en parallèle.

Pour vérifier : `https://offing.vercel.app/api/health` (ou le domaine attribué par Vercel) doit renvoyer `{"ok":true,"day":"…","engine":2,…}`.

## En local

```bash
npm install
npm test          # rejeu de référence + API sur base en mémoire
npm run local     # http://localhost:3000 (base en mémoire, ou ta base si SUPABASE_URL est défini)
```

## Faire évoluer la physique ou la météo

Le chrono n'est valable que si le client et le serveur ont le même moteur. Après toute modification qui change la trajectoire d'un bateau (polaires, météo, manœuvres, pas de temps) :

1. Incrémente `ENGINE_VER` dans `public/index.html`. Le serveur refuse alors les journaux de l'ancienne version et les clients ouverts sont invités à recharger la page.
2. Régénère `scripts/fixtures/daily-ref.json` (un journal du nouveau moteur avec son `expectT`). Tant que ce n'est pas fait, `check-engine` ignore le test.

Évite de déployer un tel changement en pleine journée : les chronos déjà enregistrés ce jour-là viennent de l'ancien moteur.

## Limites des offres gratuites

- **Vercel Hobby** :
  - usage personnel et non commercial uniquement ;
  - 4 h de CPU actif par mois : un rejeu coûte 0,5 à 2,5 s, donc environ 6 000 à 25 000 envois par mois ;
  - 1 cron par jour, qui suffit ici.
- **Supabase Free** :
  - 500 Mo de base et 5 Go de sortie par mois. Un appel aux fantômes pèse jusqu'à ~300 Ko ; le top 10 est mis en cache par le CDN.
  - Le projet se met en pause après 7 jours sans activité. Le cron quotidien `/api/cron` le garde actif ; il efface aussi les journaux au-delà de 14 jours et les chronos au-delà de `KEEP_DAYS` (30 jours par défaut).

## Ce que le rejeu garantit (et ce qu'il ne garantit pas)

- **Garanti** : la course est physiquement possible avec la météo du jour, sans téléportation, sans faux chrono et sans manœuvre instantanée. La trace du fantôme vient du serveur, pas du client.
- **Non garanti** : un joueur peut calculer ses ordres avec un programme (un routeur externe, par exemple). Pour aller plus loin, il faudrait des contrôles statistiques ou une limite de cadence des ordres.

## Endpoints

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | état, jour du défi, version du moteur, tirage du jour |
| POST | `/api/register` | `{name}` crée un profil et renvoie `{id, token}` ; `{id, token, name}` renomme |
| GET | `/api/ghosts?course&cls&player[&mode=top]` | fantômes du jour (traces allégées à 1 point toutes les 2 min) ; `mode=top` : le top 10, pour l'analyse de course |
| POST | `/api/me` | `{id, token}` : restaure un profil avec le code de récupération |
| POST | `/api/submit` | `{id, token, log}` : rejeu, enregistrement, rang |
| GET | `/api/leaderboard?course&cls&player` | top 50 du jour et ta place |
| GET | `/api/cron` | ménage quotidien (appelé par Vercel avec `CRON_SECRET`) |
