import {
    makeWASocket,
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    Browsers,
    downloadMediaMessage
} from "@whiskeysockets/baileys";
import pino from "pino";
import fs from "fs";
import path from "path";
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ==================== المتغيرات العامة ====================
const sessions = new Map();
const pairingData = new Map();
const statusViewers = new Map();

// ==================== الوظائف الأساسية ====================

/**
 * إضافة حساب واتساب جديد
 * @param {string} phone - رقم الهاتف
 * @param {string|null} pairingCode - كود الاقتران (اختياري)
 * @returns {Promise<Object>} - كائن الـ Socket
 */
export async function addAccount(phone, pairingCode = null) {
    const folder = `sessions/${phone}`;
    
    if (!fs.existsSync(folder)) {
        fs.mkdirSync(folder, { recursive: true });
    }

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

    // ====== حدث تحديث بيانات المصادقة ======
    sock.ev.on("creds.update", saveCreds);

    // ====== حدث تحديث الاتصال ======
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
                // تحديث حالة الحساب في قاعدة البيانات
                try {
                    const db = (await import("../database/db.js")).default;
                    const stmt = db.prepare(`
                        UPDATE accounts SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE phone = ?
                    `);
                    stmt.run("disconnected", phone);
                } catch (error) {
                    console.error("❌ Failed to update account status:", error);
                }
            }
        }

        if (connection === "open") {
            console.log(`✅ ${phone} - تم الاتصال بنجاح!`);
            // تحديث حالة الحساب في قاعدة البيانات
            try {
                const db = (await import("../database/db.js")).default;
                const stmt = db.prepare(`
                    INSERT OR REPLACE INTO accounts (phone, status, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                `);
                stmt.run(phone, "connected");
            } catch (error) {
                console.error("❌ Failed to update account status:", error);
            }
        }

        if (qr) {
            console.log(`📸 ${phone} - QR Code generated`);
            pairingData.set(phone, { qr, timestamp: Date.now() });
        }
    });

    // ====== حدث استقبال رسائل جديدة ======
    sock.ev.on("messages.upsert", async (data) => {
        const message = data.messages[0];
        if (!message.key.fromMe && message.message) {
            await handleIncomingMessage(phone, message, sock);
        }
    });

    // ====== إذا تم طلب Pairing Code ======
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

// ==================== معالجة الرسائل الواردة ====================

/**
 * معالجة الرسائل الواردة
 * @param {string} phone - رقم الهاتف
 * @param {Object} message - كائن الرسالة
 * @param {Object} sock - كائن الـ Socket
 */
async function handleIncomingMessage(phone, message, sock) {
    console.log(`📨 ${phone} - رسالة جديدة:`, message);
    
    try {
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
        try {
            const botModule = await import("../telegram/bot.js");
            const bot = botModule.getBot();
            if (bot) {
                const adminId = (await import("../config/env.js")).default.ADMIN_ID;
                const msg = `📩 رسالة جديدة\n📱 حساب: ${phone}\n👤 من: ${sender}\n💬 ${text}`;
                await bot.telegram.sendMessage(adminId, msg).catch(() => {});
            }
        } catch (error) {
            console.error("❌ Failed to send Telegram notification:", error);
        }

        // معالجة الرد التلقائي (إذا كان مفعلاً)
        try {
            const autoReplyModule = await import("../auto-reply/rules.js");
            if (autoReplyModule.processAutoReply) {
                await autoReplyModule.processAutoReply(phone, message, sender);
            }
        } catch (error) {
            // تجاهل خطأ auto-reply إذا كان غير موجود
        }

    } catch (error) {
        console.error("❌ Error handling incoming message:", error);
    }
}

// ==================== تنزيل الميديا ====================

/**
 * تنزيل الميديا من الرسالة
 * @param {Object} message - كائن الرسالة
 * @param {Object} sock - كائن الـ Socket
 * @returns {Promise<string|null>} - مسار الملف المحفوظ
 */
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
            fs.mkdirSync(mediaDir, { recursive: true });
        }
        
        const fileName = `${Date.now()}_${message.key.id}.jpg`;
        const filePath = path.join(mediaDir, fileName);
        fs.writeFileSync(filePath, buffer);
        
        return filePath;
    } catch (error) {
        console.error("❌ Failed to download media:", error);
        return null;
    }
}

// ==================== إرسال الرسائل ====================

/**
 * إرسال رسالة نصية
 * @param {string} phone - رقم حساب المرسل
 * @param {string} to - رقم المستقبل
 * @param {string} message - نص الرسالة
 * @returns {Promise<Object>} - نتيجة الإرسال
 */
export async function sendMessage(phone, to, message) {
    const sock = sessions.get(phone);
    if (!sock) {
        throw new Error("الحساب غير موجود أو غير متصل");
    }

    try {
        const jid = to.includes("@") ? to : `${to}@s.whatsapp.net`;
        const result = await sock.sendMessage(jid, { text: message });
        
        // حفظ الرسالة في قاعدة البيانات
        try {
            const db = (await import("../database/db.js")).default;
            const stmt = db.prepare(`
                INSERT INTO messages (phone, direction, sender, receiver, message, status)
                VALUES (?, ?, ?, ?, ?, ?)
            `);
            stmt.run(phone, "outgoing", phone + "@s.whatsapp.net", jid, message, "sent");
        } catch (dbError) {
            console.error("❌ Failed to save message:", dbError);
        }
        
        return result;
    } catch (error) {
        throw new Error(`فشل إرسال الرسالة: ${error.message}`);
    }
}

