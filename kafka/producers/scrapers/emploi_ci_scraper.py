#!/usr/bin/env python3
"""
==========================================
GoAfricaOnline Scraper - Côte d'Ivoire
==========================================
Scraper pour https://www.goafricaonline.com/ci/emploi
Remplace Emploi.ci qui est devenu inaccessible
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseJobScraperCI


class EmploiCIScraper(BaseJobScraperCI):
    """
    Scraper GoAfricaOnline (page emploi) – utilisé en remplacement d'Emploi.ci.
    Le nom de classe reste inchangé pour compatibilité avec les DAGs/pipelines existants.
    """

    BASE_URL = "https://www.goafricaonline.com"
    OFFERS_URL = "https://www.goafricaonline.com/ci/emploi"

    def scrape_page(self, page: int = 1) -> str:
        """Charge une page de résultats GoAfricaOnline."""
        possible_urls = [
            f"{self.OFFERS_URL}?page={page}",
            f"{self.OFFERS_URL}/{page}",
            f"{self.BASE_URL}/ci/emploi?page={page}",
        ]

        for url in possible_urls:
            self.logger.info(f"📄 Tentative scraping page {page}: {url}")
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # La page principale contient généralement beaucoup de contenu (>5k chars)
                if len(response.text) > 5000:
                    self.logger.info(f"✅ URL valide trouvée: {url}")
                    return response.text
            except requests.RequestException as e:
                self.logger.debug(f"❌ URL {url} échouée: {e}")
                continue

        if page % 3 == 0:
            self.rotate_user_agent()

        self.logger.error(f"❌ Aucune URL valide trouvée pour la page {page}")
        return ""

    def parse_job_offer(self, job_element) -> Optional[Dict[str, Any]]:
        """Parse une offre GoAfricaOnline à partir d'un bloc HTML."""
        try:
            title_elem = None
            for selector in [
                'h3 a', 'h2 a', '.title a', '.titre a', 'h3', 'h2', '.title', '.titre'
            ]:
                title_elem = job_element.select_one(selector)
                if title_elem:
                    break

            # Fallback sur un lien contenant /ci/emploi/
            if not title_elem:
                link_candidate = job_element.find('a', href=re.compile(r'/ci/emploi/'))
                if link_candidate:
                    title_elem = link_candidate

            if not title_elem:
                return None

            if title_elem.name == 'a':
                title = title_elem.get_text(strip=True)
                offer_url = title_elem.get('href', '')
            else:
                title = title_elem.get_text(strip=True)
                link_elem = title_elem.find_parent('a') or job_element.find('a')
                offer_url = link_elem.get('href', '') if link_elem else ''

            if not title:
                return None

            if offer_url and not offer_url.startswith('http'):
                offer_url = f"{self.BASE_URL}{offer_url}"

            # Entreprise
            company_elem = None
            for selector in ['.company', '.entreprise', '.employer', '.societe', '.company-name']:
                company_elem = job_element.select_one(selector)
                if company_elem:
                    break
            company = company_elem.get_text(strip=True) if company_elem else "Entreprise non spécifiée"

            # Localisation
            location_elem = None
            for selector in ['.location', '.ville', '.lieu', '.localisation', '.place', '.zone']:
                location_elem = job_element.select_one(selector)
                if location_elem:
                    break
            location_raw = location_elem.get_text(strip=True) if location_elem else "Côte d'Ivoire"
            location = self.clean_location_ci(location_raw)

            # Salaire
            salary_elem = None
            for selector in ['.salary', '.salaire', '.remuneration', '.pay']:
                salary_elem = job_element.select_one(selector)
                if salary_elem:
                    break
            salary_text = salary_elem.get_text(strip=True) if salary_elem else ""
            salary_info = self.clean_salary_ci(salary_text)

            # Date de publication
            date_elem = None
            for selector in ['.date', '.posted-date', '.publish-date', '.time', '.meta-date']:
                date_elem = job_element.select_one(selector)
                if date_elem:
                    break
            posted_date = self._clean_posted_date(date_elem.get_text(strip=True) if date_elem else "")

            # Type de contrat
            contract_elem = None
            for selector in ['.contract', '.type', '.job-type', '.contract-type', '.tag']:
                contract_elem = job_element.select_one(selector)
                if contract_elem:
                    break
            contract_type = self._detect_contract_type(contract_elem.get_text(strip=True) if contract_elem else "")

            # Description courte
            desc_elem = None
            for selector in ['.description', '.desc', '.summary', '.excerpt', '.preview']:
                desc_elem = job_element.select_one(selector)
                if desc_elem:
                    break
            description = desc_elem.get_text(strip=True) if desc_elem else title

            job_id = self.create_job_id('goafricaonline', f"{title}_{company}_{posted_date}")
            detected_skills = self._extract_skills_from_text(f"{title} {description}")

            job_data = {
                'job_id': job_id,
                'title': title,
                'company': company,
                'location': location,
                # Conserver le HTML brut pour sauvegarde MinIO / re-parsing
                'html_content': str(job_element),
                'description': description,
                'contract_type': contract_type,
                'job_type': contract_type,
                'source': 'goafricaonline',
                'source_url': offer_url or self.OFFERS_URL,
                'posted_date': posted_date,
                'scraped_at': datetime.now().isoformat(),
                'country': "Côte d'Ivoire",
                'salary_amount': salary_info.get('amount'),
                'salary_currency': salary_info.get('currency'),
                'salary_period': salary_info.get('period'),
                'skills': detected_skills,
                'remote_option': self._detect_remote_option(f"{title} {description}"),
                'education_level': None,
                'experience_years': None,
                'industry': self._guess_industry(title, company),
                'seniority_level': self._guess_seniority(title),
                'raw_salary_text': salary_text,
            }

            return job_data

        except Exception as e:
            self.logger.error(f"❌ Erreur parsing offre: {e}")
            return None

    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extrait les compétences du texte (tech + métier)."""
        detected_skills = []
        text_lower = text.lower()

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

        for skill, keywords in {**tech_skills, **business_skills}.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_skills.append(skill)

        return list(set(detected_skills))

    def _detect_remote_option(self, text: str) -> bool:
        """Détecte si le poste mentionne le télétravail."""
        text_lower = text.lower()
        remote_keywords = [
            'remote', 'télétravail', 'teletravail', 'home office',
            'travail à distance', 'remote work', 'work from home'
        ]
        return any(keyword in text_lower for keyword in remote_keywords)

    def _guess_industry(self, title: str, company: str) -> str:
        """Déduit le secteur d'activité."""
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
        """Déduit le niveau d'expérience."""
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

    def _clean_posted_date(self, text: str) -> str:
        """Nettoie la date affichée (ex: 'Posté le 28 nov. 2025')."""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'(?i)post[ée] le ', '', text).strip()
        return text

    def _detect_contract_type(self, text: str) -> str:
        """Détecte un type de contrat à partir du texte."""
        if not text:
            return 'Non précisé'
        text_upper = text.upper()
        if 'CDI' in text_upper:
            return 'CDI'
        if 'CDD' in text_upper:
            return 'CDD'
        if 'STAGE' in text_upper or 'INTERIM' in text_upper:
            return 'Stage'
        if 'FREELANCE' in text_upper or 'INDEPENDANT' in text_upper:
            return 'Freelance'
        return text.strip() or 'Non précisé'

    def parse_jobs_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse toutes les offres présentes sur une page HTML."""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        jobs = []

        job_selectors = [
            '.job-card',
            '.emploi-card',
            '.offer-card',
            '.annonce-item',
            '.annonce',
            '.job-item',
            'article.offer',
            'article',
            'li.offre',
            '.list-item',
        ]

        job_elements = []
        for selector in job_selectors:
            elements = soup.select(selector)
            if elements:
                job_elements = elements
                self.logger.info(f"🔍 Trouvé {len(elements)} offres avec sélecteur: {selector}")
                break

        # Fallback: rechercher des blocs contenant un lien vers /ci/emploi/
        if not job_elements:
            candidates = soup.find_all(['div', 'article', 'li'], class_=True)
            for elem in candidates:
                link = elem.find('a', href=re.compile(r'/ci/emploi/'))
                title = elem.find(['h2', 'h3', 'h4'])
                if link and title:
                    job_elements.append(elem)

        self.logger.info(f"🔍 Nombre total de blocs candidats: {len(job_elements)}")

        seen_ids = set()
        for job_elem in job_elements:
            job_data = self.parse_job_offer(job_elem)
            if job_data and job_data['job_id'] not in seen_ids:
                jobs.append(job_data)
                seen_ids.add(job_data['job_id'])

        # Si aucun bloc n'est détecté, on tente de récupérer directement les liens
        if not jobs:
            for link in soup.select('a[href*="/ci/emploi/"]'):
                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                fake_block = link.parent or link
                job_data = self.parse_job_offer(fake_block)
                if job_data and job_data['job_id'] not in seen_ids:
                    jobs.append(job_data)
                    seen_ids.add(job_data['job_id'])

        return jobs

    def get_total_pages(self, html: str) -> int:
        """Détermine le nombre total de pages de résultats."""
        if not html:
            return 1

        soup = BeautifulSoup(html, 'html.parser')
        pagination = None
        for selector in ['.pagination', '.pager', '.page-navigation', '.pagination-list']:
            pagination = soup.select_one(selector)
            if pagination:
                break

        if pagination:
            page_links = pagination.find_all(['a', 'span'], string=re.compile(r'\d+'))
            page_numbers = []
            for link in page_links:
                try:
                    page_numbers.append(int(link.get_text(strip=True)))
                except ValueError:
                    continue
            if page_numbers:
                return max(page_numbers)

        # Recherche d'un motif "Page 1 sur X"
        text_content = soup.get_text()
        match = re.search(r'Page\\s+\\d+\\s+sur\\s+(\\d+)', text_content, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass

        # Estimation si non trouvé
        offers_count = len(self.parse_jobs_from_html(html))
        if offers_count > 0:
            estimated_pages = max(1, min(30, (400 // max(1, offers_count))))
            self.logger.warning(f"⚠️ Nombre de pages non trouvé, estimation: {estimated_pages} pages")
            return estimated_pages

        self.logger.warning("⚠️ Pagination non trouvée, utilisation de 5 pages par défaut")
        return 5

    def scrape_jobs(self, max_pages: int = None, delay_min: float = 2.0, delay_max: float = 5.0) -> List[Dict[str, Any]]:
        """Scrape les offres d'emploi de GoAfricaOnline."""
        all_jobs: List[Dict[str, Any]] = []

        self.logger.info("📊 Récupération du nombre total de pages...")
        html_page1 = self.scrape_page(1)

        if not html_page1:
            self.logger.error("❌ Impossible de charger la première page")
            return []

        total_pages = self.get_total_pages(html_page1)
        actual_max_pages = min(max_pages or total_pages, total_pages)

        self.logger.info(f"📈 Total pages estimé: {total_pages}, scraping: {actual_max_pages} pages")

        jobs_page1 = self.parse_jobs_from_html(html_page1)
        all_jobs.extend(jobs_page1)
        self.logger.info(f"📄 Page 1: {len(jobs_page1)} offres trouvées")

        for page in range(2, actual_max_pages + 1):
            self.logger.info(f"🔄 Page {page}/{actual_max_pages}")
            self.wait_random(delay_min, delay_max)

            html = self.scrape_page(page)
            if not html:
                self.logger.warning(f"⚠️ Page {page} ignorée")
                continue

            jobs = self.parse_jobs_from_html(html)
            all_jobs.extend(jobs)
            self.logger.info(f"📄 Page {page}: {len(jobs)} offres trouvées (Total: {len(all_jobs)})")

        self.logger.info(f"✅ Scraping GoAfricaOnline terminé: {len(all_jobs)} offres au total")
        return all_jobs


def main():
    """Point d'entrée pour tests"""
    scraper = EmploiCIScraper()

    print("🇨🇮 Test GoAfricaOnline Scraper")
    print("=" * 50)

    # Test rapide (2 pages) – run() retourne des stats, pas la liste des offres
    stats = scraper.run(max_pages=2, delay_min=1.0, delay_max=2.0)

    print(f"\n📊 Résultats:")
    print(f"   Offres trouvées: {stats.get('jobs_scraped')}")
    print(f"   Envoyées à Kafka: {stats.get('jobs_sent_kafka')}")
    print(f"   Sauvegardées MinIO: {stats.get('jobs_saved_minio')}")
    print(f"   Erreurs: {stats.get('errors')}")
    print(f"   Durée (s): {stats.get('duration_seconds')}")


if __name__ == '__main__':
    main()
