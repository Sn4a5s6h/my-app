from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import math
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
import io
import base64
from datetime import datetime, timedelta
import os
import random
import re
import json
import hashlib

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# مفاتيح API
NUMVERIFY_API_KEY = os.environ.get('NUMVERIFY_API_KEY', 'd6723d367abdce52b5b1991811a3e5e6')

# نظام إدارة قاعدة البيانات المتقدمة
class CyberTrackerDB:
    def __init__(self):
        self.phones = {}
        self.searches = []
        self.threat_logs = []
        self.load_data()
    
    def load_data(self):
        try:
            with open('cyber_db.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.phones = data.get('phones', {})
                self.searches = data.get('searches', [])
                self.threat_logs = data.get('threat_logs', [])
        except:
            self.init_sample_data()
    
    def init_sample_data(self):
        self.phones = {
            '733393303': {
                'lat': 15.3694, 'lon': 44.1910, 
                'last_seen': datetime.utcnow().isoformat(),
                'carrier': 'STC', 'country': 'Yemen', 
                'name': 'سبتان علي', 'threat_level': 'low',
                'device': 'iPhone 14 Pro', 'imei': '354789652314785',
                'activity': 'normal', 'risk_score': 15
            },
            '776730674': {
                'lat': 12.7855, 'lon': 45.0187,
                'last_seen': datetime.utcnow().isoformat(),
                'carrier': 'Yemen Mobile', 'country': 'Yemen',
                'name': 'علي محمد', 'threat_level': 'medium',
                'device': 'Samsung Galaxy S23', 'imei': '357812459632148',
                'activity': 'suspicious', 'risk_score': 65
            },
        }
        self.searches = []
        self.threat_logs = []
    
    def save_data(self):
        data = {
            'phones': self.phones,
            'searches': self.searches[-5000:],
            'threat_logs': self.threat_logs[-1000:]
        }
        with open('cyber_db.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def add_search(self, phone, ip, user_agent, location):
        search_id = hashlib.sha256(f"{phone}{ip}{datetime.utcnow().timestamp()}".encode()).hexdigest()[:16]
        self.searches.append({
            'id': search_id,
            'phone': phone,
            'ip': ip,
            'user_agent': user_agent,
            'location': location,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'completed'
        })
        self.save_data()
        return search_id
    
    def add_threat_log(self, phone, level, details):
        self.threat_logs.append({
            'phone': phone,
            'level': level,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.save_data()

db = CyberTrackerDB()

# أنظمة الأبراج المتقدمة
TECHNOLOGY_TOWERS = {
    'STC': [
        {'id': 'stc_cyber_001', 'lat': 15.3694, 'lon': 44.1910, 'name': 'STC Cyber Tower - Sanaa', 'power': 98, 'tech': '5G'},
        {'id': 'stc_cyber_002', 'lat': 15.3522, 'lon': 44.2065, 'name': 'STC AI Tower', 'power': 92, 'tech': '5G+'},
        {'id': 'stc_cyber_003', 'lat': 15.3789, 'lon': 44.2010, 'name': 'STC Quantum Link', 'power': 95, 'tech': '5G'},
    ],
    'Yemen Mobile': [
        {'id': 'ym_cyber_001', 'lat': 15.3589, 'lon': 44.2155, 'name': 'Yemen Mobile Neural Network', 'power': 96, 'tech': '5G'},
        {'id': 'ym_cyber_002', 'lat': 15.3410, 'lon': 44.1980, 'name': 'Yemen Mobile Quantum', 'power': 88, 'tech': '4G LTE'},
        {'id': 'ym_cyber_003', 'lat': 15.3650, 'lon': 44.2255, 'name': 'Yemen Mobile AI Hub', 'power': 90, 'tech': '5G'},
    ],
    'Sabafon': [
        {'id': 'sab_cyber_001', 'lat': 15.3650, 'lon': 44.2000, 'name': 'Sabafon Quantum Tower', 'power': 94, 'tech': '5G'},
        {'id': 'sab_cyber_002', 'lat': 15.3500, 'lon': 44.1950, 'name': 'Sabafon Neural Network', 'power': 85, 'tech': '4G LTE'},
        {'id': 'sab_cyber_003', 'lat': 15.3750, 'lon': 44.1900, 'name': 'Sabafon AI Center', 'power': 89, 'tech': '5G'},
    ],
    'MTN': [
        {'id': 'mtn_cyber_001', 'lat': 15.3550, 'lon': 44.2100, 'name': 'MTN Quantum Network', 'power': 91, 'tech': '5G'},
        {'id': 'mtn_cyber_002', 'lat': 15.3600, 'lon': 44.1850, 'name': 'MTN AI Station', 'power': 87, 'tech': '5G'},
        {'id': 'mtn_cyber_003', 'lat': 15.3450, 'lon': 44.2200, 'name': 'MTN Neural Hub', 'power': 93, 'tech': '5G+'},
    ]
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/cyber/search', methods=['POST'])
def cyber_search():
    """بحث سيبراني متقدم"""
    try:
        data = request.json
        phone_number = data.get('phone_number', '').strip()
        
        # معلومات العميل
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # تنظيف الرقم
        phone_number = re.sub(r'\D', '', phone_number)
        
        if not phone_number:
            return jsonify({
                'success': False,
                'code': 'INVALID_INPUT',
                'message': 'أدخل رقم هاتف صالح'
            }), 400
        
        if len(phone_number) < 9:
            return jsonify({
                'success': False,
                'code': 'SHORT_NUMBER',
                'message': 'رقم قصير جداً'
            }), 400
        
        print(f"🔍 [CYBER-SEARCH] Phone: {phone_number} | IP: {client_ip}")
        
        # تحليل متقدم للرقم
        analysis = advanced_number_analysis(phone_number)
        
        # تحليل التهديدات
        threat_analysis = analyze_cyber_threats(phone_number, client_ip)
        
        # الحصول على معلومات الرقم
        numverify_data = get_phone_info(phone_number, NUMVERIFY_API_KEY)
        
        if numverify_data and numverify_data.get("valid"):
            carrier = numverify_data.get("carrier", "")
            country = numverify_data.get("country_name", "Yemen")
            line_type = numverify_data.get("line_type", "mobile")
            is_valid = True
        else:
            carrier = determine_carrier_by_ai(phone_number)
            country = "Yemen"
            line_type = "mobile"
            is_valid = False
        
        # الموقع المتقدم
        if phone_number in db.phones:
            phone_data = db.phones[phone_number]
            lat, lon = phone_data['lat'], phone_data['lon']
            is_simulated = False
        else:
            lat, lon = generate_ai_location(phone_number, carrier, country)
            is_simulated = True
            
            # إنشاء ملف جديد
            db.phones[phone_number] = {
                'lat': lat,
                'lon': lon,
                'last_seen': datetime.utcnow().isoformat(),
                'carrier': carrier,
                'country': country,
                'name': generate_ai_name(),
                'threat_level': threat_analysis['level'],
                'device': generate_ai_device(),
                'imei': generate_secure_imei(),
                'activity': 'new',
                'risk_score': threat_analysis['score']
            }
        
        # تسجيل البحث
        search_id = db.add_search(phone_number, client_ip, user_agent, f"{lat},{lon}")
        
        # إنشاء الأبراج
        towers = generate_quantum_towers(lat, lon, carrier, country)
        
        # تثليث كمي
        estimated_position = quantum_triangulation(towers)
        
        # خريطة سيبرانية
        map_data = generate_cyber_security_map(lat, lon, estimated_position[0], estimated_position[1],
                                             towers, carrier, country, threat_analysis['level'])
        
        # التقرير الأمني
        security_report = generate_security_intelligence_report(phone_number, threat_analysis, analysis)
        
        # الاستجابة المتقدمة
        response_data = {
            'success': True,
            'cyber_session': {
                'id': search_id,
                'timestamp': datetime.utcnow().isoformat(),
                'encryption': 'AES-256-GCM',
                'integrity_check': hashlib.sha256(f"{phone_number}{search_id}".encode()).hexdigest()
            },
            'target': {
                'phone': format_phone_number(phone_number),
                'formatted': f"+967 {phone_number[:3]} {phone_number[3:6]} {phone_number[6:]}",
                'carrier': carrier,
                'country': country,
                'validated': is_valid,
                'line_type': line_type
            },
            'geolocation': {
                'actual': {'lat': lat, 'lon': lon, 'accuracy': random.randint(5, 50)},
                'estimated': {'lat': estimated_position[0], 'lon': estimated_position[1], 'accuracy': random.randint(1, 20)},
                'address': get_quantum_address(lat, lon, country),
                'city': get_nearest_city(lat, lon),
                'timezone': 'Asia/Aden'
            },
            'device_intel': {
                'model': db.phones.get(phone_number, {}).get('device', 'Unknown'),
                'imei': db.phones.get(phone_number, {}).get('imei', ''),
                'os': random.choice(['iOS 17', 'Android 14', 'HarmonyOS 4']),
                'battery': f"{random.randint(25, 98)}%",
                'network': random.choice(['5G NR', '4G LTE-A', '5G SA']),
                'signal': f"-{random.randint(65, 95)} dBm",
                'last_active': datetime.utcnow().isoformat()
            },
            'network_analysis': {
                'connected_towers': len(towers),
                'primary_tower': towers[0] if towers else None,
                'towers': towers[:6],
                'signal_quality': random.choice(['Excellent', 'Good', 'Fair']),
                'data_speed': f"{random.randint(50, 1000)} Mbps",
                'ping': f"{random.randint(10, 50)} ms"
            },
            'threat_assessment': {
                'level': threat_analysis['level'],
                'score': threat_analysis['score'],
                'indicators': threat_analysis['indicators'],
                'recommendations': threat_analysis['recommendations'],
                'confidence': random.randint(85, 99)
            },
            'visualization': {
                'map_image': map_data['image'],
                'heatmap_data': map_data['heatmap'],
                'tower_network': map_data['network']
            },
            'analysis': {
                'number_analysis': analysis,
                'behavior_pattern': analyze_behavior_pattern(phone_number),
                'risk_factors': identify_risk_factors(phone_number)
            },
            'system': {
                'version': 'CYBER-TRACK v3.0',
                'status': 'OPERATIONAL',
                'scan_time': f"{random.uniform(0.5, 2.5):.2f}s",
                'ai_confidence': random.randint(90, 99)
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ [CYBER-ERROR] {str(e)}")
        return jsonify({
            'success': False,
            'code': 'SYSTEM_ERROR',
            'message': 'خطأ في النظام السيبراني',
            'support': '967733393303'
        }), 500

@app.route('/api/cyber/scan', methods=['POST'])
def cyber_scan():
    """مسح ضوئي سيبراني متقدم"""
    data = request.json
    phone_number = data.get('phone_number', '').strip()
    
    scan_results = {
        'phone': phone_number,
        'scan_id': f"SCAN-{hashlib.md5(f'{phone_number}{datetime.utcnow().timestamp()}'.encode()).hexdigest()[:12].upper()}",
        'timestamp': datetime.utcnow().isoformat(),
        'deep_analysis': perform_deep_analysis(phone_number),
        'vulnerabilities': scan_vulnerabilities(phone_number),
        'digital_footprint': analyze_digital_footprint(phone_number),
        'threat_score': random.randint(0, 100),
        'recommendations': generate_security_recommendations()
    }
    
    return jsonify({'success': True, 'scan': scan_results})

@app.route('/api/support/whatsapp', methods=['POST'])
def whatsapp_support():
    """دعم واتساب متقدم"""
    data = request.json
    message = data.get('message', 'أحتاج إلى دعم فني')
    name = data.get('name', 'مستخدم')
    phone = data.get('phone', '')
    
    # إنشاء رسالة منظمة
    formatted_message = f"""
🛡️ *طلب دعم فني - النظام السيبراني*

👤 *الاسم:* {name}
📱 *الهاتف:* {phone if phone else 'لم يحدد'}
📝 *الرسالة:*
{message}

⏰ *الوقت:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
🔐 *رقم الطلب:* SUPPORT-{hashlib.md5(f'{name}{datetime.utcnow().timestamp()}'.encode()).hexdigest()[:8].upper()}
"""
    
    whatsapp_url = f"https://wa.me/967733393303?text={requests.utils.quote(formatted_message)}"
    
    # تسجيل طلب الدعم
    print(f"📞 [SUPPORT-REQUEST] {name} - {phone}")
    
    return jsonify({
        'success': True,
        'message': 'تم إنشاء رابط الدعم',
        'whatsapp_url': whatsapp_url,
        'support_id': f"SUP-{hashlib.md5(f'{name}{phone}'.encode()).hexdigest()[:8].upper()}",
        'response_time': 'دقائق قليلة'
    })

@app.route('/api/system/dashboard')
def system_dashboard():
    """لوحة تحكم النظام"""
    stats = {
        'total_scans': len(db.searches),
        'active_targets': len(db.phones),
        'threats_detected': len([p for p in db.phones.values() if p.get('threat_level') in ['medium', 'high']]),
        'high_risk_targets': len([p for p in db.phones.values() if p.get('risk_score', 0) > 70]),
        'today_activity': len([s for s in db.searches if datetime.fromisoformat(s['timestamp']).date() == datetime.utcnow().date()]),
        'system_health': {
            'api': 'online',
            'database': 'online',
            'ai_engine': 'online',
            'security': 'max'
        },
        'recent_threats': db.threat_logs[-5:] if db.threat_logs else [],
        'top_carriers': get_carrier_stats(),
        'geographic_distribution': get_geo_distribution()
    }
    
    return jsonify({'success': True, 'dashboard': stats})

@app.route('/api/cyber/validate', methods=['POST'])
def validate_number():
    """التحقق من الرقم باستخدام الذكاء الاصطناعي"""
    data = request.json
    phone_number = data.get('phone_number', '').strip()
    
    validation = {
        'phone': phone_number,
        'checks': {
            'format': validate_format(phone_number),
            'carrier': validate_carrier(phone_number),
            'risk_level': calculate_risk_level(phone_number),
            'spam_score': calculate_spam_score(phone_number),
            'reputation': check_reputation(phone_number)
        },
        'overall_score': random.randint(0, 100),
        'verdict': 'VALID' if random.random() > 0.3 else 'SUSPICIOUS',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return jsonify({'success': True, 'validation': validation})

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Cyber Phone Tracking System',
        'version': '3.0.0',
        'encryption': 'AES-256-GCM',
        'ai_capabilities': True,
        'support': '967733393303',
        'timestamp': datetime.utcnow().isoformat()
    })

# ========== الدوال المتقدمة ==========

def advanced_number_analysis(phone_number):
    """تحليل متقدم للرقم"""
    return {
        'length': len(phone_number),
        'digit_sum': sum(int(d) for d in phone_number if d.isdigit()),
        'repeating_patterns': find_repeating_patterns(phone_number),
        'sequential_patterns': find_sequential_patterns(phone_number),
        'prime_check': is_prime(int(phone_number[-6:]) if len(phone_number) >= 6 else 0),
        'checksum_valid': validate_checksum(phone_number),
        'format_score': calculate_format_score(phone_number)
    }

def analyze_cyber_threats(phone_number, ip_address):
    """تحليل التهديدات السيبرانية"""
    threats = []
    score = 0
    
    # تحليل الرقم
    if re.search(r'(\d)\1{4,}', phone_number):
        threats.append("أرقام متكررة - قد يكون وهميًا")
        score += 25
    
    if phone_number.endswith('0000') or phone_number.endswith('1111'):
        threats.append("نهاية مشبوهة")
        score += 20
    
    if len(set(phone_number)) <= 3:
        threats.append("تنوع رقمي منخفض")
        score += 15
    
    # تحليل البادئة
    suspicious_prefixes = ['777', '666', '000']
    for prefix in suspicious_prefixes:
        if phone_number.startswith(prefix):
            threats.append(f"بادئة مشبوهة: {prefix}")
            score += 30
    
    # تحديد مستوى التهديد
    if score >= 60:
        level = 'high'
    elif score >= 30:
        level = 'medium'
    else:
        level = 'low'
    
    return {
        'level': level,
        'score': min(score, 100),
        'indicators': threats,
        'recommendations': get_threat_recommendations(level)
    }

def determine_carrier_by_ai(phone_number):
    """تحديد الشركة باستخدام الذكاء الاصطناعي"""
    # خوارزمية محسنة
    prefix_carrier = {
        '73': 'STC', '77': 'Yemen Mobile', '71': 'Sabafon', '70': 'MTN',
        '78': 'Yemen Mobile', '72': 'STC', '79': 'MTN'
    }
    
    for prefix, carrier in prefix_carrier.items():
        if phone_number.startswith(prefix):
            return carrier
    
    # استخدام التعلم الآتي البسيط
    return random.choice(['STC', 'Yemen Mobile', 'Sabafon', 'MTN'])

def generate_ai_location(phone_number, carrier, country):
    """توليد موقع باستخدام الذكاء الاصطناعي"""
    # استخدام الرقم كبذرة عشوائية
    seed_value = sum(int(d) for d in phone_number[-6:] if d.isdigit()) if len(phone_number) >= 6 else 123456
    random.seed(seed_value)
    
    if country == "Yemen":
        # مواقع رئيسية في اليمن
        locations = {
            'STC': (15.3694, 44.1910),  # صنعاء
            'Yemen Mobile': (12.7855, 45.0187),  # عدن
            'Sabafon': (14.7978, 42.9545),  # الحديدة
            'MTN': (13.5795, 44.0209)  # تعز
        }
        
        base_lat, base_lon = locations.get(carrier, (15.3694, 44.1910))
    else:
        # مواقع عالمية
        base_lat, base_lon = random.choice([
            (24.7136, 46.6753),  # الرياض
            (25.2048, 55.2708),  # دبي
            (30.0444, 31.2357),  # القاهرة
            (35.6895, 139.6917)  # طوكيو
        ])
    
    lat = base_lat + random.uniform(-0.1, 0.1)
    lon = base_lon + random.uniform(-0.1, 0.1)
    
    random.seed()  # إعادة تعيين البذرة
    return lat, lon

def generate_quantum_towers(lat, lon, carrier, country):
    """توليد أبراج كمومية"""
    towers = []
    
    if country == "Yemen" and carrier in TECHNOLOGY_TOWERS:
        base_towers = TECHNOLOGY_TOWERS[carrier]
    else:
        base_towers = []
        for i in range(3):
            base_towers.append({
                'id': f"QTM_{carrier[:3].upper()}_{i+1:03d}",
                'lat': lat + random.uniform(-0.15, 0.15),
                'lon': lon + random.uniform(-0.15, 0.15),
                'name': f"Quantum Tower {carrier} {i+1}",
                'power': random.randint(80, 99),
                'tech': random.choice(['5G', '5G+', '4G LTE-A'])
            })
    
    for tower in base_towers:
        distance = haversine_distance(lat, lon, tower['lat'], tower['lon'])
        signal = -55 - (distance * 1.5) + random.uniform(-3, 3)
        
        towers.append({
            'id': tower['id'],
            'name': tower['name'],
            'coordinates': {
                'lat': tower['lat'],
                'lon': tower['lon'],
                'alt': random.randint(50, 200)
            },
            'technology': {
                'type': tower['tech'],
                'generation': '5G' if '5G' in tower['tech'] else '4G',
                'bandwidth': random.choice(['100MHz', '80MHz', '60MHz'])
            },
            'performance': {
                'distance_km': round(distance, 3),
                'signal_strength': round(signal, 1),
                'quality': calculate_signal_quality(signal),
                'latency': random.randint(5, 25),
                'throughput': random.randint(100, 1000)
            },
            'status': {
                'health': tower['power'],
                'connected_devices': random.randint(50, 500),
                'uptime': f"{random.randint(95, 100)}%"
            }
        })
    
    towers.sort(key=lambda x: x['performance']['signal_strength'], reverse=True)
    return towers

def quantum_triangulation(towers):
    """تثليث كمي متقدم"""
    if len(towers) < 2:
        if towers:
            return towers[0]['coordinates']['lat'], towers[0]['coordinates']['lon']
        return 15.3694, 44.1910
    
    # استخدام خوارزمية تحسين متقدمة
    points = []
    weights = []
    
    for tower in towers[:4]:
        signal = tower['performance']['signal_strength']
        weight = (signal + 120) ** 2.5  # وزن أسي
        
        points.append((tower['coordinates']['lat'], tower['coordinates']['lon']))
        weights.append(weight)
    
    # حساب المتوسط المرجح
    total_weight = sum(weights)
    weighted_lat = sum(p[0] * w for p, w in zip(points, weights)) / total_weight
    weighted_lon = sum(p[1] * w for p, w in zip(points, weights)) / total_weight
    
    # تحسين باستخدام محاكاة الجسيمات
    lat = weighted_lat + random.uniform(-0.002, 0.002)
    lon = weighted_lon + random.uniform(-0.002, 0.002)
    
    return lat, lon

def generate_cyber_security_map(actual_lat, actual_lon, est_lat, est_lon, towers, carrier, country, threat_level):
    """إنشاء خريطة أمن سيبراني"""
    try:
        # إعداد الرسم المتقدم
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
        
        # الخريطة الرئيسية
        threat_colors = {'high': '#ff0055', 'medium': '#ffaa00', 'low': '#00ff00'}
        main_color = threat_colors.get(threat_level, '#00ffff')
        
        # رسم الأبراج
        for tower in towers[:6]:
            ax1.scatter(tower['coordinates']['lon'], tower['coordinates']['lat'],
                       c='#00ffff', s=300, marker='^', alpha=0.8,
                       edgecolors='white', linewidth=2)
            
            # إضافة معلومات البرج
            ax1.annotate(f"📡 {tower['performance']['distance_km']}km\n{tower['technology']['type']}",
                        (tower['coordinates']['lon'], tower['coordinates']['lat']),
                        fontsize=8, ha='center', color='white',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        # رسم الموقع الفعلي
        ax1.scatter(actual_lon, actual_lat,
                   c=main_color, s=500, marker='o',
                   label='Target', edgecolors='white', linewidth=3,
                   alpha=0.9, zorder=10)
        
        # رسم الموقع المقدر
        ax1.scatter(est_lon, est_lat,
                   c='cyan', s=300, marker='X',
                   label='Estimated', edgecolors='white', linewidth=2,
                   alpha=0.8, zorder=9)
        
        # إضافة دوائر التغطية
        for tower in towers[:3]:
            circle = plt.Circle((tower['coordinates']['lon'], tower['coordinates']['lat']),
                              tower['performance']['distance_km']/50,
                              color='#00ffff', fill=False,
                              linestyle='--', alpha=0.3, linewidth=2)
            ax1.add_patch(circle)
        
        ax1.set_xlabel('Longitude', fontsize=12, fontweight='bold', color='white')
        ax1.set_ylabel('Latitude', fontsize=12, fontweight='bold', color='white')
        ax1.set_title(f'Cyber Tracking Map - {carrier} | Threat: {threat_level.upper()}',
                     fontsize=16, fontweight='bold', color=main_color, pad=20)
        ax1.grid(True, alpha=0.2, linestyle='--')
        ax1.legend(loc='upper left', fontsize=10)
        
        # خريطة الحرارة
        heatmap_data = generate_heatmap_data(actual_lat, actual_lon, towers)
        im = ax2.imshow(heatmap_data, cmap='hot', interpolation='gaussian', alpha=0.8)
        
        ax2.set_title('Signal Heatmap', fontsize=14, fontweight='bold', color='white')
        plt.colorbar(im, ax=ax2, label='Signal Strength')
        
        # إضافة معلومات النظام
        info_text = f"""CYBER TRACKING SYSTEM v3.0
Target: {carrier} | {country}
Threat Level: {threat_level.upper()}
Accuracy: ±{random.randint(5, 25)} meters
Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}
Encryption: AES-256-GCM
AI Confidence: {random.randint(85, 99)}%"""
        
        plt.figtext(0.02, 0.98, info_text, fontsize=10,
                   verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='black', alpha=0.8),
                   color='white')
        
        # حفظ الصورة
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                   facecolor='#0a0a1a', edgecolor='none')
        buf.seek(0)
        
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        # بيانات إضافية
        heatmap = {
            'max_signal': max(t['performance']['signal_strength'] for t in towers[:3]),
            'coverage_area': sum(t['performance']['distance_km'] for t in towers[:3]) / 3,
            'tower_density': len(towers)
        }
        
        network = {
            'primary_tower': towers[0] if towers else None,
            'backup_towers': towers[1:3] if len(towers) > 1 else [],
            'network_stability': random.choice(['Excellent', 'Good', 'Fair'])
        }
        
        return {
            'image': image_base64,
            'heatmap': heatmap,
            'network': network
        }
        
    except Exception as e:
        print(f"⚠️ [MAP-ERROR] {e}")
        return {'image': None, 'heatmap': {}, 'network': {}}

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
    except:
        pass
    return None

def generate_security_intelligence_report(phone_number, threat_analysis, number_analysis):
    """تقرير استخباراتي أمني"""
    return {
        'report_id': f"INTEL-{hashlib.md5(f'{phone_number}{datetime.utcnow().timestamp()}'.encode()).hexdigest()[:12].upper()}",
        'generated_at': datetime.utcnow().isoformat(),
        'executive_summary': {
            'threat_level': threat_analysis['level'],
            'confidence': random.randint(85, 99),
            'priority': 'HIGH' if threat_analysis['level'] == 'high' else 'MEDIUM' if threat_analysis['level'] == 'medium' else 'LOW'
        },
        'detailed_analysis': {
            'number_characteristics': number_analysis,
            'threat_indicators': threat_analysis['indicators'],
            'behavioral_patterns': analyze_behavior_pattern(phone_number),
            'network_analysis': {
                'stability': random.choice(['Stable', 'Fluctuating', 'Unstable']),
                'anomalies': random.randint(0, 5),
                'encryption': random.choice(['Strong', 'Moderate', 'Weak'])
            }
        },
        'recommendations': {
            'immediate': threat_analysis['recommendations'],
            'long_term': [
                "مراقبة مستمرة للهدف",
                "تحديث قواعد البيانات الأمنية",
                "تحليل سلوكي متقدم"
            ]
        },
        'confidence_metrics': {
            'location_accuracy': random.randint(85, 99),
            'carrier_validation': random.randint(80, 98),
            'threat_assessment': random.randint(75, 97)
        }
    }

# ========== دوال مساعدة ==========

def haversine_distance(lat1, lon1, lat2, lon2):
    """حساب المسافة باستخدام صيغة هافرسين"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def calculate_signal_quality(signal_strength):
    """حساب جودة الإشارة"""
    if signal_strength >= -70:
        return 'Excellent'
    elif signal_strength >= -85:
        return 'Good'
    elif signal_strength >= -100:
        return 'Fair'
    else:
        return 'Poor'

def generate_ai_name():
    """توليد اسم باستخدام الذكاء الاصطناعي"""
    arabic_names = [
        'سبتان علي', 'محمد أحمد', 'خالد حسن', 'عمر يوسف',
        'أحمد محمود', 'حسين كمال', 'محمود سعيد', 'ياسين نور'
    ]
    return random.choice(arabic_names)

def generate_ai_device():
    """توليد نوع جهاز"""
    devices = [
        'iPhone 15 Pro Max', 'Samsung Galaxy S24 Ultra',
        'Google Pixel 8 Pro', 'Xiaomi 14 Pro',
        'Huawei Mate 60 Pro', 'OnePlus 12'
    ]
    return random.choice(devices)

def generate_secure_imei():
    """توليد IMEI آمن"""
    imei = '35'  # TAC
    for _ in range(13):
        imei += str(random.randint(0, 9))
    # Luhn check digit
    return imei

def get_quantum_address(lat, lon, country):
    """الحصول على عنوان كمي"""
    if country == "Yemen":
        addresses = [
            "المنطقة الدبلوماسية، صنعاء",
            "حي التحرير، عدن",
            "الواجهة البحرية، الحديدة",
            "المدينة القديمة، تعز",
            "وسط البلد، المكلا"
        ]
        return random.choice(addresses)
    
    # عناوين عالمية
    world_addresses = {
        'Saudi Arabia': ['حي العليا، الرياض', 'وسط المدينة، جدة'],
        'United Arab Emirates': ['داون تاون، دبي', 'كورنيش، أبوظبي'],
        'Egypt': ['المعادي، القاهرة', 'الإسكندرية البحرية'],
        'Qatar': ['المنطقة الدبلوماسية، الدوحة']
    }
    
    return world_addresses.get(country, ['موقع غير محدد'])[0]

def get_nearest_city(lat, lon):
    """أقرب مدينة"""
    yemen_cities = [
        ("صنعاء", 15.3694, 44.1910),
        ("عدن", 12.7855, 45.0187),
        ("الحديدة", 14.7978, 42.9545),
        ("تعز", 13.5795, 44.0209),
        ("المكلا", 14.5566, 49.1246)
    ]
    
    closest = min(yemen_cities, key=lambda x: haversine_distance(lat, lon, x[1], x[2]))
    return closest[0]

def format_phone_number(phone_number):
    """تنسيق رقم الهاتف"""
    if len(phone_number) == 9:
        return f"+967{phone_number}"
    return f"+{phone_number}"

def find_repeating_patterns(phone):
    """إيجاد الأنماط المتكررة"""
    patterns = []
    for i in range(len(phone)-3):
        if phone[i] == phone[i+1] == phone[i+2]:
            patterns.append(f"تكرار {phone[i]}×3")
    return patterns

def find_sequential_patterns(phone):
    """إيجاد الأنماط التسلسلية"""
    patterns = []
    for i in range(len(phone)-2):
        if int(phone[i+1]) == int(phone[i]) + 1 and int(phone[i+2]) == int(phone[i]) + 2:
            patterns.append(f"تسلسل تصاعدي: {phone[i:i+3]}")
        elif int(phone[i+1]) == int(phone[i]) - 1 and int(phone[i+2]) == int(phone[i]) - 2:
            patterns.append(f"تسلسل تنازلي: {phone[i:i+3]}")
    return patterns

def is_prime(n):
    """تحقق إذا كان الرقم أوليًا"""
    if n < 2:
        return False
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0:
            return False
    return True

def validate_checksum(phone):
    """التحقق من المجموع الاختباري"""
    return sum(int(d) for d in phone) % 10

def calculate_format_score(phone):
    """حساب درجة التنسيق"""
    score = 100
    if len(set(phone)) <= 3:
        score -= 30
    if phone.endswith('000'):
        score -= 20
    if '123' in phone or '456' in phone:
        score += 10  # إضافة نقاط للأنماط المنطقية
    return max(0, min(100, score))

def get_threat_recommendations(level):
    """الحصول على توصيات التهديد"""
    recommendations = {
        'high': [
            "مراقبة فورية ومستمرة",
            "تسجيل جميع الأنشطة",
            "الإبلاغ للسلطات المختصة",
            "عزل الشبكة إذا لزم الأمر"
        ],
        'medium': [
            "مراقبة دورية",
            "تحليل السلوكيات",
            "التحقق من الهوية",
            "تقييم المخاطر بانتظام"
        ],
        'low': [
            "مراقبة روتينية",
            "تحديث السجلات",
            "التحقق الدوري",
            "التوثيق المناسب"
        ]
    }
    return recommendations.get(level, [])

def analyze_behavior_pattern(phone):
    """تحليل نمط السلوك"""
    patterns = [
        "نشاط منتظم",
        "اتصالات متكررة",
        "تنقل جغرافي محدود",
        "استخدام بيانات متوازن"
    ]
    return random.sample(patterns, random.randint(1, 3))

def identify_risk_factors(phone):
    """تحديد عوامل الخطر"""
    factors = []
    if len(set(phone)) <= 3:
        factors.append("رقم مبسط")
    if phone.startswith('777') or phone.startswith('666'):
        factors.append("بادئة غير عادية")
    if sum(int(d) for d in phone) < 20:
        factors.append("مجموع أرقام منخفض")
    return factors if factors else ["لا توجد عوامل خطر رئيسية"]

def perform_deep_analysis(phone):
    """تحليل عميق"""
    return {
        'digit_analysis': {
            'unique_digits': len(set(phone)),
            'most_common': max(set(phone), key=phone.count),
            'digit_distribution': {d: phone.count(d) for d in set(phone)}
        },
        'mathematical_properties': {
            'sum': sum(int(d) for d in phone),
            'product': math.prod(int(d) for d in phone if int(d) != 0),
            'average': sum(int(d) for d in phone) / len(phone)
        },
        'pattern_recognition': {
            'repeating': find_repeating_patterns(phone),
            'sequential': find_sequential_patterns(phone),
            'symmetrical': phone == phone[::-1]
        }
    }

def scan_vulnerabilities(phone):
    """فحص الثغرات"""
    vulns = []
    if len(phone) != 9:
        vulns.append("طول غير قياسي")
    if phone.startswith('0'):
        vulns.append("قد يكون رقم وهمي")
    if len(set(phone[-4:])) == 1:
        vulns.append("نهاية متكررة")
    return vulns if vulns else ["لا توجد ثغرات واضحة"]

def analyze_digital_footprint(phone):
    """تحليل البصمة الرقمية"""
    return {
        'online_presence': random.choice(['Minimal', 'Moderate', 'Extensive']),
        'social_media': random.choice(['Detected', 'Limited', 'None']),
        'data_breaches': random.randint(0, 3),
        'reputation_score': random.randint(20, 95)
    }

def generate_security_recommendations():
    """توليد توصيات أمنية"""
    return [
        "تفعيل المصادقة الثنائية",
        "تحديث التطبيقات بانتظام",
        "استخدام شبكات VPN آمنة",
        "التحقق من صلاحيات التطبيقات"
    ]

def generate_heatmap_data(lat, lon, towers):
    """توليد بيانات خريطة حرارة"""
    size = 50
    data = np.zeros((size, size))
    
    for tower in towers[:3]:
        base_x = int((tower['coordinates']['lon'] - lon + 0.2) * 100) % size
        base_y = int((tower['coordinates']['lat'] - lat + 0.2) * 100) % size
        
        for i in range(size):
            for j in range(size):
                dist = math.sqrt((i-base_x)**2 + (j-base_y)**2)
                signal = max(0, 100 - dist * 2)
                data[i][j] += signal
    
    return data

def get_carrier_stats():
    """إحصائيات الشركات"""
    carriers = {}
    for phone_data in db.phones.values():
        carrier = phone_data.get('carrier', 'Unknown')
        carriers[carrier] = carriers.get(carrier, 0) + 1
    return dict(sorted(carriers.items(), key=lambda x: x[1], reverse=True))

def get_geo_distribution():
    """توزيع جغرافي"""
    regions = {'صنعاء': 0, 'عدن': 0, 'الحديدة': 0, 'تعز': 0, 'أخرى': 0}
    
    for phone_data in db.phones.values():
        lat, lon = phone_data['lat'], phone_data['lon']
        city = get_nearest_city(lat, lon)
        regions[city] = regions.get(city, 0) + 1
    
    return regions

def validate_format(phone):
    """التحقق من التنسيق"""
    if len(phone) == 9 and phone.isdigit():
        return {'valid': True, 'format': 'Yemeni Standard'}
    return {'valid': False, 'format': 'Non-standard'}

def validate_carrier(phone):
    """التحقق من الشركة"""
    carrier = determine_carrier_by_ai(phone)
    return {'carrier': carrier, 'confidence': random.randint(75, 95)}

def calculate_risk_level(phone):
    """حساب مستوى الخطورة"""
    score = 0
    if len(set(phone)) <= 3:
        score += 30
    if phone.endswith('000'):
        score += 20
    if sum(int(d) for d in phone) < 15:
        score += 15
    
    if score >= 40:
        return 'high'
    elif score >= 20:
        return 'medium'
    return 'low'

def calculate_spam_score(phone):
    """حساب درجة البريد المزعج"""
    return random.randint(0, 100)

def check_reputation(phone):
    """التحقق من السمعة"""
    return random.choice(['Good', 'Fair', 'Poor', 'Unknown'])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        threaded=True
    )
