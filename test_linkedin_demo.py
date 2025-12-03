#!/usr/bin/env python3
"""
Test de démonstration du scraper LinkedIn
Montre comment fonctionne le scraper avec des credentials fictives
"""

import os
import sys
from pathlib import Path

def test_linkedin_demo():
    """Test de démonstration LinkedIn"""

    print("🔗 Test de démonstration LinkedIn Scraper")
    print("=" * 50)
    print("⚠️  ATTENTION: Test avec credentials fictives")
    print("   Ce test montre le fonctionnement mais ne scrapera pas réellement")
    print()

    # Vérifier si le fichier de configuration existe
    config_file = Path("kafka/producers/.env.linkedin")
    if config_file.exists():
        print("✅ Fichier de configuration trouvé")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Afficher les variables configurées (sans les valeurs sensibles)
            lines = content.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    key = line.split('=')[0]
                    if 'PASSWORD' in key:
                        print(f"   🔒 {key}=[CONFIGURÉ]")
                    elif 'EMAIL' in key:
                        value = line.split('=')[1] if '=' in line else ''
                        if value and not value.startswith('votre_email'):
                            print(f"   📧 {key}=[EMAIL_CONFIGURÉ]")
                        else:
                            print(f"   📧 {key}=[NON_CONFIGURÉ]")
                    else:
                        value = line.split('=')[1] if '=' in line else ''
                        print(f"   ⚙️  {key}={value}")

        except Exception as e:
            print(f"   ❌ Erreur lecture config: {e}")
    else:
        print("❌ Fichier de configuration non trouvé")
        print(f"   Chemin: {config_file}")
        print("   Lancez: python setup_linkedin_credentials.py")

    print()

    # Vérifier les variables d'environnement
    print("🌍 Variables d'environnement:")
    linkedin_vars = [
        'LINKEDIN_EMAIL',
        'LINKEDIN_PASSWORD',
        'SELENIUM_HEADLESS',
        'LINKEDIN_ENRICH_DETAILS',
        'LINKEDIN_MAX_JOBS_PER_RUN'
    ]

    for var in linkedin_vars:
        value = os.getenv(var)
        if value:
            if 'PASSWORD' in var:
                print(f"   ✅ {var}=[CONFIGURÉ]")
            else:
                print(f"   ✅ {var}={value}")
        else:
            print(f"   ❌ {var}=[NON_DÉFINI]")

    print()

    # Test d'import du scraper
    print("📦 Test d'import du scraper:")
    try:
        sys.path.append('kafka/producers')
        from scrapers.linkedin_scraper import LinkedInScraper
        print("   ✅ Import réussi")
        print("   ✅ Classe LinkedInScraper disponible")

        # Créer une instance (sans connexion)
        scraper = LinkedInScraper()
        print("   ✅ Instance créée")

        # Vérifier les attributs
        if hasattr(scraper, 'linkedin_email'):
            email = scraper.linkedin_email
            if email and not email.startswith('votre_email'):
                print("   ✅ Email configuré dans l'instance")
            else:
                print("   ⚠️  Email non configuré ou par défaut")

        if hasattr(scraper, 'linkedin_password'):
            password = scraper.linkedin_password
            if password and not password.startswith('votre_mot_de_passe'):
                print("   ✅ Mot de passe configuré dans l'instance")
            else:
                print("   ⚠️  Mot de passe non configuré ou par défaut")

        print("   ✅ Scraper prêt pour les tests")

    except ImportError as e:
        print(f"   ❌ Erreur d'import: {e}")
        print("   💡 Vérifiez les dépendances: pip install selenium webdriver-manager")
    except Exception as e:
        print(f"   ❌ Erreur générale: {e}")

    print()

    # Instructions pour l'utilisateur
    print("🚀 Pour utiliser le scraper LinkedIn:")
    print("1. Configurez vos vrais credentials:")
    print("   python setup_linkedin_credentials.py")
    print()
    print("2. Testez avec de vraies credentials:")
    print("   python kafka/producers/run_scraper.py --scraper linkedin --max-pages 1")
    print()
    print("3. Pour un test complet avec Docker:")
    print("   docker-compose up -d kafka minio")
    print("   docker-compose run --rm scrapers python run_scraper.py --scraper linkedin")
    print()

    print("📋 Notes importantes:")
    print("• LinkedIn peut détecter et bloquer les scrapers")
    print("• Utilisez des délais appropriés pour éviter les bans")
    print("• Le mode headless est recommandé pour les serveurs")
    print("• Testez d'abord avec peu d'offres (max-pages=1)")

if __name__ == '__main__':
    test_linkedin_demo()
