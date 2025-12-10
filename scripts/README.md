# Scripts de développement et maintenance

Ce dossier contient des scripts pour automatiser les tâches de développement et de maintenance du projet.

## Scripts disponibles

### `setup_dev_tools.py`
Configure l'environnement de développement complet:
- Installation des dépendances
- Configuration des hooks pre-commit
- Création des scripts de développement
- Configuration des hooks Git
- Vérifications de qualité

```bash
python scripts/setup_dev_tools.py
```

Options:
- `--lint-only`: Exécuter uniquement le linting
- `--test-only`: Exécuter uniquement les tests
- `--security-only`: Exécuter uniquement le scan de sécurité

### `security_scan.py`
Effectue une analyse de sécurité complète du projet:
- Scan des vulnérabilités des dépendances (Safety)
- Analyse du code (Bandit)
- Détection de secrets
- Vérification des permissions des fichiers

```bash
python scripts/security_scan.py
```

Options:
- `--dependencies-only`: Scanner uniquement les dépendances
- `--code-only`: Scanner uniquement le code

## Utilisation

### Installation rapide
```bash
# Installer tous les outils de développement
python scripts/setup_dev_tools.py

# Exécuter un scan de sécurité
python scripts/security_scan.py
```

### Développement quotidien
```bash
# Formater le code
black .

# Vérifier le linting
flake8 .

# Lancer les tests
pytest tests/ -v

# Scan de sécurité
python scripts/security_scan.py
```

### Hooks Git automatiques
Les hooks pre-commit sont configurés pour exécuter automatiquement:
- Black (formattage)
- Flake8 (linting)
- Pytest (tests)

Ils s'exécutent à chaque `git commit`.

## Rapports

Les rapports sont générés dans les dossiers:
- `security_reports/` - Rapports de sécurité
- `htmlcov/` - Rapports de couverture de tests
- `monitoring/` - Métriques de performance

## Dépannage

### Problèmes courants
1. **Safety non trouvé**: Exécuter `pip install safety`
2. **Bandit non trouvé**: Exécuter `pip install bandit`
3. **Hooks non exécutables**: `chmod +x scripts/*.sh`
4. **Pre-commit non installé**: `pre-commit install`

### Réinitialisation
```bash
# Réinstaller tous les outils
python scripts/setup_dev_tools.py

# Réinitialiser les hooks
pre-commit uninstall
pre-commit install
```
