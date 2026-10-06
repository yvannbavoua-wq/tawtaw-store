import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tataw_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tataw.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/tataw.db'

db = SQLAlchemy(app)

# Modèle Produit
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False) # homme, femme, cosmetiques
    subcategory = db.Column(db.String(50), nullable=False) # tshirts, pulls, croptops, ensembles, babouches, chaussures, chaussettes, sacs
    image_url = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(50), nullable=True, default="")

# Initialisation de la base de données sécurisée
def init_db():
    try:
        db.create_all()
        if Product.query.count() == 0:
            default_products = [
                Product(name="T-Shirt TATAW (Noir, Blanc, Rose, Rouge)", category="homme", subcategory="tshirts", image_url="https://images.unsplash.com/photo-1521572267360-ee0c2909d518"),
                Product(name="Pull TATAW Noir", category="homme", subcategory="pulls", image_url="https://images.unsplash.com/photo-1556905055-8f358a7a47b2"),
                Product(name="Crop-top TATAW (Noir, Blanc, Rose, Rouge)", category="femme", subcategory="croptops", image_url="https://images.unsplash.com/photo-1503342217505-b0a15ec3261c"),
                Product(name="Ensemble TATAW Homme", category="homme", subcategory="ensembles", image_url="https://images.unsplash.com/photo-1515886657613-9f3515b0c78f"),
                Product(name="Babouches TATAW Homme", category="homme", subcategory="babouches", image_url="https://images.unsplash.com/photo-1542291026-7eec264c27ff"),
                Product(name="Chaussures TATAW Homme", category="homme", subcategory="chaussures", image_url="https://images.unsplash.com/photo-1549298916-b41d501d3772"),
                Product(name="Chaussettes TATAW Homme", category="homme", subcategory="chaussettes", image_url="https://images.unsplash.com/photo-1586350977771-b3b0abd50c82"),
                Product(name="Ensemble TATAW Femme", category="femme", subcategory="ensembles", image_url="https://images.unsplash.com/photo-1469334031218-e382a71b716b"),
                Product(name="Babouches TATAW Femme", category="femme", subcategory="babouches", image_url="https://images.unsplash.com/photo-1560343090-f0409e92791a"),
                Product(name="Chaussures TATAW Femme", category="femme", subcategory="chaussures", image_url="https://images.unsplash.com/photo-1543163521-1bf539c55dd2"),
                Product(name="Chaussettes TATAW Femme", category="femme", subcategory="chaussettes", image_url="https://images.unsplash.com/photo-1582966772680-860e372bb558"),
                Product(name="Sac TATAW Femme", category="femme", subcategory="sacs", image_url="https://images.unsplash.com/photo-1584917865442-de89df76afd3")
            ]
            db.session.add_all(default_products)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de l'initialisation DB: {e}")

# Appel unique au démarrage de l'application
with app.app_context():
    init_db()

@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/admin')
def admin():
    products = Product.query.all()
    return render_template('admin.html', products=products)

@app.route('/admin/add', methods=['POST'])
def add_product():
    name = request.form.get('name')
    category = request.form.get('category')
    subcategory = request.form.get('subcategory')
    image_url = request.form.get('image_url')
    price = request.form.get('price', '')

    if name and category and subcategory and image_url:
        new_prod = Product(name=name, category=category, subcategory=subcategory, image_url=image_url, price=price)
        db.session.add(new_prod)
        db.session.commit()
        flash('Produit ajouté avec succès !')
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:id>')
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Produit supprimé !')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)