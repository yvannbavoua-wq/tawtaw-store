import os
import chromadb
from datetime import datetime
from sentence_transformers import SentenceTransformer

class TatawMemoryAI:
    def __init__(self):
        # Dossier local pour stocker la mémoire vectorielle de TATAW
        self.db_path = os.path.join(os.getcwd(), "tataw_vector_db")
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Modèle léger d'embedding pour comprendre le sens des requêtes
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Collection vectorielle exclusive à TATAW
        self.collection = self.client.get_or_create_collection(name="tataw_exclusive_knowledge")
        
        # Dictionnaire mémoire pour le quota d'images (5/jour max par utilisateur)
        self.image_quotas = {}

    def add_knowledge(self, doc_id, text_content, metadata=None):
        """Ajoute ou met à jour une fiche produit / règle dans la mémoire TATAW"""
        embedding = self.encoder.encode(text_content).tolist()
        self.collection.upsert(
            ids=[str(doc_id)],
            embeddings=[embedding],
            documents=[text_content],
            metadatas=[metadata or {"source": "tataw_catalog"}]
        )

    def query_knowledge(self, query_text, n_results=3):
        """Recherche les informations les plus proches dans la mémoire TATAW"""
        query_embedding = self.encoder.encode(query_text).tolist()
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        return results.get('documents', [[]])[0]

    def check_and_increment_image_quota(self, user_id):
        """Vérifie si l'utilisateur a dépassé sa limite de 5 images/jour"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        user_key = f"{user_id}_{today}"
        current_count = self.image_quotas.get(user_key, 0)
        
        if current_count >= 5:
            return False, current_count
        
        self.image_quotas[user_key] = current_count + 1
        return True, self.image_quotas[user_key]

# Instance globale pour toute l'application
tataw_brain = TatawMemoryAI()