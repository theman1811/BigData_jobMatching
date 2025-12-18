FROM apache/airflow:2.8.0

# Java requis par spark-submit (multi-arch arm64/amd64)
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jdk && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# Support multi-arch (amd64/arm64) via Docker build arg TARGETARCH
ARG TARGETARCH
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-${TARGETARCH}
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Installer les providers en tant qu'utilisateur airflow
USER airflow
RUN pip install --no-cache-dir \
    pyspark==3.5.1 \
    apache-airflow-providers-apache-spark==4.5.0 \
    apache-airflow-providers-google==10.12.0 \
    apache-airflow-providers-docker==3.7.0 \
    minio==7.2.0 \
    kafka-python==2.0.2
