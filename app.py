#!/usr/bin/env python3
"""
النظام المحاسبي المتكامل - التطبيق الرئيسي
"""

import os
import logging
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from flask_login import login_required, current_user, login_user, logout_user
from flask_cors import CORS
from flask_migrate import Migrate

from config import config
from database.models import db, User, Account, Invoice, Customer, Supplier, Product, Payment, Transaction, JournalEntry, InvoiceItem
from database.init_db import init_database
from modules.auth import login_manager, register_auth_routes, permission_required, admin_required, record_audit_log
from modules.accounting import AccountingSystem, FinancialReports, AccountingHelpers
from modules.inventory import InventorySystem
from modules.reports import register_report_routes, PDFReportGenerator

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إنشاء تطبيق Flask
app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')
app.config.from_object(config)

# تهيئة الإضافات
db.init_app(app)
migrate = Migrate(app, db)
login_manager.init_app(app)
CORS(app, supports_credentials=True)

# تسجيل المسارات
register_auth_routes(app)
register_report_routes(app)

# تهيئة قاعدة البيانات عند التشغيل الأول
with app.app_context():
    db_file = 'accounting_system.db'
    if not os.path.exists(db_file):
        init_database(app)
        logger.info("✅ تم تهيئة قاعدة البيانات لأول مرة")
    else:
        # التأكد من أن جميع الجداول موجودة
        db.create_all()
        logger.info("✅ قاعدة البيانات جاهزة")

