"""Parse API contracts and derive conservative request dependency flows."""

import hashlib
import html
import ipaddress
import json
import re
import socket
import uuid
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests
try:
    import yaml
except ImportError:  # Keep JSON/Postman APIs available until optional YAML support is installed.
    yaml = None


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
GENERIC_FIELD_NAMES = {"id"}


class _TextExtractor(HTMLParser):
    """Collect readable HTML text.

    Returns:
        _TextExtractor: Parser with a visible-text buffer.
    """

    def __init__(self):
        """Initialize the parser and its text buffer.

        Returns:
            None: Initializes parser state.
        """
        super().__init__()
        self.parts = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        """Track non-visible content regions.

        Args:
            tag (str): HTML element name.
            attrs (list): HTML element attributes.

        Returns:
            None: Updates hidden-region depth.
        """
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        """Leave a non-visible content region.

        Args:
            tag (str): Closing HTML element name.

        Returns:
            None: Updates hidden-region depth.
        """
        if tag.lower() in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        """Append visible text nodes.

        Args:
            data (str): HTML text node content.

        Returns:
            None: Appends visible content to the parser buffer.
        """
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())


def _html_to_text(source: str) -> str:
    """Convert an HTML documentation page into plain text.

    Args:
        source (str): HTML source document.

    Returns:
        str: Visible page text without script/style content.
    """
    parser = _TextExtractor()
    parser.feed(source)
    return "\n".join(parser.parts)


