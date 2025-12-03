# 🇨🇮 Scrapers Côte d'Ivoire - Architecture

## Vue d'ensemble

Cette architecture de scraping a été adaptée au contexte ivoirien pour collecter des offres d'emploi depuis les principales plateformes locales.

## 📊 Sources de Données

| Scraper | Site | Volume Estimé | Complexité | Statut |
|---------|------|---------------|------------|--------|
| **educarriere** | `emploi.educarriere.ci` | **809 offres** | ⭐⭐⭐⭐⭐ Facile | ✅ Implémenté |
| **macarrierepro** | `macarrierepro.net` | **+300 offres** | ⭐⭐⭐⭐ Moyenne | ✅ Implémenté |
| **emploi_ci** | `emploi.ci` | **500-1000 offres** | ⭐⭐⭐ Moyenne | ✅ Implémenté |
| **linkedin** | `linkedin.com` | **100-200 offres** | ⭐⭐ Élevée | ✅ Implémenté |

## 🏗️ Architecture Technique

```
kafka/producers/
├── scrapers/
│   ├── base_scraper.py          # Classe abstraite commune
│   ├── educarriere_scraper.py   # 809 offres - Parsing simple
│   ├── macarrierepro_scraper.py # +300 offres - Interface moderne
│   ├── emploi_ci_scraper.py     # Volume principal - Adaptable
│   └── linkedin_scraper.py      # Données premium - Selenium
├── utils/
│   └── anti_ban.py             # Rotation User-Agent, proxies
└── run_scraper.py              # Orchestrateur principal
```

## 🔧 Fonctionnalités Communes

### BaseScraperCI (`base_scraper.py`)

**Anti-ban & Rate Limiting :**
- Rotation automatique des User-Agents
- Délais aléatoires entre requêtes (2-5 secondes)
- Gestion des erreurs et retry logic

**Normalisation des Données :**
- **Localisation** : Standardisation des villes ivoiriennes (Abidjan, Bouaké, etc.)
- **Salaire** : Parsing des montants en FCFA avec périodes (mois, année)
- **Compétences** : Extraction automatique des skills techniques/métier
- **ID unique** : Génération déterministe des identifiants

**Intégration :**
- **Kafka** : Envoi structuré vers `job-offers-raw`
- **MinIO** : Sauvegarde HTML dans `scraped-jobs/`
- **Logging** : Suivi détaillé avec métriques

## 📋 Scrapers Spécifiques

### 1. EducarriereScraper

**Source** : https://emploi.educarriere.ci/nos-offres
**Points forts** :
- **809 offres** actives
- Structure HTML très claire
- Pagination simple (29 pages)
- Données bien organisées (Code, Date, Type)

**Données extraites** :
- Code unique, titre, dates
- Type d'emploi (CDI, Stage, etc.)
- Description basique
- Compétences déduites du titre

### 2. MacarriereproScraper

**Source** : https://macarrierepro.net/
**Points forts** :
- **+300 offres** avec salaires affichés
- Interface moderne avec catégories
- Données enrichies (entreprise, salaire, localisation)

**Données extraites** :
- Titre, entreprise, localisation
- **Salaire en FCFA** (parsing avancé)
- Compétences par catégorie
- Secteur d'activité et niveau d'expérience

### 3. EmploiCIScraper

**Source** : https://www.emploi.ci/
**Points forts** :
- Volume principal estimé (500-1000 offres)
- Architecture adaptable à différentes structures
- Extraction intelligente des compétences

**Données extraites** :
- Parsing flexible selon la structure du site
- Détection automatique des compétences
- Analyse sémantique du titre et description
- Classification secteur/industrie

### 4. LinkedInScraper ⭐ **Premium**

**Source** : https://www.linkedin.com/jobs/
**Points forts** :
- **Données premium** : profils détaillés, compétences validées
- **Authentification officielle** : accès aux offres réservées
- **Réseau professionnel** : données de qualité supérieure
- **Filtrage avancé** : recherche ciblée Côte d'Ivoire

**Configuration requise** :
```bash
# Copier le fichier d'exemple
cp config/linkedin_credentials.example kafka/producers/.env.linkedin

# Éditer avec vos vraies credentials
nano kafka/producers/.env.linkedin
```

**Variables d'environnement** :
- `LINKEDIN_EMAIL` : Email LinkedIn
- `LINKEDIN_PASSWORD` : Mot de passe LinkedIn
- `SELENIUM_HEADLESS=true` : Mode headless (production)
- `LINKEDIN_ENRICH_DETAILS=false` : Enrichissement détails (lent)

