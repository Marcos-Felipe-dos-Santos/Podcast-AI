# /podcast_generator/scraper.py

import newspaper
import feedparser
import unicodedata
from typing import List, Dict, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# --- Feeds RSS Curados (Modo Elite) ---
ELITE_RSS_FEEDS = [
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.technologyreview.com/feed/",
    "https://www.sciencedaily.com/rss/top/technology.xml",
    "https://techcrunch.com/feed/",
    "https://www.wired.com/feed/rss",
    "https://inovacaotecnologica.com.br/feed.xml",
]

# Limite total de caracteres enviados à Groq.
# llama-3.1-8b-instant tem ~8k tokens de contexto útil.
# ~12.000 chars ≈ ~3.000 tokens — deixa margem para o system prompt e o roteiro gerado.
MAX_TOTAL_CHARS_FOR_LLM = 12_000

# Limite por artigo individual
CHAR_LIMIT_PER_ARTICLE = 1_800


def _normalize(text: str) -> str:
    """Remove acentos e coloca em minúsculas para comparação robusta entre PT e EN."""
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _make_newspaper_config() -> newspaper.Config:
    """Instancia config por chamada — evita estado global mutável."""
    cfg = newspaper.Config()
    cfg.browser_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    cfg.request_timeout = 15
    return cfg


def _fetch_from_rss(keywords: List[str], max_results_per_keyword: int) -> List[Dict[str, str]]:
    """
    Busca artigos diretamente dos RSS feeds de elite.
    Normaliza keywords para comparar com feeds em inglês.
    Se nenhum artigo bater, retorna o pool geral e deixa o LLM filtrar relevância.
    """
    normalized_keywords = [_normalize(kw) for kw in keywords]
    candidates = []
    all_entries = []

    for feed_url in ELITE_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                combined_normalized = _normalize(title + " " + summary)

                all_entries.append({"title": title, "link": link, "combined": combined_normalized})

                for kw in normalized_keywords:
                    kw_parts = kw.split()
                    # CORREÇÃO: mínimo 2 chars (antes era > 3, o que descartava "IA", "5G", etc.)
                    meaningful_parts = [p for p in kw_parts if len(p) >= 2]
                    # Testa a keyword completa normalizada também (ex: "ia" dentro de "artificial intelligence" não bate,
                    # mas "ai" bate — cobrindo siglas em inglês que correspondem às PT)
                    kw_normalized = _normalize(kw)
                    if kw_normalized in combined_normalized or any(
                        part in combined_normalized for part in meaningful_parts
                    ):
                        candidates.append({"title": title, "link": link})
                        break

        except Exception as e:
            logger.warning(f"Falha ao ler RSS '{feed_url}': {e}")

    limit = max_results_per_keyword * len(keywords)

    if candidates:
        logger.info(f"[RSS Elite] {len(candidates)} artigos relevantes encontrados (limite: {limit}).")
        return candidates[:limit]

    # Fallback: nenhuma keyword bateu. Retorna pool geral — o LLM faz curadoria.
    logger.warning(
        f"[RSS Elite] Nenhum artigo bateu com as keywords {keywords}. "
        "Retornando pool geral dos feeds — o LLM fará a curadoria de relevância."
    )
    all_clean = [{"title": e["title"], "link": e["link"]} for e in all_entries]
    return all_clean[:limit]


@retry(wait=wait_exponential(multiplier=1, min=2, max=15), stop=stop_after_attempt(3))
def _search_single_keyword(keyword: str, max_results: int) -> List[Dict[str, str]]:
    """Busca um único keyword via DuckDuckGo. Retry isolado por keyword."""
    from ddgs import DDGS
    results = []
    query = f"{keyword} inovação lançamento tecnologia"
    with DDGS() as ddgs:
        raw = ddgs.text(
            query,
            region="wt-wt",
            safesearch="moderate",
            timelimit="w",
            max_results=max_results,
        )
        if raw:
            for r in raw:
                results.append({"title": r["title"], "link": r["href"]})
    return results


