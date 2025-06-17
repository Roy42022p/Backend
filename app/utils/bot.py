import asyncio
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import get_db
from app.models import Exam, Student, Curator, Telegram
from app.services.curator import CuratorService
from app.services.student import StudentService
from app.services.exam import ExamService
from app.core.logger import logger

bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
scheduler = AsyncIOScheduler()


class RegistrationStates(StatesGroup):
    """
    Машина состояний для регистрации студента.

    Состояния:
    - fio: Ввод ФИО
    - pwd: Ввод пароля
    - student_id: Хранение идентификатора студента
    - fio_prompt_msg_id: Хранение ID сообщения с подсказкой о формате ФИО
    """
    choosing_role = State()
    fio = State()
    pwd = State()
    user_id = State()
    fio_prompt_msg_id = State()
    login = State()
    password = State()
    start_data = State()

bot_dir = Path(__file__).parent.resolve()


def validate_fio(fio: str) -> bool:
    """
    Проверка корректности формата ФИО.

    Args:
        fio: Введённое пользователем ФИО

    Returns:
        bool: Результат валидации (True, если формат корректный)
    """
    return len(fio.split()) == 3


async def send_exam_reminders():
    """
    Отправка напоминаний о предстоящих экзаменах или зачётах студентам.

    Отправляет уведомления за 1 и 3 дня до мероприятия.
    """
    try:
        today = datetime.now().date()
        logger.info("[НАПОМИНАНИЯ] Начало отправки напоминаний об экзаменах/зачётах")

        async for db in get_db():
            exams = await db.execute(
                select(Exam)
                .options(joinedload(Exam.curator))
                .where(Exam.holding_date >= today.strftime("%Y-%m-%d"))
            )
            exams = exams.scalars().all()

            for exam in exams:
                try:
                    exam_date = datetime.strptime(exam.holding_date, "%Y-%m-%d").date()
                    curator_fio = f"{exam.curator.last_name} {exam.curator.first_name} {exam.curator.patronymic or ''}".strip()
                    days_left = (exam_date - today).days

                    if days_left in [1, 3]:
                        when_text = "завтра" if days_left == 1 else "через 3 дня"
                        exam_type = "Экзамен" if exam.type.lower() == "exam" else "Зачёт"

                        telegram_ids = await ExamService.get_telegram_ids_by_exam_id(exam.id, db)

                        for tg_id in telegram_ids:
                            try:
                                await bot.send_message(
                                    chat_id=tg_id,
                                    text=f"⏰ Напоминание\n"
                                         f"📚 {exam_type} по <b>{exam.discipline}</b> {when_text}!\n"
                                         f"📅 Дата: {exam.holding_date}\n"
                                         f"👨‍🏫 Преподаватель: {curator_fio}"
                                )
                                logger.info(f"[НАПОМИНАНИЯ] Напоминание отправлено: {tg_id} | {exam.discipline}")
                                await asyncio.sleep(10)
                            except TelegramBadRequest as e:
                                logger.warning(f"[НАПОМИНАНИЯ] Ошибка отправки пользователю {tg_id}: {e}")
                except ValueError as e:
                    logger.error(f"[НАПОМИНАНИЯ] Ошибка формата даты для экзамена ID {exam.id}: {e}")
                except Exception as e:
                    logger.error(f"[НАПОМИНАНИЯ] Неизвестная ошибка при отправке напоминаний: {e}")

    except Exception as e:
        logger.error(f"[НАПОМИНАНИЯ] Неизвестная ошибка при отправке напоминаний: {e}")


async def notify_students_about_exam_link(exam_id: int, link: str):
    """
    Уведомление студентов о новой ссылке на экзамен/зачёт.

    Args:
        exam_id: Идентификатор экзамена
        link: Ссылка на билет
    """
    try:
        async for db in get_db():
            telegram_ids = await ExamService.get_telegram_ids_by_exam_id(exam_id, db)
            exam = await ExamService.get_exam_details(exam_id, db)
            break

        if not exam:
            logger.warning(f"[УВЕДОМЛЕНИЯ] Экзамен не найден: ID {exam_id}")
            return

        curator_fio = f"{exam.curator.last_name} {exam.curator.first_name} {exam.curator.patronymic or ''}".strip()
        discipline = exam.discipline
        holding_date = exam.holding_date
        exam_type = "Экзамен" if exam.type.lower() == "exam" else "Зачёт"

        message_text = (
            f"📢 <b>Внимание!</b>\n\n"
            f"📚 {exam_type} по дисциплине <b>{discipline}</b>\n"
            f"👨‍🏫 Преподаватель: <b>{curator_fio}</b>\n"
            f"📅 Дата: <b>{holding_date}</b>\n\n"
            f"🎫 Был прикреплён билет.\n\n"
            f"🍀 Удачи на {exam_type.lower()}е! 💪"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть билет", url=link)]
        ])

        for tg_id in telegram_ids:
            try:
                await bot.send_message(chat_id=tg_id, text=message_text, reply_markup=keyboard)
                logger.info(f"[УВЕДОМЛЕНИЯ] Билет отправлен: {tg_id} | {discipline}")
                await asyncio.sleep(10)
            except TelegramBadRequest as e:
                logger.warning(f"[УВЕДОМЛЕНИЯ] Ошибка отправки пользователю {tg_id}: {e}")

    except Exception as e:
        logger.error(f"[УВЕДОМЛЕНИЯ] Ошибка при рассылке уведомлений: {e}")


