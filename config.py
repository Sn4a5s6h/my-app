import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # إعدادات أساسية
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secure-secret-key-123'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///accounting_system.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }

    # إعدادات الجلسة
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # إعدادات النظام المحاسبي
    CURRENCY = 'SAR'
    TAX_RATE = 15.0
    COMPANY_NAME = os.environ.get('COMPANY_NAME') or 'شركتك المحدودة'
    COMPANY_VAT = os.environ.get('COMPANY_VAT') or '123456789101112'
    COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS') or 'العنوان التجاري'
    COMPANY_PHONE = os.environ.get('COMPANY_PHONE') or '+966500000000'
    COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL') or 'info@company.com'

    # إعدادات الملفات
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'csv'}

    # إعدادات التطبيق
    DEBUG = os.environ.get('FLASK_ENV') != 'production'
    HOST = os.environ.get('HOST') or '0.0.0.0'
    PORT = int(os.environ.get('PORT') or 5000)

    # إعدادات التقارير
    REPORT_DATE_FORMAT = '%Y-%m-%d'
    REPORT_TIME_FORMAT = '%H:%M:%S'

    @staticmethod
    def init_app(app):
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)

        # إعدادات إضافية للتطبيق
        app.config['JSON_SORT_KEYS'] = False
        app.config['JSON_AS_ASCII'] = False

config = Config()
