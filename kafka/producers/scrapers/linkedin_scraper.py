#!/usr/bin/env python3
"""
==========================================
LinkedIn Scraper - Côte d'Ivoire
==========================================
Scraper LinkedIn pour données premium - Authentification + Selenium
100-200 offres avec données enrichies (compétences, entreprise, etc.)
"""

import os
import re
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from .base_scraper import BaseJobScraperCI


class LinkedInScraper(BaseJobScraperCI):
    """Scraper LinkedIn avec authentification Selenium"""

    BASE_URL = "https://www.linkedin.com"
    LOGIN_URL = "https://www.linkedin.com/login"
    JOBS_URL = "https://www.linkedin.com/jobs/search/"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Charger le fichier .env.linkedin si présent
        self._load_linkedin_env()

        # Configuration LinkedIn
        self.linkedin_email = os.getenv('LINKEDIN_EMAIL')
        self.linkedin_password = os.getenv('LINKEDIN_PASSWORD')

        # Configuration Selenium
        self.driver = None
        self.wait = None

        # État de connexion
        self.logged_in = False

        # Statistiques spécifiques LinkedIn
        self.linkedin_stats = {
            'login_attempts': 0,
            'login_success': False,
            'pages_scrolled': 0,
            'jobs_loaded': 0
        }

    def _load_linkedin_env(self):
        """Charge les variables d'environnement depuis .env.linkedin"""
        # Chercher dans le répertoire producers (où se trouve run_scraper.py)
        env_file = Path(__file__).parent.parent / '.env.linkedin'
        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
                self.logger.info("✅ Variables LinkedIn chargées depuis .env.linkedin")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur chargement .env.linkedin: {e}")
        else:
            self.logger.info("ℹ️ Fichier .env.linkedin non trouvé")

    def setup_selenium(self) -> bool:
        """Configure le driver Selenium"""
        try:
            chrome_options = Options()

            # Mode headless pour production
            if os.getenv('SELENIUM_HEADLESS', 'true').lower() == 'true':
                chrome_options.add_argument('--headless')

            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            # Utiliser Chromium dans Docker
            chrome_options.binary_location = '/usr/bin/chromium'

            # Désactiver les images pour accélérer
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')

            # Utiliser Chromium directement (installé dans le conteneur Docker)
            from selenium.webdriver.chrome.service import Service
            service = Service(executable_path='/usr/bin/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)

            self.logger.info("✅ Selenium configuré avec succès")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur configuration Selenium: {e}")
            return False

    def linkedin_login(self) -> bool:
        """Se connecter à LinkedIn"""
        if not self.linkedin_email or not self.linkedin_password:
            self.logger.error("❌ Variables LINKEDIN_EMAIL et LINKEDIN_PASSWORD requises")
            return False

        try:
            self.linkedin_stats['login_attempts'] += 1
            self.logger.info("🔐 Tentative de connexion LinkedIn...")

            # Aller à la page de login
            self.driver.get(self.LOGIN_URL)
            time.sleep(2)

            # Remplir email
            email_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.clear()
            email_field.send_keys(self.linkedin_email)
            time.sleep(1)

            # Remplir mot de passe
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.linkedin_password)
            time.sleep(1)

            # Cliquer sur login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()

            # Attendre que la page se charge (vérifier si on est connecté)
            time.sleep(3)

            # Vérifier si connexion réussie
            if "feed" in self.driver.current_url or "jobs" in self.driver.current_url:
                self.logged_in = True
                self.linkedin_stats['login_success'] = True
                self.logger.info("✅ Connexion LinkedIn réussie")
                return True
            else:
                # Vérifier si on a une erreur
                try:
                    error_elem = self.driver.find_element(By.CLASS_NAME, "alert-error")
                    self.logger.error(f"❌ Erreur LinkedIn: {error_elem.text}")
                except NoSuchElementException:
                    self.logger.error("❌ Connexion échouée (raison inconnue)")

                return False

        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la connexion: {e}")
            return False

    def search_jobs_linkedin(self, keywords: str = "informatique OR tech OR developpeur",
                           location: str = "Côte d'Ivoire", max_jobs: int = 100) -> List[Dict[str, Any]]:
        """Rechercher des offres sur LinkedIn"""
        if not self.logged_in:
            self.logger.error("❌ Pas connecté à LinkedIn")
            return []

        try:
            # Construire l'URL de recherche
            search_url = f"{self.JOBS_URL}?keywords={keywords}&location={location}&f_TPR=r604800"  # 7 derniers jours
            self.logger.info(f"🔍 Recherche LinkedIn: {search_url}")

            self.driver.get(search_url)
            time.sleep(3)

            jobs = []
            jobs_seen = set()
            scroll_attempts = 0
            max_scrolls = 10

            while len(jobs) < max_jobs and scroll_attempts < max_scrolls:
                try:
                    # Attendre que les offres se chargent
                    job_cards = self.wait.until(
                        EC.presence_of_all_elements_located((By.CLASS_NAME, "job-card-container"))
                    )

                    self.logger.info(f"📄 {len(job_cards)} offres visibles sur la page")

                    # Parser chaque offre
                    for job_card in job_cards:
                        try:
                            job_data = self.parse_linkedin_job_card(job_card)
                            if job_data and job_data['job_id'] not in jobs_seen:
                                jobs.append(job_data)
                                jobs_seen.add(job_data['job_id'])

                                if len(jobs) >= max_jobs:
                                    break

                        except Exception as e:
                            self.logger.debug(f"Erreur parsing offre: {e}")
                            continue

                    # Scroll pour charger plus d'offres
                    if len(jobs) < max_jobs:
                        self.logger.info("📜 Scroll pour charger plus d'offres...")
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        scroll_attempts += 1
                        self.linkedin_stats['pages_scrolled'] += 1

                except TimeoutException:
                    self.logger.warning("⏰ Timeout en attendant les offres")
                    break

            self.linkedin_stats['jobs_loaded'] = len(jobs)
            self.logger.info(f"✅ {len(jobs)} offres LinkedIn collectées")

            return jobs

        except Exception as e:
            self.logger.error(f"❌ Erreur recherche LinkedIn: {e}")
            return []

    def parse_linkedin_job_card(self, job_card) -> Optional[Dict[str, Any]]:
        """Parser une carte d'offre LinkedIn"""
        try:
            # Extraire le titre (nouvelle structure LinkedIn)
            title_elem = job_card.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
            title = title_elem.text.strip()

            # Extraire l'entreprise
            company_elem = job_card.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle span")
            company = company_elem.text.strip()

            # Extraire la localisation (premier élément de la métadonnée)
            location_elem = job_card.find_element(By.CSS_SELECTOR, ".job-card-container__metadata-wrapper li")
            location_raw = location_elem.text.strip()
            location = self.clean_location_ci(location_raw)

            # Extraire les métadonnées (date, type d'emploi)
            metadata_items = job_card.find_elements(By.CLASS_NAME, "job-card-container__metadata-item")
            posted_date = ""
            job_type = "CDI"

            for item in metadata_items:
                text = item.text.strip()
                if any(word in text.lower() for word in ['minute', 'heure', 'jour', 'semaine']):
                    posted_date = text
                elif any(word in text.lower() for word in ['cdi', 'cdd', 'stage', 'freelance']):
                    job_type = text

            # Extraire le lien de l'offre
            link_elem = job_card.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
            job_url = link_elem.get_attribute("href") or ""

            # Créer l'ID unique
            job_id = self.create_job_id('linkedin', f"{title}_{company}_{posted_date}")

            # Analyse du titre pour compétences
            detected_skills = self._extract_linkedin_skills(title + " " + company)

            # Structure de données enrichie
            job_data = {
                'job_id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'description': title,  # Sera enrichi lors du détail
                'contract_type': job_type,
                'job_type': job_type,
                'source': 'linkedin_ci',
                'source_url': job_url,
                'posted_date': posted_date,
                'scraped_at': datetime.now().isoformat(),
                'country': 'Côte d\'Ivoire',

                # Données LinkedIn spécifiques
                'linkedin_premium': True,
                'skills': detected_skills,
                'remote_option': self._detect_remote_option(title),
                'education_level': None,
                'experience_years': None,
                'industry': self._guess_industry(title, company),
                'seniority_level': self._guess_seniority(title),

                # Métadonnées
                'scraped_with_selenium': True,
                'linkedin_search_keywords': None,  # Sera rempli lors de la recherche
            }

            return job_data

        except Exception as e:
            self.logger.debug(f"Erreur parsing carte LinkedIn: {e}")
            return None

    def get_job_details_linkedin(self, job_url: str) -> Optional[Dict[str, Any]]:
        """Récupérer les détails complets d'une offre LinkedIn"""
        if not self.logged_in or not job_url:
            return None

        try:
            self.logger.debug(f"🔍 Récupération détails: {job_url}")
            self.driver.get(job_url)
            time.sleep(3)

            # Extraire la description complète
            try:
                desc_elem = self.driver.find_element(By.CLASS_NAME, "jobs-description-content__text")
                description = desc_elem.text.strip()
            except NoSuchElementException:
                description = ""

            # Extraire les compétences requises
            skills = []
            try:
                skills_section = self.driver.find_element(By.CLASS_NAME, "job-details-skill-match-status-list")
                skill_elements = skills_section.find_elements(By.TAG_NAME, "li")
                skills = [skill.text.strip() for skill in skill_elements if skill.text.strip()]
            except NoSuchElementException:
                pass

            # Extraire le salaire si disponible
            salary_info = None
            try:
                salary_elem = self.driver.find_element(By.CLASS_NAME, "jobs-description-content__salary")
                salary_text = salary_elem.text.strip()
                salary_info = self.clean_salary_ci(salary_text)
            except NoSuchElementException:
                pass

            # Extraire le type d'emploi détaillé
            job_type = "CDI"
            try:
                criteria_section = self.driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__job-insight")
                criteria_text = criteria_section.text
                if "temps plein" in criteria_text.lower():
                    job_type = "CDI"
                elif "temps partiel" in criteria_text.lower():
                    job_type = "CDD"
            except NoSuchElementException:
                pass

            return {
                'description': description,
                'skills': skills,
                'salary_amount': salary_info.get('amount') if salary_info else None,
                'salary_currency': salary_info.get('currency') if salary_info else 'FCFA',
                'salary_period': salary_info.get('period') if salary_info else 'month',
                'job_type': job_type
            }

        except Exception as e:
            self.logger.debug(f"Erreur récupération détails LinkedIn: {e}")
            return None

    def _extract_linkedin_skills(self, text: str) -> List[str]:
        """Extraction spécialisée des compétences LinkedIn"""
        detected_skills = []
        text_lower = text.lower()

        # Compétences techniques avancées
        linkedin_skills = {
            'Python': ['python', 'django', 'flask'],
            'Java': ['java', 'spring', 'hibernate'],
            'JavaScript': ['javascript', 'react', 'angular', 'vue', 'node.js'],
            'PHP': ['php', 'laravel', 'symfony'],
            'C#': ['c#', '.net', 'asp.net'],
            'C++': ['c++', 'c plus plus'],
            'Go': ['go', 'golang'],
            'Rust': ['rust'],
            'Scala': ['scala'],
            'Kotlin': ['kotlin'],
            'Swift': ['swift'],
            'TypeScript': ['typescript'],
            'SQL': ['sql', 'mysql', 'postgresql', 'oracle', 'mongodb'],
            'NoSQL': ['mongodb', 'cassandra', 'redis', 'elasticsearch'],
            'AWS': ['aws', 'amazon web services', 'ec2', 's3', 'lambda'],
            'Azure': ['azure', 'microsoft azure'],
            'GCP': ['gcp', 'google cloud', 'firebase'],
            'Docker': ['docker', 'kubernetes', 'k8s', 'container'],
            'DevOps': ['devops', 'ci/cd', 'jenkins', 'gitlab ci'],
            'Machine Learning': ['machine learning', 'ml', 'ai', 'tensorflow', 'pytorch'],
            'Data Science': ['data science', 'pandas', 'numpy', 'scipy'],
            'Big Data': ['hadoop', 'spark', 'kafka', 'hive'],
            'React': ['react', 'redux'],
            'Angular': ['angular'],
            'Vue.js': ['vue'],
            'Git': ['git', 'github', 'gitlab'],
            'Agile': ['agile', 'scrum', 'kanban'],
            'SEO': ['seo', 'sem'],
            'Marketing Digital': ['marketing digital', 'google ads', 'facebook ads']
        }

        # Compétences métier LinkedIn
        business_skills = {
            'Product Management': ['product manager', 'product owner'],
            'Project Management': ['project manager', 'chef de projet'],
            'Business Analysis': ['business analyst', 'analyste métier'],
            'UX/UI Design': ['ux', 'ui', 'designer', 'design'],
            'Data Analysis': ['data analyst', 'analyste de données'],
            'Cybersecurity': ['cybersecurity', 'security', 'sécurité'],
            'Network Administration': ['network', 'réseau', 'sysadmin'],
            'Database Administration': ['dba', 'database admin'],
            'Technical Writing': ['technical writer', 'rédacteur technique'],
            'Quality Assurance': ['qa', 'quality assurance', 'testing'],
            'Sales Engineering': ['sales engineer', 'ingénieur commercial'],
            'Customer Success': ['customer success', 'succès client'],
            'HR Business Partner': ['hrbp', 'hr business partner'],
            'Talent Acquisition': ['talent acquisition', 'recrutement'],
            'Training': ['formation', 'training'],
            'Legal': ['legal', 'juriste', 'avocat'],
            'Finance': ['finance', 'comptabilité', 'accounting'],
            'Operations': ['operations', 'opérations']
        }

        # Chercher toutes les compétences
        for skill_dict in [linkedin_skills, business_skills]:
            for skill, keywords in skill_dict.items():
                if any(keyword in text_lower for keyword in keywords):
                    detected_skills.append(skill)

        return list(set(detected_skills))

    def _detect_remote_option(self, title: str) -> bool:
        """Détection spécialisée du télétravail LinkedIn"""
        title_lower = title.lower()
        remote_keywords = [
            'remote', 'télétravail', 'teletravail', 'home office',
            'work from home', 'wfh', 'remote work', 'distanciel',
            '100% remote', 'full remote'
        ]
        return any(keyword in title_lower for keyword in remote_keywords)

    def scrape_jobs(self, max_pages: int = None, delay_min: float = 2.0, delay_max: float = 5.0,
                   keywords: str = None, location: str = "Côte d'Ivoire", max_jobs: int = None) -> List[Dict[str, Any]]:
        """Scraper principal LinkedIn"""
        all_jobs = []

        # Configuration par défaut adaptée à la Côte d'Ivoire
        if not keywords:
            # Mots-clés populaires en Côte d'Ivoire
            keywords = ("informatique OR tech OR developpeur OR ingénieur OR data OR digital "
                       "OR marketing OR finance OR commercial")

        # Gérer la compatibilité avec l'interface commune
        actual_max_jobs = max_jobs or (max_pages * 20 if max_pages else 50)  # Estimation: ~20 offres par "page"

        try:
            # Setup Selenium
            if not self.setup_selenium():
                self.logger.error("❌ Impossible de configurer Selenium")
                return []

            # Connexion LinkedIn
            if not self.linkedin_login():
                self.logger.error("❌ Impossible de se connecter à LinkedIn")
                return []

            # Recherche d'offres
            jobs = self.search_jobs_linkedin(keywords, location, actual_max_jobs)

            # Enrichir avec les détails (optionnel - prend du temps)
            if jobs and os.getenv('LINKEDIN_ENRICH_DETAILS', 'false').lower() == 'true':
                self.logger.info("🔍 Enrichissement des détails d'offres...")
                for i, job in enumerate(jobs[:10]):  # Limiter à 10 pour éviter les blocages
                    if job.get('source_url'):
                        details = self.get_job_details_linkedin(job['source_url'])
                        if details:
                            job.update(details)
                            self.logger.debug(f"✅ Détails enrichis pour offre {i+1}")

            all_jobs.extend(jobs)

        except Exception as e:
            self.logger.error(f"❌ Erreur scraping LinkedIn: {e}")
        finally:
            # Cleanup
            if self.driver:
                try:
                    self.driver.quit()
                    self.logger.info("🧹 Driver Selenium fermé")
                except Exception as e:
                    self.logger.warning(f"Erreur fermeture driver: {e}")

        self.logger.info(f"✅ Scraping LinkedIn terminé: {len(all_jobs)} offres")
        return all_jobs


def main():
    """Point d'entrée pour tests"""
    scraper = LinkedInScraper()

    print("🔗 Test LinkedIn Scraper")
    print("=" * 50)
    print("⚠️  ATTENTION: Nécessite des credentials LinkedIn")
    print("   Variables: LINKEDIN_EMAIL, LINKEDIN_PASSWORD")
    print()

    # Test rapide (10 offres)
    jobs = scraper.run(max_jobs=10)

    print(f"\n📊 Résultats:")
    print(f"   Offres trouvées: {len(jobs)}")
    print(f"   Connexion réussie: {scraper.linkedin_stats['login_success']}")
    print(f"   Pages scrolled: {scraper.linkedin_stats['pages_scrolled']}")
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
        print(f"   Premium: {job.get('linkedin_premium', False)}")


if __name__ == '__main__':
    main()
