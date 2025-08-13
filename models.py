from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    cost_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    low_stock_threshold = db.Column(db.Integer, default=5)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(20), unique=True, nullable=False)
    customer_name = db.Column(db.String(200))
    total = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    qty = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

class ShopSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.String(256))

class ShopInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(100), default="Patidar Traders")
    address = db.Column(db.String(200), default="Mugaliya")
    phone = db.Column(db.String(50), default="1234567890")
    gstin = db.Column(db.String(50), default="GSTN000001")
    logo_filename = db.Column(db.String(100), default="logo.png")
