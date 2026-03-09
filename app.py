# /podcast_generator/app.py

import streamlit as st
import json
import os
import sys
import subprocess

CONFIG_FILE = "podcast_config.json"

# ATUALIZADO: Prompt reformulado para gerar fala natural e conversacional.
# As principais mudanças em relação ao prompt anterior:
# - Instrui o LLM a escrever COMO SE ESTIVESSE FALANDO, não como um artigo
# - Frases curtas (máximo 20 palavras) — frases longas soam robóticas no TTS
# - Uso de conectivos naturais ("olha", "então", "e sabe o que é interessante")
# - Perguntas retóricas para criar ritmo e envolvimento
# - Proíbe listas e enumerações, que soam artificiais em áudio
# - Velocidade padrão reduzida para 0.95 — mais próxima da fala humana natural
DEFAULT_CONFIG = {
    "search_topics": ["Inteligência Artificial", "Hardware e Processadores", "Descobertas Espaciais"],
    "max_articles": 4,
    "source_mode": "elite",
    "system_prompt": (
        "Você é um comunicador de tecnologia apaixonado, apresentando um podcast solo em Português do Brasil.\n\n"
        "SEU OBJETIVO: Transformar notícias técnicas em uma conversa envolvente e acessível, como se você estivesse "
        "contando uma novidade empolgante para um amigo inteligente. Técnico, mas humano.\n\n"
        "REGRAS DE OURO PARA O ÁUDIO:\n"
        "1. FRASES CURTAS: Escreva no máximo 20 palavras por frase. Ponto final é seu melhor amigo. "
        "Frases longas soam robóticas quando sintetizadas em áudio.\n"
        "2. FALE, NÃO ESCREVA: Use linguagem falada. 'Olha, o que aconteceu aqui é fascinante.' "
        "'Pensa comigo.' 'E aí vem a parte interessante.' 'O que isso significa na prática?'\n"
        "3. PERGUNTAS RETÓRICAS: Faça pelo menos 2 perguntas retóricas por notícia para criar ritmo. "
        "Ex: 'Por que isso importa?' 'Como isso muda o jogo?'\n"
        "4. CONECTIVOS NATURAIS: Use transições como 'E olha só', 'Mas tem mais', 'Agora pensa', "
        "'O ponto chave aqui é', 'Na prática isso significa', 'E não é só isso'.\n"
        "5. ZERO LISTAS: Nunca use listas ou enumerações. Transforme tudo em prosa falada. "
        "Em vez de '1. X, 2. Y', diga 'Primeiro X. E logo depois, Y.'\n"
        "6. PAUSAS NATURAIS: Use reticências (...) para pausas dramáticas. Use vírgulas generosamente "
        "para criar o ritmo da respiração humana.\n"
        "7. IDIOMA: Sempre em Português do Brasil, mesmo que as notícias sejam em inglês.\n"
        "8. PROIBIDO: Markdown, asteriscos, títulos, numeração, rubricas de roteiro."
    ),
    "voice": "pm_santa",
    "speed": 0.95,  # Reduzido de 1.05 — mais próximo da fala humana natural
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG


def save_config(config_data: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)


def get_venv_python() -> str:
    """Detecta o executável Python correto de forma cross-platform (Windows/Linux/macOS)."""
    scripts_dir = "Scripts" if sys.platform == "win32" else "bin"
    python_name = "python.exe" if sys.platform == "win32" else "python"
    venv_python = os.path.join(os.getcwd(), "venv", scripts_dir, python_name)
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable


# --- Layout do Painel ---
st.set_page_config(page_title="Deep Tech Podcast AI", page_icon="🎙️", layout="wide")
st.title("🎙️ Painel de Controle: Deep Tech Podcast")

config = load_config()
col1, col2 = st.columns(2)

with col1:
    st.header("🔍 Busca de Conteúdo")
    topics_str = st.text_area(
        "Tópicos (um por linha)",
        value="\n".join(config.get("search_topics", DEFAULT_CONFIG["search_topics"])),
        height=120,
    )

    source_options = {
        "🔬 Elite Tech & Ciência (Ars Technica, MIT, ScienceDaily, Wired...)": "elite",
        "🌐 Internet Aberta (Busca Geral via DuckDuckGo)": "aberta",
    }
    current_source = config.get("source_mode", "elite")
    current_source_name = [k for k, v in source_options.items() if v == current_source]
    current_source_index = (
        list(source_options.keys()).index(current_source_name[0]) if current_source_name else 0
    )
    selected_source_name = st.selectbox(
        "Qualidade das Fontes", list(source_options.keys()), index=current_source_index
    )
    selected_source_code = source_options[selected_source_name]
    max_articles = st.slider("Quantidade de Notícias Analisadas", 1, 10, config.get("max_articles", 4))

with col2:
    st.header("🗣️ Configuração de Voz")
    voice_options = {
        "Santa (Masculina BR — Grave/Analítica)": "pm_santa",
        "Dora (Feminina BR — Clara/Jornalística)": "pf_dora",
        "Julia (Feminina BR — Animada/Dinâmica)": "pf_julia",
    }
    current_voice = config.get("voice", "pm_santa")
    current_voice_name = [k for k, v in voice_options.items() if v == current_voice]
    current_voice_index = (
        list(voice_options.keys()).index(current_voice_name[0]) if current_voice_name else 0
    )
    selected_voice_name = st.selectbox(
        "Voz do Motor Kokoro", list(voice_options.keys()), index=current_voice_index
    )
    selected_voice_code = voice_options[selected_voice_name]

    speed = st.slider(
        "Velocidade da Fala",
        0.8, 1.5,
        float(config.get("speed", 0.95)),
        step=0.05,
        help="0.90–0.95 soa mais natural e humano. Acima de 1.10 começa a soar robótico.",
    )
    st.caption("💡 Dica: velocidades entre 0.90 e 0.97 tendem a soar mais naturais.")

st.header("🧠 Prompt de Engenharia")
system_prompt = st.text_area(
    "Diretrizes para o LLM (edite para personalizar o estilo):",
    value=config.get("system_prompt", DEFAULT_CONFIG["system_prompt"]),
    height=300,
)

st.markdown("---")

if st.button("💾 Salvar Configurações", use_container_width=True):
    new_config = {
        "search_topics": [t.strip() for t in topics_str.split("\n") if t.strip()],
        "max_articles": max_articles,
        "source_mode": selected_source_code,
        "system_prompt": system_prompt,
        "voice": selected_voice_code,
        "speed": speed,
    }
    save_config(new_config)
    st.success("Configurações salvas com sucesso!")

st.header("🚀 Execução do Pipeline")
if st.button("▶️ Gerar Podcast", type="primary", use_container_width=True):
    with st.spinner("Buscando inovações e gerando o podcast..."):
        python_executable = get_venv_python()
        st.caption(f"Runtime: `{python_executable}`")

        try:
            result = subprocess.run(
                [python_executable, "main.py"],
                capture_output=True,
                text=True,
                check=True,
                timeout=600,
            )
            st.success("✅ Podcast gerado e entregue no Telegram!")
            with st.expander("Ver Logs do Sistema"):
                st.code(result.stderr + "\n" + result.stdout)

        except subprocess.TimeoutExpired:
            st.error(
                "⏱️ Timeout: O pipeline excedeu 10 minutos. "
                "Verifique os logs em 'podcast_generator.log' e considere reduzir o número de artigos."
            )
        except subprocess.CalledProcessError as e:
            st.error("❌ O pipeline encerrou com erro.")
            with st.expander("Ver Detalhes do Erro"):
                st.code(e.stderr + "\n" + e.stdout)