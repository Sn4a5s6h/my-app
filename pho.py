from flask import Flask, render_template, request, jsonify, session
import requests
import math
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
import io
import base64
from datetime import datetime
import os
import random
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-123')

# مفتاح API لـ OpenCelliD
API_KEY = os.environ.get('API_KEY', '9b87939627d2445949f2')

# قاعدة بيانات محاكاة (في التطبيق الحقيقي ستكون قاعدة بيانات حقيقية)
users_db = {
    # تخزين مؤقت للمستخدمين المسجلين
}

# قاعدة بيانات أرقام الهواتف ومحاكاة مواقعهم
phones_db = {
    '0501234567': {'lat': 15.3694, 'lon': 44.1910, 'last_seen': '2024-01-20T10:30:00', 'carrier': 'STC'},
    '0559876543': {'lat': 15.3522, 'lon': 44.2065, 'last_seen': '2024-01-20T11:15:00', 'carrier': 'Yemen Mobile'},
    '0541122334': {'lat': 15.3589, 'lon': 44.2155, 'last_seen': '2024-01-20T09:45:00', 'carrier': 'Sabafon'},
    '0505556667': {'lat': 15.3410, 'lon': 44.1980, 'last_seen': '2024-01-20T12:20:00', 'carrier': 'MTN'},
}

