import asyncio
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.schemas.mark import MarkImportSchema
from app.models import Mark, Exam, Group, Student
from app.core.logger import logger
from fastapi import HTTPException
from uuid import uuid4

from app.services.exam import ExamService
from app.utils.bot import notify_student_mark


async def send_notifications_with_delay(notifications: List[tuple]):
    """
    Асинхронно отправляет уведомления студентам с задержкой 10 секунд между сообщениями.

    Args:
        notifications: Список кортежей (student_id, exam_name, mark)
    """
    for student_id, exam_name, mark in notifications:
        try:
            await notify_student_mark(student_id, exam_name, mark)
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"[ОТПРАВКА УВЕДОМЛЕНИЯ] Ошибка отправки уведомления студенту {student_id}: {e}")


class MarkService:
    @staticmethod
    async def batch_update_marks(marks_data: List[Any], db: AsyncSession) -> int:
        """
        Массовое обновление оценок студентов.

        Args:
            marks_data: Список объектов с данными оценок (student_id, exam_id, mark)
            db: Асинхронная сессия SQLAlchemy

        Returns:
            int: Количество обновленных или добавленных оценок

        Raises:
            HTTPException: 400 - Ошибка валидации данных
            HTTPException: 500 - Ошибка базы данных
        """
        updated_count = 0
        notifications = []

        try:
            for item in marks_data:
                student_id = item.student_id
                exam_id = item.exam_id
                raw_mark = item.mark

                if not student_id or not exam_id:
                    logger.warning("[ОБНОВЛЕНИЕ ОЦЕНОК] Пропущены обязательные поля student_id или exam_id")
                    raise HTTPException(
                        status_code=400,
                        detail="Пропущены обязательные поля student_id или exam_id"
                    )

                if raw_mark is None or str(raw_mark).lower() in ('н/а', 'нет', ''):
                    mark = None
                else:
                    try:
                        mark = int(raw_mark)
                        if mark < 0 or mark > 5:
                            raise ValueError("Оценка должна быть от 0 до 5")
                    except ValueError as e:
                        logger.warning(f"[ОБНОВЛЕНИЕ ОЦЕНОК] Неверный формат оценки: {raw_mark} - {str(e)}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Неверный формат оценки: {raw_mark}. {str(e)}"
                        ) from e

                exam = await ExamService.get_exam_details(exam_id, db)
                exam_name = exam.discipline if exam else "Экзамен"

                result = await db.execute(
                    select(Mark).where(
                        Mark.student_id == student_id,
                        Mark.exam_id == exam_id
                    )
                )
                existing_mark = result.scalars().first()

                if existing_mark:
                    if existing_mark.mark != mark:
                        existing_mark.mark = mark
                        updated_count += 1
                        notifications.append((student_id, exam_name, mark))
                else:
                    new_mark = Mark(student_id=student_id, exam_id=exam_id, mark=mark)
                    db.add(new_mark)
                    updated_count += 1
                    notifications.append((student_id, exam_name, mark))

            await db.commit()
            logger.info(f"[ОБНОВЛЕНИЕ ОЦЕНОК] Успешно обновлено или добавлено {updated_count} оценок")

            asyncio.create_task(send_notifications_with_delay(notifications))

            return updated_count

        except Exception as e:
            logger.error(f"[ОБНОВЛЕНИЕ ОЦЕНОК] Ошибка при обновлении оценок: {e}")
            raise

    @staticmethod
    async def get_exam_full_info(exam_id: int, db: AsyncSession) -> Dict[str, Any]:
        """
        Получение полной информации об экзамене для генерации документа.

        Args:
            exam_id: Идентификатор экзамена
            db: Асинхронная сессия SQLAlchemy

        Returns:
            dict: Полная информация об экзамене для генерации документа

        Raises:
            HTTPException: 404 - Экзамен не найден
            HTTPException: 500 - Ошибка при получении данных
        """
        try:
            result = await db.execute(
                select(Exam)
                .where(Exam.id == exam_id)
                .options(
                    selectinload(Exam.marks).selectinload(Mark.student),
                    selectinload(Exam.group).selectinload(Group.curator),
                    selectinload(Exam.curator)
                )
            )
            exam = result.scalars().first()

            if not exam:
                logger.warning(f"[ПОЛУЧЕНИЕ ДАННЫХ ЭКЗАМЕНА] Экзамен не найден: ID {exam_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Экзамен не найден"
                )

            group_name = exam.group.name if exam.group else "Не указано"

            course = str(exam.course) if exam.course else "Не указан"
            semester = str(exam.semester) if exam.semester else "Не указан"

            exam_date = str(exam.holding_date) if exam.holding_date else "Не указана"
            teacher = f"{exam.curator.last_name} {exam.curator.first_name} {exam.curator.patronymic}" \
                if exam.curator else "Не указан"

            doc_type = "credits" if exam.type == "credits" else "exam"

            students = []
            for mark in exam.marks:
                student = mark.student
                full_name = f"{student.last_name} {student.first_name} {student.patronymic}"
                grade = str(mark.mark) if mark.mark is not None else "-"
                students.append({"name": full_name, "grade": grade})

            unique_name = f"document_{uuid4().hex}"

            logger.info(f"[ПОЛУЧЕНИЕ ДАННЫХ ЭКЗАМЕНА] Получена информация для экзамена ID {exam_id}")

            return {
                "name": unique_name,
                "group": group_name,
                "course": course,
                "semester": semester,
                "discipline": exam.discipline,
                "exam_date": exam_date,
                "teacher": teacher,
                "students": students,
                "doc_type": doc_type
            }

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ ДАННЫХ ЭКЗАМЕНА] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при получении данных экзамена"
            ) from e
        except Exception as e:
            logger.error(f"[ПОЛУЧЕНИЕ ДАННЫХ ЭКЗАМЕНА] Неизвестная ошибка: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Произошла неизвестная ошибка при получении данных экзамена"
            ) from e

    async def import_marks_from_table(marks_data: List[MarkImportSchema], db: AsyncSession) -> Tuple[int, List[str]]:
        """
        Импорт оценок из таблицы.

        Args:
            marks_data: Список данных для импорта
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Tuple[int, list]: Кол-во обработанных записей и список ошибок
        """
        imported_count = 0
        errors = []

        try:
            for entry in marks_data:
                try:
                    exam_id = int(entry.id)

                    name_parts = entry.last_fist_name.strip().split()
                    if len(name_parts) < 2:
                        errors.append(f"Некорректный формат имени: {entry.last_fist_name}")
                        continue

                    last_name, first_name = name_parts[0], name_parts[1]

                    student = await db.execute(
                        select(Student).where(
                            Student.first_name.ilike(first_name),
                            Student.last_name.ilike(last_name)
                        )
                    )
                    student = student.scalars().first()

                    if not student:
                        errors.append(f"Студент не найден: {entry.last_fist_name}")
                        continue

                    raw_mark = str(entry.mark).strip().lower() if entry.mark is not None else None
                    mark_value: Optional[int] = None

                    if raw_mark is None or raw_mark == "н/а" or raw_mark == "na":
                        mark_value = None
                    else:
                        try:
                            mark_value = int(raw_mark)
                            if mark_value not in {2, 3, 4, 5}:
                                errors.append(f"Оценка вне диапазона (2–5): {entry.mark} ({entry.last_fist_name})")
                                continue
                        except ValueError:
                            errors.append(f"Оценка должна быть числом или 'н/а': {entry.mark} ({entry.last_fist_name})")
                            continue

                    existing = await db.execute(
                        select(Mark).where(
                            Mark.exam_id == exam_id,
                            Mark.student_id == student.id
                        )
                    )
                    existing_mark = existing.scalars().first()

                    if existing_mark:
                        existing_mark.mark = mark_value
                    else:
                        new_mark = Mark(
                            exam_id=exam_id,
                            student_id=student.id,
                            mark=mark_value
                        )
                        db.add(new_mark)

                    imported_count += 1

                except Exception as e:
                    logger.error(f"[ИМПОРТ ОЦЕНОК] Ошибка при обработке записи {entry.last_fist_name}: {e}")
                    errors.append(f"Ошибка записи: {entry.last_fist_name} — {str(e)}")
                    continue

            await db.commit()
            logger.info(f"[ИМПОРТ ОЦЕНОК] Импортировано {imported_count} оценок")
            return imported_count, errors

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ИМПОРТ ОЦЕНОК] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при импорте оценок"
            ) from e