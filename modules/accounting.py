"""
الوحدات المحاسبية الأساسية
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from flask import jsonify, request, flash, current_app
import logging
import json

from database.models import db, Account, Transaction, JournalEntry, JournalLine, Customer, Supplier, Payment, Invoice
from modules.auth import record_audit_log, get_current_user_id, require_accountant

# إعداد السجل
logger = logging.getLogger(__name__)

class AccountingSystem:
    """النظام المحاسبي الأساسي"""
    
    @staticmethod
    def create_account(account_data, user_id):
        """إنشاء حساب جديد"""
        try:
            # التحقق من وجود الكود مسبقاً
            if Account.query.filter_by(code=account_data['code']).first():
                return {'success': False, 'message': 'رقم الحساب موجود مسبقاً'}
            
            account = Account(
                code=account_data['code'],
                name=account_data['name'],
                account_type=account_data['account_type'],
                parent_id=account_data.get('parent_id'),
                opening_balance=Decimal(account_data.get('opening_balance', 0)).quantize(Decimal('0.01')),
                balance=Decimal(account_data.get('opening_balance', 0)).quantize(Decimal('0.01')),
                currency=account_data.get('currency', 'SAR'),
                is_active=True,
                notes=account_data.get('notes')
            )
            
            db.session.add(account)
            db.session.commit()
            
            # تسجيل حركة الإنشاء
            record_audit_log('create', 'accounts', account.id, None, account_data)
            
            return {'success': True, 'account_id': account.id, 'message': 'تم إنشاء الحساب بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating account: {e}")
            return {'success': False, 'message': f'خطأ في إنشاء الحساب: {str(e)}'}
    
    @staticmethod
    def create_transaction(transaction_data, user_id):
        """إنشاء حركة مالية"""
        try:
            # التحقق من صحة الحساب
            account = Account.query.get(transaction_data['account_id'])
            if not account:
                return {'success': False, 'message': 'الحساب غير موجود'}
            
            # توليد رقم الحركة
            last_trans = Transaction.query.order_by(Transaction.id.desc()).first()
            trans_number = f"TRN-{datetime.now().strftime('%Y%m%d')}-{(last_trans.id + 1) if last_trans else 1:04d}"
            
            transaction = Transaction(
                transaction_number=trans_number,
                transaction_date=datetime.strptime(transaction_data['transaction_date'], '%Y-%m-%d').date(),
                description=transaction_data['description'],
                transaction_type=transaction_data['transaction_type'],
                amount=Decimal(transaction_data['amount']).quantize(Decimal('0.01')),
                currency=transaction_data.get('currency', 'SAR'),
                account_id=transaction_data['account_id'],
                reference_type=transaction_data.get('reference_type'),
                reference_id=transaction_data.get('reference_id'),
                reference_number=transaction_data.get('reference_number'),
                status='active',
                created_by=user_id
            )
            
            # تحديث رصيد الحساب
            if transaction_data['transaction_type'] == 'debit':
                account.balance += Decimal(transaction_data['amount'])
            else:  # credit
                account.balance -= Decimal(transaction_data['amount'])
            
            db.session.add(transaction)
            db.session.commit()
            
            # تسجيل الحركة
            record_audit_log('create', 'transactions', transaction.id, None, transaction_data)
            
            return {'success': True, 'transaction_id': transaction.id, 'message': 'تم إنشاء الحركة بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating transaction: {e}")
            return {'success': False, 'message': f'خطأ في إنشاء الحركة: {str(e)}'}
    
    @staticmethod
    def create_journal_entry(journal_data, user_id):
        """إنشاء قيد يومية"""
        try:
            # التحقق من توازن القيد
            total_debit = sum(Decimal(line['debit']) for line in journal_data['lines'])
            total_credit = sum(Decimal(line['credit']) for line in journal_data['lines'])
            
            if abs(total_debit - total_credit) > Decimal('0.01'):
                return {'success': False, 'message': 'القيد غير متوازن. مجموع المدين يجب يساوي مجموع الدائن'}
            
            # توليد رقم القيد
            last_journal = JournalEntry.query.order_by(JournalEntry.id.desc()).first()
            journal_number = f"JRN-{datetime.now().strftime('%Y%m%d')}-{(last_journal.id + 1) if last_journal else 1:04d}"
            
            journal = JournalEntry(
                journal_number=journal_number,
                journal_date=datetime.strptime(journal_data['journal_date'], '%Y-%m-%d').date(),
                description=journal_data['description'],
                total_debit=total_debit,
                total_credit=total_credit,
                currency=journal_data.get('currency', 'SAR'),
                status='draft',
                notes=journal_data.get('notes'),
                created_by=user_id
            )
            
            db.session.add(journal)
            db.session.flush()  # للحصول على journal.id
            
            # إضافة بنود القيد
            for i, line_data in enumerate(journal_data['lines'], 1):
                line = JournalLine(
                    journal_id=journal.id,
                    account_id=line_data['account_id'],
                    debit=Decimal(line_data['debit']).quantize(Decimal('0.01')),
                    credit=Decimal(line_data['credit']).quantize(Decimal('0.01')),
                    description=line_data.get('description', ''),
                    line_number=i
                )
                db.session.add(line)
            
            db.session.commit()
            
            # تسجيل الحركة
            record_audit_log('create', 'journal_entries', journal.id, None, journal_data)
            
            return {'success': True, 'journal_id': journal.id, 'message': 'تم إنشاء القيد بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating journal entry: {e}")
            return {'success': False, 'message': f'خطأ في إنشاء القيد: {str(e)}'}
    
    @staticmethod
    def post_journal_entry(journal_id, user_id):
        """ترحيل قيد يومية"""
        try:
            journal = JournalEntry.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': 'القيد غير موجود'}
            
            if journal.status != 'draft':
                return {'success': False, 'message': 'لا يمكن ترحيل قيد غير مسودة'}
            
            # ترحيل كل بند من بنود القيد
            for line in journal.lines:
                account = Account.query.get(line.account_id)
                if not account:
                    return {'success': False, 'message': f'الحساب {line.account_id} غير موجود'}
                
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
                    status='active',
                    created_by=user_id
                )
                db.session.add(transaction)
            
            # تحديث حالة القيد
            journal.status = 'posted'
            journal.posted_by = user_id
            journal.posted_at = datetime.utcnow()
            
            db.session.commit()
            
            # تسجيل الحركة
            record_audit_log('post', 'journal_entries', journal.id)
            
            return {'success': True, 'message': 'تم ترحيل القيد بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error posting journal entry: {e}")
            return {'success': False, 'message': f'خطأ في ترحيل القيد: {str(e)}'}
    
    @staticmethod
    def create_payment(payment_data, user_id):
        """إنشاء سند قبض أو صرف"""
        try:
            # توليد رقم السند
            last_payment = Payment.query.order_by(Payment.id.desc()).first()
            payment_number = f"PAY-{datetime.now().strftime('%Y%m%d')}-{(last_payment.id + 1) if last_payment else 1:04d}"
            
            payment = Payment(
                payment_number=payment_number,
                payment_date=datetime.strptime(payment_data['payment_date'], '%Y-%m-%d').date(),
                payment_type=payment_data['payment_type'],
                amount=Decimal(payment_data['amount']).quantize(Decimal('0.01')),
                currency=payment_data.get('currency', 'SAR'),
                payment_method=payment_data['payment_method'],
                bank_account=payment_data.get('bank_account'),
                cheque_number=payment_data.get('cheque_number'),
                cheque_date=datetime.strptime(payment_data['cheque_date'], '%Y-%m-%d').date() if payment_data.get('cheque_date') else None,
                description=payment_data.get('description'),
                customer_id=payment_data.get('customer_id'),
                supplier_id=payment_data.get('supplier_id'),
                invoice_id=payment_data.get('invoice_id'),
                account_id=payment_data.get('account_id'),
                status='completed',
                notes=payment_data.get('notes'),
                created_by=user_id
            )
            
            db.session.add(payment)
            
            # تحديث رصيد الحساب المالي
            if payment_data['account_id']:
                account = Account.query.get(payment_data['account_id'])
                if payment_data['payment_type'] == 'receipt':  # سند قبض
                    account.balance += Decimal(payment_data['amount'])
                else:  # سند صرف
                    account.balance -= Decimal(payment_data['amount'])
            
            # تحديث رصيد العميل/المورد
            if payment_data.get('customer_id'):
                customer = Customer.query.get(payment_data['customer_id'])
                if payment_data['payment_type'] == 'receipt':  # قبض من عميل
                    customer.current_balance -= Decimal(payment_data['amount'])
                else:  # إعادة للعميل
                    customer.current_balance += Decimal(payment_data['amount'])
            
            elif payment_data.get('supplier_id'):
                supplier = Supplier.query.get(payment_data['supplier_id'])
                if payment_data['payment_type'] == 'payment':  # دفعة لمورد
                    supplier.current_balance -= Decimal(payment_data['amount'])
                else:  # إرجاع من مورد
                    supplier.current_balance += Decimal(payment_data['amount'])
            
            # تحديث الفاتورة إذا كانت مرتبطة
            if payment_data.get('invoice_id'):
                invoice = Invoice.query.get(payment_data['invoice_id'])
                invoice.paid_amount += Decimal(payment_data['amount'])
                invoice.remaining_amount = invoice.net_amount - invoice.paid_amount
                
                if invoice.remaining_amount <= Decimal('0.01'):
                    invoice.status = 'paid'
                elif invoice.paid_amount > Decimal('0'):
                    invoice.status = 'partially_paid'
            
            db.session.commit()
            
            # تسجيل الحركة
            record_audit_log('create', 'payments', payment.id, None, payment_data)
            
            return {'success': True, 'payment_id': payment.id, 'message': 'تم إنشاء السند بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating payment: {e}")
            return {'success': False, 'message': f'خطأ في إنشاء السند: {str(e)}'}

class FinancialReports:
    """التقارير المالية"""
    
    @staticmethod
    def get_trial_balance(start_date, end_date):
        """ميزان المراجعة"""
        try:
            # جلب جميع الحسابات
            accounts = Account.query.filter_by(is_active=True).all()
            
            trial_balance = []
            total_debit = Decimal('0')
            total_credit = Decimal('0')
            
            for account in accounts:
                # حساب مجموع المدين للفترة
                debit_sum = db.session.query(db.func.sum(Transaction.amount)).filter(
                    Transaction.account_id == account.id,
                    Transaction.transaction_type == 'debit',
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                    Transaction.status == 'active'
                ).scalar() or Decimal('0')
                
                # حساب مجموع الدائن للفترة
                credit_sum = db.session.query(db.func.sum(Transaction.amount)).filter(
                    Transaction.account_id == account.id,
                    Transaction.transaction_type == 'credit',
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                    Transaction.status == 'active'
                ).scalar() or Decimal('0')
                
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
            
            return {
                'success': True,
                'data': trial_balance,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'is_balanced': total_debit == total_credit
            }
            
        except Exception as e:
            logger.error(f"Error generating trial balance: {e}")
            return {'success': False, 'message': f'خطأ في توليد ميزان المراجعة: {str(e)}'}
    
    @staticmethod
    def get_balance_sheet(as_of_date):
        """الميزانية العمومية"""
        try:
            # حساب الأصول
            asset_accounts = Account.query.filter_by(account_type='asset', is_active=True).all()
            assets_total = Decimal('0')
            assets = []
            
            for account in asset_accounts:
                balance = AccountingSystem.get_account_balance(account.id, as_of_date)
                if balance != 0:
                    assets.append({
                        'code': account.code,
                        'name': account.name,
                        'balance': balance
                    })
                    assets_total += balance
            
            # حساب الخصوم
            liability_accounts = Account.query.filter_by(account_type='liability', is_active=True).all()
            liabilities_total = Decimal('0')
            liabilities = []
            
            for account in liability_accounts:
                balance = AccountingSystem.get_account_balance(account.id, as_of_date)
                if balance != 0:
                    liabilities.append({
                        'code': account.code,
                        'name': account.name,
                        'balance': balance
                    })
                    liabilities_total += balance
            
            # حساب حقوق الملكية
            equity_accounts = Account.query.filter_by(account_type='equity', is_active=True).all()
            equity_total = Decimal('0')
            equity = []
            
            for account in equity_accounts:
                balance = AccountingSystem.get_account_balance(account.id, as_of_date)
                if balance != 0:
                    equity.append({
                        'code': account.code,
                        'name': account.name,
                        'balance': balance
                    })
                    equity_total += balance
            
            # حساب الأرباح والخسائر
            revenue_total = Decimal('0')
            expense_total = Decimal('0')
            
            revenue_accounts = Account.query.filter_by(account_type='revenue', is_active=True).all()
            for account in revenue_accounts:
                revenue_total += AccountingSystem.get_account_balance(account.id, as_of_date)
            
            expense_accounts = Account.query.filter_by(account_type='expense', is_active=True).all()
            for account in expense_accounts:
                expense_total += AccountingSystem.get_account_balance(account.id, as_of_date)
            
            net_income = revenue_total - expense_total
            
            # إضافة صافي الدخل إلى حقوق الملكية
            equity_total += net_income
            
            return {
                'success': True,
                'assets': {
                    'items': assets,
                    'total': assets_total
                },
                'liabilities': {
                    'items': liabilities,
                    'total': liabilities_total
                },
                'equity': {
                    'items': equity,
                    'total': equity_total,
                    'net_income': net_income
                },
                'total_liabilities_equity': liabilities_total + equity_total
            }
            
        except Exception as e:
            logger.error(f"Error generating balance sheet: {e}")
            return {'success': False, 'message': f'خطأ في توليد الميزانية العمومية: {str(e)}'}
    
    @staticmethod
    def get_income_statement(start_date, end_date):
        """قائمة الدخل"""
        try:
            # حساب الإيرادات
            revenue_accounts = Account.query.filter_by(account_type='revenue', is_active=True).all()
            revenues = []
            revenue_total = Decimal('0')
            
            for account in revenue_accounts:
                period_balance = AccountingSystem.get_account_period_balance(account.id, start_date, end_date)
                if period_balance != 0:
                    revenues.append({
                        'code': account.code,
                        'name': account.name,
                        'amount': period_balance
                    })
                    revenue_total += period_balance
            
            # حساب المصروفات
            expense_accounts = Account.query.filter_by(account_type='expense', is_active=True).all()
            expenses = []
            expense_total = Decimal('0')
            
            for account in expense_accounts:
                period_balance = AccountingSystem.get_account_period_balance(account.id, start_date, end_date)
                if period_balance != 0:
                    expenses.append({
                        'code': account.code,
                        'name': account.name,
                        'amount': period_balance
                    })
                    expense_total += period_balance
            
            # حساب صافي الدخل
            gross_profit = revenue_total
            net_income = revenue_total - expense_total
            
            return {
                'success': True,
                'revenues': {
                    'items': revenues,
                    'total': revenue_total
                },
                'expenses': {
                    'items': expenses,
                    'total': expense_total
                },
                'gross_profit': gross_profit,
                'net_income': net_income,
                'period': {
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating income statement: {e}")
            return {'success': False, 'message': f'خطأ في توليد قائمة الدخل: {str(e)}'}

class AccountingHelpers:
    """وظائف مساعدة للنظام المحاسبي"""
    
    @staticmethod
    def get_account_balance(account_id, as_of_date=None):
        """الحصول على رصيد حساب حتى تاريخ معين"""
        try:
            account = Account.query.get(account_id)
            if not account:
                return Decimal('0')
            
            # الرصيد الافتتاحي
            balance = account.opening_balance
            
            # جمع الحركات حتى التاريخ المحدد
            query = Transaction.query.filter_by(account_id=account_id, status='active')
            
            if as_of_date:
                query = query.filter(Transaction.transaction_date <= as_of_date)
            
            transactions = query.all()
            
            for trans in transactions:
                if trans.transaction_type == 'debit':
                    balance += trans.amount
                else:  # credit
                    balance -= trans.amount
            
            return balance.quantize(Decimal('0.01'))
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return Decimal('0')
    
    @staticmethod
    def get_account_period_balance(account_id, start_date, end_date):
        """الحصول على رصيد حساب لفترة معينة"""
        try:
            # جمع الحركات للفترة المحددة
            transactions = Transaction.query.filter(
                Transaction.account_id == account_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.status == 'active'
            ).all()
            
            period_balance = Decimal('0')
            
            for trans in transactions:
                if trans.transaction_type == 'debit':
                    period_balance += trans.amount
                else:  # credit
                    period_balance -= trans.amount
            
            return period_balance.quantize(Decimal('0.01'))
            
        except Exception as e:
            logger.error(f"Error getting period balance: {e}")
            return Decimal('0')
    
    @staticmethod
    def validate_accounting_equation():
        """التحقق من معادلة المحاسبة"""
        try:
            # جمع أرصدة كل نوع من الحسابات
            asset_total = Decimal('0')
            liability_total = Decimal('0')
            equity_total = Decimal('0')
            revenue_total = Decimal('0')
            expense_total = Decimal('0')
            
            accounts = Account.query.filter_by(is_active=True).all()
            
            for account in accounts:
                balance = AccountingHelpers.get_account_balance(account.id)
                
                if account.account_type == 'asset':
                    asset_total += balance
                elif account.account_type == 'liability':
                    liability_total += balance
                elif account.account_type == 'equity':
                    equity_total += balance
                elif account.account_type == 'revenue':
                    revenue_total += balance
                elif account.account_type == 'expense':
                    expense_total += balance
            
            # حساب صافي الدخل
            net_income = revenue_total - expense_total
            
            # التحقق من المعادلة: الأصول = الخصوم + حقوق الملكية + صافي الدخل
            left_side = asset_total
            right_side = liability_total + equity_total + net_income
            
            is_valid = abs(left_side - right_side) < Decimal('0.01')
            
            return {
                'success': True,
                'is_valid': is_valid,
                'equation': {
                    'assets': asset_total,
                    'liabilities': liability_total,
                    'equity': equity_total,
                    'net_income': net_income,
                    'left_side': left_side,
                    'right_side': right_side,
                    'difference': left_side - right_side
                }
            }
            
        except Exception as e:
            logger.error(f"Error validating accounting equation: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def generate_account_statement(account_id, start_date, end_date):
        """كشف حساب مفصل"""
        try:
            account = Account.query.get(account_id)
            if not account:
                return {'success': False, 'message': 'الحساب غير موجود'}
            
            # الرصيد الافتتاحي
            opening_balance = AccountingHelpers.get_account_balance(account_id, start_date - timedelta(days=1))
            
            # الحركات خلال الفترة
            transactions = Transaction.query.filter(
                Transaction.account_id == account_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.status == 'active'
            ).order_by(Transaction.transaction_date, Transaction.id).all()
            
            statement_lines = []
            running_balance = opening_balance
            
            for trans in transactions:
                if trans.transaction_type == 'debit':
                    running_balance += trans.amount
                else:  # credit
                    running_balance -= trans.amount
                
                statement_lines.append({
                    'date': trans.transaction_date.strftime('%Y-%m-%d'),
                    'description': trans.description,
                    'reference': trans.reference_number,
                    'debit': trans.amount if trans.transaction_type == 'debit' else Decimal('0'),
                    'credit': trans.amount if trans.transaction_type == 'credit' else Decimal('0'),
                    'balance': running_balance
                })
            
            return {
                'success': True,
                'account': {
                    'code': account.code,
                    'name': account.name,
                    'type': account.account_type
                },
                'period': {
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                },
                'opening_balance': opening_balance,
                'closing_balance': running_balance,
                'transactions': statement_lines
            }
            
        except Exception as e:
            logger.error(f"Error generating account statement: {e}")
            return {'success': False, 'message': f'خطأ في توليد كشف الحساب: {str(e)}'}