# أبراج افتراضية للشركات اليمنية
yemen_towers = {
    'STC': [
        {'id': 'stc_001', 'lat': 15.3694, 'lon': 44.1910, 'name': 'برج STC الرئيسي - صنعاء'},
        {'id': 'stc_002', 'lat': 15.3522, 'lon': 44.2065, 'name': 'برج STC الفرعي'},
    ],
    'Yemen Mobile': [
        {'id': 'ym_001', 'lat': 15.3589, 'lon': 44.2155, 'name': 'برج يمن موبايل المركزي'},
        {'id': 'ym_002', 'lat': 15.3410, 'lon': 44.1980, 'name': 'برج يمن موبايل الغربي'},
    ],
    'Sabafon': [
        {'id': 'sab_001', 'lat': 15.3650, 'lon': 44.2000, 'name': 'برج صابافون الشمالي'},
        {'id': 'sab_002', 'lat': 15.3500, 'lon': 44.1950, 'name': 'برج صابافون الجنوبي'},
    ],
    'MTN': [
        {'id': 'mtn_001', 'lat': 15.3550, 'lon': 44.2100, 'name': 'برج MTN الشرقي'},
        {'id': 'mtn_002', 'lat': 15.3600, 'lon': 44.1850, 'name': 'برج MTN الغربي'},
    ]
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # في التطبيق الحقيقي، تحقق من قاعدة البيانات
        if username == 'admin' and password == 'admin123':
            session['user_id'] = 1
            session['username'] = username
            session['role'] = 'admin'
            return jsonify({'success': True, 'message': 'تم تسجيل الدخول بنجاح'})
        
        return jsonify({'success': False, 'message': 'بيانات الدخول غير صحيحة'})
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/search', methods=['POST'])
def search_phone():
    """البحث عن رقم هاتف وتحديد موقعه"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'يجب تسجيل الدخول أولاً'}), 401
    
    try:
        data = request.json
        phone_number = data.get('phone_number', '').strip()
        
        # تنظيف رقم الهاتف
        phone_number = re.sub(r'\D', '', phone_number)  # إزالة كل ما ليس رقم
        
        if not phone_number:
            return jsonify({'success': False, 'message': 'يرجى إدخال رقم هاتف صحيح'}), 400
        
        if len(phone_number) < 9:
            return jsonify({'success': False, 'message': 'رقم الهاتف قصير جداً'}), 400
        
        print(f"🔍 البحث عن رقم: {phone_number}")
        
        # محاكاة تحديد شركة الاتصالات بناءً على الرقم
        carrier = determine_carrier(phone_number)
        
        # التحقق مما إذا كان الرقم موجوداً في قاعدة البيانات
        if phone_number in phones_db:
            # الرقم معروف - استخدام موقعه المخزن
            phone_data = phones_db[phone_number]
            lat, lon = phone_data['lat'], phone_data['lon']
            is_simulated = False
        else:
            # الرقم جديد - إنشاء موقع عشوائي في اليمن
            lat, lon = generate_random_location_in_yemen()
            phones_db[phone_number] = {
                'lat': lat,
                'lon': lon,
                'last_seen': datetime.utcnow().isoformat(),
                'carrier': carrier
            }
            is_simulated = True
        
        # الحصول على أبراج الشركة
        company_towers = yemen_towers.get(carrier, [])
        
        # إضافة أبراج عشوائية أخرى للتنوع
        all_towers = company_towers.copy()
        other_carriers = [c for c in yemen_towers.keys() if c != carrier]
        if other_carriers:
            random_carrier = random.choice(other_carriers)
            all_towers.extend(random.sample(yemen_towers[random_carrier], 1))
        
        # محاكاة قوة الإشارة من كل برج
        towers_with_signal = []
        for tower in all_towers:
            distance = calculate_distance(lat, lon, tower['lat'], tower['lon'])
            signal_strength = calculate_signal_strength(distance)
            
            towers_with_signal.append({
                'id': tower['id'],
                'name': tower['name'],
                'lat': tower['lat'],
                'lon': tower['lon'],
                'distance_km': round(distance, 2),
                'signal_strength': signal_strength,
                'signal_percentage': min(100, max(0, signal_strength + 100)),
                'carrier': carrier if tower in company_towers else random_carrier
            })
        
        # ترتيب الأبراج حسب قوة الإشارة
        towers_with_signal.sort(key=lambda x: x['signal_strength'], reverse=True)
        
        # تقدير الموقع باستخدام التثليث
        estimated_position = triangulate_location(towers_with_signal)
        
        # إنشاء خريطة
        map_image = generate_map(lat, lon, estimated_position, towers_with_signal, carrier)
        
        # تسجيل البحث
        log_search(session['user_id'], phone_number, lat, lon)
        
        # إعداد الاستجابة
        response_data = {
            'success': True,
            'phone_number': format_phone_number(phone_number),
            'carrier': carrier,
            'location': {
                'lat': lat,
                'lon': lon,
                'address': get_approximate_address(lat, lon)
            },
            'estimated_location': {
                'lat': estimated_position[0],
                'lon': estimated_position[1]
            },
            'accuracy_meters': random.randint(50, 500),
            'last_seen': phones_db.get(phone_number, {}).get('last_seen', datetime.utcnow().isoformat()),
            'towers': towers_with_signal[:5],  # أول 5 أبراج فقط
            'map_image': map_image,
            'is_simulated': is_simulated,
            'status': 'active',
            'battery_level': f"{random.randint(20, 100)}%",
            'network_type': '4G' if random.random() > 0.3 else '3G'
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ خطأ في البحث: {e}")
        return jsonify({'success': False, 'message': f'خطأ في البحث: {str(e)}'}), 500

@app.route('/api/phone_history/<phone_number>')
def phone_history(phone_number):
    """الحصول على سجل مواقع الهاتف"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'يجب تسجيل الدخول أولاً'}), 401
    
    # محاكاة سجل المواقع
    history = []
    base_lat, base_lon = 15.3694, 44.1910  # صنعاء
    
    for i in range(10):
        history.append({
            'timestamp': (datetime.utcnow() - timedelta(hours=i*2)).isoformat(),
            'lat': base_lat + random.uniform(-0.01, 0.01),
            'lon': base_lon + random.uniform(-0.01, 0.01),
            'accuracy': random.randint(100, 1000)
        })
    
    return jsonify({'success': True, 'history': history})

@app.route('/api/carriers')
def get_carriers():
    """الحصول على قائمة شركات الاتصالات"""
    return jsonify({
        'success': True,
        'carriers': [
            {'code': 'STC', 'name': 'الاتصالات السعودية (STC)', 'color': '#FF0000'},
            {'code': 'Yemen Mobile', 'name': 'يمن موبايل', 'color': '#008000'},
            {'code': 'Sabafon', 'name': 'صابافون', 'color': '#FFA500'},
            {'code': 'MTN', 'name': 'إم تي إن', 'color': '#FFFF00'},
        ]
    })

# ========== دوال مساعدة ==========

def determine_carrier(phone_number):
    """تحديد شركة الاتصالات بناءً على رقم الهاتف"""
    prefixes = {
        '73': 'STC',
        '77': 'Yemen Mobile',
        '71': 'Sabafon',
        '70': 'MTN',
    }
    
    for prefix, carrier in prefixes.items():
        if phone_number.startswith(prefix):
            return carrier
    
    # افتراضي
    return random.choice(['STC', 'Yemen Mobile', 'Sabafon', 'MTN'])

def generate_random_location_in_yemen():
    """إنشاء موقع عشوائي داخل اليمن"""
    # حدود اليمن التقريبية
    yemen_bounds = {
        'min_lat': 12.5, 'max_lat': 19.0,
        'min_lon': 42.0, 'max_lon': 54.0
    }
    
    lat = random.uniform(yemen_bounds['min_lat'], yemen_bounds['max_lat'])
    lon = random.uniform(yemen_bounds['min_lon'], yemen_bounds['max_lon'])
    
    # تفضيل المناطق المأهولة
    cities = [
        (15.3694, 44.1910),  # صنعاء
        (12.7855, 45.0187),  # عدن
        (14.7978, 42.9545),  # الحديدة
        (13.5795, 44.0209),  # تعز
        (14.5566, 49.1246),  # المكلا
    ]
    
    if random.random() > 0.3:  # 70% من الوقت نستخدم مدينة
        city = random.choice(cities)
        lat = city[0] + random.uniform(-0.05, 0.05)
        lon = city[1] + random.uniform(-0.05, 0.05)
    
    return lat, lon

def calculate_distance(lat1, lon1, lat2, lon2):
    """حساب المسافة بين نقطتين (بالكيلومترات)"""
    R = 6371  # نصف قطر الأرض بالكيلومتر
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def calculate_signal_strength(distance_km):
    """حساب قوة الإشارة بناءً على المسافة"""
    # نموذج فقدان المسار
    if distance_km < 1:
        return random.uniform(-60, -70)  # إشارة قوية
    elif distance_km < 5:
        return random.uniform(-70, -85)  # إشارة متوسطة
    elif distance_km < 15:
        return random.uniform(-85, -100)  # إشارة ضعيفة
    else:
        return random.uniform(-100, -120)  # إشارة ضعيفة جداً

def triangulate_location(towers):
    """تثليث الموقع باستخدام أبراج متعددة"""
    if len(towers) < 3:
        # إذا كان لدينا أقل من 3 أبراج، نرجع متوسط موقع أقوى برجين
        strongest_towers = sorted(towers, key=lambda x: x['signal_strength'], reverse=True)[:2]
        avg_lat = sum(t['lat'] for t in strongest_towers) / len(strongest_towers)
        avg_lon = sum(t['lon'] for t in strongest_towers) / len(strongest_towers)
        return avg_lat, avg_lon
    
    # استخدام أقوى 3 أبراج للتثليث
    strongest_towers = sorted(towers, key=lambda x: x['signal_strength'], reverse=True)[:3]
    
    # محاكاة خوارزمية التثليث
    tower_positions = [(t['lat'], t['lon']) for t in strongest_towers]
    distances = [t['distance_km'] for t in strongest_towers]
    
    # متوسط المواقع مع تصحيح بناءً على المسافات
    weights = [1/(d+0.1) for d in distances]  # وزن عكسي مع المسافة
    
    weighted_lat = sum(pos[0] * w for pos, w in zip(tower_positions, weights)) / sum(weights)
    weighted_lon = sum(pos[1] * w for pos, w in zip(tower_positions, weights)) / sum(weights)
    
    # إضافة بعض العشوائية لمحاكاة عدم الدقة
    weighted_lat += random.uniform(-0.005, 0.005)
    weighted_lon += random.uniform(-0.005, 0.005)
    
    return weighted_lat, weighted_lon

def generate_map(actual_lat, actual_lon, estimated_lat, estimated_lon, towers, carrier):
    """إنشاء خريطة بصيغة Base64"""
    try:
        plt.figure(figsize=(12, 10))
        
        # رسم الأبراج
        colors = {'STC': 'red', 'Yemen Mobile': 'green', 'Sabafon': 'orange', 'MTN': 'yellow'}
        for tower in towers:
            color = colors.get(tower.get('carrier', carrier), 'blue')
            plt.scatter(tower['lon'], tower['lat'], 
                       c=color, s=150, marker='^', alpha=0.7,
                       label=f"{tower.get('carrier', 'برج')}" if tower == towers[0] else "")
        
        # رسم الموقع الفعلي
        plt.scatter(actual_lon, actual_lat, c='green', s=300, 
                   marker='o', label='الموقع الفعلي', edgecolors='black', linewidth=2)
        
        # رسم الموقع المقدر
        plt.scatter(estimated_lon, estimated_lat, c='red', s=300,
                   marker='X', label='الموقع المقدر', edgecolors='black', linewidth=2)
        
        # إضافة دوائر المسافة
        for tower in towers[:2]:  # أقوى برجين فقط
            circle = plt.Circle((tower['lon'], tower['lat']), tower['distance_km']/100,
                              color=colors.get(tower.get('carrier', carrier), 'blue'),
                              fill=False, linestyle='--', alpha=0.3)
            plt.gca().add_patch(circle)
        
        plt.xlabel('خط الطول', fontsize=12)
        plt.ylabel('خط العرض', fontsize=12)
        plt.title(f'تتبع رقم الهاتف - شركة: {carrier}', fontsize=16, fontweight='bold')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # حفظ الصورة
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        return image_base64
        
    except Exception as e:
        print(f"⚠️ خطأ في إنشاء الخريطة: {e}")
        return None

def get_approximate_address(lat, lon):
    """الحصول على عنوان تقريبي (محاكاة)"""
    # في التطبيق الحقيقي، استخدام Geocoding API
    locations = [
        "صنعاء، اليمن",
        "عدن، اليمن",
        "الحديدة، اليمن",
        "تعز، اليمن",
        "المكلا، اليمن",
        "إب، اليمن",
        "ذمار، اليمن"
    ]
    
    # محاكاة قرب المدينة
    return random.choice(locations)

def format_phone_number(phone_number):
    """تنسيق رقم الهاتف"""
    if len(phone_number) == 9:
        return f"+967{phone_number}"
    elif len(phone_number) == 10 and phone_number.startswith('0'):
        return f"+967{phone_number[1:]}"
    elif len(phone_number) == 12 and phone_number.startswith('967'):
        return f"+{phone_number}"
    else:
        return phone_number

def log_search(user_id, phone_number, lat, lon):
    """تسجيل عملية البحث"""
    timestamp = datetime.utcnow().isoformat()
    print(f"📝 تم تسجيل البحث: User={user_id}, Phone={phone_number}, Location=({lat}, {lon}), Time={timestamp}")

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Phone Tracking System',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')
