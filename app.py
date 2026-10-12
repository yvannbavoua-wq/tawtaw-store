import os
from datetime import datetime
import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from rl_agent import rl_agent
from werkzeug.utils import secure_filename
from google import genai

# Intégration sécurisée de Supabase
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except ImportError:
    supabase = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tataw_secret_key_change_in_production')

# Configuration Resend & WhatsApp
RESEND_API_KEY = "Re_CMfDGwQS_8quVTygFjdDn8GhXeR3PvXLQ"
WHATSAPP_GROUP_LINK = "https://chat.whatsapp.com/Ch3zFqqKM9HAJP7gnWsSSN?s=cl&p=i&mlu=4&ilr=4&iam=0"

# Connexion Base de Données
db_url = os.environ.get('DATABASE_URL', 'sqlite:///tataw.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODÈLES DE LA BASE DE DONNÉES ---

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(50), nullable=True)
    promo_info = db.Column(db.String(100), nullable=True)
    options = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_featured = db.Column(db.Boolean, default=False)
    in_stock = db.Column(db.Boolean, default=True)
    stock_qty = db.Column(db.Integer, default=5)
    rating = db.Column(db.Float, default=5.0)

class ProductMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    file_url = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(50), nullable=False)
    caption = db.Column(db.String(255), nullable=True)

class PromoCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=False)
    influencer_name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    login_method = db.Column(db.String(30), default='whatsapp')
    country = db.Column(db.String(50), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    is_verified = db.Column(db.Boolean, default=True)

class RLInteraction(db.Model):
    __tablename__ = 'rl_interactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    context_category = db.Column(db.String(50), nullable=False)
    action_product_id = db.Column(db.Integer, nullable=False)
    reward = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RLModelConfig(db.Model):
    __tablename__ = 'rl_model_config'
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(50), nullable=False, default='standard_sales')
    is_active = db.Column(db.Boolean, default=True)

with app.app_context():
    db.create_all()
    if not Product.query.first():
        default_p = Product(
            name="Tawtaw t-shirt Streetwear",
            category="HOMME",
            subcategory="T-SHIRTS",
            image_url="https://i.ibb.co/SXHNbgRS/Photoroom-20261006-212634.jpg",
            price="6000",
            options="Noir, Blanc, Bleu",
            description="T-shirt officiel TATAW x OFFX - Édition limitée 2026",
            is_featured=True,
            in_stock=True,
            stock_qty=10,
            rating=4.9
        )
        db.session.add(default_p)
        db.session.commit()

# --- NOTIFICATIONS ---

def notify_new_article(product):
    try:
        users = User.query.filter(User.email.isnot(None)).all()
        emails = [u.email for u in users if u.email]
        if emails and RESEND_API_KEY:
            headers = {
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": "TATAW x OFFX <onboarding@resend.dev>",
                "to": emails,
                "subject": f"🔥 Nouveau produit disponible : {product.name}",
                "html": f"<h2>Découvrez notre nouveauté exclusive !</h2><p><b>{product.name}</b> - {product.price} FCFA</p><p>{product.description}</p><img src='{product.image_url}' width='300'/><p><a href='{WHATSAPP_GROUP_LINK}'>Rejoindre notre groupe WhatsApp</a></p>"
            }
            requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"Erreur notification Resend: {e}")

# --- ROUTES PRINCIPALES ---

@app.route('/')
def index():
    products = Product.query.all()
    featured_products = Product.query.filter_by(is_featured=True).all()
    user = User.query.get(session.get('user_id')) if session.get('user_id') else None
    return render_template('index.html', products=products, featured_products=featured_products, user=user, whatsapp_link=WHATSAPP_GROUP_LINK)

client = genai.Client()

