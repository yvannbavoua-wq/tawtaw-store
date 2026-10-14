import os
from datetime import datetime
import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from rl_agent import rl_agent
from werkzeug.utils import secure_filename
from google import genai
from tataw_ai_memory import tataw_brain

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

class ProductVariant(db.Model):
    """Gestion autonome des stocks par taille (S, M, L, XL), couleur et photo spécifique"""
    __tablename__ = 'product_variants'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    stock_qty = db.Column(db.Integer, default=1)
    image_url = db.Column(db.Text, nullable=True)

class ProductMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    file_url = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(50), nullable=False) # 'image' ou 'hero_mannequin'
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

    # Auto-migrations SQL explicites pour compatibilité de structure
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE product_media ADD COLUMN IF NOT EXISTS caption VARCHAR(255);"))
            conn.execute(db.text("ALTER TABLE product_variants ADD COLUMN IF NOT EXISTS image_url TEXT;"))
            conn.commit()
    except Exception as e:
        print(f"Migration DB note : {e}")

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
        
        # Initialisation des variantes (S, M, L, XL) avec l'image par défaut
        for color in ["Noir", "Blanc", "Bleu"]:
            for size in ["S", "M", "L", "XL"]:
                db.session.add(ProductVariant(
                    product_id=default_p.id, 
                    color=color, 
                    size=size, 
                    stock_qty=2,
                    image_url=default_p.image_url
                ))
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

# --- HELPER TELEVERSEMENT MEDIAS ---

def save_uploaded_file(photo, subfolder="products"):
    if not photo or photo.filename == '':
        return ''
    filename = secure_filename(photo.filename)
    file_bytes = photo.read()
    url = ''
    if supabase:
        try:
            path = f"{subfolder}/{datetime.utcnow().timestamp()}_{filename}"
            supabase.storage.from_("tataw-media").upload(path, file_bytes, file_options={"content-type": photo.content_type})
            url = supabase.storage.from_("tataw-media").get_public_url(path)
        except Exception:
            pass
    if not url:
        target_dir = os.path.join('static', 'uploads', subfolder)
        os.makedirs(target_dir, exist_ok=True)
        filepath = os.path.join(target_dir, filename)
        photo.seek(0)
        photo.save(filepath)
        url = f'/{filepath}'
    return url

# --- ROUTES PRINCIPALES ---

@app.route('/api/ping')
def ping():
    return jsonify({'status': 'active'}), 200

@app.route('/')
def index():
    products = Product.query.all()
    featured_products = Product.query.filter_by(is_featured=True).all()
    hero_media = ProductMedia.query.filter_by(media_type='hero_mannequin').all()
    user = User.query.get(session.get('user_id')) if session.get('user_id') else None
    return render_template('index.html', products=products, featured_products=featured_products, hero_media=hero_media, user=user, whatsapp_link=WHATSAPP_GROUP_LINK)

@app.route('/api/product-variants/<int:id>')
def get_product_variants(id):
    variants = ProductVariant.query.filter_by(product_id=id).all()
    data = [{
        'id': v.id,
        'color': v.color, 
        'size': v.size, 
        'stock_qty': v.stock_qty,
        'image_url': v.image_url
    } for v in variants]
    return jsonify({'variants': data})

client = genai.Client()

