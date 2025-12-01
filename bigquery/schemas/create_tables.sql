-- ============================================
-- DIMENSIONS
-- ============================================

-- Dim_Entreprise
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Dim_Entreprise` (
  entreprise_id STRING NOT NULL,
  nom_entreprise STRING,
  secteur_id STRING,
  taille_entreprise STRING,
  site_web STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) OPTIONS(
  description="Dimension des entreprises"
);

-- Dim_Localisation
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Dim_Localisation` (
  localisation_id STRING NOT NULL,
  ville STRING,
  code_postal STRING,
  region STRING,
  departement STRING,
  pays STRING DEFAULT 'France',
  latitude FLOAT64,
  longitude FLOAT64,
  created_at TIMESTAMP
) OPTIONS(
  description="Dimension géographique"
);

-- Dim_Competence
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Dim_Competence` (
  competence_id STRING NOT NULL,
  nom_competence STRING,
  categorie STRING,
  niveau_demande STRING,
  popularite_score FLOAT64,
  created_at TIMESTAMP
) OPTIONS(
  description="Catalogue des compétences"
);

-- Dim_Secteur
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Dim_Secteur` (
  secteur_id STRING NOT NULL,
  nom_secteur STRING,
  categorie_parent STRING,
  description STRING,
  created_at TIMESTAMP
) OPTIONS(
  description="Secteurs d'activité"
);

-- ============================================
-- TABLES DE FAITS
-- ============================================

-- Fact_OffresEmploi
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Fact_OffresEmploi` (
  offre_id STRING NOT NULL,
  titre_poste STRING,
  entreprise_id STRING,
  localisation_id STRING,
  secteur_id STRING,
  
  type_contrat STRING,
  niveau_experience STRING,
  teletravail BOOLEAN,
  taux_teletravail INT64,
  
  salaire_min FLOAT64,
  salaire_max FLOAT64,
  devise STRING DEFAULT 'EUR',
  
  competences ARRAY<STRING>,
  competences_ids ARRAY<STRING>,
  
  source_site STRING,
  url_offre STRING,
  date_publication DATE,
  date_expiration DATE,
  scraped_at TIMESTAMP,
  last_updated TIMESTAMP,
  
  statut STRING,
  nombre_vues INT64,
  nombre_candidatures INT64
)
PARTITION BY date_publication
CLUSTER BY entreprise_id, localisation_id, secteur_id
OPTIONS(
  description="Table de faits des offres d'emploi"
);

-- Fact_CVs
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Fact_CVs` (
  cv_id STRING NOT NULL,
  
  annees_experience INT64,
  niveau_etudes STRING,
  domaine_etudes STRING,
  
  localisation_souhaitee_id STRING,
  secteur_souhaite_id STRING,
  salaire_souhaite FLOAT64,
  type_contrat_souhaite STRING,
  teletravail_souhaite BOOLEAN,
  
  competences ARRAY<STRING>,
  competences_ids ARRAY<STRING>,
  certifications ARRAY<STRING>,
  langues ARRAY<STRUCT<langue STRING, niveau STRING>>,
  
  source_site STRING,
  url_cv STRING,
  scraped_at TIMESTAMP,
  last_updated TIMESTAMP,
  
  disponibilite STRING,
  statut STRING
)
PARTITION BY DATE(scraped_at)
CLUSTER BY localisation_souhaitee_id, secteur_souhaite_id
OPTIONS(
  description="Table de faits des CVs candidats"
);

-- ============================================
-- MONITORING & LOGS
-- ============================================

-- Logs_Processing
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Logs_Processing` (
  log_id STRING NOT NULL,
  
  job_name STRING,
  job_type STRING,
  execution_id STRING,
  
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  duration_seconds INT64,
  
  statut STRING,
  records_processed INT64,
  records_success INT64,
  records_failed INT64,
  
  error_message STRING,
  error_stack_trace STRING,
  
  environment STRING,
  spark_app_id STRING,
  airflow_dag_id STRING,
  airflow_task_id STRING,
  
  memory_used_mb FLOAT64,
  cpu_time_seconds FLOAT64
)
PARTITION BY DATE(start_time)
CLUSTER BY job_name, statut
OPTIONS(
  description="Logs d'exécution des pipelines"
);