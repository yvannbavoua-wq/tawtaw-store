import os
from datetime import datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from rl_agent import rl_agent
from werkzeug.utils import secure_filename
from google import genai

# Intégration sécurisée de Supabase pour éviter les plantages si le module n'est pas installé
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except ImportError:
    supabase = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tataw_secret_key_change_in_production')

# Connexion Supabase / PostgreSQL ou fallback SQLite
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
    media_type = db.Column(db.String(50), nullable=False)  # 'image' ou 'video'
    caption = db.Column(db.String(255), nullable=True)     # Description spécifique liée à l'image

class PromoCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=False)
    influencer_name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    operator = db.Column(db.String(20), nullable=True)  # ORANGE ou MTN
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

class PollVote(db.Model):
    __tablename__ = 'poll_votes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    chosen_model = db.Column(db.String(50), nullable=False)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialisation automatique de toutes les tables
with app.app_context():
    db.create_all()
    if not Product.query.first():
        default_p = Product(
            name="Tawtaw t-shirt",
            category="HOMME",
            subcategory="T-SHIRTS",
            image_url="https://i.ibb.co/SXHNbgRS/Photoroom-20261006-212634.jpg",
            price="6000",
            options="Noir, Blanc, Bleu",
            description="T-shirt officiel TATAW - Édition limitée 2026",
            is_featured=True,
            in_stock=True,
            stock_qty=3,
            rating=4.9
        )
        db.session.add(default_p)
        db.session.commit()

# --- ROUTES SITE & USER ---

@app.route('/')
def index():
    products = Product.query.all()
    featured_products = Product.query.filter_by(is_featured=True).all()
    user = User.query.get(session.get('user_id')) if session.get('user_id') else None
    return render_template('index.html', products=products, featured_products=featured_products, user=user)

# Initialisation du client Gemini API
client = genai.Client()

