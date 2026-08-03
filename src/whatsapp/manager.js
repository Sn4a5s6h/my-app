import {
    makeWASocket,
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore,
    Browsers,
    downloadMediaMessage,
    generateWAMessageFromContent,
    proto
} from "@whiskeysockets/baileys";
import pino from "pino";
import fs from "fs";
import path from "path";
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sessions = new Map();
const pairingData = new Map();
const statusViewers = new Map(); // تخزين مشاهدات الحالات

// ============= الوظائف الأساسية =============

export async function addAccount(phone, pairingCode = null) {
    const folder = `sessions/${phone}`;
    
    if (!fs.existsSync(folder))
        fs.mkdirSync(folder, { recursive: true });

    const { state, saveCreds } = await useMultiFileAuthState(folder);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: true,
        browser: Browsers.macOS("Desktop"),
        logger: pino({ level: "silent" }),
        getMessage: async (key) => {
            return {
                conversation: "Hello"
            };
        }
    });

    sock.phone = phone;
    sock.pairingCode = pairingCode;

    sock.ev.on("creds.update", saveCreds);

    // ====== حدث الاتصال ======
    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;
        console.log(`📱 ${phone} - Connection:`, connection);

        if (connection === "close") {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== 401;
            if (shouldReconnect) {
                console.log(`🔄 ${phone} - محاولة إعادة الاتصال...`);
                setTimeout(() => addAccount(phone, pairingCode), 5000);
            } else {
                console.log(`❌ ${phone} - تم تسجيل الخروج`);
                sessions.delete(phone);
            }
        }

        if (connection === "open") {
            console.log(`✅ ${phone} - تم الاتصال بنجاح!`);
            const db = (await import("../database/db.js")).default;
            const stmt = db.prepare(`
                INSERT OR REPLACE INTO accounts (phone, status, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            `);
            stmt.run(phone, "connected");
            
            // جلب الحالات عند الاتصال
            await fetchStatuses(phone);
        }

        if (qr) {
            console.log(`📸 ${phone} - QR Code generated`);
            pairingData.set(phone, { qr, timestamp: Date.now() });
        }
    });

    // ====== حدث الرسائل ======
    sock.ev.on("messages.upsert", async (data) => {
        const message = data.messages[0];
        if (!message.key.fromMe && message.message) {
            await handleIncomingMessage(phone, message, sock);
        }
    });

    // ====== حدث تحديث الحالات ======
    sock.ev.on("messages.update", async (updates) => {
        for (const update of updates) {
            if (update.update?.status) {
                console.log(`📊 ${phone} - تحديث حالة:`, update);
                await handleStatusUpdate(phone, update);
            }
        }
    });

    // ====== حدث الحالات الجديدة ======
    sock.ev.on("messaging-history.set", async ({ messages, contacts }) => {
        console.log(`📚 ${phone} - تم استقبال تاريخ المحادثات`);
    });

    if (pairingCode) {
        console.log(`🔑 ${phone} - جاري استخدام Pairing Code: ${pairingCode}`);
        try {
            await sock.waitForConnectionUpdate(
                (update) => update.pairingCode === pairingCode,
                30000
            );
            console.log(`✅ ${phone} - تم الاقتران بنجاح`);
        } catch (error) {
            console.log(`❌ ${phone} - فشل الاقتران:`, error.message);
        }
    }

    sessions.set(phone, sock);
    return sock;
}

// ============= معالجة الرسائل الواردة =============

