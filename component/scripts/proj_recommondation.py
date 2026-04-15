def handle_file_selection(file_path: Optional[str]):
    print(f"DEBUG: File selected: {file_path}")
    """When user selects a file"""
    if not file_path:
        reset_all_state()
        return

    # Clear existing uploaded file state when selecting a new file
    app_state.reset_raster_only()  # This should clear uploaded_file_info
    app_state.file_error.value = None

    try:
        file_info_dict = get_file_info(file_path)

        if "error" in file_info_dict:
            app_state.file_error.value = file_info_dict["error"]
            selected_file_path.value = None
            selected_file_info_preview.value = None
            is_valid_file.value = False
            return

        # Only set local preview state, NOT global app_state yet
        selected_file_path.value = file_path
        selected_file_info_preview.value = file_info_dict
        is_valid_file.value = True
        app_state.file_error.value = None

    except Exception as e:
        app_state.file_error.value = str(e)
        selected_file_path.value = None
        selected_file_info_preview.value = None