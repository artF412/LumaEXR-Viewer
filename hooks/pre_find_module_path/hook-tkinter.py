def pre_find_module_path(hook_api):
    # Keep tkinter discoverable even if the local Python install reports Tcl/Tk as broken.
    # We bundle Tcl/Tk data manually in the spec file.
    return
