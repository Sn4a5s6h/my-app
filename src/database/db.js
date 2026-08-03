import Database from "better-sqlite3";

const db = new Database("database.sqlite");


db.prepare(`
CREATE TABLE IF NOT EXISTS accounts(
id INTEGER PRIMARY KEY AUTOINCREMENT,
phone TEXT UNIQUE,
status TEXT,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
`).run();


export default db;