def _fetch_from_ddgs(keywords: List[str], max_results_per_keyword: int) -> List[Dict[str, str]]:
    """Busca artigos via DuckDuckGo (modo aberto)."""
    articles = []
    for keyword in keywords:
        logger.info(f"[DDGS] Buscando: '{keyword}'")
        try:
            results = _search_single_keyword(keyword, max_results_per_keyword)
            articles.extend(results)
        except Exception as e:
            logger.error(f"[DDGS] Falha definitiva para '{keyword}' após retries: {e}")
    return articles


def fetch_news_from_keywords(
    keywords: List[str],
    max_results_per_keyword: int = 10,
    source_mode: str = "elite",
) -> List[Dict[str, str]]:
    """Roteador de fonte: elite (RSS) ou aberta (DDGS)."""
    if source_mode == "elite":
        logger.info("Modo Elite: lendo RSS feeds curados.")
        return _fetch_from_rss(keywords, max_results_per_keyword)
    else:
        logger.info("Modo Aberto: buscando via DuckDuckGo.")
        return _fetch_from_ddgs(keywords, max_results_per_keyword)


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(2))
def _download_and_parse_article_with_retry(article: newspaper.Article) -> None:
    article.download()
    article.parse()


def extract_full_text(article_url: str) -> Optional[str]:
    """Extrai o texto completo de um artigo com resiliência a falhas."""
    try:
        cfg = _make_newspaper_config()
        article = newspaper.Article(url=article_url, config=cfg)
        _download_and_parse_article_with_retry(article)
        return article.text
    except Exception as e:
        logger.warning(f"[{type(e).__name__}] Falha ao extrair '{article_url}': {e}")
        return None


def get_summarized_content(
    search_topics: List[str],
    max_articles: int = 5,
    source_mode: str = "elite",
) -> str:
    """
    Orquestra a extração e garante que o conteúdo total não exceda
    MAX_TOTAL_CHARS_FOR_LLM, evitando HTTP 413 na API da Groq.
    """
    raw_articles = fetch_news_from_keywords(
        search_topics, max_results_per_keyword=10, source_mode=source_mode
    )

    if not raw_articles:
        logger.warning("Nenhum artigo encontrado na busca.")
        return ""

    content_for_llm = []
    processed_count = 0
    total_chars = 0

    for article_data in raw_articles:
        if processed_count >= max_articles:
            logger.info(f"Cota de {max_articles} artigos atingida.")
            break

        # CORREÇÃO 413: Para antes de ultrapassar o limite de contexto da Groq
        if total_chars >= MAX_TOTAL_CHARS_FOR_LLM:
            logger.info(
                f"Limite de {MAX_TOTAL_CHARS_FOR_LLM} chars atingido com {processed_count} artigos. "
                "Parando extração para não exceder o contexto da Groq."
            )
            break

        logger.info(f"Extraindo: {article_data['title']}")
        full_text = extract_full_text(article_data["link"])

        if full_text and len(full_text) > 500:
            if len(full_text) > CHAR_LIMIT_PER_ARTICLE:
                full_text = full_text[:CHAR_LIMIT_PER_ARTICLE] + "..."

            entry = f"Título: {article_data['title']}\nConteúdo: {full_text}\n\n---\n\n"

            # Verifica se este artigo ainda cabe dentro do orçamento total
            if total_chars + len(entry) > MAX_TOTAL_CHARS_FOR_LLM:
                # Tenta encaixar uma versão menor
                available = MAX_TOTAL_CHARS_FOR_LLM - total_chars - 60  # 60 para o cabeçalho
                if available > 300:
                    trimmed_text = full_text[:available] + "..."
                    entry = f"Título: {article_data['title']}\nConteúdo: {trimmed_text}\n\n---\n\n"
                else:
                    logger.info("Sem espaço para mais artigos. Encerrando extração.")
                    break

            content_for_llm.append(entry)
            total_chars += len(entry)
            processed_count += 1
            logger.info(
                f"Artigo adicionado ({processed_count}/{max_articles}) — "
                f"total acumulado: {total_chars}/{MAX_TOTAL_CHARS_FOR_LLM} chars."
            )
        else:
            logger.warning("Conteúdo vazio, paywall ou muito curto. Descartando.")

    logger.info(f"Extração concluída: {processed_count} artigos, {total_chars} chars totais.")
    return "".join(content_for_llm)