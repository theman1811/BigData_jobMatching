#!/usr/bin/env python3
"""
==========================================
Macarrierepro Scraper - Côte d'Ivoire
==========================================
Scraper pour https://macarrierepro.net/
+300 offres d'emploi - Interface moderne avec salaires
"""

import re
from typing import List, Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseJobScraperCI


class MacarriereproScraper(BaseJobScraperCI):
    """Scraper pour Macarrierepro.net - Plateforme moderne d'emploi ivoirienne"""

    BASE_URL = "https://macarrierepro.net"
    OFFERS_URL = "https://macarrierepro.net/poste/"

    # Mapping des catégories vers des compétences
    CATEGORY_SKILLS_MAPPING = {
        'Administration des Affaires': ['Administration', 'Gestion'],
        'Agronomie': ['Agriculture', 'Agronomie'],
        'Assurance': ['Assurance', 'Finance'],
        'Audit': ['Audit', 'Comptabilité', 'Finance'],
        'Banque': ['Banque', 'Finance'],
        'Bâtiment BTP': ['Bâtiment', 'Construction', 'Génie Civil'],
        'Commerce & Vente': ['Commerce', 'Vente', 'Commercial'],
        'Communication': ['Communication', 'Marketing'],
        'Comptabilité': ['Comptabilité', 'Finance'],
        'Contrôle de Gestion': ['Contrôle de Gestion', 'Finance'],
        'Digital marketing': ['Marketing Digital', 'Communication'],
        'Droit': ['Droit', 'Juridique'],
        'Électromécanique': ['Électromécanique', 'Maintenance'],
        'Finance': ['Finance', 'Comptabilité'],
        'Génie Civil': ['Génie Civil', 'Construction'],
        'Génie Industriel': ['Génie Industriel', 'Industrie'],
        'Génie Mécanique': ['Génie Mécanique', 'Mécanique'],
        'Géologie': ['Géologie', 'Environnement'],
        'Gestion': ['Gestion', 'Administration'],
        'Hôtellerie/Restauration': ['Hôtellerie', 'Restauration', 'Tourisme'],
        'Informatique': ['Informatique', 'IT', 'Technologie'],
        'Maintenance Industrielle': ['Maintenance', 'Industrie'],
        'Marketing': ['Marketing', 'Commercial'],
        'Mécanique': ['Mécanique', 'Maintenance'],
        'Ressources Humaines': ['Ressources Humaines', 'RH'],
        'Secrétariat / Assistanat': ['Secrétariat', 'Assistanat', 'Administration'],
        'Transit / Douane': ['Transit', 'Douane', 'Logistique'],
        'Transport / Logistique': ['Transport', 'Logistique']
    }

    def scrape_page(self, page: int = 1) -> str:
        """Scrape une page d'offres d'emploi"""
        url = f"{self.OFFERS_URL}?page={page}" if page > 1 else self.OFFERS_URL

        self.logger.info(f"📄 Scraping page {page}: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Rotation User-Agent entre les pages
            if page % 3 == 0:
                self.rotate_user_agent()

            return response.text

        except requests.RequestException as e:
            self.logger.error(f"❌ Erreur requête page {page}: {e}")
            return ""

    def parse_job_offer(self, job_element) -> Dict[str, Any]:
        """Parse une offre d'emploi depuis l'élément HTML"""
        try:
            # Structure typique observée:
            # <div class="job-item"> ou <div class="job-card">
            #   <h3>Technico-Commercial</h3>
            #   <span class="company">MOOV CÔTE D'IVOIRE</span>
            #   <span class="location">Abidjan, Côte d'Ivoire</span>
            #   <span class="salary">100 000 FCFA/ Mois</span>
            #   <span class="date">il y a 2 jours</span>
            #   <div class="tags">CDI, Technico-Commercial</div>

            # Extraire le titre
            title_elem = job_element.find('h3') or job_element.find(['h2', 'h4'])
            title = title_elem.text.strip() if title_elem else "Titre non trouvé"

            # Extraire l'entreprise
            company_elem = job_element.find('span', class_='company')
            company = company_elem.text.strip() if company_elem else "Entreprise confidentielle"

            # Extraire la localisation
            location_elem = job_element.find('span', class_='location')
            location_raw = location_elem.text.strip() if location_elem else "Côte d'Ivoire"
            location = self.clean_location_ci(location_raw)

            # Extraire le salaire
            salary_elem = job_element.find('span', class_='salary')
            salary_text = salary_elem.text.strip() if salary_elem else ""
            salary_info = self.clean_salary_ci(salary_text)

            # Extraire la date
            date_elem = job_element.find('span', class_='date')
            posted_date = date_elem.text.strip() if date_elem else ""

            # Extraire les tags/type de contrat
            tags_elem = job_element.find('div', class_='tags')
            tags = []
            contract_type = 'CDI'  # Défaut
            if tags_elem:
                tags_text = tags_elem.text.strip()
                tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]

                # Déterminer le type de contrat
                for tag in tags:
                    tag_upper = tag.upper()
                    if 'CDI' in tag_upper:
                        contract_type = 'CDI'
                    elif 'CDD' in tag_upper:
                        contract_type = 'CDD'
                    elif 'STAGE' in tag_upper:
                        contract_type = 'Stage'
                    elif 'FREELANCE' in tag_upper:
                        contract_type = 'Freelance'

            # Extraire l'URL de l'offre si disponible
            offer_link = job_element.find('a', href=True)
            offer_url = offer_link['href'] if offer_link else ""
            if offer_url and not offer_url.startswith('http'):
                offer_url = f"{self.BASE_URL}{offer_url}"

            # Créer l'ID unique
            job_id = self.create_job_id('macarrierepro', f"{title}_{company}_{posted_date}")

            # Détection de compétences basée sur le titre
            detected_skills = []
            title_lower = title.lower()

            # Ajout de compétences génériques
            if any(word in title_lower for word in ['commercial', 'vente', 'sales']):
                detected_skills.extend(['Commercial', 'Vente'])
            if any(word in title_lower for word in ['informatique', 'it', 'développeur', 'developer']):
                detected_skills.extend(['Informatique', 'IT'])
            if any(word in title_lower for word in ['comptable', 'compta', 'finance']):
                detected_skills.extend(['Comptabilité', 'Finance'])
            if any(word in title_lower for word in ['ressources humaines', 'rh']):
                detected_skills.extend(['Ressources Humaines', 'RH'])
            if any(word in title_lower for word in ['marketing', 'communication']):
                detected_skills.extend(['Marketing', 'Communication'])
            if any(word in title_lower for word in ['gestion', 'manager']):
                detected_skills.extend(['Gestion', 'Management'])
            if any(word in title_lower for word in ['assistant', 'assistante']):
                detected_skills.extend(['Assistanat', 'Administration'])

            # Analyse de la description si disponible dans l'élément
            description_elem = job_element.find('p', class_=re.compile(r'description|desc'))
            description = ""
            if description_elem:
                description = description_elem.text.strip()
                # Extraire plus de compétences de la description
                desc_lower = description.lower()
                if 'python' in desc_lower or 'java' in desc_lower or 'javascript' in desc_lower:
                    detected_skills.extend(['Programmation'])
                if 'sql' in desc_lower or 'database' in desc_lower:
                    detected_skills.extend(['Base de données', 'SQL'])
                if 'excel' in desc_lower:
                    detected_skills.extend(['Excel', 'Outils Bureautiques'])

            # Supprimer les doublons et nettoyer
            detected_skills = list(set(detected_skills))

            # Structure de données standardisée
            job_data = {
                'job_id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'description': description or title,  # Description ou titre comme fallback
                'contract_type': contract_type,
                'job_type': contract_type,
                'source': 'macarrierepro_net',
                'source_url': offer_url or self.OFFERS_URL,
                'posted_date': posted_date,
                'scraped_at': datetime.now().isoformat(),
                'country': 'Côte d\'Ivoire',

                # Informations salariales
                'salary_amount': salary_info.get('amount'),
                'salary_currency': salary_info.get('currency'),
                'salary_period': salary_info.get('period'),

                # Métadonnées spécifiques
                'macarrierepro_tags': tags,
                'macarrierepro_raw_salary': salary_text,

                # Données enrichies
                'skills': detected_skills,
                'remote_option': False,  # Généralement pas spécifié sur ce site
                'education_level': None,
                'experience_years': None,

                # Catégorisation
                'industry': self._guess_industry(title, company),
                'seniority_level': self._guess_seniority(title)
            }

            return job_data

        except Exception as e:
            self.logger.error(f"❌ Erreur parsing offre: {e}")
            return None

    def _guess_industry(self, title: str, company: str) -> str:
        """Déduit le secteur d'activité"""
        text = f"{title} {company}".lower()

        industries = {
            'Technologie': ['informatique', 'it', 'tech', 'digital', 'software'],
            'Finance': ['banque', 'finance', 'assurance', 'compta'],
            'Commerce': ['commercial', 'vente', 'commerce', 'distribution'],
            'Industrie': ['industrie', 'manufacture', 'production'],
            'BTP': ['bâtiment', 'construction', 'tp', 'btp'],
            'Santé': ['santé', 'médical', 'hospital'],
            'Education': ['education', 'enseignement', 'formation'],
            'Tourisme': ['hôtellerie', 'tourisme', 'restaurant'],
            'Transport': ['transport', 'logistique', 'transit'],
            'Télécom': ['télécom', 'mobile', 'orange', 'moov', 'mtn']
        }

        for industry, keywords in industries.items():
            if any(keyword in text for keyword in keywords):
                return industry

        return 'Autre'

    def _guess_seniority(self, title: str) -> str:
        """Déduit le niveau d'expérience"""
        title_lower = title.lower()

        if any(word in title_lower for word in ['junior', 'débutant', 'stagiaire']):
            return 'Junior'
        elif any(word in title_lower for word in ['senior', 'expert', 'lead', 'principal']):
            return 'Senior'
        elif any(word in title_lower for word in ['manager', 'directeur', 'chef', 'responsable']):
            return 'Manager'
        else:
            return 'Intermédiaire'

    def parse_jobs_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse toutes les offres d'une page HTML"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        jobs = []

        # Chercher les offres (différentes structures possibles)
        job_selectors = [
            '.job-item',
            '.job-card',
            '.offre-item',
            '.emploi-item',
            'article.job',
            'div.job'
        ]

        job_elements = []
        for selector in job_selectors:
            elements = soup.select(selector)
            if elements:
                job_elements = elements
                self.logger.info(f"🔍 Trouvé {len(elements)} offres avec sélecteur: {selector}")
                break

        # Fallback: chercher tous les éléments avec titre + entreprise
        if not job_elements:
            potential_jobs = soup.find_all(['div', 'article'], class_=True)
            for elem in potential_jobs:
                if elem.find(['h3', 'h2', 'h4']) and (
                    elem.find(string=re.compile(r'\d+.*FCFA')) or
                    elem.find('span', class_=re.compile(r'company|entreprise'))
                ):
                    job_elements.append(elem)

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

        # Chercher dans la pagination
        pagination = soup.find('div', class_=re.compile(r'pagination|pager'))
        if pagination:
            # Chercher les liens de page
            page_links = pagination.find_all(['a', 'span'], string=re.compile(r'\d+'))
            if page_links:
                page_numbers = []
                for link in page_links:
                    try:
                        num = int(link.text.strip())
                        page_numbers.append(num)
                    except ValueError:
                        continue
                if page_numbers:
                    return max(page_numbers)

        # Chercher "Page 1 sur X"
        page_text = soup.find(string=re.compile(r'Page\s+\d+\s+sur\s+\d+'))
        if page_text:
            match = re.search(r'Page\s+\d+\s+sur\s+(\d+)', page_text)
            if match:
                return int(match.group(1))

        # Estimation basée sur le nombre d'offres
        # Le site affiche généralement 20-30 offres par page
        offers_count = len(self.parse_jobs_from_html(html))
        if offers_count > 0:
            estimated_pages = max(1, (300 // offers_count))  # 300 offres totales
            self.logger.warning(f"⚠️ Nombre de pages non trouvé, estimation: {estimated_pages} pages")
            return estimated_pages

        # Défaut basé sur les données observées
        self.logger.warning("⚠️ Pagination non trouvée, utilisation de 15 pages par défaut")
        return 15

    def scrape_jobs(self, max_pages: int = None, delay_min: float = 2.0, delay_max: float = 5.0) -> List[Dict[str, Any]]:
        """Scrape toutes les offres d'emploi de Macarrierepro"""
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
        self.logger.info(f"✅ Scraping Macarrierepro terminé: {len(all_jobs)} offres au total")

        return all_jobs


def main():
    """Point d'entrée pour tests"""
    scraper = MacarriereproScraper()

    print("🇨🇮 Test Macarrierepro Scraper")
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
        print(f"   Entreprise: {job['company']}")
        print(f"   Salaire: {job.get('salary_amount', 'N/A')} {job.get('salary_currency', '')}")
        print(f"   Compétences: {job.get('skills', [])}")


if __name__ == '__main__':
    main()
