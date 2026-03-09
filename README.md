# 🎙️ Deep Tech Podcast AI

Um pipeline de engenharia de dados e inteligência artificial que vasculha a internet em busca de inovações tecnológicas, sumariza artigos profundos e gera um podcast em áudio ultrarrealista, entregando o resultado final diretamente no seu Telegram.

## 🚀 Arquitetura e Funcionalidades

O sistema foi desenhado com foco em resiliência (tratamento de *Rate Limits*, *Exponential Backoff*) e arquitetura modular:

* **🔍 Motor de Busca Duplo (Scraper):** * **Modo Elite:** Vasculha diretórios RSS de alta curadoria (MIT, Ars Technica, ScienceDaily) via `feedparser`.
    * **Modo Aberto:** Busca dinâmica de inovações e descobertas via `ddgs` (DuckDuckGo Search).
    * Extração robusta de texto com `newspaper4k`.
* **🧠 Processamento LLM:** Roteirização feita por modelos de ponta (Llama 3.1) via API da **Groq**, atuando sob uma *persona* de Engenheiro Sênior.
* **🗣️ Síntese de Voz (TTS Local):** Geração de áudio *offline* com **Kokoro TTS** (v0.9.4). Aplica filtros regex anti-markdown e converte o roteiro em locução fluida.
* **📱 Entrega:** Upload automatizado do arquivo `.wav` via **Telegram Bot API**, com validação de limites de tamanho de rede.
* **⚙️ Painel de Controle UI:** Interface web construída em **Streamlit** para gerenciar os tópicos de busca, o prompt da IA, vozes e velocidade.

## 🛠️ Pré-requisitos

1. **Python 3.10 ou superior.**
2. **espeak-ng:** O Kokoro TTS depende do motor *espeak-ng* para mapeamento fonético (G2P).
   * **Windows:** Baixe e instale a versão MSI oficial no [GitHub do espeak-ng](https://github.com/espeak-ng/espeak-ng/releases).
   * **Linux:** `sudo apt-get install espeak-ng`
   * **macOS:** `brew install espeak`
   
