from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.models import Exam, Mark, Student, Telegram
from app.core.logger import logger
from app.api.v1.schemas.exam import CreateExam, ExamMarksResponse, StudentMark
from app.utils.roles import Role



class ExamService:
    @staticmethod
    async def create_exam(exam_data: CreateExam, db: AsyncSession) -> Exam:
        """
        Создание нового экзамена.

        Args:
            exam_data: Данные для создания экзамена
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Exam: Созданный экзамен

        Raises:
            HTTPException: 500 - Ошибка при создании экзамена
        """
        try:
            new_exam = Exam(
                type=exam_data.type,
                semester=exam_data.semester,
                course=exam_data.course,
                discipline=exam_data.discipline,
                holding_date=exam_data.holding_date,
                group_id=exam_data.group_id,
                curator_id=exam_data.curator_id
            )

            db.add(new_exam)
            await db.commit()
            await db.refresh(new_exam)

            logger.info(f"[СОЗДАНИЕ ЭКЗАМЕНА] Создан экзамен ID {new_exam.id}, дисциплина: {new_exam.discipline}")
            return new_exam

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[СОЗДАНИЕ ЭКЗАМЕНА] Ошибка при создании экзамена: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при создании экзамена: {str(e)}"
            ) from e

    @staticmethod
    async def get_all_exams(db: AsyncSession, exam_type: str, current_user: dict):
        """
        Получение списка всех экзаменов указанного типа.

        Args:
            db: Асинхронная сессия SQLAlchemy
            exam_type: Тип экзамена (session или exam)
            current_user: Информация о текущем пользователе

        Returns:
            List[dict]: Список экзаменов с деталями

        Raises:
            HTTPException: 500 - Ошибка при получении данных
        """
        try:
            stmt = (
                select(Exam)
                .where(Exam.type == exam_type)
                .options(
                    selectinload(Exam.group),
                    selectinload(Exam.curator)
                )
            )

            # Если текущий пользователь - куратор, возвращаем только его экзамены
            if current_user.get("role") == Role.CURATOR:
                stmt = stmt.where(Exam.curator_id == current_user.get("id"))

            result = await db.execute(stmt)
            exams = result.scalars().all()

            logger.info(f"[ПОЛУЧЕНИЕ ЭКЗАМЕНОВ] Получено {len(exams)} экзаменов типа {exam_type}")

            return [
                {
                    "id": exam.id,
                    "type": exam.type,
                    "semester": exam.semester,
                    "course": exam.course,
                    "discipline": exam.discipline,
                    "holding_date": exam.holding_date,
                    "link": exam.link,
                    "group_name": exam.group.name if exam.group else None,
                    "group_id": exam.group_id,
                    "curator_full_name": f"{exam.curator.last_name} {exam.curator.first_name}" if exam.curator else None
                }
                for exam in exams
            ]

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ ЭКЗАМЕНОВ] Ошибка при получении списка экзаменов: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Произошла ошибка при получении списка экзаменов"
            ) from e

    @staticmethod
    async def update_exam_link(exam_id: int, new_link: Optional[str], db: AsyncSession):
        """
        Обновление ссылки на экзамен.

        Args:
            exam_id: Идентификатор экзамена
            new_link: Новая ссылка
            db: Асинхронная сессия SQLAlchemy

        Returns:
            dict: Обновленный экзамен или None

        Raises:
            HTTPException: 500 - Ошибка при обновлении данных
        """
        try:
            result = await db.execute(
                select(Exam)
                .where(Exam.id == exam_id)
                .options(
                    selectinload(Exam.group),
                    selectinload(Exam.curator)
                )
            )
            exam = result.scalar_one_or_none()

            if not exam:
                logger.warning(f"[ОБНОВЛЕНИЕ ССЫЛКИ] Экзамен не найден: ID {exam_id}")
                return None

            exam.link = new_link

            await db.commit()
            await db.refresh(exam)

            logger.info(f"[ОБНОВЛЕНИЕ ССЫЛКИ] Ссылка обновлена для экзамена ID {exam_id}")

            return {
                "id": exam.id,
                "type": exam.type,
                "semester": exam.semester,
                "course": exam.course,
                "discipline": exam.discipline,
                "holding_date": exam.holding_date,
                "link": exam.link,
                "group_name": exam.group.name if exam.group else None,
                "group_id": exam.group_id,
                "curator_full_name": f"{exam.curator.last_name} {exam.curator.first_name}" if exam.curator else None
            }

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ОБНОВЛЕНИЕ ССЫЛКИ] Ошибка при обновлении ссылки для экзамена ID {exam_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при обновлении ссылки: {str(e)}"
            ) from e

    @staticmethod
    async def get_exam_marks(exam_id: int, db: AsyncSession) -> ExamMarksResponse:
        """
        Получение оценок студентов по экзамену.

        Args:
            exam_id: Идентификатор экзамена
            db: Асинхронная сессия SQLAlchemy

        Returns:
            ExamMarksResponse: Оценки студентов

        Raises:
            HTTPException: 404 - Экзамен не найден
            HTTPException: 500 - Ошибка при получении данных
        """
        try:
            result = await db.execute(
                select(Exam)
                .where(Exam.id == exam_id)
                .options(
                    selectinload(Exam.marks).selectinload(Mark.student)
                )
            )
            exam = result.scalar_one_or_none()

            if not exam:
                logger.warning(f"[ПОЛУЧЕНИЕ ОЦЕНОК] Экзамен не найден: ID {exam_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Экзамен не найден"
                )

            students = [
                StudentMark(
                    student_id=mark.student.id,
                    student_full_name=f"{mark.student.last_name} {mark.student.first_name}",
                    mark=mark.mark
                )
                for mark in exam.marks
            ]

            logger.info(f"[ПОЛУЧЕНИЕ ОЦЕНОК] Получены оценки для экзамена ID {exam_id}")

            return ExamMarksResponse(
                exam_id=exam.id,
                discipline=exam.discipline,
                holding_date=exam.holding_date,
                students=students
            )

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ ОЦЕНОК] Ошибка при получении оценок для экзамена ID {exam_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Произошла ошибка при получении оценок"
            ) from e

    @staticmethod
    async def delete_exam(exam_id: int, db: AsyncSession) -> bool:
        """
        Удаление экзамена по ID.

        Args:
            exam_id: Идентификатор экзамена
            db: Асинхронная сессия SQLAlchemy

        Returns:
            bool: Результат операции (True при успешном удалении)

        Raises:
            HTTPException: 404 - Экзамен не найден
            HTTPException: 500 - Ошибка при удалении
        """
        try:
            result = await db.execute(select(Exam).where(Exam.id == exam_id))
            exam = result.scalars().first()

            if not exam:
                logger.warning(f"[УДАЛЕНИЕ ЭКЗАМЕНА] Экзамен не найден: ID {exam_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Экзамен не найден"
                )

            await db.delete(exam)
            await db.commit()

            logger.info(f"[УДАЛЕНИЕ ЭКЗАМЕНА] Экзамен удален: ID {exam_id}")
            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[УДАЛЕНИЕ ЭКЗАМЕНА] Ошибка при удалении экзамена ID {exam_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при удалении экзамена: {str(e)}"
            ) from e

    @staticmethod
    async def get_telegram_ids_by_exam_id(exam_id: int, db: AsyncSession) -> list[int]:
        """
        Получение Telegram ID студентов для экзамена.

        Args:
            exam_id: Идентификатор экзамена
            db: Асинхронная сессия SQLAlchemy

        Returns:
            list[int]: Список Telegram ID студентов

        Raises:
            HTTPException: 404 - Экзамен не найден
            HTTPException: 500 - Ошибка при получении данных
        """
        try:
            result = await db.execute(
                select(Exam)
                .where(Exam.id == exam_id)
            )
            exam = result.scalar_one_or_none()

            if not exam:
                logger.warning(f"[ПОЛУЧЕНИЕ ID TELEGRAM] Экзамен не найден: ID {exam_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Экзамен не найден"
                )

            result = await db.execute(
                select(Telegram.telegram_id)
                .join(Student, Student.telegram_id == Telegram.id)
                .where(
                    Student.group_id == exam.group_id,
                    Student.telegram_id.is_not(None)
                )
            )

            telegram_ids = result.scalars().all()

            logger.info(f"[ПОЛУЧЕНИЕ ID TELEGRAM] Получено {len(telegram_ids)} ID для экзамена ID {exam_id}")
            return telegram_ids

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ ID TELEGRAM] Ошибка при получении ID для экзамена ID {exam_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Произошла ошибка при получении ID Telegram"
            ) from e

    @staticmethod
    async def get_exam_details(exam_id: int, db: AsyncSession) -> Optional[Exam]:
        """
        Получение детальной информации об экзамене.

        Args:
            exam_id: Идентификатор экзамена
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Optional[Exam]: Детальная информация об экзамене или None

        Raises:
            HTTPException: 500 - Ошибка при получении данных
        """
        try:
            result = await db.execute(
                select(Exam)
                .where(Exam.id == exam_id)
                .options(
                    selectinload(Exam.curator)
                )
            )
            exam = result.scalar_one_or_none()

            if exam:
                logger.info(f"[ДЕТАЛИ ЭКЗАМЕНА] Получены детали экзамена ID {exam_id}")
            else:
                logger.warning(f"[ДЕТАЛИ ЭКЗАМЕНА] Экзамен не найден: ID {exam_id}")

            return exam

        except SQLAlchemyError as e:
            logger.error(f"[ДЕТАЛИ ЭКЗАМЕНА] Ошибка при получении деталей экзамена ID {exam_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Произошла ошибка при получении деталей экзамена"
            ) from e