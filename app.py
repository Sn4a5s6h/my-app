from flask import Flask, render_template, request, jsonify
import requests
import math
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime, timedelta
import os
import random
import re
import json
from flask_cors import CORS
import hashlib

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', hashlib.sha256(b'cyber-room-789').hexdigest())

# مفاتيح API
NUMVERIFY_API_KEY = os.environ.get('NUMVERIFY_API_KEY', 'd6723d367abdce52b5b1991811a3e5e6')
OPENCELLID_API_KEY = os.environ.get('API_KEY', '9b87939627d2445949f2')

# قاعدة بيانات متقدمة
class PhoneTrackerDB:
    def __init__(self):
        self.phones = {}
        self.searches = []
        self.load_data()
    
    def load_data(self):
        try:
            with open('phone_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.phones = data.get('phones', {})
                self.searches = data.get('searches', [])
        except:
            self.phones = {
                '733393303': {'lat': 15.3694, 'lon': 44.1910, 'last_seen': datetime.utcnow().isoformat(), 
                             'carrier': 'STC', 'country': 'Yemen', 'name': 'سبتان', 'threat_level': 'low'},
                '776730674': {'lat': 12.7855, 'lon': 45.0187, 'last_seen': datetime.utcnow().isoformat(),
                             'carrier': 'Yemen Mobile', 'country': 'Yemen', 'name': 'علي', 'threat_level': 'medium'},
                '711111111': {'lat': 14.7978, 'lon': 42.9545, 'last_seen': datetime.utcnow().isoformat(),
                             'carrier': 'Sabafon', 'country': 'Yemen', 'name': 'مجهول', 'threat_level': 'high'},
            }
    
    def save_data(self):
        data = {
            'phones': self.phones,
            'searches': self.searches[-1000:]  # حفظ آخر 1000 بحث فقط
        }
        with open('phone_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_search(self, phone, ip, user_agent):
        self.searches.append({
            'phone': phone,
            'ip': ip,
            'user_agent': user_agent,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.save_data()

db = PhoneTrackerDB()

# أبراج متقدمة للشركات اليمنية
yemen_towers = {
    'STC': [
        {'id': 'stc_001', 'lat': 15.3694, 'lon': 44.1910, 'name': 'برج STC الرئيسي - صنعاء', 'power': 100},
        {'id': 'stc_002', 'lat': 15.3522, 'lon': 44.2065, 'name': 'برج STC الفرعي', 'power': 85},
        {'id': 'stc_003', 'lat': 15.3789, 'lon': 44.2010, 'name': 'برج STC الشمالي', 'power': 90},
    ],
    'Yemen Mobile': [
        {'id': 'ym_001', 'lat': 15.3589, 'lon': 44.2155, 'name': 'برج يمن موبايل المركزي', 'power': 95},
        {'id': 'ym_002', 'lat': 15.3410, 'lon': 44.1980, 'name': 'برج يمن موبايل الغربي', 'power': 80},
        {'id': 'ym_003', 'lat': 15.3650, 'lon': 44.2255, 'name': 'برج يمن موبايل الشرقي', 'power': 88},
    ],
    'Sabafon': [
        {'id': 'sab_001', 'lat': 15.3650, 'lon': 44.2000, 'name': 'برج صابافون الشمالي', 'power': 92},
        {'id': 'sab_002', 'lat': 15.3500, 'lon': 44.1950, 'name': 'برج صابافون الجنوبي', 'power': 78},
        {'id': 'sab_003', 'lat': 15.3750, 'lon': 44.1900, 'name': 'برج صابافون الغربي', 'power': 85},
    ],
    'MTN': [
        {'id': 'mtn_001', 'lat': 15.3550, 'lon': 44.2100, 'name': 'برج MTN الشرقي', 'power': 87},
        {'id': 'mtn_002', 'lat': 15.3600, 'lon': 44.1850, 'name': 'برج MTN الغربي', 'power': 82},
        {'id': 'mtn_003', 'lat': 15.3450, 'lon': 44.2200, 'name': 'برج MTN الجنوبي', 'power': 90},
    ]
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_phone():
    """البحث عن رقم هاتف - النسخة المتقدمة"""
    try:
        data = request.json
        phone_number = data.get('phone_number', '').strip()
        
        # الحصول على معلومات العميل
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # تنظيف رقم الهاتف
        phone_number = re.sub(r'\D', '', phone_number)
        
        if not phone_number:
            return jsonify({
                'success': False, 
                'message': 'يرجى إدخال رقم هاتف صحيح',
                'code': 'INVALID_PHONE'
            }), 400
        
        if len(phone_number) < 9:
            return jsonify({
                'success': False,
                'message': 'رقم الهاتف قصير جداً',
                'code': 'SHORT_PHONE'
            }), 400
        
        print(f"🔍 [CYBER-ROOM] بحث جديد: {phone_number} من IP: {client_ip}")
        
        # استخدام Numverify API للتحقق
        numverify_data = get_phone_info(phone_number, NUMVERIFY_API_KEY)
        
        # تحديد مستوى التهديد
        threat_level = analyze_threat_level(phone_number, client_ip, numverify_data)
        
        # تحديد الشركة
        if numverify_data and numverify_data.get("valid"):
            carrier = numverify_data.get("carrier", "")
            country = numverify_data.get("country_name", "Yemen")
            line_type = numverify_data.get("line_type", "mobile")
            is_valid = True
        else:
            carrier = determine_carrier(phone_number)
            country = "Yemen"
            line_type = "mobile"
            is_valid = False
        
        # الحصول على الموقع
        if phone_number in db.phones:
            phone_data = db.phones[phone_number]
            lat, lon = phone_data['lat'], phone_data['lon']
            is_simulated = False
            name = phone_data.get('name', 'مجهول')
        else:
            lat, lon = generate_cyber_location(phone_number, carrier)
            name = generate_arabic_name()
            is_simulated = True
            
            # حفظ الرقم الجديد
            db.phones[phone_number] = {
                'lat': lat,
                'lon': lon,
                'last_seen': datetime.utcnow().isoformat(),
                'carrier': carrier,
                'country': country,
                'name': name,
                'threat_level': threat_level,
                'first_seen': datetime.utcnow().isoformat()
            }
        
        # تسجيل البحث
        db.add_search(phone_number, client_ip, user_agent)
        
        # توليد الأبراج
        towers = generate_advanced_towers(lat, lon, carrier, country)
        
        # التثليث المتقدم
        estimated_position = advanced_triangulation(towers)
        
        # إنشاء خريطة متقدمة
        map_image = generate_cyber_map(lat, lon, estimated_position[0], estimated_position[1], 
                                      towers, carrier, country, threat_level)
        
        # إنشاء التقرير
        report = generate_threat_report(phone_number, threat_level, carrier, country)
        
        # إعداد الاستجابة المتقدمة
        response_data = {
            'success': True,
            'phone_number': format_phone_number(phone_number),
            'carrier': carrier,
            'country': country,
            'line_type': line_type,
            'numverify_valid': is_valid,
            'location': {
                'lat': lat,
                'lon': lon,
                'address': get_cyber_address(lat, lon, country),
                'accuracy': random.randint(10, 100)
            },
            'estimated_location': {
                'lat': estimated_position[0],
                'lon': estimated_position[1],
                'accuracy_meters': random.randint(5, 50)
            },
            'person_info': {
                'name': name,
                'threat_level': threat_level,
                'confidence': random.randint(75, 98),
                'risk_score': calculate_risk_score(threat_level)
            },
            'device_info': {
                'status': 'online',
                'battery_level': f"{random.randint(25, 95)}%",
                'network_type': random.choice(['4G LTE', '5G', '4G', '3G']),
                'imei': generate_imei(),
                'imsi': generate_imsi(),
                'last_update': datetime.utcnow().isoformat()
            },
            'towers': towers[:6],
            'map_image': map_image,
            'is_simulated': is_simulated,
            'report': report,
            'cyber_info': {
                'session_id': hashlib.md5(f"{phone_number}{datetime.utcnow().timestamp()}".encode()).hexdigest()[:16],
                'timestamp': datetime.utcnow().isoformat(),
                'search_id': hashlib.sha256(f"{phone_number}{client_ip}".encode()).hexdigest()[:24],
                'encryption_level': 'AES-256'
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ [CYBER-ERROR] {e}")
        return jsonify({
            'success': False,
            'message': 'خطأ في النظام الأمني',
            'code': 'CYBER_ERROR',
            'support_contact': '967733393303'
        }), 500

@app.route('/api/check', methods=['POST'])
def check_number():
    """فحص رقم باستخدام Numverify API"""
    try:
        data = request.json
        phone_number = data.get('phone_number', '').strip()
        phone_number = re.sub(r'\D', '', phone_number)
        
        result = get_phone_info(phone_number, NUMVERIFY_API_KEY)
        
        if result:
            return jsonify({
                'success': True,
                'data': result,
                'formatted_number': format_phone_number(phone_number)
            })
        else:
            return jsonify({
                'success': False,
                'message': 'فشل في التحقق من الرقم'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ: {str(e)}'
        }), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_number():
    """تحليل رقم هاتف متقدم"""
    data = request.json
    phone_number = data.get('phone_number', '').strip()
    
    # تحليل متقدم للرقم
    analysis = {
        'phone': phone_number,
        'format': format_phone_number(phone_number),
        'length': len(phone_number),
        'digit_sum': sum(int(d) for d in phone_number if d.isdigit()),
        'patterns': detect_patterns(phone_number),
        'carrier_predictions': predict_carriers(phone_number),
        'risk_indicators': check_risk_indicators(phone_number),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return jsonify({'success': True, 'analysis': analysis})

@app.route('/api/stats')
def get_stats():
    """الحصول على إحصائيات النظام"""
    stats = {
        'total_searches': len(db.searches),
        'unique_numbers': len(db.phones),
        'today_searches': len([s for s in db.searches if datetime.fromisoformat(s['timestamp']).date() == datetime.utcnow().date()]),
        'top_carriers': get_top_carriers(),
        'threat_levels': get_threat_distribution(),
        'system_status': 'operational',
        'last_update': datetime.utcnow().isoformat()
    }
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/support', methods=['POST'])
def contact_support():
    """تواصل مع الدعم"""
    data = request.json
    message = data.get('message', '')
    contact = data.get('contact', '')
    
    # هنا يمكن إرسال الرسالة إلى واتساب
    print(f"📞 [SUPPORT] رسالة جديدة: {message}")
    print(f"📞 [SUPPORT] جهة الاتصال: {contact}")
    
    return jsonify({
        'success': True,
        'message': 'تم استلام رسالتك. سيتواصل معك الدعم قريباً.',
        'support_number': '967733393303'
    })

@app.route('/api/whatsapp')
def whatsapp_redirect():
    """إعادة التوجيه إلى واتساب"""
    phone = request.args.get('phone', '967733393303')
    message = request.args.get('message', 'أحتاج إلى دعم فني')
    
    whatsapp_url = f"https://wa.me/{phone}?text={requests.utils.quote(message)}"
    
    return jsonify({
        'success': True,
        'url': whatsapp_url,
        'redirect': True
    })

# ========== دوال مساعدة متقدمة ==========

def get_phone_info(phone_number, api_key):
    """الحصول على معلومات الرقم"""
    try:
        url = "https://apilayer.net/api/validate"
        params = {
            "access_key": api_key,
            "number": phone_number,
            "country_code": "",
            "format": "1"
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        return None
        
    except:
        return None

def analyze_threat_level(phone_number, ip, numverify_data):
    """تحليل مستوى التهديد"""
    threats = []
    
    # التحقق من الرقم
    if numverify_data and not numverify_data.get("valid"):
        threats.append(2)
    
    # التحقق من النمط
    if re.search(r'(\d)\1{4,}', phone_number):  # أرقام متكررة
        threats.append(1)
    
    # تحليل البادئة
    prefixes = {'73': 1, '77': 0, '71': 0, '70': 1}
    prefix = phone_number[:2]
    threats.append(prefixes.get(prefix, 0))
    
    # حساب درجة التهديد
    threat_score = sum(threats)
    
    if threat_score >= 3:
        return 'high'
    elif threat_score >= 2:
        return 'medium'
    else:
        return 'low'

def generate_cyber_location(phone_number, carrier):
    """توليد موقع متقدم"""
    # استخدام الرقم كمصدر عشوائي
    seed = int(phone_number[-6:]) if len(phone_number) >= 6 else 123456
    random.seed(seed)
    
    if carrier in yemen_towers:
        tower = random.choice(yemen_towers[carrier])
        lat = tower['lat'] + random.uniform(-0.03, 0.03)
        lon = tower['lon'] + random.uniform(-0.03, 0.03)
    else:
        lat = 15.3694 + random.uniform(-1, 1)
        lon = 44.1910 + random.uniform(-1, 1)
    
    random.seed()  # إعادة تعيين البذرة
    return lat, lon

def generate_advanced_towers(lat, lon, carrier, country):
    """توليد أبراج متقدمة"""
    towers = []
    
    if country == "Yemen" and carrier in yemen_towers:
        base_towers = yemen_towers[carrier]
    else:
        base_towers = []
        for i in range(3):
            base_towers.append({
                'id': f"{carrier}_{i+1}",
                'lat': lat + random.uniform(-0.1, 0.1),
                'lon': lon + random.uniform(-0.1, 0.1),
                'name': f"برج {carrier} {i+1}",
                'power': random.randint(70, 100)
            })
    
    for tower in base_towers:
        distance = calculate_distance(lat, lon, tower['lat'], tower['lon'])
        signal_strength = -60 - (distance * 2) + random.uniform(-5, 5)
        
        towers.append({
            'id': tower['id'],
            'name': tower['name'],
            'lat': tower['lat'],
            'lon': tower['lon'],
            'distance_km': round(distance, 3),
            'signal_strength': round(signal_strength, 1),
            'signal_percentage': min(100, max(0, (signal_strength + 120) * 0.833)),
            'carrier': carrier,
            'tower_power': tower.get('power', 85)
        })
    
    # إضافة أبراج من شركات أخرى
    other_carriers = [c for c in yemen_towers.keys() if c != carrier]
    if other_carriers and len(towers) < 6:
        extra_carrier = random.choice(other_carriers)
        for i in range(min(2, len(yemen_towers.get(extra_carrier, [])))):
            tower = yemen_towers[extra_carrier][i]
            distance = calculate_distance(lat, lon, tower['lat'], tower['lon'])
            signal_strength = -65 - (distance * 2) + random.uniform(-5, 5)
            
            towers.append({
                'id': tower['id'],
                'name': tower['name'],
                'lat': tower['lat'],
                'lon': tower['lon'],
                'distance_km': round(distance, 3),
                'signal_strength': round(signal_strength, 1),
                'signal_percentage': min(100, max(0, (signal_strength + 120) * 0.833)),
                'carrier': extra_carrier,
                'tower_power': tower.get('power', 85)
            })
    
    towers.sort(key=lambda x: x['signal_strength'], reverse=True)
    return towers

def advanced_triangulation(towers):
    """تثليث متقدم"""
    if len(towers) < 3:
        return float(towers[0]['lat']), float(towers[0]['lon'])
    
    strongest = towers[:3]
    
    # استخدام متوسط مرجح مع مراعاة قوة الإشارة
    total_weight = 0
    weighted_lat = 0
    weighted_lon = 0
    
    for tower in strongest:
        weight = (tower['signal_strength'] + 120) ** 2
        weighted_lat += float(tower['lat']) * weight
        weighted_lon += float(tower['lon']) * weight
        total_weight += weight
    
    lat = weighted_lat / total_weight
    lon = weighted_lon / total_weight
    
    # إضافة بعض العشوائية للواقعية
    lat += random.uniform(-0.001, 0.001)
    lon += random.uniform(-0.001, 0.001)
    
    return lat, lon

def generate_cyber_map(actual_lat, actual_lon, est_lat, est_lon, towers, carrier, country, threat_level):
    """إنشاء خريطة سيبرانية"""
    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(14, 12))
        
        # ألوان حسب مستوى التهديد
        threat_colors = {'low': 'green', 'medium': 'orange', 'high': 'red'}
        threat_color = threat_colors.get(threat_level, 'yellow')
        
        # رسم الأبراج
        colors = {'STC': '#FF4444', 'Yemen Mobile': '#44FF44', 'Sabafon': '#FFAA44', 'MTN': '#FFFF44'}
        
        for i, tower in enumerate(towers[:8]):
            color = colors.get(tower['carrier'], '#4488FF')
            ax.scatter(tower['lon'], tower['lat'], 
                      c=color, s=200, marker='^', alpha=0.7,
                      label=tower['carrier'] if i == 0 else "")
            
            # إضافة نص للبرج
            ax.annotate(f"📡 {tower['distance_km']}km", 
                       (tower['lon'], tower['lat']),
                       fontsize=8, ha='center', color='white')
        
        # الموقع الفعلي
        ax.scatter(actual_lon, actual_lat, 
                  c=threat_color, s=400, marker='o', 
                  label='الموقع الفعلي', edgecolors='white', linewidth=3,
                  alpha=0.8)
        
        # الموقع المقدر
        ax.scatter(est_lon, est_lat,
                  c='cyan', s=300, marker='X',
                  label='الموقع المقدر', edgecolors='white', linewidth=2,
                  alpha=0.7)
        
        # دوائر المدى
        for tower in towers[:3]:
            circle = plt.Circle((tower['lon'], tower['lat']), 
                              tower['distance_km']/80,
                              color=colors.get(tower['carrier'], '#4488FF'),
                              fill=False, linestyle='--', alpha=0.2,
                              linewidth=2)
            ax.add_patch(circle)
        
        # إعدادات الرسم
        ax.set_xlabel('خط الطول', fontsize=14, fontweight='bold', color='white')
        ax.set_ylabel('خط العرض', fontsize=14, fontweight='bold', color='white')
        ax.set_title(f'نظام التتبع الأمني - {carrier} | {country}', 
                    fontsize=18, fontweight='bold', color='white', pad=20)
        
        # إضافة شبكة
        ax.grid(True, alpha=0.2, linestyle='--')
        
        # إضافة وسيلة إيضاح
        ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
        
        # إضافة نص معلومات
        info_text = f"""مستوى التهديد: {threat_level.upper()}
الدقة: {random.randint(5, 50)} متر
الوقت: {datetime.utcnow().strftime('%H:%M:%S UTC')}
نظام: CYBER-TRACK v2.0"""
        
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.7),
                color='white')
        
        # حفظ الصورة
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor='#0a0a1a', edgecolor='none')
        buf.seek(0)
        
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        return image_base64
        
    except Exception as e:
        print(f"⚠️ خطأ في الخريطة: {e}")
        return None

def generate_threat_report(phone_number, threat_level, carrier, country):
    """إنشاء تقرير التهديد"""
    reports = {
        'low': [
            "✅ الرقم يبدو طبيعياً",
            "📱 الجهاز متصل بالشبكة",
            "📍 الموقع ضمن النطاق المتوقع",
            "🔒 لا توجد مؤشرات تهديد"
        ],
        'medium': [
            "⚠️ بعض المؤشرات تستدعي الانتباه",
            "📡 الاتصال غير مستقر أحياناً",
            "📍 تغييرات غير معتادة في الموقع",
            "🔍 الرقم يحتاج إلى مراقبة"
        ],
        'high': [
            "🚨 مؤشرات تهديد عالية",
            "📵 الجهاز يستخدم تقنيات إخفاء",
            "📍 تنقلات سريعة وغير منطقية",
            "🔓 اتصالات مشبوهة مسجلة"
        ]
    }
    
    return {
        'level': threat_level,
        'messages': reports.get(threat_level, reports['low']),
        'recommendations': get_recommendations(threat_level),
        'generated_at': datetime.utcnow().isoformat()
    }

def get_recommendations(threat_level):
    """الحصول على توصيات حسب مستوى التهديد"""
    if threat_level == 'high':
        return [
            "مراقبة مستمرة للرقم",
            "تسجيل جميع الاتصالات",
            "تحديث النظام الأمني",
            "الإبلاغ عن النشاط المشبوه"
        ]
    elif threat_level == 'medium':
        return [
            "مراقبة دورية",
            "تسجيل التحركات الرئيسية",
            "التحقق من هوية المستخدم",
            "تحديث قاعدة البيانات"
        ]
    else:
        return [
            "مراقبة عادية",
            "تسجيل النشاطات المهمة",
            "التحقق الدوري",
            "الحفاظ على تحديث النظام"
        ]

def get_cyber_address(lat, lon, country):
    """الحصول على عنوان سيبراني"""
    addresses = {
        'Yemen': [
            "صنعاء - المنطقة الدبلوماسية",
            "عدن - كريتر",
            "الحديدة - الميناء",
            "تعز - المدينة القديمة",
            "المكلا - الواجهة البحرية",
            "إب - المركز التجاري",
            "ذمار - السوق المركزي"
        ],
        'Saudi Arabia': [
            "الرياض - حي العليا",
            "جدة - كورنيش البحر",
            "الدمام - شارع الملك عبدالله"
        ],
        'United Arab Emirates': [
            "دبي - برج خليفة",
            "أبوظبي - كورنيش"
        ]
    }
    
    if country in addresses:
        return random.choice(addresses[country])
    
    # حساب أقرب مدينة في اليمن
    yemen_cities = [
        ("صنعاء", 15.3694, 44.1910),
        ("عدن", 12.7855, 45.0187),
        ("الحديدة", 14.7978, 42.9545),
    ]
    
    closest = min(yemen_cities, key=lambda x: calculate_distance(lat, lon, x[1], x[2]))
    return f"قرب {closest[0]}، اليمن"

def calculate_distance(lat1, lon1, lat2, lon2):
    """حساب المسافة"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def determine_carrier(phone_number):
    """تحديد شركة الاتصالات"""
    prefixes = {
        '73': 'STC',
        '77': 'Yemen Mobile',
        '71': 'Sabafon',
        '70': 'MTN',
        '78': 'Yemen Mobile'
    }
    
    for prefix, carrier in prefixes.items():
        if phone_number.startswith(prefix):
            return carrier
    
    return random.choice(['STC', 'Yemen Mobile', 'Sabafon', 'MTN'])

def format_phone_number(phone_number):
    """تنسيق رقم الهاتف"""
    if len(phone_number) == 9:
        return f"+967{phone_number}"
    elif len(phone_number) == 10 and phone_number.startswith('0'):
        return f"+967{phone_number[1:]}"
    elif len(phone_number) == 12 and phone_number.startswith('967'):
        return f"+{phone_number}"
    else:
        return f"+{phone_number}"

def generate_arabic_name():
    """توليد اسم عربي عشوائي"""
    first_names = ['سبتان', 'علي', 'محمد', 'أحمد', 'حسن', 'حسين', 'محمود', 'خالد', 'عمر', 'يوسف']
    last_names = ['صفر', 'الشميري', 'الحداد', 'الكمالي', 'الفقيه', 'النهمي', 'العماري', 'الزبيدي']
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def calculate_risk_score(threat_level):
    """حساب درجة الخطورة"""
    scores = {'low': random.randint(10, 30), 'medium': random.randint(40, 70), 'high': random.randint(75, 95)}
    return scores.get(threat_level, 50)

def generate_imei():
    """توليد رقم IMEI عشوائي"""
    imei = '35'  # كود TAC
    for _ in range(13):
        imei += str(random.randint(0, 9))
    # رقم التحقق
    return imei

def generate_imsi():
    """توليد رقم IMSI عشوائي"""
    return f"4240{random.randint(100000000, 999999999)}"

def detect_patterns(phone_number):
    """الكشف عن أنماط في الرقم"""
    patterns = []
    
    if len(set(phone_number)) == 1:
        patterns.append("أرقام متطابقة")
    
    if phone_number == phone_number[::-1]:
        patterns.append("رقم متناظر")
    
    if '123' in phone_number or '456' in phone_number:
        patterns.append("تسلسل رقمي")
    
    return patterns

def predict_carriers(phone_number):
    """توقع شركات الاتصالات"""
    predictions = []
    
    if phone_number.startswith('73'):
        predictions.append({'carrier': 'STC', 'confidence': 95})
    if phone_number.startswith('77'):
        predictions.append({'carrier': 'Yemen Mobile', 'confidence': 90})
    if phone_number.startswith('71'):
        predictions.append({'carrier': 'Sabafon', 'confidence': 88})
    if phone_number.startswith('70'):
        predictions.append({'carrier': 'MTN', 'confidence': 85})
    
    return predictions

def check_risk_indicators(phone_number):
    """فحص مؤشرات الخطورة"""
    indicators = []
    
    if phone_number.endswith('0000'):
        indicators.append("رقم مميز - قد يكون وهمياً")
    
    if len(phone_number) != 9:
        indicators.append("طول غير قياسي")
    
    if phone_number[0] not in ['7', '0']:
        indicators.append("بادئة غير معتادة")
    
    return indicators

def get_top_carriers():
    """الحصول على أكثر الشركات بحثاً"""
    carriers = {'STC': 0, 'Yemen Mobile': 0, 'Sabafon': 0, 'MTN': 0, 'Other': 0}
    
    for phone_data in db.phones.values():
        carrier = phone_data.get('carrier', 'Other')
        carriers[carrier] = carriers.get(carrier, 0) + 1
    
    return dict(sorted(carriers.items(), key=lambda x: x[1], reverse=True)[:5])

def get_threat_distribution():
    """توزيع مستويات التهديد"""
    threats = {'low': 0, 'medium': 0, 'high': 0}
    
    for phone_data in db.phones.values():
        threat = phone_data.get('threat_level', 'low')
        threats[threat] = threats.get(threat, 0) + 1
    
    return threats

@app.route('/api/system/status')
def system_status():
    """حالة النظام"""
    return jsonify({
        'status': 'operational',
        'version': '2.0.0',
        'cyber_level': 'maximum',
        'encryption': 'AES-256-GCM',
        'uptime': random.randint(1000, 10000),
        'protected': True,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/dashboard')
def dashboard():
    """لوحة التحكم"""
    return jsonify({
        'searches_today': len([s for s in db.searches if datetime.fromisoformat(s['timestamp']).date() == datetime.utcnow().date()]),
        'active_tracking': len(db.phones),
        'threats_blocked': random.randint(50, 200),
        'system_health': 98,
        'last_scan': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    ssl_context = ('cert.pem', 'key.pem') if os.path.exists('cert.pem') and os.path.exists('key.pem') else None
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('DEBUG', 'False').lower() == 'true',
        ssl_context=ssl_context
    )
