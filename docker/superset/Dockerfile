# ============================================
# Dockerfile personnalisé pour Apache Superset
# Avec support PostgreSQL (psycopg2-binary)
# ============================================

FROM apache/superset:latest

# Installer les dépendances GCP
USER root
RUN apt-get update && \
    apt-get install -y gcc python3-dev && \
    pip install psycopg2-binary && \
    pip install google-cloud-bigquery && \
    pip install google-auth && \
    pip install pybigquery sqlalchemy-bigquery && \
    pip install "sqlalchemy<2.0" && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Revenir à l'utilisateur superset
USER superset
