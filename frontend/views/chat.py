# frontend/views/chat.py

"""
Project Chat view: persistent conversations and the versioned Knowledge Hub.

The rail keeps every persisted conversation in reach: search, an active/archived
filter, and one action menu per thread. The transcript aligns muted assistant
bubbles left and accent-tinted user bubbles right, with local timestamps above
each message. Long content can collapse, and sources stay attached to their
answer. Knowledge updates are explicit drafts reviewed before saving.
"""

from datetime import datetime
import difflib
import html
import json
import re

import streamlit as st

from frontend.core import (
    _load_project_chat_thread,
    api_delete,
    api_get,
    api_post,
    api_put,
)

FILTERS = ("Active", "All", "Archived")
COLLAPSIBLE_MESSAGE_CHARS = 900


def _short_time(value: str | None) -> str:
    """Trim an ISO timestamp to its date and minute.

    Args:
        value (str | None): Stored timestamp.

    Returns:
        str: ``YYYY-MM-DD HH:MM``, or an empty string when unparseable.
    """
    text = str(value or "").replace("T", " ")
    return text[:16] if len(text) >= 16 else text


def _local_message_time(value: str | None) -> str:
    """Format a persisted message timestamp in the frontend host's local time.

    Naive timestamps are already stored in the application's local timezone;
    timezone-aware values are converted to the host's local timezone first.

    Args:
        value (str | None): ISO timestamp returned with a chat message.

    Returns:
        str: Readable local date and time, or the original short value.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%b %d, %Y · %I:%M %p").replace(" 0", " ")
    except (TypeError, ValueError):
        return _short_time(raw)


def _scroll_to_chat_message(target_key: str) -> None:
    """Bring a newly rendered assistant reply into the viewport.

    Args:
        target_key (str): Streamlit container key for the assistant bubble.

    Returns:
        None: Emits a small same-page script that scrolls the bubble into view.
    """
    target_class = json.dumps(f"st-key-{target_key}")
    st.html(
        f"""<script>
        (() => {{
            const targetClass = {target_class};
            let attempts = 0;
            const revealReply = () => {{
                const target = document.getElementsByClassName(targetClass)[0];
                if (target) {{
                    target.scrollIntoView({{ behavior: "smooth", block: "center" }});
                }} else if (attempts++ < 12) {{
                    window.setTimeout(revealReply, 80);
                }}
            }};
            window.requestAnimationFrame(revealReply);
        }})();
        </script>""",
        unsafe_allow_javascript=True,
        width="stretch",
    )


def _render_sources(sources: list) -> None:
    """Render the endpoints an assistant answer was grounded in.

    Args:
        sources (list): Endpoint source records from the message.

    Returns:
        None: Writes one disclosure with a row per source.
    """
    usable = [item for item in sources if isinstance(item, dict)]
    if not usable:
        return
    with st.expander(f"Sources - {len(usable)} endpoint(s)", expanded=False):
        for item in usable:
            method = str(item.get("method") or "GET").upper()
            st.markdown(f":blue-badge[{method}] **{item.get('name') or 'Untitled endpoint'}**")
            st.caption(
                f"{item.get('collection_name') or 'Unassigned collection'} - "
                f"{item.get('url') or 'No URL recorded'}"
            )


def _render_knowledge_sources(sources: list) -> None:
    """Show current Knowledge Hub pages attached to an assistant reply."""
    usable = [item for item in sources if isinstance(item, dict)]
    if not usable:
        return
    with st.expander(f"Project knowledge · {len(usable)} source(s)", expanded=False):
        for item in usable:
            if item.get("kind") == "open_question":
                st.markdown(f"**Open question:** {item.get('question')}")
            elif item.get("kind") == "knowledge_hub_page":
                st.markdown(f"**{item.get('title') or 'Knowledge Hub page'}** · {item.get('status') or 'current'}")
                st.caption(str(item.get("content") or "")[:500])
            else:
                st.markdown(f"**{item.get('title') or 'Reviewed fact'}** · {item.get('status', 'reviewed')}")
                st.caption(f"{item.get('content') or ''} · Fact ID {item.get('id')}")


def _render_github_diff(diff_text: str) -> None:
    """Render a unified diff with GitHub-like line colors and gutters.

    Args:
        diff_text (str): Unified diff text for one Markdown section.

    Returns:
        None: Writes escaped diff markup with separate added and removed rows.
    """
    rows = []
    old_line = new_line = None
    for line in str(diff_text or "").splitlines():
        if line.startswith("@@"):
            match = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            old_line = int(match.group(1)) if match else None
            new_line = int(match.group(2)) if match else None
            rows.append(("hunk", "", "", line))
            continue
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("\\ No newline"):
            continue
        if line.startswith("+"):
            rows.append(("add", "", str(new_line) if new_line is not None else "", line[1:]))
            if new_line is not None:
                new_line += 1
        elif line.startswith("-"):
            rows.append(("remove", str(old_line) if old_line is not None else "", "", line[1:]))
            if old_line is not None:
                old_line += 1
        else:
            content = line[1:] if line.startswith(" ") else line
            rows.append(("context", str(old_line) if old_line is not None else "",
                         str(new_line) if new_line is not None else "", content))
            if old_line is not None:
                old_line += 1
            if new_line is not None:
                new_line += 1

    if not rows:
        st.caption("No changes in this section.")
        return

    rendered = []
    for kind, old_number, new_number, text in rows:
        escaped = html.escape(text)
        if kind == "hunk":
            rendered.append(
                '<div style="padding:4px 10px;background:#ddf4ff;color:#59636e;'
                'border-top:1px solid #b6e3ff;border-bottom:1px solid #b6e3ff;">'
                f"{escaped}</div>"
            )
            continue
        background = {"add": "#e6ffec", "remove": "#ffebe9", "context": "#ffffff"}[kind]
        marker_color = {"add": "#1a7f37", "remove": "#cf222e", "context": "#6e7781"}[kind]
        marker = "+" if kind == "add" else "−" if kind == "remove" else " "
        rendered.append(
            f'<div style="display:grid;grid-template-columns:3.5em 3.5em 1.5em minmax(0,1fr);'
            f'background:{background};font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;">'
            f'<span style="padding:0 7px;text-align:right;color:#8c959f;border-right:1px solid #d0d7de;">{old_number}</span>'
            f'<span style="padding:0 7px;text-align:right;color:#8c959f;border-right:1px solid #d0d7de;">{new_number}</span>'
            f'<span style="padding:0 5px;color:{marker_color};font-weight:700;">{marker}</span>'
            f'<span style="padding:0 8px;white-space:pre-wrap;overflow-wrap:anywhere;">{escaped}</span>'
            '</div>'
        )
    st.markdown(
        '<div style="overflow-x:auto;border:1px solid #d0d7de;border-radius:6px;">'
        + "".join(rendered) + "</div>",
        unsafe_allow_html=True,
    )


@st.dialog("Delete conversation?")
def _delete_chat_thread_dialog(project_id: str, thread_id: str, title: str) -> None:
    """Confirm permanent deletion of a project-owned conversation.

    Args:
        project_id (str): Project that owns the thread.
        thread_id (str): Thread selected for deletion.
        title (str): Human-readable thread title for confirmation.

    Returns:
        None: Deletes the thread after explicit confirmation.
    """
    st.write(f"Delete **{title or 'Untitled conversation'}** and its messages permanently?")
    st.caption("This does not delete Knowledge Hub pages or generation activity records.")
    cancel_col, delete_col = st.columns(2)
    if cancel_col.button("Cancel", key=f"chat_delete_cancel_{project_id}_{thread_id}", width="stretch"):
        return
    if delete_col.button(
        "Delete conversation", key=f"chat_delete_confirm_{project_id}_{thread_id}",
        type="primary", width="stretch",
    ):
        try:
            api_delete(f"/api/v1/projects/{project_id}/chat/threads/{thread_id}")
            st.session_state.pop(f"project_chat_thread_data_{project_id}", None)
            selected_key = f"project_chat_selected_thread_{project_id}"
            if st.session_state.get(selected_key) == thread_id:
                st.session_state[selected_key] = ""
            st.rerun()
        except Exception as exc:
            st.error(f"Could not delete conversation: {exc}")


def _render_conversation(project_id: str, thread: dict) -> None:
    """Render one transcript and its composer.

    Args:
        project_id (str): Project that owns the conversation.
        thread (dict): Thread record holding ordered messages.

    Returns:
        None: Writes the transcript and, when the thread is active, the composer.
    """
    thread_id = str(thread.get("id") or "")
    messages = thread.get("messages") or []
    scroll_state_key = f"chat_scroll_target_{project_id}_{thread_id}"
    scroll_target_key = st.session_state.get(scroll_state_key)
    with st.container(key="project-chat-transcript"):
        if not messages:
            st.caption(
                "Describe a feature, a user journey, an integration, or a requirement gap. "
                "The assistant can ask follow-up questions to clarify the product context."
            )
        for index, message in enumerate(messages, start=1):
            role = "user" if message.get("role") == "user" else "assistant"
            content = str(message.get("content") or "")
            stamp = _local_message_time(message.get("created_at"))
            with st.container(key=f"chat-time-{role}-{thread_id}-{index}"):
                if stamp:
                    st.caption(stamp)
            with st.container(key=f"chat-bubble-{role}-{thread_id}-{index}"):
                if len(content) > COLLAPSIBLE_MESSAGE_CHARS:
                    with st.expander(
                        "Expand or collapse message", expanded=True,
                        key=f"chat-message-content-{thread_id}-{index}",
                    ):
                        st.markdown(content)
                else:
                    st.markdown(content)
                provider_metadata = message.get("provider_metadata") or {}
                if role == "assistant" and provider_metadata:
                    st.caption(
                        f"{provider_metadata.get('provider') or 'LLM'} · "
                        f"{provider_metadata.get('model') or 'unknown model'}"
                    )
                _render_knowledge_sources(message.get("knowledge_sources") or [])
                _render_sources(message.get("endpoint_sources") or [])

    if scroll_target_key:
        _scroll_to_chat_message(str(scroll_target_key))
        st.session_state.pop(scroll_state_key, None)

    if thread.get("archived"):
        st.info("This conversation is archived. Restore it from the rail to continue.")
        return

    with st.container(key=f"project-chat-composer-{project_id}"):
        prompt = st.chat_input(
            "Message about this project",
            key=f"chat_composer_{project_id}_{thread_id}",
        )
    if not prompt:
        return
    with st.status("Thinking with project context", expanded=False) as status:
        try:
            response = api_post(
                f"/api/v1/projects/{project_id}/chat/threads/{thread_id}/messages",
                {"content": prompt},
            )
            updated_thread = response.get("thread") or {}
            st.session_state[f"project_chat_thread_data_{project_id}"] = updated_thread
            st.session_state[f"project_chat_selected_thread_{project_id}"] = thread_id
            updated_messages = updated_thread.get("messages") or []
            if updated_messages and updated_messages[-1].get("role") == "assistant":
                assistant_index = len(updated_messages)
                st.session_state[scroll_state_key] = (
                    f"chat-bubble-assistant-{thread_id}-{assistant_index}"
                )
            status.update(label="Reply received.", state="complete")
        except Exception as exc:
            status.update(label="Could not send the message.", state="error")
            st.error(f"Could not send message: {exc}")
            return
    st.rerun()


def _render_knowledge_hub(project_id: str, thread: dict | None) -> None:
    """Manage versioned knowledge pages and review explicit chat-based updates."""
    try:
        pages = api_get(f"/api/v1/projects/{project_id}/knowledge-hub/pages") or []
    except Exception as exc:
        st.error(f"Could not load the Knowledge Hub: {exc}")
        return
    if not pages:
        st.info("The project Knowledge Hub is not available yet.")
        return
    page_by_id = {str(item["id"]): item for item in pages if item.get("id")}
    page_ids = list(page_by_id)
    overview = next((item for item in pages if item.get("scope_type") == "project"), None)
    selection_key = f"hub_page_{project_id}"
    pending = st.session_state.pop(f"{selection_key}_pending", None)
    if pending in page_by_id:
        st.session_state[selection_key] = pending
    if st.session_state.get(selection_key) not in page_by_id:
        st.session_state[selection_key] = str((overview or pages[0])["id"])

    left, right = st.columns([1, 3], gap="large")
    with left:
        st.markdown("#### Knowledge pages")
        with st.popover("Add feature or microservice", icon=":material/add:", width="stretch"):
            new_type = st.selectbox("Page type", ["feature", "microservice"], key=f"hub_new_type_{project_id}")
            new_name = st.text_input("Name", key=f"hub_new_name_{project_id}", placeholder="e.g. Restaurant billing")
            if st.button("Create page", key=f"hub_create_{project_id}", type="primary", disabled=not new_name.strip()):
                try:
                    created = api_post(f"/api/v1/projects/{project_id}/knowledge-hub/pages", {
                        "scope_type": new_type, "name": new_name.strip(),
                    })
                    st.session_state[f"{selection_key}_pending"] = created["id"]
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not create page: {exc}")
        st.radio(
            "Project, features, and microservices", page_ids, key=selection_key,
            format_func=lambda value: (
                f"{page_by_id[value].get('name') or 'Untitled'} · "
                f"{str(page_by_id[value].get('scope_type') or 'feature').title()}"
            ),
            label_visibility="collapsed",
        )

    selected_id = str(st.session_state[selection_key])
    page = page_by_id[selected_id]
    with right:
        st.markdown(f"### {page.get('name') or 'Knowledge page'}")
        version_number = page.get("current_version_number") or 0
        page_type = str(page.get("scope_type") or "feature")
        st.caption(
            "Project-wide context · included in every generation" if page_type == "project"
            else f"{page_type.title()} knowledge · current version v{version_number}"
        )
        if page_type == "feature":
            services = [item for item in pages if item.get("scope_type") == "microservice"]
            if services:
                service_ids = [str(item["id"]) for item in services]
                link_key = f"hub_services_{project_id}_{selected_id}"
                st.session_state.setdefault(link_key, [
                    value for value in page.get("microservice_scope_ids", []) if value in service_ids
                ])
                selected_services = st.multiselect(
                    "Microservices used by this feature", service_ids, key=link_key,
                    format_func=lambda value: page_by_id[value].get("name") or "Microservice",
                    help="A feature may use several microservices. A microservice can be shared by multiple features.",
                )
                if st.button("Save service links", key=f"hub_service_save_{project_id}_{selected_id}"):
                    try:
                        api_put(
                            f"/api/v1/projects/{project_id}/knowledge-hub/features/{selected_id}/microservices",
                            {"microservice_scope_ids": selected_services},
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save service links: {exc}")

        content = str(page.get("current_content") or "")
        st.markdown("#### Current page")
        with st.container(height=320, border=True):
            if content:
                st.markdown(content)
            else:
                st.caption("This page has no saved knowledge yet. Discuss the topic in chat, then prepare an update for this page.")

        if thread and not thread.get("archived"):
            targets_key = f"hub_draft_targets_{project_id}_{thread.get('id')}"
            st.multiselect(
                "Pages to update from this conversation", page_ids, key=targets_key,
                default=[selected_id],
                format_func=lambda value: f"{page_by_id[value].get('name')} · {page_by_id[value].get('scope_type')}",
                help="Each page gets a separate draft and change comparison. Nothing is saved until you review and confirm.",
            )
            if st.button(
                "Prepare knowledge update", key=f"hub_prepare_{project_id}_{thread.get('id')}",
                type="primary", disabled=not st.session_state.get(targets_key),
            ):
                try:
                    with st.spinner("Preparing Knowledge Hub changes from this conversation…"):
                        response = api_post(
                            f"/api/v1/projects/{project_id}/chat/threads/{thread['id']}/knowledge-draft",
                            {"scope_ids": st.session_state[targets_key]},
                        )
                    previous_drafts = st.session_state.get(f"hub_draft_{project_id}") or {}
                    for previous in previous_drafts.get("pages", []):
                        previous_id = str(previous.get("scope_id") or "")
                        st.session_state.pop(f"hub_draft_editor_{project_id}_{previous_id}", None)
                        st.session_state.pop(f"hub_draft_include_{project_id}_{previous_id}", None)
                    st.session_state[f"hub_draft_{project_id}"] = response
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not prepare the update: {exc}")
        else:
            st.caption("Select an active chat thread to prepare a knowledge update from its discussion.")

        draft_key = f"hub_draft_{project_id}"
        draft_set = st.session_state.get(draft_key)
        if draft_set:
            drafts = [item for item in draft_set.get("pages", []) if item.get("scope_id") in page_by_id]
            if drafts:
                st.divider()
                st.markdown("#### Review proposed changes")
                st.caption("Review each page and its section changes. Confirmed knowledge can be saved with uncertain details under Open questions.")
                with st.container(height=560, border=True):
                    for draft in drafts:
                        scope_id = str(draft["scope_id"])
                        title = f"{page_by_id[scope_id].get('name')} · {str(page_by_id[scope_id].get('scope_type')).title()}"
                        with st.expander(title, expanded=True):
                            save_key = f"hub_draft_include_{project_id}_{scope_id}"
                            st.checkbox("Include this page in the update", value=True, key=save_key)
                            for section in draft.get("section_diffs", []):
                                st.markdown(f"**{section.get('section') or 'Section'}**")
                                _render_github_diff(section.get("diff") or "")
                            editor_key = f"hub_draft_editor_{project_id}_{scope_id}"
                            edit_tab, preview_tab = st.tabs(["Edit", "Preview"])
                            with edit_tab:
                                st.text_area("Edit proposed page content", draft.get("draft", ""), height=260, key=editor_key)
                            with preview_tab:
                                preview_content = st.session_state.get(editor_key, draft.get("draft", ""))
                                if preview_content.strip():
                                    st.markdown(preview_content)
                                else:
                                    st.caption("Markdown preview will appear here as you edit the page.")
                            st.caption("Keep uncertain or conflicting details in a clearly labeled Open questions section.")
                to_save = [
                    {"scope_id": str(item["scope_id"]),
                     "content": st.session_state.get(f"hub_draft_editor_{project_id}_{item['scope_id']}", item.get("draft", ""))}
                    for item in drafts
                    if st.session_state.get(f"hub_draft_include_{project_id}_{item['scope_id']}", True)
                ]
                save_col, discard_col = st.columns([1, 1])
                if save_col.button("Save selected page versions", type="primary", key=f"hub_save_update_{project_id}", disabled=not to_save):
                    try:
                        api_post(f"/api/v1/projects/{project_id}/knowledge-hub/updates", {
                            "source_thread_id": draft_set.get("source_thread_id"),
                            "draft_event_id": draft_set.get("draft_event_id"),
                            "pages": to_save,
                        })
                        st.session_state.pop(draft_key, None)
                        for item in drafts:
                            st.session_state.pop(f"hub_draft_editor_{project_id}_{item['scope_id']}", None)
                            st.session_state.pop(f"hub_draft_include_{project_id}_{item['scope_id']}", None)
                            st.session_state.pop(f"hub_versions_{project_id}_{item['scope_id']}", None)
                        st.success("Knowledge Hub versions saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save the Knowledge Hub update: {exc}")
                if discard_col.button("Discard drafts", key=f"hub_discard_update_{project_id}"):
                    st.session_state.pop(draft_key, None)
                    st.rerun()

        history_key = f"hub_versions_{project_id}_{selected_id}"
        with st.expander("Version history and changes", expanded=False):
            if st.button("Refresh version history", key=f"hub_refresh_versions_{project_id}_{selected_id}"):
                st.session_state.pop(history_key, None)
            if history_key not in st.session_state:
                try:
                    st.session_state[history_key] = api_get(
                        f"/api/v1/projects/{project_id}/knowledge-hub/pages/{selected_id}/versions"
                    ) or []
                except Exception as exc:
                    st.error(f"Could not load page history: {exc}")
                    st.session_state[history_key] = None
            cached_versions = st.session_state.get(history_key)
            versions = sorted(cached_versions or [], key=lambda item: int(item.get("version_number") or 0))
            if versions:
                for index, version in enumerate(versions):
                    current = bool(version.get("is_current"))
                    label = f"v{version.get('version_number', '?')}" + (" · Current" if current else "")
                    with st.expander(label, expanded=False):
                        st.caption(f"{version.get('created_at', '')}" + (f" · Source chat {version.get('source_thread_id')}" if version.get("source_thread_id") else ""))
                        st.markdown(str(version.get("content") or ""))
                        if index > 0:
                            prior_content = str(versions[index - 1].get("content") or "")
                            change = "\n".join(difflib.unified_diff(
                                prior_content.splitlines(), str(version.get("content") or "").splitlines(),
                                fromfile=f"v{versions[index - 1].get('version_number')}",
                                tofile=f"v{version.get('version_number')}", lineterm="",
                            ))
                            with st.expander("Changes from previous version", expanded=False):
                                _render_github_diff(change)
                        if not current and st.button("Restore as new version", key=f"hub_restore_{project_id}_{selected_id}_{version['id']}"):
                            try:
                                api_post(
                                    f"/api/v1/projects/{project_id}/knowledge-hub/pages/{selected_id}/versions/{version['id']}/restore", {},
                                )
                                st.session_state.pop(history_key, None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not restore version: {exc}")
            elif st.session_state.get(history_key) is not None:
                st.caption("No saved versions are available for this page yet.")

def render_project_chat_tab() -> None:
    """Render the conversation rail, transcript, and versioned Knowledge Hub."""
    project = st.session_state.get("current_project") or {}
    project_id = str(project.get("id") or "")
    if not project_id:
        st.header("Project Chat")
        st.info("Select or create a project to start a project chat.")
        return

    st.header("Project Chat")
    st.caption(
        "Discuss product behavior and requirements against the project context, "
        "then prepare and review explicit updates to durable project knowledge."
    )

    selected_key = f"project_chat_selected_thread_{project_id}"
    search_key = f"chat_search_{project_id}"
    # A new key gives existing Streamlit sessions the new Active-first default
    # instead of retaining a prior "All" selection across a hot reload.
    filter_key = f"chat_filter_active_default_{project_id}"
    if st.session_state.get(filter_key) not in FILTERS:
        st.session_state[filter_key] = "Active"

    try:
        threads = api_get(f"/api/v1/projects/{project_id}/chat/threads?include_archived=true") or []
    except Exception as exc:
        st.error(f"Could not load chats: {exc}")
        return

    query = str(st.session_state.get(search_key) or "").strip().casefold()
    choice = st.session_state.get(filter_key)
    visible = []
    for item in threads:
        archived = bool(item.get("archived"))
        if choice == "Active" and archived:
            continue
        if choice == "Archived" and not archived:
            continue
        if query and query not in str(item.get("title") or "").casefold():
            continue
        visible.append(item)

    selected_id = str(st.session_state.get(selected_key) or "")
    visible_ids = {str(item.get("id") or "") for item in visible}
    if selected_id not in visible_ids:
        selected_id = str(visible[0].get("id") or "") if visible else ""
        st.session_state[selected_key] = selected_id
        cached_thread = st.session_state.get(f"project_chat_thread_data_{project_id}") or {}
        if str(cached_thread.get("id") or "") != selected_id:
            st.session_state.pop(f"project_chat_thread_data_{project_id}", None)
    rail, main = st.columns([1.0, 3.3], gap="large")

    with rail:
        if st.button(
            "New conversation", icon=":material/add:", type="primary",
            width="stretch", key=f"chat_new_{project_id}",
        ):
            try:
                created = api_post(
                    f"/api/v1/projects/{project_id}/chat/threads",
                    {"title": "New project chat"},
                )
                _load_project_chat_thread(project_id, str(created["id"]))
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create chat: {exc}")
        st.text_input(
            "Search", key=search_key, placeholder="Search conversations",
            label_visibility="collapsed",
        )
        st.segmented_control(
            "Filter", list(FILTERS), key=filter_key, label_visibility="collapsed",
            width="stretch",
        )
        st.caption(f"{len(visible)} of {len(threads)} conversation(s)")

        for item in visible:
            thread_id = str(item.get("id") or "")
            active = thread_id == selected_id
            count = len(item.get("messages") or [])
            title_col, menu_col = st.columns([4.4, 0.7], vertical_alignment="center")
            if title_col.button(
                str(item.get("title") or "Untitled chat"),
                key=f"chat_open_{project_id}_{thread_id}",
                type="primary" if active else "secondary",
                width="stretch",
                help=f"{count} message(s)" + (" - archived" if item.get("archived") else ""),
            ):
                try:
                    _load_project_chat_thread(project_id, thread_id)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not open chat: {exc}")
            with menu_col:
                with st.popover(" ", icon=":material/more_vert:", help="Conversation actions"):
                    new_title = st.text_input(
                        "Title", value=str(item.get("title") or ""),
                        key=f"chat_title_input_{project_id}_{thread_id}",
                    )
                    if st.button(
                        "Rename", icon=":material/edit:", width="stretch",
                        key=f"chat_rename_{project_id}_{thread_id}",
                        disabled=not new_title.strip(),
                    ):
                        try:
                            api_put(
                                f"/api/v1/projects/{project_id}/chat/threads/{thread_id}",
                                {"title": new_title.strip()},
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not rename chat: {exc}")
                    archived = bool(item.get("archived"))
                    if st.button(
                        "Restore" if archived else "Archive",
                        key=f"chat_archive_{project_id}_{thread_id}",
                        icon=":material/unarchive:" if archived else ":material/archive:",
                        width="stretch",
                    ):
                        try:
                            api_put(
                                f"/api/v1/projects/{project_id}/chat/threads/{thread_id}",
                                {"archived": not archived},
                            )
                            st.session_state.pop(f"project_chat_thread_data_{project_id}", None)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not update chat: {exc}")
                    st.divider()
                    if st.button(
                        "Delete conversation", key=f"chat_delete_{project_id}_{thread_id}",
                        icon=":material/delete:", width="stretch",
                    ):
                        _delete_chat_thread_dialog(
                            project_id, thread_id, str(item.get("title") or "Untitled conversation")
                        )

    with main:
        thread = st.session_state.get(f"project_chat_thread_data_{project_id}")
        if selected_id and (not thread or str(thread.get("id")) != selected_id):
            try:
                _load_project_chat_thread(project_id, selected_id)
                thread = st.session_state.get(f"project_chat_thread_data_{project_id}")
            except Exception as exc:
                st.error(f"Could not load chat history: {exc}")
                thread = None
        if not thread:
            view_key = f"chat_view_{project_id}"
            if st.session_state.get(view_key) not in {"Conversation", "Knowledge Hub"}:
                st.session_state[view_key] = "Conversation"
            view = st.segmented_control(
                "View", ["Conversation", "Knowledge Hub"], key=view_key,
                label_visibility="collapsed", width="stretch",
            ) or "Conversation"
            if view == "Knowledge Hub":
                _render_knowledge_hub(project_id, None)
            else:
                st.caption("Select a conversation on the left, or start one to discuss product context.")
            return

        title = str(thread.get("title") or "Project chat")
        messages = thread.get("messages") or []
        st.markdown(f"### {title}")
        chips = [f":gray-badge[{len(messages)} message(s)]"]
        if thread.get("model"):
            chips.append(f":gray-badge[{thread.get('model')}]")
        if thread.get("archived"):
            chips.append(":gray-badge[Archived]")
        st.markdown(" ".join(chips))

        view_key = f"chat_view_{project_id}"
        if st.session_state.get(view_key) not in {"Conversation", "Knowledge Hub"}:
            st.session_state[view_key] = "Conversation"
        view = st.segmented_control(
            "View", ["Conversation", "Knowledge Hub"], key=view_key,
            label_visibility="collapsed", width="stretch",
        ) or "Conversation"

        if view == "Conversation":
            _render_conversation(project_id, thread)
            return

        _render_knowledge_hub(project_id, thread)
