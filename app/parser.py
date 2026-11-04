"""
Parses a raw cURL command into structured request components.

Accepts:
    curl_string (str): Raw cURL command text.

Returns:
    dict: method, url, headers, body.
"""

import shlex


def parse_curl(curl_string: str) -> dict:
    """
    Parse a cURL command into structured components.

    Args:
        curl_string (str): Raw cURL command.

    Returns:
        dict: Parsed request with method, url, headers, body.
    """
    cleaned = curl_string.strip()
    if cleaned.lower().startswith("curl "):
        cleaned = cleaned[5:].strip()

    tokens = shlex.split(cleaned)

    method = "GET"
    url = ""
    headers: dict = {}
    body = None

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 2
        elif token in ("-H", "--header") and i + 1 < len(tokens):
            header = tokens[i + 1]
            if ":" in header:
                key, value = header.split(":", 1)
                headers[key.strip()] = value.strip()
            i += 2
        elif token in ("-d", "--data", "--data-binary") and i + 1 < len(tokens):
            body = tokens[i + 1]
            i += 2
        elif token.startswith("http"):
            url = token
            i += 1
        else:
            i += 1

    return {
        "method": method,
        "url": url,
        "headers": headers,
        "body": body,
    }