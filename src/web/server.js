import express from "express";
import path from "path";
import { fileURLToPath } from 'url';
import { 
    addAccount, 
    accounts, 
    getQR, 
    getAccountStatus,
    disconnectAccount,
    sendBroadcast,
    sendStatus,
    viewAllStatuses,
    getStatusViews,
    generatePairingLink,
    executePairing,
    getPairingLinkInfo,
    revokePairingLink,
    getQRData
} from "../whatsapp/manager.js";
import db from "../database/db.js";
import multer from "multer";
import fs from "fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// ====== إعدادات الميديا ======
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        const dir = "uploads";
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        cb(null, dir);
    },
    filename: (req, file, cb) => {
        cb(null, `${Date.now()}_${file.originalname}`);
    }
});
const upload = multer({ storage });

// ====== إعدادات الـ View ======
app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "../views"));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, "../public")));
app.use("/uploads", express.static("uploads"));
app.use("/qr-codes", express.static("qr-codes"));

// ==================== صفحة الاقتران بالرابط ====================

/**
 * صفحة الاقتران - عند الضغط على الرابط
 */
app.get("/pair/:linkId", async (req, res) => {
    const { linkId } = req.params;
    
    try {
        // التحقق من صلاحية الرابط
        const validation = await import("../whatsapp/manager.js").then(m => m.validatePairingLink(linkId));
        
        if (!validation.valid) {
            return res.render("pair-error", {
                error: validation.error,
                title: "خطأ في الاقتران"
            });
        }
        
        const info = await import("../whatsapp/manager.js").then(m => m.getPairingLinkInfo(linkId));
        
        // عرض صفحة الاقتران
        res.render("pair", {
            linkId,
            phone: info.phone,
            code: info.code,
            remainingTime: info.remainingTime,
            title: "اقتران واتساب"
        });
        
    } catch (error) {
        res.render("pair-error", {
            error: error.message,
            title: "خطأ في الاقتران"
        });
    }
});

/**
 * تنفيذ الاقتران
 */
app.post("/api/pair/:linkId", async (req, res) => {
    const { linkId } = req.params;
    
    try {
        const result = await executePairing(linkId);
        res.json(result);
    } catch (error) {
        res.status(400).json({ 
            success: false, 
            error: error.message 
        });
    }
});

/**
 * الحصول على معلومات الرابط
 */
app.get("/api/pair/info/:linkId", async (req, res) => {
    const { linkId } = req.params;
    const info = getPairingLinkInfo(linkId);
    
    if (!info) {
        return res.status(404).json({ error: "الرابط غير موجود" });
    }
    
    res.json(info);
});

/**
 * إنشاء رابط اقتران جديد
 */
app.post("/api/pair/generate", async (req, res) => {
    const { phone, expiresIn = 300 } = req.body;
    
    if (!phone) {
        return res.status(400).json({ error: "رقم الهاتف مطلوب" });
    }
    
    try {
        const result = await generatePairingLink(phone, expiresIn);
        res.json(result);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

/**
 * إلغاء رابط الاقتران
 */
app.delete("/api/pair/:linkId", async (req, res) => {
    const { linkId } = req.params;
    
    const result = revokePairingLink(linkId);
    
    if (result) {
        res.json({ success: true, message: "تم إلغاء الرابط" });
    } else {
        res.status(404).json({ error: "الرابط غير موجود" });
    }
});

// ==================== الصفحة الرئيسية ====================

app.get("/", async (req, res) => {
    const accs = accounts();
    const accountsData = [];
    
    for (const phone of accs) {
        const status = getAccountStatus(phone);
        accountsData.push({ phone, status });
    }
    
    const messages = db.prepare(`
        SELECT * FROM messages 
        ORDER BY created_at DESC 
        LIMIT 50
    `).all();
    
    const statuses = db.prepare(`
        SELECT * FROM statuses 
        ORDER BY created_at DESC 
        LIMIT 20
    `).all();
    
    // جلب روابط الاقتران النشطة
    const pairingLinks = db.prepare(`
        SELECT * FROM pairing_links 
        WHERE used = 0 AND revoked = 0 AND expires_at > datetime('now')
        ORDER BY created_at DESC
    `).all();
    
    res.render("index", { 
        accounts: accountsData,
        messages,
        statuses,
        pairingLinks,
        title: "WhatsApp Manager"
    });
});

// ==================== باقي المسارات ====================

// ... (باقي المسارات كما هي) ...

export default app;
