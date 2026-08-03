import Database from "better-sqlite3";

const db = new Database("database.sqlite");

// ====== الجداول الموجودة ======
db.prepare(`
CREATE TABLE IF NOT EXISTS accounts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    status TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

db.prepare(`
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    direction TEXT,
    sender TEXT,
    receiver TEXT,
    message TEXT,
    media_type TEXT,
    media_url TEXT,
    status TEXT DEFAULT 'sent',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

db.prepare(`
CREATE TABLE IF NOT EXISTS statuses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    sender TEXT,
    status_id TEXT UNIQUE,
    message TEXT,
    media_url TEXT,
    recipients TEXT,
    is_viewed INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
)
`).run();

db.prepare(`
CREATE TABLE IF NOT EXISTS status_views(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    status_id TEXT,
    viewer TEXT,
    viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

db.prepare(`
CREATE TABLE IF NOT EXISTS groups(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    group_id TEXT UNIQUE,
    group_name TEXT,
    participants TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// ====== الجداول الجديدة ======

// 1. جدول الرسائل المجدولة
db.prepare(`
CREATE TABLE IF NOT EXISTS scheduled_messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE,
    phone TEXT,
    to_number TEXT,
    message TEXT,
    media_path TEXT,
    schedule_time DATETIME,
    repeat_type TEXT,
    repeat_interval INTEGER,
    status TEXT DEFAULT 'scheduled',
    executed_at DATETIME,
    result TEXT,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 2. جدول الحالات المجدولة
db.prepare(`
CREATE TABLE IF NOT EXISTS scheduled_statuses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE,
    phone TEXT,
    message TEXT,
    media_path TEXT,
    schedule_time DATETIME,
    repeat_type TEXT,
    status TEXT DEFAULT 'scheduled',
    executed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 3. جدول الردود التلقائية
db.prepare(`
CREATE TABLE IF NOT EXISTS auto_reply_rules(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT UNIQUE,
    phone TEXT,
    trigger_text TEXT,
    reply_text TEXT,
    match_type TEXT DEFAULT 'contains',
    media_path TEXT,
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 4. جدول سجلات الردود التلقائية
db.prepare(`
CREATE TABLE IF NOT EXISTS auto_reply_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    rule_id TEXT,
    sender TEXT,
    trigger_message TEXT,
    reply_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 5. جدول الكلمات الممنوعة
db.prepare(`
CREATE TABLE IF NOT EXISTS banned_words(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id TEXT UNIQUE,
    phone TEXT,
    word TEXT,
    action TEXT DEFAULT 'delete',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 6. جدول الردود السريعة
db.prepare(`
CREATE TABLE IF NOT EXISTS quick_replies(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reply_id TEXT UNIQUE,
    phone TEXT,
    keyword TEXT,
    reply_text TEXT,
    media_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 7. جدول سجلات الردود السريعة
db.prepare(`
CREATE TABLE IF NOT EXISTS quick_reply_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    reply_id TEXT,
    sender TEXT,
    trigger_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 8. جدول قوائم البث
db.prepare(`
CREATE TABLE IF NOT EXISTS broadcast_lists(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    list_name TEXT,
    recipients TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// 9. جدول الإعدادات
db.prepare(`
CREATE TABLE IF NOT EXISTS settings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    setting_key TEXT,
    setting_value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phone, setting_key)
)
`).run();

console.log("✅ Database initialized with all tables");

export default db;
