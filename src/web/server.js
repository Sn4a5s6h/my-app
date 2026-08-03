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
    getStatusViews
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
            fs.mkdirSync(dir);
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

// ====== الصفحة الرئيسية ======
app.get("/", async (req, res) => {
    const accs = accounts();
    const accountsData = [];
    
    for (const phone of accs) {
        const status = getAccountStatus(phone);
        accountsData.push({ phone, status });
    }
    
    // جلب آخر الرسائل
    const messages = db.prepare(`
        SELECT * FROM messages 
        ORDER BY created_at DESC 
        LIMIT 50
    `).all();
    
    // جلب آخر الحالات
    const statuses = db.prepare(`
        SELECT * FROM statuses 
        ORDER BY created_at DESC 
        LIMIT 20
    `).all();
    
    res.render("index", { 
        accounts: accountsData,
        messages,
        statuses,
        title: "WhatsApp Manager"
    });
});

// ====== صفحة الإرسال الجماعي ======
app.get("/broadcast", async (req, res) => {
    const accs = accounts();
    res.render("broadcast", { 
        accounts: accs,
        title: "إرسال رسالة جماعية"
    });
});

// ====== صفحة الحالات ======
app.get("/status", async (req, res) => {
    const accs = accounts();
    const statuses = db.prepare(`
        SELECT * FROM statuses 
        ORDER BY created_at DESC 
        LIMIT 30
    `).all();
    
    res.render("status", { 
        accounts: accs,
        statuses,
        title: "إدارة الحالات"
    });
});

// ====== API: إرسال رسالة جماعية ======
app.post("/api/broadcast", async (req, res) => {
    const { phone, numbers, message } = req.body;
    
    if (!phone || !numbers || !message) {
        return res.status(400).json({ 
            error: "جميع الحقول مطلوبة" 
        });
    }
    
    const numberList = numbers.split(",").map(n => n.trim());
    
    try {
        const result = await sendBroadcast(phone, numberList, message);
        res.json(result);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ====== API: نشر حالة ======
app.post("/api/status/send", upload.single("media"), async (req, res) => {
    const { phone, message } = req.body;
    const mediaPath = req.file ? req.file.path : null;
    
    if (!phone || !message) {
        return res.status(400).json({ 
            error: "رقم الهاتف ونص الحالة مطلوبان" 
        });
    }
    
    try {
        const result = await sendStatus(phone, message, mediaPath);
        res.json(result);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ====== API: مشاهدة جميع الحالات ======
app.post("/api/status/view-all", async (req, res) => {
    const { phone } = req.body;
    
    if (!phone) {
        return res.status(400).json({ error: "رقم الهاتف مطلوب" });
    }
    
    try {
        const result = await viewAllStatuses(phone);
        res.json(result);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ====== API: مشاهدات حالة ======
app.get("/api/status/views/:statusId", async (req, res) => {
    const { statusId } = req.params;
    const { phone } = req.query;
    
    if (!phone) {
        return res.status(400).json({ error: "رقم الهاتف مطلوب" });
    }
    
    try {
        const result = await getStatusViews(phone, statusId);
        res.json(result);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ====== API: قائمة الحالات ======
app.get("/api/status/list/:phone?", async (req, res) => {
    const { phone } = req.params;
    
    let query = `SELECT * FROM statuses`;
    const params = [];
    
    if (phone) {
        query += ` WHERE phone = ?`;
        params.push(phone);
    }
    
    query += ` ORDER BY created_at DESC LIMIT 50`;
    
    const statuses = db.prepare(query).all(...params);
    res.json(statuses);
});

// ====== الوظائف الأخرى ======
app.get("/add-account", (req, res) => {
    res.render("add-account", { title: "إضافة حساب جديد" });
});

app.post("/api/add-account", async (req, res) => {
    const { phone } = req.body;
    
    if (!phone) {
        return res.status(400).json({ error: "رقم الهاتف مطلوب" });
    }
    
    try {
        await addAccount(phone);
        setTimeout(async () => {
            const qr = getQR(phone);
        }, 3000);
        
        res.json({ 
            success: true, 
            message: `تم إضافة الحساب ${phone}`,
            qr: getQR(phone)
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.post("/api/add-account-pairing", async (req, res) => {
    const { phone, code } = req.body;
    
    if (!phone || !code) {
        return res.status(400).json({ error: "رقم الهاتف وكود الاقتران مطلوبان" });
    }
    
    try {
        await addAccount(phone, code);
        res.json({ 
            success: true, 
            message: `تم الاقتران بالحساب ${phone} بنجاح` 
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get("/api/qr/:phone", async (req, res) => {
    const { phone } = req.params;
    const qr = getQR(phone);
    
    if (qr) {
        res.json({ qr });
    } else {
        res.status(404).json({ error: "QR Code غير موجود" });
    }
});

app.post("/api/disconnect", async (req, res) => {
    const { phone } = req.body;
    
    if (!phone) {
        return res.status(400).json({ error: "رقم الهاتف مطلوب" });
    }
    
    try {
        await disconnectAccount(phone);
        res.json({ success: true, message: "تم قطع الاتصال" });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get("/api/status/:phone", async (req, res) => {
    const { phone } = req.params;
    const status = getAccountStatus(phone);
    res.json({ phone, status });
});

app.get("/api/accounts", async (req, res) => {
    const accs = accounts();
    const data = [];
    
    for (const phone of accs) {
        data.push({
            phone,
            status: getAccountStatus(phone)
        });
    }
    
    res.json(data);
});

app.get("/api/messages/:phone?", async (req, res) => {
    const { phone } = req.params;
    
    let query = `SELECT * FROM messages`;
    const params = [];
    
    if (phone) {
        query += ` WHERE phone = ?`;
        params.push(phone);
    }
    
    query += ` ORDER BY created_at DESC LIMIT 100`;
    
    const messages = db.prepare(query).all(...params);
    res.json(messages);
});

export default app;
