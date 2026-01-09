"""
نظام المصادقة والأذونات
"""

from functools import wraps
from flask import request, jsonify, session, flash, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash
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
    
    # إضافة مرشحات قالب للتحقق من الصلاحيات
    @app.context_processor
    def utility_processor():
        def has_permission(permission):
            return check_permission(permission)
        return dict(has_permission=has_permission, current_user=current_user)

def check_permission(permission):
    """التحقق من صلاحية المستخدم"""
    if not current_user.is_authenticated:
        return False
        # ربط الصلاحيات بالأدوار
    role_permissions = {
        'admin': ['view', 'create', 'edit', 'delete', 'approve', 'report', 'config', 'users'],
        'accountant': ['view', 'create', 'edit', 'report', 'approve'],
        'auditor': ['view', 'report'],
        'user': ['view']
    }
    
    user_role = current_user.role
    if user_role in role_permissions and permission in role_permissions[user_role]:
        return True
    
    return False

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

# تعريف واجهات API للمصادقة
def register_auth_routes(app):
    """تسجيل مسارات نظام المصادقة"""
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """تسجيل الدخول"""
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            remember = request.form.get('remember', False)
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                if not user.is_active:
                    flash('الحساب غير نشط. الرجاء التواصل مع المدير', 'error')
                    return redirect(url_for('login'))
                
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                # تسجيل حركة الدخول
                record_audit_log('login')
                
                flash(f'مرحباً بعودتك، {user.full_name}!', 'success')
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('main.dashboard'))
            else:
                flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
        
        return render_template('auth/login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """تسجيل الخروج"""
        # تسجيل حركة الخروج
        record_audit_log('logout')
        
        logout_user()
        flash('تم تسجيل الخروج بنجاح', 'success')
        return redirect(url_for('login'))
    
    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        """عرض وتعديل الملف الشخصي"""
        if request.method == 'POST':
            user = current_user
            old_data = {
                'full_name': user.full_name,
                'email': user.email,
                'phone': user.phone,
                'department': user.department
            }
            
            user.full_name = request.form.get('full_name', user.full_name)
            user.email = request.form.get('email', user.email)
            user.phone = request.form.get('phone', user.phone)
            user.department = request.form.get('department', user.department)
            
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password and confirm_password:
                if new_password == confirm_password:
                    user.set_password(new_password)
                    flash('تم تحديث كلمة المرور بنجاح', 'success')
                else:
                    flash('كلمات المرور غير متطابقة', 'error')
            
            db.session.commit()
            
            # تسجيل حركة التعديل
            new_data = {
                'full_name': user.full_name,
                'email': user.email,
                'phone': user.phone,
                'department': user.department
            }
            record_audit_log('update', 'users', user.id, old_data, new_data)
            
            flash('تم تحديث الملف الشخصي بنجاح', 'success')
            return redirect(url_for('profile'))
        
        return render_template('auth/profile.html', user=current_user)
    
    @app.route('/change_password', methods=['POST'])
    @login_required
    def change_password():
        """تغيير كلمة المرور"""
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(old_password):
            return jsonify({'success': False, 'message': 'كلمة المرور القديمة غير صحيحة'})
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'كلمات المرور غير متطابقة'})
        
        current_user.set_password(new_password)
        db.session.commit()
        
        # تسجيل حركة تغيير كلمة المرور
        record_audit_log('change_password', 'users', current_user.id)
        
        return jsonify({'success': True, 'message': 'تم تغيير كلمة المرور بنجاح'})
    
    return app

# وظائف مساعدة للمصادقة
def get_current_user_id():
    """الحصول على معرف المستخدم الحالي"""
    return current_user.id if current_user.is_authenticated else None

def get_current_user_role():
    """الحصول على دور المستخدم الحالي"""
    return current_user.role if current_user.is_authenticated else None

def is_admin():
    """التحقق إذا كان المستخدم مدير"""
    return current_user.is_authenticated and current_user.role == 'admin'

def is_accountant():
    """التحقق إذا كان المستخدم محاسب"""
    return current_user.is_authenticated and current_user.role in ['admin', 'accountant']

def require_admin():
    """فرض صلاحية المدير"""
    if not is_admin():
        flash('غير مصرح لك بالوصول لهذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    return True

def require_accountant():
    """فرض صلاحية المحاسب"""
    if not is_accountant():
        flash('غير مصرح لك بالوصول لهذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    return True
