# /podcast_generator/tts_generator.py

import os
import sys
import re
import logging
from datetime import datetime
from typing import Optional

import soundfile as sf
import numpy as np
from kokoro import KPipeline

from config import AUDIO_OUTPUT_DIR

logger = logging.getLogger(__name__)

try:
    pipeline = KPipeline(lang_code="p")
    SAMPLE_RATE: int = getattr(pipeline, "sample_rate", 24000)
    logger.info(f"Kokoro TTS inicializado com sucesso. Sample rate: {SAMPLE_RATE} Hz.")
except Exception as e:
    logger.critical(
        f"FALHA CRÍTICA: Não foi possível inicializar o Kokoro TTS. "
        f"Verifique se 'espeak-ng' está instalado no sistema. Erro: {e}"
    )
    sys.exit(1)


def _prepare_text_for_speech(text: str) -> str:
    """
    Transforma o roteiro escrito em texto otimizado para síntese de voz natural.

    O Kokoro TTS (e motores similares) lê o texto de forma mais natural quando:
    - As frases são curtas (idealmente até ~20 palavras)
    - Há vírgulas estratégicas que forçam micropauses de respiração
    - Abreviações técnicas são expandidas (o motor as lê letra por letra caso contrário)
    - Não há artefatos de markdown ou formatação

    Cada transformação abaixo resolve um problema específico de robotização.
    """

    # 1. Remove formatação Markdown e rubricas de roteiro
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"(?i)(Host:|Convidado:|Narrador:|Locutor:|IA:)", "", text)

    # 2. Expande abreviações técnicas comuns que o TTS lê de forma estranha
    abbreviations = {
        r"\bAI\b": "Inteligência Artificial",
        r"\bML\b": "Machine Learning",
        r"\bLLM\b": "modelo de linguagem",
        r"\bLLMs\b": "modelos de linguagem",
        r"\bAPI\b": "A-P-I",
        r"\bAPIs\b": "A-P-Is",
        r"\bGPU\b": "G-P-U",
        r"\bGPUs\b": "G-P-Us",
        r"\bCPU\b": "C-P-U",
        r"\bCPUs\b": "C-P-Us",
        r"\bUI\b": "interface",
        r"\bSSD\b": "S-S-D",
        r"\bRAM\b": "memória RAM",
        r"\bOS\b": "sistema operacional",
        r"\bCEO\b": "C-E-O",
        r"\bIPO\b": "I-P-O",
    }
    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text)

    # 3. Quebra frases muito longas (acima de ~180 chars sem pontuação)
    # Frases longas demais fazem o TTS perder o ritmo e soar monótono.
    # Insere uma vírgula antes de conectivos comuns para criar respiro natural.
    connectors = (
        r"(que permite|que possibilita|que garante|que indica|que mostra|"
        r"o que significa|o que representa|o que torna|e isso|e que|"
        r"mas que|mas isso|porém|entretanto|no entanto|além disso|"
        r"ao mesmo tempo|por outro lado|em outras palavras)"
    )
    text = re.sub(rf"\s+{connectors}", r", \1", text, flags=re.IGNORECASE)

    # 4. Garante espaço adequado após pontuação (problema comum em textos gerados por LLM)
    text = re.sub(r"([.!?])([A-ZÁÉÍÓÚÂÊÎÔÛÃÕ])", r"\1 \2", text)
    text = re.sub(r",([^\s])", r", \1", text)

    # 5. Substitui travessão tipográfico por vírgula + pausa (o TTS ignora travessões)
    text = re.sub(r"\s*—\s*", ", ", text)
    text = re.sub(r"\s*–\s*", ", ", text)

    # 6. Substitui dois pontos no meio de frases por vírgula (cria pausa sem mudança de tom)
    # Mantém dois pontos apenas no início de listas (linha terminando com ":")
    text = re.sub(r"(?<![:\n]):\s+(?=[a-záéíóúâêîôûãõ])", ", ", text)

    # 7. Remove linhas vazias excessivas, mantendo a separação entre parágrafos
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 8. Remove espaços extras
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def text_to_speech(text: str, voice: str = "pf_dora", speed: float = 1.0) -> Optional[str]:
    """
    Converte texto em áudio WAV usando o motor Kokoro TTS.
    Aplica pipeline de preparação para fala natural antes da síntese.
    """
    if not text:
        logger.warning("Texto vazio recebido. Nenhum áudio será gerado.")
        return None

    try:
        logger.info(f"Iniciando síntese — voz: '{voice}', velocidade: {speed}x")

        clean_text = _prepare_text_for_speech(text)
        logger.info(f"Texto preparado para síntese ({len(clean_text)} caracteres).")

        generator = pipeline(clean_text, voice=voice, speed=speed, split_pattern=r"\n+")

        audio_chunks = []
        for _gs, _ps, audio in generator:
            if audio is not None:
                audio_chunks.append(audio)

        if not audio_chunks:
            logger.error("O gerador Kokoro não produziu nenhum chunk de áudio.")
            return None

        wav_data = np.concatenate(audio_chunks)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(AUDIO_OUTPUT_DIR, f"podcast_{timestamp}.wav")

        sf.write(output_path, wav_data, SAMPLE_RATE)

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Arquivo salvo: '{output_path}' ({file_size_mb:.1f} MB)")
        return output_path

    except Exception as e:
        logger.error(f"Falha ao gerar áudio com Kokoro TTS: {e}", exc_info=True)
        return None