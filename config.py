# /podcast_generator/config.py

import os
import sys
from logging import getLogger
from dotenv import load_dotenv

load_dotenv()
logger = getLogger(__name__)

# --- Segredos carregados do .env ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_MODEL = "llama-3.1-8b-instant"
AUDIO_OUTPUT_DIR = "audio_files"

# CORREÇÃO #2: Cast explícito para int com validação de formato.
# TELEGRAM_CHAT_ID deve ser inteiro (IDs de grupos são negativos e falham como string).
_telegram_chat_id_raw = os.getenv("TELEGRAM_CHAT_ID", "")
try:
    TELEGRAM_CHAT_ID: int = int(_telegram_chat_id_raw)
except ValueError:
    logger.critical(
        f"TELEGRAM_CHAT_ID inválido: '{_telegram_chat_id_raw}'. "
        "Deve ser um número inteiro (ex: 123456789 ou -1001234567890 para grupos)."
    )
    sys.exit(1)

# CORREÇÃO #3: Substituído `raise ValueError` por `sys.exit(1)`.
# raise em escopo de módulo impede testes unitários e gera stack traces desnecessários
# em automações. sys.exit(1) emite um exit code não-zero claro para o agendador (cron/Task Scheduler).
if not all([GROQ_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    logger.critical(
        "Variáveis de ambiente essenciais ausentes. "
        "Configure GROQ_API_KEY, TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no arquivo .env"
    )
    sys.exit(1)

# CORREÇÃO #3b: exist_ok=True elimina a race condition da checagem os.path.exists + makedirs.
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
logger.info(f"Diretório de áudio pronto: '{AUDIO_OUTPUT_DIR}'")