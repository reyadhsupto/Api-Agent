with open('/Users/reyadhassan/Projects/apiAiTest/Api-Agent/frontend/app.py', 'r') as f:
    content = f.read()

start_marker = 'def _render_collection_navigator(project: dict, project_id: str) -> str | None:'
start = content.find(start_marker)
if start < 0:
    print('START NOT FOUND')
    exit(1)

end_marker = '\ndef _render_request_rows(rows: list[dict], kind: str, tab_id: str) -> list[dict]:'
end = content.find(end_marker, start)
if end < 0:
    print('END NOT FOUND')
    exit(1)

print(f'Old function: lines {content[:start].count(chr(10)) + 1} to {content[:end].count(chr(10)) + 1}')
print(f'Old function length: {end - start} chars')

new_function = '''def _render_collection_navigator(project: dict, project_id: str) -> str | None:
    """Render Postman-style collection navigator with request tree.

    Args:
        project (dict): Current project and its collections and requests.
        project_id (str): Stable identifier of the active project.

    Returns:
        str | None: Selected collection ID used as the default save destination.
    """
    collections = project.get("collections", [])
    all_requests = project.get("endpoints", [])
    collection_ids = {item["id"] for item in collections}
    selected_id = st.session_state.get("selected_collection_id")
    if selected_id not in collection_ids:
        selected_id = collections[0]["id"] if collections else None
        st.session_state["selected_collection_id"] = selected_id

    expanded_ids = st.session_state.setdefault(
        "workspace_expanded_collections", [selected_id] if selected_id else [],
    )
    expanded_ids = [item for item in expanded_ids if item in collection_ids]
    st.session_state["workspace_expanded_collections"] = expanded_ids

    # Ensure request selection state exists
    if "collection_request_selections" not in st.session_state:
        st.session_state["collection_request_selections"] = {}

    with st.container(key="collection-browser-header"):
        project_name = html.escape(str(project.get("name") or "Workspace"), quote=True)
        st.markdown(
            f"<div class='aa-navigator-title'>{project_name}</div>"
            "<div class='aa-navigator-subtitle'>API Workspace</div>",
            unsafe_allow_html=True,
        )
        new_col, import_col, discover_col = st.columns(
            [1, 1, 1], vertical_alignment="center",
        )
        with new_col:
            if st.button(
                "New", key=f"navigator_new_request_{project_id}",
                icon=":material/add:", type="secondary", width="stretch",
            ):
                draft = _new_request_draft()
                draft["collection_id"] = selected_id
                st.session_state["request_drafts"].append(draft)
                st.session_state["active_request_tab_id"] = draft["tab_id"]
                st.rerun()
        if import_col.button(
            "Import", key=f"navigator_import_contract_{project_id}",
            icon=":material/file_upload:", type="primary", width="stretch",
        ):
            st.session_state["workspace_contract_panel"] = "import"
            st.rerun()
        contract_sources = {
            (endpoint.get("contract") or {}).get("source_id")
            for endpoint in all_requests
            if (endpoint.get("contract") or {}).get("source_id")
        }
        if discover_col.button(
            "Discover", key=f"navigator_discover_flows_{project_id}",
            icon=":material/account_tree:", disabled=not contract_sources, width="stretch",
        ):
            st.session_state["workspace_contract_panel"] = "discover"
            st.rerun()

    with st.container(key="navigator-search-row"):
        create_col, search_col, actions_col = st.columns([.48, 4.3, .55], vertical_alignment="center")
        with create_col:
            with st.popover(
                "Create collection", icon=":material/add:",
                key=f"navigator_create_collection_{project_id}",
            ):
                with st.form(f"create_request_collection_{project_id}", clear_on_submit=True):
                    collection_name = st.text_input("Collection name", placeholder="e.g. Authentication")
                    create_clicked = st.form_submit_button(
                        "Create collection", type="primary", width="stretch",
                    )
                if create_clicked:
                    if not collection_name.strip():
                        st.error("Enter a collection name.")
                    else:
                        try:
                            created = api_post(
                                f"/api/v1/projects/{project_id}/collections",
                                {"name": collection_name.strip()},
                            )
                            _refresh_project_preserving_drafts(project_id)
                            _queue_toast("Collection created.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not create collection: {exc}")
        with search_col:
            search_text = st.text_input(
                "Search collections and requests",
                key=f"navigator_search_{project_id}",
                placeholder="Search collections and requests",
                label_visibility="collapsed",
            ).strip().casefold()
        with actions_col:
            with st.popover(
                "Generation options", icon=":material/more_horiz:",
                key=f"navigator_generation_options_{project_id}",
            ):
                enabled_count = sum(
                    bool(item.get("include_for_generation", item.get("include", False)))
                    for item in all_requests
                )
                st.caption(f"{enabled_count} of {len(all_requests)} requests enabled")
                if st.button(
                    "Select all for generation", key=f"eligible_select_all_{project_id}",
                    icon=":material/select_all:", width="stretch", disabled=not all_requests,
                ):
                    try:
                        _set_generation_eligibility(project_id, all_requests, True)
                        st.session_state["generation_eligibility_revision"] = (
                            st.session_state.get("generation_eligibility_revision", 0) + 1
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not enable all requests for generation: {exc}")
                if st.button(
                    "Deselect all", key=f"eligible_deselect_all_{project_id}",
                    icon=":material/deselect:", width="stretch", disabled=not all_requests,
                ):
                    try:
                        _set_generation_eligibility(project_id, all_requests, False)
                        st.session_state["generation_eligibility_revision"] = (
                            st.session_state.get("generation_eligibility_revision", 0) + 1
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not disable all requests for generation: {exc}")

    # Render collections as a Postman-style tree
    with st.container(key="collection-browser-scroll"):
        if not collections:
            _empty_state("No collections yet", "Create a collection here or import an API contract.")
            return selected_id

        visible_collection_count = 0
        for collection in collections:
            collection_id = collection["id"]
            saved_requests = collection.get("requests", [])
            collection_name = str(collection.get("name") or "Untitled collection")
            collection_matches = search_text in collection_name.casefold() if search_text else True
            matching_requests = [
                request for request in saved_requests
                if not search_text or collection_matches or any(
                    search_text in str(request.get(field) or "").casefold()
                    for field in ("name", "url", "method")
                )
            ]
            if search_text and not collection_matches and not matching_requests:
                continue
            visible_collection_count += 1
            is_expanded = collection_id in expanded_ids or bool(search_text)
            collection_eligible = bool(saved_requests) and all(
                bool(request.get("include_for_generation", request.get("include", False)))
                for request in saved_requests
            )
            collection_eligibility_key = f"collection_generation_{collection_id}"
            revision = st.session_state.get("generation_eligibility_revision", 0)
            _sync_generation_eligibility_widget(
                collection_eligibility_key,
                f"collection_generation_revision_{collection_id}",
                collection_eligible,
                revision,
            )

            # Collection header row
            with st.container(key=f"collection-row-{collection_id}"):
                col_check, col_title, col_menu = st.columns([0.5, 5, 0.5], vertical_alignment="center")
                with col_check:
                    is_collection_selected = st.checkbox(
                        f"Include all {collection_name} requests for generation",
                        key=collection_eligibility_key,
                        label_visibility="collapsed",
                        disabled=not saved_requests,
                    )
                    if selected_collection_eligible != collection_eligible:
                        try:
                            _set_generation_eligibility(
                                project_id, saved_requests, selected_collection_eligible,
                            )
                            st.session_state["generation_eligibility_revision"] = revision + 1
                            _queue_toast(
                                f"All requests in {collection_name} enabled for generation."
                                if selected_collection_eligible
                                else f"All requests in {collection_name} excluded from generation."
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not update collection eligibility: {exc}")
                with title_col:
                    expand_label = f"{'▾' if is_expanded else '▸'}  {collection_name}  ·  {len(saved_requests)}"
                    if st.button(
                        expand_label, key=f"toggle_collection_{collection_id}",
                        type="tertiary", width="stretch",
                    ):
                        _toggle_collection_expanded(collection_id)
                        st.session_state["selected_collection_id"] = collection_id
                        st.rerun()
                with menu_col:
                    with st.popover(
                        "Collection actions", icon=":material/more_vert:",
                        key=f"collection_menu_{collection_id}",
                    ):
                        rename_key = f"rename_collection_value_{collection_id}"
                        st.text_input(
                            "Rename collection", value=collection_name, key=rename_key,
                        )
                        if st.button("Rename", key=f"rename_collection_button_{collection_id}", width="stretch"):
                            try:
                                new_name = st.session_state[rename_key].strip()
                                if not new_name:
                                    raise ValueError("Collection name is required.")
                                api_put(
                                    f"/api/v1/projects/{project_id}/collections/{collection_id}",
                                    {"name": new_name},
                                )
                                _refresh_project_preserving_drafts(project_id)
                                _queue_toast("Collection renamed.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not rename collection: {exc}")
                        export_payload = _fetch_collection_export_cached(project_id, collection_id)
                        st.download_button(
                            "Export Postman collection",
                            data=json.dumps(export_payload, ensure_ascii=False, indent=2),
                            file_name=f"{collection_name}.postman_collection.json",
                            mime="application/json", key=f"export_collection_{collection_id}",
                            width="stretch",
                        )
                        confirm_delete = st.checkbox(
                            "Confirm delete collection and its requests",
                            key=f"confirm_delete_collection_{collection_id}",
                        )
                        if st.button("Delete collection", key=f"delete_collection_{collection_id}", type="secondary", width="stretch", disabled=not confirm_delete):
                            try:
                                api_delete(f"/api/v1/projects/{project_id}/collections/{collection_id}")
                                _refresh_project_preserving_drafts(project_id)
                                st.session_state["selected_collection_id"] = [
                                    cid for cid in st.session_state.get("selected_collection_id", [])
                                    if cid != collection_id
                                ] if isinstance(st.session_state.get("selected_collection_id"), list) else (
                                    None if st.session_state.get("selected_collection_id") == collection_id else st.session_state.get("selected_collection_id")
                                )
                                _queue_toast("Collection deleted.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not delete collection: {exc}")

            if not is_expanded:
                continue
            if not matching_requests:
                if not saved_requests:
                    st.caption("This collection is empty. Save a request here from the playground.")
                continue

            # Render individual request rows under the collection
            for saved in matching_requests:
                request_id = saved["id"]
                method = str(saved.get("method") or "GET").upper()
                display_name = str(saved.get("name") or saved.get("url") or "Untitled request")
                request_url = str(saved.get("url") or "No URL configured")
                eligible = bool(saved.get("include_for_generation", saved.get("include", False)))
                is_active_request = any(
                    draft.get("id") == request_id
                    and draft.get("tab_id") == st.session_state.get("active_request_tab_id")
                    for draft in st.session_state["request_drafts"]
                )
                eligibility_key = f"request_generation_{request_id}"
                revision = st.session_state.get("generation_eligibility_revision", 0)
                _sync_generation_eligibility_widget(
                    eligibility_key,
                    f"request_generation_revision_{request_id}",
                    eligible,
                    revision,
                )
                selected_request_class = "selected-" if is_active_request else ""

                with st.container(key=f"browser-request-row-{selected_request_class}{request_id}"):
                    col_check, col_method, col_name, col_url, col_menu = st.columns(
                        [0.45, 0.9, 3.2, 3.8, 0.6], vertical_alignment="center",
                    )

                    # Individual request checkbox
                    with col_check:
                        is_selected = st.session_state.get("collection_request_selections", {}).get(request_id, False)
                        new_selected = st.checkbox(
                            "",
                            value=is_selected,
                            key=f"req_check_{request_id}",
                            label_visibility="collapsed",
                        )
                        if new_selected != is_selected:
                            sel = set(st.session_state.get("collection_request_selections", {}))
                            if new_selected:
                                sel.add(request_id)
                            else:
                                sel.discard(request_id)
                            st.session_state["collection_request_selections"] = sel
                            st.rerun()

                    with col_method:
                        st.markdown(_method_badge(method))

                    with col_name:
                        if st.button(
                            display_name, key=f"open_saved_{request_id}",
                            type="tertiary", width="stretch",
                            help=f"{request_url} · Open request in playground",
                        ):
                            existing = next(
                                (d for drafts in [st.session_state["request_drafts"]] for d in drafts if d.get("id") == request_id),
                                None,
                            )
                            if not existing:
                                existing = _new_request_draft(saved)
                                st.session_state["request_drafts"].append(existing)
                            st.session_state["active_request_tab_id"] = existing["tab_id"]
                            st.session_state["selected_collection_id"] = collection_id
                            st.rerun()

                    with col_url:
                        st.caption(f"{request_url[:60]}…" if len(request_url) > 60 else request_url)

                    with col_menu:
                        with st.popover("Request actions", icon=":material/more_vert:", key=f"request_menu_{request_id}"):
                            rename_key = f"rename_request_value_{request_id}"
                            st.text_input(
                                "Rename request", value=display_name, key=rename_key,
                            )
                            if st.button("Rename", key=f"rename_request_button_{request_id}", width="stretch"):
                                try:
                                    new_name = st.session_state[rename_key].strip()
                                    if not new_name:
                                        raise ValueError("Request name is required.")
                                    api_put(
                                        f"/api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}",
                                        {"name": new_name},
                                    )
                                    for d in st.session_state["request_drafts"]:
                                        if d.get("id") == request_id:
                                            d["name"] = new_name
                                            st.session_state[f"name_{d['tab_id']}"] = new_name
                                    _refresh_project_preserving_drafts(project_id)
                                    _queue_toast("Request renamed.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Could not rename request: {exc}")
                            if st.button("Duplicate", key=f"duplicate_request_{request_id}", icon=":material/content_copy:", width="stretch"):
                                try:
                                    duplicate = copy.deepcopy(saved)
                                    duplicate.pop("id", None)
                                    duplicate["name"] = f"{display_name} Copy"
                                    duplicate["include_for_generation"] = False
                                    duplicate["include"] = False
                                    api_post(
                                        f"/api/v1/projects/{project_id}/collections/{collection_id}/requests",
                                        duplicate,
                                    )
                                    _refresh_project_preserving_drafts(project_id)
                                    st.session_state["selected_collection_id"] = collection_id
                                    _queue_toast("Request duplicated.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Could not duplicate request: {exc}")
                            confirm_delete = st.checkbox(
                                "Confirm delete request", key=f"confirm_delete_request_{request_id}",
                            )
                            if st.button("Delete request", key=f"delete_request_{request_id}", icon=":material/delete:", type="secondary", width="stretch", disabled=not confirm_delete):
                                try:
                                    api_delete(f"/api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}")
                                    _refresh_project_preserving_drafts(project_id)
                                    _persist_generation_order(
                                        project_id, st.session_state.get("generation_order_ids", []),
                                    )
                                    _queue_toast("Saved request deleted.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Could not delete request: {exc}")

    return selected_id


'''

# Replace the old function with the new one
new_content = content[:start] + new_function + content[end:]

with open('/Users/reyadhassan/Projects/apiAiTest/Api-Agent/frontend/app.py', 'w') as f:
    f.write(new_content)

print(f'Replacement successful! New function is {len(new_function)} chars.')
