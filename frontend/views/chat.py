# frontend/views/chat.py

"""
Project Chat view: a conversation rail, a transcript pane, and the brief workspace.

The rail keeps every persisted conversation in reach: search, an active/archived
filter, and one action menu per thread. The transcript aligns muted assistant
bubbles left and accent-tinted user bubbles right, with local timestamps above
each message. Long content can collapse, and sources stay attached to their
answer. Briefs are a peer view rather than a tab, so the composer is never
displaced by them.
"""

from datetime import datetime
import json

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

def _render_brief_cards(project_id: str, scopes: list) -> None:
    """Render one card per feature or service brief, each opening in a dialog.

    Args:
        project_id (str): Project that owns the briefs.
        scopes (list): Brief scopes other than the project overview.

    Returns:
        None: Writes the cards and their dialogs.
    """
    if not scopes:
        st.caption("No feature or service briefs yet. Add one to give generation focused context.")
        return
    columns = st.columns(2, gap="small")
    for index, scope in enumerate(scopes):
        scope_id = str(scope.get("id") or "")
        version = scope.get("current_version_number") or 1
        excerpt = " ".join(str(scope.get("current_content") or "").split())[:180]
        with columns[index % 2], st.container(border=True):
            st.markdown(f"**{scope.get('name') or 'Untitled brief'}**")
            st.markdown(
                f":gray-badge[{str(scope.get('scope_type') or 'feature').title()}] "
                f":gray-badge[v{version}]"
            )
            st.caption(excerpt or "No saved version yet.")
            opened = st.button(
                "Open", key=f"brief_open_{project_id}_{scope_id}",
                icon=":material/open_in_new:", width="stretch",
            )
        if opened:
            _brief_dialog(project_id, scope)

