#!/usr/bin/env python3
"""
Test de la structure LinkedIn Jobs pour Côte d'Ivoire
Analyse la page de recherche d'emplois
"""

import urllib.request
import urllib.error
import re
from datetime import datetime

def test_linkedin_jobs_structure():
    """Test de la structure des jobs LinkedIn"""

    # URL de recherche d'emplois en Côte d'Ivoire pour l'informatique
    url = "https://www.linkedin.com/jobs/search/?keywords=informatique&location=C%C3%B4te%20d%27Ivoire"
    print(f"🔍 Analyse LinkedIn Jobs: {url}")
    print("=" * 60)

    try:
        # Headers pour simuler un navigateur
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'identity',  # Pas de compression pour debug
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8', errors='ignore')

            print(f"✅ Status: {response.status}")
            print(f"📏 Taille: {len(content)} caractères")

            # Analyse du contenu
            print("\n🏗️ Analyse du contenu...")

            # Vérifier si c'est une page de connexion
            if 'login' in content.lower() or 'sign in' in content.lower():
                print("🔐 Page de connexion détectée - authentification requise")
                login_forms = re.findall(r'<form[^>]*>.*?</form>', content, re.DOTALL | re.IGNORECASE)
                print(f"   📝 Formulaires de login trouvés: {len(login_forms)}")
                return "REQUIRES_AUTH"

            # Chercher des offres d'emploi
            job_cards = re.findall(r'class="[^"]*job-card[^"]*"', content, re.IGNORECASE)
            print(f"💼 Cartes d'offres trouvées: {len(job_cards)}")

            # Chercher des mentions d'emplois
            job_mentions = re.findall(r'<[^>]*>([^<]*(?:job|emploi|offre)[^<]*)</[^>]*>', content, re.IGNORECASE)
            print(f"📄 Mentions d'emplois: {len(job_mentions)}")
            for i, mention in enumerate(job_mentions[:3]):
                print(f"   {i+1}. {mention.strip()[:50]}...")

            # Chercher des entreprises
            company_mentions = re.findall(r'<[^>]*>([^<]*(?:company|entreprise)[^<]*)</[^>]*>', content, re.IGNORECASE)
            print(f"🏢 Mentions d'entreprises: {len(company_mentions)}")

            # Chercher des localisations
            location_mentions = re.findall(r'<[^>]*>([^<]*(?:location|lieu|Côte d\'Ivoire|C\.I\.)[^<]*)</[^>]*>', content, re.IGNORECASE)
            print(f"📍 Mentions de localisation: {len(location_mentions)}")

            # Analyser la structure générale
            print("\n🏛️ Structure générale:")

            if '<main' in content:
                print("   ✅ Balise <main> trouvée")
            if '<article' in content:
                print("   ✅ Balise <article> trouvée")
            if 'data-job-id' in content:
                print("   ✅ Attributs data-job-id trouvés")
            if 'data-company-name' in content:
                print("   ✅ Attributs data-company-name trouvés")

            # Chercher les scripts JSON (LinkedIn charge souvent les données en JSON)
            json_scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', content, re.DOTALL)
            print(f"   📋 Scripts JSON-LD trouvés: {len(json_scripts)}")

            # Sauvegarder un extrait pour analyse
            excerpt = content[:4000] + "\n\n...[contenu tronqué]..."
            with open('/tmp/linkedin_jobs_structure.html', 'w', encoding='utf-8') as f:
                f.write(excerpt)

            print("\n💾 Extrait HTML sauvegardé dans /tmp/linkedin_jobs_structure.html")
            print("🔍 Analyse terminée")

            return "ACCESSIBLE"

    except urllib.error.HTTPError as e:
        print(f"❌ Erreur HTTP: {e.code}")
        if e.code == 403:
            print("   🚫 Accès refusé (probablement anti-bot)")
        return "BLOCKED"
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        return "ERROR"

def main():
    print("🔗 Test de structure LinkedIn Jobs Côte d'Ivoire")
    result = test_linkedin_jobs_structure()

    print(f"\n📊 Résultat: {result}")

    if result == "REQUIRES_AUTH":
        print("📝 LinkedIn nécessite une authentification pour accéder aux offres")
        print("   - Le scraper devra gérer la connexion automatique")
        print("   - Variables d'environnement nécessaires: LINKEDIN_EMAIL, LINKEDIN_PASSWORD")
    elif result == "ACCESSIBLE":
        print("✅ LinkedIn accessible sans authentification basique")
        print("   - Structure analysée et sauvegardée")
        print("   - Le scraper peut potentiellement fonctionner")
    elif result == "BLOCKED":
        print("🚫 LinkedIn bloque les accès non authentifiés")
        print("   - Authentification Selenium nécessaire")
    else:
        print("❌ Problème d'accès à LinkedIn")

if __name__ == '__main__':
    main()