@app.route('/api/ai-assistant', methods=['POST'])
def ai_assistant():
    data = request.get_json() or {}
    user_msg = data.get('message', '').strip()

    if not user_msg:
        return jsonify({'reply': 'Bonjour ! Comment puis-je vous aider aujourd’hui ?', 'products': []})

    all_products = Product.query.filter_by(in_stock=True).all()
    catalog_info = "\n".join([
        f"- [ID: {p.id}] {p.name} | Catégorie: {p.category} | Sous-catégorie: {p.subcategory} | Prix: {p.price} FCFA | Options: {p.options or 'Standard'} | Description: {p.description or 'Streetwear premium'}"
        for p in all_products
    ])

    system_prompt = f"""
    Tu es le Styliste IA officiel et conseiller de mode personnel pour la marque de streetwear premium TATAW (fondée à Yaoundé).
    Sois 100% humain, chaleureux, naturel et dynamique. Adapte-toi au ton du client.
    Ne balance pas directement les produits si le client dit juste bonjour. Réponds-lui naturellement d'abord.
    Analyse son style (streetwear, habillé, casual, etc.) et ses préférences.
    
    CATALOGUE ACTUELLEMENT DISPONIBLE :
    {catalog_info}

    À la fin de ta réponse texte, si tu recommandes des produits, indique leurs IDs sous la forme [RECOMMEND: id1, id2].
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
                        'image': p.image_url
                    })
        else:
            reply_text = full_reply.strip()

        return jsonify({
            'reply': reply_text,
            'products': recommended_products
        })

    except Exception as e:
        print(f"Erreur Styliste IA: {e}")
        return jsonify({
            'reply': "Ravi de vous accueillir chez TATAW ! Que recherchez-vous comme style aujourd'hui ?",
            'products': []
        })

@app.route('/api/check-promo', methods=['POST'])
def check_promo():
    data = request.get_json() or {}
    code_input = data.get('code', '').strip().upper()
    promo = PromoCode.query.filter_by(code=code_input, is_active=True).first()
    
    if promo:
        return jsonify({
            'valid': True,
            'code': promo.code,
            'discount': promo.discount_percent,
            'influencer': promo.influencer_name or 'Offre Spéciale'
        })
    return jsonify({'valid': False, 'message': 'Code promo invalide ou expiré'})

@app.route('/login-whatsapp', methods=['POST'])
def login_whatsapp():
    username = request.form.get('username')
    phone = request.form.get('phone')
    operator = request.form.get('operator')
    country = request.form.get('country')
    city = request.form.get('city')

    if not username or not phone:
        flash("Veuillez remplir tous les champs obligatoires.")
        return redirect(url_for('index'))

    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(username=username, phone=phone, operator=operator, country=country, city=city, is_verified=True)
        db.session.add(user)
    else:
        user.username = username
        user.operator = operator
        user.country = country
        user.city = city
        user.is_verified = True
    
    db.session.commit()
    session['user_id'] = user.id
    session['username'] = user.username
    session['phone'] = user.phone

    flash(f"Bienvenue {user.username} !")
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
    return render_template('admin.html', products=products, promos=promos)

@app.route('/admin/add-product', methods=['POST'])
def add_product():
    try:
        photos = request.files.getlist('photos')
        captions = request.form.getlist('captions')
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
                        supabase.storage.from_("tataw-media").upload(
                            path_on_storage, 
                            file_bytes, 
                            file_options={"content-type": photo.content_type}
                        )
                        url = supabase.storage.from_("tataw-media").get_public_url(path_on_storage)
                    except Exception as ex:
                        print(f"Erreur Supabase Storage: {ex}")
                
                if not url:
                    os.makedirs('static/uploads', exist_ok=True)
                    filepath = os.path.join('static/uploads', filename)
                    photo.seek(0)
                    photo.save(filepath)
                    url = f'/static/uploads/{filename}'

                caption_text = captions[idx] if idx < len(captions) and captions[idx].strip() != '' else f"Vue {idx+1}"
                if not first_image_url:
                    first_image_url = url
                saved_media.append((url, 'image', caption_text))

        if not first_image_url:
            first_image_url = "https://i.ibb.co/SXHNbgRS/Photoroom-20261006-212634.jpg"

        new_product = Product(
            name=request.form['name'],
            category=request.form.get('category'),
            subcategory=request.form.get('subcategory'),
            price=request.form['price'],
            promo_info=request.form.get('promo_info', ''),
            stock_qty=int(request.form.get('stock_qty') or 5),
            options=request.form.get('options', ''),
            description=request.form.get('description', ''),
            is_featured=True if request.form.get('is_featured') else False,
            in_stock=True if request.form.get('in_stock') else True,
            image_url=first_image_url
        )
        db.session.add(new_product)
        db.session.commit()

        for url, mtype, cap in saved_media:
            db.session.add(ProductMedia(product_id=new_product.id, file_url=url, media_type=mtype, caption=cap))

        for video in request.files.getlist('videos'):
            if video and video.filename != '':
                filename = secure_filename(video.filename)
                v_bytes = video.read()
                v_url = ''
                if supabase:
                    try:
                        path_on_storage = f"products/vid_{datetime.utcnow().timestamp()}_{filename}"
                        supabase.storage.from_("tataw-media").upload(
                            path_on_storage, 
                            v_bytes, 
                            file_options={"content-type": video.content_type}
                        )
                        v_url = supabase.storage.from_("tataw-media").get_public_url(path_on_storage)
                    except Exception:
                        pass
                
                if not v_url:
                    os.makedirs('static/uploads', exist_ok=True)
                    filepath = os.path.join('static/uploads', filename)
                    video.seek(0)
                    video.save(filepath)
                    v_url = f'/static/uploads/{filename}'
                
                db.session.add(ProductMedia(product_id=new_product.id, file_url=v_url, media_type='video', caption="Vidéo produit"))

        db.session.commit()
        flash("Article ajouté avec succès !")
        return redirect('/admin')
    except Exception as e:
        print(f"Erreur critique lors de l'ajout du produit: {e}")
        flash(f"Erreur lors de l'ajout : {str(e)}")
        return redirect('/admin')

@app.route('/admin/add-promo', methods=['POST'])
def add_promo():
    code = request.form.get('code', '').strip().upper()
    discount = request.form.get('discount', type=int)
    influencer = request.form.get('influencer', '')

    if code and discount:
        new_promo = PromoCode(code=code, discount_percent=discount, influencer_name=influencer)
        db.session.add(new_promo)
        db.session.commit()
        flash('Code promo créé !')
    return redirect(url_for('admin'))

@app.route('/admin/delete-promo/<int:id>', methods=['POST'])
def delete_promo(id):
    promo = PromoCode.query.get_or_404(id)
    db.session.delete(promo)
    db.session.commit()
    flash('Code promo supprimé !')
    return redirect(url_for('admin'))

@app.route('/admin/edit-product/<int:id>', methods=['POST'])
def edit_product(id):
    product = Product.query.get_or_404(id)
    
    product.name = request.form.get('name', product.name)
    product.price = request.form.get('price', product.price)
    product.promo_info = request.form.get('promo_info', product.promo_info)
    product.options = request.form.get('options', product.options)
    product.description = request.form.get('description', product.description)
    product.stock_qty = int(request.form.get('stock_qty', product.stock_qty) or product.stock_qty)
    product.is_featured = True if request.form.get('is_featured') else False
    product.in_stock = True if request.form.get('in_stock') else False

    image_file = request.files.get('image_file')
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        img_bytes = image_file.read()
        if supabase:
            path_on_storage = f"products/{datetime.utcnow().timestamp()}_{filename}"
            supabase.storage.from_("tataw-media").upload(
                path_on_storage, img_bytes, file_options={"content-type": image_file.content_type}
            )
            product.image_url = supabase.storage.from_("tataw-media").get_public_url(path_on_storage)
        else:
            upload_folder = 'static/uploads'
            os.makedirs(upload_folder, exist_ok=True)
            filepath = os.path.join(upload_folder, filename)
            product.image_url = f"/{filepath}"

    db.session.commit()
    flash('Article modifié avec succès !')
    return redirect(url_for('admin'))

@app.route('/admin/delete-product/<int:id>', methods=['POST'])
def delete_product(id):
    ProductMedia.query.filter_by(product_id=id).delete()
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Produit supprimé avec succès !')
    return redirect(url_for('admin'))

# --- ROUTES RL & SONDAGE ---

@app.route('/api/rl/recommend', methods=['POST'])
def get_rl_recommendation():
    data = request.get_json() or {}
    user_id = data.get('user_id', 'anonymous')
    category = data.get('category', 'autre')
    
    products = Product.query.filter_by(in_stock=True).all()
    product_ids = [p.id for p in products]

    if not product_ids:
        return jsonify({'error': 'Aucun produit disponible'}), 404

    config = RLModelConfig.query.filter_by(is_active=True).first()
    active_mode = config.model_name if config else 'standard_sales'

    history = RLInteraction.query.all()
    rl_agent.train_from_history(history, product_ids)

    chosen_id = rl_agent.recommend(category, product_ids, active_mode)

    interaction = RLInteraction(
        user_id=user_id,
        context_category=category,
        action_product_id=chosen_id,
        reward=0.0
    )
    db.session.add(interaction)
    db.session.commit()

    return jsonify({
        'recommended_product_id': chosen_id,
        'interaction_id': interaction.id,
        'active_model': active_mode
    })

@app.route('/api/rl/reward', methods=['POST'])
def set_rl_reward():
    data = request.get_json() or {}
    interaction_id = data.get('interaction_id')
    reward_value = data.get('reward', 1.0)

    interaction = RLInteraction.query.get(interaction_id)
    if interaction:
        interaction.reward = float(reward_value)
        db.session.commit()
        return jsonify({'status': 'success', 'reward': interaction.reward})
    return jsonify({'status': 'error', 'message': 'Interaction introuvable'}), 404

@app.route('/api/poll/vote', methods=['POST'])
def submit_poll_vote():
    data = request.get_json() or {}
    user_id = data.get('user_id', 'anonymous')
    chosen_model = data.get('chosen_model')

    if not chosen_model:
        return jsonify({'error': 'Modèle non spécifié'}), 400

    vote = PollVote(user_id=user_id, chosen_model=chosen_model)
    db.session.add(vote)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Vote enregistré avec succès'})

if __name__ == '__main__':
    app.run(debug=True)