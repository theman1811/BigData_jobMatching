#!/usr/bin/env python3
"""
Configuration sécurisée des credentials LinkedIn pour le scraper
"""

import os
import getpass
from pathlib import Path

def setup_linkedin_credentials():
    """Configure les credentials LinkedIn de manière sécurisée"""

    print("🔐 Configuration des credentials LinkedIn")
    print("=" * 50)
    print("⚠️  ATTENTION: Ce fichier contiendra des informations sensibles!")
    print("   - Il sera créé dans kafka/producers/.env.linkedin")
    print("   - Ce fichier est déjà ignoré par Git (.gitignore)")
    print("   - NE PARTAGEZ JAMAIS ce fichier!")
    print()

    # Chemin du fichier de configuration
    config_file = Path("kafka/producers/.env.linkedin")

    # Vérifier si le fichier existe déjà
    if config_file.exists():
        print(f"⚠️  Le fichier {config_file} existe déjà.")
        response = input("Voulez-vous le remplacer ? (o/N): ").strip().lower()
        if response not in ['o', 'oui', 'yes', 'y']:
            print("❌ Configuration annulée.")
            return False

    # Demander les credentials
    print("\n📧 Entrez vos credentials LinkedIn:")
    email = input("Email LinkedIn: ").strip()
    if not email:
        print("❌ Email requis.")
        return False

    password = getpass.getpass("Mot de passe LinkedIn: ").strip()
    if not password:
        print("❌ Mot de passe requis.")
        return False

    # Demander la configuration Selenium
    print("\n🤖 Configuration Selenium:")
    headless_input = input("Mode headless (recommandé pour serveur) [true]: ").strip().lower()
    headless = headless_input in ['true', 'oui', 'yes', 'y', ''] or headless_input == 'true'

    # Demander l'enrichissement des détails
    print("\n🔍 Enrichissement des détails:")
    print("   Cela permet d'obtenir plus d'informations par offre,")
    print("   mais ralentit considérablement le scraping.")
    enrich_input = input("Activer l'enrichissement ? (false recommandé) [false]: ").strip().lower()
    enrich_details = enrich_input in ['true', 'oui', 'yes', 'y']

    # Demander le nombre maximum d'offres
    max_jobs_input = input("Nombre maximum d'offres par exécution [50]: ").strip()
    try:
        max_jobs = int(max_jobs_input) if max_jobs_input else 50
        max_jobs = max(1, min(max_jobs, 200))  # Limiter entre 1 et 200
    except ValueError:
        max_jobs = 50

    # Créer le contenu du fichier
    config_content = f"""# ============================================
# LinkedIn Scraper - Configuration
# ============================================
# ATTENTION: Ce fichier contient des credentials sensibles !
# N'ajoutez JAMAIS ce fichier au git !
# Créé le {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Credentials LinkedIn
LINKEDIN_EMAIL={email}
LINKEDIN_PASSWORD={password}

# Configuration Selenium
SELENIUM_HEADLESS={str(headless).lower()}

# Enrichissement des détails (lent mais plus de données)
LINKEDIN_ENRICH_DETAILS={str(enrich_details).lower()}

# Limites de sécurité
LINKEDIN_MAX_JOBS_PER_RUN={max_jobs}
LINKEDIN_SCROLL_MAX_ATTEMPTS=10

# Délais anti-ban (secondes)
LINKEDIN_LOGIN_DELAY=3
LINKEDIN_SEARCH_DELAY=2
LINKEDIN_SCROLL_DELAY=2
"""

    try:
        # Créer le répertoire si nécessaire
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Écrire le fichier
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)

        print("\n✅ Configuration LinkedIn créée avec succès!")
        print(f"📁 Fichier: {config_file}")
        print("🔒 Permissions: 600 (lecture/écriture propriétaire uniquement)")
        # Définir les permissions restrictives
        try:
            config_file.chmod(0o600)
        except Exception as e:
            print(f"⚠️  Impossible de définir les permissions: {e}")

        print("\n📋 Résumé de la configuration:")
        print(f"   Email: {email}")
        print(f"   Mode headless: {headless}")
        print(f"   Enrichissement: {enrich_details}")
        print(f"   Max offres/run: {max_jobs}")

        print("\n🚀 Vous pouvez maintenant tester le scraper LinkedIn:")
        print("   python kafka/producers/run_scraper.py --scraper linkedin --max-pages 1")
        return True

    except Exception as e:
        print(f"❌ Erreur lors de la création du fichier: {e}")
        return False

def check_linkedin_credentials():
    """Vérifie si les credentials LinkedIn sont configurés"""

    config_file = Path("kafka/producers/.env.linkedin")

    if not config_file.exists():
        print("❌ Fichier de configuration LinkedIn non trouvé.")
        print(f"   Chemin attendu: {config_file}")
        return False

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Vérifier les variables essentielles
        has_email = 'LINKEDIN_EMAIL=' in content and not content.split('LINKEDIN_EMAIL=')[1].split('\n')[0].startswith('votre_email')
        has_password = 'LINKEDIN_PASSWORD=' in content and not content.split('LINKEDIN_PASSWORD=')[1].split('\n')[0].startswith('votre_mot_de_passe')

        if has_email and has_password:
            print("✅ Credentials LinkedIn configurés.")
            return True
        else:
            print("⚠️  Credentials LinkedIn incomplets ou par défaut.")
            return False

    except Exception as e:
        print(f"❌ Erreur lecture fichier: {e}")
        return False

def main():
    """Point d'entrée principal"""

    print("🇨🇮 Configuration LinkedIn Scraper")
    print("=" * 50)

    # Vérifier l'état actuel
    if check_linkedin_credentials():
        print("\n🔄 Credentials déjà configurés.")
        response = input("Voulez-vous les reconfigurer ? (o/N): ").strip().lower()
        if response not in ['o', 'oui', 'yes', 'y']:
            print("ℹ️  Configuration inchangée.")
            return

    # Lancer la configuration
    if setup_linkedin_credentials():
        print("\n🎉 Configuration terminée!")
        print("\n📚 Prochaines étapes:")
        print("   1. Testez le scraper: python kafka/producers/run_scraper.py --scraper linkedin --max-pages 1")
        print("   2. Vérifiez les logs pour les erreurs de connexion")
        print("   3. Ajustez les délais si nécessaire (risque de ban)")
    else:
        print("\n❌ Échec de la configuration.")

if __name__ == '__main__':
    main()
