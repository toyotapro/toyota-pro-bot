import os
import json
import asyncio
import re
import logging
from datetime import datetime
from keep_alive import keep_alive
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DATA_FILE = "data.json"
# =============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

CARS = [
    "Toyota RAV 4 XA60",
    "Toyota Camry 80",
    "Toyota Camry 85",
    "Toyota Highlander 2026",
    "Mazda CX-5",
    "Nissan X-Trail",
    "Nissan Qashqai",
    "Geely Monjaro"
]

DEFAULT_TRAINING_DESC = (
    "🎓 *Обучение по русификации и активации прошивок*\n\n"
    "Мы проводим профессиональное обучение для мастеров и специалистов, "
    "которые хотят освоить работу с прошивками автомобилей.\n\n"
    "📚 *Что вы узнаете:*\n"
    "• Основы работы с диагностическим оборудованием\n"
    "• Процесс русификации мультимедиа и приборных панелей\n"
    "• Активация прошивок для различных моделей авто\n"
    "• Работа с VIN-номерами и кодами прошивок\n"
    "• Типичные ошибки и как их избежать\n\n"
    "💰 *Стоимость:* 100 000 руб.\n"
    "⏱ *Длительность:* от 7 до 30 дней\n\n"
    "📞 *Для записи на обучение* нажмите кнопку ниже — "
    "администратор свяжется с вами и расскажет подробности."
)

class UserStates(StatesGroup):
    waiting_for_payment_proof = State()
    waiting_for_firmware_code = State()
    waiting_for_vin = State()
    waiting_for_activation_code = State()
    waiting_for_training_message = State()
    waiting_for_rus_car = State()
    waiting_for_rus_price = State()
    waiting_for_rus_city = State()
    waiting_for_rus_date = State()
    waiting_for_rus_time = State()

class AdminStates(StatesGroup):
    waiting_for_new_price = State()
    waiting_for_training_desc = State()

# ================= РАБОТА С ДАННЫМИ =================
async def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "prices": {car: "Уточняйте" for car in CARS},
            "requests": [],
            "training_description": DEFAULT_TRAINING_DESC,
            "rusification_bookings": [],
            "completed_activations": []
        }
        await save_data(default_data)
        return default_data
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if "training_description" not in data:
        data["training_description"] = DEFAULT_TRAINING_DESC
    if "rusification_bookings" not in data:
        data["rusification_bookings"] = []
    if "completed_activations" not in data:
        data["completed_activations"] = []
    
    await save_data(data)
    return data

