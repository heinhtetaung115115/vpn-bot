#!/usr/bin/env python3
"""
VPN Account Sales Telegram Bot
Products managed via products.json — no code changes needed.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

from config import BOT_TOKEN, ADMIN_IDS, CURRENCY, MIN_TOPUP, PAYMENT_METHODS
import products as P
from database import db, init_db

# ── Conversation states ───────────────────────────────────────────────────────
(
    TOPUP_ENTER_AMOUNT,
    TOPUP_SUBMIT_PROOF,
    ADMIN_ADD_STOCK,
    ADMIN_ADD_BRAND,
    ADMIN_ADD_PLAN,
    ADMIN_EDIT_BRAND_FIELD,
) = range(6)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def is_admin(uid): return uid in ADMIN_IDS
def fmt(n): return f"{int(n):,} {CURRENCY}"

def main_menu_kb(uid):
    btns = [
        [InlineKeyboardButton("🛒 VPN ဝယ်မည်",      callback_data="menu_buy")],
        [InlineKeyboardButton("👛 ငါ့ပိုက်ဆံအိတ်",     callback_data="menu_wallet"),
         InlineKeyboardButton("📋 ငါ့အော်ဒါများ",     callback_data="menu_orders")],
        [InlineKeyboardButton("💳 ငွေဖြည့်မည်", callback_data="menu_topup")],
        [InlineKeyboardButton("🎫 အကူအညီ",       callback_data="menu_support")],
    ]
    if is_admin(uid):
        btns.append([InlineKeyboardButton("⚙️ အက်ဒမင်", callback_data="admin_panel")])
    return InlineKeyboardMarkup(btns)


# ══════════════════════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username or user.first_name)
    await update.message.reply_text(
        f"👋 မင်္ဂလာပါ, <b>{user.first_name}</b>!\n\n"
        f"🔒 <b>VPN Shop Bot</b>\n"
        f"VPN အကောင့်များကို ချက်ချင်းဝယ်ယူနိုင်သည်။",
        parse_mode="HTML", reply_markup=main_menu_kb(user.id)
    )


# ══════════════════════════════════════════════════════════════════════════════
#  MENU ROUTER
# ══════════════════════════════════════════════════════════════════════════════

async def menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data

    if   d == "menu_buy":     await show_brands(query, ctx)
    elif d == "menu_wallet":  await show_wallet(query, ctx)
    elif d == "menu_orders":  await show_orders(query, ctx)
    elif d == "menu_topup":   await show_topup_methods(query, ctx)
    elif d == "menu_support": await show_support(query, ctx)
    elif d == "admin_panel":  await admin_panel(query, ctx)
    elif d == "back_main":
        await query.edit_message_text(
            "🏠 <b>Main Menu</b>", parse_mode="HTML",
            reply_markup=main_menu_kb(query.from_user.id)
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SHOP — Browse & Buy
# ══════════════════════════════════════════════════════════════════════════════

async def show_brands(query, ctx):
    all_products = P.get_all()
    if not all_products:
        await query.edit_message_text(
            "😔 လောလောဆယ် ပစ္စည်းမရှိသေးပါ။ နောက်မှ ပြန်လာပါ!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_main")]])
        )
        return

    btns = []
    for brand_id, brand in all_products.items():
        total = sum(db.get_stock_count(f"{brand_id}:{pid}") for pid in brand["plans"])
        tag   = f"✅ {total} ရှိသည်" if total > 0 else "❌ ကုန်သွားသည်"
        btns.append([InlineKeyboardButton(
            f"{brand['emoji']} {brand['name']}  ({tag})",
            callback_data=f"brand_{brand_id}"
        )])
    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_main")])

    await query.edit_message_text(
        "🛒 <b>VPN အမျိုးအစားရွေးပါ</b>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)
    )


async def show_plans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    brand_id = query.data.replace("brand_", "")
    brand    = P.get_brand(brand_id)
    if not brand:
        await query.answer("Brand မတွေ့ပါ။", show_alert=True)
        return

    btns = []
    text = f"{brand['emoji']} <b>{brand['name']}</b>\n{brand['description']}\n\n<b>ပက်ကေ့ချ်ရွေးပါ:</b>\n\n"
    for plan_id, plan in brand["plans"].items():
        count = db.get_stock_count(f"{brand_id}:{plan_id}")
        stock = f"✅ {count} left" if count > 0 else "❌ ကုန်သွားသည်"
        text += f"• {plan['name']} — {fmt(plan['price'])}  {stock}\n"
        btns.append([InlineKeyboardButton(
            f"{plan['name']} — {fmt(plan['price'])}",
            callback_data=f"plan_{brand_id}:{plan_id}"
        )])

    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="menu_buy")])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))


async def confirm_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    stock_key = query.data.replace("plan_", "")
    brand_id, plan_id = stock_key.split(":", 1)

    brand = P.get_brand(brand_id)
    plan  = brand["plans"].get(plan_id) if brand else None
    if not plan:
        await query.answer("ပက်ကေ့ချ်မတွေ့ပါ။", show_alert=True)
        return

    uid  = query.from_user.id
    bal  = db.get_user(uid).get("balance", 0)

    if bal < plan["price"]:
        await query.edit_message_text(
            f"❌ <b>လက်ကျန်ငွေမလုံလောက်ပါ</b>\n\n"
            f"စျေးနှုန်း : {fmt(plan['price'])}\n"
            f"လက်ကျန်ငွေ : {fmt(bal)}\n"
            f"လိုသေးသည် : {fmt(plan['price'] - bal)} more",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 ငွေဖြည့်မည်", callback_data="menu_topup")],
                [InlineKeyboardButton("🔙 နောက်သို့",       callback_data=f"brand_{brand_id}")],
            ])
        )
        return

    await query.edit_message_text(
        f"✅ <b>အတည်ပြုမည်</b>\n\n"
        f"အမျိုးအစား : {brand['emoji']} {brand['name']}\n"
        f"ပက်ကေ့ချ် : {plan['name']}\n"
        f"စျေးနှုန်း : {fmt(plan['price'])}\n"
        f"လက်ကျန်ငွေ : {fmt(bal)}  →  {fmt(bal - plan['price'])} ပြီးနောက်",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ အတည်ပြုမည်", callback_data=f"buy_{stock_key}"),
            InlineKeyboardButton("❌ မလုပ်တော့",  callback_data=f"brand_{brand_id}"),
        ]])
    )


async def process_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    stock_key = query.data.replace("buy_", "")
    brand_id, plan_id = stock_key.split(":", 1)

    brand = P.get_brand(brand_id)
    plan  = brand["plans"].get(plan_id) if brand else None
    uid   = query.from_user.id

    if not plan or db.get_user(uid).get("balance", 0) < plan["price"]:
        await query.answer("လက်ကျန်ငွေပြောင်းသွားသည် — မလုံလောက်ပါ။", show_alert=True)
        return

    account = db.pop_account(stock_key)
    if not account:
        await query.edit_message_text(
            f"⚠️ <b>ကုန်သွားသည်</b>\n\n{brand['emoji']} {brand['name']} {plan['name']} ကုန်သွားပါပြီ။",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data=f"brand_{brand_id}")]])
        )
        return

    db.deduct_balance(uid, plan["price"])
    order_id = db.create_order(uid, brand_id, plan_id, plan, account)

    await query.edit_message_text(
        f"🎉 <b>ဝယ်ယူမှုအောင်မြင်သည်!</b>\n\n"
        f"အော်ဒါ : <code>{order_id}</code>\n"
        f"အမျိုးအစား : {brand['emoji']} {brand['name']}\n"
        f"ပက်ကေ့ချ် : {plan['name']}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>အကောင့်အချက်အလက်</b>\n\n"
        f"<code>{account['details']}</code>\n"
        + (f"\n📝 <b>မှတ်ချက်:</b> {account['note']}\n" if account.get('note') else "")
        + "━━━━━━━━━━━━━━━━\n\n"
        + f"လက်ကျန်ငွေ: {fmt(db.get_user(uid)['balance'])}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 မီနူးသို့", callback_data="back_main")]])
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id,
                f"💰 <b>အသစ်ရောင်းပြီး</b>\nသုံးစွဲသူ: @{query.from_user.username} (ID:{uid})\n"
                f"ပစ္စည်း: {brand['emoji']} {brand['name']} {plan['name']}\n"
                f"စျေးနှုန်း: {fmt(plan['price'])}", parse_mode="HTML")
        except: pass


# ══════════════════════════════════════════════════════════════════════════════
#  WALLET
# ══════════════════════════════════════════════════════════════════════════════

async def show_wallet(query, ctx):
    uid  = query.from_user.id
    user = db.get_user(uid)
    txns = db.get_transactions(uid, limit=5)
    text = f"👛 <b>ငါ့ပိုက်ဆံအိတ်</b>\n\n💰 လက်ကျန်ငွေ: <b>{fmt(user.get('balance', 0))}</b>\n\n"
    if txns:
        text += "📜 <b>လတ်တလောငွေသွင်းငွေထုတ်:</b>\n"
        for t in txns:
            sign = "+" if t["type"] == "topup" else "-"
            text += f"  {sign}{fmt(t['amount'])} — {t['note']} ({t['date']})\n"
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ငွေဖြည့်မည်", callback_data="menu_topup")],
        [InlineKeyboardButton("🔙 နောက်သို့",   callback_data="back_main")],
    ]))


# ══════════════════════════════════════════════════════════════════════════════
#  TOP-UP
# ══════════════════════════════════════════════════════════════════════════════

async def show_topup_methods(query, ctx):
    btns = []
    text = "💳 <b>ငွေဖြည့်မည်</b>\n\nငွေပေးချေမှုနည်းလမ်းရွေးပါ:\n\n"
    for mid, m in PAYMENT_METHODS.items():
        text += f"• <b>{m['name']}</b>\n"
        btns.append([InlineKeyboardButton(f"{m['emoji']} {m['name']}", callback_data=f"topup_method_{mid}")])
    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_main")])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))


async def topup_choose_method(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    mid    = query.data.replace("topup_method_", "")
    method = PAYMENT_METHODS.get(mid)
    if not method:
        await query.answer("မတွေ့ပါ", show_alert=True)
        return
    ctx.user_data["topup_method"] = mid
    await query.edit_message_text(
        f"💳 <b>Top-up via {method['name']}</b>\n\n"
        f"📋 <b>ငွေပေးချေရန်အချက်အလက်:</b>\n<code>{method['payment_info']}</code>\n\n"
        f"အနည်းဆုံး: {fmt(MIN_TOPUP)}\n\nပမာဏထည့်ပါ:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]])
    )
    return TOPUP_ENTER_AMOUNT


async def topup_enter_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip().replace(",", ""))
        if amount < MIN_TOPUP:
            await update.message.reply_text(f"❌ အနည်းဆုံး {fmt(MIN_TOPUP)} ဖြစ်သည်။ ထပ်ကြိုးစားပါ:")
            return TOPUP_ENTER_AMOUNT
        ctx.user_data["topup_amount"] = amount
        method = PAYMENT_METHODS[ctx.user_data["topup_method"]]
        await update.message.reply_text(
            f"📸 <b>ငွေပေးချေမှုအထောက်အထားပို့ပါ</b>\n\nပမာဏ: <b>{fmt(amount)}</b>\nနည်းလမ်း: <b>{method['name']}</b>\n\nငွေလွှဲပြီးကြောင်း screenshot ပို့ပါ:",
            parse_mode="HTML"
        )
        return TOPUP_SUBMIT_PROOF
    except ValueError:
        await update.message.reply_text("❌ ပမာဏမမှန်ကန်ပါ။ နံပါတ်ထည့်ပါ:")
        return TOPUP_ENTER_AMOUNT


async def topup_submit_proof(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid       = update.effective_user.id
    amount    = ctx.user_data.get("topup_amount")
    mid       = ctx.user_data.get("topup_method")
    method    = PAYMENT_METHODS[mid]
    has_proof = update.message.photo or update.message.document
    note      = update.message.caption or update.message.text or ""

    if not has_proof and not note:
        await update.message.reply_text("❌ Screenshot သို့မဟုတ် reference နံပါတ်ပို့ပါ:")
        return TOPUP_SUBMIT_PROOF

    req_id   = db.create_topup_request(uid, amount, mid, note)
    short_id = req_id.replace("-", "")[:20]
    db.register_short_id(short_id, req_id)

    await update.message.reply_text(
        f"✅ <b>တောင်းဆိုမှုပေးပို့ပြီး!</b>\n\nID: <code>{req_id}</code>\nပမာဏ: {fmt(amount)}\n\n⏳ အက်ဒမင်မှ မကြာမီအတည်ပြုပေးမည်။",
        parse_mode="HTML", reply_markup=main_menu_kb(uid)
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Approve {fmt(amount)}", callback_data=f"apr_{short_id}"),
        InlineKeyboardButton("❌ Reject",                 callback_data=f"rej_{short_id}"),
    ]])
    caption = (
        f"💳 <b>New Top-up Request</b>\n\n"
        f"ID    : <code>{req_id}</code>\n"
        f"User  : @{update.effective_user.username} (ID: {uid})\n"
        f"ပမာဏ: {fmt(amount)}\n"
        f"နည်းလမ်း: {method['name']}\n"
        f"Note  : {note}"
    )
    for admin_id in ADMIN_IDS:
        try:
            if update.message.photo:
                await ctx.bot.send_photo(admin_id, photo=update.message.photo[-1].file_id, caption=caption, parse_mode="HTML")
            elif update.message.document:
                await ctx.bot.send_document(admin_id, document=update.message.document.file_id, caption=caption, parse_mode="HTML")
            else:
                await ctx.bot.send_message(admin_id, caption, parse_mode="HTML")
            await ctx.bot.send_message(admin_id, "⬆️ အပေါ်မှ အထောက်အထားကြည့်ပြီး action နှိပ်ပါ:", reply_markup=kb)
        except Exception as e:
            logger.error(f"Admin notify error: {e}")
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
#  ORDERS
# ══════════════════════════════════════════════════════════════════════════════

async def show_orders(query, ctx):
    uid    = query.from_user.id
    orders = db.get_orders(uid)
    if not orders:
        text = "📋 <b>ငါ့အော်ဒါများ</b>\n\nအော်ဒါမရှိသေးပါ။"
    else:
        text = "📋 <b>ငါ့အော်ဒါများ</b>\n\n"
        for o in orders[:10]:
            brand   = P.get_brand(o.get("brand_id")) or {}
            plan    = brand.get("plans", {}).get(o.get("plan_id"), {})
            details   = o.get("details", "N/A")
            acct_note = o.get("acct_note", "")
            text += (
                f"━━━━━━━━━━━━━━━━\n"
                f"🏷 <b>{brand.get('emoji','')} {brand.get('name','?')} — {plan.get('name','?')}</b>\n"
                f"📅 {o['date']}  |  💰 {fmt(o['amount'])}\n"
                f"🔑 <code>{details}</code>\n"
            )
        text += "━━━━━━━━━━━━━━━━"
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_main")]
    ]))



# ══════════════════════════════════════════════════════════════════════════════
#  SUPPORT
# ══════════════════════════════════════════════════════════════════════════════

async def show_support(query, ctx):
    await query.edit_message_text(
        "🎫 <b>အကူအညီ</b>\n\nပြဿနာတစ်ခုခုရှိပါက admin ကိုဆက်သွယ်ပါ။",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_main")]])
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════════════

async def admin_panel(query, ctx):
    if not is_admin(query.from_user.id):
        await query.answer("ခွင့်မပြုပါ", show_alert=True)
        return
    stats = db.get_stats()
    await query.edit_message_text(
        f"⚙️ <b>အက်ဒမင်</b>\n\n"
        f"👥 အသုံးပြုသူ : {stats['users']}\n"
        f"💰 ဝင်ငွေ : {fmt(stats['revenue'])}\n"
        f"📦 အော်ဒါ : {stats['orders']}\n"
        f"⏳ စောင့်ဆိုင်းဆဲ : {stats['pending_topups']}\n",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏳ စောင့်ဆိုင်းဆဲ ငွေဖြည့်မှုများ",   callback_data="admin_pending_topups")],
            [InlineKeyboardButton("📦 အကောင့်များတင်မည်",   callback_data="admin_add_stock")],
            [InlineKeyboardButton("🗂 ပစ္စည်းများစီမံမည်",   callback_data="admin_products")],
            [InlineKeyboardButton("🔙 နောက်သို့",              callback_data="back_main")],
        ])
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — TOP-UP APPROVE / REJECT
# ══════════════════════════════════════════════════════════════════════════════

async def admin_pending_topups(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    reqs = db.get_pending_topups()
    if not reqs:
        await query.edit_message_text("✅ စောင့်ဆိုင်းဆဲ ငွေဖြည့်မှုမရှိပါ။",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="admin_panel")]]))
        return
    text = "⏳ <b>စောင့်ဆိုင်းဆဲ ငွေဖြည့်တောင်းဆိုမှုများ</b>\n\n"
    btns = []
    for r in reqs:
        sid = r["request_id"].replace("-", "")[:20]
        db.register_short_id(sid, r["request_id"])
        text += f"• <code>{r['request_id'][:8]}</code> | {r['user_id']} | {fmt(r['amount'])} | {r['method']}\n"
        btns.append([
            InlineKeyboardButton(f"✅ {r['request_id'][:8]}", callback_data=f"apr_{sid}"),
            InlineKeyboardButton(f"❌ {r['request_id'][:8]}", callback_data=f"rej_{sid}"),
        ])
    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="admin_panel")])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))


async def admin_approve_topup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("ခွင့်မပြုပါ", show_alert=True)
        return

    short_id = query.data.replace("apr_", "")
    req_id   = db.resolve_short_id(short_id)

    # Fallback: try using short_id directly as req_id prefix match
    if not req_id:
        for r in db.get_pending_topups():
            if r["request_id"].replace("-", "")[:20] == short_id:
                req_id = r["request_id"]
                break

    req = db.get_topup_request(req_id) if req_id else None

    if not req:
        await query.answer("တောင်းဆိုမှုမတွေ့ပါ။", show_alert=True)
        return
    if req["status"] != "pending":
        await query.answer("လုပ်ဆောင်ပြီးသားဖြစ်သည်။", show_alert=True)
        return
    if not db.approve_topup(req_id):
        await query.answer("❌ အတည်ပြုမရပါ။", show_alert=True)
        return

    await query.answer("✅ အတည်ပြုပြီး!", show_alert=False)
    user = db.get_user(req["user_id"])
    await query.edit_message_text(
        f"✅ <b>အတည်ပြုပြီး</b> — {fmt(req['amount'])} သုံးစွဲသူအတွက် {req['user_id']}",
        parse_mode="HTML"
    )
    try:
        await ctx.bot.send_message(
            req["user_id"],
            f"✅ <b>ငွေဖြည့်မှုအတည်ပြုပြီး!</b>\n\n"
            f"<b>{fmt(req['amount'])}</b> သင့်ပိုက်ဆံအိတ်သို့ထည့်ပြီးပါပြီ။\n"
            f"လက်ကျန်ငွေ: {fmt(user.get('balance', 0))}",
            parse_mode="HTML", reply_markup=main_menu_kb(req["user_id"])
        )
    except Exception as e:
        logger.error(f"Notify error: {e}")


async def admin_reject_topup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("ခွင့်မပြုပါ", show_alert=True)
        return

    short_id = query.data.replace("rej_", "")
    req_id   = db.resolve_short_id(short_id)

    # Fallback: try matching short_id directly
    if not req_id:
        for r in db.get_pending_topups():
            if r["request_id"].replace("-", "")[:20] == short_id:
                req_id = r["request_id"]
                break

    req = db.get_topup_request(req_id) if req_id else None

    if not req:
        await query.answer("တောင်းဆိုမှုမတွေ့ပါ။", show_alert=True)
        return
    if req["status"] != "pending":
        await query.answer("လုပ်ဆောင်ပြီးသားဖြစ်သည်။", show_alert=True)
        return
    db.reject_topup(req_id)
    await query.answer("❌ ငြင်းပယ်ပြီး", show_alert=False)
    await query.edit_message_text(f"❌ <b>Rejected</b> top-up {req_id[:8]}", parse_mode="HTML")
    try:
        await ctx.bot.send_message(req["user_id"],
            f"❌ <b>ငွေဖြည့်မှုငြင်းပယ်ခံရသည်</b>\n\nYour {fmt(req['amount'])} တောင်းဆိုမှုကိုငြင်းပယ်လိုက်သည်။\nမမှန်ကန်ပါက admin ကိုဆက်သွယ်ပါ။",
            parse_mode="HTML")
    except Exception as e:
        logger.error(f"Notify error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — UPLOAD ACCOUNTS (stock)
# ══════════════════════════════════════════════════════════════════════════════

async def admin_add_stock_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return

    lines = ""
    for brand_id, brand in P.get_all().items():
        for plan_id, plan in brand["plans"].items():
            count = db.get_stock_count(f"{brand_id}:{plan_id}")
            lines += f"  <code>{brand_id}:{plan_id}</code> — {brand['name']} {plan['name']} ({count} ရှိသည်)\n"

    await query.edit_message_text(
        f"📦 <b>အကောင့်များတင်မည်</b>\n\n"
        f"လက်ရှိအကောင့်အရေအတွက်:\n{lines}\n"
        f"ဖော်မတ် (တစ်ကြောင်းတစ်ခု):\n"
        f"<code>brand_id:plan_id|account details|note (optional)</code>\n\n"
        f"ဥပမာ (note မပါ):\n"
        f"<code>expressvpn:1month|user@mail.com:Pass123</code>\n\n"
        f"ဥပမာ (note ပါ):\n"
        f"<code>expressvpn:1month|user@mail.com:Pass123|Windows နှင့် Android တွင်သုံးနိုင်သည်</code>\n\n"
        f"/cancel ပို့ပြီး ရပ်နိုင်သည်။",
        parse_mode="HTML"
    )
    return ADMIN_ADD_STOCK


async def admin_add_stock_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    lines = update.message.text.strip().splitlines()
    added, errors = 0, []

    for line in lines:
        line = line.strip()
        if not line: continue
        if "|" not in line or ":" not in line.split("|")[0]:
            errors.append(f"❌ ဖော်မတ်မမှန်: <code>{line}</code>")
            continue
        parts    = line.split("|")
        key      = parts[0].strip()
        details  = parts[1].strip() if len(parts) > 1 else ""
        acct_note = parts[2].strip() if len(parts) > 2 else ""
        brand_id, plan_id = key.split(":", 1)
        brand = P.get_brand(brand_id)
        if not brand:
            errors.append(f"❌ မသိသောbrand: <code>{brand_id}</code>")
            continue
        if plan_id.strip() not in brand["plans"]:
            errors.append(f"❌ မသိသောပက်ကေ့ချ်: <code>{plan_id}</code>")
            continue
        db.add_account(f"{brand_id}:{plan_id.strip()}", details, acct_note)
        added += 1

    result = f"✅ ထည့်ပြီး <b>{added}</b> အကောင့်။\n"
    if errors:
        result += "\nErrors:\n" + "\n".join(errors) + "\n"
    result += "\n<b>လက်ကျန်အကောင့်:</b>\n"
    for brand_id, brand in P.get_all().items():
        for plan_id in brand["plans"]:
            count = db.get_stock_count(f"{brand_id}:{plan_id}")
            result += f"  {brand['emoji']} {brand['name']} {brand['plans'][plan_id]['name']}: {count}\n"

    await update.message.reply_text(result, parse_mode="HTML", reply_markup=main_menu_kb(update.effective_user.id))
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — MANAGE PRODUCTS (brands & plans)
# ══════════════════════════════════════════════════════════════════════════════

async def admin_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return

    all_products = P.get_all()
    text = "🗂 <b>ပစ္စည်းများစီမံမည်</b>\n\n"
    for brand_id, brand in all_products.items():
        text += f"{brand['emoji']} <b>{brand['name']}</b> (<code>{brand_id}</code>)\n"
        for plan_id, plan in brand["plans"].items():
            text += f"   • {plan['name']} — {fmt(plan['price'])}  (<code>{plan_id}</code>)\n"
        text += "\n"

    if not all_products:
        text += "ပစ္စည်းမရှိသေးပါ။\n"

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Brand အသစ်ထည့်မည်",    callback_data="prod_add_brand")],
        [InlineKeyboardButton("➕ ပက်ကေ့ချ်ထည့်မည်",     callback_data="prod_add_plan_pick")],
        [InlineKeyboardButton("🗑 ပက်ကေ့ချ်ဖျက်မည်",  callback_data="prod_del_plan_pick")],
        [InlineKeyboardButton("🗑 Brand ဖျက်မည်", callback_data="prod_del_brand_pick")],
        [InlineKeyboardButton("🔙 နောက်သို့",         callback_data="admin_panel")],
    ]))


# ── ADD BRAND ─────────────────────────────────────────────────────────────────

async def prod_add_brand_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text(
        "➕ <b>Brand အသစ်ထည့်မည်</b>\n\n"
        "ဤဖော်မတ်ဖြင့်ပေးပို့ပါ:\n"
        "<code>brand_id|Name|emoji|description</code>\n\n"
        "Example:\n"
        "<code>surfshark|Surfshark VPN|🦈|Unlimited devices VPN</code>\n\n"
        "• <code>brand_id</code> — အသေးစာလုံး၊ space မပါ (ဥပမာ surfshark)\n\n"
        "/cancel ပို့ပြီး ရပ်နိုင်သည်။",
        parse_mode="HTML"
    )
    return ADMIN_ADD_BRAND


async def prod_add_brand_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = update.message.text.strip().split("|")
    if len(parts) < 4:
        await update.message.reply_text("❌ Need 4 parts: brand_id|Name|emoji|description\nTry again:")
        return ADMIN_ADD_BRAND

    brand_id, name, emoji, desc = [p.strip() for p in parts[:4]]
    if " " in brand_id:
        await update.message.reply_text("❌ brand_id cannot have spaces ဖြစ်သည်။ ထပ်ကြိုးစားပါ:")
        return ADMIN_ADD_BRAND

    if P.add_brand(brand_id, name, emoji, desc):
        await update.message.reply_text(
            f"✅ Brand <b>{name}</b> ထည့်ပြီး!\n\nယခု <b>ပစ္စည်းစီမံမည် → ပက်ကေ့ချ်ထည့်မည်</b> မှပက်ကေ့ချ်ထည့်ပါ။",
            parse_mode="HTML", reply_markup=main_menu_kb(update.effective_user.id)
        )
    else:
        await update.message.reply_text(f"❌ Brand ID <code>{brand_id}</code> already exists.", parse_mode="HTML")
    return ConversationHandler.END


# ── ADD PLAN ──────────────────────────────────────────────────────────────────

async def prod_add_plan_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return

    btns = [[InlineKeyboardButton(f"{b['emoji']} {b['name']}", callback_data=f"addplan_{bid}")]
            for bid, b in P.get_all().items()]
    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="admin_products")])
    await query.edit_message_text(
        "➕ <b>ပက်ကေ့ချ်ထည့်မည် — Brand ရွေးပါ</b>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)
    )


async def prod_add_plan_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    brand_id = query.data.replace("addplan_", "")
    brand    = P.get_brand(brand_id)
    if not brand:
        await query.answer("Brand မတွေ့ပါ", show_alert=True)
        return

    ctx.user_data["adding_plan_brand"] = brand_id
    await query.edit_message_text(
        f"➕ <b>Add Plan to {brand['emoji']} {brand['name']}</b>\n\n"
        f"ပက်ကေ့ချ်အချက်အလက်ပို့ပါ:\n"
        f"<code>plan_id|Name|duration_ရက်|price</code>\n\n"
        f"Example:\n"
        f"<code>3month|3 Months|90|12000</code>\n\n"
        f"• <code>plan_id</code> — အသေးစာလုံး၊ space မပါ\n"
        f"• <code>duration_ရက်</code> — ရက်အရေအတွက်\n"
        f"• <code>price</code> — ကျပ်ဖြင့်\n\n"
        f"/cancel ပို့ပြီး ရပ်နိုင်သည်။",
        parse_mode="HTML"
    )
    return ADMIN_ADD_PLAN


async def prod_add_plan_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    brand_id = ctx.user_data.get("adding_plan_brand")
    brand    = P.get_brand(brand_id)
    if not brand:
        await update.message.reply_text("❌ Session expired. Start again.")
        return ConversationHandler.END

    parts = update.message.text.strip().split("|")
    if len(parts) < 4:
        await update.message.reply_text("❌ Need 4 parts: plan_id|Name|duration_ရက်|price\nTry again:")
        return ADMIN_ADD_PLAN

    plan_id, name, ရက်, price = [p.strip() for p in parts[:4]]

    try:
        ရက်  = int(ရက်)
        price = int(price)
    except ValueError:
        await update.message.reply_text("❌ duration_ရက် and price must be numbers ဖြစ်သည်။ ထပ်ကြိုးစားပါ:")
        return ADMIN_ADD_PLAN

    if " " in plan_id:
        await update.message.reply_text("❌ plan_id cannot have spaces ဖြစ်သည်။ ထပ်ကြိုးစားပါ:")
        return ADMIN_ADD_PLAN

    P.add_plan(brand_id, plan_id, name, ရက်, price)
    await update.message.reply_text(
        f"✅ ပက်ကေ့ချ် <b>{name}</b> added to {brand['emoji']} {brand['name']}!\n"
        f"စျေးနှုန်း: {fmt(price)} | ကာလ: {ရက်} ရက်\n\n"
        f"အကောင့်တင်ရန် stock key: <code>{brand_id}:{plan_id}</code>",
        parse_mode="HTML", reply_markup=main_menu_kb(update.effective_user.id)
    )
    return ConversationHandler.END


# ── REMOVE PLAN ───────────────────────────────────────────────────────────────

async def prod_del_plan_pick_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    btns = [[InlineKeyboardButton(f"{b['emoji']} {b['name']}", callback_data=f"delplan_brand_{bid}")]
            for bid, b in P.get_all().items()]
    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="admin_products")])
    await query.edit_message_text("🗑 <b>ပက်ကေ့ချ်ဖျက်မည် — Brand ရွေးပါ</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(btns))


async def prod_del_plan_pick_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    brand_id = query.data.replace("delplan_brand_", "")
    brand    = P.get_brand(brand_id)
    if not brand:
        await query.answer("Brand မတွေ့ပါ", show_alert=True)
        return
    btns = []
    for pid, plan in brand["plans"].items():
        count = db.get_stock_count(f"{brand_id}:{pid}")
        btns.append([InlineKeyboardButton(
            f"🗑 {plan['name']} — {fmt(plan['price'])} ({count} ရှိသည်)",
            callback_data=f"delplan_confirm_{brand_id}:{pid}"
        )])
    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="prod_del_plan_pick")])
    await query.edit_message_text(
        f"🗑 <b>ပက်ကေ့ချ်ဖျက်မည် — {brand['emoji']} {brand['name']}</b>\n\nဖျက်မည့်ပက်ကေ့ချ်ရွေးပါ:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)
    )


async def prod_del_plan_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    key       = query.data.replace("delplan_confirm_", "")
    brand_id, plan_id = key.split(":", 1)
    brand     = P.get_brand(brand_id)
    plan      = brand["plans"].get(plan_id) if brand else None
    if not plan:
        await query.answer("ပက်ကေ့ချ်မတွေ့ပါ", show_alert=True)
        return
    count = db.get_stock_count(f"{brand_id}:{plan_id}")
    await query.edit_message_text(
        f"⚠️ <b>ပက်ကေ့ချ်ဖျက်ရန်အတည်ပြုပါ</b>\n\n"
        f"အမျိုးအစား : {brand['emoji']} {brand['name']}\n"
        f"ပက်ကေ့ချ် : {plan['name']}\n"
        f"အကောင့် : {count} ခု (ပျောက်သွားမည်!)\n\n"
        f"သေချာပြီလား?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 ဟုတ်သည်၊ ဖျက်မည်", callback_data=f"delplan_do_{brand_id}:{plan_id}"),
             InlineKeyboardButton("❌ မလုပ်တော့",      callback_data="admin_products")],
        ])
    )


async def prod_del_plan_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    key       = query.data.replace("delplan_do_", "")
    brand_id, plan_id = key.split(":", 1)
    brand     = P.get_brand(brand_id)
    plan_name = brand["plans"][plan_id]["name"] if brand else plan_id
    P.remove_plan(brand_id, plan_id)
    await query.edit_message_text(
        f"✅ ပက်ကေ့ချ် <b>{plan_name}</b> မှဖျက်ပြီး {brand['name']}.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့ to Products", callback_data="admin_products")]])
    )


# ── REMOVE BRAND ──────────────────────────────────────────────────────────────

async def prod_del_brand_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    btns = [[InlineKeyboardButton(f"🗑 {b['emoji']} {b['name']}", callback_data=f"delbrand_confirm_{bid}")]
            for bid, b in P.get_all().items()]
    btns.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="admin_products")])
    await query.edit_message_text("🗑 <b>Brand ဖျက်မည်</b>\n\nဖျက်မည့် Brand ရွေးပါ:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))


async def prod_del_brand_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    brand_id = query.data.replace("delbrand_confirm_", "")
    brand    = P.get_brand(brand_id)
    if not brand:
        await query.answer("Brand မတွေ့ပါ", show_alert=True)
        return
    total = sum(db.get_stock_count(f"{brand_id}:{pid}") for pid in brand["plans"])
    await query.edit_message_text(
        f"⚠️ <b>Brand ဖျက်ရန်အတည်ပြုပါ</b>\n\n"
        f"အမျိုးအစား : {brand['emoji']} {brand['name']}\n"
        f"ပက်ကေ့ချ် : {len(brand['plans'])}\n"
        f"Stock  : {total} ခု (ပျောက်သွားမည်!)\n\n"
        f"ဤလုပ်ဆောင်ချက်ကို ပြန်မလုပ်နိုင်ပါ!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 ဟုတ်သည်၊ ဖျက်မည်", callback_data=f"delbrand_do_{brand_id}"),
             InlineKeyboardButton("❌ မလုပ်တော့",      callback_data="admin_products")],
        ])
    )


async def prod_del_brand_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    brand_id = query.data.replace("delbrand_do_", "")
    brand    = P.get_brand(brand_id)
    name     = brand["name"] if brand else brand_id
    P.remove_brand(brand_id)
    await query.edit_message_text(
        f"✅ Brand <b>{name}</b> ဖျက်ပြီး။",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့ to Products", callback_data="admin_products")]])
    )


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ မလုပ်တော့led.", reply_markup=main_menu_kb(update.effective_user.id))
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    topup_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(topup_choose_method, pattern="^topup_method_")],
        states={
            TOPUP_ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_enter_amount)],
            TOPUP_SUBMIT_PROOF: [MessageHandler(filters.ALL  & ~filters.COMMAND, topup_submit_proof)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    stock_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_stock_start, pattern="^admin_add_stock$")],
        states={ADMIN_ADD_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_stock_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    add_brand_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(prod_add_brand_start, pattern="^prod_add_brand$")],
        states={ADMIN_ADD_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, prod_add_brand_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    add_plan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(prod_add_plan_brand, pattern="^addplan_")],
        states={ADMIN_ADD_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, prod_add_plan_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(topup_conv)
    app.add_handler(stock_conv)
    app.add_handler(add_brand_conv)
    app.add_handler(add_plan_conv)

    app.add_handler(CallbackQueryHandler(menu_handler,           pattern="^(menu_|back_main|admin_panel)"))
    app.add_handler(CallbackQueryHandler(show_plans,             pattern="^brand_"))
    app.add_handler(CallbackQueryHandler(confirm_plan,           pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(process_buy,            pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(admin_pending_topups,   pattern="^admin_pending_topups$"))
    app.add_handler(CallbackQueryHandler(admin_approve_topup,    pattern="^apr_"))
    app.add_handler(CallbackQueryHandler(admin_reject_topup,     pattern="^rej_"))
    app.add_handler(CallbackQueryHandler(admin_products,         pattern="^admin_products$"))
    app.add_handler(CallbackQueryHandler(prod_add_plan_pick,     pattern="^prod_add_plan_pick$"))
    app.add_handler(CallbackQueryHandler(prod_del_plan_pick_brand, pattern="^prod_del_plan_pick$"))
    app.add_handler(CallbackQueryHandler(prod_del_plan_pick_plan,  pattern="^delplan_brand_"))
    app.add_handler(CallbackQueryHandler(prod_del_plan_confirm,    pattern="^delplan_confirm_"))
    app.add_handler(CallbackQueryHandler(prod_del_plan_do,         pattern="^delplan_do_"))
    app.add_handler(CallbackQueryHandler(prod_del_brand_pick,      pattern="^prod_del_brand_pick$"))
    app.add_handler(CallbackQueryHandler(prod_del_brand_confirm,   pattern="^delbrand_confirm_"))
    app.add_handler(CallbackQueryHandler(prod_del_brand_do,        pattern="^delbrand_do_"))

    init_db()
    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
