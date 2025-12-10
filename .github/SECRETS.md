# Configuration GitHub Secrets

Ce document explique comment configurer les secrets GitHub pour le pipeline CI/CD.

## ⚠️ Notes importantes

### Warnings de linting normaux
Vous pouvez voir des warnings de linting comme :
```
Context access might be invalid: DOCKER_USERNAME
Context access might be invalid: DOCKER_PASSWORD
```

**Ces warnings sont NORMAUX et attendus :**
- ✅ Le pipeline fonctionnera correctement
- ✅ Les warnings disparaîtront après configuration des secrets
- ✅ Aucune action requise pour le développement

## Secrets GitHub requis

### Secrets optionnels (Docker)
Ces secrets sont **optionnels** - le pipeline fonctionnera sans eux mais ne poussera pas les images Docker.

#### DOCKER_USERNAME
- **Description**: Nom d'utilisateur Docker Hub
- **Valeur**: Votre nom d'utilisateur Docker Hub
- **Requis**: Optionnel

#### DOCKER_PASSWORD
- **Description**: Mot de passe ou token d'accès Docker Hub
- **Valeur**: Token d'accès Docker Hub (recommandé) ou mot de passe
- **Requis**: Optionnel

## Configuration des secrets

### Étape 1: Accéder aux secrets du repository
1. Aller sur votre repository GitHub
2. Cliquer sur **Settings** (onglet)
3. Dans le menu gauche, cliquer sur **Secrets and variables** → **Actions**
4. Cliquer sur **New repository secret**

### Étape 2: Créer le secret Docker Hub
1. **Name**: `DOCKER_USERNAME`
2. **Secret**: Votre nom d'utilisateur Docker Hub
3. Cliquer sur **Add secret**

### Étape 3: Créer le secret de mot de passe
1. **Name**: `DOCKER_PASSWORD`
2. **Secret**: Votre token d'accès Docker Hub
3. Cliquer sur **Add secret**

## Obtenir un token d'accès Docker Hub

### Option recommandée: Token d'accès
1. Se connecter à [Docker Hub](https://hub.docker.com/)
2. Aller dans **Account Settings** → **Security**
3. Cliquer sur **New Access Token**
4. Donner un nom (ex: `github-actions`)
5. Cocher les permissions nécessaires:
   - `read` (lire les repositories)
   - `write` (pousser les images)
6. Cliquer sur **Generate**
7. Copier le token (il ne sera plus visible)

### Alternative: Mot de passe
Utilisez votre mot de passe Docker Hub directement (moins sécurisé).

## Fonctionnement du pipeline

### Avec secrets configurés
- ✅ Login Docker Hub automatique
- ✅ Build et push des images
- ✅ Tags avec version et SHA

### Sans secrets configurés
- ⚠️ Étape login Docker Hub skippée
- ✅ Build local des images
- ❌ Pas de push vers Docker Hub
- ✅ Tags locaux seulement

## Variables d'environnement supplémentaires

Pour un déploiement complet, vous pouvez ajouter:

### Production (optionnel)
- `PRODUCTION_HOST`: URL du serveur de production
- `PRODUCTION_USER`: Utilisateur SSH
- `PRODUCTION_KEY`: Clé SSH privée
- `PRODUCTION_PORT`: Port SSH (défaut: 22)

### Monitoring (optionnel)
- `SLACK_WEBHOOK`: URL webhook pour notifications Slack
- `SENTRY_DSN`: URL pour error tracking Sentry

## Sécurité

### Bonnes pratiques
- ✅ Utiliser des tokens d'accès plutôt que les mots de passe
- ✅ Limiter les permissions des tokens
- ✅ Faire tourner les tokens régulièrement
- ✅ Ne jamais partager les secrets

### Révocation
En cas de compromission:
1. Révoquer le token dans Docker Hub
2. Supprimer le secret GitHub
3. Créer un nouveau token
4. Mettre à jour le secret GitHub

## Dépannage

### Erreur: "Unable to access repository"
- Vérifier que le token a les permissions `write`
- Vérifier que le nom d'utilisateur est correct

### Erreur: "denied: requested access to the resource is denied"
- Vérifier que le repository Docker existe
- Vérifier l'orthographe du nom d'utilisateur

### Erreur: "no basic auth credentials"
- Vérifier que DOCKER_USERNAME et DOCKER_PASSWORD sont corrects
- Vérifier que les secrets sont bien configurés

## Test de configuration

Pour vérifier que tout fonctionne:
1. Faire un push sur la branche `main`
2. Vérifier le workflow dans **Actions** → **Workflows**
3. Consulter les logs de l'étape "Build Docker image"

---

## 📝 Résumé

Les secrets Docker sont **optionnels** mais recommandés pour un déploiement complet en production. Le pipeline est conçu pour fonctionner avec ou sans ces secrets.