@st.dialog("Project brief", width="large")
def _brief_dialog(project_id: str, scope: dict) -> None:
    """Edit one brief and manage its version history in a modal.

    Args:
        project_id (str): Project that owns the brief.
        scope (dict): Brief scope record shown in the editor.

    Returns:
        None: Writes the editor: and the history.
    """
    scope_id = str(scope.get("id") or "")
    version = scope.get("current_version_number") or 1
    stored = str(scope.get("current_content") or "")
    st.caption(
        f"{str(scope.get('scope_type') or 'feature').title()} brief, current v{version}. "
        "Saving adds a version and keeps the earlier ones restorable."
    )
    content = st.text_area(
        "Content", value=stored, height=300,
        key=f"brief_edit_{project_id}_{scope_id}",
    )
    dirty = content.strip() != stored.strip()
    if not content.strip():
        st.caption(":orange[The brief is empty, so there is nothing to save.]")
    elif not dirty:
        st.caption(":gray[No changes yet.]")
    saved = st.button(
        f"Save as v{version + 1}", type="primary", icon=":material/save:",
        width="stretch", disabled=not dirty,
        key=f"brief_save_{project_id}_{scope_id}",
    )
    if saved:
        try:
            api_post(
                f"/api/v1/projects/{project_id}/brief-scopes/{scope_id}/versions",
                {"content": content},
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save the brief: {exc}")

    st.divider()
    st.markdown("**Version history**")
    try:
        versions = api_get(
            f"/api/v1/projects/{project_id}/brief-scopes/{scope_id}/versions"
        ) or []
    except Exception as exc:
        st.error(f"Could not load versions: {exc}")
        return
    if not versions:
        st.caption("No versions saved yet.")
        return
    for item in versions:
        current = bool(item.get("is_current"))
        label = f"v{item.get('version_number', '?')} - {_short_time(item.get('created_at'))}"
        with st.expander(label + (" - current" if current else ""), expanded=False):
            st.markdown(str(item.get("content") or ""))
            restore = st.button(
                "Make current",
                key=f"brief_restore_{project_id}_{scope_id}_{item.get('id')}",
                icon=":material/history:", disabled=current,
            )
            if restore:
                try:
                    api_post(
                        f"/api/v1/projects/{project_id}/brief-scopes/{scope_id}"
                        f"/versions/{item.get('id')}/restore",
                        {},
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not restore that version: {exc}")

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
    """Show reviewed fact and unresolved-question citations attached to a reply."""
    usable = [item for item in sources if isinstance(item, dict)]
    if not usable:
        return
    with st.expander(f"Project knowledge · {len(usable)} source(s)", expanded=False):
        for item in usable:
            if item.get("kind") == "open_question":
                st.markdown(f"**Open question:** {item.get('question')}")
            else:
                st.markdown(f"**{item.get('title') or 'Reviewed fact'}** · {item.get('status', 'reviewed')}")
                st.caption(f"{item.get('content') or ''} · Fact ID {item.get('id')}")


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
    st.caption("This does not delete project briefs or generation activity records.")
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
    notice = st.session_state.get(f"knowledge_extraction_notice_{project_id}")
    if notice:
        if notice.get("status") == "failed":
            st.warning("Chat reply is saved, but knowledge extraction needs attention. Open Knowledge to retry.")
        elif notice.get("proposal_count"):
            st.info(f"{notice['proposal_count']} knowledge proposal(s) are ready for review.")
        if st.button("Review in Knowledge", key=f"chat_review_knowledge_{project_id}", icon=":material/rate_review:"):
            st.session_state[f"chat_view_{project_id}"] = "Knowledge"
            st.rerun()
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
                        "Message content", expanded=True,
                        key=f"chat-message-content-{thread_id}-{index}",
                    ):
                        st.markdown(content)
                else:
                    st.markdown(content)
                _render_knowledge_sources(message.get("knowledge_sources") or [])
                _render_sources(message.get("endpoint_sources") or [])

    if thread.get("archived"):
        st.info("This conversation is archived. Restore it from the rail to continue.")
        return

    prompt = st.chat_input(
        "Message about this project",
        key=f"chat_composer_{project_id}_{thread_id}",
    )
    if not prompt:
        return
    with st.status("Thinking with project context and extracting knowledge proposals", expanded=False) as status:
        try:
            response = api_post(
                f"/api/v1/projects/{project_id}/chat/threads/{thread_id}/messages",
                {"content": prompt},
            )
            st.session_state[f"project_chat_thread_data_{project_id}"] = response.get("thread")
            st.session_state[f"project_chat_selected_thread_{project_id}"] = thread_id
            st.session_state[f"knowledge_extraction_notice_{project_id}"] = response.get("knowledge_extraction") or {}
            status.update(label="Reply received.", state="complete")
        except Exception as exc:
            status.update(label="Could not send the message.", state="error")
            st.error(f"Could not send message: {exc}")
            return
    st.rerun()


def _render_knowledge_ledger(project_id: str) -> None:
    """Render source submissions, fact proposals, approved facts, and open questions."""
    try:
        ledger = api_get(f"/api/v1/projects/{project_id}/knowledge/ledger") or {}
        scopes = ledger.get("scopes", [])
    except Exception as exc:
        st.error(f"Could not load project knowledge: {exc}")
        return
    scope_names = {str(item.get("id")): f"{item.get('scope_type', '').title()} · {item.get('name')}" for item in scopes}
    fact_by_id = {str(item.get("id")): item for item in ledger.get("facts", [])}
    scope_ids = list(scope_names)
    overview_scope = next((item for item in scopes if item.get("scope_type") == "project"), None)
    if not scope_ids:
        st.info("Create a project brief scope before adding knowledge.")
        return
    with st.expander("Add source text", expanded=False):
        selected_scope = st.selectbox("Store under", scope_ids, format_func=lambda value: scope_names.get(value, value), key=f"knowledge_scope_{project_id}")
        source_name = st.text_input("Source name", value="Pasted context", key=f"knowledge_source_name_{project_id}")
        source_text = st.text_area("Paste product knowledge", height=180, key=f"knowledge_source_text_{project_id}", placeholder="Paste a requirement, workflow, integration note, or product document.")
        uploaded = st.file_uploader("Or import Markdown or text", type=["md", "txt"], key=f"knowledge_upload_{project_id}")
        if st.button("Extract proposals for review", type="primary", disabled=not (source_text.strip() or uploaded), key=f"knowledge_submit_{project_id}"):
            try:
                content = uploaded.getvalue().decode("utf-8", errors="replace") if uploaded else source_text
                name = uploaded.name if uploaded else source_name
                with st.spinner("Extracting source-linked knowledge proposals…"):
                    result = api_post(f"/api/v1/projects/{project_id}/knowledge/submissions", {"content": content, "source_name": name, "scope_id": selected_scope})
                if result.get("status") == "failed":
                    st.error(f"Extraction failed; source text is retained. {result.get('extraction_error', '')}")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not submit knowledge source: {exc}")

    notice_key = f"knowledge_extraction_notice_{project_id}"
    notice = st.session_state.get(notice_key)
    if notice:
        if notice.get("status") == "failed":
            st.warning(f"Chat was saved, but knowledge extraction failed: {notice.get('error', 'Unknown error')}")
            if notice.get("submission_id") and st.button("Retry extraction", key=f"knowledge_retry_chat_{project_id}_{notice['submission_id']}"):
                try:
                    api_post(f"/api/v1/projects/{project_id}/knowledge/submissions/{notice['submission_id']}/retry", {})
                    st.rerun()
                except Exception as exc: st.error(f"Retry failed: {exc}")
        elif notice.get("proposal_count"):
            st.success(f"Chat saved. {notice['proposal_count']} knowledge proposal(s) are ready for review below.")
        else:
            st.caption("Chat saved. No durable fact proposals were extracted from that turn.")
        if st.button("Dismiss extraction notice", key=f"knowledge_notice_dismiss_{project_id}"):
            st.session_state.pop(notice_key, None)
            st.rerun()

    st.subheader("Review queue")
    submissions = [item for item in ledger.get("submissions", []) if item.get("status") in {"pending_review", "failed"}]
    if not submissions:
        st.caption("No submissions are waiting for review.")
    for submission in submissions:
        label = f"{submission.get('source_name') or 'Source'} · {submission.get('status')} · {_short_time(submission.get('created_at'))}"
        with st.expander(label, expanded=submission.get("status") == "pending_review"):
            st.caption(f"Scope: {scope_names.get(str(submission.get('scope_id')), 'Unknown scope')}")
            if submission.get("gist"):
                st.markdown(f"**Summary:** {submission['gist']}")
            with st.expander("Original source", expanded=False): st.text(submission.get("source_text") or "")
            if submission.get("extraction_error"):
                st.warning(submission["extraction_error"])
                if st.button("Retry extraction", key=f"knowledge_retry_{project_id}_{submission['id']}"):
                    try: api_post(f"/api/v1/projects/{project_id}/knowledge/submissions/{submission['id']}/retry", {}); st.rerun()
                    except Exception as exc: st.error(f"Retry failed: {exc}")
            for conflict in submission.get("conflicts", []): st.warning(str(conflict))
            decisions = []
            reviewed_proposal_ids = set(submission.get("reviewed_proposal_ids") or [])
            for proposal in submission.get("proposals", []):
                proposal_id = str(proposal.get("id") or "")
                with st.container(border=True):
                    reviewed = proposal_id in reviewed_proposal_ids
                    st.markdown(f"**{proposal.get('title') or 'Proposed fact'}** · {proposal.get('operation', 'add')}" + (" · reviewed" if reviewed else ""))
                    st.write(proposal.get("content") or "")
                    if proposal.get("evidence_quote"): st.caption(f"Source: “{proposal['evidence_quote']}”")
                    target_fact = fact_by_id.get(str(proposal.get("target_fact_id") or ""), {})
                    suggested_scope = str(target_fact.get("scope_id") or submission.get("scope_id") or "")
                    scope_id = st.selectbox("Fact scope", scope_ids, index=scope_ids.index(suggested_scope) if suggested_scope in scope_ids else 0, format_func=lambda value: scope_names.get(value, value), key=f"knowledge_proposal_scope_{project_id}_{proposal_id}", disabled=reviewed or proposal.get("operation") in {"update", "supersede"})
                    fact_status = st.selectbox("Confidence", ["confirmed", "assumed", "needs-clarification"], key=f"knowledge_proposal_status_{project_id}_{proposal_id}", disabled=reviewed)
                    decision = st.radio("Decision", ["leave pending", "approve", "reject"], horizontal=True, key=f"knowledge_proposal_decision_{project_id}_{proposal_id}", label_visibility="collapsed", disabled=reviewed)
                    if decision != "leave pending" and not reviewed: decisions.append({"proposal_id": proposal_id, "decision": decision, "scope_id": scope_id, "status": fact_status})
            for question in submission.get("questions", []): st.info(f"Open question: {question}")
            if decisions and st.button("Save review decisions", type="primary", key=f"knowledge_review_{project_id}_{submission['id']}"):
                try:
                    api_post(f"/api/v1/projects/{project_id}/knowledge/submissions/{submission['id']}/review", {"decisions": decisions})
                    st.rerun()
                except Exception as exc: st.error(f"Could not save review: {exc}")

    st.subheader("Current approved knowledge")
    active_facts = [item for item in ledger.get("facts", []) if item.get("active")]
    if not active_facts: st.caption("No facts are active yet. Approve proposals to use them in chat and generation context.")
    for fact in active_facts:
        with st.expander(f"{fact.get('title')} · {fact.get('status')} · {scope_names.get(str(fact.get('scope_id')), 'Scope')}", expanded=False):
            st.write(fact.get("content") or "")
            st.caption(f"Fact ID {fact.get('id')} · source {fact.get('source_name') or fact.get('source_submission_id')} · {_short_time(fact.get('created_at'))}")
            if fact.get("supersedes_fact_id"): st.caption(f"Supersedes fact {fact['supersedes_fact_id']}")

    st.subheader("Open questions")
    open_questions = [item for item in ledger.get("questions", []) if item.get("status") == "open"]
    for question in open_questions:
        st.markdown(f"**{question.get('question')}**")
        answer = st.text_input("Answer", key=f"knowledge_question_answer_{project_id}_{question['id']}")
        answer_col, dismiss_col = st.columns([3, 1])
        if answer_col.button("Submit answer for review", key=f"knowledge_question_submit_{project_id}_{question['id']}", disabled=not answer.strip()):
            try: api_post(f"/api/v1/projects/{project_id}/knowledge/questions/{question['id']}/answer", {"answer": answer}); st.rerun()
            except Exception as exc: st.error(f"Could not submit answer: {exc}")
        if dismiss_col.button("Dismiss", key=f"knowledge_question_dismiss_{project_id}_{question['id']}"):
            try: api_post(f"/api/v1/projects/{project_id}/knowledge/questions/{question['id']}/dismiss", {}); st.rerun()
            except Exception as exc: st.error(f"Could not dismiss question: {exc}")

    legacy = [item for item in ledger.get("legacy_entries", []) if not item.get("retired")]
    if legacy:
        with st.expander(f"Legacy entries to review ({len(legacy)})", expanded=False):
            st.caption("These older mutable entries are not used as confirmed context. Import each into the source review queue before relying on it.")
            for entry in legacy:
                st.markdown(f"**{entry.get('title')}** · {entry.get('source_name')}")
                st.caption(str(entry.get("content") or "")[:300])
                if st.button("Import for review", key=f"knowledge_legacy_{project_id}_{entry['id']}"):
                    try:
                        api_post(f"/api/v1/projects/{project_id}/knowledge/submissions", {"content": entry.get("content", ""), "source_name": f"Legacy: {entry.get('title')}", "scope_id": (overview_scope or {}).get("id", scope_ids[0])})
                        st.rerun()
                    except Exception as exc: st.error(f"Could not import legacy entry: {exc}")

    with st.expander(f"Source and change history ({len(ledger.get('submissions', []))} submissions, {len(ledger.get('events', []))} events)", expanded=False):
        for submission in ledger.get("submissions", []):
            with st.expander(f"{submission.get('source_name')} · {submission.get('status')} · {_short_time(submission.get('created_at'))}", expanded=False):
                st.caption(f"Scope: {scope_names.get(str(submission.get('scope_id')), 'Unknown scope')}")
                if submission.get("gist"): st.markdown(f"**Gist:** {submission['gist']}")
                st.text(submission.get("source_text") or "")
        st.markdown("**Append-only change events**")
        for event in ledger.get("events", []):
            payload = event.get("payload") or {}
            st.caption(f"{_short_time(event.get('created_at'))} · {event.get('event_type')} · {json.dumps(payload, ensure_ascii=False)}")

def render_project_chat_tab() -> None:
    """Render the conversation rail, the transcript, and the brief workspace."""
    project = st.session_state.get("current_project") or {}
    project_id = str(project.get("id") or "")
    if not project_id:
        st.header("Project Chat")
        st.info("Select or create a project to start a project chat.")
        return

    st.header("Project Chat")
    st.caption(
        "Discuss product behavior and requirements against the project context, "
        "then keep what matters as a versioned brief."
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
            st.session_state.setdefault(view_key, "Conversation")
            view = st.segmented_control(
                "View", ["Conversation", "Project briefs", "Knowledge"], key=view_key,
                label_visibility="collapsed", width="stretch",
            ) or "Conversation"
            if view == "Knowledge":
                _render_knowledge_ledger(project_id)
            elif view == "Project briefs":
                try:
                    scopes = api_get(f"/api/v1/projects/{project_id}/brief-scopes") or []
                    overview = next((s for s in scopes if s.get("scope_type") == "project"), None)
                    if overview and st.button("Edit project overview", key=f"brief_open_{project_id}_{overview.get('id')}", icon=":material/edit:"):
                        _brief_dialog(project_id, overview)
                    _render_brief_cards(project_id, [s for s in scopes if s.get("scope_type") != "project"])
                except Exception as exc:
                    st.error(f"Could not load project briefs: {exc}")
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
        st.session_state.setdefault(view_key, "Conversation")
        view = st.segmented_control(
            "View", ["Conversation", "Project briefs", "Knowledge"], key=view_key,
            label_visibility="collapsed", width="stretch",
        ) or "Conversation"

        if view == "Conversation":
            _render_conversation(project_id, thread)
            return

        if view == "Knowledge":
            _render_knowledge_ledger(project_id)
            return

        try:
            scopes = api_get(f"/api/v1/projects/{project_id}/brief-scopes") or []
        except Exception as exc:
            st.error(f"Could not load project briefs: {exc}")
            return
        overview = next((s for s in scopes if s.get("scope_type") == "project"), None)
        with st.container(border=True):
            if overview:
                st.markdown(f"**{overview.get('name') or 'Project overview'}** :gray-badge[always included]")
                st.caption(
                    " ".join(str(overview.get("current_content") or "").split())[:240]
                    or "No saved version yet."
                )
                if st.button(
                    "Edit project overview", key=f"brief_open_{project_id}_{overview.get('id')}",
                    icon=":material/edit:", width="stretch",
                ):
                    _brief_dialog(project_id, overview)
            else:
                st.caption("No project overview scope yet.")

        with st.popover("Add a feature or service brief", icon=":material/add:"):
            scope_type = st.selectbox("Scope", ["feature", "microservice"], key=f"brief_new_type_{project_id}")
            scope_name = st.text_input("Name", key=f"brief_new_name_{project_id}", placeholder="For example, Checkout")
            if st.button(
                "Create brief", key=f"brief_create_{project_id}", type="primary",
                width="stretch", disabled=not scope_name.strip(),
            ):
                try:
                    api_post(
                        f"/api/v1/projects/{project_id}/brief-scopes",
                        {"scope_type": scope_type, "name": scope_name.strip()},
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not create brief scope: {exc}")

        _render_brief_cards(
            project_id,
            [s for s in scopes if s.get("scope_type") != "project"],
        )
