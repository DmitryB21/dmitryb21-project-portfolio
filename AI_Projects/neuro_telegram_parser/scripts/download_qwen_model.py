#!/usr/bin/env python3
"""
Скрипт для скачивания модели Qwen2.5-7B-Instruct-Q5_K_M.gguf

Использование:
    python scripts/download_qwen_model.py [--output-dir DIR]
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def download_from_huggingface(repo_id: str, filename: str, output_path: str):
    """
    Скачать файл модели с HuggingFace
    
    Args:
        repo_id: ID репозитория на HuggingFace (например, "Qwen/Qwen2.5-7B-Instruct-GGUF")
        filename: Имя файла для скачивания
        output_path: Путь для сохранения файла
    """
    try:
        from huggingface_hub import hf_hub_download
        logger.info(f"📥 Скачивание {filename} из {repo_id}...")
        logger.info(f"   Сохранение в: {output_path}")
        
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=os.path.dirname(output_path),
            local_dir_use_symlinks=False
        )
        
        # Перемещаем файл в нужное место, если нужно
        if downloaded_path != output_path:
            import shutil
            shutil.move(downloaded_path, output_path)
        
        logger.info(f"✅ Модель успешно скачана: {output_path}")
        return output_path
        
    except ImportError:
        logger.error("❌ huggingface_hub не установлен")
        logger.info("💡 Установите: pip install huggingface_hub")
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при скачивании: {e}")
        raise


def download_with_requests(url: str, output_path: str):
    """
    Скачать файл по прямой ссылке
    
    Args:
        url: URL файла
        output_path: Путь для сохранения
    """
    try:
        import requests
        from tqdm import tqdm
        
        logger.info(f"📥 Скачивание модели из {url}...")
        logger.info(f"   Сохранение в: {output_path}")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            if total_size > 0:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc="Скачивание") as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        logger.info(f"✅ Модель успешно скачана: {output_path}")
        return output_path
        
    except ImportError:
        logger.error("❌ requests или tqdm не установлены")
        logger.info("💡 Установите: pip install requests tqdm")
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при скачивании: {e}")
        raise


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Скачать модель Qwen2.5-7B-Instruct-Q5_K_M.gguf')
    parser.add_argument(
        '--output-dir',
        type=str,
        default='models',
        help='Директория для сохранения модели (по умолчанию: models)'
    )
    parser.add_argument(
        '--method',
        type=str,
        choices=['huggingface', 'direct'],
        default='huggingface',
        help='Метод скачивания: huggingface или direct (по умолчанию: huggingface)'
    )
    
    args = parser.parse_args()
    
    # Создаем директорию для моделей
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    model_filename = "Qwen2.5-7B-Instruct-Q5_K_M.gguf"
    output_path = output_dir / model_filename
    
    # Проверяем, не скачана ли уже модель
    if output_path.exists():
        logger.warning(f"⚠️ Модель уже существует: {output_path}")
        response = input("Перезаписать? (y/N): ")
        if response.lower() != 'y':
            logger.info("Отменено пользователем")
            return
        output_path.unlink()
    
    logger.info("=" * 60)
    logger.info("СКАЧИВАНИЕ МОДЕЛИ QWEN2.5-7B-INSTRUCT-Q5_K_M")
    logger.info("=" * 60)
    logger.info(f"Метод: {args.method}")
    logger.info(f"Выходная директория: {output_dir.absolute()}")
    logger.info(f"Размер модели: ~4.5 GB")
    logger.info("")
    
    try:
        if args.method == 'huggingface':
            # Попробуем несколько возможных репозиториев
            repos_to_try = [
                "Qwen/Qwen2.5-7B-Instruct-GGUF",
                "bartowski/Qwen2.5-7B-Instruct-GGUF",
                "TheBloke/Qwen2.5-7B-Instruct-GGUF",
            ]
            
            filename = "Qwen2.5-7B-Instruct-Q5_K_M.gguf"
            
            success = False
            for repo_id in repos_to_try:
                try:
                    logger.info(f"Попытка скачать из {repo_id}...")
                    download_from_huggingface(repo_id, filename, str(output_path))
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"Не удалось скачать из {repo_id}: {e}")
                    continue
            
            if not success:
                logger.error("❌ Не удалось скачать модель ни из одного репозитория")
                logger.info("💡 Попробуйте использовать --method direct с прямой ссылкой")
                return 1
        
        elif args.method == 'direct':
            # Прямые ссылки на модель (могут устареть)
            logger.warning("⚠️ Метод 'direct' требует прямой URL")
            logger.info("💡 Найдите актуальную ссылку на модель и используйте:")
            logger.info("   python scripts/download_qwen_model.py --method direct --url <URL>")
            logger.info("")
            logger.info("Возможные источники:")
            logger.info("  - HuggingFace: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF")
            logger.info("  - Ollama: https://ollama.com/library/qwen2.5:7b")
            return 1
        
        # Проверяем размер файла
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Файл сохранен: {output_path}")
            logger.info(f"   Размер: {size_mb:.2f} MB")
            
            # Обновляем config.ini
            logger.info("")
            logger.info("💡 Обновите config.ini:")
            logger.info(f"   [topic_modeling]")
            logger.info(f"   qwen_model_path = {output_path.absolute()}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Прервано пользователем")
        if output_path.exists():
            output_path.unlink()
            logger.info("Частично скачанный файл удален")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())

