import json
import re
import subprocess
from pathlib import Path
from typing import Dict, Any

from fastapi import HTTPException

from app.core.logger import logger
from app.core.database import get_db
from app.services.mark import MarkService

script_dir = Path(__file__).parent.resolve()


def load_specialties() -> Dict[str, str]:
    """
    Загрузка специальностей из JSON-файла.

    Returns:
        Dict[str, str]: Словарь соответствий группа: специальность

    Raises:
        HTTPException: 500 - Ошибка загрузки файла специальностей
    """
    json_path = script_dir / 'spec.json'

    try:
        with json_path.open('r', encoding='utf-8') as f:
            logger.info(f"[ЗАГРУЗКА СПЕЦИАЛЬНОСТЕЙ] Успешно загружены из {json_path}")
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"[ЗАГРУЗКА СПЕЦИАЛЬНОСТЕЙ] Файл не найден: {json_path}")
        raise HTTPException(
            status_code=500,
            detail=f"Файл специальностей не найден: {json_path}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"[ЗАГРУЗКА СПЕЦИАЛЬНОСТЕЙ] Ошибка декодирования JSON: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка декодирования файла специальностей: {str(e)}"
        )


def sanitize_filename(filename: str) -> str:
    """
    Очистка имени файла от недопустимых символов.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


async def get_exam_data(exam_id: int) -> Dict[str, Any]:
    """
    Получение данных экзамена для генерации документа.

    Args:
        exam_id: Идентификатор экзамена

    Returns:
        Dict[str, Any]: Данные экзамена

    Raises:
        HTTPException: 404 - Экзамен не найден
        HTTPException: 500 - Ошибка получения данных
    """
    try:
        async for db in get_db():
            result = await MarkService.get_exam_full_info(exam_id, db)

            if not result:
                logger.warning(f"[ПОЛУЧЕНИЕ ДАННЫХ ЭКЗАМЕНА] Экзамен не найден: ID {exam_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Экзамен не найден"
                )

            logger.info(f"[ПОЛУЧЕНИЕ ДАННЫХ ЭКЗАМЕНА] Успешно получены данные для экзамена ID {exam_id}")
            return result

    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ ДАННЫХ ЭКЗАМЕНА] Ошибка для ID {exam_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения данных экзамена: {str(e)}"
        ) from e


async def create_exam_document(exam_id: int) -> str:
    """
    Создание Word-документа для экзамена.

    Args:
        exam_id: Идентификатор экзамена

    Returns:
        str: Путь к сгенерированному документу

    Raises:
        HTTPException: 404 - Экзамен не найден
        HTTPException: 500 - Ошибка создания документа
        HTTPException: 500 - Ошибка выполнения скрипта
    """
    try:
        exam_data = await get_exam_data(exam_id)

        students_str = (
            ",".join(f"{student['name']}:{student['grade']}" for student in exam_data["students"])
            if exam_data["students"]
            else ""
        )

        specialties = load_specialties()
        specialty = specialties.get(exam_data["group"], "Неизвестная специальность")

        date_parts = exam_data["exam_date"].split("-")
        date = ".".join(reversed(date_parts)) if date_parts else "Не указана"

        discipline = exam_data['discipline']
        exam_date = exam_data['exam_date']
        clean_discipline = sanitize_filename(discipline)

        output_filename = str(script_dir / f"{exam_data['name']}.docx")
        filename = f"{clean_discipline}-{exam_date}.docx"

        args = [
            str(script_dir / "docx-generator"),
            str(exam_data["group"]),
            str(exam_data["course"]),
            str(exam_data["semester"]),
            specialty,
            str(exam_data["discipline"]),
            date,
            str(exam_data["teacher"]),
            students_str,
            "exam" if exam_data["doc_type"] == "exam" else "gradesheet",
            output_filename,
        ]

        logger.info(f"[ГЕНЕРАЦИЯ ДОКУМЕНТА] Запуск генерации для экзамена ID {exam_id} || Filename: {filename}")
        logger.debug(f"[ГЕНЕРАЦИЯ ДОКУМЕНТА] Аргументы скрипта: {' '.join(args)}")

        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        logger.debug(f"[ГЕНЕРАЦИЯ ДОКУМЕНТА] Вывод скрипта: {result.stdout}")

        if not Path(output_filename).exists():
            logger.error(f"[ГЕНЕРАЦИЯ ДОКУМЕНТА] Файл не создан: {output_filename}")
            raise HTTPException(
                status_code=500,
                detail=f"Файл {output_filename} не был создан"
            )

        logger.info(f"[ГЕНЕРАЦИЯ ДОКУМЕНТА] Документ создан: {output_filename}")
        return {
            "output_filename": output_filename,
            "filename": filename
        }

    except subprocess.CalledProcessError as e:
        logger.error(f"[ГЕНЕРАЦИЯ ДОКУМЕНТА] Ошибка выполнения скрипта: {e.stderr}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании документа: {e.stderr}"
        ) from e
    except Exception as e:
        logger.error(f"[ГЕНЕРАЦИЯ ДОКУМЕНТА] Неизвестная ошибка для ID {exam_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Произошла ошибка при создании документа: {str(e)}"
        ) from e