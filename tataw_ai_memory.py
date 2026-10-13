import os
from datetime import datetime

class TatawMemoryAI:
    def __init__(self):
        self.image_quotas = {}
        self.brand_story = (
            "TATAW x OFFX est le fruit de la rencontre et de la vision commune de deux frères : offx & nybe. "
            "Dans les traditions nomades, TATAW représente l'étoile guidante, le point de repère à travers le parcours. "
            "Né de la réunion entre l'héritage familial de nybe et la quête d'offx à promouvoir cet héritage."
        )

    def add_knowledge(self, doc_id, text_content, metadata=None):
        pass

    def query_knowledge(self, query_text, n_results=3):
        return [self.brand_story]

    def check_and_increment_image_quota(self, user_id):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        user_key = f"{user_id}_{today}"
        current_count = self.image_quotas.get(user_key, 0)
        
        if current_count >= 5:
            return False, current_count
        
        self.image_quotas[user_key] = current_count + 1
        return True, self.image_quotas[user_key]

tataw_brain = TatawMemoryAI()