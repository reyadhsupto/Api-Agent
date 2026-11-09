# frontend/request_controls.py

"""Bidirectional Streamlit controls for debounced cURL input and request ordering."""

import streamlit as st


_HTML = '<div class="aa-request-control-root"></div>'

_CSS = """
.aa-request-control-root { font: inherit; color: var(--st-text-color, inherit); container-type: inline-size; }
.aa-url-area {
    display: block; box-sizing: border-box; width: 100%; min-height: 39px; max-height: 112px;
    resize: vertical; overflow: auto; padding: .48rem .7rem; border: 1px solid var(--st-border-color, rgba(128,128,128,.35));
    border-radius: 8px; color: var(--st-text-color, inherit); background: var(--st-background-color, transparent);
    font: 400 .9rem/1.35 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.aa-url-area:focus { outline: 2px solid rgba(255,108,55,.48); border-color: #ff6c37; }
.aa-request-list { display: grid; gap: 5px; position: relative; }
.aa-request-row {
    display: grid; grid-template-columns: 30px 22px 18px 64px minmax(0, 1fr); align-items: center; gap: 8px;
    min-height: 44px; padding: 5px 10px; border: 1px solid var(--st-border-color, rgba(128,128,128,.24));
    border-radius: 9px; background: var(--st-secondary-background-color, rgba(128,128,128,.055));
    transition: border-color 150ms ease, background-color 150ms ease, box-shadow 150ms ease, transform 220ms cubic-bezier(.2,.8,.2,1);
    will-change: transform;
}
.aa-request-row:hover { border-color: rgba(255,108,55,.55); }
.aa-request-row.aa-dragging {
    position: relative; z-index: 3; opacity: .96;
    transform: translateY(var(--aa-drag-y, 0px)) scale(1.012);
    transition: box-shadow 150ms ease, border-color 150ms ease, background-color 150ms ease;
    border-color: #ff6c37; background: var(--st-background-color, #fff);
    box-shadow: 0 10px 26px rgba(25, 30, 40, .20), 0 0 0 2px rgba(255,108,55,.24);
}
.aa-request-row.aa-settled { animation: aa-settle 480ms ease-out; }
@keyframes aa-settle {
    from { box-shadow: 0 0 0 3px rgba(255,108,55,.38); border-color: #ff6c37; }
    to { box-shadow: 0 0 0 0 rgba(255,108,55,0); }
}
.aa-request-row.aa-dragging, .aa-request-row.aa-dragging * { user-select: none; }
.aa-request-row.aa-drop-target { border-color: rgba(255,108,55,.8); background: rgba(255,108,55,.08); }
.aa-drag-handle {
    display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 32px;
    border: 0; border-radius: 6px; color: var(--st-secondary-text-color, #777); background: transparent;
    cursor: grab; touch-action: none; user-select: none; -webkit-user-select: none;
}
.aa-drag-handle:hover, .aa-drag-handle:focus-visible { color: #ff6c37; background: rgba(255,108,55,.10); outline: none; }
.aa-drag-handle:focus-visible { box-shadow: 0 0 0 2px rgba(255,108,55,.5); }
.aa-drag-handle:active { cursor: grabbing; }
.aa-request-rank { color: var(--st-secondary-text-color, #777); font: 600 .72rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; text-align: center; }
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
.aa-sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
@container (max-width: 660px) {
    .aa-request-row { grid-template-columns: 28px 18px 16px 54px minmax(0, 1fr); gap: 5px; padding-inline: 6px; }
    .aa-request-meta { display: grid; gap: 1px; }
    .aa-request-url { font-size: .68rem; }
}
@media (prefers-reduced-motion: reduce) {
    .aa-request-row, .aa-drag-handle { transition: none !important; }
    .aa-request-row.aa-settled { animation: none; }
}
"""

