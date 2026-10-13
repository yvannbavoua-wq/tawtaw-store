FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copie et installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'ensemble du code du projet
COPY . .

# Hugging Face utilise le port 7860 par défaut
EXPOSE 7860

# Lancement de l'application avec Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]