def _public_http_url(url: str) -> str:
    """Validate a public URL and reject private network hosts.

    Args:
        url (str): Anonymous documentation URL to validate.

    Returns:
        str: The validated URL.

    Raises:
        ValueError: If the URL is invalid or resolves to a non-public host.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Use a public http:// or https:// documentation URL without embedded credentials.")
    host = parts.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise ValueError("Documentation URL must use a publicly reachable host.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
            }
        except OSError as exc:
            raise ValueError(f"Could not resolve documentation host: {exc}") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Documentation URL must resolve only to public IP addresses.")
    return url


def fetch_public_document(url: str, max_bytes: int = 5_000_000) -> tuple[str, str]:
    """Fetch a public page with redirect and size limits.

    Args:
        url (str): Public documentation URL.
        max_bytes (int): Maximum downloaded document size.

    Returns:
        tuple[str, str]: Document text and HTTP Content-Type.

    Raises:
        ValueError: If redirects, host validation, or size limits fail.
        requests.RequestException: If the HTTP request fails.
    """
    current_url = url
    for _ in range(6):
        current_url = _public_http_url(current_url)
        response = requests.get(current_url, timeout=20, allow_redirects=False, stream=True)
        if response.is_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ValueError("Documentation URL returned a redirect without a location.")
            current_url = urljoin(current_url, location)
            continue
        response.raise_for_status()
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            response.close()
            raise ValueError("Documentation URL exceeds the 5 MB import limit.")
        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > max_bytes:
                response.close()
                raise ValueError("Documentation URL exceeds the 5 MB import limit.")
            chunks.append(chunk)
        content = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        return content, response.headers.get("Content-Type", "")
    raise ValueError("Documentation URL redirected too many times.")


def _resolve_ref(document: dict, value, ref_stack: set[str] | None = None):
    """Resolve local JSON references recursively while preventing reference loops.

    Args:
        document (dict): OpenAPI/Swagger document containing components.
        value (Any): Value that may contain local `$ref` fields.
        ref_stack (set[str] | None): References already being resolved.

    Returns:
        Any: Value with resolvable local references expanded.
    """
    if isinstance(value, list):
        return [_resolve_ref(document, item, ref_stack) for item in value]
    if not isinstance(value, dict):
        return value
    stack = set(ref_stack or ())
    ref = value.get("$ref")
    merged = {}
    if isinstance(ref, str) and ref.startswith("#/") and ref not in stack:
        target = document
        try:
            for token in ref[2:].split("/"):
                target = target[token.replace("~1", "/").replace("~0", "~")]
            stack.add(ref)
            resolved = _resolve_ref(document, target, stack)
            if isinstance(resolved, dict):
                merged.update(resolved)
        except (KeyError, TypeError):
            pass
    merged.update({key: _resolve_ref(document, item, stack) for key, item in value.items() if key != "$ref"})
    return merged


def _schema_fields(document: dict, schema: dict, prefix: str = "", stack: set[str] | None = None) -> list[dict]:
    """Return property paths while expanding local refs and compositions.

    Args:
        document (dict): OpenAPI/Swagger document.
        schema (dict): JSON Schema node to traverse.
        prefix (str): Parent property path.
        stack (set[str] | None): References already traversed.

    Returns:
        list[dict]: Fields with property name and dotted path.
    """
    if not isinstance(schema, dict):
        return []
    refs = set(stack or ())
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref in refs:
        return []
    if isinstance(ref, str):
        refs.add(ref)
    resolved = _resolve_ref(document, schema, stack)
    results = []
    properties = resolved.get("properties", {})
    if isinstance(properties, dict):
        for name, child in properties.items():
            path = f"{prefix}.{name}" if prefix else str(name)
            results.append({"name": str(name), "path": path})
            results.extend(_schema_fields(document, child, path, refs))
    for keyword in ("allOf", "oneOf", "anyOf"):
        for child in resolved.get(keyword, []) if isinstance(resolved.get(keyword), list) else []:
            results.extend(_schema_fields(document, child, prefix, refs))
    return results


def _schema_example(document: dict, schema: dict):
    """Return documented example/default values from a schema.

    Args:
        document (dict): OpenAPI/Swagger document containing references.
        schema (dict): Schema to inspect.

    Returns:
        Any: Explicit example/default object, or None when absent.
    """
    schema = _resolve_ref(document, schema)
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if isinstance(schema.get("properties"), dict):
        example = {
            name: value
            for name, child in schema["properties"].items()
            if (value := _schema_example(document, child)) is not None
        }
        return example or None
    return None


def _server_url(server: dict) -> tuple[str, bool]:
    """Resolve server variables using defaults.

    Args:
        server (dict): OpenAPI server declaration.

    Returns:
        tuple[str, bool]: Resolved server URL and unresolved-variable flag.
    """
    url = str(server.get("url", ""))
    variables = server.get("variables", {}) or {}
    missing = False
    for name in re.findall(r"\{([^{}]+)\}", url):
        variable = variables.get(name, {})
        value = variable.get("default")
        if value is None:
            missing = True
        else:
            url = url.replace("{" + name + "}", str(value))
    return url, missing


def _make_url(base_url: str, path: str) -> str:
    """Join a base URL and endpoint path.

    Args:
        base_url (str): API origin/base path, possibly empty.
        path (str): Operation path.

    Returns:
        str: Joined request URL or relative path.
    """
    if not base_url:
        return path
    if base_url.startswith(("http://", "https://")):
        return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _endpoint_sort_path(endpoint: dict) -> str:
    """Return the contract path used for stable method/path ranking.

    Args:
        endpoint (dict): Imported endpoint with optional contract metadata.

    Returns:
        str: Original API path, falling back to the request URL.
    """
    return str((endpoint.get("contract") or {}).get("path") or endpoint.get("url") or "")


def _openapi_endpoints(document: dict, source_id: str, base_url_override: str = "") -> tuple[list[dict], str, bool]:
    """Extract every HTTP operation from OpenAPI or Swagger paths.

    Args:
        document (dict): Parsed OpenAPI 3.x or Swagger 2.0 document.
        source_id (str): Stable identifier shared by this import's operations.
        base_url_override (str): Optional user-provided API base URL.

    Returns:
        tuple[list[dict], str, bool]: Endpoint previews, API title, and OpenAPI flag.
    """
    swagger = str(document.get("swagger", "")).startswith("2.")
    source_format = "swagger2" if swagger else "openapi3"
    if swagger:
        scheme = (document.get("schemes") or ["https"])[0]
        server = f"{scheme}://{document.get('host', '')}{document.get('basePath', '')}"
        document = dict(document)
        document.setdefault("components", {})
        document["components"].setdefault("schemas", document.get("definitions", {}))
        servers = [{"url": server}] if document.get("host") else []
    else:
        servers = document.get("servers") or []
    title = ((document.get("info") or {}).get("title") or "Imported API")
    endpoints = []
    paths = document.get("paths", {}) or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_item = _resolve_ref(document, path_item)
        path_parameters = path_item.get("parameters", []) or []
        for method, operation in path_item.items():
            method_lower = str(method).lower()
            if method_lower not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation = _resolve_ref(document, operation)
            parameters = {}
            for raw_parameter in path_parameters + (operation.get("parameters", []) or []):
                parameter = _resolve_ref(document, raw_parameter)
                if isinstance(parameter, dict) and parameter.get("name") and parameter.get("in"):
                    parameters[(parameter["in"], parameter["name"])] = parameter
            headers, query_params, request_fields = {}, [], []
            for (location, name), parameter in parameters.items():
                if location == "path":
                    request_fields.append({"name": name, "path": name, "target": f"request.path.{name}", "in": "path"})
                elif location == "query":
                    parameter_schema = parameter.get("schema") or {}
                    query_value = parameter.get(
                        "example", parameter_schema.get("example", parameter_schema.get("default", ""))
                    )
                    query_params.append({"key": name, "value": query_value, "enabled": True})
                    request_fields.append({"name": name, "path": name, "target": f"query_params.{name}", "in": "query"})
                elif location == "header":
                    parameter_schema = parameter.get("schema") or {}
                    header_value = parameter.get(
                        "example", parameter_schema.get("example", parameter_schema.get("default", ""))
                    )
                    headers[name] = str(header_value)
                    request_fields.append({"name": name, "path": name, "target": f"headers.{name}", "in": "header"})
            request_body = _resolve_ref(document, operation.get("requestBody", {}) or {})
            if swagger:
                body_parameter = next((parameter for parameter in parameters.values() if parameter.get("in") == "body"), None)
                body_schema = body_parameter.get("schema", {}) if body_parameter else {}
            else:
                body_schema = (((request_body.get("content") or {}).get("application/json") or {}).get("schema") or {})
            body_schema = _resolve_ref(document, body_schema)
            request_fields.extend(
                {"name": field["name"], "path": field["path"], "target": "request.body." + field["path"], "in": "body"}
                for field in _schema_fields(document, body_schema)
            )
            body = _schema_example(document, body_schema)
            if not swagger:
                body_content = (request_body.get("content") or {}).get("application/json") or {}
                if "example" in body_content:
                    body = body_content["example"]
                elif body_content.get("examples"):
                    first_example = next(iter(body_content["examples"].values()))
                    body = first_example.get("value") if isinstance(first_example, dict) else None
            responses = operation.get("responses", {}) or {}
            response_fields = []
            for status, raw_response in responses.items():
                if not str(status).startswith("2"):
                    continue
                response = _resolve_ref(document, raw_response)
                if swagger:
                    response_schema = response.get("schema", {})
                else:
                    response_schema = (((response.get("content") or {}).get("application/json") or {}).get("schema") or {})
                response_fields.extend(
                    {"name": field["name"], "path": field["path"], "json_path": "$." + field["path"]}
                    for field in _schema_fields(document, response_schema)
                )
            operation_server = (operation.get("servers") or path_item.get("servers") or servers or [{}])[0]
            operation_base, unresolved = _server_url(operation_server)
            if base_url_override:
                operation_base, unresolved = base_url_override, False
            missing_base = bool(
                unresolved
                or not (operation_base or base_url_override).startswith(("http://", "https://"))
            )
            operation_id = operation.get("operationId") or f"{method_lower.upper()} {path}"
            description = operation.get("summary") or operation.get("description") or ""
            endpoints.append({
                "id": str(uuid.uuid4()), "name": operation.get("summary") or operation_id,
                "method": method_lower.upper(), "url": _make_url(operation_base, path),
                "headers": headers, "query_params": query_params, "body": body,
                "include_body": body is not None, "include": False, "include_for_generation": False,
                "deprecated": bool(operation.get("deprecated", False)),
                "source_excerpt": description,
                "contract": {"source_id": source_id, "source_format": source_format,
                    "operation_id": operation_id, "path": path,
                    "request_fields": request_fields, "response_fields": response_fields},
                "_base_url_required": missing_base,
            })
    return endpoints, title, source_format == "openapi3" or source_format == "swagger2"


def _postman_url(request: dict, variables: dict, base_url_override: str) -> tuple[str, list[dict], bool]:
    """Normalize a Postman URL and query rows.

    Args:
        request (dict): Postman request definition.
        variables (dict): Collection variables and values.
        base_url_override (str): Optional base URL supplied during review.

    Returns:
        tuple[str, list[dict], bool]: URL, query rows, and base-URL-required flag.
    """
    url_data = request.get("url", "")
    if isinstance(url_data, dict):
        raw_url = url_data.get("raw", "")
    else:
        raw_url = str(url_data)
    unresolved = False
    for key, value in variables.items():
        raw_url = raw_url.replace("{{" + key + "}}", str(value))
    remaining = re.findall(r"\{\{([^{}]+)\}\}", raw_url)
    query = []
    if isinstance(url_data, dict):
        query = [
            {"key": row.get("key", ""), "value": row.get("value", ""), "enabled": not row.get("disabled", False)}
            for row in url_data.get("query", []) if row.get("key")
        ]
    parts = urlsplit(raw_url)
    if parts.query and not query:
        from urllib.parse import parse_qsl
        query = [{"key": key, "value": value, "enabled": True} for key, value in parse_qsl(parts.query, keep_blank_values=True)]
    if remaining:
        if base_url_override:
            raw_url = _make_url(base_url_override, raw_url[raw_url.find("}}") + 2:] if "}}" in raw_url else raw_url)
        else:
            unresolved = True
    elif base_url_override and not parts.scheme:
        raw_url = _make_url(base_url_override, raw_url)
    if parts.query:
        raw_url = raw_url.split("?", 1)[0]
    unresolved = unresolved or not raw_url.startswith(("http://", "https://"))
    return raw_url, query, unresolved


def _postman_endpoints(document: dict, source_id: str, base_url_override: str = "") -> tuple[list[dict], str]:
    """Flatten nested Postman folders into request endpoint records.

    Args:
        document (dict): Postman Collection v2.1 document.
        source_id (str): Stable identifier shared by this import's requests.
        base_url_override (str): Optional base URL supplied during review.

    Returns:
        tuple[list[dict], str]: Endpoint previews and collection name.
    """
    variables = {
        str(item.get("key", item.get("name", ""))): item.get("value", item.get("currentValue", ""))
        for item in document.get("variable", []) if isinstance(item, dict)
    }
    endpoints = []

    def walk(items: list, folder: str = ""):
        """Visit nested collection items.

        Args:
            items (list): Postman folder entries.
            folder (str): Parent folder name prefix.

        Returns:
            None: Appends request entries to the enclosing endpoint list.
        """
        for item in items:
            if not isinstance(item, dict):
                continue
            request = item.get("request")
            if isinstance(request, dict):
                url, query, unresolved = _postman_url(request, variables, base_url_override)
                body_data = request.get("body", {}) or {}
                body = body_data.get("raw") if body_data.get("mode") == "raw" else None
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError:
                        pass
                headers = [
                    {"key": row.get("key"), "value": row.get("value", ""),
                     "enabled": not row.get("disabled", False), "description": row.get("description", "")}
                    for row in request.get("header", []) if row.get("key")
                ]
                name = item.get("name") or "Untitled Request"
                endpoints.append({
                    "id": str(uuid.uuid4()), "name": f"{folder}{name}" if folder else name,
                    "method": str(request.get("method", "GET")).upper(), "url": url,
                    "headers": headers, "query_params": query, "body": body,
                    "include_body": body is not None and not body_data.get("disabled", False),
                    "include": False, "include_for_generation": False,
                    "source_excerpt": "",
                    "contract": {"source_id": source_id, "source_format": "postman21"},
                    "_base_url_required": unresolved,
                })
            elif isinstance(item.get("item"), list):
                walk(item["item"], f"{folder}{item.get('name', 'Folder')} / ")

    walk(document.get("item", []))
    return endpoints, (document.get("info", {}) or {}).get("name", "Postman Collection")


def normalize_prose_endpoints(items: list[dict], source_id: str, source_format: str, base_url: str = "") -> list[dict]:
    """Normalize LLM-proposed endpoints extracted from prose documentation.

    Args:
        items (list[dict]): LLM-proposed operation objects.
        source_id (str): Stable identifier for the imported source.
        source_format (str): Normalized source type.
        base_url (str): Optional API base URL supplied during review.

    Returns:
        list[dict]: Endpoint previews in the saved-request format.
    """
    endpoints = []
    for item in items:
        method = str(item.get("method", "GET")).upper()
        path = str(item.get("path") or item.get("url") or "").strip()
        if method.lower() not in HTTP_METHODS or not path:
            continue
        url = path if path.startswith(("http://", "https://")) else _make_url(base_url, path)
        endpoints.append({
            "id": str(uuid.uuid4()), "name": str(item.get("name") or f"{method} {path}"),
            "method": method, "url": url, "headers": item.get("headers") or {},
            "query_params": item.get("query_params") or [], "body": item.get("body"),
            "include_body": item.get("body") is not None, "include": False,
            "include_for_generation": False, "source_excerpt": str(item.get("source_excerpt") or item.get("evidence") or ""),
            "confidence": item.get("confidence"),
            "contract": {"source_id": source_id, "source_format": source_format},
            "_base_url_required": not url.startswith(("http://", "https://")),
        })
    return endpoints


def parse_contract_document(
    content: str,
    source_name: str = "",
    format_hint: str = "auto",
    base_url: str = "",
    source_id: str | None = None,
    is_html: bool = False,
) -> dict:
    """Parse supported contract or prose content into endpoint preview data.

    Args:
        content (str): Contract or documentation text.
        source_name (str): Name or URL shown in the review UI.
        format_hint (str): Auto, OpenAPI, Postman, or prose mode.
        base_url (str): Optional API base URL override.
        source_id (str | None): Stable ID retained when re-previewing.
        is_html (bool): Whether content should be converted from HTML first.

    Returns:
        dict: Endpoint previews, dependency evidence, and flow candidates.

    Raises:
        ValueError: If the input format is unsupported or has no usable operations.
        RuntimeError: If LLM-assisted prose extraction fails.
    """
    if not content.strip():
        raise ValueError("Provide a document or contract to import.")
    if is_html:
        content = _html_to_text(content)
    source_id = source_id or str(uuid.uuid4())
    document = None
    if format_hint != "text":
        try:
            document = json.loads(content)
        except json.JSONDecodeError:
            if yaml is None:
                looks_like_contract = format_hint == "openapi" or re.search(
                    r"(?m)^\s*(?:openapi|swagger|paths|info):", content
                )
                if looks_like_contract:
                    raise ValueError("YAML contract import requires PyYAML. Install project dependencies with `make install-backend`.")
            else:
                try:
                    document = yaml.safe_load(content)
                except yaml.YAMLError:
                    document = None
    is_openapi = isinstance(document, dict) and ("openapi" in document or "swagger" in document)
    is_postman = isinstance(document, dict) and isinstance(document.get("info"), dict) and isinstance(document.get("item"), list)
    if format_hint == "openapi" and not is_openapi:
        raise ValueError("The provided content is not an OpenAPI 3.x or Swagger 2.0 document.")
    if format_hint == "postman" and not is_postman:
        raise ValueError("The provided content is not a Postman collection document.")
    if is_openapi:
        if "openapi" in document and not str(document["openapi"]).startswith("3."):
            raise ValueError("Only OpenAPI 3.x and Swagger 2.0 specifications are supported.")
        if "swagger" in document and not str(document["swagger"]).startswith("2."):
            raise ValueError("Only OpenAPI 3.x and Swagger 2.0 specifications are supported.")
        endpoints, title, _ = _openapi_endpoints(document, source_id, base_url)
        source_format = "swagger2" if "swagger" in document else "openapi3"
    elif is_postman:
        schema_url = str((document.get("info") or {}).get("schema", ""))
        if schema_url and "v2.1.0" not in schema_url:
            raise ValueError("Only Postman Collection v2.1 is supported.")
        endpoints, title = _postman_endpoints(document, source_id, base_url)
        source_format = "postman21"
    else:
        from app.generator import extract_endpoints_from_document
        extracted = extract_endpoints_from_document(content)
        source_format = "prose"
        title = source_name or "API Documentation"
        endpoints = normalize_prose_endpoints(extracted, source_id, source_format, base_url)
    for endpoint in endpoints:
        endpoint.get("contract", {})["source_name"] = source_name or title
    graph = build_dependency_graph(endpoints)
    return {
        "source_id": source_id,
        "source_name": source_name or title,
        "source_format": source_format,
        "title": title,
        "base_url_required": any(item.get("_base_url_required") for item in endpoints),
        "endpoints": endpoints,
        "dependencies": graph["dependencies"],
        "candidate_flows": graph["candidate_flows"],
    }


def _normalized_field(name: str) -> str:
    """Normalize case and separators for exact identifier matching.

    Args:
        name (str): Schema property or parameter name.

    Returns:
        str: Lowercase identifier with non-alphanumeric characters removed.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _reachable(start: str, target: str, adjacency: dict[str, set[str]]) -> bool:
    """Check reachability in a directed graph.

    Args:
        start (str): Starting endpoint ID.
        target (str): Destination endpoint ID.
        adjacency (dict[str, set[str]]): Outgoing edge map.

    Returns:
        bool: Whether a directed path connects start to target.
    """
    pending, visited = [start], set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, set()) - visited)
    return False


