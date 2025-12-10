#!/usr/bin/env python3
"""
Script de scanning de sécurité pour les dépendances et le code
Intègre safety et bandit pour une analyse complète
"""

import subprocess
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

class SecurityScanner:
    """Scanner de sécurité complet pour le projet"""
    
    def __init__(self, project_path: str = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.reports_dir = self.project_path / "security_reports"
        self.reports_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def scan_dependencies(self) -> dict:
        """Scanner les dépendances avec safety"""
        print("🔍 Scanning des dépendances avec Safety...")
        
        try:
            # Exécuter safety check
            result = subprocess.run(
                ["safety", "check", "--json", "--output", "-"],
                capture_output=True,
                text=True,
                cwd=self.project_path
            )
            
            safety_report = {
                "timestamp": datetime.now().isoformat(),
                "scanner": "safety",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            # Parser le JSON si disponible
            if result.stdout and result.returncode == 0:
                try:
                    vulnerabilities = json.loads(result.stdout)
                    safety_report["vulnerabilities"] = vulnerabilities
                    safety_report["vulnerability_count"] = len(vulnerabilities)
                except json.JSONDecodeError:
                    safety_report["vulnerabilities"] = []
                    safety_report["vulnerability_count"] = 0
            else:
                safety_report["vulnerabilities"] = []
                safety_report["vulnerability_count"] = 0
                
            print(f"✅ Safety scan terminé - {safety_report['vulnerability_count']} vulnérabilités trouvées")
            return safety_report
            
        except FileNotFoundError:
            print("❌ Safety n'est pas installé. Installation en cours...")
            subprocess.run([sys.executable, "-m", "pip", "install", "safety"])
            return self.scan_dependencies()
        except Exception as e:
            print(f"❌ Erreur lors du scan Safety: {e}")
            return {"error": str(e)}
            
    def scan_code(self) -> dict:
        """Scanner le code avec bandit"""
        print("🔍 Scanning du code avec Bandit...")
        
        try:
            # Exécuter bandit
            result = subprocess.run(
                ["bandit", "-r", ".", "-f", "json", "-o", "-"],
                capture_output=True,
                text=True,
                cwd=self.project_path
            )
            
            bandit_report = {
                "timestamp": datetime.now().isoformat(),
                "scanner": "bandit",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            # Parser le JSON si disponible
            if result.stdout:
                try:
                    bandit_data = json.loads(result.stdout)
                    bandit_report["results"] = bandit_data.get("results", [])
                    bandit_report["high_confidence_issues"] = len([
                        r for r in bandit_data.get("results", []) 
                        if r.get("issue_confidence") == "HIGH"
                    ])
                    bandit_report["high_severity_issues"] = len([
                        r for r in bandit_data.get("results", []) 
                        if r.get("issue_severity") == "HIGH"
                    ])
                    bandit_report["total_issues"] = len(bandit_data.get("results", []))
                except json.JSONDecodeError:
                    bandit_report["results"] = []
                    bandit_report["total_issues"] = 0
            else:
                bandit_report["results"] = []
                bandit_report["total_issues"] = 0
                
            print(f"✅ Bandit scan terminé - {bandit_report['total_issues']} problèmes trouvés")
            return bandit_report
            
        except FileNotFoundError:
            print("❌ Bandit n'est pas installé. Installation en cours...")
            subprocess.run([sys.executable, "-m", "pip", "install", "bandit"])
            return self.scan_code()
        except Exception as e:
            print(f"❌ Erreur lors du scan Bandit: {e}")
            return {"error": str(e)}
            
    def check_secrets(self) -> dict:
        """Vérifier la présence de secrets dans le code"""
        print("🔍 Vérification des secrets...")
        
        secrets_report = {
            "timestamp": datetime.now().isoformat(),
            "scanner": "secrets_check",
            "secrets_found": []
        }
        
        # Patterns de secrets à rechercher
        secret_patterns = [
            ("password", r'password\s*=\s*["\'][^"\']+["\']'),
            ("api_key", r'api_key\s*=\s*["\'][^"\']+["\']'),
            ("token", r'token\s*=\s*["\'][^"\']+["\']'),
            ("secret", r'secret\s*=\s*["\'][^"\']+["\']'),
            ("private_key", r'-----BEGIN [A-Z]+ PRIVATE KEY-----'),
        ]
        
        import re
        
        for file_path in self.project_path.rglob("*.py"):
            if file_path.is_file() and not any(skip in str(file_path) for skip in ["venv", "__pycache__", ".git"]):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern_name, pattern in secret_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            secrets_report["secrets_found"].append({
                                "file": str(file_path.relative_to(self.project_path)),
                                "line": line_num,
                                "type": pattern_name,
                                "match": match.group()[:50] + "..." if len(match.group()) > 50 else match.group()
                            })
                except Exception as e:
                    continue
                    
        secrets_report["secrets_count"] = len(secrets_report["secrets_found"])
        print(f"✅ Vérification des secrets terminée - {secrets_report['secrets_count']} secrets potentiels trouvés")
        return secrets_report
        
    def check_file_permissions(self) -> dict:
        """Vérifier les permissions des fichiers sensibles"""
        print("🔍 Vérification des permissions des fichiers...")
        
        permissions_report = {
            "timestamp": datetime.now().isoformat(),
            "scanner": "file_permissions",
            "issues": []
        }
        
        # Fichiers sensibles à vérifier
        sensitive_files = [
            "requirements.txt",
            ".env",
            "config.py",
            "secrets.txt",
            "private_key.pem"
        ]
        
        for file_name in sensitive_files:
            file_path = self.project_path / file_name
            if file_path.exists():
                stat = file_path.stat()
                mode = oct(stat.st_mode)[-3:]
                
                # Vérifier si le fichier est lisible par tout le monde
                if mode[-2:] in ["44", "04", "40"]:
                    permissions_report["issues"].append({
                        "file": file_name,
                        "permissions": mode,
                        "issue": "Fichier lisible par tout le monde"
                    })
                    
        print(f"✅ Vérification des permissions terminée - {len(permissions_report['issues'])} problèmes trouvés")
        return permissions_report
        
    def generate_security_report(self, safety_report: dict, bandit_report: dict, 
                               secrets_report: dict, permissions_report: dict) -> str:
        """Générer un rapport de sécurité complet"""
        
        report = {
            "scan_timestamp": datetime.now().isoformat(),
            "project_path": str(self.project_path),
            "scanners": ["safety", "bandit", "secrets_check", "file_permissions"],
            "summary": {
                "total_vulnerabilities": safety_report.get("vulnerability_count", 0),
                "total_code_issues": bandit_report.get("total_issues", 0),
                "high_severity_issues": bandit_report.get("high_severity_issues", 0),
                "secrets_found": secrets_report.get("secrets_count", 0),
                "permission_issues": len(permissions_report.get("issues", [])),
                "overall_status": "SECURE"
            },
            "detailed_reports": {
                "dependencies": safety_report,
                "code_analysis": bandit_report,
                "secrets": secrets_report,
                "permissions": permissions_report
            },
            "recommendations": []
        }
        
        # Déterminer le statut de sécurité global
        if (report["summary"]["total_vulnerabilities"] > 0 or 
            report["summary"]["high_severity_issues"] > 0 or
            report["summary"]["secrets_found"] > 0):
            report["summary"]["overall_status"] = "VULNERABLE"
        elif (report["summary"]["total_code_issues"] > 5 or 
              report["summary"]["permission_issues"] > 0):
            report["summary"]["overall_status"] = "WARNING"
            
        # Générer des recommandations
        if report["summary"]["total_vulnerabilities"] > 0:
            report["recommendations"].append("Mettre à jour les dépendances vulnérables")
            
        if report["summary"]["high_severity_issues"] > 0:
            report["recommendations"].append("Corriger les problèmes de sécurité de haute sévérité")
            
        if report["summary"]["secrets_found"] > 0:
            report["recommendations"].append("Retirer les secrets du code et utiliser des variables d'environnement")
            
        if report["summary"]["permission_issues"] > 0:
            report["recommendations"].append("Corriger les permissions des fichiers sensibles")
            
        # Sauvegarder le rapport
        report_file = self.reports_dir / f"security_report_{self.timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        return str(report_file)
        
    def run_full_scan(self) -> str:
        """Exécuter tous les scans de sécurité"""
        print("🚀 Lancement du scan de sécurité complet...")
        print("=" * 60)
        
        # Exécuter tous les scans
        safety_report = self.scan_dependencies()
        bandit_report = self.scan_code()
        secrets_report = self.check_secrets()
        permissions_report = self.check_file_permissions()
        
        # Générer le rapport
        report_file = self.generate_security_report(
            safety_report, bandit_report, secrets_report, permissions_report
        )
        
        print("=" * 60)
        print("📊 RÉSUMÉ DU SCAN DE SÉCURITÉ")
        print("=" * 60)
        
        # Afficher le résumé
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
            
        summary = report["summary"]
        print(f"🔹 Vulnérabilités dépendances: {summary['total_vulnerabilities']}")
        print(f"🔹 Problèmes code: {summary['total_code_issues']} ({summary['high_severity_issues']} haute sévérité)")
        print(f"🔹 Secrets trouvés: {summary['secrets_found']}")
        print(f"🔹 Problèmes permissions: {summary['permission_issues']}")
        print(f"🔹 Statut global: {summary['overall_status']}")
        
        if report["recommendations"]:
            print("\n📋 RECOMMANDATIONS:")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. {rec}")
                
        print(f"\n📄 Rapport détaillé sauvegardé: {report_file}")
        
        return report_file

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Scanner de sécurité pour le projet Bot Démineur")
    parser.add_argument("--path", help="Chemin du projet à scanner", default=".")
    parser.add_argument("--dependencies-only", action="store_true", help="Scanner uniquement les dépendances")
    parser.add_argument("--code-only", action="store_true", help="Scanner uniquement le code")
    
    args = parser.parse_args()
    
    scanner = SecurityScanner(args.path)
    
    if args.dependencies_only:
        report = scanner.scan_dependencies()
        print(json.dumps(report, indent=2))
    elif args.code_only:
        report = scanner.scan_code()
        print(json.dumps(report, indent=2))
    else:
        report_file = scanner.run_full_scan()
        
        # Sortir avec le bon code de retour
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
            
        if report["summary"]["overall_status"] == "VULNERABLE":
            sys.exit(1)
        elif report["summary"]["overall_status"] == "WARNING":
            sys.exit(2)
        else:
            sys.exit(0)

if __name__ == "__main__":
    main()
