#!/usr/bin/env python3
"""
==========================================
Spark Batch - Parsing Jobs HTML
==========================================
Job Spark Batch pour parser les offres d'emploi HTML brutes
et extraire les informations structurées.

Source: s3a://scraped-jobs/
Destination: s3a://processed-data/jobs_parsed/
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, regexp_extract, regexp_replace, trim, lower,
    when, coalesce, length, split, explode, array_distinct,
    current_timestamp, date_format, lit, array, size
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType,
    BooleanType, ArrayType
)

# Imports pour le parsing HTML
from bs4 import BeautifulSoup
import re


def create_spark_session():
    """Crée la session Spark avec configuration MinIO"""
    return SparkSession.builder \
        .appName("JobOffersParser") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()


def extract_title_udf(html_content):
    """UDF pour extraire le titre depuis le HTML"""
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Patterns courants pour les titres d'offres
        title_selectors = [
            'h1.job-title', 'h1.title', '.job-title h1', '.offer-title',
            'h1', '.title', '[class*="title"]', '[class*="job"]'
        ]

        for selector in title_selectors:
            elements = soup.select(selector)
            if elements:
                title = elements[0].get_text(strip=True)
                if title and len(title) > 5:  # Titre valide
                    return title

        # Fallback: chercher dans le titre de la page
        if soup.title:
            title = soup.title.get_text(strip=True)
            if title and len(title) > 5:
                return title

    except Exception as e:
        print(f"Erreur extraction titre: {e}")

    return None


def extract_company_udf(html_content):
    """UDF pour extraire le nom de l'entreprise"""
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Patterns pour les entreprises
        company_selectors = [
            '.company-name', '.employer', '.company', '[class*="company"]',
            '.organization', '.firm', '.enterprise'
        ]

        for selector in company_selectors:
            elements = soup.select(selector)
            if elements:
                company = elements[0].get_text(strip=True)
                if company and len(company) > 2:
                    return company

        # Chercher des patterns textuels
        text = soup.get_text()
        company_patterns = [
            r'(?:chez|pour|company|entreprise)\s*:?\s*([A-Z][A-Za-z\s&\-\.]+)',
            r'([A-Z][A-Za-z\s&\-\.]+(?:SA|SARL|SARL|Groupe|Group|Corp|Corporation|Inc|Ltd))'
        ]

        for pattern in company_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                if len(company) > 2:
                    return company

    except Exception as e:
        print(f"Erreur extraction entreprise: {e}")

    return "Entreprise confidentielle"


def extract_description_udf(html_content):
    """UDF pour extraire la description de l'offre"""
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Patterns pour la description
        desc_selectors = [
            '.job-description', '.description', '.offer-description',
            '.job-content', '.position-description', '[class*="description"]',
            '.content', '.main-content'
        ]

        for selector in desc_selectors:
            elements = soup.select(selector)
            if elements:
                desc = elements[0].get_text(strip=True)
                if desc and len(desc) > 50:  # Description valide
                    return desc

        # Fallback: prendre le contenu textuel principal
        # Enlever les headers, footers, etc.
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()

        text = soup.get_text(separator=' ', strip=True)
        if len(text) > 100:
            return text[:2000]  # Limiter la taille

    except Exception as e:
        print(f"Erreur extraction description: {e}")

    return None


def extract_requirements_udf(html_content):
    """UDF pour extraire les exigences/compétences"""
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Patterns pour les exigences
        req_selectors = [
            '.requirements', '.qualifications', '.skills', '.competences',
            '.job-requirements', '.profile', '[class*="requirement"]',
            '[class*="skill"]', '[class*="competence"]'
        ]

        requirements = []

        for selector in req_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 10:
                    requirements.append(text)

        if requirements:
            return ' '.join(requirements)

        # Chercher des listes dans la description
        desc_elem = soup.select('.description, .content')
        if desc_elem:
            text = desc_elem[0].get_text()
            # Extraire les listes à puces
            list_items = re.findall(r'[•\-\*]\s*([^\n•\-\*]+)', text)
            if list_items:
                return ' '.join(list_items[:10])  # Limiter à 10 items

    except Exception as e:
        print(f"Erreur extraction exigences: {e}")

    return None


def extract_location_udf(html_content):
    """UDF pour extraire la localisation"""
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Patterns pour la localisation
        location_selectors = [
            '.location', '.place', '.city', '.address', '[class*="location"]',
            '[class*="place"]', '[class*="city"]'
        ]

        for selector in location_selectors:
            elements = soup.select(selector)
            if elements:
                location = elements[0].get_text(strip=True)
                if location and len(location) > 2:
                    return location

        # Chercher dans le texte avec patterns Côte d'Ivoire
        text = soup.get_text()
        ci_cities = [
            'Abidjan', 'Bouaké', 'Daloa', 'Yamoussoukro', 'San-Pédro',
            'Korhogo', 'Man', 'Gagnoa', 'Divo', 'Soubré', 'Côte d\'Ivoire',
            'Côte d\'Ivoire', 'Ivory Coast'
        ]

        for city in ci_cities:
            if city.lower() in text.lower():
                return city

    except Exception as e:
        print(f"Erreur extraction localisation: {e}")

    return "Côte d'Ivoire"


