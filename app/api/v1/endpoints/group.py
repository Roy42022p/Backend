from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.group import CreateGroup, GroupResponse, GroupImportSchema
from app.core.database import get_db
from app.core.logger import logger
from app.services.group import GroupService
from app.utils.roles import require_roles, Role

router = APIRouter(prefix="/group", tags=["Group"])


@router.get("/", response_model=List[GroupResponse], status_code=status.HTTP_200_OK)
async def get_groups(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Получение списка всех учебных групп.

    Args:
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        List[GroupResponse]: Список групп с их данными

    Raises:
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        groups = await GroupService.get_all_groups(db=db, current_user=current_user)

        logger.info(f"[ПОЛУЧЕНИЕ ГРУПП] Получено {len(groups)} учебных групп")

        return [
            GroupResponse(
                group_id=group_data["group_id"],
                name=group_data["name"],
                curator_id=group_data["curator_id"],
                students_count=group_data["students_count"]
            ) for group_data in groups
        ]

    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ ГРУПП] Ошибка при получении списка групп: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при получении списка групп"
        ) from e


@router.post("/create", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
        group: CreateGroup,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Создание новой учебной группы.

    Args:
        group: Данные для создания группы
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        GroupResponse: Созданная группа

    Raises:
        HTTPException: 400 - Ошибка валидации данных
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        new_group = await GroupService.create_group(group, db)
        logger.info(f"[СОЗДАНИЕ ГРУППЫ] Создана группа ID {new_group.group_id}, название: {new_group.name}")
        return new_group

    except ValueError as e:
        logger.warning(f"[СОЗДАНИЕ ГРУППЫ] Ошибка валидации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"[СОЗДАНИЕ ГРУППЫ] Ошибка при создании группы: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при создании группы"
        ) from e


@router.patch("/update/{group_id}", response_model=GroupResponse, status_code=status.HTTP_200_OK)
async def update_group(
        group_id: int = Path(..., description="Идентификатор группы для обновления"),
        group_data: CreateGroup = Body(...),
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Обновление информации об учебной группе.

    Args:
        group_id: Идентификатор группы для обновления
        group_data: Новые данные группы
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        GroupResponse: Обновленная группа

    Raises:
        HTTPException: 404 - Группа не найдена
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        updated_group = await GroupService.update_group(group_id, group_data, db)

        if not updated_group:
            logger.warning(f"[ОБНОВЛЕНИЕ ГРУППЫ] Группа не найдена: ID {group_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Группа не найдена"
            )

        logger.info(f"[ОБНОВЛЕНИЕ ГРУППЫ] Группа обновлена: ID {group_id}")
        return updated_group

    except Exception as e:
        logger.error(f"[ОБНОВЛЕНИЕ ГРУППЫ] Ошибка при обновлении группы ID {group_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при обновлении группы"
        ) from e


@router.delete("/delete/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
        group_id: int = Path(..., description="Идентификатор группы для удаления"),
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Удаление учебной группы по ID.

    Args:
        group_id: Идентификатор группы для удаления
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        Response: 204 No Content при успешном удалении

    Raises:
        HTTPException: 404 - Группа не найдена
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        deleted = await GroupService.delete_group(group_id, db)

        if not deleted:
            logger.warning(f"[УДАЛЕНИЕ ГРУППЫ] Группа не найдена: ID {group_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Группа не найдена"
            )

        logger.info(f"[УДАЛЕНИЕ ГРУППЫ] Группа удалена: ID {group_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.error(f"[УДАЛЕНИЕ ГРУППЫ] Ошибка при удалении группы ID {group_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при удалении группы"
        ) from e


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_groups(
    groups_data: List[GroupImportSchema],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Массовый импорт групп с привязкой к кураторам по ФИО.

    Args:
        groups_data: Список данных для импорта групп
        db: Асинхронная сессия базы данных
        current_user: Информация о текущем пользователе с ролями

    Returns:
        dict: Результат импорта с количеством импортированных групп и ошибками

    Raises:
        HTTPException: 400 - Ошибка валидации данных
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        imported_count, errors = await GroupService.import_groups_from_table(groups_data, db)
        logger.info(f"[ИМПОРТ ГРУПП] Импортировано {imported_count} групп из {len(groups_data)} записей")

        return {
            "message": f"Импортировано групп: {imported_count}",
            "errors": errors,
            "total_attempts": len(groups_data)
        }

    except ValueError as e:
        logger.warning(f"[ИМПОРТ ГРУПП] Ошибка валидации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"[ИМПОРТ ГРУПП] Ошибка при импорте групп: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при импорте групп"
        ) from e