async function handleIncomingMessage(phone, message, sock) {
    console.log(`📨 ${phone} - رسالة جديدة:`, message);
    
    const db = (await import("../database/db.js")).default;
    const sender = message.key.remoteJid;
    const receiver = phone + "@s.whatsapp.net";
    
    let text = "";
    let mediaType = null;
    let mediaUrl = null;

    // استخراج محتوى الرسالة
    if (message.message) {
        const msg = message.message;
        
        if (msg.conversation) {
            text = msg.conversation;
        } else if (msg.extendedTextMessage?.text) {
            text = msg.extendedTextMessage.text;
        } else if (msg.imageMessage) {
            text = "🖼️ صورة";
            mediaType = "image";
            mediaUrl = await downloadMedia(message, sock);
        } else if (msg.videoMessage) {
            text = "🎥 فيديو";
            mediaType = "video";
            mediaUrl = await downloadMedia(message, sock);
        } else if (msg.audioMessage) {
            text = "🎵 صوت";
            mediaType = "audio";
        } else if (msg.documentMessage) {
            text = `📄 مستند: ${msg.documentMessage.fileName || 'ملف'}`;
            mediaType = "document";
        } else if (msg.stickerMessage) {
            text = "🧩 ملصق";
            mediaType = "sticker";
        } else if (msg.contactMessage) {
            text = `👤 جهة اتصال: ${msg.contactMessage.displayName}`;
        } else if (msg.locationMessage) {
            text = `📍 موقع: ${msg.locationMessage.degreesLatitude}, ${msg.locationMessage.degreesLongitude}`;
        } else {
            text = "📎 وسائط";
        }
    }

    // حفظ الرسالة في قاعدة البيانات
    const stmt = db.prepare(`
        INSERT INTO messages (phone, direction, sender, receiver, message, media_type, media_url, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(phone, "incoming", sender, receiver, text, mediaType, mediaUrl, "received");

    // إرسال إشعار إلى التيليجرام
    const bot = (await import("../telegram/bot.js")).getBot();
    if (bot) {
        const adminId = (await import("../config/env.js")).default.ADMIN_ID;
        const msg = `📩 رسالة جديدة\n📱 حساب: ${phone}\n👤 من: ${sender}\n💬 ${text}`;
        bot.telegram.sendMessage(adminId, msg).catch(() => {});
    }
}

// ============= تنزيل الميديا =============

async function downloadMedia(message, sock) {
    try {
        const buffer = await downloadMediaMessage(
            message,
            "buffer",
            {},
            { 
                reuploadRequest: sock.updateMediaMessage
            }
        );
        
        // حفظ الميديا في مجلد
        const mediaDir = "media";
        if (!fs.existsSync(mediaDir)) {
            fs.mkdirSync(mediaDir);
        }
        
        const fileName = `${Date.now()}_${message.key.id}.jpg`;
        const filePath = path.join(mediaDir, fileName);
        fs.writeFileSync(filePath, buffer);
        
        return filePath;
    } catch (error) {
        console.error("فشل تنزيل الميديا:", error);
        return null;
    }
}

// ============= الرسائل الجماعية =============

export async function sendBroadcast(phone, numbers, message, mediaPath = null) {
    const sock = sessions.get(phone);
    if (!sock) {
        throw new Error("الحساب غير موجود أو غير متصل");
    }

    const results = [];
    const db = (await import("../database/db.js")).default;

    for (const number of numbers) {
        try {
            const jid = number.includes("@") ? number : `${number}@s.whatsapp.net`;
            
            let result;
            if (mediaPath && fs.existsSync(mediaPath)) {
                // إرسال رسالة مع ميديا
                const mediaBuffer = fs.readFileSync(mediaPath);
                const ext = path.extname(mediaPath).toLowerCase();
                
                if (['.jpg', '.jpeg', '.png', '.gif'].includes(ext)) {
                    result = await sock.sendMessage(jid, { 
                        image: mediaBuffer, 
                        caption: message 
                    });
                } else if (['.mp4', '.mov', '.avi'].includes(ext)) {
                    result = await sock.sendMessage(jid, { 
                        video: mediaBuffer, 
                        caption: message 
                    });
                } else if (['.mp3', '.wav', '.ogg'].includes(ext)) {
                    result = await sock.sendMessage(jid, { 
                        audio: mediaBuffer, 
                        mimetype: 'audio/mp4' 
                    });
                } else {
                    result = await sock.sendMessage(jid, { 
                        document: mediaBuffer, 
                        caption: message,
                        fileName: path.basename(mediaPath)
                    });
                }
            } else {
                // إرسال نص فقط
                result = await sock.sendMessage(jid, { text: message });
            }

            // حفظ الرسالة في قاعدة البيانات
            const stmt = db.prepare(`
                INSERT INTO messages (phone, direction, sender, receiver, message, status)
                VALUES (?, ?, ?, ?, ?, ?)
            `);
            stmt.run(phone, "outgoing", phone + "@s.whatsapp.net", jid, message, "sent");

            results.push({ number, success: true, result });
            
            // تأخير بين الرسائل لتجنب الحظر
            await sleep(1000);
            
        } catch (error) {
            results.push({ 
                number, 
                success: false, 
                error: error.message 
            });
        }
    }

    return {
        total: numbers.length,
        success: results.filter(r => r.success).length,
        failed: results.filter(r => !r.success).length,
        results
    };
}

// ============= إرسال الحالات (Status/Story) =============

export async function sendStatus(phone, message, mediaPath = null, recipients = null) {
    const sock = sessions.get(phone);
    if (!sock) {
        throw new Error("الحساب غير موجود أو غير متصل");
    }

    try {
        let statusMessage;
        const jid = phone + "@s.whatsapp.net";

        if (mediaPath && fs.existsSync(mediaPath)) {
            const mediaBuffer = fs.readFileSync(mediaPath);
            const ext = path.extname(mediaPath).toLowerCase();
            
            // تحديد نوع الميديا
            if (['.jpg', '.jpeg', '.png', '.gif'].includes(ext)) {
                statusMessage = await sock.sendMessage(jid, {
                    image: mediaBuffer,
                    caption: message,
                    ephemeralExpiration: 86400 // 24 ساعة
                }, {
                    statusJidList: recipients || [],
                    broadcast: true // جعلها حالة عامة
                });
            } else if (['.mp4', '.mov', '.avi'].includes(ext)) {
                statusMessage = await sock.sendMessage(jid, {
                    video: mediaBuffer,
                    caption: message,
                    ephemeralExpiration: 86400
                }, {
                    statusJidList: recipients || [],
                    broadcast: true
                });
            } else {
                throw new Error("نوع الميديا غير مدعوم للحالات");
            }
        } else {
            // حالة نصية فقط
            statusMessage = await sock.sendMessage(jid, {
                text: message,
                ephemeralExpiration: 86400
            }, {
                statusJidList: recipients || [],
                broadcast: true
            });
        }

        // حفظ الحالة في قاعدة البيانات
        const db = (await import("../database/db.js")).default;
        const stmt = db.prepare(`
            INSERT INTO statuses (phone, message, media_url, recipients, status_id, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        `);
        stmt.run(
            phone,
            message,
            mediaPath,
            JSON.stringify(recipients || []),
            statusMessage.key.id
        );

        return {
            success: true,
            statusId: statusMessage.key.id,
            message: "تم نشر الحالة بنجاح"
        };

    } catch (error) {
        throw new Error(`فشل نشر الحالة: ${error.message}`);
    }
}

// ============= جلب الحالات =============

export async function fetchStatuses(phone) {
    const sock = sessions.get(phone);
    if (!sock) {
        throw new Error("الحساب غير موجود");
    }

    try {
        // جلب حالات الأصدقاء
        const statuses = await sock.fetchStatus();
        console.log(`📊 ${phone} - تم جلب ${statuses.length} حالة`);
        
        // حفظ الحالات في قاعدة البيانات
        const db = (await import("../database/db.js")).default;
        for (const status of statuses) {
            const stmt = db.prepare(`
                INSERT OR REPLACE INTO statuses (phone, sender, status_id, message, created_at)
                VALUES (?, ?, ?, ?, ?)
            `);
            stmt.run(
                phone,
                status.jid,
                status.id,
                status.status || "حالة بدون نص",
                new Date(status.timestamp * 1000).toISOString()
            );
        }
        
        return statuses;
    } catch (error) {
        console.error(`❌ فشل جلب الحالات:`, error);
        return [];
    }
}

// ============= عرض حالة معينة =============

export async function viewStatus(phone, statusId) {
    const sock = sessions.get(phone);
    if (!sock) {
        throw new Error("الحساب غير موجود");
    }

    try {
        // محاكاة مشاهدة الحالة
        const result = await sock.readStatus(statusId);
        
        // تسجيل المشاهدة
        const db = (await import("../database/db.js")).default;
        const stmt = db.prepare(`
            INSERT INTO status_views (phone, status_id, viewer, viewed_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        `);
        stmt.run(phone, statusId, phone + "@s.whatsapp.net");
        
        return {
            success: true,
            message: "تم مشاهدة الحالة"
        };
    } catch (error) {
        throw new Error(`فشل مشاهدة الحالة: ${error.message}`);
    }
}

// ============= جلب مشاهدات الحالة =============

export async function getStatusViews(phone, statusId) {
    const db = (await import("../database/db.js")).default;
    
    const stmt = db.prepare(`
        SELECT * FROM status_views 
        WHERE status_id = ? 
        ORDER BY viewed_at DESC
    `);
    
    const views = stmt.all(statusId);
    
    return {
        total: views.length,
        views
    };
}

// ============= مشاهدة جميع الحالات =============

export async function viewAllStatuses(phone) {
    const sock = sessions.get(phone);
    if (!sock) {
        throw new Error("الحساب غير موجود");
    }

    try {
        const statuses = await sock.fetchStatus();
        const results = [];
        
        for (const status of statuses) {
            try {
                await viewStatus(phone, status.id);
                results.push({
                    id: status.id,
                    sender: status.jid,
                    success: true
                });
                await sleep(2000); // تأخير بين المشاهدات
            } catch (error) {
                results.push({
                    id: status.id,
                    sender: status.jid,
                    success: false,
                    error: error.message
                });
            }
        }
        
        return {
            total: statuses.length,
            viewed: results.filter(r => r.success).length,
            results
        };
    } catch (error) {
        throw new Error(`فشل مشاهدة الحالات: ${error.message}`);
    }
}

// ============= وظائف مساعدة =============

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function getAccount(phone) {
    return sessions.get(phone);
}

export function getQR(phone) {
    const data = pairingData.get(phone);
    if (data && (Date.now() - data.timestamp) < 120000) {
        return data.qr;
    }
    return null;
}

export function accounts() {
    return [...sessions.keys()];
}

export function getAccountStatus(phone) {
    const sock = sessions.get(phone);
    if (!sock) return "disconnected";
    return sock.user ? "connected" : "connecting";
}

export async function disconnectAccount(phone) {
    const sock = sessions.get(phone);
    if (sock) {
        try {
            await sock.logout();
            sessions.delete(phone);
            return true;
        } catch (error) {
            throw new Error(`فشل قطع الاتصال: ${error.message}`);
        }
    }
    throw new Error("الحساب غير موجود");
}

export default {
    addAccount,
    getAccount,
    getQR,
    accounts,
    getAccountStatus,
    disconnectAccount,
    sendBroadcast,
    sendStatus,
    fetchStatuses,
    viewStatus,
    viewAllStatuses,
    getStatusViews
};