def extract_salary_udf(html_content):
    """UDF pour extraire les informations salariales"""
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Patterns pour le salaire
        salary_selectors = [
            '.salary', '.remuneration', '.compensation', '.pay',
            '[class*="salary"]', '[class*="pay"]', '[class*="remun"]'
        ]

        for selector in salary_selectors:
            elements = soup.select(selector)
            if elements:
                salary_text = elements[0].get_text(strip=True)
                if salary_text:
                    return salary_text

        # Chercher dans le texte avec regex FCFA
        text = soup.get_text()
        salary_patterns = [
            r'(\d+(?:[\s\.,]\d+)*)\s*(?:FCFA|CFA|XOF|francs?|€|\$)',
            r'(?:salaire|rémunération|paye)\s*:?\s*(\d+(?:[\s\.,]\d+)*[^\n,]*)',
            r'(\d+(?:[\s\.,]\d+)*)\s*(?:par|\/)\s*(?:mois|month|an|year)'
        ]

        for pattern in salary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

    except Exception as e:
        print(f"Erreur extraction salaire: {e}")

    return None


def extract_contract_type_udf(html_content):
    """UDF pour extraire le type de contrat"""
    if not html_content:
        return "Non spécifié"

    try:
        text = html_content.lower()

        # Types de contrat courants
        contract_types = {
            'CDI': ['cdi', 'contrat à durée indéterminée', 'permanent', 'durable'],
            'CDD': ['cdd', 'contrat à durée déterminée', 'temporaire', 'intérim'],
            'Stage': ['stage', 'internship', 'formation', 'apprentissage'],
            'Freelance': ['freelance', 'indépendant', 'consultant', 'prestataire'],
            'Alternance': ['alternance', 'apprentissage', 'contrat pro'],
            'Mission': ['mission', 'projet', 'contractuel']
        }

        for contract, keywords in contract_types.items():
            for keyword in keywords:
                if keyword in text:
                    return contract

    except Exception as e:
        print(f"Erreur extraction type contrat: {e}")

    return "Non spécifié"


def extract_skills_udf(text):
    """UDF pour extraire les compétences depuis le texte"""
    if not text:
        return []

    try:
        # Liste étendue de compétences techniques
        technical_skills = [
            # Programmation
            'python', 'java', 'javascript', 'typescript', 'c#', 'c++', 'php', 'ruby',
            'go', 'rust', 'scala', 'kotlin', 'swift', 'r', 'matlab', 'sas',

            # Web
            'html', 'css', 'react', 'vue', 'angular', 'node.js', 'express',
            'django', 'flask', 'spring', 'laravel', 'symfony', '.net',

            # Bases de données
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
            'oracle', 'sqlite', 'cassandra', 'hbase',

            # Big Data
            'hadoop', 'spark', 'kafka', 'hive', 'pig', 'flume', 'sqoop',
            'airflow', 'presto', 'druid', 'cassandra',

            # Cloud
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
            'jenkins', 'gitlab', 'github', 'bitbucket',

            # BI & Analytics
            'tableau', 'power bi', 'qlik', 'looker', 'excel', 'sap',
            'sas', 'spss', 'stata', 'r studio',

            # Méthodologies
            'agile', 'scrum', 'kanban', 'devops', 'ci/cd', 'tdd', 'bdd',

            # Soft skills
            'management', 'leadership', 'communication', 'teamwork', 'problem solving'
        ]

        text_lower = text.lower()
        detected_skills = []

        for skill in technical_skills:
            if skill in text_lower:
                detected_skills.append(skill.title())

        return list(set(detected_skills))  # Éliminer les doublons

    except Exception as e:
        print(f"Erreur extraction compétences: {e}")
        return []


