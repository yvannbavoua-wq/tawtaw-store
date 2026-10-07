import numpy as np
from mabwiser.bandit import LinUCB

class CommerceRLAgent:
    def __init__(self):
        # Algorithme LinUCB (Contextual Bandit)
        self.model = LinUCB(alpha=1.0)
        self.is_trained = False

    def train_from_history(self, interactions, all_product_ids):
        """Entraîne l'agent avec l'historique des interactions et récompenses."""
        if len(interactions) < 3:
            return False  # Attend d'avoir au moins 3 interactions pour s'entraîner

        contexts = []
        actions = []
        rewards = []

        # Encodage simple des catégories
        category_map = {'electronique': [1, 0], 'mode': [0, 1], 'autre': [0, 0]}

        for inter in interactions:
            ctx_vec = category_map.get(inter.context_category, [0, 0])
            contexts.append(ctx_vec)
            actions.append(inter.action_product_id)
            rewards.append(inter.reward)

        try:
            self.model.fit(
                decisions=np.array(actions),
                rewards=np.array(rewards),
                contexts=np.array(contexts)
            )
            self.is_trained = True
            return True
        except Exception as e:
            print("Erreur d'entraînement RL:", e)
            return False

    def recommend(self, user_category, available_products, strategy_mode='standard_sales'):
        """Recommande le produit optimal selon les choix passés."""
        if not available_products:
            return None

        category_map = {'electronique': [1, 0], 'mode': [0, 1], 'autre': [0, 0]}
        ctx_vec = np.array([category_map.get(user_category, [0, 0])])

        # Si l'agent n'a pas encore assez de données, il choisit au hasard
        if not self.is_trained:
            return int(np.random.choice(available_products))

        try:
            prediction = self.model.predict(ctx_vec)
            return int(prediction[0])
        except Exception:
            return int(np.random.choice(available_products))

# Instance globale de l'agent
rl_agent = CommerceRLAgent()