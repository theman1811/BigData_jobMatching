#!/usr/bin/env python3
"""
==========================================
Emploi.ci Scraper - Côte d'Ivoire
==========================================
Scraper pour https://www.emploi.ci/
Plateforme principale d'emploi ivoirienne - Volume important
"""

import re
from typing import List, Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseJobScraperCI


class EmploiCIScraper(BaseJobScraperCI):
    """Scraper pour Emploi.ci - Plateforme principale d'emploi ivoirienne"""

    BASE_URL = "https://www.emploi.ci"
    OFFERS_URL = "https://www.emploi.ci/offres-emploi"

    def scrape_page(self, page: int = 1) -> str:
        """Scrape une page d'offres d'emploi"""
        # Différentes structures d'URL possibles selon le site
        possible_urls = [
            f"{self.OFFERS_URL}?page={page}",
            f"{self.OFFERS_URL}/page/{page}",
            f"{self.BASE_URL}/offres-emploi?page={page}",
            f"{self.BASE_URL}/emplois?page={page}"
        ]

        for url in possible_urls:
            self.logger.info(f"📄 Tentative scraping page {page}: {url}")

            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # Si on obtient une réponse valide, on garde cette URL
                if len(response.text) > 10000:  # Page avec contenu
                    self.logger.info(f"✅ URL valide trouvée: {url}")
                    return response.text

            except requests.RequestException as e:
                self.logger.debug(f"❌ URL {url} échouée: {e}")
                continue

        # Rotation User-Agent entre les pages
        if page % 3 == 0:
            self.rotate_user_agent()

        self.logger.error(f"❌ Aucune URL valide trouvée pour la page {page}")
        return ""

    def parse_job_offer(self, job_element) -> Dict[str, Any]:
        """Parse une offre d'emploi depuis l'élément HTML"""
        try:
            # Structures possibles (à adapter selon le site réel):
            # Variante 1: <div class="job-offer"> <h3><a href="...">Titre</a></h3> ...
            # Variante 2: <article class="offer"> <h2>Titre</h2> ...
            # Variante 3: <div class="emploi-item"> ...

            # Essayer différentes structures
            title_elem = None
            link_elem = None

            # Chercher le titre
            for selector in ['h3 a', 'h2 a', '.job-title a', '.offer-title a', 'h3', 'h2']:
                title_elem = job_element.select_one(selector)
                if title_elem:
                    break

            if not title_elem:
                return None

            # Extraire le titre et le lien
            if title_elem.name == 'a':
                title = title_elem.text.strip()
                offer_url = title_elem.get('href', '')
            else:
                title = title_elem.text.strip()
                link_elem = title_elem.find_parent('a') or job_element.find('a')
                offer_url = link_elem.get('href', '') if link_elem else ''

            if not offer_url.startswith('http'):
                offer_url = f"{self.BASE_URL}{offer_url}"

            # Extraire l'entreprise
            company_elem = None
            for selector in ['.company', '.entreprise', '.employer', '.company-name']:
                company_elem = job_element.select_one(selector)
                if company_elem:
                    break
            company = company_elem.text.strip() if company_elem else "Entreprise non spécifiée"

            # Extraire la localisation
            location_elem = None
            for selector in ['.location', '.ville', '.lieu', '.place']:
                location_elem = job_element.select_one(selector)
                if location_elem:
                    break
            location_raw = location_elem.text.strip() if location_elem else "Côte d'Ivoire"
            location = self.clean_location_ci(location_raw)

            # Extraire le salaire
            salary_elem = None
            for selector in ['.salary', '.salaire', '.remuneration', '.pay']:
                salary_elem = job_element.select_one(selector)
                if salary_elem:
                    break
            salary_text = salary_elem.text.strip() if salary_elem else ""
            salary_info = self.clean_salary_ci(salary_text)

            # Extraire la date
            date_elem = None
            for selector in ['.date', '.posted-date', '.publish-date', '.time']:
                date_elem = job_element.select_one(selector)
                if date_elem:
                    break
            posted_date = date_elem.text.strip() if date_elem else ""

            # Extraire le type de contrat
            contract_elem = None
            for selector in ['.contract', '.type', '.job-type', '.contract-type']:
                contract_elem = job_element.select_one(selector)
                if contract_elem:
                    break
            contract_type = 'CDI'  # Défaut
            if contract_elem:
                contract_text = contract_elem.text.strip().upper()
                if 'CDI' in contract_text:
                    contract_type = 'CDI'
                elif 'CDD' in contract_text:
                    contract_type = 'CDD'
                elif 'STAGE' in contract_text:
                    contract_type = 'Stage'
                elif 'FREELANCE' in contract_text or 'INDEPENDANT' in contract_text:
                    contract_type = 'Freelance'

            # Extraire la description courte si disponible
            desc_elem = None
            for selector in ['.description', '.desc', '.summary', '.excerpt']:
                desc_elem = job_element.select_one(selector)
                if desc_elem:
                    break
            description = desc_elem.text.strip() if desc_elem else title

            # Créer l'ID unique
            job_id = self.create_job_id('emploi_ci', f"{title}_{company}_{posted_date}")

            # Analyse du titre et description pour extraire les compétences
            detected_skills = self._extract_skills_from_text(title + " " + description)

            # Structure de données standardisée
            job_data = {
                'job_id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'contract_type': contract_type,
                'job_type': contract_type,
                'source': 'emploi_ci',
                'source_url': offer_url,
                'posted_date': posted_date,
                'scraped_at': datetime.now().isoformat(),
                'country': 'Côte d\'Ivoire',

                # Informations salariales
                'salary_amount': salary_info.get('amount'),
                'salary_currency': salary_info.get('currency'),
                'salary_period': salary_info.get('period'),

                # Données enrichies
                'skills': detected_skills,
                'remote_option': self._detect_remote_option(title + " " + description),
                'education_level': None,
                'experience_years': None,

                # Catégorisation
                'industry': self._guess_industry(title, company),
                'seniority_level': self._guess_seniority(title),

                # Métadonnées spécifiques
                'emploi_ci_raw_salary': salary_text
            }

            return job_data

        except Exception as e:
            self.logger.error(f"❌ Erreur parsing offre: {e}")
            return None

    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extrait les compétences du texte"""
        detected_skills = []
        text_lower = text.lower()

        # Compétences techniques
        tech_skills = {
            'Python': ['python'],
            'Java': ['java', 'java '],
            'JavaScript': ['javascript', 'js'],
            'PHP': ['php'],
            'SQL': ['sql', 'mysql', 'postgresql', 'oracle'],
            'HTML/CSS': ['html', 'css'],
            'React': ['react'],
            'Angular': ['angular'],
            'Vue.js': ['vue'],
            'Node.js': ['node', 'nodejs'],
            'Docker': ['docker'],
            'Kubernetes': ['kubernetes', 'k8s'],
            'AWS': ['aws', 'amazon web services'],
            'Azure': ['azure'],
            'GCP': ['gcp', 'google cloud'],
            'Git': ['git'],
            'Linux': ['linux'],
            'Windows': ['windows'],
            'Excel': ['excel'],
            'Word': ['word'],
            'PowerPoint': ['powerpoint']
        }

        # Compétences métier
        business_skills = {
            'Gestion': ['gestion', 'management'],
            'Commerce': ['commerce', 'commercial', 'vente', 'sales'],
            'Marketing': ['marketing', 'communication'],
            'Finance': ['finance', 'compta', 'comptable'],
            'Ressources Humaines': ['rh', 'ressources humaines', 'hr'],
            'Juridique': ['droit', 'juridique', 'legal'],
            'Logistique': ['logistique', 'supply chain'],
            'Qualité': ['qualité', 'qa', 'qc']
        }

        # Chercher toutes les compétences
        for skill, keywords in {**tech_skills, **business_skills}.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_skills.append(skill)

        return list(set(detected_skills))

    def _detect_remote_option(self, text: str) -> bool:
        """Détecte si le poste permet le télétravail"""
        text_lower = text.lower()
        remote_keywords = [
            'remote', 'télétravail', 'teletravail', 'home office',
            'travail à distance', 'remote work', 'work from home'
        ]
        return any(keyword in text_lower for keyword in remote_keywords)

    def _guess_industry(self, title: str, company: str) -> str:
        """Déduit le secteur d'activité"""
        text = f"{title} {company}".lower()

        industries = {
            'Technologie': ['informatique', 'it', 'tech', 'digital', 'software', 'développement'],
            'Finance': ['banque', 'finance', 'assurance', 'compta', 'comptable'],
            'Commerce': ['commercial', 'vente', 'commerce', 'distribution', 'retail'],
            'Industrie': ['industrie', 'manufacture', 'production', 'usine'],
            'BTP': ['bâtiment', 'construction', 'tp', 'btp', 'immobilier'],
            'Santé': ['santé', 'médical', 'hospital', 'clinique', 'pharmacie'],
            'Education': ['education', 'enseignement', 'formation', 'école'],
            'Tourisme': ['hôtellerie', 'tourisme', 'restaurant', 'hôtel'],
            'Transport': ['transport', 'logistique', 'transit', 'chauffeur'],
            'Télécom': ['télécom', 'mobile', 'internet', 'orange', 'moov', 'mtn'],
            'Agriculture': ['agriculture', 'agronomie', 'ferme', 'plantation'],
            'Énergie': ['énergie', 'pétrole', 'gaz', 'electricité']
        }

        for industry, keywords in industries.items():
            if any(keyword in text for keyword in keywords):
                return industry

        return 'Autre'

    def _guess_seniority(self, title: str) -> str:
        """Déduit le niveau d'expérience"""
        title_lower = title.lower()

        if any(word in title_lower for word in ['junior', 'débutant', 'stagiaire', 'apprenti']):
            return 'Junior'
        elif any(word in title_lower for word in ['senior', 'expert', 'lead', 'principal', 'architecte']):
            return 'Senior'
        elif any(word in title_lower for word in ['manager', 'directeur', 'chef', 'responsable', 'coordinateur']):
            return 'Manager'
        elif any(word in title_lower for word in ['assistante', 'assistant']):
            return 'Assistant'
        else:
            return 'Intermédiaire'

    def parse_jobs_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse toutes les offres d'une page HTML"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        jobs = []

        # Essayer différents sélecteurs pour trouver les offres
        job_selectors = [
            '.job-offer',
            '.emploi-item',
            '.offer-item',
            '.job-listing',
            'article.offer',
            'div.job',
            '.emploi-card',
            '.offer-card'
        ]

        job_elements = []
        for selector in job_selectors:
            elements = soup.select(selector)
            if elements:
                job_elements = elements
                self.logger.info(f"🔍 Trouvé {len(elements)} offres avec sélecteur: {selector}")
                break

        # Fallback: chercher des éléments avec titre et entreprise
        if not job_elements:
            potential_jobs = soup.find_all(['div', 'article'], class_=True)
            for elem in potential_jobs:
                title_elem = elem.find(['h3', 'h2', 'h4'])
                company_elem = elem.find(['span', 'div'], class_=re.compile(r'company|entreprise'))
                if title_elem and company_elem:
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
        pagination_selectors = ['.pagination', '.pager', '.page-navigation']
        for selector in pagination_selectors:
            pagination = soup.select_one(selector)
            if pagination:
                break

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

        # Chercher "Page 1 sur X" ou similaires
        page_patterns = [
            r'Page\s+\d+\s+sur\s+(\d+)',
            r'page\s+\d+\s+of\s+(\d+)',
            r'(\d+)\s+pages?',
            r'Page\s+(\d+)'
        ]

        text_content = soup.get_text()
        for pattern in page_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                try:
                    page_num = int(match.group(1))
                    if page_num > 1:  # Si on trouve "page 5", il y a probablement 5 pages
                        return page_num
                except (ValueError, IndexError):
                    continue

        # Estimation basée sur le nombre d'offres
        offers_count = len(self.parse_jobs_from_html(html))
        if offers_count > 0:
            # Estimation: sites d'emploi ont généralement 10-50 offres par page
            estimated_pages = max(1, min(50, (500 // offers_count)))  # Estimation conservatrice
            self.logger.warning(f"⚠️ Nombre de pages non trouvé, estimation: {estimated_pages} pages")
            return estimated_pages

        # Défaut
        self.logger.warning("⚠️ Pagination non trouvée, utilisation de 10 pages par défaut")
        return 10

    def scrape_jobs(self, max_pages: int = None, delay_min: float = 2.0, delay_max: float = 5.0) -> List[Dict[str, Any]]:
        """Scrape toutes les offres d'emploi d'Emploi.ci"""
        all_jobs = []

        # Page 1 pour déterminer le nombre total de pages
        self.logger.info("📊 Récupération du nombre total de pages...")
        html_page1 = self.scrape_page(1)

        if not html_page1:
            self.logger.error("❌ Impossible de charger la première page")
            return []

        total_pages = self.get_total_pages(html_page1)
        actual_max_pages = min(max_pages or total_pages, total_pages)

        self.logger.info(f"📈 Total pages estimé: {total_pages}, scraping: {actual_max_pages} pages")

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
        self.logger.info(f"✅ Scraping Emploi.ci terminé: {len(all_jobs)} offres au total")

        return all_jobs


def main():
    """Point d'entrée pour tests"""
    scraper = EmploiCIScraper()

    print("🇨🇮 Test Emploi.ci Scraper")
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
        print(f"   Localisation: {job['location']}")
        print(f"   Compétences: {job.get('skills', [])}")


if __name__ == '__main__':
    main()
