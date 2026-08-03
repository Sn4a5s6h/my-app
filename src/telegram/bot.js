// إضافة الأوامر الجديدة في دالة startBot

// ====== جدولة رسالة ======
bot.command("schedule", async ctx => {
    const args = ctx.message.text.split(" ");
    // schedule [phone] [type] [recipient] [datetime] [message]
    // مثال: schedule 966512345678 single 966511111111 2024-01-01T10:00 مرحبا
    
    if (args.length < 6) {
        return ctx.reply(
            "❌ استخدام: /schedule [رقم حسابك] [نوع: single/broadcast/status] [مستلم/أرقام] [التاريخ] [الرسالة]\n" +
            "مثال: /schedule 966512345678 single 966511111111 2024-01-01T10:00 مرحبا"
        );
    }
    
    const phone = args[1];
    const type = args[2];
    const recipient = args[3];
    const datetime = args[4];
    const message = args.slice(5).join(" ");
    
    try {
        const { addScheduledTask } = await import('../scheduler/scheduler.js');
        const taskId = addScheduledTask({
            phone,
            type,
            recipient,
            message,
            scheduled_at: datetime
        });
        
        await ctx.reply(`✅ تم جدولة الرسالة\n🆔 معرف المهمة: ${taskId}\n📅 التاريخ: ${datetime}`);
    } catch (error) {
        await ctx.reply(`❌ فشل الجدولة: ${error.message}`);
    }
});

// ====== عرض المهام المجدولة ======
bot.command("scheduled", async ctx => {
    try {
        const { getScheduledTasks } = await import('../scheduler/scheduler.js');
        const tasks = getScheduledTasks('pending');
        
        if (tasks.length === 0) {
            return ctx.reply("📭 لا توجد مهام مجدولة");
        }
        
        let reply = "⏰ المهام المجدولة:\n\n";
        for (const task of tasks.slice(0, 10)) {
            reply += `🆔 #${task.id}\n`;
            reply += `📱 ${task.phone}\n`;
            reply += `📝 ${task.message.substring(0, 30)}...\n`;
            reply += `📅 ${new Date(task.scheduled_at).toLocaleString()}\n\n`;
        }
        if (tasks.length > 10) {
            reply += `... و ${tasks.length - 10} أخرى`;
        }
        
        await ctx.reply(reply);
    } catch (error) {
        await ctx.reply(`❌ خطأ: ${error.message}`);
    }
});

// ====== إلغاء مهمة مجدولة ======
bot.command("cancel_schedule", async ctx => {
    const taskId = ctx.message.text.split(" ")[1];
    
    if (!taskId) {
        return ctx.reply("❌ يرجى كتابة معرف المهمة\nمثال: /cancel_schedule 5");
    }
    
    try {
        const { cancelScheduledTask } = await import('../scheduler/scheduler.js');
        cancelScheduledTask(parseInt(taskId));
        await ctx.reply(`✅ تم إلغاء المهمة #${taskId}`);
    } catch (error) {
        await ctx.reply(`❌ فشل الإلغاء: ${error.message}`);
    }
});

// ====== إضافة قاعدة رد تلقائي ======
bot.command("add_reply", async ctx => {
    const args = ctx.message.text.split(" ");
    // add_reply [phone] [trigger] [reply]
    // مثال: add_reply 966512345678 مرحبا أهلا بك
    
    if (args.length < 4) {
        return ctx.reply(
            "❌ استخدام: /add_reply [رقم حسابك] [كلمة محفزة] [الرد]\n" +
            "مثال: /add_reply 966512345678 مرحبا أهلا بك"
        );
    }
    
    const phone = args[1];
    const trigger = args[2];
    const reply = args.slice(3).join(" ");
    
    try {
        const { addReplyRule } = await import('../auto-reply/rules.js');
        const ruleId = addReplyRule({ phone, trigger, reply });
        await ctx.reply(`✅ تم إضافة قاعدة رد جديدة\n🆔 معرف القاعدة: ${ruleId}\n🔹 الكلمة: ${trigger}\n🔸 الرد: ${reply}`);
    } catch (error) {
        await ctx.reply(`❌ فشل الإضافة: ${error.message}`);
    }
});

