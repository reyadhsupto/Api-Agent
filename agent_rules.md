# Agent Rules - Api-Agent

## Code Documentation Standards
Every function, method, and class must include a docstring comment specifying:
- What it does (purpose)
- What it accepts (parameters with names and data types)
- What it returns (return type and description)

Example:

def parse_curl(curl_string: str) -> dict:
    """
    Parses a raw cURL command string into a structured request dictionary.

    Args:
        curl_string (str): The raw cURL command to parse.

    Returns:
        dict: A dictionary containing method, url, headers, params, and body.
    """

## General Engineering Principles
1. SOLID: Single responsibility, open-closed, Liskov substitution, interface segregation, dependency inversion.
2. DRY: Do not repeat yourself. Extract shared logic into services or utilities.
3. KISS: Keep it simple. Avoid over-engineering for MVP.
4. Separation of Concerns: Keep API routes, schemas, services, and PostgreSQL persistence in separate modules.
5. Fail Fast: Validate inputs early at the API boundary.
6. Defensive Programming: Assume external APIs and LLMs can fail. Implement fallback chains.

## UI/UX Guidelines
1. Single-Page Flow: The user should move from cURL input to generated test cases to execution results without unnecessary page reloads.
2. Inline Editing: Allow users to edit generated test cases (payload, expected status) before execution.
3. Real-Time Feedback: Show loading states during LLM generation and test execution.
4. Error States: Display clear error messages for invalid cURL, LLM failures, or assertion mismatches.
5. Responsive Layout: Use a sidebar for navigation and a main content area for the active tab.
6. Design Principles: Always think of eyecatchy, vibrant and project aligned design maintaining good design principles
7. Usability: Always Think of best UX

## Prohibited Practices
- Do NOT use emojis in any documentation, code comments, or README files.
- Do NOT hardcode secrets or API keys in source code. Use environment variables.
- Use the configured PostgreSQL persistence layer; do not replace durable project data with in-memory storage.
- Do NOT implement authentication or authorization for MVP.
- Do NOT write unnecessary functions or methods. Keep code flat and readable.

## HTTP Client Standard
- Use the python requests library for all outbound HTTP calls.
- Do NOT use httpx, urllib, or other HTTP clients unless explicitly approved.

## LLM Integration Standard
- Support multiple free-tier LLM providers.
- Implement automatic fallback: if Provider A hits a token or rate limit, switch to Provider B.
- Log which provider was used for each generation request.
