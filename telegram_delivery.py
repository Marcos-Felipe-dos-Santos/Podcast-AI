# /podcast_generator/telegram_delivery.py

import os
import logging

from telegram import Bot
from telegram.error import TelegramError

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

# Limite de upload de arquivos via Bot API do Telegram: 50 MB.
# Usamos 45 MB como margem de segurança.
TELEGRAM_MAX_FILE_SIZE_BYTES = 45 * 1024 * 1024


async def send_audio_to_telegram(audio_path: str, caption: str) -> bool:
    """
    Envia o arquivo de áudio para o Telegram.
    Valida o tamanho do arquivo antes do upload para evitar erros silenciosos.
    """
    # CORREÇÃO #13: Validação de tamanho antes do envio.
    # 10 artigos × 4000 chars pode gerar áudio > 50 MB, excedendo o limite do Telegram.
    # Sem essa checagem, o bot tentaria o upload, falharia após ~120s de timeout
    # e o arquivo ficaria em disco sem diagnóstico claro.
    try:
        file_size = os.path.getsize(audio_path)
    except OSError as e:
        logger.error(f"Não foi possível verificar o tamanho do arquivo '{audio_path}': {e}")
        return False

    file_size_mb = file_size / (1024 * 1024)
    if file_size > TELEGRAM_MAX_FILE_SIZE_BYTES:
        logger.error(
            f"Arquivo '{audio_path}' ({file_size_mb:.1f} MB) excede o limite de "
            f"{TELEGRAM_MAX_FILE_SIZE_BYTES // (1024*1024)} MB da Bot API do Telegram. "
            "Considere reduzir max_articles ou a velocidade da fala para encurtar o áudio."
        )
        return False

    logger.info(f"Tamanho do arquivo validado: {file_size_mb:.1f} MB. Iniciando envio...")

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        logger.info(f"Enviando '{audio_path}' para chat ID {TELEGRAM_CHAT_ID}...")

        async with bot:
            with open(audio_path, "rb") as audio_file:
                await bot.send_audio(
                    chat_id=TELEGRAM_CHAT_ID,
                    audio=audio_file,
                    caption=caption,
                    write_timeout=120,
                    connect_timeout=20,
                )

        logger.info("Áudio enviado com sucesso para o Telegram!")
        return True

    except TelegramError as e:
        logger.error(f"Erro da API do Telegram ao enviar áudio: {e}")
        return False
    except Exception as e:
        logger.error(f"Falha inesperada ao enviar para o Telegram: {e}", exc_info=True)
        return False