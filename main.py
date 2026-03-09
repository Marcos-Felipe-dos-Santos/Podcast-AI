# /podcast_generator/main.py

import asyncio
import logging
import os
import json
from datetime import datetime
from typing import List

# Configuração centralizada do logging (DEVE vir antes das importações locais)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("podcast_generator.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from scraper import get_summarized_content
from llm_script import generate_podcast_script
from tts_generator import text_to_speech
from telegram_delivery import send_audio_to_telegram


# CORREÇÃO #14: Validação de schema com dataclass.
# Sem validação, um valor como speed="rápido" causaria ValueError não tratado
# que interromperia o workflow silenciosamente após consumir créditos de API.
# Pydantic seria ideal, mas dataclass evita adicionar uma dependência extra.
from dataclasses import dataclass, field


@dataclass
class PodcastConfig:
    search_topics: List[str] = field(default_factory=lambda: ["Tecnologia e Inovação"])
    max_articles: int = 5
    source_mode: str = "elite"
    system_prompt: str = "Você é um podcaster técnico."
    voice: str = "pm_santa"
    speed: float = 1.05

    @classmethod
    def from_dict(cls, data: dict) -> "PodcastConfig":
        """Carrega e valida o config com tipos estritos e mensagens de erro claras."""
        try:
            speed = float(data.get("speed", 1.05))
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Campo 'speed' inválido no podcast_config.json: '{data.get('speed')}'. "
                "Deve ser um número (ex: 1.05)."
            ) from e

        try:
            max_articles = int(data.get("max_articles", 5))
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Campo 'max_articles' inválido: '{data.get('max_articles')}'. "
                "Deve ser um inteiro."
            ) from e

        search_topics = data.get("search_topics", ["Tecnologia e Inovação"])
        if not isinstance(search_topics, list) or not search_topics:
            raise ValueError("Campo 'search_topics' deve ser uma lista não-vazia.")

        return cls(
            search_topics=search_topics,
            max_articles=max_articles,
            source_mode=str(data.get("source_mode", "elite")),
            system_prompt=str(data.get("system_prompt", "Você é um podcaster técnico.")),
            voice=str(data.get("voice", "pm_santa")),
            speed=speed,
        )


async def main_workflow():
    """Executa o fluxo completo de geração e entrega do podcast."""
    logger.info(">>> INICIANDO WORKFLOW DO PODCAST GENERATOR <<<")
    audio_file_path = None

    config_file = "podcast_config.json"
    if not os.path.exists(config_file):
        logger.error(
            f"'{config_file}' não encontrado. "
            "Execute 'streamlit run app.py', configure e salve as opções no painel."
        )
        return

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            raw_config = json.load(f)

        # CORREÇÃO #14: Validação de schema antes de qualquer chamada de rede
        cfg = PodcastConfig.from_dict(raw_config)
        logger.info(
            f"Config carregada — tópicos: {cfg.search_topics}, "
            f"artigos: {cfg.max_articles}, modo: {cfg.source_mode}, voz: {cfg.voice}"
        )

        # --- ETAPA 1: Extração ---
        logger.info("--- ETAPA 1: Buscando artigos ---")
        news_content = get_summarized_content(cfg.search_topics, cfg.max_articles, cfg.source_mode)
        if not news_content:
            logger.error("Nenhum artigo encontrado. Abortando.")
            return

        # --- ETAPA 2: Roteiro ---
        logger.info("--- ETAPA 2: Gerando roteiro com a Groq ---")
        podcast_script = generate_podcast_script(news_content, cfg.system_prompt)
        if not podcast_script:
            logger.error("Falha ao gerar roteiro. Abortando.")
            return

        # --- ETAPA 3: Áudio ---
        logger.info("--- ETAPA 3: Convertendo roteiro em áudio (Kokoro TTS) ---")
        audio_file_path = text_to_speech(podcast_script, voice=cfg.voice, speed=cfg.speed)
        if not audio_file_path:
            logger.error("Falha ao gerar áudio. Abortando.")
            return

        # --- ETAPA 4: Entrega ---
        logger.info("--- ETAPA 4: Enviando podcast via Telegram ---")
        today_date = datetime.now().strftime("%d/%m/%Y")
        top_assuntos = ", ".join(cfg.search_topics[:2]) if cfg.search_topics else "Inovações Tecnológicas"
        caption = f"🔬 Podcast Deep Tech — {top_assuntos} ({today_date})"

        send_success = await send_audio_to_telegram(audio_file_path, caption)

        if send_success:
            logger.info(">>> WORKFLOW FINALIZADO COM SUCESSO <<<")
        else:
            logger.error("Falha no envio. Arquivo de áudio mantido localmente para diagnóstico.")
            logger.info(">>> WORKFLOW FINALIZADO COM ERROS <<<")

    except ValueError as e:
        # Erros de validação de config são esperados e não precisam de stack trace
        logger.error(f"Erro de configuração: {e}")
    except Exception as e:
        logger.critical(f"Exceção crítica no workflow: {e}", exc_info=True)
    finally:
        # CORREÇÃO #15: Limpeza garantida no bloco finally, independente do caminho de execução.
        # Antes, arquivos .wav acumulavam em disco quando send_success era False,
        # podendo consumir GBs em execuções automáticas diárias.
        if audio_file_path and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                logger.info(f"Arquivo de áudio '{audio_file_path}' removido (finally).")
            except Exception as e:
                logger.error(f"Não foi possível remover '{audio_file_path}': {e}")


if __name__ == "__main__":
    asyncio.run(main_workflow())