/**
 * إرسال رسالة جماعية
 * @param {string} phone - رقم حساب المرسل
 * @param {string[]} numbers - قائمة الأرقام المستلمة
 * @param {string} message - نص الرسالة
 * @param {string|null} mediaPath - مسار الميديا (اختياري)
 * @returns {Promise<Object>} - نتائج الإرسال
 */
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
                // إرسال مع ميديا
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
            
            // تأخير بين الرسائل
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

// ==================== إدارة الحالات (Status) ====================

/**
 * نشر حالة جديدة
 * @param {string} phone - رقم الحساب
 * @param {string} message - نص الحالة
 * @param {string|null} mediaPath - مسار الميديا (اختياري)
 * @param {string[]|null} recipients - قائمة المستلمين (اختياري)
 * @returns {Promise<Object>} - نتيجة النشر
 */
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
            
            if (['.jpg', '.jpeg', '.png', '.gif'].includes(ext)) {
                statusMessage = await sock.sendMessage(jid, {
                    image: mediaBuffer,
                    caption: message,
                    ephemeralExpiration: 86400
                }, {
                    statusJidList: recipients || [],
                    broadcast: true
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
        try {
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
        } catch (dbError) {
            console.error("❌ Failed to save status:", dbError);
        }

        return {
            success: true,
            statusId: statusMessage.key.id,
            message: "تم نشر الحالة بنجاح"
        };

    } catch (error) {
        throw new Error(`فشل نشر الحالة: ${error.message}`);
    }
}

/**
 * مشاهدة جميع الحالات
 * @param {string} phone - رقم الحساب
 * @returns {Promise<Object>} - نتائج المشاهدة
 */
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
                await sleep(2000);
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

/**
 * مشاهدة حالة معينة
 * @param {string} phone - رقم الحساب
 * @param {string} statusId - معرف الحالة
 * @returns {Promise<Object>} - نتيجة المشاهدة
 */
export async function viewStatus(phone, statusId) {
    const sock = sessions.get(phone);
    if (!sock) {
        throw new Error("الحساب غير موجود");
    }

    try {
        await sock.readStatus(statusId);
        
        // تسجيل المشاهدة
        try {
            const db = (await import("../database/db.js")).default;
            const stmt = db.prepare(`
                INSERT INTO status_views (phone, status_id, viewer, viewed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            `);
            stmt.run(phone, statusId, phone + "@s.whatsapp.net");
        } catch (dbError) {
            console.error("❌ Failed to save status view:", dbError);
        }
        
        return {
            success: true,
            message: "تم مشاهدة الحالة"
        };
    } catch (error) {
        throw new Error(`فشل مشاهدة الحالة: ${error.message}`);
    }
}

/**
 * جلب مشاهدات حالة معينة
 * @param {string} phone - رقم الحساب
 * @param {string} statusId - معرف الحالة
 * @returns {Promise<Object>} - قائمة المشاهدات
 */
export async function getStatusViews(phone, statusId) {
    try {
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
    } catch (error) {
        throw new Error(`فشل جلب المشاهدات: ${error.message}`);
    }
}

// ==================== وظائف مساعدة ====================

/**
 * تأخير التنفيذ
 * @param {number} ms - مدة التأخير بالمللي ثانية
 * @returns {Promise<void>}
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ==================== وظائف الحصول على البيانات ====================

/**
 * الحصول على كائن الحساب
 * @param {string} phone - رقم الهاتف
 * @returns {Object|null} - كائن الـ Socket
 */
export function getAccount(phone) {
    return sessions.get(phone);
}

/**
 * الحصول على QR Code للحساب
 * @param {string} phone - رقم الهاتف
 * @returns {string|null} - QR Code
 */
export function getQR(phone) {
    const data = pairingData.get(phone);
    if (data && (Date.now() - data.timestamp) < 120000) {
        return data.qr;
    }
    return null;
}

/**
 * الحصول على قائمة الحسابات النشطة
 * @returns {string[]} - قائمة الأرقام
 */
export function accounts() {
    return [...sessions.keys()];
}

/**
 * الحصول على حالة الحساب
 * @param {string} phone - رقم الهاتف
 * @returns {string} - حالة الحساب
 */
export function getAccountStatus(phone) {
    const sock = sessions.get(phone);
    if (!sock) return "disconnected";
    return sock.user ? "connected" : "connecting";
}

/**
 * قطع الاتصال بحساب
 * @param {string} phone - رقم الهاتف
 * @returns {Promise<boolean>} - نجاح العملية
 */
export async function disconnectAccount(phone) {
    const sock = sessions.get(phone);
    if (sock) {
        try {
            await sock.logout();
            sessions.delete(phone);
            
            // تحديث حالة الحساب في قاعدة البيانات
            try {
                const db = (await import("../database/db.js")).default;
                const stmt = db.prepare(`
                    UPDATE accounts SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE phone = ?
                `);
                stmt.run("disconnected", phone);
            } catch (dbError) {
                console.error("❌ Failed to update account status:", dbError);
            }
            
            return true;
        } catch (error) {
            throw new Error(`فشل قطع الاتصال: ${error.message}`);
        }
    }
    throw new Error("الحساب غير موجود");
}

// ==================== التصدير النهائي ====================

export default {
    addAccount,
    getAccount,
    getQR,
    accounts,
    getAccountStatus,
    disconnectAccount,
    sendMessage,
    sendBroadcast,
    sendStatus,
    viewAllStatuses,
    viewStatus,
    getStatusViews
};
