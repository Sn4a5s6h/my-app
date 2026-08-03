import express from "express";

import config from "./config/env.js";

import "./database/db.js";

import {
startBot
} from "./telegram/bot.js";


const app=express();


app.use(express.json());


app.get("/",(req,res)=>{

res.send(
"WhatsApp Manager Running"
);

});


app.listen(
config.PORT,
()=>{

console.log(
"Server running:",
config.PORT
);

});



startBot();
