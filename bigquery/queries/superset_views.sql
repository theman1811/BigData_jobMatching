-- Superset Phase 6 - Vues BigQuery pour accélérer la création de dashboards
-- Exécution recommandée :
--   bq query --use_legacy_sql=false < bigquery/queries/superset_views.sql

CREATE OR REPLACE VIEW `jobmatching_dw.v_offres_daily` AS
SELECT
  DATE(date_publication) AS date_publication,
  COALESCE(source_site, 'unknown') AS source_site,
  COALESCE(secteur_id, 'unknown') AS secteur_id,
  COALESCE(localisation_id, 'unknown') AS localisation_id,
  COALESCE(type_contrat, 'unknown') AS type_contrat,
  COUNT(*) AS offres_totales,
  COUNT(DISTINCT offre_id) AS offres_uniques,
  AVG(salaire_min) AS salaire_min_moy,
  AVG(salaire_max) AS salaire_max_moy
FROM `jobmatching_dw.Fact_OffresEmploi`
GROUP BY 1, 2, 3, 4, 5;

CREATE OR REPLACE VIEW `jobmatching_dw.v_top_competences` AS
WITH exploded AS (
  SELECT
    DATE(date_publication) AS date_publication,
    secteur_id,
    localisation_id,
    source_site,
    skill
  FROM `jobmatching_dw.Fact_OffresEmploi`,
  UNNEST(competences) AS skill
)
SELECT
  date_publication,
  COALESCE(secteur_id, 'unknown') AS secteur_id,
  COALESCE(localisation_id, 'unknown') AS localisation_id,
  COALESCE(source_site, 'unknown') AS source_site,
  LOWER(TRIM(skill)) AS competence,
  COUNT(*) AS occurrences
FROM exploded
GROUP BY 1, 2, 3, 4, 5
HAVING competence IS NOT NULL AND competence != '';

CREATE OR REPLACE VIEW `jobmatching_dw.v_salaires_secteur_ville` AS
SELECT
  COALESCE(se.nom_secteur, 'unknown') AS secteur,
  COALESCE(lo.ville, 'unknown') AS ville,
  COUNT(*) AS offres_totales,
  AVG(salaire_min) AS salaire_min_moy,
  AVG(salaire_max) AS salaire_max_moy,
  APPROX_QUANTILES(salaire_min, 100)[OFFSET(50)] AS salaire_min_p50,
  APPROX_QUANTILES(salaire_max, 100)[OFFSET(50)] AS salaire_max_p50
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
LEFT JOIN `jobmatching_dw.Dim_Localisation` lo ON fe.localisation_id = lo.localisation_id
GROUP BY 1, 2;

CREATE OR REPLACE VIEW `jobmatching_dw.v_geo_offres` AS
SELECT
  fe.offre_id,
  fe.titre_poste,
  fe.source_site,
  fe.date_publication,
  fe.secteur_id,
  fe.localisation_id,
  lo.ville,
  lo.region,
  lo.latitude,
  lo.longitude,
  fe.salaire_min,
  fe.salaire_max
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Localisation` lo ON fe.localisation_id = lo.localisation_id
WHERE lo.latitude IS NOT NULL AND lo.longitude IS NOT NULL;

-- Salaires par secteur (avec médianes et percentiles)
CREATE OR REPLACE VIEW `jobmatching_dw.v_salaires_secteur` AS
SELECT
  COALESCE(fe.secteur_id, 'unknown') AS secteur_id,
  COALESCE(se.nom_secteur, 'unknown') AS nom_secteur,
  COUNT(*) AS offres_totales,
  AVG(salaire_min) AS salaire_min_moy,
  AVG(salaire_max) AS salaire_max_moy,
  APPROX_QUANTILES(salaire_min, 100)[OFFSET(50)] AS salaire_min_p50,
  APPROX_QUANTILES(salaire_max, 100)[OFFSET(50)] AS salaire_max_p50,
  APPROX_QUANTILES(salaire_min, 100)[OFFSET(10)] AS salaire_min_p10,
  APPROX_QUANTILES(salaire_max, 100)[OFFSET(90)] AS salaire_max_p90
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1, 2;

-- Télétravail par secteur (part des offres + distribution du taux)
CREATE OR REPLACE VIEW `jobmatching_dw.v_teletravail_secteur` AS
SELECT
  COALESCE(fe.secteur_id, 'unknown') AS secteur_id,
  COALESCE(se.nom_secteur, 'unknown') AS nom_secteur,
  COUNT(*) AS offres_totales,
  SUM(CASE WHEN teletravail IS TRUE THEN 1 ELSE 0 END) AS offres_teletravail,
  SAFE_DIVIDE(SUM(CASE WHEN teletravail IS TRUE THEN 1 ELSE 0 END), COUNT(*)) AS part_teletravail,
  AVG(taux_teletravail) AS taux_teletravail_moy,
  APPROX_QUANTILES(taux_teletravail, 100)[OFFSET(50)] AS taux_teletravail_p50,
  APPROX_QUANTILES(taux_teletravail, 100)[OFFSET(90)] AS taux_teletravail_p90
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1, 2;
