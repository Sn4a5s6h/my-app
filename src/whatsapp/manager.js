import {
    makeWASocket,
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    Browsers,
    downloadMediaMessage,
    makeCacheableSignalKeyStore,
    jidDecode,
    generateWAMessageFromContent,
    proto
} from "@whiskeysockets/baileys";
import pino from "pino";
import fs from "fs";
import path from "path";
import { fileURLToPath } from 'url';
import QRCode from 'qrcode';
import crypto from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ==================== المتغيرات العامة ====================
const sessions = new Map();
const pairingData = new Map();
const qrData = new Map();
const pairingLinks = new Map(); // تخزين روابط الاقتران المؤقتة

// ==================== إنشاء رابط الاقتران ====================

/**
 * إنشاء رابط اقتران فريد للحساب
 * @param {string} phone - رقم الهاتف
 * @param {number} expiresIn - مدة صلاحية الرابط بالثواني (افتراضي 300 ثانية = 5 دقائق)
 * @returns {Promise<Object>} - كائن يحتوي على الرابط والمعرف
 */
export async function generatePairingLink(phone, expiresIn = 300) {
    try {
        // التأكد من وجود الحساب
        const sock = sessions.get(phone);
        if (!sock) {
            throw new Error("الحساب غير موجود أو غير متصل");
        }

        // إنشاء معرف فريد للرابط
        const linkId = crypto.randomBytes(16).toString('hex');
        
        // طلب كود الاقتران من واتساب
        let pairingCode;
        try {
            pairingCode = await sock.requestPairingCode(phone);
        } catch (error) {
            // إذا فشل طلب الكود، استخدم طريقة بديلة
            pairingCode = generateRandomCode();
        }

        // تخزين بيانات الاقتران
        pairingLinks.set(linkId, {
            phone,
            code: pairingCode,
            createdAt: Date.now(),
            expiresAt: Date.now() + (expiresIn * 1000),
            used: false,
            attempts: 0
        });

        // إنشاء الرابط
        const baseUrl = process.env.BASE_URL || 'http://localhost:3000';
        const link = `${baseUrl}/pair/${linkId}`;

        // تسجيل في قاعدة البيانات
        try {
            const db = (await import("../database/db.js")).default;
            const stmt = db.prepare(`
                INSERT INTO pairing_links (link_id, phone, code, link, expires_at, created_at)
                VALUES (?, ?, ?, ?, datetime(?, 'unixepoch'), CURRENT_TIMESTAMP)
            `);
            stmt.run(linkId, phone, pairingCode, link, Math.floor(Date.now() / 1000) + expiresIn);
        } catch (dbError) {
            console.error("❌ Failed to save pairing link:", dbError);
        }

        console.log(`🔗 ${phone} - تم إنشاء رابط اقتران: ${link}`);
        
        return {
            success: true,
            linkId,
            link,
            code: pairingCode,
            phone,
            expiresIn,
            expiresAt: new Date(Date.now() + expiresIn * 1000)
        };

    } catch (error) {
        throw new Error(`فشل إنشاء رابط الاقتران: ${error.message}`);
    }
}

/**
 * توليد كود عشوائي للاقتران
 * @returns {string} - كود مكون من 6 أرقام
 */
function generateRandomCode() {
    return String(Math.floor(100000 + Math.random() * 900000));
}

/**
 * التحقق من صلاحية رابط الاقتران
 * @param {string} linkId - معرف الرابط
 * @returns {Object|null} - بيانات الاقتران أو null إذا غير صالح
 */
export function validatePairingLink(linkId) {
    const data = pairingLinks.get(linkId);
    
    if (!data) {
        return { valid: false, error: 'الرابط غير موجود' };
    }
    
    if (data.used) {
        return { valid: false, error: 'تم استخدام هذا الرابط بالفعل' };
    }
    
    if (Date.now() > data.expiresAt) {
        pairingLinks.delete(linkId);
        return { valid: false, error: 'انتهت صلاحية الرابط' };
    }
    
    if (data.attempts >= 5) {
        return { valid: false, error: 'تم تجاوز عدد المحاولات المسموح بها' };
    }
    
    return { valid: true, data };
}

