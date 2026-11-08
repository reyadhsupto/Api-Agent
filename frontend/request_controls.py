"""Bidirectional Streamlit controls for debounced cURL input and request ordering."""

import streamlit as st


_HTML = '<div class="aa-request-control-root"></div>'

_CSS = """
.aa-request-control-root { font: inherit; color: var(--st-text-color, inherit); }
.aa-url-area {
    display: block; box-sizing: border-box; width: 100%; min-height: 39px; max-height: 112px;
    resize: vertical; overflow: auto; padding: .48rem .7rem; border: 1px solid var(--st-border-color, rgba(128,128,128,.35));
    border-radius: 8px; color: var(--st-text-color, inherit); background: var(--st-background-color, transparent);
    font: 400 .9rem/1.35 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.aa-url-area:focus { outline: 2px solid rgba(255,108,55,.48); border-color: #ff6c37; }
.aa-request-list { display: grid; gap: 5px; }
.aa-request-row {
    display: grid; grid-template-columns: 34px 30px 78px minmax(0, 1fr); align-items: center; gap: 9px;
    min-height: 44px; padding: 5px 10px; border: 1px solid var(--st-border-color, rgba(128,128,128,.24));
    border-radius: 9px; background: var(--st-secondary-background-color, rgba(128,128,128,.055));
}
.aa-request-row:hover { border-color: rgba(255,108,55,.55); }
.aa-request-row.aa-dragging { opacity: .5; }
.aa-request-row.aa-drop-target { border-top: 2px solid #ff6c37; }
.aa-drag-handle {
    display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px;
    border: 0; border-radius: 6px; color: var(--st-secondary-text-color, #777); background: transparent;
    cursor: grab; touch-action: none; user-select: none;
}
.aa-drag-handle:hover, .aa-drag-handle:focus-visible { color: #ff6c37; background: rgba(255,108,55,.10); outline: none; }
.aa-drag-handle:active { cursor: grabbing; }
.aa-request-check { width: 17px; height: 17px; accent-color: #ff6c37; cursor: pointer; }
.aa-method-pill { justify-self: start; min-width: 46px; padding: 3px 7px; border-radius: 6px; font: 700 .7rem/1.15 ui-monospace, SFMono-Regular, Menlo, monospace; text-align: center; }
.aa-method-get { color: #16834a; background: rgba(46,158,91,.13); }
.aa-method-post { color: #c64c21; background: rgba(255,108,55,.16); }
.aa-method-put, .aa-method-patch { color: #3269a8; background: rgba(57,126,202,.14); }
.aa-method-delete { color: #c0393b; background: rgba(229,72,77,.13); }
.aa-method-other { color: var(--st-secondary-text-color, #777); background: rgba(128,128,128,.12); }
.aa-request-meta { display: flex; align-items: baseline; gap: .65rem; min-width: 0; overflow: hidden; }
.aa-request-name { min-width: 0; overflow: hidden; font-size: .88rem; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.aa-request-url { min-width: 0; overflow: hidden; color: var(--st-secondary-text-color, #777); font: .74rem/1.3 ui-monospace, SFMono-Regular, Menlo, monospace; text-overflow: ellipsis; white-space: nowrap; }
"""

