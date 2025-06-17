from typing import List

from fastapi import APIRouter, Depends, Body, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.mark import MarkUpdateBatch, MarkImportSchema
from app.core.database import get_db
from app.core.logger import logger
from app.services.mark import MarkService
from app.utils.roles import require_roles, Role

router = APIRouter(prefix="/mark", tags=["Mark"])


@router.patch("/batch", status_code=status.HTTP_200_OK)
async def update_marks_batch(
        marks_data: MarkUpdateBatch = Body(...),
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR])),
):
    """
    Массовое обновление оценок студентов.

    Args:
        marks_data: Список оценок для обновления в формате MarkUpdateBatch
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        dict: Результат операции с количеством обновленных оценок

    Raises:
        HTTPException: 400 - Ошибка валидации данных
        HTTPException: 404 - Некоторые оценки не найдены
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        updated_count = await MarkService.batch_update_marks(marks_data.marks, db)

        logger.info(f"[ОБНОВЛЕНИЕ ОЦЕНОК] Успешно обновлено {updated_count} оценок")

        return {
            "detail": "Оценки успешно обновлены",
            "updated_count": updated_count,
            "total_attempts": len(marks_data.marks)
        }

    except ValueError as e:
        logger.warning(f"[ОБНОВЛЕНИЕ ОЦЕНОК] Ошибка валидации данных: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e

    except Exception as e:
        logger.error(f"[ОБНОВЛЕНИЕ ОЦЕНОК] Ошибка при массовом обновлении оценок: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при обновлении оценок"
        ) from e


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_marks(
    marks_data: List[MarkImportSchema],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    try:
        imported_count, errors = await MarkService.import_marks_from_table(marks_data, db)

        return {
            "message": f"Импортировано оценок: {imported_count}",
            "errors": errors,
            "total_attempts": len(marks_data)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Произошла ошибка при импорте оценок"
        ) from e