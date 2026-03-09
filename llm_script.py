# /podcast_generator/llm_script.py

import time
import logging
from typing import Optional

from groq import Groq, RateLimitError, BadRequestError
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from config import GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

# Limite de segurança de chars antes de enviar à Groq.
# Se o scraper por algum motivo entregar mais que isso, truncamos aqui como última linha de defesa.
# llama-3.1-8b-instant: ~8k tokens. 1 token ≈ 4 chars. 8000 * 4 = 32.000 chars.
# Usamos 12.000 como margem segura considerando system prompt + resposta gerada.
MAX_CONTENT_CHARS = 12_000


@retry(wait=wait_exponential(multiplier=1, min=4, max=30), stop=stop_after_attempt(4))
def _create_chat_completion_with_retry(
    client: Groq, messages: list, model: str, max_tokens: int
):
    logger.info(f"Tentando gerar roteiro com '{model}' (max_tokens={max_tokens})...")
    try:
        return client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=max_tokens,
        )
    except RateLimitError as e:
        # Respeita o retry-after da Groq (pode exigir 60s+)
        retry_after = 60
        if hasattr(e, "response") and e.response is not None:
            retry_after = int(e.response.headers.get("retry-after", 60))
        logger.warning(f"Rate limit atingido. Aguardando {retry_after}s...")
        time.sleep(retry_after)
        raise
    except BadRequestError as e:
        # HTTP 413 / payload too large — não adianta fazer retry, o conteúdo não vai encolher
        logger.error(
            f"Groq rejeitou o payload (413/BadRequest): {e}. "
            "O conteúdo enviado é grande demais. Verifique MAX_CONTENT_CHARS no scraper."
        )
        raise  # Deixa o tenacity re-tentar, mas o caller trata BadRequestError separado


def generate_podcast_script(
    news_content: str,
    system_prompt: str,
    max_tokens: int = 2048,
) -> Optional[str]:
    """
    Gera o roteiro do podcast via Groq.
    Trunca o conteúdo se necessário para evitar HTTP 413.
    """
    if not news_content:
        logger.warning("Conteúdo de notícias vazio. Roteiro não será gerado.")
        return None

    # Guarda de segurança: trunca se o scraper enviou mais do que o limite
    if len(news_content) > MAX_CONTENT_CHARS:
        logger.warning(
            f"Conteúdo muito grande ({len(news_content)} chars). "
            f"Truncando para {MAX_CONTENT_CHARS} chars antes de enviar à Groq."
        )
        news_content = news_content[:MAX_CONTENT_CHARS] + "\n\n[conteúdo truncado]"

    try:
        client = Groq(api_key=GROQ_API_KEY)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Aqui estão as notícias de hoje. "
                    "Transforme-as no roteiro do podcast:\n\n" + news_content
                ),
            },
        ]

        total_input_chars = len(system_prompt) + len(news_content)
        logger.info(f"Enviando {total_input_chars} chars totais para a Groq.")

        chat_completion = _create_chat_completion_with_retry(
            client, messages, LLM_MODEL, max_tokens
        )
        script = chat_completion.choices[0].message.content
        logger.info(f"Roteiro gerado com sucesso ({len(script)} chars).")
        return script

    except BadRequestError as e:
        logger.error(
            f"Payload rejeitado pela Groq mesmo após truncagem: {e}. "
            "Reduza max_articles no painel ou diminua MAX_CONTENT_CHARS em scraper.py."
        )
        return None
    except RetryError as e:
        logger.error(f"Falha ao comunicar com a Groq após múltiplas tentativas: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao gerar roteiro: {e}", exc_info=True)
        return None