async def notify_students_about_exam_creation(exam_id: int):
    """
    Уведомление студентов о добавлении нового экзамена или зачёта.

    Args:
        exam_id: Идентификатор экзамена или зачёта
    """
    try:
        async for db in get_db():
            telegram_ids = await ExamService.get_telegram_ids_by_exam_id(exam_id, db)
            exam = await ExamService.get_exam_details(exam_id, db)
            break

        if not exam:
            logger.warning(f"[УВЕДОМЛЕНИЯ] Экзамен/зачёт не найден: ID {exam_id}")
            return

        curator_fio = f"{exam.curator.last_name} {exam.curator.first_name} {exam.curator.patronymic or ''}".strip()
        discipline = exam.discipline
        holding_date = exam.holding_date
        exam_type = "Экзамен" if exam.type.lower() == "exam" else "Зачёт"

        message_text = (
            f"🆕 <b>Добавлен новый {exam_type.lower()}!</b>\n\n"
            f"📚 Дисциплина: <b>{discipline}</b>\n"
            f"👨‍🏫 Преподаватель: <b>{curator_fio}</b>\n"
            f"📅 Дата проведения: <b>{holding_date}</b>\n\n"
            f"📌 Проверь расписание и подготовься заранее!"
        )

        for tg_id in telegram_ids:
            try:
                await bot.send_message(chat_id=tg_id, text=message_text)
                logger.info(f"[УВЕДОМЛЕНИЯ] Уведомление о создании отправлено: {tg_id} | {discipline}")
                await asyncio.sleep(10)
            except TelegramBadRequest as e:
                logger.warning(f"[УВЕДОМЛЕНИЯ] Ошибка отправки пользователю {tg_id}: {e}")

    except Exception as e:
        logger.error(f"[УВЕДОМЛЕНИЯ] Ошибка при уведомлении о создании экзамена/зачёта: {e}")


async def notify_student_mark(student_id: int, exam_name: str, mark: int | None):
    """
    Уведомление студента о выставленной или обновлённой оценке.

    Args:
        student_id: ID студента
        exam_name: Название экзамена/дисциплины
        mark: Оценка (None если отсутствует)
    """
    try:
        async for db in get_db():
            result = await db.execute(
                select(Student)
                .options(joinedload(Student.telegram))
                .where(Student.id == student_id)
            )
            student = result.scalars().first()
            break

        if not student or not student.telegram or not student.telegram.telegram_id:
            logger.warning(f"[УВЕДОМЛЕНИЕ] Telegram ID не найден для студента ID {student_id}")
            return

        tg_id = student.telegram.telegram_id
        mark_text = str(mark) if mark is not None else "н/а"

        text = (
            f"🎓 Ваша оценка по предмету <b>{exam_name}</b> обновлена:\n"
            f"⭐ Оценка: <b>{mark_text}</b>"
        )

        await bot.send_message(chat_id=tg_id, text=text)
        logger.info(f"[УВЕДОМЛЕНИЕ] Оценка отправлена студенту ID {student_id}")

    except TelegramBadRequest as e:
        logger.warning(f"[УВЕДОМЛЕНИЕ] Ошибка отправки уведомления студенту {student_id}: {e}")
    except Exception as e:
        logger.error(f"[УВЕДОМЛЕНИЕ] Неизвестная ошибка уведомления студенту {student_id}: {e}")


async def send_welcome_photo(user, state: FSMContext):
    await state.clear()

    async for db in get_db():
        telegram_id = user.from_user.id

        result = await db.execute(select(Telegram.telegram_id))
        all_tg_ids = result.scalars().all()

        if telegram_id in all_tg_ids:
            await user.answer("✅ Вы уже зарегистрированы!")
            return


    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Студент", callback_data="role_student"),
         InlineKeyboardButton(text="👨‍🏫 Куратор", callback_data="role_curator")]
    ])
    photo = FSInputFile(bot_dir / "logo.png")
    await user.answer_photo(
        photo=photo,
        caption=(
            f"🌟 <b>Добро пожаловать в <u>Навигатор Промежуточной Аттестации корпуса Угреша</u>, {user.from_user.first_name}</b>! 🌟\n\n"
            "📚 Здесь вы сможете зарегистрироваться и начать работу.\n\n"
            "🙋‍♂️🙋‍♀️ Пожалуйста, выберите свою роль, чтобы продолжить:"
        ),
        reply_markup=keyboard
    )
    await state.set_state(RegistrationStates.choosing_role)


@dp.message(Command("start"))
async def start_command(message: Message, state: FSMContext, command: CommandObject):
    await send_welcome_photo(message, state)

