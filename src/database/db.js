import Database from "better-sqlite3";

const db = new Database("database.sqlite");

// ====== الجداول الأساسية ======
// جدول الحسابات
db.prepare(`
CREATE TABLE IF NOT EXISTS accounts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    status TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// جدول الرسائل
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

// جدول الحالات
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
)
`).run();

// جدول مشاهدات الحالات
db.prepare(`
CREATE TABLE IF NOT EXISTS status_views(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    status_id TEXT,
    viewer TEXT,
    viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (status_id) REFERENCES statuses(status_id)
)
`).run();

// جدول المجموعات
db.prepare(`
CREATE TABLE IF NOT EXISTS groups(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    group_id TEXT UNIQUE,
    group_name TEXT,
    participants TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// ====== الجداول الجديدة ======

// جدول الرسائل المجدولة
db.prepare(`
CREATE TABLE IF NOT EXISTS scheduled_messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    type TEXT CHECK(type IN ('single', 'broadcast', 'status')),
    recipient TEXT,
    recipients TEXT,
    message TEXT,
    media_url TEXT,
    scheduled_at DATETIME,
    executed_at DATETIME,
    repeat TEXT,
    end_date DATETIME,
    status TEXT DEFAULT 'pending',
    result TEXT,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// جدول الردود التلقائية
db.prepare(`
CREATE TABLE IF NOT EXISTS auto_reply_rules(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    trigger TEXT,
    reply TEXT,
    match_type TEXT DEFAULT 'contains',
    priority INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// جدول سجل الردود التلقائية
db.prepare(`
CREATE TABLE IF NOT EXISTS auto_reply_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    sender TEXT,
    trigger TEXT,
    reply TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// جدول قوائم البث
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

// ====== إنشاء فهارس للتحسين ======
db.prepare(`CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(phone)`).run();
db.prepare(`CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)`).run();
db.prepare(`CREATE INDEX IF NOT EXISTS idx_scheduled_status ON scheduled_messages(status)`).run();
db.prepare(`CREATE INDEX IF NOT EXISTS idx_scheduled_date ON scheduled_messages(scheduled_at)`).run();
db.prepare(`CREATE INDEX IF NOT EXISTS idx_auto_reply_phone ON auto_reply_rules(phone)`).run();
db.prepare(`CREATE INDEX IF NOT EXISTS idx_statuses_phone ON statuses(phone)`).run();

console.log("✅ Database initialized successfully");

export default db; 

// src/database/db.js - أضف هذا الجدول

db.prepare(`
CREATE TABLE IF NOT EXISTS pairing_links(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id TEXT UNIQUE,
    phone TEXT,
    code TEXT,
    link TEXT,
    expires_at DATETIME,
    used INTEGER DEFAULT 0,
    revoked INTEGER DEFAULT 0,
    used_at DATETIME,
    revoked_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();
