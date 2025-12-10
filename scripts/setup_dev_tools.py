#!/usr/bin/env python3
"""
Script de configuration des outils de développement
Installe et configure pre-commit hooks, outils de qualité, etc.
"""

import subprocess
import sys
import os
from pathlib import Path

class DevToolsInstaller:
    """Installateur d'outils de développement"""
    
    def __init__(self, project_path: str = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        
    def run_command(self, command: list, description: str) -> bool:
        """Exécuter une commande et afficher le résultat"""
        print(f"🔧 {description}...")
        try:
            result = subprocess.run(command, capture_output=True, text=True, cwd=self.project_path)
            if result.returncode == 0:
                print(f"✅ {description} terminé avec succès")
                return True
            else:
                print(f"❌ {description} a échoué: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Erreur lors de {description}: {e}")
            return False
            
    def install_dependencies(self) -> bool:
        """Installer les dépendances de développement"""
        return self.run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            "Installation des dépendances"
        )
        
    def setup_pre_commit(self) -> bool:
        """Configurer les hooks pre-commit"""
        # Installer pre-commit
        if not self.run_command(
            [sys.executable, "-m", "pip", "install", "pre-commit"],
            "Installation de pre-commit"
        ):
            return False
            
        # Installer les hooks
        return self.run_command(
            [sys.executable, "-m", "pre_commit", "install"],
            "Installation des hooks pre-commit"
        )
        
    def run_quality_checks(self) -> bool:
        """Exécuter les vérifications de qualité"""
        checks = [
            ([sys.executable, "-m", "black", "--check", "."], "Vérification formatage Black"),
            ([sys.executable, "-m", "flake8", "."], "Vérification linting Flake8"),
            ([sys.executable, "-m", "pytest", "tests/", "-v"], "Exécution des tests"),
        ]
        
        all_passed = True
        for command, description in checks:
            if not self.run_command(command, description):
                all_passed = False
                print(f"⚠️ {description} a échoué")
                
        return all_passed
        
    def setup_git_hooks(self) -> bool:
        """Configurer les hooks Git personnalisés"""
        hooks_dir = self.project_path / ".git" / "hooks"
        if not hooks_dir.exists():
            print("⚠️ Dossier .git/hooks non trouvé. Initialisation Git requise.")
            return False
            
        # Créer un hook pre-commit personnalisé
        pre_commit_hook = hooks_dir / "pre-commit"
        hook_content = """#!/bin/sh
# Hook pre-commit personnalisé
echo "🔍 Exécution des vérifications de qualité..."

# Exécuter black
python -m black --check .
if [ $? -ne 0 ]; then
    echo "❌ Formatage Black échoué. Exécutez: black ."
    exit 1
fi

# Exécuter flake8
python -m flake8 .
if [ $? -ne 0 ]; then
    echo "❌ Linting Flake8 échoué."
    exit 1
fi

# Exécuter les tests
python -m pytest tests/ --tb=short
if [ $? -ne 0 ]; then
    echo "❌ Tests échoués."
    exit 1
fi

echo "✅ Toutes les vérifications ont réussi!"
"""
        
        try:
            with open(pre_commit_hook, 'w') as f:
                f.write(hook_content)
                
            # Rendre le hook exécutable
            os.chmod(pre_commit_hook, 0o755)
            print("✅ Hook Git pre-commit configuré")
            return True
        except Exception as e:
            print(f"❌ Erreur configuration hook Git: {e}")
            return False
            
    def create_dev_scripts(self) -> bool:
        """Créer des scripts de développement pratiques"""
        scripts_dir = self.project_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        
        # Script de linting
        lint_script = scripts_dir / "lint.sh"
        lint_content = """#!/bin/bash
echo "🔍 Linting du code..."
black .
flake8 .
echo "✅ Linting terminé"
"""
        
        # Script de test
        test_script = scripts_dir / "test.sh"
        test_content = """#!/bin/bash
echo "🧪 Exécution des tests..."
python -m pytest tests/ -v --cov=lib --cov-report=html
echo "✅ Tests terminés"
"""
        
        # Script de sécurité
        security_script = scripts_dir / "security.sh"
        security_content = """#!/bin/bash
echo "🔒 Scan de sécurité..."
python scripts/security_scan.py
echo "✅ Scan sécurité terminé"
"""
        
        scripts = [
            (lint_script, lint_content),
            (test_script, test_content),
            (security_script, security_content)
        ]
        
        for script_path, content in scripts:
            try:
                with open(script_path, 'w') as f:
                    f.write(content)
                os.chmod(script_path, 0o755)
                print(f"✅ Script créé: {script_path.name}")
            except Exception as e:
                print(f"❌ Erreur création {script_path.name}: {e}")
                return False
                
        return True
        
    def setup_development_environment(self) -> bool:
        """Configurer l'environnement de développement complet"""
        print("🚀 Configuration de l'environnement de développement...")
        print("=" * 60)
        
        steps = [
            ("Installation des dépendances", self.install_dependencies),
            ("Configuration pre-commit", self.setup_pre_commit),
            ("Création scripts de développement", self.create_dev_scripts),
            ("Configuration hooks Git", self.setup_git_hooks),
            ("Vérifications qualité", self.run_quality_checks),
        ]
        
        all_success = True
        for step_name, step_func in steps:
            print(f"\n📋 {step_name}...")
            if not step_func():
                all_success = False
                print(f"❌ {step_name} a échoué")
            else:
                print(f"✅ {step_name} réussi")
                
        print("\n" + "=" * 60)
        if all_success:
            print("🎉 Environnement de développement configuré avec succès!")
            print("\n📋 Prochaines étapes:")
            print("  1. Exécutez 'python scripts/security_scan.py' pour vérifier la sécurité")
            print("  2. Exécutez 'python -m pytest tests/' pour lancer les tests")
            print("  3. Utilisez 'black .' pour formater le code")
            print("  4. Les hooks pre-commit s'exécuteront automatiquement à chaque commit")
        else:
            print("⚠️ Certaines configurations ont échoué. Vérifiez les erreurs ci-dessus.")
            
        return all_success

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Configuration des outils de développement")
    parser.add_argument("--path", help="Chemin du projet", default=".")
    parser.add_argument("--lint-only", action="store_true", help="Exécuter uniquement le linting")
    parser.add_argument("--test-only", action="store_true", help="Exécuter uniquement les tests")
    parser.add_argument("--security-only", action="store_true", help="Exécuter uniquement le scan de sécurité")
    
    args = parser.parse_args()
    
    installer = DevToolsInstaller(args.path)
    
    if args.lint_only:
        installer.run_command([sys.executable, "-m", "black", "."], "Formatage Black")
        installer.run_command([sys.executable, "-m", "flake8", "."], "Linting Flake8")
    elif args.test_only:
        installer.run_command([sys.executable, "-m", "pytest", "tests/", "-v"], "Tests")
    elif args.security_only:
        installer.run_command([sys.executable, "scripts/security_scan.py"], "Scan sécurité")
    else:
        installer.setup_development_environment()

if __name__ == "__main__":
    main()