_JS = r"""
export default function(component) {
    const { data, parentElement, setStateValue, setTriggerValue } = component;
    const host = parentElement.querySelector('.aa-request-control-root');
    if (!host) return;

    if (data.mode === 'url') {
        let input = host.querySelector('.aa-url-area');
        if (!input) {
            input = document.createElement('textarea');
            input.className = 'aa-url-area';
            input.rows = 1;
            input.setAttribute('aria-label', 'URL or paste cURL');
            input.setAttribute('spellcheck', 'false');
            input.placeholder = 'https://api.example.com/resource or paste cURL';
            host.replaceChildren(input);
            input.addEventListener('input', () => {
                const text = input.value;
                setStateValue('text', text);
                input.rows = Math.min(5, Math.max(1, text.split('\n').length));
                const timerKey = `aa-curl-debounce-${data.instance_key}`;
                if (window[timerKey]) window.clearTimeout(window[timerKey]);
                if (/^\s*curl(?:\.exe)?(?:\s|$)/i.test(text)) {
                    window[timerKey] = window.setTimeout(() => {
                        setTriggerValue('curl_ready', text);
                        window[timerKey] = null;
                    }, 1000);
                }
            });
            input.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    input.blur();
                }
            });
        }
        const value = data.value || '';
        if (input.value !== value) {
            input.value = value;
            input.rows = Math.min(5, Math.max(1, value.split('\n').length));
            setStateValue('text', value);
        }
        return;
    }

    host.replaceChildren();
    const list = document.createElement('div');
    list.className = 'aa-request-list';
    host.appendChild(list);
    const rows = Array.isArray(data.rows) ? data.rows : [];
    let draggingRow = null;
    let dragPointerId = null;
    let orderChanged = false;

    const sendChange = () => {
        setTriggerValue('rows_change', {
            order_ids: Array.from(list.children).map((row) => row.dataset.requestId),
            selected_ids: Array.from(list.querySelectorAll('.aa-request-check:checked'))
                .map((checkbox) => checkbox.closest('.aa-request-row').dataset.requestId),
        });
    };
    const moveRow = (row, direction) => {
        const sibling = direction < 0 ? row.previousElementSibling : row.nextElementSibling;
        if (!sibling) return;
        if (direction < 0) list.insertBefore(row, sibling);
        else list.insertBefore(sibling, row);
        sendChange();
    };

    for (const item of rows) {
        const row = document.createElement('div');
        row.className = 'aa-request-row';
        row.dataset.requestId = item.id;
        const handle = document.createElement('button');
        handle.type = 'button';
        handle.className = 'aa-drag-handle';
        handle.title = 'Drag to reorder; use Alt+Up or Alt+Down when focused';
        handle.setAttribute('aria-label', `Reorder ${item.name || item.id}`);
        handle.innerHTML = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="6" cy="4" r="1.2" fill="currentColor"/><circle cx="12" cy="4" r="1.2" fill="currentColor"/><circle cx="6" cy="9" r="1.2" fill="currentColor"/><circle cx="12" cy="9" r="1.2" fill="currentColor"/><circle cx="6" cy="14" r="1.2" fill="currentColor"/><circle cx="12" cy="14" r="1.2" fill="currentColor"/></svg>';
        handle.addEventListener('keydown', (event) => {
            if (event.altKey && event.key === 'ArrowUp') { event.preventDefault(); moveRow(row, -1); }
            if (event.altKey && event.key === 'ArrowDown') { event.preventDefault(); moveRow(row, 1); }
        });
        row.appendChild(handle);

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'aa-request-check';
        checkbox.checked = Boolean(item.selected);
        checkbox.setAttribute('aria-label', `Include ${item.name || item.id} in this run`);
        checkbox.addEventListener('change', sendChange);
        row.appendChild(checkbox);

        const method = document.createElement('span');
        const methodValue = String(item.method || 'GET').toUpperCase();
        const methodClass = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(methodValue)
            ? methodValue.toLowerCase() : 'other';
        method.className = `aa-method-pill aa-method-${methodClass}`;
        method.textContent = methodValue;
        row.appendChild(method);

        const metadata = document.createElement('div');
        metadata.className = 'aa-request-meta';
        const name = document.createElement('span');
        name.className = 'aa-request-name';
        name.textContent = item.name || 'Untitled request';
        name.title = name.textContent;
        metadata.appendChild(name);
        if (item.url) {
            const url = document.createElement('span');
            url.className = 'aa-request-url';
            url.textContent = item.url;
            url.title = item.url;
            metadata.appendChild(url);
        }
        row.appendChild(metadata);

        handle.addEventListener('pointerdown', (event) => {
            if (event.button !== 0) return;
            event.preventDefault();
            draggingRow = row;
            dragPointerId = event.pointerId;
            orderChanged = false;
            row.classList.add('aa-dragging');
            handle.setPointerCapture(event.pointerId);
        });
        handle.addEventListener('pointermove', (event) => {
            if (!draggingRow || event.pointerId !== dragPointerId) return;
            const targetRow = Array.from(list.children).find((candidate) => {
                if (candidate === draggingRow) return false;
                const bounds = candidate.getBoundingClientRect();
                return event.clientY >= bounds.top && event.clientY <= bounds.bottom;
            });
            if (!targetRow) return;
            const bounds = targetRow.getBoundingClientRect();
            const insertAfter = event.clientY >= bounds.top + bounds.height / 2;
            const reference = insertAfter ? targetRow.nextSibling : targetRow;
            if (reference !== draggingRow && draggingRow.nextSibling !== reference) {
                list.insertBefore(draggingRow, reference);
                orderChanged = true;
            }
        });
        const finishDrag = (event) => {
            if (!draggingRow || event.pointerId !== dragPointerId) return;
            draggingRow.classList.remove('aa-dragging');
            draggingRow = null;
            dragPointerId = null;
            if (orderChanged) sendChange();
            orderChanged = false;
        };
        handle.addEventListener('pointerup', finishDrag);
        handle.addEventListener('pointercancel', finishDrag);
        list.appendChild(row);
    }
}
"""


_request_controls = st.components.v2.component(
    "api_agent_request_controls",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def render_curl_aware_url(value: str, instance_key: str):
    """Render the URL editor with debounced cURL detection.

    Args:
        value (str): Current URL or pasted cURL text.
        instance_key (str): Stable request-tab identifier.

    Returns:
        ComponentResult: Current text and an optional debounced cURL trigger.
    """
    return _request_controls(
        data={"mode": "url", "value": value, "instance_key": instance_key},
        default={"text": value},
        key=f"request-url-control-{instance_key}",
        on_text_change=lambda: None,
        on_curl_ready_change=lambda: None,
        width="stretch",
    )


def render_request_order_list(rows: list[dict], key: str):
    """Render the integrated selectable and draggable request list.

    Args:
        rows (list[dict]): Ordered eligible request rows and selection flags.
        key (str): Stable component key scoped to the current project.

    Returns:
        ComponentResult: Transient order/selection change, if one occurred.
    """
    return _request_controls(
        data={"mode": "order", "rows": rows},
        key=key,
        on_rows_change=lambda: None,
        width="stretch",
    )
