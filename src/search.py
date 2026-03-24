from ddgs import DDGS


def web_search(query: str, max_results: int = 6) -> list:
    """Search the web and return list of {title, href, body} dicts."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception:
        return []