@app.route('/api/ai-assistant', methods=['POST'])
def ai_assistant():
    data = request.get_json() or {}
    user_msg = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_msg:
        return jsonify({'reply': "Yo ! Je suis Lia, l'assistant officiel TATAW x OFFX. En quoi puis-je te styliser aujourd'hui ?", 'products': []})

    master_context = tataw_brain.get_full_context()

    system_instruction = f"""
    Tu es Lia, l'Assistant IA Exclusif, Expert Styliste et Ambassadeur de Marque pour TATAW x OFFX (Yaoundé / Douala).
    Tu te comportes comme un personal shopper de haute voltige : charismatique, précis, chaleureux et passionné.

    --- SOCLE D'EXPERTISE MODE & STREETWEAR ---
    - Maîtrise totale des codes streetwear (oversize, boxy fit, layering, techwear, minimalisme urbain, contrastes de matières).
    - Capable de conseiller les coupes idéales selon la morphologie, les associations de couleurs et de proposer des assemblages complets.
    - Attitude urbaine, raffinée, accessible et professionnelle.

    {master_context}

    DIRECTIVES STRICTES :
    1. LANGUE : Détecte automatiquement la langue (Français, Anglais, Pidgin) et réponds dans la même langue.
    2. VENTE CROISÉE & CONSEIL : Utilise le catalogue ci-dessus en temps réel pour suggérer les tailles (S, M, L, XL), verifier les prix en FCFA et proposer des ensembles.
    3. HISTOIRE : Valorise l'alliance des deux frères (offx & nybe) et l'identité nomade streetwear de TATAW.
    """

    try:
        chat_contents = [system_instruction]
        for h in history:
            role = "Utilisateur" if h.get('sender') == 'user' else "Assistant Lia (TATAW)"
            chat_contents.append(f"{role}: {h.get('text')}")
            
        chat_contents.append(f"Utilisateur: {user_msg}\nAssistant Lia (TATAW):")

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents="\n".join(chat_contents)
        )
        return jsonify({'reply': response.text.strip(), 'products': []})
    except Exception as e:
        return jsonify({'reply': "Yo ! Bienvenue chez TATAW x OFFX. Dis-moi ce que tu cherches aujourd'hui, je m'en occupe !", 'products': []})

@app.route('/api/generate-image', methods=['POST'])
def generate_image_route():
    data = request.get_json() or {}
    prompt = data.get('prompt', '').strip()
    user_id = session.get('user_id', request.remote_addr)

    allowed, count = tataw_brain.check_and_increment_image_quota(user_id)
    if not allowed:
        return jsonify({'error': "Quota quotidien atteint (5/5). Réessayez demain !"}), 429

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Génère une description de visuel streetwear TATAW x OFFX : {prompt}"
        )
        return jsonify({'status': 'success', 'result': response.text, 'quota_used': count, 'quota_max': 5})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-file', methods=['POST'])
def analyze_file():
    files = request.files.getlist('file')
    if not files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400
    
    results = []
    for file in files:
        file_bytes = file.read()
        file_type = file.content_type or ""

        try:
            if file_type.startswith('image/'):
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[file_bytes, "Analyse ce vêtement ou accessoire pour l'univers streetwear TATAW x OFFX."]
                )
                results.append(response.text)
            elif file_type.startswith('audio/'):
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[file_bytes, "Transcris cet audio et réponds à la demande client pour TATAW x OFFX."]
                )
                results.append(response.text)
            else:
                results.append(f"Format non pris en charge pour {file.filename}")
        except Exception as e:
            results.append(f"Erreur sur {file.filename}: {str(e)}")

    return jsonify({'analysis': "<br><br>".join(results)})

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

# --- ADMINISTRATION & GÉRANCE PAR L'IA ---

@app.route('/admin')
def admin():
    products = Product.query.all()
    promos = PromoCode.query.all()
    hero_media = ProductMedia.query.filter_by(media_type='hero_mannequin').all()
    variants = ProductVariant.query.all()
    return render_template('admin.html', products=products, promos=promos, hero_media=hero_media, variants=variants, whatsapp_link=WHATSAPP_GROUP_LINK)

@app.route('/api/admin/lia-report')
def get_lia_report():
    """Génère un rapport d'état de l'IA (Lia) pour le centre de contrôle Admin"""
    products_count = Product.query.count()
    total_stock = db.session.query(db.func.sum(Product.stock_qty)).scalar() or 0
    interactions_count = RLInteraction.query.count()
    return jsonify({
        'status': 'Opérationnel',
        'model': 'gemini-2.5-flash',
        'catalog_synced_items': products_count,
        'total_units_tracked': total_stock,
        'rl_interactions_total': interactions_count,
        'last_sync': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    })

