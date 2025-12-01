-- Création du dataset BigQuery
CREATE SCHEMA IF NOT EXISTS `jobmatching_dw`
OPTIONS(
  description = "Data Warehouse pour le système de matching d'emplois",
  location = "EU"
);