**Données extraites** :
- **Compétences validées** par LinkedIn
- **Profils entreprise complets**
- **Informations salariales** quand disponibles
- **Niveau d'expérience** et secteur
- **Options télétravail** explicites
- **Dates de publication précises**

**⚠️ Considérations importantes** :
- **Rate limiting strict** : LinkedIn limite les connexions
- **Authentification requise** : Compte LinkedIn valide nécessaire
- **Délais anti-ban** : Attendre 2-3 secondes entre actions
- **IP rotation** recommandée pour usage intensif

## 🚀 Utilisation

### Lancement Individuel

```bash
# Test rapide (2 pages)
python kafka/producers/run_scraper.py --scraper educarriere --max-pages 2 --verbose

# Scraping complet
python kafka/producers/run_scraper.py --scraper macarrierepro --max-pages 10

# LinkedIn (nécessite credentials)
python kafka/producers/run_scraper.py --scraper linkedin --max-jobs 25
```

### Lancement Tous Scrapers

```bash
# Mode test (2 pages chacun)
python kafka/producers/run_scraper.py --scraper all --max-pages 2

# Production (pages illimitées)
python kafka/producers/run_scraper.py --scraper all
```

### Options Disponibles

```bash
--scraper {all,educarriere,macarrierepro,emploi_ci}  # Scraper à lancer
--max-pages INT                                     # Pages max par scraper
--delay-min FLOAT                                   # Délai min entre requêtes
--delay-max FLOAT                                   # Délai max entre requêtes
--verbose                                           # Mode debug
```

## 📊 Métriques et Monitoring

Chaque scraper fournit :
- **jobs_scraped** : Nombre d'offres collectées
- **jobs_sent_kafka** : Offres envoyées à Kafka
- **jobs_saved_minio** : HTML sauvegardé dans MinIO
- **errors** : Nombre d'erreurs
- **duration_seconds** : Temps d'exécution

## 🔧 Configuration

### Variables d'Environnement

```bash
# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:29092

# MinIO
MINIO_ENDPOINT=minio:9000

# Scraping général
SCRAPER_DELAY_MIN=2.0
SCRAPER_DELAY_MAX=5.0

# LinkedIn (si utilisé)
LINKEDIN_EMAIL=votre_email@linkedin.com
LINKEDIN_PASSWORD=votre_mot_de_passe
SELENIUM_HEADLESS=true
LINKEDIN_ENRICH_DETAILS=false
```

### Adaptation aux Sites

Pour ajouter un nouveau site ivoirien :

1. **Créer** `nouveau_scraper.py` héritant de `BaseJobScraperCI`
2. **Implémenter** `scrape_page()` et `parse_jobs_from_html()`
3. **Ajouter** au dictionnaire dans `run_scraper.py`
4. **Tester** avec `--scraper nouveau --max-pages 2`

## 🎯 Points d'Amélioration Futurs

### Performance
- **Multithreading** pour scraper plusieurs pages en parallèle
- **Cache intelligent** pour éviter re-scraping
- **Proxy rotation** pour volumes élevés

### Données
- **Enrichissement NLP** avec spaCy pour extraction compétences
- **Géocodage** des localisations pour cartes
- **Déduplication** inter-sources

### Monitoring
- **Dashboard Grafana** pour métriques temps réel
- **Alertes automatiques** sur échecs
- **Rapports quotidiens** d'activité

## 📞 Support

**Test rapide** : Lancez toujours avec `--max-pages 2` pour valider
**Logs** : Vérifiez `/app/logs/scrapers_orchestrator.log`
**Debug** : Utilisez `--verbose` pour détails complets

### 🔒 Bonnes Pratiques LinkedIn

**Sécurité du compte** :
- Utilisez un compte LinkedIn dédié au scraping
- Activez la 2FA si possible
- Évitez de scraper pendant les heures de bureau
- Respectez les limites LinkedIn (max 100-200 offres/jour)

**Performance** :
- `SELENIUM_HEADLESS=true` en production
- Commencez par `LINKEDIN_ENRICH_DETAILS=false`
- Limitez à 25-50 offres par exécution
- Attendez 2-3 secondes entre les actions

**Dépannage** :
- Si blocage IP : Utilisez un VPN ou proxy
- Si compte suspendu : Créez un nouveau compte
- Vérifiez les logs Selenium pour les erreurs

---

**Total estimé** : **1800-2500 offres/jour** avec les 4 scrapers actifs 🎯
