from typing import List
import os

from fastapi import APIRouter, Depends, HTTPException, Path, Body, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.api.v1.schemas.exam import CreateExam, ExamResponse, UpdateExamLink, ExamMarksResponse, ExamType
from app.core.database import get_db
from app.core.logger import logger
from app.services.exam import ExamService
from app.utils.roles import require_roles, Role
from app.utils.create_docx import create_exam_document
from app.utils.bot import notify_students_about_exam_link, notify_students_about_exam_creation

router = APIRouter(prefix="/exam", tags=["Exam"])


@router.get("/", response_model=List[ExamResponse])
async def get_exams(
        exam_type: ExamType,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Получение списка всех экзаменов указанного типа.

    Args:
        exam_type: Тип экзамена (session или exam)
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        List[ExamResponse]: Список экзаменов

    Raises:
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        exams = await ExamService.get_all_exams(db, exam_type.value, current_user)
        logger.info(f"[ПОЛУЧЕНИЕ ЭКЗАМЕНОВ] Получено {len(exams)} экзаменов типа {exam_type.value}")
        return exams
    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ ЭКЗАМЕНОВ] Ошибка при получении экзаменов: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при получении списка экзаменов"
        ) from e


@router.post("/create", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
        exam: CreateExam,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Создание нового экзамена.

    Args:
        exam: Данные для создания экзамена
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        ExamResponse: Созданный экзамен

    Raises:
        HTTPException: 400 - Ошибка валидации данных
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        new_exam = await ExamService.create_exam(exam, db)
        logger.info(f"[СОЗДАНИЕ ЭКЗАМЕНА] Создан экзамен ID {new_exam.id}, дисциплина: {new_exam.discipline}")

        background_tasks.add_task(notify_students_about_exam_creation, new_exam.id)

        return ExamResponse(
            id=new_exam.id,
            type=new_exam.type,
            semester=new_exam.semester,
            course=new_exam.course,
            discipline=new_exam.discipline,
            holding_date=new_exam.holding_date,
            group_id=new_exam.group_id,
            curator_id=new_exam.curator_id,
            link=new_exam.link,
        )
    except ValueError as e:
        logger.warning(f"[СОЗДАНИЕ ЭКЗАМЕНА] Ошибка валидации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"[СОЗДАНИЕ ЭКЗАМЕНА] Ошибка при создании экзамена: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при создании экзамена"
        ) from e


@router.patch("/{exam_id}/link")
async def update_exam_link(
        exam_id: int = Path(...),
        link_data: UpdateExamLink = Body(...),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Обновление ссылки на экзамен.

    Args:
        exam_id: Идентификатор экзамена
        link_data: Новая ссылка
        background_tasks: Фоновые задачи FastAPI
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        dict: Обновленный экзамен

    Raises:
        HTTPException: 404 - Экзамен не найден
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        updated_exam = await ExamService.update_exam_link(exam_id, link_data.link, db)

        if not updated_exam:
            logger.warning(f"[ОБНОВЛЕНИЕ ССЫЛКИ] Экзамен не найден: ID {exam_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Экзамен не найден"
            )

        background_tasks.add_task(notify_students_about_exam_link, exam_id, updated_exam["link"])

        logger.info(f"[ОБНОВЛЕНИЕ ССЫЛКИ] Ссылка обновлена для экзамена ID {exam_id}")
        return updated_exam

    except Exception as e:
        logger.error(f"[ОБНОВЛЕНИЕ ССЫЛКИ] Ошибка при обновлении ссылки для экзамена ID {exam_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при обновлении ссылки на экзамен"
        ) from e


@router.get(
    "/{exam_id}/marks",
    response_model=ExamMarksResponse,
    status_code=status.HTTP_200_OK
)
async def get_exam_marks(
        exam_id: int = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Получение оценок для экзамена.

    Args:
        exam_id: Идентификатор экзамена
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        ExamMarksResponse: Оценки студентов по экзамену

    Raises:
        HTTPException: 404 - Экзамен не найден
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        exam_marks = await ExamService.get_exam_marks(exam_id, db)

        if not exam_marks:
            logger.warning(f"[ПОЛУЧЕНИЕ ОЦЕНОК] Экзамен не найден: ID {exam_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Экзамен не найден"
            )

        logger.info(f"[ПОЛУЧЕНИЕ ОЦЕНОК] Получены оценки для экзамена ID {exam_id}")
        return exam_marks

    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ ОЦЕНОК] Ошибка при получении оценок для экзамена ID {exam_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при получении оценок"
        ) from e


@router.get("/{exam_id}/document")
async def create_exam_document_r(
        exam_id: int,
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Генерация документа с информацией об экзамене.

    Args:
        exam_id: Идентификатор экзамена
        background_tasks: Фоновые задачи FastAPI
        current_user: Информация о текущем пользователе

    Returns:
        FileResponse: Сгенерированный Word-документ

    Raises:
        HTTPException: 404 - Экзамен не найден
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        result = await create_exam_document(exam_id)

        background_tasks.add_task(os.remove, result["output_filename"])

        logger.info(f"[СОЗДАНИЕ ДОКУМЕНТА] Документ создан для экзамена ID {exam_id}")

        return FileResponse(
            path=result["output_filename"],
            filename=result["filename"],
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    except FileNotFoundError:
        logger.error(f"[СОЗДАНИЕ ДОКУМЕНТА] Файл не найден для экзамена ID {exam_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл документа не найден"
        )
    except Exception as e:
        logger.error(f"[СОЗДАНИЕ ДОКУМЕНТА] Ошибка при создании документа для экзамена ID {exam_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при создании документа"
        ) from e


@router.delete("/delete/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
        exam_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Удаление экзамена по ID.

    Args:
        exam_id: Идентификатор экзамена
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        Response: 204 No Content при успешном удалении

    Raises:
        HTTPException: 404 - Экзамен не найден
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        deleted = await ExamService.delete_exam(exam_id, db)

        if not deleted:
            logger.warning(f"[УДАЛЕНИЕ ЭКЗАМЕНА] Экзамен не найден: ID {exam_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Экзамен не найден"
            )

        logger.info(f"[УДАЛЕНИЕ ЭКЗАМЕНА] Экзамен удален: ID {exam_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.error(f"[УДАЛЕНИЕ ЭКЗАМЕНА] Ошибка при удалении экзамена ID {exam_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при удалении экзамена"
        ) from e