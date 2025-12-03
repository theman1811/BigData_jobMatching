#!/usr/bin/env python3
"""
Debug script pour analyser la structure HTML d'Educarriere.ci
"""

import requests
from bs4 import BeautifulSoup
import json
import re

def debug_educarriere():
    """Debug de la page Educarriere"""

    url = "https://emploi.educarriere.ci/nos-offres"
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    print(f"🔍 Debug de: {url}")
    print("=" * 60)

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        print(f"✅ Status: {response.status_code}")
        print(f"📏 Taille: {len(response.text)} caractères")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Chercher différents patterns d'offres
        print("\n🔍 Recherche d'offres d'emploi...")

        # Pattern 1: Chercher les offres par titre
        titles = soup.find_all(['h1', 'h2', 'h3', 'h4'], string=lambda text: text and ('assistant' in text.lower() or 'gestionnaire' in text.lower() or 'commercia' in text.lower()))
        print(f"📋 Titres potentiels trouvés: {len(titles)}")
        for i, title in enumerate(titles[:3]):
            print(f"   {i+1}. {title.text.strip()}")

        # Pattern 2: Chercher les offres par structure
        offers = soup.find_all(['div', 'article'], class_=lambda c: c and any(word in str(c).lower() for word in ['offer', 'job', 'emploi', 'offre']))
        print(f"📦 Éléments avec classes 'offer/job/emploi': {len(offers)}")

        # Pattern 3: Chercher par contenu (Code:, Date d'édition:)
        code_elements = soup.find_all(string=lambda text: text and 'Code:' in text)
        print(f"🏷️  Éléments avec 'Code:': {len(code_elements)}")

        date_elements = soup.find_all(string=lambda text: text and "Date d'édition:" in text)
        print(f"📅 Éléments avec 'Date d'édition:': {len(date_elements)}")

        # Pattern 4: Chercher les numéros de code (format 137560)
        code_pattern = soup.find_all(string=lambda text: text and re.match(r'\d{6}', text.strip()))
        print(f"🔢 Numéros à 6 chiffres: {len(code_pattern)}")

        # Analyser la structure générale
        print("\n🏗️  Structure générale:")
        body = soup.find('body')
        if body:
            main_content = body.find(['main', 'div'], class_=lambda c: c and 'container' in str(c).lower())
            if main_content:
                print("   ✅ Conteneur principal trouvé")
                job_sections = main_content.find_all(['div', 'section'], recursive=False)
                print(f"   📂 Sections dans le conteneur: {len(job_sections)}")
            else:
                print("   ❌ Pas de conteneur principal trouvé")

        # Sauvegarder un extrait pour analyse
        print("\n💾 Sauvegarde d'un extrait HTML...")
        with open('/tmp/educarriere_debug.html', 'w', encoding='utf-8') as f:
            # Sauvegarder juste le body ou les 2000 premiers caractères
            content = str(body) if body else response.text[:2000]
            f.write(content)

        print("✅ Extrait sauvegardé dans /tmp/educarriere_debug.html")

        return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == '__main__':
    debug_educarriere()
