"""
GoldFlow — Telegram-бот для личного учёта финансов.
Золото-зелёная тема, интуитивные кнопки, красивые графики.

Запуск: python bot.py
"""

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

import database as db
import charts
from categorizer import parse_transaction, get_all_categories
from config import BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Временное хранилище "операция ждёт выбора категории" (user_id -> данные операции)
pending_transactions = {}


# ---------- Клавиатуры ----------

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Добавить операцию", callback_data="menu_add")],
        [InlineKeyboardButton("📊 Отчёт", callback_data="menu_report"),
         InlineKeyboardButton("📈 Баланс", callback_data="menu_trend")],
        [InlineKeyboardButton("🎯 Бюджет", callback_data="menu_budget")],
    ])


def category_keyboard(include_income=False):
    categories = get_all_categories(include_income=include_income)
    buttons = [InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in categories]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


# ---------- Команды ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение с главным меню."""
    welcome_text = (
        "✨ *Добро пожаловать в GoldFlow!* ✨\n\n"
        "Я помогу тебе легко следить за доходами и расходами.\n\n"
        "💬 Просто напиши мне сумму и на что потратил(а), например:\n"
        "`500 продукты` или `+5000 зарплата`\n\n"
        "Или выбери действие ниже 👇"
    )
    await update.message.reply_text(
        welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💡 *Как пользоваться GoldFlow:*\n\n"
        "• Напиши сумму и категорию: `500 еда` — это расход\n"
        "• Для дохода добавь плюс: `+5000 зарплата`\n"
        "• /report — диаграмма расходов по категориям\n"
        "• /trend — график баланса по дням\n"
        "• /budget — управление лимитами бюджета\n"
        "• /start — главное меню",
        parse_mode="Markdown",
    )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_report(update.effective_user.id, update.effective_chat.id, context)


async def trend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_trend(update.effective_user.id, update.effective_chat.id, context)


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_budget_status(update.effective_user.id, update.effective_chat.id, context)


# ---------- Обработка свободного текста (ввод операций) ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Распознаёт сумму/категорию из обычного сообщения и сохраняет операцию."""
    user_id = update.effective_user.id
    text = update.message.text

    # Если пользователь сейчас вводит лимит бюджета
    if context.user_data.get("awaiting_budget_category"):
        await handle_budget_amount(update, context)
        return

    parsed = parse_transaction(text)

    if not parsed:
        await update.message.reply_text(
            "🤔 Не поняла сумму. Попробуй, например: `500 еда` или `+5000 зарплата`",
            parse_mode="Markdown",
        )
        return

    if parsed["category"] is None:
        # Категория не распознана — спрашиваем кнопками
        pending_transactions[user_id] = parsed
        keyboard = category_keyboard(include_income=parsed["is_income"])
        await update.message.reply_text(
            f"💰 Сумма: {parsed['amount']:.0f}\nВыбери категорию:",
            reply_markup=keyboard,
        )
        return

    db.add_transaction(user_id, parsed["amount"], parsed["category"], parsed["is_income"])
    await confirm_transaction(update.message, parsed["amount"], parsed["category"], parsed["is_income"])


async def confirm_transaction(message, amount, category, is_income):
    icon = "💚" if is_income else "💸"
    kind = "Доход" if is_income else "Расход"
    await message.reply_text(
        f"{icon} *{kind} записан*\n{amount:.0f} — {category}",
        parse_mode="Markdown",
    )


# ---------- Обработка нажатий на кнопки ----------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "menu_add":
        await query.message.reply_text(
            "✍️ Напиши сумму и на что, например:\n`500 продукты` или `+5000 зарплата`",
            parse_mode="Markdown",
        )

    elif data == "menu_report":
        await send_report(user_id, query.message.chat_id, context)

    elif data == "menu_trend":
        await send_trend(user_id, query.message.chat_id, context)

    elif data == "menu_budget":
        await send_budget_status(user_id, query.message.chat_id, context)

    elif data.startswith("cat_"):
        category = data[4:]
        if user_id in pending_transactions:
            parsed = pending_transactions.pop(user_id)
            db.add_transaction(user_id, parsed["amount"], category, parsed["is_income"])
            await query.message.delete()
            await confirm_transaction(query.message, parsed["amount"], category, parsed["is_income"])

    elif data.startswith("setbudget_"):
        category = data[len("setbudget_"):]
        context.user_data["awaiting_budget_category"] = category
        await query.message.reply_text(f"Введи лимит для категории «{category}» (просто число):")


