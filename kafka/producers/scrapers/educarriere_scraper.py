#!/usr/bin/env python3
"""
==========================================
Educarriere Scraper - Côte d'Ivoire
==========================================
Scraper pour https://emploi.educarriere.ci/nos-offres
809 offres d'emploi & de stage - Structure très claire
"""

import re
import time
from typing import List, Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseJobScraperCI


class EducarriereScraper(BaseJobScraperCI):
    """Scraper pour Educarriere.ci - Plateforme d'emploi éducative ivoirienne"""

    BASE_URL = "https://emploi.educarriere.ci"
    OFFERS_URL = "https://emploi.educarriere.ci/nos-offres"

    # Types d'emploi mappés
    JOB_TYPES_MAPPING = {
        'Emploi (CDI)': 'CDI',
        'Emploi': 'CDI',  # Défaut pour Emploi
        'Stage': 'Stage',
        'Freelance': 'Freelance',
        'CDD': 'CDD',
        'CDD CDI': 'CDD/CDI'
    }

    def scrape_page(self, page: int = 1) -> str:
        """Scrape une page d'offres d'emploi"""
        url = f"{self.OFFERS_URL}?page={page}" if page > 1 else self.OFFERS_URL

        self.logger.info(f"📄 Scraping page {page}: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Rotation User-Agent entre les pages
            if page % 3 == 0:  # Tous les 3 pages
                self.rotate_user_agent()

            return response.text

        except requests.RequestException as e:
            self.logger.error(f"❌ Erreur requête page {page}: {e}")
            return ""

    def parse_job_offer(self, job_element) -> Dict[str, Any]:
        """Parse une offre d'emploi depuis l'élément HTML"""
        try:
            # Analyser tout le texte de l'élément
            all_text = job_element.get_text(separator=' | ', strip=True)
            self.logger.debug(f"📝 Parsing offre: {all_text[:200]}...")

            # Extraire le code
            code_match = re.search(r'Code:\s*(\d+)', all_text)
            code = code_match.group(1) if code_match else ""

            # Extraire les dates
            date_edition_match = re.search(r"Date d'édition:\s*([^|]+)", all_text)
            date_edition = date_edition_match.group(1).strip() if date_edition_match else ""

            date_limite_match = re.search(r"Date limite:\s*([^|]+)", all_text)
            date_limite = date_limite_match.group(1).strip() if date_limite_match else ""

            # Extraire le titre - chercher dans les éléments de titre ou liens
            title = "Titre non trouvé"

            # Essayer les éléments de titre
            title_candidates = job_element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b', 'a'])
            for candidate in title_candidates:
                candidate_text = candidate.get_text(strip=True)
                if (len(candidate_text) > 5 and
                    not candidate_text.startswith('Code:') and
                    not 'Date' in candidate_text and
                    not candidate_text.isdigit()):
                    title = candidate_text
                    break

            # Si toujours pas trouvé, chercher dans le texte complet
            if title == "Titre non trouvé":
                lines = [line.strip() for line in all_text.split(' | ') if line.strip()]
                for line in lines:
                    if (len(line) > 10 and
                        not line.startswith('Code:') and
                        not 'Date' in line and
                        not line.replace('/', '').replace('-', '').isdigit()):
                        title = line
                        break

            # Chercher l'URL
            offer_link = job_element.find('a', href=True)
            offer_url = ""
            if offer_link:
                offer_url = offer_link['href']
                if offer_url and not offer_url.startswith('http'):
                    offer_url = f"{self.BASE_URL}{offer_url}"

            # Déterminer le type de contrat depuis le titre
            contract_type = 'CDI'
            title_lower = title.lower()
            if 'stage' in title_lower:
                contract_type = 'Stage'
            elif 'cdd' in title_lower:
                contract_type = 'CDD'
            elif 'freelance' in title_lower or 'indépendant' in title_lower:
                contract_type = 'Freelance'

            # Créer l'ID unique
            job_id = self.create_job_id('educarriere', code or title)

            # Extraire les compétences du titre
            detected_skills = super()._extract_skills_from_text(title)

            # Structure de données standardisée
            job_data = {
                'job_id': job_id,
                'title': title,
                'company': 'Entreprise confidentielle',  # Educarriere n'affiche pas toujours l'entreprise
                'location': 'Côte d\'Ivoire',
                'description': title,
                'contract_type': contract_type,
                'job_type': contract_type,
                'source': 'educarriere_ci',
                'source_url': offer_url,
                'posted_date': date_edition,
                'application_deadline': date_limite,
                'scraped_at': datetime.now().isoformat(),
                'country': 'Côte d\'Ivoire',

                # Métadonnées spécifiques Educarriere
                'educarriere_code': code,
                'educarriere_date_edition': date_edition,
                'educarriere_date_limite': date_limite,

                # Données enrichies
                'salary': None,
                'remote_option': False,
                'skills': detected_skills,
                'education_level': None,
                'experience_years': None,

                # Catégorisation
                'industry': self._guess_industry(title, 'Entreprise confidentielle'),
                'seniority_level': self._guess_seniority(title)
            }

            self.logger.debug(f"✅ Offre parsée: {code} - {title}")
            return job_data

        except Exception as e:
            self.logger.error(f"❌ Erreur parsing offre: {e}")
            return None

    def parse_jobs_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse toutes les offres d'une page HTML"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        jobs = []

        # DEBUG: Analyser le contenu de la page
        page_title = soup.find('title')
        self.logger.info(f"🔍 DEBUG: Titre de la page: {page_title.text.strip() if page_title else 'AUCUN TITRE'}")

        body = soup.find('body')
        if body:
            self.logger.info(f"🔍 DEBUG: Body trouvé, longueur: {len(str(body))} caractères")
            # Chercher tous les liens
            all_links = body.find_all('a', href=True)
            self.logger.info(f"🔍 DEBUG: {len(all_links)} liens trouvés")
            for i, link in enumerate(all_links[:3]):
                self.logger.info(f"   {i+1}. {link.text.strip()[:30]}... -> {link['href'][:50]}")

            # Chercher tous les éléments de texte significatifs
            text_elements = body.find_all(string=lambda t: t and len(t.strip()) > 20)
            self.logger.info(f"🔍 DEBUG: {len(text_elements)} éléments texte (>20 chars)")
            for i, text in enumerate(text_elements[:3]):
                self.logger.info(f"   {i+1}. {text.strip()[:50]}...")
        else:
            self.logger.error("❌ DEBUG: AUCUN body trouvé dans la page!")
            self.logger.info(f"🔍 DEBUG: Contenu HTML brut (500 premiers chars): {html[:500]}")

        # DEBUG: Chercher tous les titres potentiels
        all_titles = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5'], string=lambda t: t and len(t.strip()) > 5)
        self.logger.info(f"🔍 DEBUG: {len(all_titles)} titres H1-H5 trouvés")
        for i, title in enumerate(all_titles[:5]):
            self.logger.info(f"   H{i+1}. {title.text.strip()[:50]}...")

        # DEBUG: Chercher tous les éléments avec "Code:"
        all_codes = soup.find_all(string=re.compile(r'Code:'))
        self.logger.info(f"🔍 DEBUG: {len(all_codes)} éléments avec 'Code:' trouvés")
        for i, code in enumerate(all_codes[:3]):
            self.logger.info(f"   {i+1}. {code.strip()}")

        # Chercher les offres - Nouvelle approche : chercher les conteneurs qui ont les patterns complets
        # Pattern: élément qui contient "Code:" ET "Date d'édition:"
        job_elements = []

        # Chercher tous les éléments (div, article, etc.) qui contiennent les patterns d'une offre complète
        all_containers = soup.find_all(['div', 'article', 'li', 'tr'])

        for container in all_containers:
            container_text = container.get_text(separator=' ', strip=True)

            # Vérifier si cet élément contient les patterns caractéristiques d'une offre d'emploi
            has_code = re.search(r'Code:\s*\d+', container_text)
            has_date_edition = re.search(r"Date d'édition:", container_text)
            has_date_limite = re.search(r"Date limite:", container_text)

            # Et qu'il a du texte qui ressemble à un titre d'offre (longueur significative)
            text_length = len(container_text)
            has_title_like_text = text_length > 50 and text_length < 500  # Longueur réaliste pour une offre

            if has_code and (has_date_edition or has_date_limite) and has_title_like_text:
                # Filtrer les faux positifs (articles de news, etc.)
                if not any(skip_word in container_text.lower() for skip_word in [
                    'formation lbc/ft', 'agboville', 'coupure d\'eau', 'actualité', 'news'
                ]):
                    job_elements.append(container)
                    self.logger.debug(f"✅ Offre trouvée: {container_text[:100]}...")

        self.logger.info(f"🔍 Trouvé {len(job_elements)} éléments d'offres valides")

        self.logger.info(f"🔍 Trouvé {len(job_elements)} éléments d'offres sur la page")

        for job_elem in job_elements:
            job_data = self.parse_job_offer(job_elem)
            if job_data:
                jobs.append(job_data)

        return jobs

    def get_total_pages(self, html: str) -> int:
        """Détermine le nombre total de pages"""
        if not html:
            return 1

        soup = BeautifulSoup(html, 'html.parser')

        # Chercher "Page n° 1 sur 29"
        page_text = soup.find(string=re.compile(r'Page\s+n°\s+\d+\s+sur\s+\d+'))
        if page_text:
            match = re.search(r'Page\s+n°\s+\d+\s+sur\s+(\d+)', page_text)
            if match:
                return int(match.group(1))

        # Chercher dans la pagination
        pagination = soup.find('div', class_=re.compile(r'pagination|pager'))
        if pagination:
            page_links = pagination.find_all(['a', 'span'], string=re.compile(r'\d+'))
            if page_links:
                # Prendre le numéro le plus élevé
                page_numbers = []
                for link in page_links:
                    try:
                        num = int(link.text.strip())
                        page_numbers.append(num)
                    except ValueError:
                        continue
                if page_numbers:
                    return max(page_numbers)

        # Défaut: 29 pages comme vu dans les résultats
        self.logger.warning("⚠️ Nombre de pages non trouvé, utilisation de 29 par défaut")
        return 29

    def scrape_jobs(self, max_pages: int = None, delay_min: float = 2.0, delay_max: float = 5.0) -> List[Dict[str, Any]]:
        """Scrape toutes les offres d'emploi d'Educarriere"""
        all_jobs = []

        # Page 1 pour déterminer le nombre total de pages
        self.logger.info("📊 Récupération du nombre total de pages...")
        html_page1 = self.scrape_page(1)

        if not html_page1:
            self.logger.error("❌ Impossible de charger la première page")
            return []

        total_pages = self.get_total_pages(html_page1)
        actual_max_pages = min(max_pages or total_pages, total_pages)

        self.logger.info(f"📈 Total pages: {total_pages}, scraping: {actual_max_pages} pages")

        # Parser la première page
        jobs_page1 = self.parse_jobs_from_html(html_page1)
        all_jobs.extend(jobs_page1)
        self.logger.info(f"📄 Page 1: {len(jobs_page1)} offres trouvées")

        # Scraper les pages suivantes
        for page in range(2, actual_max_pages + 1):
            self.logger.info(f"🔄 Page {page}/{actual_max_pages}")

            # Délai anti-ban
            self.wait_random(delay_min, delay_max)

            html = self.scrape_page(page)
            if not html:
                self.logger.warning(f"⚠️ Page {page} ignorée")
                continue

            jobs = self.parse_jobs_from_html(html)
            all_jobs.extend(jobs)

            self.logger.info(f"📄 Page {page}: {len(jobs)} offres trouvées (Total: {len(all_jobs)})")

        # Statistiques finales
        self.logger.info(f"✅ Scraping Educarriere terminé: {len(all_jobs)} offres au total")

        return all_jobs


def main():
    """Point d'entrée pour tests"""
    scraper = EducarriereScraper()

    print("🚀 Test Educarriere Scraper")
    print("=" * 50)

    # Test rapide (2 pages)
    jobs = scraper.run(max_pages=2, delay_min=1.0, delay_max=2.0)

    print(f"\n📊 Résultats:")
    print(f"   Offres trouvées: {len(jobs)}")
    print(f"   Envoyées à Kafka: {scraper.stats['jobs_sent_kafka']}")
    print(f"   Sauvegardées MinIO: {scraper.stats['jobs_saved_minio']}")
    print(f"   Erreurs: {scraper.stats['errors']}")

    if jobs:
        print(f"\n🔍 Exemple d'offre:")
        job = jobs[0]
        print(f"   ID: {job['job_id']}")
        print(f"   Titre: {job['title']}")
        print(f"   Type: {job['job_type']}")
        print(f"   Source: {job['source']}")


if __name__ == '__main__':
    main()
