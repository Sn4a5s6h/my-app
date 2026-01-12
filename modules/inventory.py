"""
نظام إدارة المخزون
"""

from datetime import datetime
from decimal import Decimal
from flask import jsonify, request
import logging
from sqlalchemy import func

from database.models import db, Product, Invoice, InvoiceItem, Transaction, Account
from modules.auth import record_audit_log, get_current_user_id
from modules.accounting import AccountingSystem

logger = logging.getLogger(__name__)

class InventorySystem:
    """نظام إدارة المخزون"""
    
    @staticmethod
    def add_product(product_data, user_id):
        """إضافة منتج جديد"""
        try:
            # التحقق من وجود الكود مسبقاً
            if Product.query.filter_by(product_code=product_data['product_code']).first():
                return {'success': False, 'message': 'كود المنتج موجود مسبقاً'}
            
            product = Product(
                product_code=product_data['product_code'],
                product_name=product_data['product_name'],
                product_name_en=product_data.get('product_name_en'),
                description=product_data.get('description'),
                barcode=product_data.get('barcode'),
                category=product_data.get('category'),
                unit=product_data.get('unit', 'قطعة'),
                purchase_price=Decimal(product_data.get('purchase_price', 0)).quantize(Decimal('0.01')),
                selling_price=Decimal(product_data.get('selling_price', 0)).quantize(Decimal('0.01')),
                cost_price=Decimal(product_data.get('cost_price', 0)).quantize(Decimal('0.01')),
                quantity=Decimal(product_data.get('quantity', 0)).quantize(Decimal('0.001')),
                min_quantity=Decimal(product_data.get('min_quantity', 0)).quantize(Decimal('0.001')),
                max_quantity=Decimal(product_data.get('max_quantity')).quantize(Decimal('0.001')) if product_data.get('max_quantity') else None,
                inventory_account_id=product_data.get('inventory_account_id'),
                sales_account_id=product_data.get('sales_account_id'),
                cogs_account_id=product_data.get('cogs_account_id'),
                has_tax=product_data.get('has_tax', True),
                is_active=True,
                notes=product_data.get('notes')
            )
            
            db.session.add(product)
            db.session.commit()
            
            # تسجيل الحركة
            record_audit_log('create', 'products', product.id, None, product_data)
            
            return {'success': True, 'product_id': product.id, 'message': 'تم إضافة المنتج بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding product: {e}")
            return {'success': False, 'message': f'خطأ في إضافة المنتج: {str(e)}'}
    
    @staticmethod
    def update_stock(product_id, quantity_change, transaction_type, reference, reference_id, user_id):
        """تحديث المخزون"""
        try:
            product = Product.query.get(product_id)
            if not product:
                return {'success': False, 'message': 'المنتج غير موجود'}
            
            old_quantity = product.quantity
            
            if transaction_type == 'purchase':
                product.quantity += Decimal(quantity_change)
            elif transaction_type == 'sale':
                product.quantity -= Decimal(quantity_change)
            elif transaction_type == 'return':
                product.quantity += Decimal(quantity_change)
            elif transaction_type == 'adjustment':
                product.quantity = Decimal(quantity_change)
            elif transaction_type == 'damage':
                product.quantity -= Decimal(quantity_change)
            
            # التحقق من عدم وجود كمية سالبة
            if product.quantity < 0:
                return {'success': False, 'message': 'الكمية لا يمكن أن تكون سالبة'}
            
            # تسجيل حركة المخزون
            stock_transaction = {
                'account_id': product.inventory_account_id,
                'transaction_date': datetime.now().date(),
                'description': f'{transaction_type} - {product.product_name}',
                'transaction_type': 'debit' if transaction_type in ['purchase', 'return'] else 'credit',
                'amount': Decimal(quantity_change) * product.cost_price,
                'reference_type': 'inventory',
                'reference_id': reference_id,
                'reference_number': reference
            }
            
            AccountingSystem.create_transaction(stock_transaction, user_id)
            
            db.session.commit()
            
            # تسجيل الحركة
            record_audit_log('update', 'products', product.id, 
                           {'quantity': old_quantity}, 
                           {'quantity': product.quantity})
            
            return {'success': True, 'message': 'تم تحديث المخزون بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating stock: {e}")
            return {'success': False, 'message': f'خطأ في تحديث المخزون: {str(e)}'}
    
    @staticmethod
    def process_invoice_items(invoice_id, invoice_type, user_id):
        """معالجة بنود الفاتورة وتحديث المخزون"""
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            for item in invoice.items:
                if item.product_id:
                    if invoice_type == 'sales':
                        # خصم من المخزون للمبيعات
                        InventorySystem.update_stock(
                            item.product_id,
                            item.quantity,
                            'sale',
                            invoice.invoice_number,
                            invoice.id,
                            user_id
                        )
                        
                        # تسجيل تكلفة البضاعة المباعة
                        if item.product.cogs_account_id:
                            cogs_transaction = {
                                'account_id': item.product.cogs_account_id,
                                'transaction_date': invoice.invoice_date,
                                'description': f'COGS - {item.product.product_name}',
                                'transaction_type': 'debit',
                                'amount': item.quantity * item.product.cost_price,
                                'reference_type': 'invoice',
                                'reference_id': invoice.id,
                                'reference_number': invoice.invoice_number
                            }
                            AccountingSystem.create_transaction(cogs_transaction, user_id)
                    
                    elif invoice_type == 'purchase':
                        # إضافة إلى المخزون للمشتريات
                        InventorySystem.update_stock(
                            item.product_id,
                            item.quantity,
                            'purchase',
                            invoice.invoice_number,
                            invoice.id,
                            user_id
                        )
            
            return {'success': True, 'message': 'تم معالجة بنود الفاتورة بنجاح'}
            
        except Exception as e:
            logger.error(f"Error processing invoice items: {e}")
            return {'success': False, 'message': f'خطأ في معالجة بنود الفاتورة: {str(e)}'}
    
    @staticmethod
    def get_inventory_report():
        """تقرير المخزون الحالي"""
        try:
            products = Product.query.filter_by(is_active=True).order_by(Product.category, Product.product_name).all()
            
            inventory_data = []
            total_value = Decimal('0')
            
            for product in products:
                item_value = product.quantity * product.cost_price
                total_value += item_value
                
                inventory_data.append({
                    'id': product.id,
                    'product_code': product.product_code,
                    'product_name': product.product_name,
                    'category': product.category,
                    'unit': product.unit,
                    'quantity': product.quantity,
                    'min_quantity': product.min_quantity,
                    'max_quantity': product.max_quantity,
                    'cost_price': product.cost_price,
                    'selling_price': product.selling_price,
                    'total_value': item_value,
                    'status': 'منخفض' if product.quantity < product.min_quantity else 'طبيعي'
                })
            
            return {
                'success': True,
                'inventory': inventory_data,
                'total_value': total_value,
                'total_items': len(inventory_data)
            }
            
        except Exception as e:
            logger.error(f"Error getting inventory report: {e}")
            return {'success': False, 'message': f'خطأ في توليد تقرير المخزون: {str(e)}'}
    
    @staticmethod
    def get_low_stock_items(threshold_percent=20):
        """الحصول على المنتجات ذات المخزون المنخفض"""
        try:
            low_stock_items = []
            
            products = Product.query.filter_by(is_active=True).all()
            
            for product in products:
                if product.max_quantity and product.min_quantity:
                    stock_percentage = (product.quantity / product.max_quantity) * 100
                    
                    if stock_percentage <= threshold_percent or product.quantity <= product.min_quantity:
                        low_stock_items.append({
                            'product_code': product.product_code,
                            'product_name': product.product_name,
                            'current_quantity': product.quantity,
                            'min_quantity': product.min_quantity,
                            'max_quantity': product.max_quantity,
                            'percentage': round(stock_percentage, 2),
                            'unit': product.unit
                        })
            
            return {
                'success': True,
                'items': low_stock_items,
                'count': len(low_stock_items)
            }
            
        except Exception as e:
            logger.error(f"Error getting low stock items: {e}")
            return {'success': False, 'message': f'خطأ في الحصول على المنتجات المنخفضة: {str(e)}'}
    
    @staticmethod
    def get_inventory_movement(product_id, start_date, end_date):
        """حركة المخزون لمنتج معين"""
        try:
            product = Product.query.get(product_id)
            if not product:
                return {'success': False, 'message': 'المنتج غير موجود'}
            
            # جلب الحركات المرتبطة بالمنتج
            sales_items = InvoiceItem.query.join(Invoice).filter(
                InvoiceItem.product_id == product_id,
                Invoice.invoice_type == 'sales',
                Invoice.invoice_date >= start_date,
                Invoice.invoice_date <= end_date,
                Invoice.status.in_(['sent', 'partially_paid', 'paid'])
            ).all()
            
            purchase_items = InvoiceItem.query.join(Invoice).filter(
                InvoiceItem.product_id == product_id,
                Invoice.invoice_type == 'purchase',
                Invoice.invoice_date >= start_date,
                Invoice.invoice_date <= end_date,
                Invoice.status.in_(['sent', 'partially_paid', 'paid'])
            ).all()
            
            # تتبع الحركات
            movements = []
            
            # المبيعات
            for item in sales_items:
                movements.append({
                    'date': item.invoice.invoice_date.strftime('%Y-%m-%d'),
                    'type': 'sale',
                    'document': item.invoice.invoice_number,
                    'quantity': -item.quantity,  # سالب للمبيعات
                    'unit_price': item.unit_price,
                    'total': -item.total_amount,
                    'customer': item.invoice.customer.customer_name if item.invoice.customer else 'غير معروف'
                })
            
            # المشتريات
            for item in purchase_items:
                movements.append({
                    'date': item.invoice.invoice_date.strftime('%Y-%m-%d'),
                    'type': 'purchase',
                    'document': item.invoice.invoice_number,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total': item.total_amount,
                    'supplier': item.invoice.supplier.supplier_name if item.invoice.supplier else 'غير معروف'
                })
            
            # ترتيب الحركات حسب التاريخ
            movements.sort(key=lambda x: x['date'])
            
            # حساب المجاميع
            total_sales = sum(m['quantity'] for m in movements if m['type'] == 'sale')
            total_purchases = sum(m['quantity'] for m in movements if m['type'] == 'purchase')
            net_movement = total_purchases + total_sales  # total_sales سالب
            
            return {
                'success': True,
                'product': {
                    'code': product.product_code,
                    'name': product.product_name,
                    'current_stock': product.quantity
                },
                'period': {
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                },
                'movements': movements,
                'summary': {
                    'total_purchases': total_purchases,
                    'total_sales': abs(total_sales),
                    'net_movement': net_movement
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting inventory movement: {e}")
            return {'success': False, 'message': f'خطأ في الحصول على حركة المخزون: {str(e)}'}

class InventoryValuation:
    """تقييم المخزون"""
    
    @staticmethod
    def calculate_inventory_value(valuation_method='fifo'):
        """حساب قيمة المخزون باستخدام طرق تقييم مختلفة"""
        try:
            products = Product.query.filter_by(is_active=True).all()
            
            total_value = Decimal('0')
            valuation_data = []
            
            for product in products:
                if valuation_method == 'fifo':
                    # طريقة أول وارد أول صادر (تتطلب تسجيل دقيق للدفعات)
                    value = product.quantity * product.cost_price
                elif valuation_method == 'average':
                    # طريقة المتوسط المرجح
                    value = product.quantity * product.cost_price
                elif valuation_method == 'lifo':
                    # طريقة آخر وارد أول صادر
                    value = product.quantity * product.cost_price
                else:  # طريقة التكلفة الفعلية
                    value = product.quantity * product.cost_price
                
                total_value += value
                
                valuation_data.append({
                    'product_code': product.product_code,
                    'product_name': product.product_name,
                    'quantity': product.quantity,
                    'unit_cost': product.cost_price,
                    'total_value': value,
                    'valuation_method': valuation_method
                })
            
            return {
                'success': True,
                'valuation_method': valuation_method,
                'items': valuation_data,
                'total_value': total_value,
                'as_of_date': datetime.now().date().strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Error calculating inventory value: {e}")
            return {'success': False, 'message': f'خطأ في حساب قيمة المخزون: {str(e)}'}
    
    @staticmethod
    def get_inventory_turnover(start_date, end_date):
        """حساب معدل دوران المخزون"""
        try:
            # حساب تكلفة البضاعة المباعة
            cogs_accounts = Account.query.filter_by(account_type='expense').filter(
                Account.name.like('%تكلفة%')
            ).all()
            
            total_cogs = Decimal('0')
            for account in cogs_accounts:
                period_balance = AccountingHelpers.get_account_period_balance(account.id, start_date, end_date)
                total_cogs += period_balance
            
            # حساب متوسط المخزون
            inventory_accounts = Account.query.filter_by(account_type='asset').filter(
                Account.name.like('%مخزون%')
            ).all()
            
            opening_inventory = Decimal('0')
            closing_inventory = Decimal('0')
            
            for account in inventory_accounts:
                opening_inventory += AccountingHelpers.get_account_balance(account.id, start_date)
                closing_inventory += AccountingHelpers.get_account_balance(account.id, end_date)
            
            average_inventory = (opening_inventory + closing_inventory) / 2
            
            # حساب معدل الدوران
            if average_inventory > 0:
                turnover_ratio = total_cogs / average_inventory
                days_inventory = 365 / turnover_ratio if turnover_ratio > 0 else 0
            else:
                turnover_ratio = Decimal('0')
                days_inventory = Decimal('0')
            
            return {
                'success': True,
                'cost_of_goods_sold': total_cogs,
                'average_inventory': average_inventory,
                'turnover_ratio': round(turnover_ratio, 2),
                'days_inventory': round(days_inventory, 2),
                'period': {
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating inventory turnover: {e}")
            return {'success': False, 'message': f'خطأ في حساب معدل دوران المخزون: {str(e)}'}