# ======================= الصفحات الرئيسية =======================

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم"""
    # إحصائيات سريعة
    total_customers = Customer.query.filter_by(is_active=True).count()
    total_suppliers = Supplier.query.filter_by(is_active=True).count()
    total_products = Product.query.filter_by(is_active=True).count()
    
    # الفواتير المعلقة
    pending_invoices = Invoice.query.filter(
        Invoice.status.in_(['draft', 'sent', 'partially_paid']),
        Invoice.due_date <= date.today()
    ).count()
    
    # الأرصدة النقدية
    cash_accounts = Account.query.filter(
        Account.account_type == 'asset',
        Account.name.like('%نقد%')
    ).all()
    cash_balance = sum(acc.balance for acc in cash_accounts)
    
    # المنتجات المنخفضة
    low_stock_items = Product.query.filter(
        Product.quantity <= Product.min_quantity,
        Product.is_active == True
    ).count()
    
    # أحدث الحركات
    recent_transactions = Transaction.query.filter_by(status='active')\
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())\
        .limit(10).all()
    
    return render_template('dashboard.html',
                         total_customers=total_customers,
                         total_suppliers=total_suppliers,
                         total_products=total_products,
                         pending_invoices=pending_invoices,
                         cash_balance=cash_balance,
                         low_stock_items=low_stock_items,
                         recent_transactions=recent_transactions)

# ======================= واجهات API للحسابات =======================

@app.route('/api/accounts')
@login_required
def get_accounts():
    """الحصول على قائمة الحسابات"""
    try:
        accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
        
        accounts_data = []
        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'code': account.code,
                'name': account.name,
                'type': account.account_type,
                'parent_id': account.parent_id,
                'balance': float(account.balance),
                'currency': account.currency
            })
        
        return jsonify({'success': True, 'data': accounts_data})
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/accounts/<int:account_id>')
@login_required
def get_account(account_id):
    """الحصول على بيانات حساب محدد"""
    try:
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'success': False, 'message': 'الحساب غير موجود'}), 404
        
        account_data = {
            'id': account.id,
            'code': account.code,
            'name': account.name,
            'type': account.account_type,
            'parent_id': account.parent_id,
            'opening_balance': float(account.opening_balance),
            'balance': float(account.balance),
            'currency': account.currency,
            'notes': account.notes,
            'created_at': account.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify({'success': True, 'data': account_data})
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/accounts', methods=['POST'])
@login_required
@permission_required('create')
def create_account():
    """إنشاء حساب جديد"""
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['code', 'name', 'account_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'حقل {field} مطلوب'}), 400
        
        result = AccountingSystem.create_account(data, current_user.id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= واجهات API للفواتير =======================

@app.route('/api/invoices')
@login_required
def get_invoices():
    """الحصول على قائمة الفواتير"""
    try:
        invoice_type = request.args.get('type', 'sales')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        query = Invoice.query.filter_by(invoice_type=invoice_type)
        
        if status:
            query = query.filter_by(status=status)
        
        if invoice_type == 'sales':
            query = query.filter(Invoice.customer_id.isnot(None))
        else:
            query = query.filter(Invoice.supplier_id.isnot(None))
        
        invoices = query.order_by(Invoice.invoice_date.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        invoices_data = []
        for invoice in invoices.items:
            invoice_data = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
                'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else None,
                'total_amount': float(invoice.total_amount),
                'tax_amount': float(invoice.tax_amount),
                'net_amount': float(invoice.net_amount),
                'paid_amount': float(invoice.paid_amount),
                'remaining_amount': float(invoice.remaining_amount),
                'status': invoice.status,
                'customer_name': invoice.customer.customer_name if invoice.customer else None,
                'supplier_name': invoice.supplier.supplier_name if invoice.supplier else None
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
    except Exception as e:
        logger.error(f"Error getting invoices: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/invoices', methods=['POST'])
@login_required
@permission_required('create')
def create_invoice():
    """إنشاء فاتورة جديدة"""
    try:
        data = request.get_json()
        
        # توليد رقم الفاتورة
        last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
        prefix = 'SALE' if data.get('invoice_type') == 'sales' else 'PUR'
        invoice_number = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{(last_invoice.id + 1) if last_invoice else 1:04d}"
        
        # حساب المجاميع
        items = data.get('items', [])
        total_amount = sum(item['quantity'] * item['unit_price'] for item in items)
        tax_amount = total_amount * (data.get('tax_rate', 15) / 100)
        discount_amount = data.get('discount_amount', 0)
        net_amount = total_amount + tax_amount - discount_amount
        
        invoice = Invoice(
            invoice_number=invoice_number,
            invoice_type=data.get('invoice_type', 'sales'),
            invoice_date=datetime.strptime(data.get('invoice_date'), '%Y-%m-%d').date(),
            due_date=datetime.strptime(data.get('due_date'), '%Y-%m-%d').date() if data.get('due_date') else None,
            customer_id=data.get('customer_id'),
            supplier_id=data.get('supplier_id'),
            total_amount=total_amount,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            net_amount=net_amount,
            paid_amount=0,
            remaining_amount=net_amount,
            status='draft',
            payment_terms=data.get('payment_terms'),
            notes=data.get('notes'),
            terms_conditions=data.get('terms_conditions'),
            created_by=current_user.id
        )
        
        db.session.add(invoice)
        db.session.flush()  # للحصول على invoice.id
        
        # إضافة البنود
        for item_data in items:
            item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=item_data.get('product_id'),
                description=item_data.get('description'),
                quantity=item_data.get('quantity'),
                unit_price=item_data.get('unit_price'),
                total_amount=item_data.get('quantity') * item_data.get('unit_price')
            )
            db.session.add(item)
        
        db.session.commit()
        
        # تسجيل الحركة
        record_audit_log('create', 'invoices', invoice.id, None, data)
        
        return jsonify({
            'success': True,
            'invoice_id': invoice.id,
            'invoice_number': invoice_number,
            'message': 'تم إنشاء الفاتورة بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating invoice: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= واجهات API للعملاء =======================

@app.route('/api/customers')
@login_required
def get_customers():
    """الحصول على قائمة العملاء"""
    try:
        customers = Customer.query.filter_by(is_active=True).order_by(Customer.customer_name).all()
        
        customers_data = []
        for customer in customers:
            customers_data.append({
                'id': customer.id,
                'customer_code': customer.customer_code,
                'customer_name': customer.customer_name,
                'tax_number': customer.tax_number,
                'email': customer.email,
                'phone': customer.phone,
                'current_balance': float(customer.current_balance),
                'credit_limit': float(customer.credit_limit)
            })
        
        return jsonify({'success': True, 'data': customers_data})
    except Exception as e:
        logger.error(f"Error getting customers: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= واجهات API للموردين =======================

@app.route('/api/suppliers')
@login_required
def get_suppliers():
    """الحصول على قائمة الموردين"""
    try:
        suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.supplier_name).all()
        
        suppliers_data = []
        for supplier in suppliers:
            suppliers_data.append({
                'id': supplier.id,
                'supplier_code': supplier.supplier_code,
                'supplier_name': supplier.supplier_name,
                'tax_number': supplier.tax_number,
                'email': supplier.email,
                'phone': supplier.phone,
                'current_balance': float(supplier.current_balance)
            })
        
        return jsonify({'success': True, 'data': suppliers_data})
    except Exception as e:
        logger.error(f"Error getting suppliers: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= واجهات API للمنتجات =======================

@app.route('/api/products')
@login_required
def get_products():
    """الحصول على قائمة المنتجات"""
    try:
        products = Product.query.filter_by(is_active=True).order_by(Product.product_name).all()
        
        products_data = []
        for product in products:
            products_data.append({
                'id': product.id,
                'product_code': product.product_code,
                'product_name': product.product_name,
                'category': product.category,
                'unit': product.unit,
                'quantity': float(product.quantity),
                'selling_price': float(product.selling_price),
                'purchase_price': float(product.purchase_price)
            })
        
        return jsonify({'success': True, 'data': products_data})
    except Exception as e:
        logger.error(f"Error getting products: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= صفحات الواجهة =======================

@app.route('/accounts')
@login_required
def accounts_page():
    """صفحة الحسابات"""
    return render_template('accounts.html')

@app.route('/invoices')
@login_required
def invoices_page():
    """صفحة الفواتير"""
    return render_template('invoices.html')

@app.route('/customers')
@login_required
def customers_page():
    """صفحة العملاء"""
    return render_template('customers.html')

@app.route('/suppliers')
@login_required
def suppliers_page():
    """صفحة الموردين"""
    return render_template('suppliers.html')

@app.route('/products')
@login_required
def products_page():
    """صفحة المنتجات"""
    return render_template('products.html')

@app.route('/reports')
@login_required
@permission_required('report')
def reports_page():
    """صفحة التقارير"""
    return render_template('reports.html')

@app.route('/journal')
@login_required
@permission_required('accountant')
def journal_page():
    """صفحة القيود اليومية"""
    return render_template('journal.html')

@app.route('/payments')
@login_required
def payments_page():
    """صفحة السندات"""
    return render_template('payments.html')

@app.route('/settings')
@login_required
@admin_required
def settings_page():
    """صفحة الإعدادات"""
    return render_template('settings.html')

# ======================= واجهات API للقيود اليومية =======================

@app.route('/api/journal-entries')
@login_required
@permission_required('accountant')
def get_journal_entries():
    """الحصول على قائمة القيود اليومية"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        query = JournalEntry.query
        
        if status:
            query = query.filter_by(status=status)
        
        entries = query.order_by(JournalEntry.journal_date.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        entries_data = []
        for entry in entries.items:
            entries_data.append({
                'id': entry.id,
                'journal_number': entry.journal_number,
                'journal_date': entry.journal_date.strftime('%Y-%m-%d'),
                'description': entry.description,
                'total_debit': float(entry.total_debit),
                'total_credit': float(entry.total_credit),
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
        logger.error(f"Error getting journal entries: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/journal-entries/<int:entry_id>')
@login_required
@permission_required('accountant')
def get_journal_entry(entry_id):
    """الحصول على بيانات قيد يومية محدد"""
    try:
        entry = JournalEntry.query.get(entry_id)
        if not entry:
            return jsonify({'success': False, 'message': 'القيد غير موجود'}), 404
        
        lines_data = []
        for line in entry.lines:
            lines_data.append({
                'id': line.id,
                'account_id': line.account_id,
                'account_code': line.account.code,
                'account_name': line.account.name,
                'debit': float(line.debit),
                'credit': float(line.credit),
                'description': line.description
            })
        
        entry_data = {
            'id': entry.id,
            'journal_number': entry.journal_number,
            'journal_date': entry.journal_date.strftime('%Y-%m-%d'),
            'description': entry.description,
            'total_debit': float(entry.total_debit),
            'total_credit': float(entry.total_credit),
            'status': entry.status,
            'notes': entry.notes,
            'created_by': entry.creator.full_name if entry.creator else None,
            'created_at': entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'lines': lines_data
        }
        
        return jsonify({'success': True, 'data': entry_data})
    except Exception as e:
        logger.error(f"Error getting journal entry: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/journal-entries', methods=['POST'])
@login_required
@permission_required('accountant')
def create_journal_entry():
    """إنشاء قيد يومية جديد"""
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        if 'description' not in data or 'journal_date' not in data or 'lines' not in data:
            return jsonify({'success': False, 'message': 'بيانات غير مكتملة'}), 400
        
        result = AccountingSystem.create_journal_entry(data, current_user.id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error creating journal entry: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/journal-entries/<int:entry_id>/post', methods=['POST'])
@login_required
@permission_required('accountant')
def post_journal_entry(entry_id):
    """ترحيل قيد يومية"""
    try:
        result = AccountingSystem.post_journal_entry(entry_id, current_user.id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error posting journal entry: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= واجهات API للسندات =======================

@app.route('/api/payments')
@login_required
def get_payments():
    """الحصول على قائمة السندات"""
    try:
        payment_type = request.args.get('type')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        query = Payment.query
        
        if payment_type:
            query = query.filter_by(payment_type=payment_type)
        
        payments = query.order_by(Payment.payment_date.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        payments_data = []
        for payment in payments.items:
            payments_data.append({
                'id': payment.id,
                'payment_number': payment.payment_number,
                'payment_date': payment.payment_date.strftime('%Y-%m-%d'),
                'payment_type': 'سند قبض' if payment.payment_type == 'receipt' else 'سند صرف',
                'amount': float(payment.amount),
                'payment_method': payment.payment_method,
                'customer_name': payment.customer.customer_name if payment.customer else None,
                'supplier_name': payment.supplier.supplier_name if payment.supplier else None,
                'invoice_number': payment.invoice.invoice_number if payment.invoice else None,
                'description': payment.description,
                'status': payment.status
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
        logger.error(f"Error getting payments: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/payments', methods=['POST'])
@login_required
@permission_required('accountant')
def create_payment():
    """إنشاء سند جديد"""
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['payment_date', 'payment_type', 'amount', 'payment_method']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'حقل {field} مطلوب'}), 400
        
        result = AccountingSystem.create_payment(data, current_user.id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= واجهات API للحركات المالية =======================

@app.route('/api/transactions')
@login_required
def get_transactions():
    """الحصول على قائمة الحركات المالية"""
    try:
        account_id = request.args.get('account_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        query = Transaction.query.filter_by(status='active')
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date >= start_date_obj)
        
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date <= end_date_obj)
        
        transactions = query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        transactions_data = []
        for trans in transactions.items:
            transactions_data.append({
                'id': trans.id,
                'transaction_number': trans.transaction_number,
                'transaction_date': trans.transaction_date.strftime('%Y-%m-%d'),
                'description': trans.description,
                'transaction_type': trans.transaction_type,
                'amount': float(trans.amount),
                'account_code': trans.account.code,
                'account_name': trans.account.name,
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
    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= واجهات API للتقارير السريعة =======================

@app.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    """الحصول على إحصائيات لوحة التحكم"""
    try:
        # حساب الإحصائيات
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        # إجمالي المبيعات للشهر
        monthly_sales = db.session.query(db.func.sum(Invoice.net_amount)).filter(
            Invoice.invoice_type == 'sales',
            Invoice.invoice_date >= month_start,
            Invoice.invoice_date <= today,
            Invoice.status.in_(['sent', 'partially_paid', 'paid'])
        ).scalar() or 0
        
        # إجمالي المشتريات للشهر
        monthly_purchases = db.session.query(db.func.sum(Invoice.net_amount)).filter(
            Invoice.invoice_type == 'purchase',
            Invoice.invoice_date >= month_start,
            Invoice.invoice_date <= today,
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
            'monthly_sales': float(monthly_sales),
            'monthly_purchases': float(monthly_purchases),
            'overdue_invoices': overdue_invoices,
            'low_stock_items': low_stock_items,
            'cash_balance': float(cash_balance),
            'new_customers': new_customers
        }
        
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/dashboard/chart-data')
@login_required
def get_chart_data():
    """الحصول على بيانات الرسوم البيانية"""
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
                'sales': float(monthly_sales),
                'purchases': float(monthly_purchases)
            })
        
        # توزيع الحسابات
        account_types = ['asset', 'liability', 'equity', 'revenue', 'expense']
        account_balances = {}
        
        for acc_type in account_types:
            balance = db.session.query(db.func.sum(Account.balance)).filter(
                Account.account_type == acc_type,
                Account.is_active == True
            ).scalar() or 0
            
            account_balances[acc_type] = float(balance)
        
        chart_data = {
            'monthly_trend': months_data,
            'account_balances': account_balances
        }
        
        return jsonify({'success': True, 'data': chart_data})
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================= معالجة الأخطاء =======================

@app.errorhandler(404)
def page_not_found(e):
    """معالجة الصفحات غير الموجودة"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """معالجة الأخطاء الداخلية"""
    logger.error(f"Internal server error: {e}")
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    """معالجة الأخطاء المحظورة"""
    flash('غير مصرح لك بالوصول إلى هذه الصفحة', 'error')
    return redirect(url_for('dashboard'))

# ======================= نقطة الدخول الرئيسية =======================

if __name__ == '__main__':
    # إنشاء المجلدات المطلوبة
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('static/exports', exist_ok=True)
    
    # تشغيل التطبيق
    print("\n" + "="*50)
    print("   النظام المحاسبي المتكامل")
    print("="*50)
    print(f"📊 الوصول إلى النظام من خلال: http://{config.HOST}:{config.PORT}")
    print(f"👤 اسم المستخدم الافتراضي: admin")
    print(f"🔐 كلمة المرور الافتراضية: admin123")
    print("="*50 + "\n")
    
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True
    )
