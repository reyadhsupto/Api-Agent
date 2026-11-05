"""
Parses a raw cURL command into structured request components.

Accepts:
    curl_string (str): Raw cURL command text.

Returns:
    dict: method, url, headers, body.
"""

import shlex
from urllib.parse import parse_qsl, urlsplit, urlunsplit


def parse_curl(curl_string: str) -> dict:
    """
    Parse a cURL command into structured components.

    Args:
        curl_string (str): Raw cURL command.

    Returns:
        dict: Parsed request with method, url, headers, body.
    """
    tokens = shlex.split(curl_string.strip(), posix=True)
    if tokens and tokens[0].lower() in {"curl", "curl.exe"}:
        tokens.pop(0)

    method = "GET"
    url = ""
    headers: dict = {}
    body = None
    query_params: dict = {}
    data_parts: list[str] = []
    get_with_data = False
    basic_auth = None

    def option_value(index: int, token: str, short: str, long: str):
        if token in (short, long):
            if index + 1 >= len(tokens):
                raise ValueError(f"{token} requires a value")
            return tokens[index + 1], 2
        for prefix in (short, long + "="):
            if prefix and token.startswith(prefix) and token != short:
                return token[len(prefix):].lstrip("="), 1
        return None, 0

    i = 0
    while i < len(tokens):
        token = tokens[i]
        value, consumed = option_value(i, token, "-X", "--request")
        if consumed:
            method = value.upper()
            i += consumed
        elif token in ("-G", "--get"):
            get_with_data = True
            method = "GET"
            i += 1
        elif token in ("-H", "--header") and i + 1 < len(tokens):
            header = tokens[i + 1]
            if ":" in header:
                key, value = header.split(":", 1)
                headers[key.strip()] = value.strip()
            i += 2
        elif token in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode") and i + 1 < len(tokens):
            data_parts.append(tokens[i + 1])
            i += 2
        elif token in ("-u", "--user") and i + 1 < len(tokens):
            basic_auth = tokens[i + 1]
            i += 2
        elif token in ("--url", "-A", "--user-agent", "-e", "--referer", "-b", "--cookie") and i + 1 < len(tokens):
            if token == "--url":
                url = tokens[i + 1]
            elif token in ("-A", "--user-agent"):
                headers["User-Agent"] = tokens[i + 1]
            elif token in ("-e", "--referer"):
                headers["Referer"] = tokens[i + 1]
            elif token in ("-b", "--cookie"):
                headers["Cookie"] = tokens[i + 1]
            i += 2
        elif token.startswith(("http://", "https://")):
            url = token
            i += 1
        elif token in ("--compressed", "-k", "--insecure", "-i", "--include", "-L", "--location", "-s", "--silent", "-S", "--show-error"):
            i += 1
        else:
            i += 1

    if basic_auth:
        import base64
        headers["Authorization"] = "Basic " + base64.b64encode(basic_auth.encode()).decode()
    if data_parts:
        if get_with_data:
            query_params.update(parse_qsl("&".join(data_parts), keep_blank_values=True))
        else:
            body = "&".join(data_parts)
            method = "POST" if method == "GET" else method
    if url:
        parts = urlsplit(url)
        existing_query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query_params = {**existing_query, **query_params}
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))

    return {
        "method": method,
        "url": url,
        "headers": headers,
        "body": body,
        "query_params": query_params,
    }
