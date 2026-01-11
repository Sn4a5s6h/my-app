import os
import logging
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json

# إعداد التطبيق
app = Flask(__name__)

# التكوين لـ Render
if 'RENDER' in os.environ:
    # على Render
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'render-secret-key')
else:
    # محلياً
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///accounting.db'
    app.config['SECRET_KEY'] = 'dev-secret-key'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# تهيئة الإضافات
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ========== النماذج المحدثة ==========

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')
    phone = db.Column(db.String(20))
    department = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)  # asset, liability, equity, revenue, expense
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    balance = db.Column(db.Float, default=0.0)
    opening_balance = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='SAR')
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    parent = db.relationship('Account', remote_side=[id], backref='sub_accounts')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    transaction_number = db.Column(db.String(50), unique=True, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    description = db.Column(db.String(200), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # debit, credit
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='SAR')
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    reference_type = db.Column(db.String(50))  # invoice, payment, expense
    reference_id = db.Column(db.Integer)
    reference_number = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # العلاقات
    account = db.relationship('Account', backref='transactions')
    user = db.relationship('User', backref='transactions')

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(20), unique=True, nullable=False)
    customer_name = db.Column(db.String(200), nullable=False)
    tax_number = db.Column(db.String(50))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    country = db.Column(db.String(50), default='السعودية')
    customer_type = db.Column(db.String(50))  # individual, company, government
    credit_limit = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    account_receivable_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    account_receivable = db.relationship('Account', backref='customers')

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    supplier_code = db.Column(db.String(20), unique=True, nullable=False)
    supplier_name = db.Column(db.String(200), nullable=False)
    tax_number = db.Column(db.String(50))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    country = db.Column(db.String(50), default='السعودية')
    current_balance = db.Column(db.Float, default=0.0)
    account_payable_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    account_payable = db.relationship('Account', backref='suppliers')

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), unique=True, nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    unit = db.Column(db.String(20), default='قطعة')
    purchase_price = db.Column(db.Float, default=0.0)
    selling_price = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=0.0)
    min_quantity = db.Column(db.Float, default=0.0)
    max_quantity = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    has_tax = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_type = db.Column(db.String(20), nullable=False)  # sales, purchase
    invoice_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    due_date = db.Column(db.Date)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    total_amount = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0.0)
    remaining_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='SAR')
    status = db.Column(db.String(20), default='draft')  # draft, sent, partially_paid, paid, overdue, cancelled
    payment_terms = db.Column(db.String(100))
    notes = db.Column(db.Text)
    terms_conditions = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    customer = db.relationship('Customer', backref='invoices')
    supplier = db.relationship('Supplier', backref='invoices')
    creator = db.relationship('User', backref='invoices')

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    discount_percent = db.Column(db.Float, default=0.0)
    tax_percent = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))

    # العلاقات
    invoice = db.relationship('Invoice', backref='items')
    product = db.relationship('Product', backref='invoice_items')
    account = db.relationship('Account', backref='invoice_items')

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True, nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    payment_type = db.Column(db.String(20), nullable=False)  # receipt, payment
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='SAR')
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, cheque, credit_card
    bank_account = db.Column(db.String(100))
    cheque_number = db.Column(db.String(50))
    cheque_date = db.Column(db.Date)
    description = db.Column(db.String(500))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    customer = db.relationship('Customer', backref='payments')
    supplier = db.relationship('Supplier', backref='payments')
    invoice = db.relationship('Invoice', backref='payments')
    account = db.relationship('Account', backref='payments')
    creator = db.relationship('User', backref='payments')

class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'
    id = db.Column(db.Integer, primary_key=True)
    journal_number = db.Column(db.String(50), unique=True, nullable=False)
    journal_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    description = db.Column(db.String(500), nullable=False)
    total_debit = db.Column(db.Float, nullable=False)
    total_credit = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='SAR')
    status = db.Column(db.String(20), default='draft')  # draft, posted, cancelled
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    posted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_journals')
    poster = db.relationship('User', foreign_keys=[posted_by], backref='posted_journals')

