#!/usr/bin/env python3
"""
==========================================
Spark Batch - Parsing Jobs HTML
==========================================
Job Spark Batch pour parser les offres d'emploi HTML brutes
et extraire les informations structurées.

Source: s3a://scraped-jobs/
Destination: s3a://processed-data/jobs_parsed/

Format des fichiers: JSON métadonnées + "\n\n" + HTML content
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, regexp_extract, regexp_replace, trim, lower,
    when, coalesce, length, split, explode, array_distinct,
    current_timestamp, date_format, lit, array, size, substring, expr, locate, decode
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
    # Récupérer le master depuis l'environnement ou utiliser la valeur par défaut
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    
    return SparkSession.builder \
        .appName("JobOffersParser") \
        .master(spark_master) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()


def extract_title_udf(html_content):
    """UDF pour extraire le titre depuis le HTML"""
    if not html_content:
        return None

    # Mots à exclure des titres (faux positifs)
    excluded_words = ['partager', 'partagez', 'share', 'menu', 'navigation', 
                      'accueil', 'home', 'footer', 'header', 'sidebar']

    def is_valid_title(text):
        """Vérifie si le texte est un titre valide"""
        if not text or len(text) < 5 or len(text) > 200:
            return False
        text_lower = text.lower()
        return not any(word in text_lower for word in excluded_words)

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Sélecteurs prioritaires pour les titres d'offres (ordre important)
        title_selectors = [
            # Sélecteurs spécifiques aux sites d'emploi
            'h1.job-title', 'h1.title', '.job-title h1', '.offer-title',
            '.bread-title', '.job-title', '.position-title', '.vacancy-title',
            # Balises h1, h2, h3 génériques
            'h1', 'h2.title', 'h3.title',
            # Sélecteurs avec attributs
            '[class*="job-title"]', '[class*="offer-title"]', '[class*="position-title"]',
        ]

        for selector in title_selectors:
            elements = soup.select(selector)
            for elem in elements:
                title = elem.get_text(strip=True)
                if is_valid_title(title):
                    return title

        # Fallback: chercher dans le titre de la page (souvent contient le titre de l'offre)
        if soup.title:
            page_title = soup.title.get_text(strip=True)
            # Nettoyer le titre de page (enlever le nom du site)
            for sep in [' | ', ' - ', ' :: ', ' — ']:
                if sep in page_title:
                    parts = page_title.split(sep)
                    # Prendre la partie la plus longue qui semble être le titre
                    for part in parts:
                        if is_valid_title(part.strip()):
                            return part.strip()
            # Si pas de séparateur, utiliser le titre complet
            if is_valid_title(page_title):
                return page_title

        # Dernier recours: sélecteurs génériques avec [class*="title"]
        for selector in ['[class*="title"]']:
            elements = soup.select(selector)
            for elem in elements:
                title = elem.get_text(strip=True)
                if is_valid_title(title):
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
        input_path: Chemin MinIO source (HTML compressé gzip)
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

    # Lire les fichiers HTML depuis MinIO
    # Les fichiers sont au format: JSON metadata + "\n\n" + HTML content
    max_files = int(os.getenv("BATCH_LIMIT", "0"))
    
    # Préparer la liste des fichiers à traiter
    from py4j.java_gateway import java_import
    java_import(spark._jvm, 'org.apache.hadoop.fs.Path')
    java_import(spark._jvm, 'org.apache.hadoop.fs.FileSystem')
    
    hadoop_conf = spark._jsc.hadoopConfiguration()
    base_path = input_path.split('*')[0]
    fs = spark._jvm.FileSystem.get(spark._jvm.java.net.URI(base_path), hadoop_conf)
    path = spark._jvm.Path(input_path.replace('*.html', ''))
    
    # Lister tous les fichiers HTML
    file_status = fs.listStatus(path)
    all_html_files = [f.getPath().toString() for f in file_status if f.getPath().toString().endswith('.html')]
    
    if max_files > 0:
        html_files = all_html_files[:max_files]
        print(f"📁 {len(html_files)} fichiers HTML sélectionnés sur {len(all_html_files)} disponibles")
    else:
        html_files = all_html_files
        print(f"📁 {len(html_files)} fichiers HTML trouvés")
    
    if not html_files:
        raise ValueError("Aucun fichier HTML trouvé")
    
    # Lire les fichiers avec binaryFile pour avoir le contenu complet
    # binaryFile est plus fiable que text avec wholetext pour S3A
    html_df = spark.read \
        .format("binaryFile") \
        .load(html_files)
    
    # Décoder le contenu binaire en texte UTF-8
    # La colonne 'content' contient les bytes, 'path' contient le chemin
    html_df = html_df.withColumn(
        'value',
        decode(col('content'), 'UTF-8')
    ).select('path', 'value')
    
    # Appliquer la limite si nécessaire
    if max_files > 0:
        html_df = html_df.limit(max_files)
    
    file_count = html_df.count()
    print(f"✅ {file_count} fichiers HTML lus depuis {input_path}")
    
    # DEBUG: Afficher un échantillon du contenu brut
    print("🔍 DEBUG - Échantillon du contenu brut (value):")
    html_df.select(length(col('value')).alias('content_length')).show(5)
    
    # DEBUG: Afficher les premiers caractères pour vérifier le format
    print("🔍 DEBUG - Premiers 250 caractères:")
    html_df.select(substring(col('value'), 1, 250).alias('start')).show(1, truncate=False)

    # Parser le format de stockage (métadonnées + HTML)
    # Format: JSON multi-ligne suivi de \n\n puis HTML (commence par <!DOCTYPE ou <html)
    # 
    # Approche: trouver la position de <!DOCTYPE ou <html et séparer avant/après
    # locate() retourne la position 1-based du premier caractère trouvé
    parsed_df = html_df.withColumn(
        # Trouver où commence le HTML (<!DOCTYPE ou <html)
        'html_start_pos',
        # Chercher <!DOCTYPE d'abord, sinon <html
        when(
            locate('<!DOCTYPE', col('value')) > 0,
            locate('<!DOCTYPE', col('value'))
        ).otherwise(
            locate('<html', col('value'))
        )
    )
    
    # Utiliser expr() pour les opérations sur colonnes dans substring
    parsed_df = parsed_df.withColumn(
        # Métadonnées = tout ce qui précède le HTML (moins les newlines)
        'metadata_json',
        trim(expr("substring(value, 1, html_start_pos - 1)"))
    ).withColumn(
        # HTML = tout à partir de <!DOCTYPE ou <html
        'html_content',
        expr("substring(value, html_start_pos)")
    )
    
    # DEBUG: Vérifier les positions trouvées
    print("🔍 DEBUG - Positions HTML trouvées:")
    parsed_df.select('html_start_pos').show(5)
    
    # DEBUG: Vérifier le résultat du split
    print("🔍 DEBUG - Après split:")
    parsed_df.select(
        length(col('metadata_json')).alias('metadata_len'),
        length(col('html_content')).alias('html_len')
    ).show(5)
    
    # DEBUG: Compter les NULLs
    null_html_count = parsed_df.filter(col('html_content').isNull()).count()
    print(f"🔍 DEBUG - Fichiers avec html_content NULL: {null_html_count}/{file_count}")

    # Extraire les métadonnées JSON
    # Utiliser le chemin du fichier comme fallback pour job_id
    metadata_df = parsed_df.withColumn(
        'job_id',
        coalesce(
            # D'abord essayer d'extraire du JSON
            regexp_extract(col('metadata_json'), r'"job_id"\s*:\s*"([^"]+)"', 1),
            # Sinon extraire du nom de fichier (ex: s3a://bucket/abc123.html -> abc123)
            regexp_extract(col('path'), r'/([^/]+)\.html$', 1)
        )
    ).withColumn(
        'source',
        coalesce(
            regexp_extract(col('metadata_json'), r'"source"\s*:\s*"([^"]+)"', 1),
            lit('Unknown')
        )
    )
    
    # DEBUG: Vérifier l'extraction des métadonnées
    print("🔍 DEBUG - Métadonnées extraites (échantillon):")
    metadata_df.select('job_id', 'source').show(5, truncate=False)

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
    
    # DEBUG: Vérifier les résultats du parsing
    print("🔍 DEBUG - Résultats parsing (échantillon):")
    parsed_jobs_df.select(
        'job_id',
        length(col('parsed_title')).alias('title_len'),
        length(col('parsed_description')).alias('desc_len'),
        length(col('parsed_company')).alias('company_len')
    ).show(5)
    
    # DEBUG: Compter les NULLs après parsing
    null_title = parsed_jobs_df.filter(col('parsed_title').isNull()).count()
    null_desc = parsed_jobs_df.filter(col('parsed_description').isNull()).count()
    null_company = parsed_jobs_df.filter(col('parsed_company').isNull()).count()
    total = parsed_jobs_df.count()
    print(f"🔍 DEBUG - NULL counts: title={null_title}/{total}, desc={null_desc}/{total}, company={null_company}/{total}")

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
    input_bucket = os.getenv("INPUT_BUCKET", os.getenv("MINIO_BUCKET", "scraped-jobs"))
    input_prefix = os.getenv("INPUT_PREFIX", "").strip("/")
    output_bucket = os.getenv("OUTPUT_BUCKET", "processed-data")

    input_path = f"s3a://{input_bucket}/{input_prefix + '/' if input_prefix else ''}*.html"
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