def process_job_parsing(spark, input_path, output_path):
    """
    Traite le parsing des offres d'emploi HTML

    Args:
        spark: SparkSession
        input_path: Chemin MinIO source (HTML)
        output_path: Chemin MinIO destination (Parquet)
    """

    # Enregistrer les UDFs
    extract_title = udf(extract_title_udf, StringType())
    extract_company = udf(extract_company_udf, StringType())
    extract_description = udf(extract_description_udf, StringType())
    extract_requirements = udf(extract_requirements_udf, StringType())
    extract_location = udf(extract_location_udf, StringType())
    extract_salary = udf(extract_salary_udf, StringType())
    extract_contract_type = udf(extract_contract_type_udf, StringType())
    extract_skills = udf(extract_skills_udf, ArrayType(StringType()))

    print("✅ UDFs enregistrées")

    # Lire les données HTML depuis MinIO
    html_df = spark.read.text(input_path)
    print(f"✅ Données HTML lues depuis {input_path}")

    # Parser le format de stockage (métadonnées + HTML)
    # Format: JSON métadonnées\n\nHTML content
    parsed_df = html_df.withColumn(
        'content_parts',
        split(col('value'), '\n\n', 2)
    ).withColumn(
        'metadata_json', col('content_parts').getItem(0)
    ).withColumn(
        'html_content', col('content_parts').getItem(1)
    )

    # Extraire les métadonnées JSON
    metadata_df = parsed_df.withColumn(
        'job_id',
        regexp_extract(col('metadata_json'), r'"job_id"\s*:\s*"([^"]+)"', 1)
    ).withColumn(
        'source',
        regexp_extract(col('metadata_json'), r'"source"\s*:\s*"([^"]+)"', 1)
    )

    print("✅ Métadonnées extraites")

    # Appliquer le parsing HTML
    parsed_jobs_df = metadata_df \
        .withColumn("parsed_title", extract_title(col("html_content"))) \
        .withColumn("parsed_company", extract_company(col("html_content"))) \
        .withColumn("parsed_description", extract_description(col("html_content"))) \
        .withColumn("parsed_requirements", extract_requirements(col("html_content"))) \
        .withColumn("parsed_location", extract_location(col("html_content"))) \
        .withColumn("parsed_salary_text", extract_salary(col("html_content"))) \
        .withColumn("parsed_contract_type", extract_contract_type(col("html_content"))) \
        .withColumn("extracted_skills", extract_skills(
            coalesce(col("parsed_description"), col("parsed_requirements"))
        ))

    print("✅ Parsing HTML appliqué")

    # Fusionner avec les données existantes (si elles existent)
    # et gérer les valeurs manquantes
    final_df = parsed_jobs_df \
        .withColumn("title",
                   coalesce(col("parsed_title"), lit("Titre non disponible"))) \
        .withColumn("company",
                   coalesce(col("parsed_company"), lit("Entreprise confidentielle"))) \
        .withColumn("description",
                   coalesce(col("parsed_description"), lit("Description non disponible"))) \
        .withColumn("requirements",
                   coalesce(col("parsed_requirements"), lit("Exigences non spécifiées"))) \
        .withColumn("location",
                   coalesce(col("parsed_location"), lit("Côte d'Ivoire"))) \
        .withColumn("contract_type",
                   coalesce(col("parsed_contract_type"), lit("Non spécifié"))) \
        .withColumn("skills",
                   when(col("extracted_skills").isNotNull(), col("extracted_skills"))
                   .otherwise(array())) \
        .withColumn("parsed_at", current_timestamp()) \
        .withColumn("parsing_quality_score",
                   (when(col("parsed_title").isNotNull(), 1).otherwise(0) +
                    when(col("parsed_company").isNotNull(), 1).otherwise(0) +
                    when(col("parsed_description").isNotNull(), 1).otherwise(0) +
                    when(size(col("extracted_skills")) > 0, 1).otherwise(0)) / 4.0)

    # Sélectionner les colonnes finales
    output_df = final_df.select(
        "job_id", "source", "title", "company", "description",
        "requirements", "location", "parsed_salary_text", "contract_type",
        "skills", "parsed_at", "parsing_quality_score",
        "html_content"  # Garder pour debug
    )

    print("✅ Données finales préparées")

    # Écrire en Parquet partitionné
    output_df.write \
        .mode("overwrite") \
        .partitionBy("source") \
        .parquet(output_path)

    print(f"✅ Données écrites vers {output_path}")

    # Statistiques
    total_jobs = output_df.count()
    avg_quality = output_df.agg({"parsing_quality_score": "avg"}).collect()[0][0]

    print(f"📊 Statistiques:")
    print(f"   Total offres parsées: {total_jobs}")
    print(f"   Score qualité moyen: {avg_quality:.2f}")

    return total_jobs, avg_quality


def main():
    """Fonction principale"""
    print("🚀 Démarrage du parsing Spark Batch - Offres d'emploi")

    # Configuration
    input_bucket = os.getenv("MINIO_BUCKET", "scraped-jobs")
    output_bucket = os.getenv("MINIO_BUCKET", "processed-data")

    input_path = f"s3a://{input_bucket}/*.html"
    output_path = f"s3a://{output_bucket}/jobs_parsed"

    print(f"📋 Configuration:")
    print(f"   Input: {input_path}")
    print(f"   Output: {output_path}")

    try:
        # Créer la session Spark
        spark = create_spark_session()
        print("✅ Session Spark créée")

        # Traiter les données
        total_jobs, avg_quality = process_job_parsing(spark, input_path, output_path)

        print("✅ Parsing terminé avec succès")
        print(f"📊 {total_jobs} offres parsées (qualité moyenne: {avg_quality:.2f})")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)
    finally:
        if 'spark' in locals():
            spark.stop()
            print("✅ Session Spark arrêtée")


if __name__ == "__main__":
    main()
