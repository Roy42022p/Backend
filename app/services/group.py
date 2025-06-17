from typing import List

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from app.models import Student, Group, Curator
from app.core.logger import logger
from app.api.v1.schemas.group import CreateGroup, GroupResponse
from app.utils.roles import Role



class GroupService:
    @staticmethod
    async def create_group(group_data: CreateGroup, db: AsyncSession) -> GroupResponse:
        """
        Создание новой учебной группы.

        Args:
            group_data: Данные для создания группы
            db: Асинхронная сессия SQLAlchemy

        Returns:
            GroupResponse: Созданная группа

        Raises:
            HTTPException: 400 - Куратор не найден
            HTTPException: 500 - Ошибка при создании группы
        """
        try:
            # Проверяем существование куратора
            curator_result = await db.execute(
                select(Curator).where(Curator.id == group_data.curator_id)
            )
            curator = curator_result.scalars().first()

            if not curator:
                logger.warning(f"[СОЗДАНИЕ ГРУППЫ] Куратор не найден: ID {group_data.curator_id}")
                raise HTTPException(
                    status_code=400,
                    detail="Куратор не найден"
                )

            new_group = Group(
                name=group_data.name,
                curator_id=group_data.curator_id
            )

            db.add(new_group)
            await db.commit()
            await db.refresh(new_group)

            logger.info(f"[СОЗДАНИЕ ГРУППЫ] Создана группа ID {new_group.id}, название: {new_group.name}")

            return GroupResponse(
                group_id=new_group.id,
                name=new_group.name,
                curator_id=new_group.curator_id
            )

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[СОЗДАНИЕ ГРУППЫ] Ошибка при создании группы: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при создании группы: {str(e)}"
            ) from e

    @staticmethod
    async def get_all_groups(db: AsyncSession, current_user: dict) -> List[dict]:
        """
        Получение списка всех учебных групп.

        Args:
            db: Асинхронная сессия SQLAlchemy
            current_user: Информация о текущем пользователе

        Returns:
            List[dict]: Список групп с их данными

        Raises:
            HTTPException: 500 - Ошибка при получении данных
        """
        try:
            # Формируем запрос с учетом роли пользователя
            stmt = (
                select(Group, func.count(Student.id).label("students_count"))
                .join(Student, Group.id == Student.group_id, isouter=True)
                .group_by(Group.id)
            )

            if current_user.get("role") == Role.CURATOR:
                stmt = stmt.where(Group.curator_id == current_user.get("id"))

            result = await db.execute(stmt)
            groups_with_counts = result.all()

            logger.info(f"[ПОЛУЧЕНИЕ ГРУПП] Получено {len(groups_with_counts)} учебных групп")

            return [
                {
                    "group_id": group.id,
                    "name": group.name,
                    "curator_id": group.curator_id,
                    "students_count": students_count
                }
                for group, students_count in groups_with_counts
            ]

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ ГРУПП] Ошибка при получении списка групп: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Произошла ошибка при получении списка групп"
            ) from e

    @staticmethod
    async def update_group(group_id: int, group_data: CreateGroup, db: AsyncSession) -> GroupResponse:
        """
        Обновление информации об учебной группе.

        Args:
            group_id: Идентификатор группы
            group_data: Новые данные группы
            db: Асинхронная сессия SQLAlchemy

        Returns:
            GroupResponse: Обновленная группа

        Raises:
            HTTPException: 400 - Куратор не найден
            HTTPException: 404 - Группа не найдена
            HTTPException: 500 - Ошибка при обновлении
        """
        try:
            result = await db.execute(select(Group).where(Group.id == group_id))
            group = result.scalars().first()

            if not group:
                logger.warning(f"[ОБНОВЛЕНИЕ ГРУППЫ] Группа не найдена: ID {group_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Группа не найдена"
                )

            curator_result = await db.execute(
                select(Curator).where(Curator.id == group_data.curator_id)
            )
            curator = curator_result.scalars().first()

            if not curator:
                logger.warning(f"[ОБНОВЛЕНИЕ ГРУППЫ] Куратор не найден: ID {group_data.curator_id}")
                raise HTTPException(
                    status_code=400,
                    detail="Куратор не найден"
                )

            group.name = group_data.name
            group.curator_id = group_data.curator_id

            await db.commit()
            await db.refresh(group)

            logger.info(f"[ОБНОВЛЕНИЕ ГРУППЫ] Группа обновлена: ID {group_id}")

            return GroupResponse(
                group_id=group.id,
                name=group.name,
                curator_id=group.curator_id
            )

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ОБНОВЛЕНИЕ ГРУППЫ] Ошибка при обновлении группы ID {group_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при обновлении группы: {str(e)}"
            ) from e

    @staticmethod
    async def delete_group(group_id: int, db: AsyncSession) -> bool:
        """
        Удаление учебной группы.

        Args:
            group_id: Идентификатор группы
            db: Асинхронная сессия SQLAlchemy

        Returns:
            bool: Результат операции (True при успешном удалении)

        Raises:
            HTTPException: 404 - Группа не найдена
            HTTPException: 500 - Ошибка при удалении
        """
        try:
            result = await db.execute(select(Group).where(Group.id == group_id))
            group = result.scalars().first()

            if not group:
                logger.warning(f"[УДАЛЕНИЕ ГРУППЫ] Группа не найдена: ID {group_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Группа не найдена"
                )

            await db.delete(group)
            await db.commit()

            logger.info(f"[УДАЛЕНИЕ ГРУППЫ] Группа удалена: ID {group_id}")
            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[УДАЛЕНИЕ ГРУППЫ] Ошибка при удалении группы ID {group_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при удалении группы: {str(e)}"
            ) from e

    @staticmethod
    async def import_groups_from_table(groups_data: list, db: AsyncSession) -> tuple[int, list]:
        """
           Импорт учебных групп с назначением кураторов.

           Args:
               groups_data: Список данных для импорта групп
               db: Асинхронная сессия SQLAlchemy.

           Returns:
               tuple[int, list]: Кортеж из количества успешно импортированных групп и списка ошибок.

           Raises:
               HTTPException: 500 — Ошибка при сохранении данных в базе.
           """
        imported_count = 0
        errors = []

        for entry in groups_data:
            try:
                if not entry.name or not entry.curator_full_name:
                    errors.append(f"Пропущена запись (недостаточно данных): {entry}")
                    continue

                parts = entry.curator_full_name.strip().split()
                if len(parts) != 3:
                    errors.append(f"Неверный формат ФИО куратора: {entry.curator_full_name}")
                    continue

                last_name, first_name, patronymic = parts

                curator_stmt = select(Curator).where(
                    Curator.last_name == last_name,
                    Curator.first_name == first_name,
                    Curator.patronymic == patronymic
                )
                curator = await db.scalar(curator_stmt)

                if not curator:
                    errors.append(f"Куратор не найден: {entry.curator_full_name}")
                    continue

                group_stmt = select(Group).where(Group.name == entry.name)
                existing_group = await db.scalar(group_stmt)

                if existing_group:
                    if existing_group.curator_id != curator.id:
                        existing_group.curator_id = curator.id
                else:
                    new_group = Group(
                        name=entry.name,
                        curator_id=curator.id
                    )
                    db.add(new_group)
                    imported_count += 1

            except Exception as e:
                errors.append(f"Ошибка при обработке группы '{entry.name}': {str(e)}")

        try:
            await db.commit()
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при импорте групп"
            ) from e

        return imported_count, errors