@dp.callback_query(F.data == "menu")
async def menu_handler(callback: CallbackQuery, state: FSMContext):
    await send_welcome_photo(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data.startswith("role_"))
async def choose_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    await state.update_data(role=role)
    await state.set_state(RegistrationStates.fio)
    msg = await callback.message.answer("✍️ Введите своё ФИО (например: Иванов Иван Иванович)")
    await state.update_data(fio_prompt_msg_id=msg.message_id)
    await callback.answer()

@dp.message(RegistrationStates.fio)
async def fio_handler(message: Message, state: FSMContext):
    """
    Обработчик ввода ФИО студента.

    Args:
        message: Сообщение с введённым ФИО
        state: Контекст машины состояний
    """
    fio_input = message.text.strip()
    logger.info(f"[РЕГИСТРАЦИЯ] Получено ФИО: {fio_input} | {message.from_user.id}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu")]
    ])

    if not validate_fio(fio_input):
        await message.answer("<b>❌ ФИО набрано неверно</b>. Пожалуйста, попробуйте написать снова.\n\n"
                             "<b>❓ Что не так?</b>\n"
                             "Убедитесь, что вы ввели ваше полное имя в правильном формате.\n\n"
                             "Например:\n"
                             "Иванов Иван Иванович\n\n"
                             "💡 <b>Пожалуйста</b>, вводите данные без ошибок, <b>чтобы регистрация прошла успешно!</b>",
                             reply_markup=keyboard
                             )
        return

    split_fio = fio_input.split()
    await state.update_data(fio=fio_input.lower())

    data = await state.get_data()
    prompt_msg_id = data.get("fio_prompt_msg_id")

    if prompt_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        except Exception as e:
            logger.warning(f"[РЕГИСТРАЦИЯ] Не удалось удалить подсказку о ФИО: {e}")


    try:
        role = data.get("role")
        async for db in get_db():
            if role == "student":
                user = await StudentService.get_student_by_fio(split_fio[1], split_fio[0], split_fio[2], db)
            else:
                user = await CuratorService.get_curator_by_fio(split_fio[1], split_fio[0], split_fio[2], db)
            await state.update_data(user_id=user.id)

        await state.set_state(RegistrationStates.pwd)
        await message.answer("🔐 Введите пароль (минимум 4 символа):")

    except Exception as e:
        logger.error(f"[РЕГИСТРАЦИЯ] Ошибка поиска студента: {e}")
        await message.answer("❌ Студент не найден. Проверьте ФИО и попробуйте снова.")


@dp.message(RegistrationStates.pwd)
async def pwd_handler(message: Message, state: FSMContext):
    """
    Обработчик ввода пароля студента.

    Args:
        message: Сообщение с паролем
        state: Контекст машины состояний
    """
    password = message.text.strip()
    logger.info(f"[РЕГИСТРАЦИЯ] Получен пароль для студента | {message.from_user.id}")

    if len(password) < 4:
        await message.answer("⚠️ Пароль должен содержать не менее 4 символов.")
        return

    data = await state.get_data()
    role = data.get("role")
    user_id = data.get("user_id")
    login = None

    try:
        async for db in get_db():
            if role == "student":
                student = await StudentService.set_student_password_and_telegram(
                    student_id=user_id,
                    password=password,
                    telegram_id=message.from_user.id,
                    db=db
                )
                login = student.login
            else:
                curator = await CuratorService.set_curator_password_and_telegram(
                    curator_id=user_id,
                    password=password,
                    telegram_id=message.from_user.id,
                    db=db
                )
                login = curator.login

        await message.answer(
            f"🌟 Регистрация прошла успешно! 🌟/\n\n"
            f"Мы зарегистрировали вас в системе. Вот ваши данные:\n"
            f"Ваш логин: <b>{login}</b>\n"
            f"Ваш пароль: <tg-spoiler>{password}</tg-spoiler>",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"[РЕГИСТРАЦИЯ] Регистрация успешна: {login} | {message.from_user.id}")

    except Exception as e:
        logger.error(f"[РЕГИСТРАЦИЯ] Ошибка регистрации студента: {e}")
        await message.answer("❌ Не удалось завершить регистрацию. Попробуйте позже.")
    finally:
        await state.clear()


async def on_startup():
    """Инициализация при запуске бота."""
    try:
        logger.info("[БОТ] Начало запуска бота")
        await send_exam_reminders()

        scheduler.add_job(
            send_exam_reminders,
            'cron',
            hour=9,
            minute=0
        )
        scheduler.start()
        logger.info("[БОТ] Расписание установлено: ежедневные напоминания в 09:00")

    except Exception as e:
        logger.error(f"[БОТ] Ошибка при запуске: {e}")


async def main():
    """Запуск основного цикла бота."""
    try:
        logger.info("[БОТ] Запуск бота")
        await on_startup()
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e:
        logger.critical(f"[БОТ] Критическая ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()
        logger.info("[БОТ] Сессия бота закрыта")