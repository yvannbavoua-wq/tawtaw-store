import numpy as np
from mabwiser.mab import MAB, LearningPolicy

class CommerceRLAgent:
    def __init__(self):
        self.is_trained = False
        self.mab = None

    def train_from_history(self, interactions, all_product_ids):
        """Entraîne l'agent avec l'historique des interactions."""
        if len(interactions) < 3 or not all_product_ids:
            return False

        contexts = []
        actions = []
        rewards = []

        category_map = {'electronique': [1, 0], 'mode': [0, 1], 'autre': [0, 0]}

        for inter in interactions:
            ctx_vec = category_map.get(inter.context_category, [0, 0])
            contexts.append(ctx_vec)
            actions.append(inter.action_product_id)
            rewards.append(inter.reward)

        try:
            # Initialisation de MAB avec la politique LinUCB
            self.mab = MAB(
                arms=all_product_ids,
                learning_policy=LearningPolicy.LinUCB(alpha=1.0)
            )
            self.mab.fit(
                decisions=actions,
                rewards=rewards,
                contexts=contexts
            )
            self.is_trained = True
            return True
        except Exception as e:
            print("Erreur entraînement RL:", e)
            return False

    def recommend(self, user_category, available_products, strategy_mode='standard_sales'):
        """Recommande un produit."""
        if not available_products:
            return None

        if not self.is_trained or self.mab is None:
            return int(np.random.choice(available_products))

        category_map = {'electronique': [1, 0], 'mode': [0, 1], 'autre': [0, 0]}
        ctx_vec = [category_map.get(user_category, [0, 0])]

        try:
            prediction = self.mab.predict(contexts=ctx_vec)
            return int(prediction[0])
        except Exception as e:
            print("Erreur prédiction RL:", e)
            return int(np.random.choice(available_products))

rl_agent = CommerceRLAgent()