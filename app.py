from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from config import config
import os

# إنشاء التطبيق
app = Flask(__name__)
app.config.from_object(config)
config.init_app(app)

# إنشاء قاعدة البيانات
db = SQLAlchemy(app)

# -------------------------------
# نموذج مستخدم بسيط
# -------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# -------------------------------
# إنشاء قاعدة البيانات تلقائيًا
# -------------------------------
with app.app_context():
    try:
        db.create_all()
        print("✅ قاعدة البيانات جاهزة")
    except Exception as e:
        print("❌ خطأ في إنشاء قاعدة البيانات:", e)

# -------------------------------
# الصفحات الأساسية
# -------------------------------
@app.route('/')
@app.route('/dashboard')  # يمكن الوصول من كلا الرابطين
def dashboard():
    return render_template('index.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/products')
def products():
    return render_template('products.html')

# -------------------------------
# تسجيل مستخدم جديد
# -------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not username or not email or not password:
            flash("جميع الحقول مطلوبة", "danger")
            return redirect(url_for('register'))

        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash("تم إنشاء الحساب بنجاح", "success")
        return redirect(url_for('dashboard'))
    return render_template('auth/register.html')

# -------------------------------
# تسجيل الدخول
# -------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            flash(f"مرحبًا {user.username}", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("بيانات الدخول غير صحيحة", "danger")
    return render_template('auth/login.html')

# -------------------------------
# صفحة 404
# -------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# -------------------------------
# تشغيل التطبيق
# -------------------------------
if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
