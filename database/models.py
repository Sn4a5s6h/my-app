from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, accountant, auditor, user
    department = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))  # الاسم بالإنجليزية للمستقبل
    account_type = db.Column(db.String(50), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    balance = db.Column(db.Float, default=0.0)
    opening_balance = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='SAR')
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    parent = db.relationship('Account', remote_side=[id], backref='sub_accounts')
    transactions = db.relationship('Transaction', backref='account', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Account {self.code}: {self.name}>'

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    transaction_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    transaction_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # debit, credit
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='SAR')
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    reference_type = db.Column(db.String(50))  # invoice, payment, expense, journal
    reference_id = db.Column(db.Integer)  # ID of the reference document
    reference_number = db.Column(db.String(100), index=True)
    status = db.Column(db.String(20), default='active')  # active, reversed, cancelled
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reversed_at = db.Column(db.DateTime)
    
    # العلاقات
    user = db.relationship('User', backref='transactions')
    
    def __repr__(self):
        return f'<Transaction {self.transaction_number}: {self.amount} {self.currency}>'

class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'
    id = db.Column(db.Integer, primary_key=True)
    journal_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    journal_date = db.Column(db.Date, nullable=False, index=True)
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
    lines = db.relationship('JournalLine', backref='journal_entry', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<JournalEntry {self.journal_number}>'

class JournalLine(db.Model):
    __tablename__ = 'journal_lines'
    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    description = db.Column(db.String(200))
    currency = db.Column(db.String(3), default='SAR')
    exchange_rate = db.Column(db.Float, default=1.0)
    line_number = db.Column(db.Integer)  # ترتيب البند في القيد
    
    # العلاقات
    account = db.relationship('Account', backref='journal_lines')
    
    def __repr__(self):
        return f'<JournalLine {self.debit}/{self.credit}>'

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    invoice_type = db.Column(db.String(20), nullable=False)  # sales, purchase
    invoice_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), index=True)
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
    creator = db.relationship('User', backref='created_invoices')
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy=True)
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}: {self.net_amount} {self.currency}>'

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), index=True)
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    discount_percent = db.Column(db.Float, default=0.0)
    tax_percent = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    
    # العلاقات
    product = db.relationship('Product', backref='invoice_items')
    account = db.relationship('Account', backref='invoice_items')
    
    def __repr__(self):
        return f'<InvoiceItem {self.description}: {self.quantity} x {self.unit_price}>'

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_name_en = db.Column(db.String(200))
    tax_number = db.Column(db.String(50), index=True)
    commercial_registration = db.Column(db.String(50))
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    country = db.Column(db.String(50), default='السعودية')
    customer_type = db.Column(db.String(50))  # individual, company, government
    credit_limit = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    account_receivable_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    account_receivable = db.relationship('Account', backref='customers')
    
    def __repr__(self):
        return f'<Customer {self.customer_code}: {self.customer_name}>'

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    supplier_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    supplier_name = db.Column(db.String(200), nullable=False)
    supplier_name_en = db.Column(db.String(200))
    tax_number = db.Column(db.String(50), index=True)
    commercial_registration = db.Column(db.String(50))
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    country = db.Column(db.String(50), default='السعودية')
    supplier_type = db.Column(db.String(50))  # local, international
    credit_limit = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    account_payable_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    account_payable = db.relationship('Account', backref='suppliers')
    
    def __repr__(self):
        return f'<Supplier {self.supplier_code}: {self.supplier_name}>'

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_name_en = db.Column(db.String(200))
    description = db.Column(db.Text)
    barcode = db.Column(db.String(100), index=True)
    category = db.Column(db.String(100))
    unit = db.Column(db.String(20), default='قطعة')
    purchase_price = db.Column(db.Float, default=0.0)
    selling_price = db.Column(db.Float, default=0.0)
    cost_price = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=0.0)
    min_quantity = db.Column(db.Float, default=0.0)
    max_quantity = db.Column(db.Float)
    inventory_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    sales_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    cogs_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    is_active = db.Column(db.Boolean, default=True)
    has_tax = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    inventory_account = db.relationship('Account', foreign_keys=[inventory_account_id], backref='inventory_products')
    sales_account = db.relationship('Account', foreign_keys=[sales_account_id], backref='sales_products')
    cogs_account = db.relationship('Account', foreign_keys=[cogs_account_id], backref='cogs_products')
    
    def __repr__(self):
        return f'<Product {self.product_code}: {self.product_name}>'

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    payment_date = db.Column(db.Date, nullable=False, index=True)
    payment_type = db.Column(db.String(20), nullable=False)  # receipt, payment
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='SAR')
    exchange_rate = db.Column(db.Float, default=1.0)
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, cheque, credit_card
    bank_account = db.Column(db.String(100))
    cheque_number = db.Column(db.String(50))
    cheque_date = db.Column(db.Date)
    description = db.Column(db.String(500))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), index=True)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    customer = db.relationship('Customer', backref='payments')
    supplier = db.relationship('Supplier', backref='payments')
    account = db.relationship('Account', backref='payments')
    creator = db.relationship('User', backref='created_payments')
    
    def __repr__(self):
        return f'<Payment {self.payment_number}: {self.amount} {self.currency}>'

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    expense_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='SAR')
    expense_type = db.Column(db.String(50))  # operational, administrative, marketing
    expense_category = db.Column(db.String(100))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    payment_method = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    attachment = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')  # pending, approved, paid, cancelled
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    supplier = db.relationship('Supplier', backref='expenses')
    account = db.relationship('Account', backref='expenses')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_expenses')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_expenses')
    
    def __repr__(self):
        return f'<Expense {self.expense_number}: {self.amount} {self.currency}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)  # create, update, delete, login, logout, view
    table_name = db.Column(db.String(50), index=True)
    record_id = db.Column(db.Integer, index=True)
    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # العلاقات
    user = db.relationship('User', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.action} on {self.table_name}>'

class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')  # string, number, boolean, json
    category = db.Column(db.String(50), default='general')
    description = db.Column(db.String(200))
    is_public = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Setting {self.key}>'
