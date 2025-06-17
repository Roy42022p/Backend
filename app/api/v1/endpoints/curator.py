from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.curator import CreateNewCurator, CuratorResponse, UpdateCurator, CuratorImportSchema
from app.core.config import settings
from app.core.database import get_db
from app.core.logger import logger
from app.services.auth import AuthService
from app.services.curator import CuratorService
from app.utils.roles import require_roles, Role

router = APIRouter(prefix="/curator", tags=["Curator"])


@router.get("/", response_model=List[CuratorResponse])
async def get_all_curators(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Получение списка всех кураторов.

    Args:
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе, проверенная через require_roles

    Returns:
        List[CuratorResponse]: Список объектов кураторов с их данными

    Raises:
        HTTPException: 400 - Ошибка при получении данных
    """
    try:
        curators = await CuratorService.get_all_curators(db=db, current_user=current_user)

        logger.info(f"[ПОЛУЧЕНИЕ КУРАТОРОВ] Получено {len(curators)} кураторов")

        return [
            CuratorResponse(
                curator_id=curator.id,
                firstName=curator.first_name,
                lastName=curator.last_name,
                patronymic=curator.patronymic,
                login=curator.login,
                groups=[g.name for g in curator.groups]
            ) for curator in curators
        ]

    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ КУРАТОРОВ] Ошибка при получении списка кураторов: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при получении списка кураторов"
        )


@router.post("/create", response_model=CuratorResponse, status_code=status.HTTP_201_CREATED)
async def create_curator(
        curator: CreateNewCurator,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN]))
):
    """
    Создание нового куратора.

    Args:
        curator: Данные для создания куратора (CreateNewCurator)
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем администраторе

    Returns:
        CuratorResponse: Объект созданного куратора

    Raises:
        HTTPException: 400 - Ошибка валидации данных или создания куратора
    """
    try:
        new_curator = await AuthService.register_curator(
            login=curator.login,
            password=curator.password,
            secret_key=settings.CURATOR_KEY,
            first_name=curator.firstName,
            last_name=curator.lastName,
            patronymic=curator.patronymic,
            db=db,
        )

        logger.info(f"[СОЗДАНИЕ КУРАТОРА] Куратор создан: ID {new_curator.id}, логин {new_curator.login}")

        return CuratorResponse(
            curator_id=new_curator.id,
            firstName=new_curator.first_name,
            lastName=new_curator.last_name,
            patronymic=new_curator.patronymic,
            login=new_curator.login
        )

    except ValueError as e:
        logger.warning(f"[СОЗДАНИЕ КУРАТОРА] Ошибка при создании куратора: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/update/{curator_id}", response_model=CuratorResponse)
async def update_curator(
        curator_id: int,
        curator_data: UpdateCurator,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN]))
):
    """
    Обновление информации о кураторе по ID.

    Args:
        curator_id: Идентификатор куратора для обновления
        curator_data: Новые данные для обновления (UpdateCurator)
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем администраторе

    Returns:
        CuratorResponse: Объект обновленного куратора

    Raises:
        HTTPException: 400 - Ошибка при обновлении данных
        HTTPException: 404 - Куратор не найден
    """
    try:
        updated_curator = await CuratorService.update_curator(curator_id, curator_data, db)

        if not updated_curator:
            logger.warning(f"[ОБНОВЛЕНИЕ КУРАТОРА] Куратор не найден: ID {curator_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Куратор не найден"
            )

        logger.info(f"[ОБНОВЛЕНИЕ КУРАТОРА] Куратор обновлён: ID {curator_id}")

        return CuratorResponse(
            curator_id=updated_curator.id,
            firstName=updated_curator.first_name,
            lastName=updated_curator.last_name,
            patronymic=updated_curator.patronymic,
            login=updated_curator.login
        )

    except ValueError as e:
        logger.warning(f"[ОБНОВЛЕНИЕ КУРАТОРА] Ошибка при обновлении куратора ID {curator_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/delete/{curator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_curator(
        curator_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN]))
):
    """
    Удаление куратора по ID.

    Args:
        curator_id: Идентификатор куратора для удаления
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем администраторе

    Returns:
        Response: 204 No Content при успешном удалении

    Raises:
        HTTPException: 400 - Ошибка при удалении
        HTTPException: 404 - Куратор не найден
    """
    try:
        deleted = await CuratorService.delete_curator(curator_id, db)

        if not deleted:
            logger.warning(f"[УДАЛЕНИЕ КУРАТОРА] Куратор не найден: ID {curator_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Куратор не найден"
            )

        logger.info(f"[УДАЛЕНИЕ КУРАТОРА] Куратор удалён: ID {curator_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.error(f"[УДАЛЕНИЕ КУРАТОРА] Ошибка при удалении куратора ID {curator_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка при удалении куратора"
        )

@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_curators(
    curators_data: List[CuratorImportSchema],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Массовый импорт кураторов из таблицы.

    Args:
        curators_data: Список данных для импорта кураторов
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        dict: Результат импорта с количеством импортированных кураторов и ошибками
    """
    try:
        imported_count, errors = await CuratorService.import_curators_from_table(curators_data, db)

        logger.info(f"[ИМПОРТ КУРАТОРОВ] Импортировано {imported_count} кураторов из {len(curators_data)} записей")

        return {
            "message": f"Импортировано кураторов: {imported_count}",
            "errors": errors,
            "total_attempts": len(curators_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ИМПОРТ КУРАТОРОВ] Ошибка при импорте кураторов: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при импорте кураторов"
        ) from e