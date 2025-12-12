FROM apache/spark:3.5.1

USER root

# Install Python dependencies needed for Spark jobs
# Specifically for HTML parsing in parse_jobs.py
RUN pip install --no-cache-dir \
    beautifulsoup4==4.12.2 \
    lxml==4.9.3

# Switch back to spark user (UID 185)
USER 185
