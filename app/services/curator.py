from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.schemas.curator import UpdateCurator
from app.models import Curator, Group, Telegram
from app.core.logger import logger
from app.utils.roles import Role
from app.utils.security import hash_password


class CuratorService:
    @staticmethod
    async def get_curator_by_login(login: str, db: AsyncSession) -> Optional[Curator]:
        """
        Получение куратора по его логину.

        Args:
            login: Логин куратора
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Optional[Curator]: Найденный куратор или None

        Raises:
            HTTPException: 404 - Куратор не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            query = select(Curator).filter(Curator.login == login)
            result = await db.execute(query)
            curator = result.scalars().first()

            if not curator:
                logger.warning(f"[ПОЛУЧЕНИЕ КУРАТОРА] Куратор с логином {login} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Куратор с логином '{login}' не найден"
                )

            logger.info(f"[ПОЛУЧЕНИЕ КУРАТОРА] Найден куратор: {login}")
            return curator

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ КУРАТОРА] Ошибка базы данных для {login}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении данных куратора"
            ) from e

    @staticmethod
    async def get_all_curators(db: AsyncSession, current_user: dict) -> List[Curator]:
        """
        Получение списка всех кураторов.

        Args:
            db: Асинхронная сессия SQLAlchemy
            current_user: Информация о текущем пользователе

        Returns:
            List[Curator]: Список кураторов

        Raises:
            HTTPException: 500 - Ошибка при получении данных
        """
        try:
            stmt = select(Curator).options(selectinload(Curator.groups))

            if current_user.get("role") == Role.CURATOR:
                stmt = stmt.where(Curator.id == current_user.get("id"))

            result = await db.execute(stmt)
            curators = result.scalars().all()

            logger.info(f"[ПОЛУЧЕНИЕ КУРАТОРОВ] Получено {len(curators)} кураторов")
            return curators

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ КУРАТОРОВ] Ошибка при получении списка кураторов: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Произошла ошибка при получении списка кураторов"
            ) from e

    @staticmethod
    async def update_curator(curator_id: int, curator_data: UpdateCurator, db: AsyncSession) -> Curator:
        """
        Обновление информации о кураторе.

        Args:
            curator_id: Идентификатор куратора
            curator_data: Новые данные куратора
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Curator: Обновленный куратор

        Raises:
            HTTPException: 404 - Куратор не найден
            HTTPException: 500 - Ошибка при обновлении данных
        """
        try:
            result = await db.execute(select(Curator).where(Curator.id == curator_id))
            curator = result.scalars().first()

            if not curator:
                logger.warning(f"[ОБНОВЛЕНИЕ КУРАТОРА] Куратор не найден: ID {curator_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Куратор не найден"
                )

            update_data = curator_data.model_dump(exclude_unset=True)

            for field, value in update_data.items():
                if field == "firstName":
                    curator.first_name = value
                elif field == "lastName":
                    curator.last_name = value
                elif field == "patronymic":
                    curator.patronymic = value
                elif field == "login":
                    curator.login = value

            await db.commit()
            await db.refresh(curator)

            logger.info(f"[ОБНОВЛЕНИЕ КУРАТОРА] Куратор обновлен: ID {curator_id}")
            return curator

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ОБНОВЛЕНИЕ КУРАТОРА] Ошибка при обновлении куратора ID {curator_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Произошла ошибка при обновлении данных куратора"
            ) from e

    @staticmethod
    async def delete_curator(curator_id: int, db: AsyncSession) -> bool:
        """
        Удаление куратора по ID.

        Args:
            curator_id: Идентификатор куратора
            db: Асинхронная сессия SQLAlchemy

        Returns:
            bool: Результат операции (True при успешном удалении)

        Raises:
            HTTPException: 404 - Куратор не найден
            HTTPException: 500 - Ошибка при удалении
        """
        try:
            result = await db.execute(select(Curator).where(Curator.id == curator_id))
            curator = result.scalars().first()

            if not curator:
                logger.warning(f"[УДАЛЕНИЕ КУРАТОРА] Куратор не найден: ID {curator_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Куратор не найден"
                )

            await db.delete(curator)
            await db.commit()

            logger.info(f"[УДАЛЕНИЕ КУРАТОРА] Куратор удален: ID {curator_id}")
            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[УДАЛЕНИЕ КУРАТОРА] Ошибка при удалении куратора ID {curator_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Произошла ошибка при удалении куратора"
            ) from e

    @staticmethod
    async def get_curator_by_fio(
            first_name: str,
            last_name: str,
            patronymic: str,
            db: AsyncSession
    ) -> Optional[Curator]:
        """
        Получение куратора по ФИО (без учета регистра).

        Args:
            first_name: Имя куратора
            last_name: Фамилия куратора
            patronymic: Отчество куратора
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Optional[Curator]: Найденный куратор или None

        Raises:
            HTTPException: 404 - Куратор не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            result = await db.execute(
                select(Curator).where(
                    Curator.first_name.ilike(first_name),
                    Curator.last_name.ilike(last_name),
                    Curator.patronymic.ilike(patronymic)
                )
            )
            curator = result.scalars().first()

            if not curator:
                logger.warning(f"[ПОЛУЧЕНИЕ КУРАТОРА ПО ФИО] Куратор не найден: {last_name} {first_name} {patronymic}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Куратор не найден"
                )

            logger.info(f"[ПОЛУЧЕНИЕ КУРАТОРА ПО ФИО] Найден куратор: {last_name} {first_name} {patronymic}")
            return curator

        except SQLAlchemyError as e:
            logger.error(f"[ПОЛУЧЕНИЕ КУРАТОРА ПО ФИО] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при поиске куратора по ФИО"
            ) from e

    @staticmethod
    async def import_curators_from_table(curators_data: List, db: AsyncSession) -> Tuple[int, List[str]]:
        """
        Импорт кураторов из таблицы.

        Args:
            curators_data: Список данных для импорта (должен содержать full_name, groups, login, password)
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Tuple[int, list]: Количество импортированных кураторов и список ошибок

        Raises:
            HTTPException: 500 - Ошибка сохранения данных
        """
        imported_count = 0
        errors = []

        try:
            for entry in curators_data:
                try:
                    parts = entry.full_name.split()
                    if len(parts) != 3:
                        errors.append(f"Пропущена запись (неверный формат ФИО): {entry.full_name}")
                        continue
                    last_name, first_name, patronymic = parts

                    existing = await db.execute(
                        select(Curator).where(Curator.login == entry.login)
                    )
                    existing_curator = existing.scalar_one_or_none()
                    if existing_curator:
                        errors.append(f"Пропущена запись (логин уже существует): {entry.login}")
                        continue

                    curator = Curator(
                        last_name=last_name,
                        first_name=first_name,
                        patronymic=patronymic,
                        login=entry.login,
                        password=hash_password(entry.password),
                        role=Role.CURATOR
                    )

                    if entry.groups:
                        for group_name in entry.groups:
                            result = await db.execute(select(Group).where(Group.name == group_name))
                            group = result.scalar_one_or_none()
                            if group:
                                curator.groups.append(group)
                            else:
                                errors.append(f"Группа не найдена: '{group_name}' для куратора {entry.full_name}")

                    db.add(curator)
                    imported_count += 1

                except Exception as e:
                    errors.append(f"Ошибка в записи {entry.full_name}: {str(e)}")
                    logger.error(f"[ИМПОРТ КУРАТОРОВ] Ошибка при обработке {entry.full_name}: {str(e)}")
                    continue

            await db.commit()
            logger.info(f"[ИМПОРТ КУРАТОРОВ] Импортировано {imported_count} кураторов")
            return imported_count, errors

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ИМПОРТ КУРАТОРОВ] Ошибка базы данных: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при импорте кураторов"
            ) from e

    @staticmethod
    async def set_curator_password_and_telegram(
            curator_id: int,
            password: str,
            telegram_id: int,
            db: AsyncSession
    ) -> Curator:
        """
        Установка пароля и Telegram ID для куратора.

        Args:
            curator_id: Идентификатор куратора
            password: Пароль куратора
            telegram_id: Telegram ID куратора
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Curator: Обновленный куратор

        Raises:
            HTTPException: 404 - Куратор не найден
            HTTPException: 500 - Ошибка базы данных
        """
        try:
            curator = await db.get(Curator, curator_id)

            if not curator:
                logger.warning(f"[ОБНОВЛЕНИЕ КУРАТОРА] Куратор не найден: ID {curator_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Куратор не найден"
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
            curator.password = hashed_pw
            curator.telegram_id = telegram.id

            await db.commit()
            await db.refresh(curator)

            logger.info(f"[ОБНОВЛЕНИЕ КУРАТОРА] Куратор обновлен: ID {curator_id}")
            return curator

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"[ОБНОВЛЕНИЕ КУРАТОРА] Ошибка базы данных для ID {curator_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при обновлении куратора"
            ) from e