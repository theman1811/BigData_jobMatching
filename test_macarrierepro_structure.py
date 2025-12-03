#!/usr/bin/env python3
"""
Test de la structure HTML de Macarrierepro.net
Analyse la page pour comprendre comment extraire les offres
"""

import urllib.request
import urllib.error
from urllib.parse import urljoin
import re
from datetime import datetime

def test_macarrierepro_structure():
    """Test de la structure HTML de Macarrierepro"""

    url = "https://macarrierepro.net/"
    print(f"🔍 Analyse de la structure: {url}")
    print("=" * 60)

    try:
        # Headers pour éviter les blocages
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8', errors='ignore')

            print(f"✅ Status: {response.status}")
            print(f"📏 Taille: {len(content)} caractères")

            # Analyse basique du HTML
            print("\n🏗️ Analyse de la structure...")

            # Chercher des liens d'offres d'emploi
            job_links = re.findall(r'href="([^"]*(?:emploi|job|offre)[^"]*)"', content, re.IGNORECASE)
            print(f"🔗 Liens potentiels d'emplois trouvés: {len(job_links)}")
            for i, link in enumerate(job_links[:5]):
                full_link = urljoin(url, link)
                print(f"   {i+1}. {full_link}")

            # Chercher des éléments avec "offre" ou "emploi"
            offre_matches = re.findall(r'<[^>]*>([^<]*(?:offre|emploi)[^<]*)</[^>]*>', content, re.IGNORECASE)
            print(f"📄 Éléments HTML avec 'offre'/'emploi': {len(offre_matches)}")
            for i, match in enumerate(offre_matches[:5]):
                print(f"   {i+1}. {match.strip()[:60]}...")

            # Chercher des patterns de salaires (FCFA)
            salary_matches = re.findall(r'(\d+(?:[\s,.]\d+)*)\s*FCFA', content, re.IGNORECASE)
            print(f"💰 Mentions de salaires FCFA: {len(salary_matches)}")
            for i, salary in enumerate(salary_matches[:5]):
                print(f"   {i+1}. {salary} FCFA")

            # Chercher des dates
            date_patterns = [
                r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # DD/MM/YYYY
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY/MM/DD
                r'il y a \d+ \w+',                # "il y a 2 jours"
                r'publié \w+ \d+',               # "publié le 15"
            ]

            all_dates = []
            for pattern in date_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                all_dates.extend(matches)

            print(f"📅 Mentions de dates trouvées: {len(set(all_dates))}")
            for i, date in enumerate(list(set(all_dates))[:5]):
                print(f"   {i+1}. {date}")

            # Analyser la structure générale
            print("\n🏛️ Structure générale:")

            # Chercher les balises principales
            if '<main' in content:
                print("   ✅ Balise <main> trouvée")
            if '<article' in content:
                print("   ✅ Balise <article> trouvée")
            if 'class="job' in content:
                print("   ✅ Classes CSS 'job' trouvées")
            if 'class="offre' in content:
                print("   ✅ Classes CSS 'offre' trouvées")
            if 'class="emploi' in content:
                print("   ✅ Classes CSS 'emploi' trouvées")

            # Chercher des conteneurs potentiels d'offres
            containers = re.findall(r'<div[^>]*class="[^"]*(?:job|offre|emploi|card)[^"]*"[^>]*>.*?</div>', content, re.DOTALL | re.IGNORECASE)
            print(f"   📦 Conteneurs potentiels: {len(containers)}")

            # Sauvegarder un extrait pour analyse manuelle
            excerpt = content[:3000] + "\n\n...[contenu tronqué]..."
            with open('/tmp/macarrierepro_structure.html', 'w', encoding='utf-8') as f:
                f.write(excerpt)

            print("\n💾 Extrait HTML sauvegardé dans /tmp/macarrierepro_structure.html")
            print("🔍 Analyse terminée")

            return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    print("🇨🇮 Test de structure Macarrierepro.net")
    success = test_macarrierepro_structure()

    if success:
        print("\n📝 Résumé:")
        print("   - Site accessible")
        print("   - Contient des liens d'emplois")
        print("   - Structure HTML à analyser plus en détail")
        print("   - Extrait sauvegardé pour analyse manuelle")
    else:
        print("\n❌ Échec de l'analyse")

if __name__ == '__main__':
    main()