class JournalLine(db.Model):
    __tablename__ = 'journal_lines'
    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    description = db.Column(db.String(200))
    currency = db.Column(db.String(3), default='SAR')
    line_number = db.Column(db.Integer)

    # العلاقات
    journal_entry = db.relationship('JournalEntry', backref='lines')
    account = db.relationship('Account', backref='journal_lines')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== الصفحات الرئيسية ==========

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('auth/login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('مرحباً بعودتك!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور', 'error')

    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # إحصائيات سريعة
    total_accounts = Account.query.filter_by(is_active=True).count()
    total_customers = Customer.query.filter_by(is_active=True).count()
    total_suppliers = Supplier.query.filter_by(is_active=True).count()
    total_products = Product.query.filter_by(is_active=True).count()
    total_invoices = Invoice.query.count()

    # حساب الرصيد النقدي
    cash_accounts = Account.query.filter(
        Account.account_type == 'asset',
        Account.name.like('%نقد%')
    ).all()
    cash_balance = sum(acc.balance for acc in cash_accounts)

    # الفواتير المستحقة
    overdue_invoices = Invoice.query.filter(
        Invoice.status.in_(['sent', 'partially_paid']),
        Invoice.due_date < date.today(),
        Invoice.remaining_amount > 0
    ).count()

    # أحدث الحركات
    recent_transactions = Transaction.query.filter_by(status='active').order_by(
        Transaction.transaction_date.desc()
    ).limit(10).all()

    return render_template('dashboard.html',
                         total_accounts=total_accounts,
                         total_customers=total_customers,
                         total_suppliers=total_suppliers,
                         total_products=total_products,
                         total_invoices=total_invoices,
                         cash_balance=cash_balance,
                         overdue_invoices=overdue_invoices,
                         recent_transactions=recent_transactions)

# ========== صفحات التطبيق ==========

@app.route('/accounts')
@login_required
def accounts_page():
    return render_template('accounts.html')

@app.route('/customers')
@login_required
def customers_page():
    return render_template('customers.html')

@app.route('/suppliers')
@login_required
def suppliers_page():
    return render_template('suppliers.html')

@app.route('/products')
@login_required
def products_page():
    return render_template('products.html')

@app.route('/invoices')
@login_required
def invoices_page():
    return render_template('invoices.html')

@app.route('/payments')
@login_required
def payments_page():
    return render_template('payments.html')

@app.route('/journal')
@login_required
def journal_page():
    return render_template('journal.html')

@app.route('/reports')
@login_required
def reports_page():
    return render_template('reports.html')

@app.route('/profile')
@login_required
def profile_page():
    return render_template('profile.html', user=current_user)

# ========== واجهات API للحسابات ==========

@app.route('/api/accounts')
@login_required
def get_accounts():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    return jsonify([{
        'id': acc.id,
        'code': acc.code,
        'name': acc.name,
        'type': acc.account_type,
        'parent_id': acc.parent_id,
        'balance': acc.balance,
        'currency': acc.currency,
        'is_active': acc.is_active
    } for acc in accounts])

@app.route('/api/accounts/<int:account_id>')
@login_required
def get_account(account_id):
    account = Account.query.get_or_404(account_id)
    return jsonify({
        'id': account.id,
        'code': account.code,
        'name': account.name,
        'type': account.account_type,
        'parent_id': account.parent_id,
        'balance': account.balance,
        'opening_balance': account.opening_balance,
        'currency': account.currency,
        'is_active': account.is_active,
        'notes': account.notes,
        'created_at': account.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/accounts', methods=['POST'])
@login_required
def create_account():
    try:
        data = request.get_json()
        
        # التحقق من عدم تكرار الكود
        if Account.query.filter_by(code=data['code']).first():
            return jsonify({'success': False, 'message': 'كود الحساب موجود مسبقاً'}), 400
        
        account = Account(
            code=data['code'],
            name=data['name'],
            account_type=data['type'],
            parent_id=data.get('parent_id'),
            opening_balance=data.get('opening_balance', 0),
            balance=data.get('opening_balance', 0),
            currency=data.get('currency', 'SAR'),
            is_active=True,
            notes=data.get('notes')
        )
        
        db.session.add(account)
        db.session.commit()
        
        return jsonify({'success': True, 'id': account.id, 'message': 'تم إنشاء الحساب بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/accounts/<int:account_id>', methods=['PUT'])
@login_required
def update_account(account_id):
    try:
        account = Account.query.get_or_404(account_id)
        data = request.get_json()
        
        # تحديث البيانات
        if 'name' in data:
            account.name = data['name']
        if 'type' in data:
            account.account_type = data['type']
        if 'parent_id' in data:
            account.parent_id = data['parent_id']
        if 'currency' in data:
            account.currency = data['currency']
        if 'is_active' in data:
            account.is_active = data['is_active']
        if 'notes' in data:
            account.notes = data['notes']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم تحديث الحساب بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== واجهات API للعملاء ==========

@app.route('/api/customers')
@login_required
def get_customers():
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.customer_name).all()
    return jsonify([{
        'id': cust.id,
        'customer_code': cust.customer_code,
        'customer_name': cust.customer_name,
        'tax_number': cust.tax_number,
        'email': cust.email,
        'phone': cust.phone,
        'city': cust.city,
        'current_balance': cust.current_balance,
        'credit_limit': cust.credit_limit,
        'is_active': cust.is_active
    } for cust in customers])

@app.route('/api/customers/<int:customer_id>')
@login_required
def get_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return jsonify({
        'id': customer.id,
        'customer_code': customer.customer_code,
        'customer_name': customer.customer_name,
        'tax_number': customer.tax_number,
        'email': customer.email,
        'phone': customer.phone,
        'address': customer.address,
        'city': customer.city,
        'country': customer.country,
        'customer_type': customer.customer_type,
        'current_balance': customer.current_balance,
        'credit_limit': customer.credit_limit,
        'account_receivable_id': customer.account_receivable_id,
        'is_active': customer.is_active,
        'notes': customer.notes,
        'created_at': customer.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/customers', methods=['POST'])
@login_required
def create_customer():
    try:
        data = request.get_json()
        
        # التحقق من عدم تكرار الكود
        if Customer.query.filter_by(customer_code=data['customer_code']).first():
            return jsonify({'success': False, 'message': 'كود العميل موجود مسبقاً'}), 400
        
        customer = Customer(
            customer_code=data['customer_code'],
            customer_name=data['customer_name'],
            tax_number=data.get('tax_number'),
            email=data.get('email'),
            phone=data.get('phone'),
            address=data.get('address'),
            city=data.get('city'),
            country=data.get('country', 'السعودية'),
            customer_type=data.get('customer_type'),
            credit_limit=data.get('credit_limit', 0),
            current_balance=data.get('current_balance', 0),
            is_active=True,
            notes=data.get('notes')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({'success': True, 'id': customer.id, 'message': 'تم إنشاء العميل بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== واجهات API للموردين ==========

@app.route('/api/suppliers')
@login_required
def get_suppliers():
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.supplier_name).all()
    return jsonify([{
        'id': sup.id,
        'supplier_code': sup.supplier_code,
        'supplier_name': sup.supplier_name,
        'tax_number': sup.tax_number,
        'email': sup.email,
        'phone': sup.phone,
        'city': sup.city,
        'current_balance': sup.current_balance,
        'is_active': sup.is_active
    } for sup in suppliers])

@app.route('/api/suppliers/<int:supplier_id>')
@login_required
def get_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    return jsonify({
        'id': supplier.id,
        'supplier_code': supplier.supplier_code,
        'supplier_name': supplier.supplier_name,
        'tax_number': supplier.tax_number,
        'email': supplier.email,
        'phone': supplier.phone,
        'address': supplier.address,
        'city': supplier.city,
        'country': supplier.country,
        'current_balance': supplier.current_balance,
        'account_payable_id': supplier.account_payable_id,
        'is_active': supplier.is_active,
        'notes': supplier.notes,
        'created_at': supplier.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

# ========== واجهات API للمنتجات ==========

@app.route('/api/products')
@login_required
def get_products():
    products = Product.query.filter_by(is_active=True).order_by(Product.product_name).all()
    return jsonify([{
        'id': prod.id,
        'product_code': prod.product_code,
        'product_name': prod.product_name,
        'description': prod.description,
        'category': prod.category,
        'unit': prod.unit,
        'purchase_price': prod.purchase_price,
        'selling_price': prod.selling_price,
        'quantity': prod.quantity,
        'min_quantity': prod.min_quantity,
        'max_quantity': prod.max_quantity,
        'has_tax': prod.has_tax,
        'is_active': prod.is_active
    } for prod in products])

@app.route('/api/products/<int:product_id>')
@login_required
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify({
        'id': product.id,
        'product_code': product.product_code,
        'product_name': product.product_name,
        'description': product.description,
        'category': product.category,
        'unit': product.unit,
        'purchase_price': product.purchase_price,
        'selling_price': product.selling_price,
        'quantity': product.quantity,
        'min_quantity': product.min_quantity,
        'max_quantity': product.max_quantity,
        'has_tax': product.has_tax,
        'is_active': product.is_active,
        'notes': product.notes,
        'created_at': product.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

# ========== واجهات API للفواتير ==========

@app.route('/api/invoices')
@login_required
def get_invoices():
    invoice_type = request.args.get('type', 'sales')
    status = request.args.get('status')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    query = Invoice.query.filter_by(invoice_type=invoice_type)
    
    if status:
        query = query.filter_by(status=status)
    
    invoices = query.order_by(Invoice.invoice_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    invoices_data = []
    for invoice in invoices.items:
        invoice_data = {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
            'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else None,
            'customer_name': invoice.customer.customer_name if invoice.customer else None,
            'supplier_name': invoice.supplier.supplier_name if invoice.supplier else None,
            'total_amount': invoice.total_amount,
            'tax_amount': invoice.tax_amount,
            'discount_amount': invoice.discount_amount,
            'net_amount': invoice.net_amount,
            'paid_amount': invoice.paid_amount,
            'remaining_amount': invoice.remaining_amount,
            'status': invoice.status,
            'currency': invoice.currency
        }
        invoices_data.append(invoice_data)
    
    return jsonify({
        'success': True,
        'data': invoices_data,
        'pagination': {
            'page': invoices.page,
            'per_page': invoices.per_page,
            'total': invoices.total,
            'pages': invoices.pages
        }
    })

@app.route('/api/invoices/<int:invoice_id>')
@login_required
def get_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    items_data = []
    for item in invoice.items:
        items_data.append({
            'id': item.id,
            'product_id': item.product_id,
            'description': item.description,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'discount_percent': item.discount_percent,
            'tax_percent': item.tax_percent,
            'total_amount': item.total_amount
        })
    
    return jsonify({
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'invoice_type': invoice.invoice_type,
        'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
        'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else None,
        'customer_id': invoice.customer_id,
        'supplier_id': invoice.supplier_id,
        'total_amount': invoice.total_amount,
        'tax_amount': invoice.tax_amount,
        'discount_amount': invoice.discount_amount,
        'net_amount': invoice.net_amount,
        'paid_amount': invoice.paid_amount,
        'remaining_amount': invoice.remaining_amount,
        'status': invoice.status,
        'currency': invoice.currency,
        'payment_terms': invoice.payment_terms,
        'notes': invoice.notes,
        'terms_conditions': invoice.terms_conditions,
        'items': items_data,
        'created_at': invoice.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

# ========== واجهات API للحركات ==========

@app.route('/api/transactions')
@login_required
def get_transactions():
    account_id = request.args.get('account_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    query = Transaction.query.filter_by(status='active')
    
    if account_id:
        query = query.filter_by(account_id=account_id)
    
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    
    transactions = query.order_by(
        Transaction.transaction_date.desc(), 
        Transaction.id.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    transactions_data = []
    for trans in transactions.items:
        transactions_data.append({
            'id': trans.id,
            'transaction_number': trans.transaction_number,
            'transaction_date': trans.transaction_date.strftime('%Y-%m-%d'),
            'description': trans.description,
            'transaction_type': trans.transaction_type,
            'amount': trans.amount,
            'currency': trans.currency,
            'account_id': trans.account_id,
            'account_name': trans.account.name if trans.account else '',
            'reference_number': trans.reference_number,
            'created_at': trans.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({
        'success': True,
        'data': transactions_data,
        'pagination': {
            'page': transactions.page,
            'per_page': transactions.per_page,
            'total': transactions.total,
            'pages': transactions.pages
        }
    })

@app.route('/api/transactions', methods=['POST'])
@login_required
def create_transaction():
    try:
        data = request.get_json()
        
        # توليد رقم الحركة
        last_trans = Transaction.query.order_by(Transaction.id.desc()).first()
        trans_number = f"TRN-{datetime.now().strftime('%Y%m%d')}-{(last_trans.id + 1) if last_trans else 1:04d}"
        
        transaction = Transaction(
            transaction_number=trans_number,
            transaction_date=datetime.strptime(data['transaction_date'], '%Y-%m-%d').date(),
            description=data['description'],
            transaction_type=data['transaction_type'],
            amount=float(data['amount']),
            currency=data.get('currency', 'SAR'),
            account_id=data['account_id'],
            reference_type=data.get('reference_type'),
            reference_id=data.get('reference_id'),
            reference_number=data.get('reference_number'),
            created_by=current_user.id
        )
        
        db.session.add(transaction)
        
        # تحديث رصيد الحساب
        account = Account.query.get(data['account_id'])
        if data['transaction_type'] == 'debit':
            account.balance += float(data['amount'])
        else:  # credit
            account.balance -= float(data['amount'])
        
        db.session.commit()
        
        return jsonify({'success': True, 'id': transaction.id, 'message': 'تم إنشاء الحركة بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== واجهات API للتقارير ==========

@app.route('/api/reports/balance-sheet')
@login_required
def get_balance_sheet():
    try:
        # حساب الأصول
        asset_accounts = Account.query.filter_by(
            account_type='asset', is_active=True
        ).all()
        assets_total = sum(acc.balance for acc in asset_accounts)
        
        # حساب الخصوم
        liability_accounts = Account.query.filter_by(
            account_type='liability', is_active=True
        ).all()
        liabilities_total = sum(acc.balance for acc in liability_accounts)
        
        # حساب حقوق الملكية
        equity_accounts = Account.query.filter_by(
            account_type='equity', is_active=True
        ).all()
        equity_total = sum(acc.balance for acc in equity_accounts)
        
        # حساب صافي الدخل
        revenue_total = sum(acc.balance for acc in Account.query.filter_by(
            account_type='revenue', is_active=True
        ).all())
        expense_total = sum(acc.balance for acc in Account.query.filter_by(
            account_type='expense', is_active=True
        ).all())
        net_income = revenue_total - expense_total
        
        return jsonify({
            'success': True,
            'assets': [{'name': a.name, 'balance': a.balance} for a in asset_accounts],
            'liabilities': [{'name': l.name, 'balance': l.balance} for l in liability_accounts],
            'equity': [{'name': e.name, 'balance': e.balance} for e in equity_accounts],
            'total_assets': assets_total,
            'total_liabilities': liabilities_total,
            'total_equity': equity_total + net_income,
            'net_income': net_income,
            'as_of_date': date.today().strftime('%Y-%m-%d')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reports/income-statement')
@login_required
def get_income_statement():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # إذا لم يتم تحديد تاريخ، استخدم الشهر الحالي
        if not start_date or not end_date:
            today = date.today()
            start_date = date(today.year, today.month, 1)
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # حساب الإيرادات
        revenue_accounts = Account.query.filter_by(
            account_type='revenue', is_active=True
        ).all()
        
        revenues = []
        revenue_total = 0
        for account in revenue_accounts:
            # حساب حركات الحساب للفترة
            period_balance = calculate_account_period_balance(account.id, start_date, end_date)
            if period_balance != 0:
                revenues.append({
                    'name': account.name,
                    'amount': period_balance
                })
                revenue_total += period_balance
        
        # حساب المصروفات
        expense_accounts = Account.query.filter_by(
            account_type='expense', is_active=True
        ).all()
        
        expenses = []
        expense_total = 0
        for account in expense_accounts:
            # حساب حركات الحساب للفترة
            period_balance = calculate_account_period_balance(account.id, start_date, end_date)
            if period_balance != 0:
                expenses.append({
                    'name': account.name,
                    'amount': period_balance
                })
                expense_total += period_balance
        
        # حساب صافي الدخل
        net_income = revenue_total - expense_total
        
        return jsonify({
            'success': True,
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'revenues': {
                'items': revenues,
                'total': revenue_total
            },
            'expenses': {
                'items': expenses,
                'total': expense_total
            },
            'net_income': net_income
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def calculate_account_period_balance(account_id, start_date, end_date):
    """حساب رصيد حساب لفترة محددة"""
    transactions = Transaction.query.filter(
        Transaction.account_id == account_id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date,
        Transaction.status == 'active'
    ).all()
    
    period_balance = 0
    for trans in transactions:
        if trans.transaction_type == 'debit':
            period_balance += trans.amount
        else:  # credit
            period_balance -= trans.amount
    
    return period_balance

@app.route('/api/reports/trial-balance')
@login_required
def get_trial_balance():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # إذا لم يتم تحديد تاريخ، استخدم اليوم
        if not start_date or not end_date:
            today = date.today()
            start_date = today
            end_date = today
        
        accounts = Account.query.filter_by(is_active=True).all()
        
        trial_balance = []
        total_debit = 0
        total_credit = 0
        
        for account in accounts:
            # حساب مجموع المدين للفترة
            debit_sum = db.session.query(db.func.sum(Transaction.amount)).filter(
                Transaction.account_id == account.id,
                Transaction.transaction_type == 'debit',
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.status == 'active'
            ).scalar() or 0
            
            # حساب مجموع الدائن للفترة
            credit_sum = db.session.query(db.func.sum(Transaction.amount)).filter(
                Transaction.account_id == account.id,
                Transaction.transaction_type == 'credit',
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.status == 'active'
            ).scalar() or 0
            
            # حساب الرصيد
            balance = (account.opening_balance + debit_sum) - credit_sum
            
            trial_balance.append({
                'code': account.code,
                'name': account.name,
                'opening_balance': account.opening_balance,
                'debit': debit_sum,
                'credit': credit_sum,
                'balance': balance,
                'balance_type': 'مدين' if balance >= 0 else 'دائن'
            })
            
            if balance >= 0:
                total_debit += balance
            else:
                total_credit += abs(balance)
        
        return jsonify({
            'success': True,
            'period': {
                'start': start_date,
                'end': end_date
            },
            'data': trial_balance,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'is_balanced': abs(total_debit - total_credit) < 0.01
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reports/customer-statement/<int:customer_id>')
@login_required
def get_customer_statement(customer_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        customer = Customer.query.get_or_404(customer_id)
        
        # إذا لم يتم تحديد تاريخ، استخدم الشهر الحالي
        if not start_date or not end_date:
            today = date.today()
            start_date = date(today.year, today.month, 1)
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # جلب فواتير العميل للفترة
        invoices = Invoice.query.filter(
            Invoice.customer_id == customer_id,
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date,
            Invoice.invoice_type == 'sales'
        ).order_by(Invoice.invoice_date).all()
        
        # جلب مدفوعات العميل للفترة
        payments = Payment.query.filter(
            Payment.customer_id == customer_id,
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.payment_type == 'receipt',
            Payment.status == 'completed'
        ).order_by(Payment.payment_date).all()
        
        # دمج الفواتير والمدفوعات
        statement_lines = []
        running_balance = customer.current_balance
        
        all_transactions = []
        
        for invoice in invoices:
            all_transactions.append({
                'date': invoice.invoice_date,
                'type': 'invoice',
                'document': invoice.invoice_number,
                'debit': invoice.net_amount,
                'credit': 0,
                'description': f'فاتورة {invoice.invoice_number}'
            })
        
        for payment in payments:
            all_transactions.append({
                'date': payment.payment_date,
                'type': 'payment',
                'document': payment.payment_number,
                'debit': 0,
                'credit': payment.amount,
                'description': f'سند قبض {payment.payment_number}'
            })
        
        # ترتيب حسب التاريخ
        all_transactions.sort(key=lambda x: x['date'])
        
        for trans in all_transactions:
            running_balance += trans['debit'] - trans['credit']
            
            statement_lines.append({
                'date': trans['date'].strftime('%Y-%m-%d'),
                'document': trans['document'],
                'description': trans['description'],
                'debit': trans['debit'],
                'credit': trans['credit'],
                'balance': running_balance
            })
        
        return jsonify({
            'success': True,
            'customer': {
                'code': customer.customer_code,
                'name': customer.customer_name,
                'current_balance': customer.current_balance
            },
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'opening_balance': customer.current_balance,
            'closing_balance': running_balance,
            'transactions': statement_lines,
            'summary': {
                'total_invoices': sum(inv.net_amount for inv in invoices),
                'total_payments': sum(pay.amount for pay in payments),
                'balance_due': customer.current_balance
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== واجهات API للسندات ==========

@app.route('/api/payments')
@login_required
def get_payments():
    try:
        payment_type = request.args.get('type')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        query = Payment.query
        
        if payment_type:
            query = query.filter_by(payment_type=payment_type)
        
        if status:
            query = query.filter_by(status=status)
        
        payments = query.order_by(Payment.payment_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        payments_data = []
        for payment in payments.items:
            payments_data.append({
                'id': payment.id,
                'payment_number': payment.payment_number,
                'payment_date': payment.payment_date.strftime('%Y-%m-%d'),
                'payment_type': payment.payment_type,
                'amount': payment.amount,
                'currency': payment.currency,
                'payment_method': payment.payment_method,
                'customer_name': payment.customer.customer_name if payment.customer else None,
                'supplier_name': payment.supplier.supplier_name if payment.supplier else None,
                'invoice_number': payment.invoice.invoice_number if payment.invoice else None,
                'description': payment.description,
                'status': payment.status,
                'created_at': payment.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({
            'success': True,
            'data': payments_data,
            'pagination': {
                'page': payments.page,
                'per_page': payments.per_page,
                'total': payments.total,
                'pages': payments.pages
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/payments', methods=['POST'])
@login_required
def create_payment():
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['payment_date', 'payment_type', 'amount', 'payment_method']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'حقل {field} مطلوب'}), 400
        
        # توليد رقم السند
        last_payment = Payment.query.order_by(Payment.id.desc()).first()
        payment_number = f"PAY-{datetime.now().strftime('%Y%m%d')}-{(last_payment.id + 1) if last_payment else 1:04d}"
        
        payment = Payment(
            payment_number=payment_number,
            payment_date=datetime.strptime(data['payment_date'], '%Y-%m-%d').date(),
            payment_type=data['payment_type'],
            amount=float(data['amount']),
            currency=data.get('currency', 'SAR'),
            payment_method=data['payment_method'],
            bank_account=data.get('bank_account'),
            cheque_number=data.get('cheque_number'),
            cheque_date=datetime.strptime(data['cheque_date'], '%Y-%m-%d').date() if data.get('cheque_date') else None,
            description=data.get('description'),
            customer_id=data.get('customer_id'),
            supplier_id=data.get('supplier_id'),
            invoice_id=data.get('invoice_id'),
            account_id=data.get('account_id'),
            status='completed',
            notes=data.get('notes'),
            created_by=current_user.id
        )
        
        db.session.add(payment)
        
        # تحديث رصيد الحساب المالي
        if 'account_id' in data:
            account = Account.query.get(data['account_id'])
            if data['payment_type'] == 'receipt':  # سند قبض
                account.balance += float(data['amount'])
            else:  # سند صرف
                account.balance -= float(data['amount'])
        
        # تحديث رصيد العميل/المورد
        if 'customer_id' in data:
            customer = Customer.query.get(data['customer_id'])
            if data['payment_type'] == 'receipt':  # قبض من عميل
                customer.current_balance -= float(data['amount'])
            else:  # إعادة للعميل
                customer.current_balance += float(data['amount'])
        
        elif 'supplier_id' in data:
            supplier = Supplier.query.get(data['supplier_id'])
            if data['payment_type'] == 'payment':  # دفعة لمورد
                supplier.current_balance -= float(data['amount'])
            else:  # إرجاع من مورد
                supplier.current_balance += float(data['amount'])
        
        # تحديث الفاتورة إذا كانت مرتبطة
        if 'invoice_id' in data:
            invoice = Invoice.query.get(data['invoice_id'])
            invoice.paid_amount += float(data['amount'])
            invoice.remaining_amount = invoice.net_amount - invoice.paid_amount
            
            if invoice.remaining_amount <= 0.01:
                invoice.status = 'paid'
            elif invoice.paid_amount > 0:
                invoice.status = 'partially_paid'
        
        db.session.commit()
        
        return jsonify({'success': True, 'id': payment.id, 'message': 'تم إنشاء السند بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== واجهات API للقيود اليومية ==========

@app.route('/api/journal-entries')
@login_required
def get_journal_entries():
    try:
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        query = JournalEntry.query
        
        if status:
            query = query.filter_by(status=status)
        
        entries = query.order_by(JournalEntry.journal_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        entries_data = []
        for entry in entries.items:
            entries_data.append({
                'id': entry.id,
                'journal_number': entry.journal_number,
                'journal_date': entry.journal_date.strftime('%Y-%m-%d'),
                'description': entry.description,
                'total_debit': entry.total_debit,
                'total_credit': entry.total_credit,
                'status': entry.status,
                'created_by': entry.creator.full_name if entry.creator else None,
                'posted_at': entry.posted_at.strftime('%Y-%m-%d %H:%M:%S') if entry.posted_at else None
            })
        
        return jsonify({
            'success': True,
            'data': entries_data,
            'pagination': {
                'page': entries.page,
                'per_page': entries.per_page,
                'total': entries.total,
                'pages': entries.pages
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/journal-entries/<int:entry_id>')
@login_required
def get_journal_entry(entry_id):
    try:
        entry = JournalEntry.query.get_or_404(entry_id)
        
        lines_data = []
        for line in entry.lines:
            lines_data.append({
                'id': line.id,
                'account_id': line.account_id,
                'account_code': line.account.code,
                'account_name': line.account.name,
                'debit': line.debit,
                'credit': line.credit,
                'description': line.description
            })
        
        return jsonify({
            'success': True,
            'data': {
                'id': entry.id,
                'journal_number': entry.journal_number,
                'journal_date': entry.journal_date.strftime('%Y-%m-%d'),
                'description': entry.description,
                'total_debit': entry.total_debit,
                'total_credit': entry.total_credit,
                'status': entry.status,
                'notes': entry.notes,
                'created_by': entry.creator.full_name if entry.creator else None,
                'created_at': entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'lines': lines_data
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/journal-entries', methods=['POST'])
@login_required
def create_journal_entry():
    try:
        data = request.get_json()
        
        # التحقق من توازن القيد
        total_debit = sum(line['debit'] for line in data['lines'])
        total_credit = sum(line['credit'] for line in data['lines'])
        
        if abs(total_debit - total_credit) > 0.01:
            return jsonify({'success': False, 'message': 'القيد غير متوازن. مجموع المدين يجب يساوي مجموع الدائن'}), 400
        
        # توليد رقم القيد
        last_journal = JournalEntry.query.order_by(JournalEntry.id.desc()).first()
        journal_number = f"JRN-{datetime.now().strftime('%Y%m%d')}-{(last_journal.id + 1) if last_journal else 1:04d}"
        
        journal = JournalEntry(
            journal_number=journal_number,
            journal_date=datetime.strptime(data['journal_date'], '%Y-%m-%d').date(),
            description=data['description'],
            total_debit=total_debit,
            total_credit=total_credit,
            currency=data.get('currency', 'SAR'),
            status='draft',
            notes=data.get('notes'),
            created_by=current_user.id
        )
        
        db.session.add(journal)
        db.session.flush()  # للحصول على journal.id
        
        # إضافة بنود القيد
        for i, line_data in enumerate(data['lines'], 1):
            line = JournalLine(
                journal_id=journal.id,
                account_id=line_data['account_id'],
                debit=line_data['debit'],
                credit=line_data['credit'],
                description=line_data.get('description', ''),
                line_number=i
            )
            db.session.add(line)
        
        db.session.commit()
        
        return jsonify({'success': True, 'id': journal.id, 'message': 'تم إنشاء القيد بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/journal-entries/<int:entry_id>/post', methods=['POST'])
@login_required
def post_journal_entry(entry_id):
    try:
        journal = JournalEntry.query.get_or_404(entry_id)
        
        if journal.status != 'draft':
            return jsonify({'success': False, 'message': 'لا يمكن ترحيل قيد غير مسودة'}), 400
        
        # ترحيل كل بند من بنود القيد
        for line in journal.lines:
            account = Account.query.get(line.account_id)
            if not account:
                return jsonify({'success': False, 'message': f'الحساب {line.account_id} غير موجود'}), 400
            
            # تحديث رصيد الحساب
            if line.debit > 0:
                account.balance += line.debit
            if line.credit > 0:
                account.balance -= line.credit
            
            # إنشاء حركة لكل بند
            transaction = Transaction(
                transaction_number=f"{journal.journal_number}-{line.line_number}",
                transaction_date=journal.journal_date,
                description=f"{journal.description} - {line.description}",
                transaction_type='debit' if line.debit > 0 else 'credit',
                amount=line.debit if line.debit > 0 else line.credit,
                currency=journal.currency,
                account_id=line.account_id,
                reference_type='journal',
                reference_id=journal.id,
                reference_number=journal.journal_number,
                created_by=current_user.id
            )
            db.session.add(transaction)
        
        # تحديث حالة القيد
        journal.status = 'posted'
        journal.posted_by = current_user.id
        journal.posted_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم ترحيل القيد بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== واجهات API إضافية للوحة التحكم ==========

@app.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    try:
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        # إحصائيات الشهر
        monthly_sales = db.session.query(db.func.sum(Invoice.net_amount)).filter(
            Invoice.invoice_type == 'sales',
            Invoice.invoice_date >= month_start,
            Invoice.status.in_(['sent', 'partially_paid', 'paid'])
        ).scalar() or 0
        
        monthly_purchases = db.session.query(db.func.sum(Invoice.net_amount)).filter(
            Invoice.invoice_type == 'purchase',
            Invoice.invoice_date >= month_start,
            Invoice.status.in_(['sent', 'partially_paid', 'paid'])
        ).scalar() or 0
        
        # عدد الفواتير المستحقة
        overdue_invoices = Invoice.query.filter(
            Invoice.status.in_(['sent', 'partially_paid']),
            Invoice.due_date < today,
            Invoice.remaining_amount > 0
        ).count()
        
        # المنتجات المنخفضة
        low_stock_items = Product.query.filter(
            Product.quantity <= Product.min_quantity,
            Product.is_active == True
        ).count()
        
        # الرصيد النقدي
        cash_accounts = Account.query.filter(
            Account.account_type == 'asset',
            Account.name.like('%نقد%')
        ).all()
        cash_balance = sum(acc.balance for acc in cash_accounts)
        
        # العملاء الجدد هذا الشهر
        new_customers = Customer.query.filter(
            Customer.created_at >= month_start
        ).count()
        
        stats = {
            'monthly_sales': monthly_sales,
            'monthly_purchases': monthly_purchases,
            'overdue_invoices': overdue_invoices,
            'low_stock_items': low_stock_items,
            'cash_balance': cash_balance,
            'new_customers': new_customers
        }
        
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/dashboard/chart-data')
@login_required
def get_chart_data():
    try:
        # بيانات المبيعات للشهور الـ 6 الماضية
        today = date.today()
        months_data = []
        
        for i in range(5, -1, -1):
            month = today.month - i
            year = today.year
            
            if month <= 0:
                month += 12
                year -= 1
            
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)
            
            monthly_sales = db.session.query(db.func.sum(Invoice.net_amount)).filter(
                Invoice.invoice_type == 'sales',
                Invoice.invoice_date >= month_start,
                Invoice.invoice_date <= month_end,
                Invoice.status.in_(['sent', 'partially_paid', 'paid'])
            ).scalar() or 0
            
            monthly_purchases = db.session.query(db.func.sum(Invoice.net_amount)).filter(
                Invoice.invoice_type == 'purchase',
                Invoice.invoice_date >= month_start,
                Invoice.invoice_date <= month_end,
                Invoice.status.in_(['sent', 'partially_paid', 'paid'])
            ).scalar() or 0
            
            months_data.append({
                'month': f"{year}-{month:02d}",
                'sales': monthly_sales,
                'purchases': monthly_purchases
            })
        
        # توزيع الحسابات
        account_types = ['asset', 'liability', 'equity', 'revenue', 'expense']
        account_balances = {}
        
        for acc_type in account_types:
            balance = db.session.query(db.func.sum(Account.balance)).filter(
                Account.account_type == acc_type,
                Account.is_active == True
            ).scalar() or 0
            
            account_balances[acc_type] = balance
        
        chart_data = {
            'monthly_trend': months_data,
            'account_balances': account_balances
        }
        
        return jsonify({'success': True, 'data': chart_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== معالجة الأخطاء ==========

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    flash('غير مصرح لك بالوصول إلى هذه الصفحة', 'error')
    return redirect(url_for('dashboard'))

# ========== وظائف مساعدة ==========

def init_basic_data():
    """تهيئة البيانات الأساسية للنظام"""
    with app.app_context():
        # إنشاء الجداول
        db.create_all()
        
        # إنشاء مستخدم مدير إذا لم يكن موجوداً
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@company.com',
                full_name='مدير النظام',
                role='admin',
                phone='+966500000000',
                department='الإدارة'
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        # إنشاء الحسابات الأساسية إذا لم تكن موجودة
        if not Account.query.first():
            basic_accounts = [
                ('101', 'النقدية', 'asset', 10000),
                ('102', 'البنك الأهلي', 'asset', 50000),
                ('110', 'المدينون', 'asset', 0),
                ('120', 'المخزون', 'asset', 0),
                ('130', 'الأصول الثابتة', 'asset', 0),
                ('201', 'الدائنون', 'liability', 0),
                ('210', 'القروض', 'liability', 0),
                ('220', 'الضريبة المستحقة', 'liability', 0),
                ('301', 'رأس المال', 'equity', 60000),
                ('310', 'الأرباح المحتجزة', 'equity', 0),
                ('401', 'المبيعات', 'revenue', 0),
                ('402', 'إيرادات خدمات', 'revenue', 0),
                ('501', 'تكلفة البضاعة المباعة', 'expense', 0),
                ('510', 'مرتبات وأجور', 'expense', 0),
                ('520', 'إيجار', 'expense', 0),
                ('530', 'مصاريف نقل', 'expense', 0),
                ('540', 'مصاريف تسويق', 'expense', 0)
            ]
            
            for code, name, acc_type, balance in basic_accounts:
                account = Account(
                    code=code,
                    name=name,
                    account_type=acc_type,
                    balance=balance,
                    is_active=True
                )
                db.session.add(account)
        
        db.session.commit()
        print("✅ تم تهيئة النظام بنجاح")

# ========== نقطة التشغيل الرئيسية ==========

if __name__ == '__main__':
    # تهيئة البيانات الأساسية
    init_basic_data()
    
    # تشغيل التطبيق
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*50}")
    print("   🚀 النظام المحاسبي المتكامل")
    print(f"{'='*50}")
    print(f"📊 الوصول إلى النظام:")
    print(f"   http://localhost:{port}")
    print(f"   أو http://127.0.0.1:{port}")
    print(f"\n👤 بيانات الدخول الافتراضية:")
    print(f"   اسم المستخدم: admin")
    print(f"   كلمة المرور: admin123")
    print(f"{'='*50}\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)
else:
    # عند التشغيل على Render أو خادم إنتاجي
    init_basic_data()