// ====== عرض قواعد الردود ======
bot.command("reply_rules", async ctx => {
    const phone = ctx.message.text.split(" ")[1];
    
    try {
        const { getReplyRules } = await import('../auto-reply/rules.js');
        const rules = getReplyRules(phone);
        
        if (rules.length === 0) {
            return ctx.reply("📭 لا توجد قواعد ردود");
        }
        
        let reply = "🤖 قواعد الردود التلقائية:\n\n";
        for (const rule of rules) {
            reply += `🆔 #${rule.id}\n`;
            reply += `🔹 الكلمة: ${rule.trigger}\n`;
            reply += `🔸 الرد: ${rule.reply.substring(0, 30)}...\n`;
            reply += `📱 حساب: ${rule.phone}\n\n`;
        }
        
        await ctx.reply(reply);
    } catch (error) {
        await ctx.reply(`❌ خطأ: ${error.message}`);
    }
});

// ====== حذف قاعدة رد ======
bot.command("delete_reply", async ctx => {
    const ruleId = ctx.message.text.split(" ")[1];
    
    if (!ruleId) {
        return ctx.reply("❌ يرجى كتابة معرف القاعدة\nمثال: /delete_reply 5");
    }
    
    try {
        const { deleteReplyRule } = await import('../auto-reply/rules.js');
        deleteReplyRule(parseInt(ruleId));
        await ctx.reply(`✅ تم حذف القاعدة #${ruleId}`);
    } catch (error) {
        await ctx.reply(`❌ فشل الحذف: ${error.message}`);
    }
});

// ====== إحصائيات ======
bot.command("stats", async ctx => {
    try {
        const { getGeneralStats } = await import('../analytics/dashboard.js');
        const stats = getGeneralStats();
        
        let reply = "📊 الإحصائيات العامة:\n\n";
        reply += `📱 الحسابات الكلية: ${stats.totalAccounts}\n`;
        reply += `🟢 المتصلة: ${stats.connectedAccounts}\n`;
        reply += `💬 رسائل اليوم: ${stats.messagesToday}\n`;
        reply += `📝 إجمالي الرسائل: ${stats.totalMessages}\n`;
        reply += `📸 الحالات: ${stats.totalStatuses}\n`;
        reply += `👥 المجموعات: ${stats.totalGroups}\n`;
        reply += `⏰ مهام مجدولة: ${stats.scheduledPending}\n`;
        reply += `🤖 ردود تلقائية: ${stats.totalAutoReplies}\n`;
        
        await ctx.reply(reply);
    } catch (error) {
        await ctx.reply(`❌ خطأ: ${error.message}`);
    }
});

// ====== إحصائيات حساب معين ======
bot.command("account_stats", async ctx => {
    const phone = ctx.message.text.split(" ")[1];
    
    if (!phone) {
        return ctx.reply("❌ يرجى كتابة رقم الهاتف\nمثال: /account_stats 966512345678");
    }
    
    try {
        const { getAccountPerformance } = await import('../analytics/dashboard.js');
        const stats = getAccountPerformance(phone);
        
        let reply = `📊 إحصائيات الحساب ${phone}:\n\n`;
        reply += `📤 مرسل: ${stats.total.sent}\n`;
        reply += `📥 مستلم: ${stats.total.received}\n`;
        reply += `📸 حالات: ${stats.total.statuses}\n`;
        reply += `👥 مجموعات: ${stats.total.groups}\n`;
        reply += `⏰ مهام مجدولة: ${stats.total.scheduled}\n`;
        reply += `🤖 ردود تلقائية: ${stats.total.autoReplies}\n`;
        reply += `📊 متوسط يومي: ${stats.averageDaily.sent} مرسل, ${stats.averageDaily.received} مستلم\n`;
        reply += `🎯 نسبة الاستجابة: ${stats.responseRate}%\n`;
        reply += `📅 أيام النشاط: ${stats.daysActive}\n`;
        
        await ctx.reply(reply);
    } catch (error) {
        await ctx.reply(`❌ خطأ: ${error.message}`);
    }
});