_JS = r"""
const GLOBAL_STYLE_ID = 'aa-drag-global-style';

function ensureGlobalStyle() {
    if (document.getElementById(GLOBAL_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = GLOBAL_STYLE_ID;
    style.textContent = 'html.aa-dragging-global, html.aa-dragging-global * { cursor: grabbing !important; user-select: none !important; -webkit-user-select: none !important; }';
    document.head.appendChild(style);
}

function getScrollParent(element) {
    let node = element;
    while (node) {
        const root = node.getRootNode && node.getRootNode();
        node = node.parentElement || (root && root.host) || null;
        if (!node || node === document.body || node === document.documentElement) break;
        const style = getComputedStyle(node);
        if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight) return node;
    }
    return document.scrollingElement || document.documentElement;
}

export default function(component) {
    const { data, parentElement } = component;
    const host = parentElement.querySelector('.aa-request-control-root');
    if (!host) return;
    host.__aaComponent = component;
    const api = () => host.__aaComponent;

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
                input.rows = Math.min(5, Math.max(1, text.split('\n').length));
                if (host.__aaCurlTimer) window.clearTimeout(host.__aaCurlTimer);
                host.__aaCurlTimer = null;
                if (/^\s*curl(?:\.exe)?(?:\s|$)/i.test(text)) {
                    host.__aaCurlTimer = window.setTimeout(() => {
                        if (input.isConnected) {
                            api().setStateValue('text', text);
                            api().setTriggerValue('curl_ready', text);
                        }
                        host.__aaCurlTimer = null;
                    }, 3000);
                }
            });
            input.addEventListener('blur', () => {
                if (input.isConnected) api().setStateValue('text', input.value);
            });
            input.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    input.blur();
                }
            });
        }
        const value = data.value || '';
        const syncKey = data.sync_key || '';
        // Only apply server updates when the server-provided value actually
        // changes and the field is not being edited. A sync key marks an
        // intentional external replacement, such as the result of cURL parsing.
        if (!Object.prototype.hasOwnProperty.call(host, '__aaLastUrlValue')) {
            host.__aaSyncKey = syncKey;
            host.__aaLastUrlValue = value;
            input.value = value;
            input.rows = Math.min(5, Math.max(1, value.split('\n').length));
            api().setStateValue('text', value);
        } else if (host.__aaSyncKey !== syncKey) {
            host.__aaSyncKey = syncKey;
            host.__aaLastUrlValue = value;
            input.value = value;
            input.rows = Math.min(5, Math.max(1, value.split('\n').length));
            api().setStateValue('text', value);
        } else if (host.__aaLastUrlValue !== value) {
            if (!input.matches(':focus')) {
                host.__aaLastUrlValue = value;
                input.value = value;
                input.rows = Math.min(5, Math.max(1, value.split('\n').length));
            }
        }
        return;
    }

    ensureGlobalStyle();
    host.replaceChildren();
    const list = document.createElement('div');
    list.className = 'aa-request-list';
    list.setAttribute('role', 'list');
    const status = document.createElement('div');
    status.className = 'aa-sr-only';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    host.append(list, status);

    const rows = Array.isArray(data.rows) ? data.rows : [];
    let drag = null;
    const slotBase = () => list.firstElementChild ? list.firstElementChild.offsetTop : 0;
    const slotTop = (row) => row.offsetTop - slotBase();

    const updateRanks = () => {
        Array.from(list.children).forEach((row, index) => {
            const rank = row.querySelector('.aa-request-rank');
            if (rank) rank.textContent = String(index + 1);
        });
    };

    const animateLayoutChange = (change) => {
        const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const movable = () => Array.from(list.children).filter((row) => !row.classList.contains('aa-dragging'));
        const before = new Map(movable().map((row) => [row, row.getBoundingClientRect().top]));
        change();
        if (reduceMotion) return;
        const moved = [];
        for (const row of movable()) {
            const previous = before.get(row);
            if (previous === undefined) continue;
            const delta = previous - row.getBoundingClientRect().top;
            if (!delta) continue;
            row.style.transition = 'none';
            row.style.transform = `translateY(${delta}px)`;
            moved.push(row);
        }
        if (!moved.length) return;
        list.getBoundingClientRect();
        requestAnimationFrame(() => {
            for (const row of moved) { row.style.transition = ''; row.style.transform = ''; }
        });
    };

    const sendChange = () => {
        api().setTriggerValue('rows_change', {
            order_ids: Array.from(list.children).map((row) => row.dataset.requestId),
            selected_ids: Array.from(list.querySelectorAll('.aa-request-check:checked'))
                .map((checkbox) => checkbox.closest('.aa-request-row').dataset.requestId),
        });
    };

    const announce = (row) => {
        const index = Array.from(list.children).indexOf(row) + 1;
        const name = row.querySelector('.aa-request-name');
        status.textContent = `${name ? name.textContent : 'Request'} moved to position ${index} of ${list.children.length}`;
    };

    const settle = (row) => {
        row.classList.remove('aa-settled');
        void row.offsetWidth;
        row.classList.add('aa-settled');
        window.setTimeout(() => row.classList.remove('aa-settled'), 520);
    };

    const moveRow = (row, direction) => {
        const sibling = direction < 0 ? row.previousElementSibling : row.nextElementSibling;
        if (!sibling) return;
        animateLayoutChange(() => {
            if (direction < 0) list.insertBefore(row, sibling);
            else list.insertBefore(sibling, row);
        });
        updateRanks();
        announce(row);
        host.__aaFocusId = row.dataset.requestId;
        row.querySelector('.aa-drag-handle')?.focus({ preventScroll: true });
        sendChange();
    };

    const updateDrag = (clientY) => {
        if (!drag) return;
        drag.lastY = clientY;
        const listRect = list.getBoundingClientRect();
        const rowHeight = drag.row.offsetHeight;
        const rawTop = clientY - listRect.top - drag.grabOffset;
        const center = rawTop + rowHeight / 2;
        let reference = null;
        for (const other of list.children) {
            if (other === drag.row) continue;
            if (center < slotTop(other) + other.offsetHeight / 2) { reference = other; break; }
        }
        if (reference !== drag.row.nextElementSibling) {
            animateLayoutChange(() => list.insertBefore(drag.row, reference));
            drag.moved = true;
            updateRanks();
        }
        const top = Math.max(-rowHeight * 0.5, Math.min(rawTop, list.offsetHeight - rowHeight * 0.5));
        drag.row.style.setProperty('--aa-drag-y', `${top - slotTop(drag.row)}px`);
    };

    const autoScroll = () => {
        if (!drag) return;
        const scroller = drag.scroller;
        const bounds = (scroller === document.scrollingElement || scroller === document.documentElement)
            ? { top: 0, bottom: window.innerHeight }
            : scroller.getBoundingClientRect();
        const edge = 56;
        let speed = 0;
        if (drag.lastY < bounds.top + edge) speed = -Math.ceil((bounds.top + edge - drag.lastY) / 4);
        else if (drag.lastY > bounds.bottom - edge) speed = Math.ceil((drag.lastY - (bounds.bottom - edge)) / 4);
        if (speed) {
            scroller.scrollTop += Math.max(-24, Math.min(24, speed));
            updateDrag(drag.lastY);
        }
        drag.raf = requestAnimationFrame(autoScroll);
    };

    const onPointerMove = (event) => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        if (event.pointerType === 'mouse' && event.buttons === 0) { endDrag(true); return; }
        event.preventDefault();
        updateDrag(event.clientY);
    };
    const onPointerUp = (event) => { if (drag && event.pointerId === drag.pointerId) endDrag(true); };
    const onPointerCancel = (event) => { if (drag && event.pointerId === drag.pointerId) endDrag(false); };
    const onAbort = () => endDrag(false);
    const onKeyDown = (event) => {
        if (event.key === 'Escape') { event.preventDefault(); endDrag(false); }
    };
    const onVisibility = () => { if (document.hidden) endDrag(false); };

    const attach = () => {
        window.addEventListener('pointermove', onPointerMove, { capture: true, passive: false });
        window.addEventListener('pointerup', onPointerUp, true);
        window.addEventListener('pointercancel', onPointerCancel, true);
        window.addEventListener('keydown', onKeyDown, true);
        window.addEventListener('blur', onAbort);
        window.addEventListener('contextmenu', onAbort, true);
        document.addEventListener('visibilitychange', onVisibility);
    };
    const detach = () => {
        window.removeEventListener('pointermove', onPointerMove, true);
        window.removeEventListener('pointerup', onPointerUp, true);
        window.removeEventListener('pointercancel', onPointerCancel, true);
        window.removeEventListener('keydown', onKeyDown, true);
        window.removeEventListener('blur', onAbort);
        window.removeEventListener('contextmenu', onAbort, true);
        document.removeEventListener('visibilitychange', onVisibility);
    };

    function endDrag(commit) {
        if (!drag) return;
        const finished = drag;
        drag = null;
        cancelAnimationFrame(finished.raf);
        detach();
        document.documentElement.classList.remove('aa-dragging-global');
        try {
            if (finished.handle.hasPointerCapture(finished.pointerId)) {
                finished.handle.releasePointerCapture(finished.pointerId);
            }
        } catch (_) {}
        finished.row.classList.remove('aa-dragging');
        finished.row.style.removeProperty('--aa-drag-y');
        for (const row of list.children) {
            row.classList.remove('aa-drop-target');
            row.style.transition = '';
            if (row !== finished.row) row.style.transform = '';
        }
        if (!commit) {
            animateLayoutChange(() => { for (const row of finished.startOrder) list.appendChild(row); });
            updateRanks();
        } else if (finished.moved) {
            settle(finished.row);
            announce(finished.row);
            sendChange();
        }
    }

    for (const item of rows) {
        const row = document.createElement('div');
        row.className = 'aa-request-row';
        row.setAttribute('role', 'listitem');
        row.dataset.requestId = item.id;

        const handle = document.createElement('button');
        handle.type = 'button';
        handle.className = 'aa-drag-handle';
        handle.title = 'Drag to reorder (Alt+Up / Alt+Down with the keyboard)';
        handle.setAttribute('aria-label', `Reorder ${item.name || item.id}`);
        handle.innerHTML = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="6" cy="4" r="1.2" fill="currentColor"/><circle cx="12" cy="4" r="1.2" fill="currentColor"/><circle cx="6" cy="9" r="1.2" fill="currentColor"/><circle cx="12" cy="9" r="1.2" fill="currentColor"/><circle cx="6" cy="14" r="1.2" fill="currentColor"/><circle cx="12" cy="14" r="1.2" fill="currentColor"/></svg>';
        handle.addEventListener('keydown', (event) => {
            if (event.altKey && event.key === 'ArrowUp') { event.preventDefault(); moveRow(row, -1); }
            if (event.altKey && event.key === 'ArrowDown') { event.preventDefault(); moveRow(row, 1); }
        });
        row.appendChild(handle);

        const rank = document.createElement('span');
        rank.className = 'aa-request-rank';
        rank.setAttribute('aria-hidden', 'true');
        row.appendChild(rank);

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
            if (event.pointerType === 'mouse' && event.button !== 0) return;
            event.preventDefault();
            if (drag) endDrag(false);
            const rect = row.getBoundingClientRect();
            drag = {
                row, handle, pointerId: event.pointerId,
                grabOffset: event.clientY - rect.top,
                startOrder: Array.from(list.children),
                moved: false, lastY: event.clientY, raf: 0,
                scroller: getScrollParent(list),
            };
            row.classList.add('aa-dragging');
            document.documentElement.classList.add('aa-dragging-global');
            attach();
            try { handle.setPointerCapture(event.pointerId); } catch (_) {}
            drag.raf = requestAnimationFrame(autoScroll);
        });
        handle.addEventListener('lostpointercapture', (event) => {
            if (drag && drag.handle === handle && event.pointerId === drag.pointerId) endDrag(true);
        });
        list.appendChild(row);
    }
    updateRanks();

    if (host.__aaFocusId) {
        const target = Array.from(list.children).find((row) => row.dataset.requestId === host.__aaFocusId);
        target?.querySelector('.aa-drag-handle')?.focus({ preventScroll: true });
        host.__aaFocusId = null;
    }

    return () => {
        if (drag) endDrag(false);
        if (host.__aaCurlTimer) window.clearTimeout(host.__aaCurlTimer);
        host.__aaCurlTimer = null;
        document.documentElement.classList.remove('aa-dragging-global');
    };
}
"""


_request_controls = st.components.v2.component(
    "api_agent_request_controls_v2",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def render_curl_aware_url(value: str, instance_key: str, sync_key: str = ''):
    """Render the URL editor with debounced cURL detection.

    Args:
        value (str): Current URL or pasted cURL text.
        instance_key (str): Stable request-tab identifier.
        sync_key (str): Changes when the application intentionally replaces the URL.

    Returns:
        ComponentResult: Current text and an optional debounced cURL trigger.
    """
    return _request_controls(
        data={
            "mode": "url", "value": value,
            "instance_key": instance_key, "sync_key": sync_key,
        },
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
