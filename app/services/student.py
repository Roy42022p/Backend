from fastapi import HTTPException
from typing import  Tuple, Optional
from sqlalchemy import  select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models import Student, Group, Telegram
from app.core.logger import logger
from app.utils.security import hash_password
from app.utils.roles import Role
from app.api.v1.schemas.student import UpdateStudent



class StudentService:
    @staticmethod
    async def get_student_by_login(login: str, db: AsyncSession) -> Student:
        """
        Получение студента по его логину.

        Args:
            login: Логин студента
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Student: Найденный студент

        Raises:
            HTTPException: 404 - Студент не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            result = await db.execute(
                select(Student)
                .options(
                    joinedload(Student.group).joinedload(Group.curator),
                    joinedload(Student.telegram)
                )
                .where(Student.login == login)
            )
            student = result.scalars().first()

            if not student:
                logger.warning(f"[ПОЛУЧЕНИЕ СТУДЕНТА] Студент не найден: логин {login}")
                raise HTTPException(
                    status_code=404,
                    detail="Студент не найден"
                )

            logger.info(f"[ПОЛУЧЕНИЕ СТУДЕНТА] Найден студент: {login}")
            return student

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ СТУДЕНТА] Ошибка базы данных для {login}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при получении данных студента"
            ) from e

    @staticmethod
    async def get_student_by_fio(first_name: str, last_name: str, patronymic: str, db: AsyncSession) -> Student:
        """
        Получение студента по его ФИО.

        Args:
            first_name: Имя студента
            last_name: Фамилия студента
            patronymic: Отчество студента
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Student: Найденный студент

        Raises:
            HTTPException: 404 - Студент не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            result = await db.execute(
                select(Student).where(
                    Student.first_name.ilike(first_name),
                    Student.last_name.ilike(last_name),
                    Student.patronymic.ilike(patronymic)
                )
            )
            student = result.scalars().first()

            if not student:
                logger.warning(f"[ПОЛУЧЕНИЕ СТУДЕНТА ПО ФИО] Студент не найден: {last_name} {first_name} {patronymic}")
                raise HTTPException(
                    status_code=404,
                    detail="Студент не найден"
                )

            logger.info(f"[ПОЛУЧЕНИЕ СТУДЕНТА ПО ФИО] Найден студент: {last_name} {first_name} {patronymic}")
            return student

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ СТУДЕНТА ПО ФИО] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при поиске студента по ФИО"
            ) from e

    @staticmethod
    async def get_students_by_group_id(group_id: int, db: AsyncSession, exam_id: int = None):
        """
        Получение списка студентов по идентификатору группы и, если передан, оценок за конкретный экзамен.

        Args:
            group_id: Идентификатор группы
            db: Асинхронная сессия SQLAlchemy
            exam_id: Идентификатор экзамена (необязательно)

        Returns:
            list: Список кортежей (студент, оценка)

        Raises:
            HTTPException: 404 - Группа не найдена
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            group_result = await db.execute(
                select(Group).where(Group.id == group_id)
            )
            group = group_result.scalars().first()

            if not group:
                logger.warning(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Группа не найдена: ID {group_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Группа не найдена"
                )

            students_result = await db.execute(
                select(Student)
                .where(Student.group_id == group.id)
                .options(selectinload(Student.marks))
            )
            students = students_result.scalars().all()

            results = []
            for student in students:
                grade = None
                if exam_id is not None:
                    for mark in student.marks:
                        if mark.exam_id == exam_id:
                            grade = mark.mark
                            break
                else:
                    grade = student.marks[0].mark if student.marks else None

                results.append((student, grade))

            logger.info(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Получено {len(results)} студентов для группы ID {group_id}")
            return results

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при получении студентов"
            ) from e

    @staticmethod
    async def get_all_students(db: AsyncSession, current_user: dict):
        """
        Получение списка всех студентов.

        Args:
            db: Асинхронная сессия SQLAlchemy
            current_user: Информация о текущем пользователе

        Returns:
            list: Список студентов

        Raises:
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            stmt = select(Student)

            if current_user.get("role") == Role.CURATOR:
                stmt = stmt.join(Student.group).where(Group.curator_id == current_user.get("id"))

            result = await db.execute(stmt)
            students = result.scalars().all()

            logger.info(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Получено {len(students)} студентов")
            return students

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при получении списка студентов"
            ) from e

    @staticmethod
    async def update_student(student_id: int, student_data: UpdateStudent, db: AsyncSession) -> Student:
        """
        Обновление информации о студенте.

        Args:
            student_id: Идентификатор студента
            student_data: Новые данные студента
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Student: Обновленный студент

        Raises:
            HTTPException: 404 - Студент не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            result = await db.execute(select(Student).where(Student.id == student_id))
            student = result.scalars().first()

            if not student:
                logger.warning(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Студент не найден: ID {student_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Студент не найден"
                )

            update_data = student_data.model_dump(exclude_unset=True)
            if "dateOfBirth" in update_data:
                update_data["date_of_birth"] = update_data.pop("dateOfBirth")

            for field, value in update_data.items():
                if hasattr(student, field):
                    setattr(student, field, value)

            await db.commit()
            await db.refresh(student)

            logger.info(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Студент обновлен: ID {student_id}")
            return student

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Ошибка базы данных для ID {student_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при обновлении данных студента"
            ) from e

    @staticmethod
    async def delete_student(student_id: int, db: AsyncSession) -> bool:
        """
        Удаление студента по ID.

        Args:
            student_id: Идентификатор студента
            db: Асинхронная сессия SQLAlchemy

        Returns:
            bool: Результат операции (True при успешном удалении)

        Raises:
            HTTPException: 404 - Студент не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            student = await db.get(Student, student_id)

            if not student:
                logger.warning(f"[УДАЛЕНИЕ СТУДЕНТА] Студент не найден: ID {student_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Студент не найден"
                )

            await db.delete(student)
            await db.commit()

            logger.info(f"[УДАЛЕНИЕ СТУДЕНТА] Студент удален: ID {student_id}")
            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[УДАЛЕНИЕ СТУДЕНТА] Ошибка базы данных для ID {student_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при удалении студента"
            ) from e

    @staticmethod
    async def set_student_password_and_telegram(
            student_id: int,
            password: str,
            telegram_id: int,
            db: AsyncSession
    ) -> Student:
        """
        Установка пароля и Telegram ID для студента.

        Args:
            student_id: Идентификатор студента
            password: Пароль студента
            telegram_id: Telegram ID студента
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Student: Обновленный студент

        Raises:
            HTTPException: 404 - Студент не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            student = await db.get(Student, student_id)

            if not student:
                logger.warning(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Студент не найден: ID {student_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Студент не найден"
                )

            result = await db.execute(
                select(Telegram).where(Telegram.telegram_id == telegram_id)
            )
            telegram = result.scalars().first()

            if not telegram:
                telegram = Telegram(telegram_id=telegram_id)
                db.add(telegram)
                await db.flush()

            hashed_pw = hash_password(password)
            student.password = hashed_pw
            student.telegram_id = telegram.id
            student.verif = True

            await db.commit()
            await db.refresh(student)

            logger.info(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Студент обновлен: ID {student_id}")
            return student

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Ошибка базы данных для ID {student_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при обновлении студента"
            ) from e

    @staticmethod
    async def _check_group_exists(group_name: str, db: AsyncSession) -> Optional[Group]:
        """Вспомогательный метод для проверки наличия группы."""
        group_result = await db.execute(
            select(Group).where(func.lower(Group.name) == func.lower(group_name))
        )
        return group_result.scalars().first()

    @staticmethod
    async def _check_student_exists(
            last_name: str,
            first_name: str,
            patronymic: str,
            group_id: int,
            db: AsyncSession
    ) -> bool:
        """Вспомогательный метод для проверки существования студента."""
        existing_student = await db.execute(
            select(Student).where(
                Student.last_name == last_name,
                Student.first_name == first_name,
                Student.patronymic == patronymic,
                Student.group_id == group_id
            )
        )
        return existing_student.scalars().first() is not None

    @staticmethod
    async def _generate_login(last_name: str, first_name: str, patronymic: str) -> str:
        """Генерация логина на основе ФИО."""
        cyrillic_to_latin = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
            'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }

        def transliterate(text: str) -> str:
            return ''.join(cyrillic_to_latin.get(c.lower(), c.lower()) for c in text)

        last = transliterate(last_name.strip())
        f = transliterate(first_name.strip()[0:1]).upper()
        m = transliterate(patronymic.strip()[0:1]).upper()

        return f"{last}{f}{m}"

    @staticmethod
    async def import_students_from_table(students_data: list, db: AsyncSession) -> Tuple[int, list]:
        """
        Импорт студентов из таблицы.

        Args:
            students_data: Список данных для импорта
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Tuple[int, list]: Количество импортированных студентов и список ошибок

        Raises:
            HTTPException: 500 - Ошибка сохранения данных
        """
        imported_count = 0
        errors = []

        try:
            for entry in students_data:
                try:
                    parts = entry.full_name.split()
                    if len(parts) != 3:
                        errors.append(f"Пропущена запись (неверный формат ФИО): {entry.full_name}")
                        continue

                    last_name, first_name, patronymic = parts

                    group = await StudentService._check_group_exists(entry.group_name, db)

                    if not group:
                        errors.append(
                            f"Пропущена запись (группа не найдена): {entry.full_name} — группа '{entry.group_name}'")
                        continue

                    if await StudentService._check_student_exists(last_name, first_name, patronymic, group.id, db):
                        continue

                    login = await StudentService._generate_login(last_name, first_name, patronymic)

                    new_student = Student(
                        last_name=last_name,
                        first_name=first_name,
                        patronymic=patronymic,
                        group_id=group.id,
                        login=login,
                        password=None,
                        verif=False,
                        role=Role.STUDENT
                    )

                    db.add(new_student)
                    imported_count += 1

                except Exception as e:
                    errors.append(f"Ошибка в записи {entry.full_name}: {str(e)}")
                    logger.error(f"[ИМПОРТ СТУДЕНТОВ] Ошибка при обработке {entry.full_name}: {str(e)}")
                    continue

            await db.commit()
            logger.info(f"[ИМПОРТ СТУДЕНТОВ] Импортировано {imported_count} студентов")
            return imported_count, errors

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ИМПОРТ СТУДЕНТОВ] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при импорте студентов"
            ) from e

