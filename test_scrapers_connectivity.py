#!/usr/bin/env python3
"""
Test de connectivité des sites de scraping
Vérifie que les sites sont accessibles avant d'installer les dépendances
"""

import urllib.request
import urllib.error
import json
from datetime import datetime

def test_site_connectivity(url, name):
    """Test la connectivité d'un site"""
    print(f"🌐 Test de {name}: {url}")

    try:
        # Configuration basique pour éviter les blocages
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()
            size = len(content)
            status = response.status

            print(f"   ✅ Status: {status}")
            print(f"   📏 Taille: {size} octets")
            print(f"   📄 Type: {response.headers.get('content-type', 'unknown')}")

            # Test basique du contenu
            content_str = content.decode('utf-8', errors='ignore')
            if 'emploi' in content_str.lower() or 'job' in content_str.lower():
                print(f"   ✅ Contenu semble pertinent (contient 'emploi' ou 'job')")
            else:
                print(f"   ⚠️ Contenu peut ne pas être pertinent")

            return True, size, status

    except urllib.error.HTTPError as e:
        print(f"   ❌ Erreur HTTP: {e.code} - {e.reason}")
        return False, 0, e.code
    except urllib.error.URLError as e:
        print(f"   ❌ Erreur URL: {e.reason}")
        return False, 0, None
    except Exception as e:
        print(f"   ❌ Erreur générale: {e}")
        return False, 0, None

def main():
    """Test de tous les sites de scraping"""
    print("🇨🇮 Test de connectivité des sites de scraping Côte d'Ivoire")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Liste des sites à tester
    sites = [
        {
            'name': 'Educarriere.ci',
            'url': 'https://emploi.educarriere.ci/nos-offres',
            'description': 'Plateforme éducative - 809 offres'
        },
        {
            'name': 'Macarrierepro.net',
            'url': 'https://macarrierepro.net/',
            'description': '+300 offres avec salaires'
        },
        {
            'name': 'Macarrierepro.net (emplois)',
            'url': 'https://macarrierepro.net/emplois',
            'description': 'URL alternative pour les emplois'
        },
        {
            'name': 'Macarrierepro.net (jobs)',
            'url': 'https://macarrierepro.net/jobs',
            'description': 'URL alternative pour les jobs'
        },
        {
            'name': 'Emploi.ci',
            'url': 'https://www.emploi.ci/',
            'description': 'Plateforme principale ivoirienne'
        },
        {
            'name': 'Emploi.ci (emplois)',
            'url': 'https://www.emploi.ci/emplois',
            'description': 'URL alternative pour les emplois'
        },
        {
            'name': 'LinkedIn Jobs CI',
            'url': 'https://www.linkedin.com/jobs/search/?keywords=informatique&location=C%C3%B4te%20d%27Ivoire',
            'description': 'LinkedIn Côte d\'Ivoire (nécessite authentification)'
        }
    ]

    results = []

    for site in sites:
        print(f"\n🔍 {site['name']}")
        print(f"   {site['description']}")
        print("-" * 50)

        success, size, status = test_site_connectivity(site['url'], site['name'])

        result = {
            'name': site['name'],
            'url': site['url'],
            'success': success,
            'size': size,
            'status': status,
            'timestamp': datetime.now().isoformat()
        }
        results.append(result)

        print()

    # Résumé
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 70)

    successful = sum(1 for r in results if r['success'])
    total = len(results)

    print(f"Sites testés: {total}")
    print(f"Sites accessibles: {successful}")
    print(f"Taux de succès: {successful/total*100:.1f}%")

    print("\n📋 DÉTAIL:")
    for result in results:
        status_icon = "✅" if result['success'] else "❌"
        status_text = f"{result['status']}" if result['status'] else "N/A"
        print(f"   {status_icon} {result['name']}: {status_text} ({result['size']} octets)")

    # Sauvegarde des résultats
    with open('connectivity_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n💾 Résultats sauvegardés dans: connectivity_test_results.json")
    print("\n🏁 Tests de connectivité terminés")

    if successful == total:
        print("🎉 Tous les sites sont accessibles!")
    elif successful > 0:
        print("⚠️ Certains sites sont accessibles, d'autres non.")
    else:
        print("❌ Aucun site n'est accessible. Problème de connectivité.")

if __name__ == '__main__':
    main()
