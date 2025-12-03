#!/usr/bin/env python3
"""
==========================================
Run Scrapers - Orchestrateur Côte d'Ivoire
==========================================
Lance tous les scrapers d'emplois ivoiriens
Utilisé par Airflow ou en ligne de commande
"""

import os
import sys
import argparse
import time
from typing import Dict, List, Any
from datetime import datetime

# Ajouter le répertoire parent au path pour importer les scrapers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.educarriere_scraper import EducarriereScraper
from scrapers.macarrierepro_scraper import MacarriereproScraper
from scrapers.emploi_ci_scraper import EmploiCIScraper
from scrapers.linkedin_scraper import LinkedInScraper
from loguru import logger


class CIScrapersOrchestrator:
    """Orchestrateur pour tous les scrapers Côte d'Ivoire"""

    def __init__(self):
        self.scrapers = {
            'educarriere': EducarriereScraper,
            'macarrierepro': MacarriereproScraper,
            'emploi_ci': EmploiCIScraper,
            'linkedin': LinkedInScraper,
        }

        self.results = {}

        # Configuration logging
        logger.add(
            "scrapers_orchestrator.log",
            rotation="1 day",
            retention="7 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
        )

    def run_single_scraper(self, scraper_name: str, **kwargs) -> Dict[str, Any]:
        """Lance un scraper spécifique"""
        if scraper_name not in self.scrapers:
            raise ValueError(f"Scraper inconnu: {scraper_name}")

        logger.info(f"🚀 Lancement du scraper: {scraper_name}")

        try:
            scraper_class = self.scrapers[scraper_name]
            scraper = scraper_class()

            start_time = time.time()
            result = scraper.run(**kwargs)
            duration = time.time() - start_time

            result['duration_seconds'] = duration
            result['scraper_name'] = scraper_name
            result['timestamp'] = datetime.now().isoformat()

            logger.info(f"✅ {scraper_name} terminé en {duration:.2f}s - {result.get('jobs_scraped', 0)} offres")

            return result

        except Exception as e:
            logger.error(f"❌ Erreur scraper {scraper_name}: {e}")
            return {
                'scraper_name': scraper_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'jobs_scraped': 0,
                'jobs_sent_kafka': 0,
                'jobs_saved_minio': 0,
                'errors': 1
            }

    def run_all_scrapers(self, **kwargs) -> Dict[str, Any]:
        """Lance tous les scrapers disponibles"""
        logger.info("🎯 Lancement de tous les scrapers Côte d'Ivoire")

        all_results = {}
        total_jobs = 0
        total_errors = 0

        for scraper_name in self.scrapers.keys():
            logger.info(f"🔄 Lancement {scraper_name}...")

            try:
                result = self.run_single_scraper(scraper_name, **kwargs)
                all_results[scraper_name] = result

                total_jobs += result.get('jobs_scraped', 0)
                total_errors += result.get('errors', 0)

                # Petit délai entre scrapers pour éviter surcharge
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Erreur lancement {scraper_name}: {e}")
                all_results[scraper_name] = {
                    'scraper_name': scraper_name,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }

        summary = {
            'total_scrapers': len(self.scrapers),
            'total_jobs_scraped': total_jobs,
            'total_errors': total_errors,
            'timestamp': datetime.now().isoformat(),
            'scrapers_results': all_results
        }

        logger.info(f"🏁 Orchestration terminée: {total_jobs} offres scrapées, {total_errors} erreurs")

        return summary

    def get_available_scrapers(self) -> List[str]:
        """Retourne la liste des scrapers disponibles"""
        return list(self.scrapers.keys())


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Orchestrateur Scrapers Côte d\'Ivoire')
    parser.add_argument('--scraper', choices=['all', 'educarriere', 'macarrierepro', 'emploi_ci', 'linkedin'],
                       default='all', help='Scraper à lancer')
    parser.add_argument('--max-pages', type=int, default=None,
                       help='Nombre max de pages par scraper')
    parser.add_argument('--delay-min', type=float, default=2.0,
                       help='Délai minimum entre requêtes (secondes)')
    parser.add_argument('--delay-max', type=float, default=5.0,
                       help='Délai maximum entre requêtes (secondes)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Mode verbose')

    args = parser.parse_args()

    # Configuration logging console
    if args.verbose:
        logger.add(sys.stdout, level="DEBUG", format="{time:HH:mm:ss} | {level} | {message}")
    else:
        logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

    # Initialisation
    orchestrator = CIScrapersOrchestrator()

    print("🇨🇮 Orchestrateur Scrapers Côte d'Ivoire")
    print("=" * 50)
    print(f"Scrapers disponibles: {orchestrator.get_available_scrapers()}")
    print()

    try:
        kwargs = {
            'max_pages': args.max_pages,
            'delay_min': args.delay_min,
            'delay_max': args.delay_max
        }

        if args.scraper == 'all':
            result = orchestrator.run_all_scrapers(**kwargs)

            print("\n📊 Résumé général:")
            print(f"   Scrapers exécutés: {result['total_scrapers']}")
            print(f"   Total offres: {result['total_jobs_scraped']}")
            print(f"   Erreurs totales: {result['total_errors']}")

            print("\n📈 Détail par scraper:")
            for scraper_name, scraper_result in result['scrapers_results'].items():
                jobs = scraper_result.get('jobs_scraped', 0)
                errors = scraper_result.get('errors', 0)
                duration = scraper_result.get('duration_seconds', 0)
                print(".2f")

        else:
            result = orchestrator.run_single_scraper(args.scraper, **kwargs)

            print(f"\n📊 Résultat {args.scraper}:")
            print(f"   Offres scrapées: {result.get('jobs_scraped', 0)}")
            print(f"   Envoyées à Kafka: {result.get('jobs_sent_kafka', 0)}")
            print(f"   Sauvegardées MinIO: {result.get('jobs_saved_minio', 0)}")
            print(f"   Erreurs: {result.get('errors', 0)}")
            print(".2f")

    except KeyboardInterrupt:
        print("\n⏹️  Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur orchestrateur: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
