import {Telegraf} from "telegraf";

import config from "../config/env.js";

import {
addAccount,
accounts
} from "../whatsapp/manager.js";


let bot;


export function startBot(){


bot=new Telegraf(
config.TELEGRAM_TOKEN
);



bot.start(ctx=>{

ctx.reply(
"🤖 WhatsApp Manager Online"
);

});



bot.command(
"accounts",
ctx=>{

ctx.reply(
JSON.stringify(accounts(),null,2)
);

});



bot.command(
"add",
async ctx=>{


let phone=
ctx.message.text.split(" ")[1];


if(!phone)
return ctx.reply(
"اكتب الرقم بعد الأمر"
);



await addAccount(phone);


ctx.reply(
"جاري ربط الحساب: "+phone
);


});



bot.launch();


console.log(
"Telegram bot started"
);


}
