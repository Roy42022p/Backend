from typing import Optional, Type, Union
from enum import Enum
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext

from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.logger import logger
from app.models import Admin, Curator, Student
from app.utils.security import hash_password

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Role(str, Enum):
    ADMIN = "admin"
    CURATOR = "curator"
    STUDENT = "student"


class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Проверка пароля с использованием bcrypt.

        Args:
            plain_password: Открытый текст пароля
            hashed_password: Хэшированный пароль для сравнения

        Returns:
            bool: Результат проверки (True если пароли совпадают)
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    async def authenticate_user(
            username: str,
            password: str,
            db: AsyncSession
    ) -> Optional[dict]:
        """
        Поиск и аутентификация пользователя (Admin, Curator или Student).

        Args:
            username: Логин пользователя
            password: Пароль пользователя
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Optional[dict]: Словарь с пользователем и его ролью или None
        """
        try:
            for user_model in [Admin, Curator, Student]:
                result = await db.execute(select(user_model).filter(user_model.login == username))
                user = result.scalars().first()

                if user and AuthService.verify_password(password, user.password):
                    if hasattr(user, "is_active") and not user.is_active:
                        logger.warning(f"[АУТЕНТИФИКАЦИЯ] Неактивный пользователь: {username}")
                        return None

                    role = Role.ADMIN if isinstance(user, Admin) else \
                        Role.CURATOR if isinstance(user, Curator) else Role.STUDENT

                    logger.info(f"[АУТЕНТИФИКАЦИЯ] Успешная аутентификация: {username}, роль: {role.value}")
                    return {"user": user, "role": role}

            logger.warning(f"[АУТЕНТИФИКАЦИЯ] Пользователь не найден: {username}")
            return None

        except Exception as e:
            logger.error(f"[АУТЕНТИФИКАЦИЯ] Ошибка аутентификации для {username}: {str(e)}")
            return None

    @staticmethod
    def verify_secret_key(secret_key: str, role: Role) -> bool:
        """
        Проверка секретного ключа для указанной роли.

        Args:
            secret_key: Секретный ключ для проверки
            role: Роль пользователя

        Returns:
            bool: Результат проверки (True если ключ валиден)
        """
        if role == Role.STUDENT:
            logger.info("[ПРОВЕРКА КЛЮЧА] Пропущена проверка для студента")
            return True

        valid_key = settings.ADMIN_KEY if role == Role.ADMIN else settings.CURATOR_KEY

        if secret_key == valid_key:
            logger.info(f"[ПРОВЕРКА КЛЮЧА] Ключ успешно проверен для роли {role.value}")
            return True

        logger.warning(f"[ПРОВЕРКА КЛЮЧА] Неверный ключ для роли {role.value}")
        return False

    @staticmethod
    def get_role_by_key(secret_key: str) -> Optional[Role]:
        """
        Получение роли по секретному ключу.

        Args:
            secret_key: Секретный ключ для проверки

        Returns:
            Optional[Role]: Роль пользователя или None
        """
        if secret_key == settings.ADMIN_KEY:
            logger.info("[ПОЛУЧЕНИЕ РОЛИ] Найдена роль: ADMIN")
            return Role.ADMIN
        elif secret_key == settings.CURATOR_KEY:
            logger.info("[ПОЛУЧЕНИЕ РОЛИ] Найдена роль: CURATOR")
            return Role.CURATOR

        logger.warning("[ПОЛУЧЕНИЕ РОЛИ] Неверный секретный ключ")
        return None

    @staticmethod
    def create_token(login: str, role: Role, id: int) -> str:
        """
        Создание JWT-токена для пользователя.

        Args:
            login: Логин пользователя
            role: Роль пользователя
            id: Идентификатор пользователя

        Returns:
            str: Сгенерированный JWT-токен
        """
        logger.info(f"[СОЗДАНИЕ ТОКЕНА] Для пользователя {login}, роль: {role.value}")
        return create_access_token(
            data={"sub": login, "role": role.value, "id": id},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )

    @staticmethod
    async def _base_registration(
            db: AsyncSession,
            model_class: Type[Union[Admin, Curator, Student]],
            login: str,
            **kwargs
    ) -> Union[Admin, Curator, Student]:
        """
        Базовая логика регистрации для всех ролей
        """
        result = await db.execute(select(model_class).filter(model_class.login == login))
        existing_user = result.scalars().first()

        if existing_user:
            logger.warning(f"[РЕГИСТРАЦИЯ] Пользователь с логином {login} уже существует")
            raise ValueError(f"Пользователь с логином {login} уже существует")

        user = model_class(login=login, **kwargs)
        db.add(user)
        await db.flush()
        await db.commit()
        logger.info(f"[РЕГИСТРАЦИЯ] Пользователь {login} успешно зарегистрирован")
        return user

    @staticmethod
    async def register_admin(
            login: str,
            password: str,
            db: AsyncSession
    ) -> Admin:
        """
        Регистрация администратора с проверкой на существующий логин.

        Args:
            login: Логин администратора
            password: Пароль администратора
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Admin: Зарегистрированный администратор

        Raises:
            ValueError: Если логин уже существует или произошла ошибка
        """
        hashed_pw = hash_password(password)

        return await AuthService._base_registration(
            db=db,
            model_class=Admin,
            login=login,
            password=hashed_pw,
            role=Role.ADMIN.value
        )

    @staticmethod
    async def register_curator(
            login: str,
            password: str,
            secret_key: str,
            first_name: str,
            last_name: str,
            patronymic: str,
            db: AsyncSession
    ) -> Curator:
        """
        Регистрация куратора с проверкой секретного ключа и существующего логина.

        Args:
            login: Логин куратора
            password: Пароль куратора
            secret_key: Секретный ключ для регистрации
            first_name: Имя куратора
            last_name: Фамилия куратора
            patronymic: Отчество куратора
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Curator: Зарегистрированный куратор

        Raises:
            ValueError: Если ключ недействителен или логин уже существует
        """
        if not AuthService.verify_secret_key(secret_key, Role.CURATOR):
            logger.warning(f"[РЕГИСТРАЦИЯ КУРАТОРА] Неверный секретный ключ для {login}")
            raise ValueError("Неверный секретный ключ")

        hashed_pw = hash_password(password)

        return await AuthService._base_registration(
            db=db,
            model_class=Curator,
            login=login,
            password=hashed_pw,
            role=Role.CURATOR.value,
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic
        )

    @staticmethod
    async def register_student(
            login: str,
            first_name: str,
            last_name: str,
            patronymic: str,
            group_id: int,
            db: AsyncSession
    ) -> Student:
        """
        Регистрация студента с проверкой на существующий логин.

        Args:
            login: Логин студента
            first_name: Имя студента
            last_name: Фамилия студента
            patronymic: Отчество студента
            group_id: Идентификатор группы
            db: Асинхронная сессия SQLAlchemy

        Returns:
            Student: Зарегистрированный студент

        Raises:
            ValueError: Если логин уже существует или произошла ошибка
        """
        return await AuthService._base_registration(
            db=db,
            model_class=Student,
            login=login,
            role=Role.STUDENT.value,
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic,
            group_id=group_id,
            verif=False
        )