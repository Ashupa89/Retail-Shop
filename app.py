from flask import Flask, render_template, redirect, url_for, request, flash , jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Product, Sale, SaleItem, ShopSetting, ShopInfo
from datetime import datetime
from invoice import generate_invoice_pdf, format_invoice_no
from weasyprint import HTML
from io import BytesIO, StringIO
import os
import pandas as pd
from werkzeug.utils import secure_filename
import io

# -------------------------
# App & Config
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'  # change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Init DB with app
db.init_app(app)

# -------------------------
# Login Manager
# -------------------------
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# Routes
# -------------------------
@app.route('/')
@login_required
def index():
    products = Product.query.all()
    sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()
    low_stock = [p for p in products if p.quantity <= p.low_stock_threshold]
    return render_template('index.html',
        products=products, sales=sales, low_stock=low_stock
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password", "danger")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Example protected route
@app.route('/products')
@login_required
def products():
    items = Product.query.all()
    return render_template('products.html', products=items)

# -------------------------
# DB Init with Admin
# -------------------------
import os
from werkzeug.security import generate_password_hash
from models import db, User, Product, ShopInfo

def init_db(reset=False):
    """
    Initialize the database safely.
    - reset=True will delete the existing DB.
    - Automatically avoids duplicates for admin, products, and shop info.
    """
    db_path = 'database.db'

    if reset and os.path.exists(db_path):
        os.remove(db_path)
        print("🗑️ Existing database deleted.")

    with app.app_context():
        db.create_all()
        print("📦 Database tables created/verified.")

        # 1️⃣ Default admin
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                is_admin=True
            )
            db.session.add(admin)
            print("✅ Admin user created: username='admin', password='admin'")
        else:
            print("ℹ Admin already exists.")

        # 2️⃣ Sample products
        sample_products = [
            ('1', 'Apple', 30.0, 50, 30.0, 5),
            ('2', 'Banana', 10.0, 100, 10.0, 10),
            ('3', 'Milk (1L)', 45.0, 40, 45.0, 4)
        ]
        for id, name, selling_price, quantity, cost_price, low_stock_threshold in sample_products:
            existing = Product.query.filter_by(id=id).first()
            if not existing:
                p = Product(
                    id=id,
                    name=name,
                    selling_price=selling_price,
                    cost_price=cost_price,
                    quantity=quantity,
                    low_stock_threshold=low_stock_threshold
                )
                db.session.add(p)
                print(f"✅ Product added: {name}")
            else:
                print(f"ℹ Product already exists: {name}")

        # 3️⃣ Default shop info
        shop_info = ShopInfo.query.first()
        if not shop_info:
            shop_info = ShopInfo(
                shop_name="Patidar Traders",
                address="Mugaliya",
                phone="1234567890",
                gstin="GSTN000001",
                logo_filename="logo.png"
            )
            db.session.add(shop_info)
            print("✅ Default shop info added.")
        else:
            print("ℹ Shop info already exists.")

        db.session.commit()
        print("💾 Database initialization complete.")

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():
    products = Product.query.all()
    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        qty = int(request.form['quantity'])
        customer_name = request.form.get('customer_name', '') or 'Ashish Patil'
        customer_contact = request.form.get('customer_contact')
        customer_address = request.form.get('customer_address')

        prod = Product.query.get_or_404(product_id)
        if prod.quantity < qty:
            flash('Insufficient stock.', 'danger')
            return redirect(url_for('sales'))

        prod.quantity -= qty
        invoice_no = get_next_invoice_no()
        total = qty * prod.selling_price
        sale = Sale(
            invoice_no=invoice_no,
            product_id=product_id,
            product_name=prod.name,
            quantity=qty,
            customer_name=customer_name,
            customer_contact=customer_contact,
            customer_address=customer_address,
            unit_price=prod.selling_price,
            total_price=total
        )
        db.session.add(sale)
        db.session.commit()

        # Generate PDF on disk
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{invoice_no}.pdf")
        save_invoice_pdf(sale, pdf_path)

        flash('Sale recorded and invoice generated.', 'success')
        return redirect(url_for('invoice', sale_id=sale.id))
    sales = Sale.query.order_by(Sale.created_at.desc()).all()
    return render_template('sales.html', products=products, sales=sales)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    shop = ShopInfo.query.first()
    if not shop:
        shop = ShopInfo()
        db.session.add(shop)
        db.session.commit()

    if request.method == 'POST':
        shop.shop_name = request.form['shop_name']
        shop.address = request.form['address']
        shop.phone = request.form['phone']
        shop.gstin = request.form['gstin']

        file = request.files.get('logo')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            shop.logo_filename = filename

        db.session.commit()
        flash("Shop details updated!", "success")
        return redirect(url_for('settings'))

    return render_template('settings.html', shop=shop)

# --- CSV Export ---

@app.route('/products/export')
@login_required
def export_products():
    products = Product.query.all()
    data = [{
        'Name': p.name,
        'Category': p.category,
        'Cost Price': p.cost_price,
        'Selling Price': p.selling_price,
        'Quantity': p.quantity
    } for p in products]
    df = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        as_attachment=True, download_name="products.csv",
        mimetype='text/csv'
    )
@app.route('/sales/export')
@login_required
def export_sales():
    sales = Sale.query.all()
    data = [{
        'Invoice': s.invoice_no,
        'Product': s.product_name,
        'Quantity': s.quantity,
        'Customer Name': s.customer_name,
        'Contact': s.customer_contact,
        'Address': s.customer_address,
        'Date': s.created_at.strftime('%d-%m-%Y %I:%M %p'),
        'Unit Price': s.unit_price,
        'Total Price': s.total_price
    } for s in sales]
    df = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        as_attachment=True, download_name="sales.csv",
        mimetype='text/csv'
    )

