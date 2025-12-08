from urllib.parse import urlparse, parse_qs

def extract_youtube_id(url: str):
    """
    Tách YouTube video ID từ mọi dạng URL.
    """
    parsed = urlparse(url)

    if parsed.hostname in ["www.youtube.com", "youtube.com"]:
        qs = parse_qs(parsed.query)
        return qs.get("v", [None])[0]

    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/")

    if "shorts" in parsed.path:
        return parsed.path.split("/")[-1]

    return None
