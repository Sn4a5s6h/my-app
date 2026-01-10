#!/usr/bin/env python3
"""
النظام المحاسبي المتكامل - التطبيق الرئيسي
متوافق مع Render + Gunicorn
"""

import os
import logging
from datetime import datetime, date, timedelta

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, flash
)
from flask_login import (
    login_required, current_user
)
from flask_cors import CORS
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config
from database.models import (
    db, User, Account, Invoice, Customer, Supplier,
    Product, Payment, Transaction, JournalEntry, InvoiceItem
)
from database.init_db import init_database
from modules.auth import (
    login_manager, register_auth_routes,
    permission_required, admin_required, record_audit_log
)
from modules.accounting import AccountingSystem
from modules.reports import register_report_routes

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# Flask App
# -------------------------------------------------
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

# -------------------------------------------------
# Configuration
# -------------------------------------------------
app.config.from_object(config)

# Render يستخدم Proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# -------------------------------------------------
# Extensions
# -------------------------------------------------
db.init_app(app)
migrate = Migrate(app, db)
login_manager.init_app(app)
CORS(app, supports_credentials=True)

# -------------------------------------------------
# Routes Registration
# -------------------------------------------------
register_auth_routes(app)
register_report_routes(app)

# -------------------------------------------------
# Database Initialization
# -------------------------------------------------
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")

# =================================================
# Main Pages
# =================================================

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    total_customers = Customer.query.filter_by(is_active=True).count()
    total_suppliers = Supplier.query.filter_by(is_active=True).count()
    total_products = Product.query.filter_by(is_active=True).count()

    pending_invoices = Invoice.query.filter(
        Invoice.status.in_(["draft", "sent", "partially_paid"]),
        Invoice.due_date <= date.today()
    ).count()

    cash_accounts = Account.query.filter(
        Account.account_type == "asset",
        Account.name.like("%نقد%")
    ).all()
    cash_balance = sum(acc.balance for acc in cash_accounts)

    low_stock_items = Product.query.filter(
        Product.quantity <= Product.min_quantity,
        Product.is_active.is_(True)
    ).count()

    recent_transactions = Transaction.query.filter_by(status="active") \
        .order_by(Transaction.transaction_date.desc()) \
        .limit(10).all()

    return render_template(
        "dashboard.html",
        total_customers=total_customers,
        total_suppliers=total_suppliers,
        total_products=total_products,
        pending_invoices=pending_invoices,
        cash_balance=cash_balance,
        low_stock_items=low_stock_items,
        recent_transactions=recent_transactions
    )

# =================================================
# Accounts API
# =================================================

@app.route("/api/accounts")
@login_required
def get_accounts():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    return jsonify({
        "success": True,
        "data": [
            {
                "id": a.id,
                "code": a.code,
                "name": a.name,
                "type": a.account_type,
                "parent_id": a.parent_id,
                "balance": float(a.balance),
                "currency": a.currency
            } for a in accounts
        ]
    })

@app.route("/api/accounts", methods=["POST"])
@login_required
@permission_required("create")
def create_account():
    data = request.get_json()
    result = AccountingSystem.create_account(data, current_user.id)
    return jsonify(result)

# =================================================
# Invoices API
# =================================================

@app.route("/api/invoices")
@login_required
def get_invoices():
    invoice_type = request.args.get("type", "sales")
    query = Invoice.query.filter_by(invoice_type=invoice_type)

    invoices = query.order_by(Invoice.invoice_date.desc()).all()
    return jsonify({
        "success": True,
        "data": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date.strftime("%Y-%m-%d"),
                "total_amount": float(inv.total_amount),
                "net_amount": float(inv.net_amount),
                "status": inv.status
            } for inv in invoices
        ]
    })

@app.route("/api/invoices", methods=["POST"])
@login_required
@permission_required("create")
def create_invoice():
    data = request.get_json()
    result = AccountingSystem.create_invoice(data, current_user.id)
    return jsonify(result)

# =================================================
# Customers / Suppliers / Products
# =================================================

@app.route("/api/customers")
@login_required
def get_customers():
    customers = Customer.query.filter_by(is_active=True).all()
    return jsonify({"success": True, "data": [
        {
            "id": c.id,
            "name": c.customer_name,
            "balance": float(c.current_balance)
        } for c in customers
    ]})

@app.route("/api/suppliers")
@login_required
def get_suppliers():
    suppliers = Supplier.query.filter_by(is_active=True).all()
    return jsonify({"success": True, "data": [
        {
            "id": s.id,
            "name": s.supplier_name,
            "balance": float(s.current_balance)
        } for s in suppliers
    ]})

@app.route("/api/products")
@login_required
def get_products():
    products = Product.query.filter_by(is_active=True).all()
    return jsonify({"success": True, "data": [
        {
            "id": p.id,
            "name": p.product_name,
            "qty": float(p.quantity)
        } for p in products
    ]})

# =================================================
# Error Handlers
# =================================================

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(e)
    return render_template("500.html"), 500

@app.errorhandler(403)
def forbidden(e):
    flash("غير مصرح لك بالدخول", "error")
    return redirect(url_for("dashboard"))

# =================================================
# Render Entry Point (IMPORTANT)
# =================================================
# لا يوجد app.run()
# Gunicorn سيشغل:
# gunicorn app:app
