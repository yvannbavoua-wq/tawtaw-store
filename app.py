import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = 'tataw_secret_key_change_in_production'

# Configuration Base de données
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tataw.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Credentials Twilio pour WhatsApp (Optionnel)
TWILIO_ACCOUNT_SID = 'votre_account_sid'
TWILIO_AUTH_TOKEN = 'votre_auth_token'
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID != 'votre_account_sid' else None

# Modèle Produit mis à jour (avec options/modèles et description)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(50), nullable=True)
    options = db.Column(db.String(200), nullable=True) # Modèles, tailles, couleurs...
    description = db.Column(db.Text, nullable=True)

# Modèle Utilisateur pour l'authentification WhatsApp
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    otp_code = db.Column(db.String(6), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    products = Product.query.all()
    user = User.query.get(session.get('user_id')) if session.get('user_id') else None
    return render_template('index.html', products=products, user=user)

# --- Authentification WhatsApp (OTP) ---
@app.route('/login-whatsapp', methods=['POST'])
def request_otp():
    username = request.form.get('username')
    phone = request.form.get('phone')

    if not username or not phone:
        flash("Veuillez remplir tous les champs.")
        return redirect(url_for('index'))

    otp = str(random.randint(100000, 999999))
    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(username=username, phone=phone)
        db.session.add(user)
    
    user.username = username
    user.otp_code = otp
    db.session.commit()

    if twilio_client:
        try:
            twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=f"Bonjour {username} ! Votre code de vérification TATAW est : {otp}",
                to=f"whatsapp:{phone}"
            )
            session['pending_phone'] = phone
            flash("Code envoyé par WhatsApp !")
            return redirect(url_for('verify_otp_page'))
        except Exception:
            flash("Erreur lors de l'envoi WhatsApp.")
            return redirect(url_for('index'))
    else:
        session['pending_phone'] = phone
        return redirect(url_for('verify_otp_page'))

@app.route('/verify-otp-page')
def verify_otp_page():
    return render_template('verify_otp.html')

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    user_code = request.form.get('otp_code')
    phone = session.get('pending_phone')
    user = User.query.filter_by(phone=phone).first() if phone else None

    if user and user.otp_code == user_code:
        user.is_verified = True
        user.otp_code = None
        db.session.commit()
        session['user_id'] = user.id
        session['username'] = user.username
        session.pop('pending_phone', None)
        flash(f"Bienvenue {user.username} !")
        return redirect(url_for('index'))
    else:
        flash("Code incorrect. Réessayez.")
        return redirect(url_for('verify_otp_page'))

# --- Administration ---
@app.route('/admin')
def admin():
    products = Product.query.all()
    return render_template('admin.html', products=products)

@app.route('/admin/add-product', methods=['POST'])
def add_product():
    name = request.form.get('name')
    category = request.form.get('category')
    subcategory = request.form.get('subcategory')
    image_url = request.form.get('image_url')
    price = request.form.get('price', '')
    options = request.form.get('options', '')
    description = request.form.get('description', '')

    if name and category and subcategory and image_url:
        new_prod = Product(
            name=name, category=category, subcategory=subcategory,
            image_url=image_url, price=price, options=options, description=description
        )
        db.session.add(new_prod)
        db.session.commit()
        flash('Produit ajouté !')
    return redirect(url_for('admin'))

@app.route('/admin/update-product/<int:id>', methods=['POST'])
def update_product(id):
    product = Product.query.get_or_404(id)
    product.image_url = request.form.get('image_url', product.image_url)
    product.price = request.form.get('price', product.price)
    product.options = request.form.get('options', product.options)
    product.description = request.form.get('description', product.description)
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
