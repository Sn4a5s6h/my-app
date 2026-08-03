import fs from "fs";
import path from "path";
import { exec } from "child_process";
import { promisify } from "util";
import db from "../database/db.js";

const execAsync = promisify(exec);

// ====== إنشاء نسخة احتياطية ======
export async function createBackup() {
    const backupDir = "backups";
    if (!fs.existsSync(backupDir)) {
        fs.mkdirSync(backupDir, { recursive: true });
    }
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupName = `backup_${timestamp}`;
    const backupPath = path.join(backupDir, backupName);
    
    // إنشاء مجلد النسخة
    fs.mkdirSync(backupPath);
    
    try {
        // نسخ قاعدة البيانات
        fs.copyFileSync('database.sqlite', path.join(backupPath, 'database.sqlite'));
        
        // نسخ مجلد الجلسات
        if (fs.existsSync('sessions')) {
            fs.cpSync('sessions', path.join(backupPath, 'sessions'), { recursive: true });
        }
        
        // نسخ الميديا
        if (fs.existsSync('media')) {
            fs.cpSync('media', path.join(backupPath, 'media'), { recursive: true });
        }
        
        // نسخ الإعدادات
        if (fs.existsSync('.env')) {
            fs.copyFileSync('.env', path.join(backupPath, '.env.backup'));
        }
        
        // حفظ معلومات النسخة
        const info = {
            timestamp: new Date().toISOString(),
            version: '2.0.0',
            files: {
                database: 'database.sqlite',
                sessions: 'sessions/',
                media: 'media/',
                env: '.env.backup'
            }
        };
        
        fs.writeFileSync(
            path.join(backupPath, 'backup_info.json'),
            JSON.stringify(info, null, 2)
        );
        
        // ضغط النسخة
        await execAsync(`cd ${backupDir} && tar -czf ${backupName}.tar.gz ${backupName}`);
        
        // حذف المجلد غير المضغوط
        fs.rmSync(backupPath, { recursive: true, force: true });
        
        return {
            success: true,
            backupPath: `${backupName}.tar.gz`,
            size: fs.statSync(path.join(backupDir, `${backupName}.tar.gz`)).size
        };
        
    } catch (error) {
        console.error('❌ Backup failed:', error);
        throw new Error(`فشل النسخ الاحتياطي: ${error.message}`);
    }
}

// ====== استعادة نسخة احتياطية ======
export async function restoreBackup(backupFile) {
    const backupDir = "backups";
    const backupPath = path.join(backupDir, backupFile);
    
    if (!fs.existsSync(backupPath)) {
        throw new Error("النسخة الاحتياطية غير موجودة");
    }
    
    try {
        // فك الضغط
        const extractDir = path.join(backupDir, 'temp_restore');
        await execAsync(`mkdir -p ${extractDir}`);
        await execAsync(`tar -xzf ${backupPath} -C ${extractDir}`);
        
        // العثور على المجلد المستخرج
        const files = fs.readdirSync(extractDir);
        const backupFolder = files.find(f => f.startsWith('backup_'));
        
        if (!backupFolder) {
            throw new Error("تنسيق النسخة الاحتياطية غير صحيح");
        }
        
        const sourcePath = path.join(extractDir, backupFolder);
        
        // استعادة قاعدة البيانات (نسخ احتياطي للقاعدة الحالية)
        if (fs.existsSync('database.sqlite')) {
            fs.copyFileSync('database.sqlite', 'database.sqlite.bak');
        }
        fs.copyFileSync(
            path.join(sourcePath, 'database.sqlite'),
            'database.sqlite'
        );
        
        // استعادة الجلسات
        if (fs.existsSync(path.join(sourcePath, 'sessions'))) {
            if (fs.existsSync('sessions')) {
                fs.rmSync('sessions', { recursive: true, force: true });
            }
            fs.cpSync(
                path.join(sourcePath, 'sessions'),
                'sessions',
                { recursive: true }
            );
        }
        
        // تنظيف
        fs.rmSync(extractDir, { recursive: true, force: true });
        
        return {
            success: true,
            message: "تم استعادة النسخة الاحتياطية بنجاح"
        };
        
    } catch (error) {
        console.error('❌ Restore failed:', error);
        throw new Error(`فشل استعادة النسخة: ${error.message}`);
    }
}

// ====== الحصول على قائمة النسخ الاحتياطية ======
export function getBackupList() {
    const backupDir = "backups";
    if (!fs.existsSync(backupDir)) {
        return [];
    }
    
    const files = fs.readdirSync(backupDir);
    const backups = [];
    
    for (const file of files) {
        if (file.endsWith('.tar.gz')) {
            const stats = fs.statSync(path.join(backupDir, file));
            backups.push({
                name: file,
                size: stats.size,
                created: stats.mtime,
                sizeFormatted: formatBytes(stats.size)
            });
        }
    }
    
    return backups.sort((a, b) => b.created - a.created);
}

// ====== وظائف مساعدة ======
function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

// ====== نسخ احتياطي تلقائي ======
export function startAutoBackup(intervalHours = 24) {
    // إنشاء نسخة فورية
    createBackup().then(result => {
        console.log(`✅ Initial backup created: ${result.backupPath}`);
    }).catch(error => {
        console.error('❌ Initial backup failed:', error);
    });
    
    // جدولة النسخ التلقائي
    const interval = intervalHours * 60 * 60 * 1000;
    setInterval(() => {
        createBackup().then(result => {
            console.log(`✅ Auto-backup created: ${result.backupPath}`);
        }).catch(error => {
            console.error('❌ Auto-backup failed:', error);
        });
    }, interval);
    
    console.log(`🔄 Auto-backup scheduled every ${intervalHours} hours`);
}

export default {
    createBackup,
    restoreBackup,
    getBackupList,
    startAutoBackup
};
