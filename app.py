import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tataw_secret_key_change_in_production')

# Connexion Supabase / PostgreSQL ou fallback SQLite
db_url = os.environ.get('DATABASE_URL', 'sqlite:///tataw.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
    stock_qty = db.Column(db.Integer, default=5) # NOUVEAU: Stock restant
    rating = db.Column(db.Float, default=5.0)     # NOUVEAU: Note par étoiles

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
    is_verified = db.Column(db.Boolean, default=True)

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
            description="T-shirt officiel TATAW  - Édition limitée 2026",
            is_featured=True,
            in_stock=True,
            stock_qty=3,
            rating=4.9
        )
        db.session.add(default_p)
        db.session.commit()

@app.route('/')
def index():
    products = Product.query.all()
    featured_products = Product.query.filter_by(is_featured=True).all()
    user = User.query.get(session.get('user_id')) if session.get('user_id') else None
    return render_template('index.html', products=products, featured_products=featured_products, user=user)

# --- API Assistant IA Styliste ---
@app.route('/api/ai-assistant', methods=['POST'])
def ai_assistant():
    data = request.get_json()
    user_msg = data.get('message', '').lower()
    products = Product.query.filter_by(in_stock=True).all()
    recommendations = []
    response_text = "Je suis votre Styliste IA TATAW ! 👋 "

    if "homme" in user_msg or "garçon" in user_msg:
        matched = [p for p in products if p.category.upper() == 'HOMME']
        recommendations = matched[:3]
        response_text += "Voici les meilleures pièces pour Homme de notre collection actuelle :"
    elif "femme" in user_msg or "fille" in user_msg:
        matched = [p for p in products if p.category.upper() == 'FEMME']
        recommendations = matched[:3]
        response_text += "Voici nos sélections coup de cœur pour Femme :"
    elif "cosmétique" in user_msg or "beaute" in user_msg:
        matched = [p for p in products if p.category.upper() == 'COSMETIQUES']
        recommendations = matched[:3]
        response_text += "Voici nos articles cosmétiques :"
    else:
        recommendations = products[:2]
        response_text += "Voici nos pépites du moment disponibles immédiatement :"

    recs_data = [{
        'id': p.id,
        'name': p.name,
        'price': p.price or 'Sur demande',
        'image': p.image_url
    } for p in recommendations]

    return jsonify({'reply': response_text, 'products': recs_data})

# --- API Vérification Code Promo ---
@app.route('/api/check-promo', methods=['POST'])
def check_promo():
    data = request.get_json()
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

    if not username or not phone:
        flash("Veuillez remplir tous les champs.")
        return redirect(url_for('index'))

    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(username=username, phone=phone, is_verified=True)
        db.session.add(user)
    else:
        user.username = username
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

# --- Administration ---
@app.route('/admin')
def admin():
    products = Product.query.all()
    promos = PromoCode.query.all()
    return render_template('admin.html', products=products, promos=promos)

@app.route('/admin/add-product', methods=['POST'])
def add_product():
    name = request.form.get('name')
    category = request.form.get('category')
    subcategory = request.form.get('subcategory')
    image_url = request.form.get('image_url')
    price = request.form.get('price', '')
    promo_info = request.form.get('promo_info', '')
    options = request.form.get('options', '')
    description = request.form.get('description', '')
    stock_qty = request.form.get('stock_qty', type=int) or 5
    is_featured = True if request.form.get('is_featured') else False
    in_stock = True if request.form.get('in_stock') else False

    if name and category and subcategory and image_url:
        new_prod = Product(
            name=name, category=category, subcategory=subcategory,
            image_url=image_url, price=price, promo_info=promo_info,
            options=options, description=description, stock_qty=stock_qty,
            is_featured=is_featured, in_stock=in_stock
        )
        db.session.add(new_prod)
        db.session.commit()
        flash('Produit ajouté !')
    return redirect(url_for('admin'))

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

@app.route('/admin/update-product/<int:id>', methods=['POST'])
def update_product(id):
    product = Product.query.get_or_404(id)
    product.image_url = request.form.get('image_url', product.image_url)
    product.price = request.form.get('price', product.price)
    product.promo_info = request.form.get('promo_info', product.promo_info)
    product.options = request.form.get('options', product.options)
    product.description = request.form.get('description', product.description)
    product.stock_qty = request.form.get('stock_qty', type=int) or product.stock_qty
    product.is_featured = True if request.form.get('is_featured') else False
    product.in_stock = True if request.form.get('in_stock') else False
    db.session.commit()
    flash('Produit mis à jour !')
    return redirect(url_for('admin'))

@app.route('/admin/delete-product/<int:id>', methods=['POST'])
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Produit supprimé !')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)