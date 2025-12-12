#!/usr/bin/env python3
"""
==========================================
Base Job Scraper - Côte d'Ivoire
==========================================
Classe abstraite pour tous les scrapers d'emplois en Côte d'Ivoire
Adapté aux spécificités du marché ivoirien (FCFA, localisation, etc.)
"""

import os
import time
import json
import logging
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

from kafka import KafkaProducer
from minio import Minio
import requests
from fake_useragent import UserAgent
from loguru import logger

# Configuration Côte d'Ivoire
COTE_D_IVOIRE_REGIONS = [
    'Abidjan', 'Bouaké', 'Daloa', 'Yamoussoukro', 'San-Pédro',
    'Korhogo', 'Man', 'Gagnoa', 'Divo', 'Soubré'
]

COTE_D_IVOIRE_CURRENCIES = ['FCFA', 'CFA', 'XOF']

class BaseJobScraperCI(ABC):
    """Classe abstraite pour tous les scrapers d'emplois en Côte d'Ivoire"""

    def __init__(self, kafka_servers=None, minio_endpoint=None):
        # Configuration Kafka
        self.kafka_servers = kafka_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.kafka_topic = 'job-offers-raw'

        # Configuration MinIO
        minio_env = os.getenv('MINIO_ENDPOINT', 'minio:9000')
        # Enlever le protocole http:// si présent (MinIO library l'ajoute automatiquement)
        if minio_env.startswith('http://'):
            minio_env = minio_env.replace('http://', '')
        self.minio_endpoint = minio_endpoint or minio_env
        self.minio_bucket = 'scraped-jobs'

        # Configuration scraping
        self.ua = UserAgent()
        self.session = requests.Session()
        self.setup_session()

        # Métriques
        self.stats = {
            'jobs_scraped': 0,
            'jobs_sent_kafka': 0,
            'jobs_saved_minio': 0,
            'errors': 0,
            'start_time': datetime.now()
        }

        # Setup logging
        self.logger = logger.bind(scraper=self.__class__.__name__)

    def setup_session(self):
        """Configure la session HTTP avec rotation User-Agent"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'identity',  # Désactiver la compression pour debug
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Linux"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Connection': 'keep-alive',
        })

    def rotate_user_agent(self):
        """Change le User-Agent pour éviter la détection"""
        # Utiliser un User-Agent Chrome fixe pour éviter les blocages
        chrome_ua = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.session.headers['User-Agent'] = chrome_ua

    def setup_kafka(self):
        """Configure la connexion Kafka"""
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1
            )
            self.logger.info(f"✅ Kafka connecté: {self.kafka_servers}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur connexion Kafka: {e}")
            return False

    def setup_minio(self):
        """Configure la connexion MinIO"""
        try:
            self.minio_client = Minio(
                self.minio_endpoint,
                access_key="minioadmin",
                secret_key="minioadmin123",
                secure=False
            )

            # Créer le bucket s'il n'existe pas
            if not self.minio_client.bucket_exists(self.minio_bucket):
                self.minio_client.make_bucket(self.minio_bucket)
                self.logger.info(f"📦 Bucket MinIO créé: {self.minio_bucket}")

            self.logger.info(f"✅ MinIO connecté: {self.minio_endpoint}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur connexion MinIO: {e}")
            return False

    def clean_location_ci(self, location: str) -> str:
        """Nettoie et standardise les localisations ivoiriennes"""
        if not location:
            return "Côte d'Ivoire"

        location = location.strip().lower()

        # Mapping des variantes communes
        location_mapping = {
            'abj': 'Abidjan',
            'abidjan': 'Abidjan',
            'côte d\'ivoire': 'Côte d\'Ivoire',
            'ci': 'Côte d\'Ivoire',
            'ivory coast': 'Côte d\'Ivoire',
            'bouake': 'Bouaké',
            'yamoussoukro': 'Yamoussoukro',
            'san pedro': 'San-Pédro',
            'san-pedro': 'San-Pédro'
        }

        for key, value in location_mapping.items():
            if key in location:
                return value

        # Capitaliser proprement
        return location.title()

    def clean_salary_ci(self, salary_text: str) -> Dict[str, Any]:
        """Parse et nettoie les salaires en FCFA"""
        if not salary_text:
            return {'amount': None, 'currency': 'FCFA', 'period': 'month'}

        salary_text = salary_text.upper().replace(' ', '')

        # Extraction du montant
        amount = None
        for currency in COTE_D_IVOIRE_CURRENCIES:
            if currency in salary_text:
                # Extraire les chiffres avant la devise
                import re
                numbers = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)', salary_text)
                if numbers:
                    # Prendre le dernier nombre (généralement le salaire)
                    amount_str = numbers[-1].replace(',', '').replace('.', '')
                    try:
                        amount = int(amount_str)
                    except ValueError:
                        pass
                break

        # Déterminer la période
        period = 'month'
        if any(word in salary_text for word in ['AN', 'ANS', 'ANNUEL']):
            period = 'year'
        elif any(word in salary_text for word in ['JOUR', 'DAY']):
            period = 'day'
        elif any(word in salary_text for word in ['HEURE', 'HOUR']):
            period = 'hour'

        return {
            'amount': amount,
            'currency': 'FCFA',
            'period': period,
            'original_text': salary_text
        }

    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extrait les compétences/technologies du texte"""
        # Liste basique de compétences à rechercher (à améliorer)
        common_skills = [
            'python', 'java', 'javascript', 'php', 'sql', 'mysql', 'postgresql',
            'html', 'css', 'react', 'vue', 'angular', 'nodejs', 'django', 'flask',
            'docker', 'kubernetes', 'aws', 'azure', 'linux', 'windows',
            'git', 'agile', 'scrum', 'management', 'leadership'
        ]

        text_lower = text.lower()
        detected_skills = []

        for skill in common_skills:
            if skill in text_lower:
                detected_skills.append(skill.title())

        return detected_skills

    def _guess_industry(self, title: str, company: str = "") -> str:
        """Déduit le secteur d'activité à partir du titre et de l'entreprise"""
        title_lower = title.lower()
        company_lower = company.lower()

        # Mappings de secteurs par mots-clés
        industry_mappings = {
            'Technologie': ['informatique', 'développeur', 'développement', 'software', 'it', 'tech',
                          'programmeur', 'analyste', 'data', 'web', 'mobile', 'digital'],
            'Santé': ['médecin', 'infirmier', 'infirmière', 'pharmacie', 'pharmaceutique',
                     'médical', 'biomédical', 'santé', 'clinique', 'hôpital'],
            'Finance': ['banque', 'finance', 'comptable', 'comptabilité', 'audit', 'banquier',
                       'financier', 'assurance', 'credit'],
            'Commerce': ['commercial', 'vente', 'ventes', 'commerce', 'marketing', 'business',
                        'client', 'relation client', 'caissier', 'vendeur'],
            'Logistique': ['logistique', 'transport', 'chauffeur', 'shipping', 'supply chain',
                          'entrepôt', 'stock', 'gestionnaire'],
            'Construction': ['bâtiment', 'construction', 'architecte', 'ingénieur', 'chantier',
                           'carreleur', 'plaquiste', 'maçon'],
            'Agriculture': ['agricole', 'agriculture', 'cultivateur', 'plantation', 'ferme'],
            'Education': ['enseignant', 'professeur', 'école', 'formation', 'éducateur'],
            'Tourisme': ['hôtellerie', 'restaurant', 'tourisme', 'hôtel', 'service'],
            'Industrie': ['usine', 'production', 'manufacture', 'ingénierie', 'technique']
        }

        # Recherche dans le titre
        for industry, keywords in industry_mappings.items():
            for keyword in keywords:
                if keyword in title_lower:
                    return industry

        # Recherche dans le nom de l'entreprise (moins prioritaire)
        if company and company != 'Entreprise confidentielle':
            for industry, keywords in industry_mappings.items():
                for keyword in keywords:
                    if keyword in company_lower:
                        return industry

        return 'Autre'

    def _guess_seniority(self, title: str) -> str:
        """Déduit le niveau d'expérience à partir du titre"""
        title_lower = title.lower()

        # Mappings de niveaux par mots-clés
        seniority_mappings = {
            'Senior': ['senior', 'expert', 'lead', 'principal', 'chef', 'directeur',
                      'manager', 'responsable', 'coordinateur', 'superviseur'],
            'Mid-level': ['chargé', 'spécialiste', 'analyste', 'technicien', 'assistant',
                         'collaborateur', 'professionnel'],
            'Entry-level': ['junior', 'stagiaire', 'apprenti', 'débutant', 'assistant junior']
        }

        for level, keywords in seniority_mappings.items():
            for keyword in keywords:
                if keyword in title_lower:
                    return level

        return 'Non spécifié'

    def create_job_id(self, source: str, unique_identifier: str) -> str:
        """Crée un ID unique pour l'offre d'emploi"""
        import hashlib
        content = f"{source}_{unique_identifier}_{datetime.now().date()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def send_to_kafka(self, job_data: Dict[str, Any], key: Optional[str] = None) -> bool:
        """Envoie les données d'offre à Kafka"""
        try:
            # Ajouter métadonnées
            job_data['scraped_at'] = datetime.now().isoformat()
            job_data['scraper_version'] = '1.0'
            job_data['country'] = 'Côte d\'Ivoire'

            future = self.kafka_producer.send(
                self.kafka_topic,
                value=job_data,
                key=key
            )

            # Wait for confirmation
            record_metadata = future.get(timeout=10)

            self.stats['jobs_sent_kafka'] += 1
            self.logger.info(f"📤 Offre envoyée à Kafka: {job_data.get('job_id', 'unknown')}")

            return True

        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"❌ Erreur envoi Kafka: {e}")
            return False

    def save_to_minio(self, job_id: str, html_content: str) -> bool:
        """Sauvegarde le HTML brut dans MinIO"""
        try:
            from io import BytesIO
            import gzip

            # Créer le contenu avec métadonnées
            metadata = {
                'job_id': job_id,
                'scraped_at': datetime.now().isoformat(),
                'source': self.__class__.__name__,
                'size': len(html_content)
            }

            content_with_meta = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n\n" + html_content

            # Compression gzip pour limiter l'espace disque et le trafic
            compressed = gzip.compress(content_with_meta.encode('utf-8'))
            data = BytesIO(compressed)

            self.minio_client.put_object(
                self.minio_bucket,
                f"{job_id}.html",
                data,
                length=len(compressed),
                content_type='text/html; charset=utf-8',
                metadata={"content-encoding": "gzip"}  # l'API ne supporte pas content_encoding direct
            )

            self.stats['jobs_saved_minio'] += 1
            self.logger.info(f"💾 HTML sauvegardé dans MinIO: {job_id}")

            return True

        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"❌ Erreur sauvegarde MinIO: {e}")
            return False

    def wait_random(self, min_seconds: float = 2.0, max_seconds: float = 5.0):
        """Attend un délai aléatoire pour éviter le rate limiting"""
        delay = random.uniform(min_seconds, max_seconds)
        self.logger.debug(f"⏳ Attente: {delay:.2f}s")
        time.sleep(delay)

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du scraper"""
        duration = datetime.now() - self.stats['start_time']
        return {
            **self.stats,
            'duration_seconds': duration.total_seconds(),
            'success_rate': (self.stats['jobs_scraped'] / max(1, self.stats['jobs_scraped'] + self.stats['errors'])) * 100
        }

    @abstractmethod
    def scrape_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        """Méthode principale à implémenter - retourne la liste des offres"""
        pass

    def run(self, **kwargs) -> Dict[str, Any]:
        """Méthode principale d'exécution du scraper"""
        self.logger.info(f"🚀 Démarrage du scraper: {self.__class__.__name__}")

        # Setup connexions
        kafka_ok = self.setup_kafka()
        minio_ok = self.setup_minio()

        if not kafka_ok or not minio_ok:
            self.logger.error("❌ Impossible de se connecter aux services")
            return self.get_stats()

        try:
            # Exécution du scraping
            jobs = self.scrape_jobs(**kwargs)

            self.stats['jobs_scraped'] = len(jobs)
            self.logger.info(f"✅ Scraping terminé: {len(jobs)} offres trouvées")

            # Traitement des offres
            for job in jobs:
                job_id = job.get('job_id', self.create_job_id(self.__class__.__name__, str(job)))

                # Envoyer à Kafka
                self.send_to_kafka(job, key=job_id)

                # Sauvegarder HTML si disponible
                if 'html_content' in job:
                    self.save_to_minio(job_id, job['html_content'])

                self.wait_random(1, 3)  # Petit délai entre chaque offre

        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"❌ Erreur scraping: {e}")

        finally:
            # Cleanup
            if hasattr(self, 'kafka_producer'):
                self.kafka_producer.close()

        final_stats = self.get_stats()
        self.logger.info(f"🏁 Scraper terminé - Stats: {final_stats}")
        return final_stats
