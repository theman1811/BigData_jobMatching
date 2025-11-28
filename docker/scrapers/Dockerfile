# ============================================
# Dockerfile for Web Scrapers
# ============================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="BigData Team"
LABEL description="Web Scraping Container for Job Offers and CVs"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    # Build tools
    gcc \
    g++ \
    make \
    # Networking
    curl \
    wget \
    # Browsers & drivers (pour Selenium)
    chromium \
    chromium-driver \
    firefox-esr \
    # Utilities
    git \
    vim \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Répertoire de travail
WORKDIR /app

# Copier les requirements
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Télécharger le modèle spaCy français
RUN pip install https://github.com/explosion/spacy-models/releases/download/fr_core_news_md-3.7.0/fr_core_news_md-3.7.0-py3-none-any.whl

# Télécharger les données NLTK
RUN python -m nltk.downloader punkt stopwords wordnet

# Installation Playwright browsers (optionnel)
RUN playwright install chromium

# Créer les dossiers nécessaires
RUN mkdir -p /app/producers /app/data /app/config /app/logs

# Copier les scripts
COPY scraper_daemon.py /app/
COPY requirements.txt /app/

# Permissions
RUN chmod +x /app/scraper_daemon.py

# Port (si nécessaire pour une API)
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Commande par défaut
CMD ["python", "/app/scraper_daemon.py"]