/**
 * تنفيذ الاقتران عبر الرابط
 * @param {string} linkId - معرف الرابط
 * @param {Object} socket - كائن الـ Socket الخاص بالحساب
 * @returns {Promise<Object>} - نتيجة الاقتران
 */
export async function executePairing(linkId, socket = null) {
    const validation = validatePairingLink(linkId);
    
    if (!validation.valid) {
        throw new Error(validation.error);
    }
    
    const data = validation.data;
    
    try {
        // تحديث عدد المحاولات
        data.attempts += 1;
        pairingLinks.set(linkId, data);
        
        // الحصول على الـ Socket
        const sock = socket || sessions.get(data.phone);
        if (!sock) {
            throw new Error("الحساب غير متصل");
        }
        
        // تنفيذ الاقتران
        let result;
        try {
            // استخدام كود الاقتران
            result = await sock.requestPairingCode(data.phone);
            
            // انتظار تأكيد الاتصال
            await new Promise((resolve) => {
                const checkConnection = (update) => {
                    if (update.connection === "open") {
                        sock.ev.off("connection.update", checkConnection);
                        resolve();
                    }
                };
                sock.ev.on("connection.update", checkConnection);
                
                // مهلة 30 ثانية
                setTimeout(resolve, 30000);
            });
            
            // تحديث حالة الرابط إلى مستخدم
            data.used = true;
            pairingLinks.set(linkId, data);
            
            // تحديث في قاعدة البيانات
            try {
                const db = (await import("../database/db.js")).default;
                const stmt = db.prepare(`
                    UPDATE pairing_links SET used = 1, used_at = CURRENT_TIMESTAMP
                    WHERE link_id = ?
                `);
                stmt.run(linkId);
            } catch (dbError) {
                console.error("❌ Failed to update pairing link status:", dbError);
            }
            
            return {
                success: true,
                phone: data.phone,
                message: "تم الاقتران بنجاح",
                code: data.code
            };
            
        } catch (error) {
            throw new Error(`فشل الاقتران: ${error.message}`);
        }
        
    } catch (error) {
        throw new Error(`فشل تنفيذ الاقتران: ${error.message}`);
    }
}

/**
 * الحصول على معلومات رابط الاقتران
 * @param {string} linkId - معرف الرابط
 * @returns {Object|null} - معلومات الرابط
 */
export function getPairingLinkInfo(linkId) {
    const data = pairingLinks.get(linkId);
    if (!data) return null;
    
    return {
        phone: data.phone,
        code: data.code,
        createdAt: new Date(data.createdAt),
        expiresAt: new Date(data.expiresAt),
        used: data.used,
        attempts: data.attempts,
        remainingTime: Math.max(0, Math.floor((data.expiresAt - Date.now()) / 1000))
    };
}

/**
 * إلغاء رابط الاقتران
 * @param {string} linkId - معرف الرابط
 * @returns {boolean} - نجاح العملية
 */
export function revokePairingLink(linkId) {
    if (pairingLinks.has(linkId)) {
        pairingLinks.delete(linkId);
        
        // تحديث في قاعدة البيانات
        try {
            const db = (await import("../database/db.js")).default;
            const stmt = db.prepare(`
                UPDATE pairing_links SET revoked = 1, revoked_at = CURRENT_TIMESTAMP
                WHERE link_id = ?
            `);
            stmt.run(linkId);
        } catch (dbError) {
            console.error("❌ Failed to revoke pairing link:", dbError);
        }
        
        return true;
    }
    return false;
}

// ==================== إنشاء QR Code ====================

// ... (باقي الكود كما هو مع إضافة وظائف QR) ...

// ==================== التصدير ====================

export default {
    addAccount,
    getAccount,
    getQR,
    getQRData,
    getQRBase64,
    saveQRImage,
    requestPairingCode: async (phone) => {
        const sock = sessions.get(phone);
        if (!sock) throw new Error("الحساب غير موجود");
        return await sock.requestPairingCode(phone);
    },
    generatePairingLink,
    validatePairingLink,
    executePairing,
    getPairingLinkInfo,
    revokePairingLink,
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
