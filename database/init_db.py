#!/usr/bin/env python3
"""
تهيئة قاعدة البيانات وإنشاء البيانات الأساسية
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date
from database.models import db, User, Account, Customer, Supplier, Product, Setting
from config import config

def init_database(app):
    """تهيئة قاعدة البيانات"""
    with app.app_context():
        # إنشاء جميع الجداول
        db.create_all()
        print("✅ تم إنشاء جميع الجداول بنجاح")
        
        # تهيئة البيانات الأساسية
        init_basic_data()
        
        print("✅ تم تهيئة قاعدة البيانات بنجاح")

def init_basic_data():
    """تهيئة البيانات الأساسية للنظام"""
    
    # إنشاء مستخدم مدير إذا لم يكن موجوداً
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@company.com',
            full_name='مدير النظام',
            role='admin',
            department='الإدارة',
            phone='+966500000000'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        print("✅ تم إنشاء مستخدم المدير")
    
    # إنشاء الحسابات الأساسية
    create_basic_accounts()
    
    # إنشاء إعدادات النظام
    create_settings()
    
    # إنشاء عميل افتراضي
    if not Customer.query.first():
        customer = Customer(
            customer_code='CUST001',
            customer_name='عميل افتراضي',
            email='customer@example.com',
            phone='+966500000001',
            city='الرياض',
            credit_limit=100000,
            current_balance=0
        )
        db.session.add(customer)
        print("✅ تم إنشاء عميل افتراضي")
    
    # إنشاء مورد افتراضي
    if not Supplier.query.first():
        supplier = Supplier(
            supplier_code='SUPP001',
            supplier_name='مورد افتراضي',
            email='supplier@example.com',
            phone='+966500000002',
            city='الرياض'
        )
        db.session.add(supplier)
        print("✅ تم إنشاء مورد افتراضي")
    
    # إنشاء منتج افتراضي
    if not Product.query.first():
        product = Product(
            product_code='PROD001',
            product_name='منتج افتراضي',
            description='منتج افتراضي للنظام',
            unit='قطعة',
            purchase_price=100,
            selling_price=150,
            cost_price=80,
            quantity=100,
            min_quantity=10
        )
        db.session.add(product)
        print("✅ تم إنشاء منتج افتراضي")
    
    db.session.commit()

def create_basic_accounts():
    """إنشاء الحسابات الأساسية للنظام المحاسبي"""
    
    # الحسابات الرئيسية
    main_accounts = [
        # الأصول (1)
        {'code': '101', 'name': 'النقدية في الصندوق', 'type': 'asset'},
        {'code': '102', 'name': 'البنك الأهلي', 'type': 'asset'},
        {'code': '103', 'name': 'البنك الرياض', 'type': 'asset'},
        {'code': '110', 'name': 'المدينون', 'type': 'asset'},
        {'code': '115', 'name': 'مخصص ديون مشكوك في تحصيلها', 'type': 'asset'},
        {'code': '120', 'name': 'المخزون', 'type': 'asset'},
        {'code': '130', 'name': 'الأصول الثابتة', 'type': 'asset'},
        {'code': '131', 'name': 'معدات ومكائن', 'type': 'asset'},
        {'code': '132', 'name': 'أثاث وتجهيزات', 'type': 'asset'},
        {'code': '133', 'name': 'سيارات', 'type': 'asset'},
        {'code': '140', 'name': 'مجمع إهلاك الأصول', 'type': 'asset'},
        
        # الخصوم (2)
        {'code': '201', 'name': 'الدائنون', 'type': 'liability'},
        {'code': '210', 'name': 'القروض', 'type': 'liability'},
        {'code': '220', 'name': 'الضريبة المستحقة', 'type': 'liability'},
        {'code': '230', 'name': 'المصروفات المستحقة', 'type': 'liability'},
        {'code': '240', 'name': 'الإيرادات المؤجلة', 'type': 'liability'},
        
        # حقوق الملكية (3)
        {'code': '301', 'name': 'رأس المال', 'type': 'equity'},
        {'code': '310', 'name': 'الأرباح المحتجزة', 'type': 'equity'},
        {'code': '320', 'name': 'أرباح العام الحالي', 'type': 'equity'},
        
        # الإيرادات (4)
        {'code': '401', 'name': 'مبيعات', 'type': 'revenue'},
        {'code': '402', 'name': 'إيرادات خدمات', 'type': 'revenue'},
        {'code': '410', 'name': 'خصم مكتسب', 'type': 'revenue'},
        {'code': '420', 'name': 'إيرادات أخرى', 'type': 'revenue'},
        
        # المصروفات (5)
        {'code': '501', 'name': 'تكلفة البضاعة المباعة', 'type': 'expense'},
        {'code': '510', 'name': 'مرتبات وأجور', 'type': 'expense'},
        {'code': '511', 'name': 'تأمينات اجتماعية', 'type': 'expense'},
        {'code': '520', 'name': 'إيجار', 'type': 'expense'},
        {'code': '521', 'name': 'كهرباء وماء', 'type': 'expense'},
        {'code': '522', 'name': 'هاتف وإنترنت', 'type': 'expense'},
        {'code': '530', 'name': 'مصاريف نقل ومواصلات', 'type': 'expense'},
        {'code': '531', 'name': 'مصاريف سفر', 'type': 'expense'},
        {'code': '540', 'name': 'مصاريف تسويق وإعلان', 'type': 'expense'},
        {'code': '550', 'name': 'مصاريف إدارية وعمومية', 'type': 'expense'},
        {'code': '560', 'name': 'استهلاك', 'type': 'expense'},
        {'code': '570', 'name': 'ضرائب ورسوم', 'type': 'expense'},
        {'code': '580', 'name': 'مصاريف مالية', 'type': 'expense'},
        {'code': '590', 'name': 'خصم مسموح به', 'type': 'expense'},
    ]
    
    for account_data in main_accounts:
        if not Account.query.filter_by(code=account_data['code']).first():
            account = Account(
                code=account_data['code'],
                name=account_data['name'],
                account_type=account_data['type'],
                opening_balance=0.0,
                balance=0.0,
                currency='SAR',
                is_active=True
            )
            db.session.add(account)
    
    print("✅ تم إنشاء الحسابات الأساسية")

def create_settings():
    """إنشاء إعدادات النظام الأساسية"""
    
    basic_settings = [
        {'key': 'company_name', 'value': 'شركتك المحدودة', 'category': 'company'},
        {'key': 'company_address', 'value': 'الرياض - حي الملقا', 'category': 'company'},
        {'key': 'company_phone', 'value': '+966112345678', 'category': 'company'},
        {'key': 'company_email', 'value': 'info@company.com', 'category': 'company'},
        {'key': 'company_vat', 'value': '123456789101112', 'category': 'company'},
        {'key': 'company_cr', 'value': '1010123456', 'category': 'company'},
        {'key': 'default_currency', 'value': 'SAR', 'category': 'financial'},
        {'key': 'tax_rate', 'value': '15', 'category': 'financial'},
        {'key': 'invoice_prefix', 'value': 'INV', 'category': 'invoice'},
        {'key': 'invoice_terms', 'value': 'الدفع خلال 30 يوم من تاريخ الفاتورة', 'category': 'invoice'},
        {'key': 'receipt_prefix', 'value': 'RCP', 'category': 'payment'},
        {'key': 'payment_prefix', 'value': 'PAY', 'category': 'payment'},
        {'key': 'journal_prefix', 'value': 'JRN', 'category': 'journal'},
        {'key': 'decimal_places', 'value': '2', 'category': 'system'},
        {'key': 'date_format', 'value': 'dd/mm/yyyy', 'category': 'system'},
        {'key': 'timezone', 'value': 'Asia/Riyadh', 'category': 'system'},
        {'key': 'items_per_page', 'value': '25', 'category': 'system'},
        {'key': 'backup_enabled', 'value': 'true', 'category': 'backup'},
        {'key': 'backup_frequency', 'value': 'daily', 'category': 'backup'},
        {'key': 'email_enabled', 'value': 'false', 'category': 'email'},
        {'key': 'smtp_server', 'value': 'smtp.gmail.com', 'category': 'email'},
        {'key': 'smtp_port', 'value': '587', 'category': 'email'},
    ]
    
    for setting_data in basic_settings:
        if not Setting.query.filter_by(key=setting_data['key']).first():
            setting = Setting(
                key=setting_data['key'],
                value=setting_data['value'],
                category=setting_data['category']
            )
            db.session.add(setting)
    
    print("✅ تم إنشاء إعدادات النظام")

if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.config.from_object(config)
    db.init_app(app)
    
    init_database(app)
    print("\n🎉 النظام المحاسبي جاهز للاستخدام!")
    print("📋 بيانات الدخول الافتراضية:")
    print("   اسم المستخدم: admin")
    print("   كلمة المرور: admin123")
    print("\n🚀 ابدأ التطبيق بـ: python app.py")
