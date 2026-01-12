from functools import wraps
from flask import (
    request,
    jsonify,
    session,
    flash,
    redirect,
    url_for,
    render_template  # ✅ الإضافة الوحيدة
)
from flask_login import (
    LoginManager, login_user,
    logout_user,
    current_user,
    login_required
)
from werkzeug.security import check_password_hash, generate_password_hash
import logging
from datetime import datetime

from database.models import db, User, AuditLog
from config import config

# إعدادات تسجيل الدخول
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'الرجاء تسجيل الدخول للوصول إلى هذه الصفحة'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    """تحميل المستخدم من قاعدة البيانات"""
    return User.query.get(int(user_id))


def init_auth(app):
    """تهيئة نظام المصادقة"""
    login_manager.init_app(app)

    # إنشاء المستخدم الافتراضي عند بدء التطبيق
    with app.app_context():
        create_default_user()

    @app.context_processor
    def utility_processor():
        def has_permission(permission):
            return check_permission(permission)
        return dict(has_permission=has_permission, current_user=current_user)


def create_default_user():
    """إنشاء المستخدم الافتراضي عند بدء التطبيق إذا لم يكن موجودًا"""
    default_username = '1'
    default_password = '1'

    # تحقق من وجود المستخدم
    user = User.query.filter_by(username=default_username).first()

    # إذا لم يكن موجودًا، يتم إنشاؤه
    if not user:
        user = User(username=default_username, email='user1@example.com')
        user.set_password(default_password)
        db.session.add(user)
        db.session.commit()
        print(f"تم إنشاء المستخدم الافتراضي: {default_username}")


def check_permission(permission):
    """التحقق من صلاحية المستخدم"""
    if not current_user.is_authenticated:
        return False

    role_permissions = {
        'admin': ['view', 'create', 'edit', 'delete', 'approve', 'report', 'config', 'users'],
        'accountant': ['view', 'create', 'edit', 'report', 'approve'],
        'auditor': ['view', 'report'],
        'user': ['view']
    }
    user_role = current_user.role
    return user_role in role_permissions and permission in role_permissions[user_role]


def permission_required(permission):
    """ديكورات للتحقق من الصلاحيات"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            if not check_permission(permission):
                flash('غير مصرح لك بالوصول لهذه الصفحة', 'error')
                return redirect(url_for('main.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """ديكورات للتحقق من صلاحيات المدير"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        if current_user.role != 'admin':
            flash('غير مصرح لك بالوصول لهذه الصفحة', 'error')
            return redirect(url_for('main.dashboard'))

        return f(*args, **kwargs)
    return decorated_function


def record_audit_log(action, table_name=None, record_id=None, old_values=None, new_values=None):
    """تسجيل حركة في سجل التدقيق"""
    try:
        audit_log = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=str(old_values) if old_values else None,
            new_values=str(new_values) if new_values else None,
            ip_address=request.remote_addr if request else None,
            user_agent=request.user_agent.string if request and request.user_agent else None
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        logging.error(f"Error recording audit log: {e}")


def register_auth_routes(app):
    """تسجيل مسارات نظام المصادقة"""
    
    # **تأكد من أن هذا المسار مسجل داخل blueprint**
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """تسجيل مستخدم جديد"""
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))

        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # التحقق من أن كلمة المرور و تأكيد كلمة المرور متطابقتان
            if password != confirm_password:
                flash('كلمات المرور غير متطابقة', 'error')
                return redirect(url_for('auth.register'))

            # التحقق من أن البريد الإلكتروني أو اسم المستخدم غير موجود مسبقًا
            user = User.query.filter_by(email=email).first()
            if user:
                flash('البريد الإلكتروني مسجل بالفعل', 'error')
                return redirect(url_for('auth.register'))

            new_user = User(username=username, email=email)
            new_user.set_password(password)

            # إضافة المستخدم إلى قاعدة البيانات
            db.session.add(new_user)
            db.session.commit()

            flash('تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول', 'success')
            return redirect(url_for('auth.login'))

        return render_template('auth/register.html')

    return app


def get_current_user_id():
    return current_user.id if current_user.is_authenticated else None


def get_current_user_role():
    return current_user.role if current_user.is_authenticated else None


def require_accountant():
    """فرض صلاحية المحاسب"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if current_user.role not in ['admin', 'accountant']:
        flash('غير مصرح لك بالوصول لهذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

    return True