async def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def save_activation(user_id, username, full_name, car, firmware_code, vin, activation_code, source="client"):
    data = await load_data()
    activation_id = len(data["completed_activations"]) + 1
    new_activation = {
        "id": activation_id,
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "car": car,
        "firmware_code": firmware_code,
        "vin": vin,
        "activation_code": activation_code,
        "source": source,
        "completed_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    data["completed_activations"].append(new_activation)
    await save_data(data)
    print(f"✅ Активация #{activation_id} сохранена")
    return activation_id

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def parse_price(price_str):
    # Извлекает число из строки типа "5000 руб.", "5 000", "5000₽"
    if not price_str:
        return 0
    try:
        digits = re.findall(r'\d+', str(price_str).replace(' ', ''))
        if digits:
            return int(''.join(digits))
    except:
        pass
    return 0

def format_money(amount):
    # Форматирует сумму: 15000 -> "15 000 ₽"
    return f"{amount:,}".replace(',', ' ') + " ₽"

# ================= КЛАВИАТУРЫ =================
def get_main_menu_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Активация прошивок", callback_data="section_activation")
    builder.button(text="🔧 Запись на русификацию", callback_data="section_rusification")
    builder.button(text="🎓 Обучение", callback_data="section_training")
    if user_id == ADMIN_ID:
        builder.button(text="📊 Панель администратора", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()

def get_cars_keyboard():
    builder = InlineKeyboardBuilder()
    for car in CARS:
        builder.button(text=car, callback_data=f"select_car|{car}")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_prices_keyboard():
    builder = InlineKeyboardBuilder()
    for car in CARS:
        builder.button(text=f"💰 {car}", callback_data=f"edit_price|{car}")
    builder.button(text="❌ Закрыть", callback_data="close_admin")
    builder.adjust(1)
    return builder.as_markup()

def get_back_to_cars_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Выбрать другой автомобиль", callback_data="section_activation")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()

def get_cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить", callback_data="cancel_order")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()

def get_training_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Записаться на обучение", callback_data="training_signup")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()

def get_booking_action_keyboard(booking_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"booking_confirm_btn|{booking_id}")
    builder.button(text="❌ Отменить", callback_data=f"booking_cancel_btn|{booking_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_panel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Календарь записей", callback_data="admin_bookings")
    builder.button(text="✅ Выполненные активации", callback_data="admin_activations")
    builder.button(text="💰 Доход за месяц", callback_data="admin_income")
    builder.button(text="💵 Изменить цены", callback_data="admin_prices")
    builder.button(text="🎓 Изменить описание обучения", callback_data="admin_training_desc")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()

def get_booking_manage_keyboard(booking_id, status):
    # Кнопки управления записью в календаре
    builder = InlineKeyboardBuilder()
    if status == "completed":
        builder.button(text="🗑 Удалить из истории", callback_data=f"booking_delete|{booking_id}")
    elif status == "cancelled":
        builder.button(text="🗑 Удалить", callback_data=f"booking_delete|{booking_id}")
    else:
        # new или confirmed
        builder.button(text="✅ Выполнено", callback_data=f"booking_complete|{booking_id}")
        builder.button(text="🗑 Удалить", callback_data=f"booking_delete|{booking_id}")
        builder.adjust(2)
    return builder.as_markup()

# ================= ГЛАВНОЕ МЕНЮ =================
@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    text = (
        "🚗 *Центр русификации Toyota Pro*\n\n"
        "Добро пожаловать! Мы специализируемся на:\n"
        "• Русификации мультимедиа и приборных панелей\n"
        "• Активации прошивок для автомобилей\n"
        "• Обучении мастеров\n\n"
        "Выберите интересующий вас раздел:"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(message.from_user.id))

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🚗 *Центр русификации Toyota Pro*\n\n"
        "Выберите интересующий вас раздел:"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(callback.from_user.id))
    await callback.answer()

# ================= ПАНЕЛЬ АДМИНИСТРАТОРА =================
@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ только для администратора", show_alert=True)
        return
    await state.clear()
    
    data = await load_data()
    bookings = data.get("rusification_bookings", [])
    
    # Считаем краткую статистику для главной панели
    new_count = sum(1 for b in bookings if b.get("status") == "new")
    confirmed_count = sum(1 for b in bookings if b.get("status") == "confirmed")
    completed_count = sum(1 for b in bookings if b.get("status") == "completed")
    
    # Доход за текущий месяц
    now = datetime.now()
    month_income = 0
    for b in bookings:
        if b.get("status") != "completed":
            continue
        try:
            date = datetime.strptime(b.get("date", ""), "%d.%m.%Y")
            if date.month == now.month and date.year == now.year:
                month_income += parse_price(b.get("price", ""))
        except:
            pass
    
    text = (
        "📊 *Панель администратора*\n\n"
        "📈 *Краткая статистика:*\n"
        f"🆕 Новых записей: {new_count}\n"
        f"✅ Подтверждено: {confirmed_count}\n"
        f"🏆 Выполнено: {completed_count}\n\n"
        f"💰 *Доход за {now.strftime('%B %Y')}:* {format_money(month_income)}\n\n"
        "Выберите раздел для подробного просмотра:"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_panel_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_bookings")
async def admin_bookings(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа", show_alert=True)
        return
    
    data = await load_data()
    bookings = data.get("rusification_bookings", [])
    
    if not bookings:
        await callback.message.edit_text(
            "📋 Записей пока нет.",
            reply_markup=get_admin_panel_keyboard()
        )
        await callback.answer()
        return
    
    # Группируем по дате
    bookings_by_date = {}
    for b in bookings:
        date = b.get("date", "Без даты")
        if date not in bookings_by_date:
            bookings_by_date[date] = []
        bookings_by_date[date].append(b)
    
    def parse_date(d):
        try:
            return datetime.strptime(d, "%d.%m.%Y")
        except:
            return datetime.max
    
    sorted_dates = sorted(bookings_by_date.keys(), key=parse_date)
    
    text = "📅 *КАЛЕНДАРЬ ЗАПИСЕЙ*\n\n"
    text += "Нажмите кнопку под записью, чтобы отметить её как выполненную или удалить.\n\n"
    
    # Telegram ограничивает длину сообщения 4096 символами
    # Также ограничиваем количество кнопок (до 100 на сообщение)
    max_bookings = 15
    shown_count = 0
    
    for date in sorted_dates:
        if shown_count >= max_bookings:
            break
        text += f"🗓 *{date}*\n"
        for b in bookings_by_date[date]:
            if shown_count >= max_bookings:
                break
            status_emoji = {"new": "🆕", "confirmed": "✅", "cancelled": "❌", "completed": "🏆"}.get(b.get("status"), "🆕")
            text += (
                f"  {status_emoji} #{b['id']} | {b['time']} | {b['car']}\n"
                f"     👤 {b.get('full_name', '—')} | 🏙 {b['city']} | 💰 {b['price']}\n"
            )
            shown_count += 1
        text += "\n"
    
    # Статистика
    new_count = sum(1 for b in bookings if b.get("status") == "new")
    confirmed_count = sum(1 for b in bookings if b.get("status") == "confirmed")
    cancelled_count = sum(1 for b in bookings if b.get("status") == "cancelled")
    completed_count = sum(1 for b in bookings if b.get("status") == "completed")
    
    text += (
        f"\n📈 *Статистика:*\n"
        f"🆕 Новых: {new_count}\n"
        f"✅ Подтверждено: {confirmed_count}\n"
        f"🏆 Выполнено: {completed_count}\n"
        f"❌ Отменено: {cancelled_count}\n"
        f"📊 Всего: {len(bookings)}"
    )
    
    if len(bookings) > max_bookings:
        text += f"\n\n_Показаны первые {max_bookings} записей._"
    
    if len(text) > 3500:
        text = text[:3500] + "\n\n... (список обрезан)"
    
    # Создаём клавиатуру с кнопками управления для каждой записи
    builder = InlineKeyboardBuilder()
    shown_for_buttons = 0
    for date in sorted_dates:
        for b in bookings_by_date[date]:
            if shown_for_buttons >= 20:  # ограничение на кнопки
                break
            status = b.get("status", "new")
            status_label = {"new": "🆕", "confirmed": "✅", "cancelled": "❌", "completed": "🏆"}.get(status, "🆕")
            
            if status == "completed":
                builder.button(text=f"🗑 #{b['id']}", callback_data=f"booking_delete|{b['id']}")
            elif status == "cancelled":
                builder.button(text=f"🗑 #{b['id']}", callback_data=f"booking_delete|{b['id']}")
            else:
                builder.button(text=f"✅ #{b['id']}", callback_data=f"booking_complete|{b['id']}")
                builder.button(text=f"🗑 #{b['id']}", callback_data=f"booking_delete|{b['id']}")
            shown_for_buttons += 1
            if shown_for_buttons >= 20:
                break
    
    builder.button(text="🔙 Назад в панель", callback_data="admin_panel")
    builder.adjust(2)
    
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        # Если сообщение слишком длинное, отправляем без кнопок управления
        await callback.message.edit_text(
            text + "\n\n⚠️ Кнопки управления недоступны из-за длины сообщения.",
            parse_mode="Markdown",
            reply_markup=get_admin_panel_keyboard()
        )
    await callback.answer()

# НОВОЕ: Отметить запись как выполненную
@router.callback_query(F.data.startswith("booking_complete|"))
async def booking_complete_from_calendar(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа", show_alert=True)
        return
    
    booking_id = int(callback.data.split("|")[1])
    data = await load_data()
    booking = next((b for b in data["rusification_bookings"] if b["id"] == booking_id), None)
    
    if not booking:
        await callback.answer("⚠️ Запись не найдена", show_alert=True)
        return
    
    booking["status"] = "completed"
    booking["completed_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    await save_data(data)
    
    # Уведомляем клиента
    client_notification = (
        f"🏆 *Ваша запись #{booking_id} ВЫПОЛНЕНА!*\n\n"
        f"📋 *Детали:*\n"
        f"🚗 {booking['car']}\n"
        f"💰 {booking['price']}\n"
        f"🏙 {booking['city']}\n"
        f"📅 {booking['date']} в {booking['time']}\n\n"
        f"Спасибо, что выбрали нас! 🙏"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    
    try:
        await bot.send_message(
            booking["user_id"],
            client_notification,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
        print(f"✅ Запись #{booking_id} отмечена как выполненная, клиент уведомлён")
    except Exception as e:
        print(f"❌ Ошибка уведомления клиента: {e}")
    
    await callback.answer("🏆 Запись отмечена как выполненная!", show_alert=True)
    
    # Обновляем календарь
    await admin_bookings(callback)

# НОВОЕ: Удалить запись
@router.callback_query(F.data.startswith("booking_delete|"))
async def booking_delete_from_calendar(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа", show_alert=True)
        return
    
    booking_id = int(callback.data.split("|")[1])
    data = await load_data()
    booking = next((b for b in data["rusification_bookings"] if b["id"] == booking_id), None)
    
    if not booking:
        await callback.answer("⚠️ Запись не найдена", show_alert=True)
        return
    
    # Удаляем запись
    data["rusification_bookings"] = [b for b in data["rusification_bookings"] if b["id"] != booking_id]
    await save_data(data)
    
    # Уведомляем клиента (если запись не была уже отменена/выполнена)
    if booking.get("status") in ["new", "confirmed"]:
        client_notification = (
            f"❌ *Ваша запись #{booking_id} удалена*\n\n"
            f"🚗 {booking['car']}\n"
            f"📅 {booking['date']} в {booking['time']}\n\n"
            f"Свяжитесь с администратором для уточнения деталей."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="🏠 Главное меню", callback_data="main_menu")
        try:
            await bot.send_message(
                booking["user_id"],
                client_notification,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            print(f"❌ Ошибка уведомления клиента: {e}")
    
    print(f"🗑 Запись #{booking_id} удалена")
    await callback.answer("🗑 Запись удалена", show_alert=True)
    
    # Обновляем календарь
    await admin_bookings(callback)

# НОВОЕ: Доход за месяц
@router.callback_query(F.data == "admin_income")
async def admin_income(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа", show_alert=True)
        return
    
    data = await load_data()
    bookings = data.get("rusification_bookings", [])
    
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    month_name = now.strftime("%B %Y")
    
    # Фильтруем выполненные записи за текущий месяц
    month_bookings = []
    for b in bookings:
        if b.get("status") != "completed":
            continue
        try:
            date = datetime.strptime(b.get("date", ""), "%d.%m.%Y")
            if date.month == current_month and date.year == current_year:
                month_bookings.append(b)
        except:
            pass
    
    # Считаем общий доход
    total_income = sum(parse_price(b.get("price", "")) for b in month_bookings)
    
    # Группируем по автомобилям для детализации
    by_car = {}
    for b in month_bookings:
        car = b.get("car", "Неизвестно")
        if car not in by_car:
            by_car[car] = {"count": 0, "income": 0}
        by_car[car]["count"] += 1
        by_car[car]["income"] += parse_price(b.get("price", ""))
    
    # Группируем по городам
    by_city = {}
    for b in month_bookings:
        city = b.get("city", "Неизвестно")
        if city not in by_city:
            by_city[city] = {"count": 0, "income": 0}
        by_city[city]["count"] += 1
        by_city[city]["income"] += parse_price(b.get("price", ""))
    
    text = (
        f"💰 *ДОХОД ЗА {month_name.upper()}*\n\n"
        f"💵 *Общий доход:* {format_money(total_income)}\n"
        f"🏆 *Выполнено записей:* {len(month_bookings)}\n"
        f"💼 *Средний чек:* {format_money(total_income // len(month_bookings) if month_bookings else 0)}\n\n"
    )
    
    if by_car:
        text += "🚗 *По автомобилям:*\n"
        for car, stats in sorted(by_car.items(), key=lambda x: x[1]["income"], reverse=True):
            text += f"  • {car}: {stats['count']} шт. — {format_money(stats['income'])}\n"
        text += "\n"
    
    if by_city:
        text += "🏙 *По городам:*\n"
        for city, stats in sorted(by_city.items(), key=lambda x: x[1]["income"], reverse=True):
            text += f"  • {city}: {stats['count']} шт. — {format_money(stats['income'])}\n"
        text += "\n"
    
    if month_bookings:
        text += "📋 *Детализация:*\n"
        for b in sorted(month_bookings, key=lambda x: datetime.strptime(x.get("date", "01.01.2000"), "%d.%m.%Y")):
            text += (
                f"  🏆 #{b['id']} | {b.get('date')} | {b['car']}\n"
                f"     👤 {b.get('full_name', '—')} | 💰 {b['price']}\n"
            )
    else:
        text += "_В этом месяце пока нет выполненных записей._"
    
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (список обрезан)"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_panel_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_activations")
async def admin_activations(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа", show_alert=True)
        return
    
    data = await load_data()
    activations = data.get("completed_activations", [])
    
    if not activations:
        await callback.message.edit_text(
            "✅ Выполненных активаций пока нет.",
            reply_markup=get_admin_panel_keyboard()
        )
        await callback.answer()
        return
    
    activations_by_date = {}
    for a in activations:
        date = a.get("completed_at", "Без даты").split(" ")[0]
        if date not in activations_by_date:
            activations_by_date[date] = []
        activations_by_date[date].append(a)
    
    def parse_date(d):
        try:
            return datetime.strptime(d, "%d.%m.%Y")
        except:
            return datetime.max
    
    sorted_dates = sorted(activations_by_date.keys(), key=parse_date, reverse=True)
    
    text = "✅ *ВЫПОЛНЕННЫЕ АКТИВАЦИИ*\n\n"
    
    for date in sorted_dates:
        text += f"🗓 *{date}*\n"
        for a in activations_by_date[date]:
            source_emoji = "👤" if a.get("source") == "client" else "👑"
            time_part = a['completed_at'].split(' ')[1] if ' ' in a['completed_at'] else '—'
            text += (
                f"  {source_emoji} #{a['id']} | {a['car']}\n"
                f"     🕐 {time_part}\n"
                f"     🔧 FW: `{a.get('firmware_code', '—')}`\n"
                f"     🚘 VIN: `{a.get('vin', '—')}`\n"
                f"     🔑 Код: `{a['activation_code']}`\n"
                f"     👤 {a.get('full_name', '—')}\n"
            )
        text += "\n"
    
    today = datetime.now().strftime("%d.%m.%Y")
    today_count = sum(1 for a in activations if a.get("completed_at", "").startswith(today))
    week_count = 0
    for a in activations:
        try:
            act_date = datetime.strptime(a.get("completed_at", "").split(" ")[0], "%d.%m.%Y")
            if (datetime.now() - act_date).days <= 7:
                week_count += 1
        except:
            pass
    
    text += (
        f"\n📈 *Статистика:*\n"
        f"📅 Сегодня: {today_count}\n"
        f"📆 За неделю: {week_count}\n"
        f"📊 Всего: {len(activations)}"
    )
    
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (список обрезан)"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_panel_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_prices")
async def admin_prices_from_panel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа", show_alert=True)
        return
    await callback.message.edit_text(
        "💰 Выберите автомобиль для изменения цены:",
        reply_markup=get_admin_prices_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_training_desc")
async def admin_training_desc_from_panel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_training_desc)
    await callback.message.edit_text(
        "✏️ Отправьте НОВЫЙ текст описания обучения.\n\n"
        "Чтобы отменить, отправьте /cancel"
    )
    await callback.answer()

# ================= РАЗДЕЛ АКТИВАЦИЯ =================
@router.callback_query(F.data == "section_activation")
async def section_activation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    data = await load_data()
    price_list = "\n".join([f"🚗 {car}: `{price}`" for car, price in data["prices"].items()])
    text = (
        f"🔑 *Активация прошивок*\n\n"
        f"📋 *Актуальные цены:*\n{price_list}\n\n"
        f"Выберите ваш автомобиль:"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_cars_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("select_car|"))
async def process_car_selection(callback: types.CallbackQuery, state: FSMContext):
    car_model = callback.data.split("|", 1)[1]
    user_id = callback.from_user.id
    username = callback.from_user.username or f"ID: {user_id}"
    
    data = await load_data()
    price = data["prices"].get(car_model, "Уточняйте")
    
    await state.update_data(car=car_model, price=price, username=username)
    
    if user_id == ADMIN_ID:
        await state.set_state(UserStates.waiting_for_firmware_code)
        await callback.message.edit_text(
            f"👑 *Режим администратора*\n\n"
            f"🚗 Автомобиль: *{car_model}*\n"
            f"💵 Стоимость: *{price}*\n\n"
            f"⚡ *Оплата пропущена* (вы администратор)\n\n"
            f"🔧 Теперь отправьте *уникальный код прошивки*:",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        await callback.answer()
        return
    
    await state.set_state(UserStates.waiting_for_payment_proof)
    
    payment_text = (
        f"💳 *Оплата активации*\n\n"
        f"🚗 Автомобиль: *{car_model}*\n"
        f"💵 Стоимость: *{price}*\n\n"
        f"📲 *Реквизиты для оплаты по СБП:*\n"
        f"📞 Номер: `+7 (918) 024-32-27`\n"
        f"🏦 Банк: Сбербанк\n"
        f"👤 Получатель: Вадим Д.\n\n"
        f"⚠️ *Инструкция:*\n"
        f"1. Переведите точную сумму по указанным реквизитам.\n"
        f"2. После перевода отправьте в этот чат **скриншот чека** или **номер перевода**.\n"
        f"3. Затем вам нужно будет указать код прошивки и VIN-номер автомобиля.\n"
        f"4. Администратор проверит оплату и выдаст код активации!"
    )
    
    await callback.message.edit_text(payment_text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())
    await callback.answer()

@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "❌ Действие отменено.\n\n"
        "🚗 *Центр русификации Toyota Pro*\n\n"
        "Выберите интересующий вас раздел:"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(callback.from_user.id))
    await callback.answer()

@router.message(UserStates.waiting_for_payment_proof)
async def handle_payment_proof(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    state_data = await state.get_data()
    
    if message.photo:
        await state.update_data(proof_type="photo", proof_file_id=message.photo[-1].file_id)
    elif message.text:
        await state.update_data(proof_type="text", proof_text=message.text)
    else:
        await message.answer("⚠️ Пожалуйста, отправьте скриншот чека (фото) или номер перевода (текстом).")
        return
    
    await state.set_state(UserStates.waiting_for_firmware_code)
    
    await message.answer(
        "✅ Чек принят!\n\n"
        "🔧 Теперь отправьте мне *уникальный код прошивки* для вашего автомобиля.",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@router.message(UserStates.waiting_for_firmware_code)
async def handle_firmware_code(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте код прошивки текстом.")
        return
    
    firmware_code = message.text.strip()
    await state.update_data(firmware_code=firmware_code)
    await state.set_state(UserStates.waiting_for_vin)
    
    await message.answer(
        f"✅ Код прошивки принят: `{firmware_code}`\n\n"
        "🚗 Теперь отправьте мне *VIN-номер* вашего автомобиля.\n\n"
        "_(17 символов, например: JN1TBNT32Z0L00001)_",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@router.message(UserStates.waiting_for_vin)
async def handle_vin(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте VIN-номер текстом.")
        return
    
    vin = message.text.strip().upper()
    
    if len(vin) != 17 or not re.match(r"^[A-HJ-NPR-Z0-9]{17}$", vin):
        await message.answer(
            "⚠️ *Некорректный VIN-номер!*\n\n"
            "VIN должен содержать ровно 17 символов.\n\n"
            "Попробуйте ещё раз:",
            parse_mode="Markdown"
        )
        return
    
    await state.update_data(vin=vin)
    
    state_data = await state.get_data()
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        await state.set_state(UserStates.waiting_for_activation_code)
        await message.answer(
            f"✅ VIN принят: `{vin}`\n\n"
            f"⚡ *Введите код активации:*",
            parse_mode="Markdown"
        )
        return
    
    proof_type = state_data.get("proof_type", "text")
    car_model = state_data.get("car", "Неизвестно")
    price = state_data.get("price", "Неизвестно")
    username = state_data.get("username", f"ID: {user_id}")
    firmware_code = state_data.get("firmware_code", "Неизвестно")
    
    admin_caption = (
        f"💰 НОВАЯ ЗАЯВКА НА АКТИВАЦИЮ\n\n"
        f"ID клиента: {user_id}\n"
        f"Юзернейм: {username}\n"
        f"Автомобиль: {car_model}\n"
        f"Сумма: {price}\n\n"
        f"Код прошивки: {firmware_code}\n"
        f"VIN: {vin}\n\n"
        f"Проверьте оплату и ответьте на это сообщение кодом активации."
    )
    
    if len(admin_caption) > 1024:
        admin_caption = admin_caption[:1020] + "..."
    
    try:
        if proof_type == "photo":
            await bot.send_photo(ADMIN_ID, state_data.get("proof_file_id"), caption=admin_caption)
        else:
            await bot.send_message(ADMIN_ID, f"{admin_caption}\n\nЧек (текст): {state_data.get('proof_text', '')}")
        
        await state.clear()
        await message.answer(
            "✅ Все данные получены!\n\n"
            f"🔧 Код прошивки: `{firmware_code}`\n"
            f"🚘 VIN: `{vin}`\n\n"
            "Ожидайте код активации.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"❌ ОШИБКА: {type(e).__name__}: {e}")
        await message.answer("❌ Произошла техническая ошибка.")

@router.message(UserStates.waiting_for_activation_code)
async def handle_activation_code_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте код активации текстом.")
        return
    
    activation_code = message.text.strip()
    state_data = await state.get_data()
    car_model = state_data.get("car", "Неизвестно")
    firmware_code = state_data.get("firmware_code", "Неизвестно")
    vin = state_data.get("vin", "Неизвестно")
    
    act_id = await save_activation(
        user_id=ADMIN_ID,
        username=message.from_user.username or "admin",
        full_name=message.from_user.full_name,
        car=car_model,
        firmware_code=firmware_code,
        vin=vin,
        activation_code=activation_code,
        source="admin_self"
    )
    
    await state.clear()
    
    await message.answer(
        f"🎉 *Код активации выдан!*\n\n"
        f"🔑 *Код:* `{activation_code}`\n"
        f"📋 *Номер в истории:* #{act_id}\n\n"
        f"🚗 Автомобиль: {car_model}\n"
        f"🔧 Код прошивки: `{firmware_code}`\n"
        f"🚘 VIN: `{vin}`\n\n"
        f"✅ Заявка завершена и сохранена в истории!",
        parse_mode="Markdown",
        reply_markup=get_back_to_cars_keyboard()
    )

# ================= РАЗДЕЛ ЗАПИСЬ НА РУСИФИКАЦИЮ =================
@router.callback_query(F.data == "section_rusification")
async def section_rusification(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(UserStates.waiting_for_rus_car)
    
    text = (
        "🔧 *Запись на русификацию*\n\n"
        "Мы проводим профессиональную русификацию мультимедиа "
        "и приборных панелей автомобилей.\n\n"
        "📋 *Шаги записи:*\n"
        "1. Укажите ваш автомобиль\n"
        "2. Укажите согласованную цену\n"
        "3. Укажите город\n"
        "4. Укажите удобную дату\n"
        "5. Укажите ориентировочное время\n\n"
        "🚗 *Напишите модель вашего автомобиля:*"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())
    await callback.answer()

@router.message(UserStates.waiting_for_rus_car)
async def rus_car(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Укажите модель автомобиля текстом.")
        return
    car = message.text.strip()
    await state.update_data(rus_car=car)
    await state.set_state(UserStates.waiting_for_rus_price)
    await message.answer(
        f"✅ Автомобиль: *{car}*\n\n💰 Теперь укажите *согласованную цену* русификации.",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@router.message(UserStates.waiting_for_rus_price)
async def rus_price(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Укажите цену текстом.")
        return
    price = message.text.strip()
    await state.update_data(rus_price=price)
    await state.set_state(UserStates.waiting_for_rus_city)
    await message.answer(
        f"✅ Цена: *{price}*\n\n🏙 Теперь укажите *город*:",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@router.message(UserStates.waiting_for_rus_city)
async def rus_city(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Укажите город текстом.")
        return
    city = message.text.strip()
    await state.update_data(rus_city=city)
    await state.set_state(UserStates.waiting_for_rus_date)
    await message.answer(
        f"✅ Город: *{city}*\n\n📅 Укажите *дату* в формате ДД.ММ.ГГГГ (например: 25.10.2026):",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@router.message(UserStates.waiting_for_rus_date)
async def rus_date(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Укажите дату текстом.")
        return
    date_str = message.text.strip()
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        formatted_date = date_obj.strftime("%d.%m.%Y")
    except ValueError:
        await message.answer(
            "⚠️ *Неверный формат даты!*\n\nИспользуйте: ДД.ММ.ГГГГ\nПопробуйте ещё раз:",
            parse_mode="Markdown"
        )
        return
    await state.update_data(rus_date=formatted_date)
    await state.set_state(UserStates.waiting_for_rus_time)
    await message.answer(
        f"✅ Дата: *{formatted_date}*\n\n🕐 Укажите *ориентировочное время* (например: 14:00):",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@router.message(UserStates.waiting_for_rus_time)
async def rus_time(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Укажите время текстом.")
        return
    time_str = message.text.strip()
    await state.update_data(rus_time=time_str)
    
    state_data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or f"ID: {user_id}"
    full_name = message.from_user.full_name
    
    car = state_data.get("rus_car")
    price = state_data.get("rus_price")
    city = state_data.get("rus_city")
    date = state_data.get("rus_date")
    time = state_data.get("rus_time")
    
    data = await load_data()
    booking_id = len(data["rusification_bookings"]) + 1
    new_booking = {
        "id": booking_id,
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "car": car,
        "price": price,
        "city": city,
        "date": date,
        "time": time,
        "status": "new",
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    data["rusification_bookings"].append(new_booking)
    await save_data(data)
    
    admin_text = (
        f"🔧 НОВАЯ ЗАПИСЬ НА РУСИФИКАЦИЮ #{booking_id}\n\n"
        f"👤 Клиент: {full_name}\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Юзернейм: @{username}\n\n"
        f"🚗 Автомобиль: {car}\n"
        f"💰 Цена: {price}\n"
        f"🏙 Город: {city}\n"
        f"📅 Дата: {date}\n"
        f"🕐 Время: {time}\n\n"
        f"📝 Статус: НОВАЯ\n"
        f"⏰ Создана: {new_booking['created_at']}"
    )
    
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_booking_action_keyboard(booking_id))
        print(f"✅ Запись #{booking_id} создана")
    except Exception as e:
        print(f"❌ Ошибка отправки записи: {e}")
    
    await state.clear()
    
    client_text = (
        f"✅ *Ваша запись принята!*\n\n"
        f"📋 *Номер записи:* #{booking_id}\n\n"
        f"🚗 Автомобиль: {car}\n"
        f"💰 Цена: {price}\n"
        f"🏙 Город: {city}\n"
        f"📅 Дата: {date}\n"
        f"🕐 Время: {time}\n\n"
        f"Администратор свяжется с вами для подтверждения."
    )
    
    await message.answer(client_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(user_id))

@router.callback_query(F.data.startswith("booking_confirm_btn|"))
async def booking_confirm_btn(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для администратора", show_alert=True)
        return
    booking_id = int(callback.data.split("|")[1])
    data = await load_data()
    booking = next((b for b in data["rusification_bookings"] if b["id"] == booking_id), None)
    if not booking:
        await callback.answer("⚠️ Запись не найдена", show_alert=True)
        return
    booking["status"] = "confirmed"
    await save_data(data)
    
    client_notification = (
        f"🎉 *Ваша запись #{booking_id} ПОДТВЕРЖДЕНА!*\n\n"
        f"📋 *Детали записи:*\n"
        f"🚗 Автомобиль: {booking['car']}\n"
        f"💰 Цена: {booking['price']}\n"
        f"🏙 Город: {booking['city']}\n"
        f"📅 Дата: {booking['date']}\n"
        f"🕐 Время: {booking['time']}\n\n"
        f"✅ Администратор подтвердил вашу запись.\n"
        f"Ждём вас в указанное время!"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    
    try:
        await bot.send_message(booking["user_id"], client_notification, parse_mode="Markdown", reply_markup=builder.as_markup())
        print(f"✅ Уведомление о подтверждении #{booking_id} отправлено")
        await callback.message.edit_text(callback.message.text + "\n\n✅ *ПОДТВЕРЖДЕНА* — клиент уведомлён", parse_mode="Markdown")
        await callback.answer("✅ Запись подтверждена", show_alert=True)
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")
        await callback.answer("✅ Подтверждена, но клиент не уведомлён", show_alert=True)

@router.callback_query(F.data.startswith("booking_cancel_btn|"))
async def booking_cancel_btn(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для администратора", show_alert=True)
        return
    booking_id = int(callback.data.split("|")[1])
    data = await load_data()
    booking = next((b for b in data["rusification_bookings"] if b["id"] == booking_id), None)
    if not booking:
        await callback.answer("⚠️ Запись не найдена", show_alert=True)
        return
    booking["status"] = "cancelled"
    await save_data(data)
    
    client_notification = (
        f"❌ *Ваша запись #{booking_id} ОТМЕНЕНА*\n\n"
        f"📋 *Детали записи:*\n"
        f"🚗 Автомобиль: {booking['car']}\n"
        f"💰 Цена: {booking['price']}\n"
        f"🏙 Город: {booking['city']}\n"
        f"📅 Дата: {booking['date']}\n"
        f"🕐 Время: {booking['time']}\n\n"
        f"⚠️ К сожалению, запись отменена.\n"
        f"Свяжитесь с администратором для уточнения деталей."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    
    try:
        await bot.send_message(booking["user_id"], client_notification, parse_mode="Markdown", reply_markup=builder.as_markup())
        print(f"✅ Уведомление об отмене #{booking_id} отправлено")
        await callback.message.edit_text(callback.message.text + "\n\n❌ *ОТМЕНЕНА* — клиент уведомлён", parse_mode="Markdown")
        await callback.answer("❌ Запись отменена", show_alert=True)
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")
        await callback.answer("❌ Отменена, но клиент не уведомлён", show_alert=True)

# ================= РАЗДЕЛ ОБУЧЕНИЕ =================
@router.callback_query(F.data == "section_training")
async def section_training(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    data = await load_data()
    description = data.get("training_description", DEFAULT_TRAINING_DESC)
    try:
        await callback.message.edit_text(description, parse_mode="Markdown", reply_markup=get_training_keyboard())
    except Exception:
        await callback.message.edit_text(description, reply_markup=get_training_keyboard())
    await callback.answer()

@router.callback_query(F.data == "training_signup")
async def training_signup(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    username = callback.from_user.username or "не указан"
    admin_text = (
        f"🎓 НОВАЯ ЗАЯВКА НА ОБУЧЕНИЕ\n\n"
        f"ID клиента: {user_id}\n"
        f"Юзернейм: {username}\n"
        f"Имя: {callback.from_user.full_name}\n\n"
        f"Свяжитесь с клиентом для записи на обучение."
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text)
    except Exception as e:
        print(f"❌ ОШИБКА ОТПРАВКИ ЗАЯВКИ: {e}")
        await callback.answer("❌ Не удалось отправить заявку.", show_alert=True)
        return
    await state.set_state(UserStates.waiting_for_training_message)
    await callback.message.edit_text(
        "✅ Заявка на обучение отправлена!\n\n"
        "Администратор свяжется с вами в ближайшее время.\n\n"
        "Можете сразу написать сюда:\n"
        "• модель вашего автомобиля\n"
        "• ваш город\n"
        "• удобный формат: онлайн или очно\n\n"
        "Всё, что вы напишете, будет пересылаться администратору."
    )
    await callback.answer()

@router.message(UserStates.waiting_for_training_message)
async def handle_training_message(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith('/'):
        return
    user_id = message.from_user.id
    username = message.from_user.username or "не указан"
    text = message.text or message.caption or "(вложение)"
    admin_text = (
        f"🎓 СООБЩЕНИЕ ПО ОБУЧЕНИЮ\n\n"
        f"ID клиента: {user_id}\n"
        f"Юзернейм: {username}\n"
        f"Имя: {message.from_user.full_name}\n\n"
        f"Текст: {text}"
    )
    if len(admin_text) > 4000:
        admin_text = admin_text[:4000]
    try:
        if message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text)
        else:
            await bot.send_message(ADMIN_ID, admin_text)
        await message.answer("✅ Сообщение передано администратору.", reply_markup=get_main_menu_keyboard(user_id))
    except Exception as e:
        print(f"❌ ОШИБКА ПЕРЕСЫЛКИ: {e}")
        await message.answer("❌ Не удалось отправить сообщение.")

# ================= АДМИН-ПАНЕЛЬ (команды) =================
@router.message(Command("getid"))
async def cmd_getid(message: types.Message):
    await message.answer(f"Ваш Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

@router.message(Command("prices_admin"))
async def cmd_prices_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Выберите автомобиль для изменения цены:", reply_markup=get_admin_prices_keyboard())

@router.callback_query(F.data.startswith("edit_price|"))
async def process_edit_price_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    car_model = callback.data.split("|", 1)[1]
    await state.update_data(car_to_edit=car_model)
    await state.set_state(AdminStates.waiting_for_new_price)
    await callback.message.edit_text(
        f"✏️ Вы редактируете цену для: *{car_model}*\n\nОтправьте мне новую цену:",
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_new_price)
async def process_new_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    new_price = message.text.strip()
    state_data = await state.get_data()
    car_model = state_data.get("car_to_edit")
    data = await load_data()
    data["prices"][car_model] = new_price
    await save_data(data)
    await state.clear()
    await message.answer(f"✅ Цена обновлена: `{new_price}`", parse_mode="Markdown")
    await message.answer("Выберите следующий автомобиль:", reply_markup=get_admin_prices_keyboard())

@router.message(Command("edit_training"))
async def cmd_edit_training(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_training_desc)
    await message.answer("✏️ Отправьте НОВЫЙ текст описания обучения.\n\nЧтобы отменить: /cancel")

@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=get_main_menu_keyboard(message.from_user.id))

@router.message(AdminStates.waiting_for_training_desc)
async def process_training_desc(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text:
        await message.answer("⚠️ Отправьте описание текстом.")
        return
    new_desc = message.text
    data = await load_data()
    data["training_description"] = new_desc
    await save_data(data)
    await state.clear()
    await message.answer("✅ Описание обучения обновлено!")
    await message.answer(new_desc, parse_mode="Markdown", reply_markup=get_training_keyboard())

@router.callback_query(F.data == "close_admin")
async def close_admin_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.delete()

@router.message(F.reply_to_message)
async def handle_admin_reply(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    replied_msg = message.reply_to_message
    if not replied_msg or replied_msg.from_user.id != bot.id:
        return
    text_to_search = replied_msg.caption or replied_msg.text or ""
    
    if "ОБУЧЕНИЕ" in text_to_search:
        training_match = re.search(r"ID клиента: (\d+)", text_to_search)
        if training_match:
            try:
                await bot.send_message(int(training_match.group(1)), message.text or message.caption or "")
                await message.answer("✅ Ответ отправлен клиенту.")
            except Exception as e:
                await message.answer(f"❌ Ошибка отправки: {e}")
        return
    
    match = re.search(r"ID клиента: (\d+)", text_to_search)
    if not match:
        match = re.search(r"ID: (\d+)", text_to_search)
    if not match:
        match = re.search(r"(\d{5,})", text_to_search)
    if not match:
        await message.answer("⚠️ Не могу найти ID пользователя.")
        return
    
    target_user_id = int(match.group(1))
    activation_code = message.text
    
    car_match = re.search(r"Автомобиль: (.+?)(?:\n|$)", text_to_search)
    fw_match = re.search(r"Код прошивки: (.+?)(?:\n|$)", text_to_search)
    vin_match = re.search(r"VIN: (.+?)(?:\n|$)", text_to_search)
    username_match = re.search(r"Юзернейм: (.+?)(?:\n|$)", text_to_search)
    
    car_model = car_match.group(1).strip() if car_match else "Неизвестно"
    firmware_code = fw_match.group(1).strip() if fw_match else "Неизвестно"
    vin = vin_match.group(1).strip() if vin_match else "Неизвестно"
    username = username_match.group(1).strip() if username_match else "неизвестно"
    
    try:
        chat = await bot.get_chat(target_user_id)
        full_name = chat.full_name or "—"
    except:
        full_name = "—"
    
    act_id = await save_activation(
        user_id=target_user_id,
        username=username,
        full_name=full_name,
        car=car_model,
        firmware_code=firmware_code,
        vin=vin,
        activation_code=activation_code,
        source="client"
    )
    
    try:
        await bot.send_message(
            target_user_id, 
            f"🎉 *Оплата подтверждена!*\n\n"
            f"🔑 *Ваш код активации:*\n`{activation_code}`\n\n"
            f"Спасибо за использование нашего сервиса!",
            parse_mode="Markdown",
            reply_markup=get_back_to_cars_keyboard()
        )
        await message.answer(f"✅ Код активации отправлен пользователю!\n📋 Сохранено в истории под #{act_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ================= УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК =================
@router.message()
async def handle_any_message(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith('/'):
        return
    current_state = await state.get_state()
    if current_state:
        return
    text = (
        "🚗 *Центр русификации Toyota Pro*\n\n"
        "Выберите интересующий вас раздел:"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(message.from_user.id))

async def main():
    keep_alive()  # <-- ЭТА СТРОКА ОБЯЗАТЕЛЬНА
    
    print("=" * 60)
    print("✅ БОТ УСПЕШНО ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
    print("=" * 60)
    print(f"ADMIN_ID: {ADMIN_ID}")
    print(f"Bot ID: {bot.id}")
    print("=" * 60)
    print(" Панель администратора доступна через главное меню")
    print("=" * 60)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
