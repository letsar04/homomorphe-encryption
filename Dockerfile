FROM python:3.11-slim

# Dépendances système pour Pyfhel et la compilation si nécessaire
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source du serveur et des benchmarks
COPY config.py .
COPY schemes/ schemes/
COPY cloud_sim/ cloud_sim/
COPY data/ data/
COPY benchmarks/ benchmarks/
COPY web_ui/ web_ui/

# Exposition du port REST API
EXPOSE 8000

ENV BIND_HOST=0.0.0.0
ENV CLOUD_PORT=8000

# Démarrage du serveur Cloud REST API
CMD ["python", "cloud_sim/cloud_api_server.py"]
