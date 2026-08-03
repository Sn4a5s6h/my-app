import Database from "better-sqlite3";

const db = new Database("database.sqlite");

// ====== جدول الحسابات ======
db.prepare(`
CREATE TABLE IF NOT EXISTS accounts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    status TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// ====== جدول الرسائل ======
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

// ====== جدول الحالات (Statuses) ======
db.prepare(`
CREATE TABLE IF NOT EXISTS statuses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    sender TEXT,
    status_id TEXT UNIQUE,
    message TEXT,
    media_url TEXT,
    recipients TEXT,  -- JSON array
    is_viewed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
)
`).run();

// ====== جدول مشاهدات الحالات ======
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

// ====== جدول المجموعات ======
db.prepare(`
CREATE TABLE IF NOT EXISTS groups(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    group_id TEXT UNIQUE,
    group_name TEXT,
    participants TEXT,  -- JSON array
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// ====== جدول قوائم البث ======
db.prepare(`
CREATE TABLE IF NOT EXISTS broadcast_lists(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    list_name TEXT,
    recipients TEXT,  -- JSON array
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();

// ====== إضافة أعمدة جديدة للجداول الموجودة ======
try {
    db.prepare(`ALTER TABLE messages ADD COLUMN media_type TEXT`).run();
} catch (e) {}
try {
    db.prepare(`ALTER TABLE messages ADD COLUMN media_url TEXT`).run();
} catch (e) {}
try {
    db.prepare(`ALTER TABLE messages ADD COLUMN status TEXT DEFAULT 'sent'`).run();
} catch (e) {}

console.log("✅ Database initialized successfully");

export default db;
