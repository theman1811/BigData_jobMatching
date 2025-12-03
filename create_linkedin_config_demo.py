#!/usr/bin/env python3
"""
Création d'un fichier de configuration LinkedIn d'exemple
"""

from pathlib import Path
from datetime import datetime

def create_linkedin_config_demo():
    """Crée un fichier de configuration LinkedIn d'exemple"""

    print("🔗 Création d'une configuration LinkedIn d'exemple")
    print("=" * 50)

    config_file = Path("kafka/producers/.env.linkedin")

    # Vérifier si le fichier existe
    if config_file.exists():
        print(f"⚠️  Le fichier {config_file} existe déjà.")
        print("   Il sera remplacé par la version d'exemple.")
        print()

    # Contenu d'exemple avec des credentials fictives
    config_content = f"""# ============================================
# LinkedIn Scraper - Configuration d'exemple
# ============================================
# ATTENTION: Ce fichier contient des credentials sensibles !
# N'ajoutez JAMAIS ce fichier au git !
# Créé le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
#
# ⚠️  À MODIFIER: Remplacez les valeurs ci-dessous par vos vraies credentials
#     Email et mot de passe LinkedIn

# Credentials LinkedIn (À CONFIGURER)
LINKEDIN_EMAIL=votre_email_linkedin@exemple.com
LINKEDIN_PASSWORD=votre_mot_de_passe_linkedin

# Configuration Selenium
SELENIUM_HEADLESS=true

# Enrichissement des détails (lent mais plus de données)
LINKEDIN_ENRICH_DETAILS=false

# Limites de sécurité
LINKEDIN_MAX_JOBS_PER_RUN=10
LINKEDIN_SCROLL_MAX_ATTEMPTS=5

# Délais anti-ban (secondes)
LINKEDIN_LOGIN_DELAY=3
LINKEDIN_SEARCH_DELAY=2
LINKEDIN_SCROLL_DELAY=2
"""

    try:
        # Créer le répertoire
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Écrire le fichier
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)

        print("✅ Fichier de configuration créé:")
        print(f"   📁 {config_file}")
        print()
        print("📝 À faire maintenant:")
        print("   1. Ouvrez le fichier avec un éditeur:")
        print(f"      nano {config_file}")
        print("   2. Remplacez les valeurs fictives par vos vraies credentials LinkedIn")
        print("   3. Sauvegardez le fichier")
        print()
        print("🔐 Sécurité:")
        print("   - Ce fichier est ignoré par Git (.gitignore)")
        print("   - Il ne sera jamais commité")
        print("   - Gardez-le confidentiel")
        print()
        print("🚀 Test après configuration:")
        print("   python kafka/producers/run_scraper.py --scraper linkedin --max-pages 1")
        print()
        print("⚠️  Rappels importants:")
        print("   • Utilisez un compte LinkedIn secondaire si possible")
        print("   • LinkedIn peut détecter l'automatisation")
        print("   • Commencez par des tests limités (max-pages=1)")
        print("   • Respectez les délais pour éviter les blocages")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la création: {e}")
        return False

if __name__ == '__main__':
    create_linkedin_config_demo()
