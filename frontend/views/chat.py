# frontend/views/chat.py

"""
Project Chat view: project-persistent conversations and the brief workspace.
"""

import streamlit as st

import html, json

from frontend.core import (
    _load_project_chat_thread,
    _render_project_brief_manager,
    api_get,
    api_post,
    api_put,
)


def render_project_chat_tab() -> None:
    """Render project-persistent conversations and the separate brief workspace."""
    project = st.session_state.get("current_project") or {}
    project_id = str(project.get("id") or "")
    st.subheader("Project Chat")
    if not project_id:
        st.info("Select or create a project to start a project chat.")
        return

    list_col, main_col = st.columns([1.05, 3.95], gap="large")
    with list_col:
        st.markdown("#### Chats")
        if st.button("New chat", icon=":material/add:", key=f"chat_new_{project_id}", width="stretch"):
            try:
                thread = api_post(f"/api/v1/projects/{project_id}/chat/threads", {"title": "New project chat"})
                _load_project_chat_thread(project_id, str(thread["id"]))
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create chat: {exc}")
        show_archived = st.toggle("Show archived", key=f"chat_show_archived_{project_id}")
        try:
            threads = api_get(
                f"/api/v1/projects/{project_id}/chat/threads" + ("?include_archived=true" if show_archived else "")
            ) or []
        except Exception as exc:
            st.error(f"Could not load chats: {exc}")
            threads = []
        active_thread_id = st.session_state.get(f"project_chat_selected_thread_{project_id}")
        with st.container(height=520, border=False, key=f"chat_thread_list_{project_id}"):
            for thread_item in threads:
                thread_id = str(thread_item.get("id") or "")
                title_col, action_col = st.columns([5, 1], vertical_alignment="center")
                with title_col:
                    if st.button(
                        str(thread_item.get("title") or "New chat"),
                        key=f"chat_open_{project_id}_{thread_id}",
                        type="primary" if thread_id == active_thread_id else "tertiary",
                        width="stretch",
                    ):
                        try:
                            _load_project_chat_thread(project_id, thread_id)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not open chat: {exc}")
                with action_col:
                    with st.popover(
                        "⋯", type="tertiary", key=f"chat_actions_{project_id}_{thread_id}",
                        help="Rename or archive this chat", width="content",
                    ):
                        renamed = st.text_input(
                            "Thread name", value=str(thread_item.get("title") or ""),
                            key=f"chat_rename_value_{project_id}_{thread_id}",
                        )
                        if st.button("Rename", key=f"chat_rename_{project_id}_{thread_id}", disabled=not renamed.strip()):
                            try:
                                api_put(f"/api/v1/projects/{project_id}/chat/threads/{thread_id}", {"title": renamed.strip()})
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not rename chat: {exc}")
                        target_archived = not bool(thread_item.get("archived"))
                        if st.button(
                            "Restore" if thread_item.get("archived") else "Archive",
                            key=f"chat_archive_{project_id}_{thread_id}",
                        ):
                            try:
                                api_put(f"/api/v1/projects/{project_id}/chat/threads/{thread_id}", {"archived": target_archived})
                                if thread_id == active_thread_id and target_archived:
                                    st.session_state.pop(f"project_chat_thread_data_{project_id}", None)
                                    st.session_state.pop(f"project_chat_selected_thread_{project_id}", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not update chat: {exc}")

    with main_col:
        thread_id = st.session_state.get(f"project_chat_selected_thread_{project_id}")
        thread = st.session_state.get(f"project_chat_thread_data_{project_id}")
        if thread_id and (not thread or str(thread.get("id")) != str(thread_id)):
            try:
                _load_project_chat_thread(project_id, str(thread_id))
                thread = st.session_state.get(f"project_chat_thread_data_{project_id}")
            except Exception as exc:
                st.error(f"Could not load chat history: {exc}")
                thread = None
        if not thread_id:
            st.caption("Create or select a chat to discuss product behavior, workflows, integrations, or requirement gaps.")
            return

        conversation_tab, briefs_tab = st.tabs(["Conversation", "Project briefs"])
        with conversation_tab:
            if thread:
                st.markdown(f"### {html.escape(str(thread.get('title') or 'Project chat'))}")
            read_only = bool(thread and thread.get("archived"))
            messages = (thread or {}).get("messages", [])
            if not messages:
                st.caption("Describe a feature, user journey, integration, or requirement gap below. The assistant can ask follow-up questions to clarify the product context.")
            else:
                with st.container(height=535, border=True, key=f"chat_history_{project_id}_{thread_id}"):
                    for index in range(0, len(messages), 2):
                        first = messages[index]
                        second = messages[index + 1] if index + 1 < len(messages) else None
                        user_message = first if first.get("role") == "user" else second
                        assistant_message = second if first.get("role") == "user" else first
                        label = str((user_message or {}).get("content") or "Conversation").strip().replace("\n", " ")
                        label = label[:90] + ("…" if len(label) > 90 else "")
                        with st.expander(label or "Conversation", expanded=True):
                            if user_message:
                                st.markdown("**You**")
                                st.markdown(str(user_message.get("content") or ""))
                            if assistant_message:
                                st.markdown("**Assistant**")
                                st.markdown(str(assistant_message.get("content") or ""))
                                sources = assistant_message.get("endpoint_sources") or []
                                if sources:
                                    with st.expander(f"Sources · {len(sources)} saved endpoints", expanded=False):
                                        for source in sources:
                                            st.caption(
                                                f"{source.get('collection_name') or 'Unassigned'} · "
                                                f"{source.get('method', 'GET')} · {source.get('name') or source.get('url') or 'Endpoint'}"
                                            )
                                            st.code(str(source.get("url") or ""), language=None)
                    scroll_flag = st.session_state.pop(f"chat_scroll_latest_{project_id}_{thread_id}", False)
                    if scroll_flag:
                        anchor_id = f"chat-scroll-{project_id}-{thread_id}"
                        st.html(
                            f'<div id="{html.escape(anchor_id, quote=True)}"></div><script>'
                            f'(()=>{{const a=document.getElementById({json.dumps(anchor_id)});if(!a)return;'
                            'let n=a.parentElement;while(n&&n!==document.body){const s=getComputedStyle(n);'
                            'if(/(auto|scroll)/.test(s.overflowY)&&n.scrollHeight>n.clientHeight){n.scrollTop=n.scrollHeight;break;}n=n.parentElement;}})();'
                            '</script>', unsafe_allow_javascript=True,
                        )
            if read_only:
                st.info("This chat is archived. Restore it from the thread menu to continue the conversation.")
            else:
                message = st.chat_input("Message about this project…", key=f"chat_composer_{project_id}_{thread_id}")
                if message:
                    try:
                        with st.spinner("Thinking with the project context…"):
                            response = api_post(
                                f"/api/v1/projects/{project_id}/chat/threads/{thread_id}/messages",
                                {"content": message},
                            )
                        st.session_state[f"project_chat_thread_data_{project_id}"] = response.get("thread")
                        st.session_state[f"chat_scroll_latest_{project_id}_{thread_id}"] = True
                        st.session_state[f"project_chat_selected_thread_{project_id}"] = thread_id
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not send message: {exc}")
        with briefs_tab:
            _render_project_brief_manager(project_id, thread)