@app.route('/admin/add-hero-media', methods=['POST'])
def add_hero_media():
    try:
        photos = request.files.getlist('hero_photos')
        if not photos or photos[0].filename == '':
            # Fallback champ unique si envoyé sous un autre nom
            p = request.files.get('hero_photo')
            photos = [p] if p else []

        count = 0
        for photo in photos:
            if photo and photo.filename != '':
                url = save_uploaded_file(photo, subfolder="hero")
                if url:
                    db.session.add(ProductMedia(product_id=0, file_url=url, media_type='hero_mannequin'))
                    count += 1
        
        if count > 0:
            db.session.commit()
            flash(f"{count} visuel(s) ajouté(s) au carrousel haut de page avec succès !")
        return redirect('/admin')
    except Exception as e:
        flash(f"Erreur visuel mannequin : {e}")
        return redirect('/admin')

@app.route('/admin/add-product', methods=['POST'])
def add_product():
    try:
        photos = request.files.getlist('photos')
        first_image_url = ''
        saved_media = []
        
        for photo in photos:
            if photo and photo.filename != '':
                url = save_uploaded_file(photo, subfolder="products")
                if url:
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

        colors = [c.strip() for c in new_product.options.split(',')] if new_product.options else ['Noir']
        for color in colors:
            for size in ['S', 'M', 'L', 'XL']:
                db.session.add(ProductVariant(
                    product_id=new_product.id, 
                    color=color, 
                    size=size, 
                    stock_qty=2,
                    image_url=first_image_url
                ))
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

@app.route('/admin/add-variant', methods=['POST'])
def add_variant():
    """Route pour ajouter ou associer une photo/stock à une couleur et taille spécifique"""
    try:
        product_id = int(request.form['product_id'])
        color = request.form['color'].strip()
        size = request.form['size'].strip()
        stock_qty = int(request.form.get('stock_qty', 1))

        photo = request.files.get('variant_photo')
        image_url = save_uploaded_file(photo, subfolder="variants") if photo else None

        existing = ProductVariant.query.filter_by(product_id=product_id, color=color, size=size).first()
        if existing:
            existing.stock_qty = stock_qty
            if image_url:
                existing.image_url = image_url
        else:
            p = Product.query.get(product_id)
            img = image_url or (p.image_url if p else '')
            db.session.add(ProductVariant(
                product_id=product_id,
                color=color,
                size=size,
                stock_qty=stock_qty,
                image_url=img
            ))
        db.session.commit()
        flash("Déclinaison couleur/taille mise à jour !")
    except Exception as e:
        flash(f"Erreur ajout déclinaison : {e}")
    return redirect('/admin')

@app.route('/admin/delete-variant/<int:id>', methods=['POST'])
def delete_variant(id):
    variant = ProductVariant.query.get_or_404(id)
    db.session.delete(variant)
    db.session.commit()
    flash("Déclinaison supprimée !")
    return redirect('/admin')

@app.route('/admin/update-product/<int:id>', methods=['POST'])
def update_product(id):
    try:
        product = Product.query.get_or_404(id)
        product.name = request.form.get('name', product.name)
        product.price = request.form.get('price', product.price)
        
        stock_qty = request.form.get('stock_qty')
        if stock_qty is not None:
            product.stock_qty = int(stock_qty)
            product.in_stock = True if int(stock_qty) > 0 else False

        photo = request.files.get('image')
        if photo and photo.filename != '':
            url = save_uploaded_file(photo, subfolder="products")
            if url:
                product.image_url = url

        db.session.commit()
        flash("Article mis à jour avec succès !")
    except Exception as e:
        flash(f"Erreur mise à jour : {e}")
    return redirect('/admin')

@app.route('/admin/delete-product/<int:id>', methods=['POST'])
def delete_product(id):
    ProductMedia.query.filter_by(product_id=id).delete()
    ProductVariant.query.filter_by(product_id=id).delete()
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Produit supprimé !')
    return redirect(url_for('admin'))

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

if __name__ == '__main__':
    app.run(debug=True)