# ---------- Отчёты и графики ----------

async def send_report(user_id, chat_id, context):
    category_totals = db.get_expenses_by_category(user_id, days=30)
    if not category_totals:
        await context.bot.send_message(chat_id, "Пока нет расходов за последние 30 дней 🙂")
        return
    buf = charts.generate_pie_chart(category_totals, title="Расходы за 30 дней")
    await context.bot.send_photo(chat_id, photo=buf, caption="📊 Твои расходы по категориям")


async def send_trend(user_id, chat_id, context):
    dates, balances = db.get_daily_balance_trend(user_id, days=30)
    if not dates:
        await context.bot.send_message(chat_id, "Пока недостаточно данных для графика 🙂")
        return
    balance = db.get_balance(user_id)
    buf = charts.generate_trend_chart(dates, balances, title="Баланс за 30 дней")
    await context.bot.send_photo(chat_id, photo=buf, caption=f"📈 Текущий баланс: {balance:.0f}")


async def send_budget_status(user_id, chat_id, context):
    budgets = db.get_budgets(user_id)

    if not budgets:
        # Предлагаем создать первый лимит
        categories = get_all_categories()
        buttons = [[InlineKeyboardButton(c, callback_data=f"setbudget_{c}")] for c in categories]
        await context.bot.send_message(
            chat_id,
            "У тебя пока нет лимитов бюджета. Выбери категорию, чтобы задать лимит:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    spent = {cat: db.get_spent_this_month(user_id, cat) for cat in budgets}
    buf = charts.generate_budget_bar(budgets, spent, title="Прогресс по бюджету (этот месяц)")

    # Текстовая сводка с эмодзи-прогресс-барами
    lines = []
    for cat, limit in budgets.items():
        s = spent.get(cat, 0)
        ratio = min(s / limit, 1.0) if limit > 0 else 0
        filled = int(ratio * 5)
        bar = "🟩" * filled + "⬜" * (5 - filled)
        warning = " ⚠️" if s > limit else ""
        lines.append(f"{cat}: {bar} {s:.0f}/{limit:.0f}{warning}")

    await context.bot.send_photo(chat_id, photo=buf, caption="🎯 " + "\n".join(lines))


async def handle_budget_amount(update, context):
    """Обрабатывает ввод числового лимита после выбора категории."""
    category = context.user_data.pop("awaiting_budget_category")
    text = update.message.text.strip().replace(",", ".")
    try:
        limit = float(text)
        db.set_budget(update.effective_user.id, category, limit)
        await update.message.reply_text(f"✅ Лимит для «{category}» установлен: {limit:.0f}")
    except ValueError:
        await update.message.reply_text("Не поняла число, попробуй ещё раз через /budget")


# ---------- Крошечный веб-сервер (нужен только для бесплатного хостинга) ----------
# Render/Railway на бесплатном тарифе ожидают "Web Service", то есть сервис,
# который слушает какой-то порт. Сам бот работает через polling и порт ему
# не нужен — этот сервер просто отвечает "OK", чтобы хостинг видел, что
# сервис "жив", и не требовал платный тариф "Background Worker".

class _HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("GoldFlow bot is running ✅".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # не засоряем логи запросами health-check


def _start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), _HealthCheckHandler)
    logger.info(f"Health-check сервер слушает порт {port}")
    server.serve_forever()


# ---------- Запуск ----------

def main():
    db.init_db()

    # Веб-сервер запускаем в отдельном потоке, чтобы не мешать боту
    threading.Thread(target=_start_health_server, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("trend", trend_command))
    application.add_handler(CommandHandler("budget", budget_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("GoldFlow bot запущен 🚀")
    application.run_polling()


if __name__ == "__main__":
    main()
