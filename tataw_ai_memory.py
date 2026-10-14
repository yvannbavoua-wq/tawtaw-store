Import os
from datetime import datetime

class TatawMemoryAI:
    def __init__(self):
        self.image_quotas = {}
        self.brand_story = (
            "TATAW x OFFX est le fruit de la rencontre et de la vision commune de deux frères : offx & nybe. "
            "Dans les traditions nomades, TATAW représente l'étoile guidante, le point de repère à travers le parcours. "
            "Né de la réunion entre l'héritage familial de nybe et la quête d'offx à promouvoir cet héritage."
        )
        self.streetwear_expertise = (
            "Culture et stylisme streetwear : Maîtrise des coupes oversize et boxy fit, layering (superposition), "
            "association des couleurs neutres et vives, coupes lourdes (heavyweight cotton), minimalisme urbain "
            "et tendances streetwear de Yaoundé / Douala à l'international."
        )

    def get_full_context(self):
        """Récupère l'intégralité du catalogue, des variantes de couleurs/tailles et de l'histoire pour l'IA Lia."""
        try:
            from app import Product, ProductVariant
            products = Product.query.all()
            prod_texts = []
            
            for p in products:
                variants = ProductVariant.query.filter_by(product_id=p.id).all()
                variant_summary = ""
                if variants:
                    v_details = [f"{v.color}/{v.size} (Stock: {v.stock_qty})" for v in variants]
                    variant_summary = f" | Déclinaisons: [{', '.join(v_details)}]"

                prod_texts.append(
                    f"- [ID: {p.id}] {p.name} | Catégorie: {p.category}/{p.subcategory} | "
                    f"Prix: {p.price} FCFA | Stock global: {p.stock_qty} | Couleurs: {p.options}{variant_summary} | "
                    f"Desc: {p.description}"
                )
            
            full_catalog = "\n".join(prod_texts) if prod_texts else "Aucun produit pour l'instant dans le catalogue."
            return (
                f"--- HISTOIRE ET VALEURS DE LA MARQUE ---\n{self.brand_story}\n\n"
                f"--- EXPERTISE CULTURE STREETWEAR & MODE ---\n{self.streetwear_expertise}\n\n"
                f"--- CATALOGUE COMPLET ET STOCKS EN TEMPS RÉEL ---\n{full_catalog}"
            )
        except Exception as e:
            return f"--- HISTOIRE ET VALEURS ---\n{self.brand_story}\n\n--- EXPERTISE MODE ---\n{self.streetwear_expertise}"

    def add_knowledge(self, doc_id, text_content, metadata=None):
        pass

    def query_knowledge(self, query_text, n_results=3):
        return [self.brand_story, self.streetwear_expertise]

    def check_and_increment_image_quota(self, user_id):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        user_key = f"{user_id}_{today}"
        current_count = self.image_quotas.get(user_key, 0)
        
        if current_count >= 5:
            return False, current_count
        
        self.image_quotas[user_key] = current_count + 1
        return True, self.image_quotas[user_key]

tataw_brain = TatawMemoryAI()