@app.route('/import/products', methods=['GET','POST'])
@login_required
def import_products():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f:
            flash('No file uploaded', 'danger')
            return redirect(url_for('import_products'))

        try:
            stream = StringIO(f.stream.read().decode('utf-8'))
        except UnicodeDecodeError:
            flash('Invalid file encoding. Please upload a UTF-8 CSV.', 'danger')
            return redirect(url_for('import_products'))

        reader = csv.DictReader(stream)
        count = 0
        for row in reader:
            try:
                p = Product(
                    name=row.get('Name'),
                    category=row.get('Category'),
                    cost_price=float(row.get('Cost Price') or 0),
                    selling_price=float(row.get('Selling Price') or 0),
                    quantity=int(row.get('Quantity') or 0),
                    low_stock_threshold=int(row.get('Threshold') or 0)
                )
                db.session.add(p)
                count += 1
            except Exception as e:
                app.logger.error(f"Skipping row due to error: {e}")
                continue

        db.session.commit()
        flash(f'Imported {count} products', 'success')
        return redirect(url_for('index'))

    return render_template('import_products.html')

@app.route('/products/edit/<int:pid>', methods=['GET', 'POST'])
@login_required
def edit_product(pid):
    product = Product.query.get_or_404(pid)
    if request.method == 'POST':
        try:
            product.name = request.form['name']
            product.category = request.form['category']
            product.cost_price = float(request.form['cost_price'])
            product.selling_price = float(request.form['selling_price'])
            product.quantity = int(request.form['quantity'])
            product.low_stock_threshold = int(request.form['threshold'])
            db.session.commit()
            flash('Product updated successfully.', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            flash(f'Error updating product: {e}', 'danger')
    products = Product.query.all()
    return render_template("products.html", products=products, edit_product=product)

@app.route('/products/add', methods=['POST'])
@login_required
def add_product():
    try:
        product = Product(
            name=request.form['name'],
            category=request.form.get('category', ''),
            cost_price=float(request.form['cost_price']),
            selling_price=float(request.form['selling_price']),
            quantity=int(request.form['quantity']),
            low_stock_threshold=int(request.form.get('threshold', 5))
        )
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully.', 'success')
    except Exception as e:
        flash(f'Error adding product: {e}', 'danger')
    return redirect(url_for('products'))

@app.route('/products/delete/<int:pid>')
@login_required
def delete_product(pid):
    prod = Product.query.get_or_404(pid)
    db.session.delete(prod)
    db.session.commit()
    flash('Product deleted!', 'success')
    return redirect(url_for('products'))

from flask import request, jsonify
from sqlalchemy.exc import SQLAlchemyError

@app.route('/create-sale', methods=['POST'])
def create_sale():
    data = request.get_json()
    if not data or 'items' not in data or not data.get('customer_name'):
        return jsonify({'error': 'Bad request, missing customer name or items'}), 400

    customer_name = data['customer_name'].strip()
    if not customer_name:
        return jsonify({'error': 'Customer name cannot be empty'}), 400

    items_data = data['items']
    if not items_data:
        return jsonify({'error': 'At least one item is required'}), 400

    try:
        last = Sale.query.order_by(Sale.id.desc()).first()
        next_no = 1 if not last else last.id + 1
        inv_no = format_invoice_no(next_no)

        sale = Sale(invoice_no=inv_no, customer_name=customer_name, total=0)
        db.session.add(sale)
        db.session.flush()  # get sale.id

        total = 0
        for it in items_data:
            product_id = it.get('product_id')
            qty = int(it.get('quantity', 0))
            if qty < 1:
                db.session.rollback()
                return jsonify({'error': f'Invalid quantity for product {product_id}'}), 400

            product = Product.query.get(product_id)
            if not product:
                db.session.rollback()
                return jsonify({'error': f'Product with ID {product_id} not found'}), 404

            if product.quantity < qty:
                db.session.rollback()
                return jsonify({'error': f'Insufficient stock for product {product.name}'}), 400

            # Use selling_price or cost_price as you prefer
            price = product.selling_price

            sale_item = SaleItem(sale_id=sale.id, product_id=product.id, qty=qty, price=price)
            product.quantity -= qty
            total += qty * price
            db.session.add(sale_item)

        sale.total = total
        db.session.commit()

        # Generate invoice PDF
        os.makedirs('invoices', exist_ok=True)
        invoice_path = os.path.join('invoices', f"{sale.invoice_no}.pdf")
        generate_invoice_pdf(sale.id, invoice_path)

        return jsonify({'invoice': invoice_path, 'invoice_no': sale.invoice_no})

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': 'Database error', 'details': str(e)}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Unexpected error', 'details': str(e)}), 500


@app.route('/invoice/<invoice_no>')
def get_invoice(invoice_no):
    path = os.path.join('invoices', f"{invoice_no}.pdf")
    if os.path.exists(path):
        return send_file(path)
    return 'Not found', 404

@app.route('/invoice_view/<invoice_no>')
def invoice_view(invoice_no):
    sale = Sale.query.filter_by(invoice_no=invoice_no).first_or_404()
    items = SaleItem.query.filter_by(sale_id=sale.id).all()
    # Attach products for template
    for si in items:
        si.product = Product.query.get(si.product_id)
    return render_template('invoice_view.html', sale=sale, items=items)

# Allowed extensions for logo upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# -------------------------
# Main Entry
# -------------------------
if __name__ == '__main__':
    # reset=True will rebuild DB completely
    init_db(reset=False)
    app.run(debug=True)

