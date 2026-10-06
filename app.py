import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tataw_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tataw.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modèle Produit
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False) # homme, femme, cosmetiques
    subcategory = db.Column(db.String(50), nullable=False) # tshirts, pulls, croptops, ensembles, babouches, chaussures, chaussettes, sacs
    image_url = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(50), nullable=True, default="")

# Initialisation de la base de données avec des produits par défaut
def init_db():
    db.create_all()
    if Product.query.count() == 0:
        default_products = [
            Product(name="T-Shirt TATAW (Noir, Blanc, Rose, Rouge)", category="homme", subcategory="tshirts", image_url="https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=600&q=80", price="6000"),
            Product(name="Pull TATAW Noir", category="homme", subcategory="pulls", image_url="https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=600&q=80", price="10000"),
            Product(name="Croptop TATAW (Noir, Blanc, Rose, Rouge)", category="femme", subcategory="croptops", image_url="https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80", price="6000"),
            Product(name="Ensemble TATAW Homme", category="homme", subcategory="ensembles", image_url="https://images.unsplash.com/photo-1552374196-1ab2a1c593e8?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Babouches TATAW Homme", category="homme", subcategory="babouches", image_url="https://images.unsplash.com/photo-1543163521-1bf539c55dd2?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Chaussures TATAW Homme", category="homme", subcategory="chaussures", image_url="https://images.unsplash.com/photo-1549298916-b41d501d3772?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Chaussettes TATAW Homme", category="homme", subcategory="chaussettes", image_url="https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Ensemble TATAW Femme", category="femme", subcategory="ensembles", image_url="https://images.unsplash.com/photo-1485230895905-ec40ba36b9bc?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Babouches TATAW Femme", category="femme", subcategory="babouches", image_url="https://images.unsplash.com/photo-1560343090-f0409e92791a?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Chaussures TATAW Femme", category="femme", subcategory="chaussures", image_url="https://images.unsplash.com/photo-1543163521-1bf539c55dd2?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Chaussettes TATAW Femme", category="femme", subcategory="chaussettes", image_url="https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?auto=format&fit=crop&w=600&q=80", price=""),
            Product(name="Sac TATAW Femme", category="femme", subcategory="sacs", image_url="https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=600&q=80", price="")
        ]
        db.session.bulk_save_objects(default_products)
        db.session.commit()
with app.app_context():
    init_db()
    
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/admin')
def admin_page():
    products = Product.query.all()
    return render_template('admin.html', products=products)

# API Endpoints
@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'category': p.category,
        'subcategory': p.subcategory,
        'image_url': p.image_url,
        'price': p.price
    } for p in products])

@app.route('/admin/add-product', methods=['POST'])
def add_product():
    name = request.form.get('name')
    category = request.form.get('category')
    subcategory = request.form.get('subcategory')
    image_url = request.form.get('image_url')
    price = request.form.get('price', '')

    new_prod = Product(name=name, category=category, subcategory=subcategory, image_url=image_url, price=price)
    db.session.add(new_prod)
    db.session.commit()
    flash('Produit ajouté avec succès !', 'success')
    return redirect(url_for('admin_page'))

@app.route('/admin/update-product/<int:id>', methods=['POST'])
def update_product(id):
    prod = Product.query.get_or_404(id)
    prod.price = request.form.get('price', '')
    prod.image_url = request.form.get('image_url', prod.image_url)
    db.session.commit()
    flash('Produit mis à jour !', 'success')
    return redirect(url_for('admin_page'))

@app.route('/admin/delete-product/<int:id>', methods=['POST'])
def delete_product(id):
    prod = Product.query.get_or_404(id)
    db.session.delete(prod)
    db.session.commit()
    flash('Produit supprimé !', 'info')
    return redirect(url_for('admin_page'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)