def build_dependency_graph(endpoints: list[dict]) -> dict:
    """Build field-match edges and ranked maximal paths.

    Args:
        endpoints (list[dict]): Saved or preview endpoint records with contract metadata.

    Returns:
        dict: Dependency edges and ranked candidate flow paths.
    """
    by_source: dict[str, list[dict]] = {}
    for endpoint in endpoints:
        contract = endpoint.get("contract") or {}
        if contract.get("response_fields") or contract.get("request_fields"):
            by_source.setdefault(contract.get("source_id", ""), []).append(endpoint)
    dependencies, candidate_flows = [], []
    for source_id, group in by_source.items():
        edges = []
        for producer in group:
            producer_contract = producer["contract"]
            producer_fields = producer_contract.get("response_fields", [])
            for consumer in group:
                if producer["id"] == consumer["id"]:
                    continue
                consumer_fields = consumer["contract"].get("request_fields", [])
                matches = []
                for response_field in producer_fields:
                    normalized = _normalized_field(response_field.get("name", ""))
                    if not normalized or normalized in GENERIC_FIELD_NAMES:
                        continue
                    for request_field in consumer_fields:
                        if normalized == _normalized_field(request_field.get("name", "")):
                            matches.append({
                                "response_field": response_field.get("json_path"),
                                "request_field": request_field.get("target"),
                                "field_name": response_field.get("name"),
                            })
                if matches:
                    edges.append({"from": producer["id"], "to": consumer["id"], "evidence": matches})
        adjacency: dict[str, set[str]] = {endpoint["id"]: set() for endpoint in group}
        for edge in edges:
            adjacency[edge["from"]].add(edge["to"])
        cyclic_edges = [
            edge for edge in edges if _reachable(edge["to"], edge["from"], adjacency)
        ]
        cyclic_pairs = {(edge["from"], edge["to"]) for edge in cyclic_edges}
        dependencies.extend({**edge, "cyclic": (edge["from"], edge["to"]) in cyclic_pairs} for edge in edges)
        usable = [edge for edge in edges if (edge["from"], edge["to"]) not in cyclic_pairs]
        graph: dict[str, list[dict]] = {endpoint["id"]: [] for endpoint in group}
        incoming = {endpoint["id"]: 0 for endpoint in group}
        for edge in usable:
            graph[edge["from"]].append(edge)
            incoming[edge["to"]] += 1
        endpoint_by_id = {item["id"]: item for item in group}
        paths = []

        def walk(endpoint_id: str, current: list[str], path_edges: list[dict]):
            """Enumerate a maximal path in the acyclic dependency graph.

            Args:
                endpoint_id (str): Current endpoint ID.
                current (list[str]): Endpoint IDs already in this path.
                path_edges (list[dict]): Dependency edges already in this path.

            Returns:
                None: Appends each completed maximal path to the enclosing list.
            """
            outgoing = sorted(graph[endpoint_id], key=lambda item: (
                endpoint_by_id[item["to"]].get("method", ""), _endpoint_sort_path(endpoint_by_id[item["to"]])
            ))
            if not outgoing:
                if len(current) > 1:
                    paths.append((current, path_edges))
                return
            for edge in outgoing:
                walk(edge["to"], current + [edge["to"]], path_edges + [edge])

        starts = sorted(
            (key for key, count in incoming.items() if count == 0 and graph[key]),
            key=lambda key: (endpoint_by_id[key].get("method", ""), _endpoint_sort_path(endpoint_by_id[key])),
        )
        for start in starts:
            walk(start, [start], [])
        paths.sort(key=lambda item: (
            -len(item[1]),
            tuple((endpoint_by_id[key].get("method", ""), _endpoint_sort_path(endpoint_by_id[key])) for key in item[0]),
        ))
        for path, path_edges in paths:
            digest = hashlib.sha1(",".join(path).encode("utf-8")).hexdigest()[:12]
            candidate_flows.append({
                "id": f"candidate-{digest}", "source_id": source_id,
                "endpoint_ids": path, "dependency_count": len(path_edges), "dependencies": path_edges,
                "endpoints": [endpoint_by_id[key] for key in path],
            })
    return {"dependencies": dependencies, "candidate_flows": candidate_flows}

