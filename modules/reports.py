"""
نظام التقارير
"""

from datetime import datetime, date
from decimal import Decimal
import io
import logging

from flask import send_file, jsonify, request
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import arabic_reshaper
from bidi.algorithm import get_display

from flask_login import login_required
from modules.auth import permission_required

from database.models import (
    db, Invoice, Payment, Customer, Supplier,
    Transaction, Account, Product
)

from modules.accounting import FinancialReports
from modules.inventory import InventorySystem


# ================= LOGGER =================
logger = logging.getLogger(__name__)


# ==========================================================
#                     Report Generator
# ==========================================================
class ReportGenerator:

    @staticmethod
    def generate_customer_statement(customer_id, start_date, end_date):
        try:
            customer = Customer.query.get(customer_id)
            if not customer:
                return {'success': False, 'message': 'العميل غير موجود'}

            invoices = Invoice.query.filter(
                Invoice.customer_id == customer_id,
                Invoice.invoice_date >= start_date,
                Invoice.invoice_date <= end_date
            ).all()

            payments = Payment.query.filter(
                Payment.customer_id == customer_id,
                Payment.payment_date >= start_date,
                Payment.payment_date <= end_date
            ).all()

            transactions = []

            for inv in invoices:
                transactions.append({
                    'date': inv.invoice_date,
                    'desc': f'فاتورة {inv.invoice_number}',
                    'debit': inv.net_amount,
                    'credit': Decimal('0')
                })

            for pay in payments:
                transactions.append({
                    'date': pay.payment_date,
                    'desc': f'سند {pay.payment_number}',
                    'debit': Decimal('0'),
                    'credit': pay.amount
                })

            transactions.sort(key=lambda x: x['date'])

            balance = Decimal('0')
            rows = []

            for t in transactions:
                balance += t['debit'] - t['credit']
                rows.append({
                    'date': t['date'].strftime('%Y-%m-%d'),
                    'description': t['desc'],
                    'debit': float(t['debit']),
                    'credit': float(t['credit']),
                    'balance': float(balance)
                })

            return {
                'success': True,
                'customer': customer.customer_name,
                'transactions': rows,
                'closing_balance': float(balance)
            }

        except Exception as e:
            logger.error(e)
            return {'success': False, 'message': str(e)}


# ==========================================================
#                   PDF Report Generator
# ==========================================================
class PDFReportGenerator:

    @staticmethod
    def reshape_arabic(text):
        if not text:
            return ''
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)

    @staticmethod
    def generate_pdf_balance_sheet(as_of_date):
        try:
            report = FinancialReports.get_balance_sheet(as_of_date)
            if not report['success']:
                return None

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            story = []

            title = Paragraph(
                PDFReportGenerator.reshape_arabic('الميزانية العمومية'),
                styles['Heading1']
            )
            subtitle = Paragraph(
                PDFReportGenerator.reshape_arabic(
                    f'حتى تاريخ {as_of_date.strftime("%Y-%m-%d")}'
                ),
                styles['Heading2']
            )

            story.extend([title, subtitle, Spacer(1, 20)])

            table_data = [[
                PDFReportGenerator.reshape_arabic('البند'),
                PDFReportGenerator.reshape_arabic('المبلغ')
            ]]

            for item in report['assets']['items']:
                table_data.append([
                    PDFReportGenerator.reshape_arabic(item['name']),
                    f"{item['balance']:,.2f}"
                ])

            table = Table(table_data, colWidths=[400, 150])
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)
            ]))

            story.append(table)
            doc.build(story)

            buffer.seek(0)
            return buffer

        except Exception as e:
            logger.error(f"PDF balance sheet error: {e}")
            return None


# ==========================================================
#                   Excel Report Generator
# ==========================================================
class ExcelReportGenerator:

    @staticmethod
    def generate_excel_trial_balance(start_date, end_date):
        try:
            report = FinancialReports.get_trial_balance(start_date, end_date)
            if not report['success']:
                return None

            df = pd.DataFrame(report['data'])
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='ميزان المراجعة')

            output.seek(0)
            return output

        except Exception as e:
            logger.error(e)
            return None


# ==========================================================
#                       API ROUTES
# ==========================================================
def register_report_routes(app):

    @app.route('/api/reports/balance-sheet/<date>')
    @login_required
    @permission_required('report')
    def get_balance_sheet(date):
        try:
            d = datetime.strptime(date, '%Y-%m-%d').date()
            return jsonify(FinancialReports.get_balance_sheet(d))
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    @app.route('/api/reports/export/pdf/balance-sheet/<date>')
    @login_required
    @permission_required('report')
    def export_balance_sheet_pdf(date):
        try:
            d = datetime.strptime(date, '%Y-%m-%d').date()
            pdf = PDFReportGenerator.generate_pdf_balance_sheet(d)

            if not pdf:
                return jsonify({'success': False, 'message': 'فشل توليد PDF'}), 500

            return send_file(
                pdf,
                as_attachment=True,
                download_name=f'balance_sheet_{date}.pdf',
                mimetype='application/pdf'
            )

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    return app