@app.route('/api/ai-assistant', methods=['POST'])
def ai_assistant():
    data = request.get_json() or {}
    user_msg = data.get('message', '').strip()

    if not user_msg:
        return jsonify({'reply': 'Bonjour ! Comment puis-je vous aider aujourd’hui chez TATAW x OFFX ?', 'products': []})

    all_products = Product.query.filter_by(in_stock=True).all()
    catalog_info = "\n".join([
        f"- [ID: {p.id}] {p.name} | Catégorie: {p.category} | Prix: {p.price} FCFA | Options: {p.options or 'Standard'}"
        for p in all_products
    ])

    system_prompt = f"""
    Tu es le Styliste IA officiel et conseiller de mode personnel pour la marque streetwear TATAW x OFFX.
    Réponds de manière humaine, chaleureuse et professionnelle.
    CATALOGUE ACTUEL :
    {catalog_info}
    À la fin de ta réponse, si tu recommandes des articles, indique leurs IDs sous la forme [RECOMMEND: id1, id2].
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nClient: {user_msg}\nStyliste TATAW:"
        )
        full_reply = response.text
        recommended_products = []
        
        if "[RECOMMEND:" in full_reply:
            parts = full_reply.split("[RECOMMEND:")
            reply_text = parts[0].strip()
            ids_str = parts[1].replace("]", "").strip()
            product_ids = [int(i.strip()) for i in ids_str.split(",") if i.strip().isdigit()]
            for p in all_products:
                if p.id in product_ids:
                    recommended_products.append({
                        'id': p.id,
                        'name': p.name,
                        'price': p.price or 'Sur demande',
                        'image_url': p.image_url
                    })
        else:
            reply_text = full_reply.strip()

        return jsonify({'reply': reply_text, 'products': recommended_products})
    except Exception as e:
        return jsonify({'reply': "Bienvenue chez TATAW x OFFX ! Que recherchez-vous ?", 'products': []})

@app.route('/api/visual-search', methods=['POST'])
def visual_search():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucune image envoyée'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400

    try:
        image_bytes = file.read()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                image_bytes,
                "Analyse cette image de vêtement/accessoire et identifie le style dominant, la couleur principale et la catégorie correspondante. Réponds uniquement au format JSON strict avec les clés: 'category', 'keywords'."
            ]
        )
        return jsonify({'status': 'success', 'analysis': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/login-auth', methods=['POST'])
def login_auth():
    username = request.form.get('username')
    phone = request.form.get('phone')
    email = request.form.get('email')
    login_method = request.form.get('login_method', 'whatsapp')

    if not username or (not phone and not email):
        flash("Informations requises manquantes.")
        return redirect(url_for('index'))

    user = User.query.filter((User.phone == phone) | (User.email == email)).first() if (phone or email) else None
    if not user:
        user = User(username=username, phone=phone or f"wa_{datetime.utcnow().timestamp()}", email=email, login_method=login_method, is_verified=True)
        db.session.add(user)
    else:
        user.username = username
        if email: user.email = email
        if phone: user.phone = phone
        user.login_method = login_method
    
    db.session.commit()
    session['user_id'] = user.id
    session['username'] = user.username
    flash(f"Connexion réussie avec {login_method.capitalize()} !")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Vous êtes déconnecté.")
    return redirect(url_for('index'))

# --- ADMINISTRATION ---

@app.route('/admin')
def admin():
    products = Product.query.all()
    promos = PromoCode.query.all()
    return render_template('admin.html', products=products, promos=promos, whatsapp_link=WHATSAPP_GROUP_LINK)

@app.route('/admin/add-product', methods=['POST'])
def add_product():
    try:
        photos = request.files.getlist('photos')
        first_image_url = ''
        saved_media = []
        
        for idx, photo in enumerate(photos):
            if photo and photo.filename != '':
                filename = secure_filename(photo.filename)
                file_bytes = photo.read()
                url = ''
                if supabase:
                    try:
                        path_on_storage = f"products/{datetime.utcnow().timestamp()}_{filename}"
                        supabase.storage.from_("tataw-media").upload(path_on_storage, file_bytes, file_options={"content-type": photo.content_type})
                        url = supabase.storage.from_("tataw-media").get_public_url(path_on_storage)
                    except Exception:
                        pass
                if not url:
                    os.makedirs('static/uploads', exist_ok=True)
                    filepath = os.path.join('static/uploads', filename)
                    photo.seek(0)
                    photo.save(filepath)
                    url = f'/{filepath}'
                
                if not first_image_url:
                    first_image_url = url
                saved_media.append((url, 'image'))

        if not first_image_url:
            first_image_url = "https://i.ibb.co/SXHNbgRS/Photoroom-20261006-212634.jpg"

        stock_qty = int(request.form.get('stock_qty') or 5)
        new_product = Product(
            name=request.form['name'],
            category=request.form.get('category', 'HOMME'),
            subcategory=request.form.get('subcategory', 'GENERAL'),
            price=request.form['price'],
            promo_info=request.form.get('promo_info', ''),
            stock_qty=stock_qty,
            options=request.form.get('options', 'Noir, Blanc'),
            description=request.form.get('description', ''),
            is_featured=True if request.form.get('is_featured') else False,
            in_stock=True if stock_qty > 0 else False,
            image_url=first_image_url
        )
        db.session.add(new_product)
        db.session.commit()

        for url, mtype in saved_media:
            db.session.add(ProductMedia(product_id=new_product.id, file_url=url, media_type=mtype))
        db.session.commit()

        notify_new_article(new_product)

        flash("Article ajouté avec succès !")
        return redirect('/admin')
    except Exception as e:
        flash(f"Erreur : {str(e)}")
        return redirect('/admin')

# Route ajoutée pour correspondre au formulaire admin.html et éliminer l'erreur 500
@app.route('/admin/edit-product/<int:id>', methods=['POST'])
def edit_product(id):
    try:
        product = Product.query.get_or_404(id)
        product.name = request.form.get('name', product.name)
        product.price = request.form.get('price', product.price)
        product.stock_qty = int(request.form.get('stock_qty') or product.stock_qty)
        product.in_stock = True if product.stock_qty > 0 else False

        image_file = request.files.get('image_file')
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            file_bytes = image_file.read()
            url = ''
            if supabase:
                try:
                    path_on_storage = f"products/{datetime.utcnow().timestamp()}_{filename}"
                    supabase.storage.from_("tataw-media").upload(path_on_storage, file_bytes, file_options={"content-type": image_file.content_type})
                    url = supabase.storage.from_("tataw-media").get_public_url(path_on_storage)
                except Exception:
                    pass
            if not url:
                os.makedirs('static/uploads', exist_ok=True)
                filepath = os.path.join('static/uploads', filename)
                image_file.seek(0)
                image_file.save(filepath)
                url = f'/{filepath}'
            product.image_url = url

        db.session.commit()
        flash("Article mis à jour avec succès !")
        return redirect('/admin')
    except Exception as e:
        flash(f"Erreur lors de la modification : {str(e)}")
        return redirect('/admin')

@app.route('/admin/delete-product/<int:id>', methods=['POST'])
def delete_product(id):
    ProductMedia.query.filter_by(product_id=id).delete()
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Produit supprimé !')
    return redirect(url_for('admin'))

@app.route('/admin/add-promo', methods=['POST'])
def add_promo():
    try:
        code = request.form.get('code', '').strip().upper()
        discount = int(request.form.get('discount') or 10)
        influencer = request.form.get('influencer', '')
        if code:
            new_promo = PromoCode(code=code, discount_percent=discount, influencer_name=influencer)
            db.session.add(new_promo)
            db.session.commit()
            flash("Code promo ajouté !")
        return redirect('/admin')
    except Exception as e:
        flash(f"Erreur promo: {str(e)}")
        return redirect('/admin')

@app.route('/admin/delete-promo/<int:id>', methods=['POST'])
def delete_promo(id):
    promo = PromoCode.query.get_or_404(id)
    db.session.delete(promo)
    db.session.commit()
    flash("Code promo supprimé !")
    return redirect('/admin')

# --- REINFORCEMENT LEARNING ---

@app.route('/api/rl/recommend', methods=['POST'])
def get_rl_recommendation():
    data = request.get_json() or {}
    user_id = data.get('user_id', 'anonymous')
    category = data.get('category', 'All')
    
    products = Product.query.filter_by(in_stock=True).all()
    product_ids = [p.id for p in products]

    if not product_ids:
        return jsonify({'error': 'Aucun produit'}), 404

    config = RLModelConfig.query.filter_by(is_active=True).first()
    active_mode = config.model_name if config else 'standard_sales'

    history = RLInteraction.query.all()
    rl_agent.train_from_history(history, product_ids)
    chosen_id = rl_agent.recommend(category, product_ids, active_mode)

    interaction = RLInteraction(user_id=user_id, context_category=category, action_product_id=chosen_id, reward=0.0)
    db.session.add(interaction)
    db.session.commit()

    return jsonify({'recommended_product_id': chosen_id, 'interaction_id': interaction.id})

@app.route('/api/rl/reward', methods=['POST'])
def set_rl_reward():
    data = request.get_json() or {}
    interaction_id = data.get('interaction_id')
    reward_value = data.get('reward', 1.0)
    interaction = RLInteraction.query.get(interaction_id)
    if interaction:
        interaction.reward = float(reward_value)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

if __name__ == '__main__':
    app.run(debug=True)