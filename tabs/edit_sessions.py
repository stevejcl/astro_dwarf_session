import os
import json
import tkinter as tk
from tkinter import messagebox
import re
from astro_dwarf_scheduler import get_json_files_sorted
import time

def edit_sessions_tab(parent_tab, session_dir, refresh_callback=None):
    frame = tk.Frame(parent_tab)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    label = tk.Label(frame, text="Available Sessions (JSON files):", font=("Arial", 12), pady=5)
    label.pack(anchor="w")

    listbox = tk.Listbox(frame, width=40, height=20, selectmode=tk.EXTENDED)
    listbox.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

    scrollbar = tk.Scrollbar(frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side=tk.LEFT, fill=tk.Y)
    listbox.config(yscrollcommand=scrollbar.set)

    # --- Add scrollable form frame (scrollbar on right) ---
    form_canvas = tk.Canvas(frame, borderwidth=0, highlightthickness=0)
    form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    form_scrollbar = tk.Scrollbar(frame, orient="vertical", command=form_canvas.yview)
    form_scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 0))
    form_canvas.configure(yscrollcommand=form_scrollbar.set)

    # Create a frame inside the canvas
    form_frame = tk.Frame(form_canvas)
    form_window = form_canvas.create_window((0, 0), window=form_frame, anchor="nw")

    # Configure the grid layout for `form_frame`
    form_frame.grid_columnconfigure(1, weight=1)  # Make the second column stretchable

    # Debounce mechanism
    last_resize_time = [0.0]  # Use a mutable object to track the last resize time (float)

    # Ensure the form_frame always has a minimum width so widgets are visible
    def on_canvas_configure(event):
        current_time = time.time()
        if current_time - last_resize_time[0] > 0.1:  # Update every 100ms
            form_canvas.itemconfig(form_window, width=event.width)
            last_resize_time[0] = current_time

    form_canvas.bind('<Configure>', on_canvas_configure)

    # Update the scroll region when the form_frame changes
    def update_scrollregion(event=None):
        form_canvas.configure(scrollregion=form_canvas.bbox("all"))

    form_frame.bind("<Configure>", update_scrollregion)

    # Handle mouse wheel scrolling
    def _on_mousewheel(event):
        if event.num == 4:  # Scroll up
            form_canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Scroll down
            form_canvas.yview_scroll(1, "units")
        else:  # For standard mouse wheel events
            form_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # Bind mouse wheel events for both Windows and Linux
    form_canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows
    form_canvas.bind_all("<Button-4>", _on_mousewheel)    # Linux scroll up
    form_canvas.bind_all("<Button-5>", _on_mousewheel)    # Linux scroll down

    entries = {}
    form_widgets = {}  # Cache for form structure
    selected_file = {'name': None, 'data': None}
    form_built = {'flag': False}  # Track if form structure is built
    has_unsaved_changes = {'flag': False}  # Track if there are unsaved changes

    def refresh_list():
        listbox.delete(0, tk.END)
        for fname in get_json_files_sorted(session_dir):
            listbox.insert(tk.END, fname)
        clear_form()
        selected_file['name'] = None
        selected_file['data'] = None
        has_unsaved_changes['flag'] = False
        if refresh_callback:
            refresh_callback()

    def clear_form():
        # Only clear values, not destroy widgets
        if form_built['flag']:
            for key, widget in entries.items():
                if hasattr(widget, 'delete'):
                    widget.delete(0, tk.END)
                elif hasattr(widget, 'set'):
                    widget.set('')
        else:
            # First time - destroy everything
            for widget in form_frame.winfo_children():
                widget.destroy()
            entries.clear()
            form_widgets.clear()
        has_unsaved_changes['flag'] = False

    def mark_changed():
        """Mark that changes have been made"""
        has_unsaved_changes['flag'] = True

    def save_json():
        """Save the current file if there are unsaved changes"""
        if not has_unsaved_changes['flag']:
            return
            
        fname = selected_file['name']
        if not fname:
            return
        data = selected_file['data']
        if not data:
            return
            
        try:
            id_cmd = data['command']['id_command']
            for key in ["description", "date", "time", "process", "max_retries", "result", "message", "nb_try"]:
                if ('id_command', key) in entries:
                    val = entries[('id_command', key)].get()
                    if key in ["max_retries", "nb_try"]:
                        try: val = int(val)
                        except: val = 0
                    elif key == "result":
                        val = val.lower() == 'true'
                    id_cmd[key] = val
                    
            for subcmd in ["eq_solving", "auto_focus", "infinite_focus", "calibration", "goto_solar", "goto_manual", "setup_camera", "setup_wide_camera"]:
                sub = data['command'].get(subcmd, {})
                for k in sub.keys():
                    if (subcmd, k) in entries:
                        widget = entries[(subcmd, k)]
                        if k == 'do_action':
                            val = widget.get()
                            val = val == 'True'
                        else:
                            val = widget.get()
                            if isinstance(val, str) and val.lower() in ['true', 'false']:
                                val = val.lower() == 'true'
                            else:
                                try:
                                    if '.' in val:
                                        val = float(val)
                                    else:
                                        val = int(val)
                                except:
                                    pass
                        sub[k] = val
                        
            fpath = os.path.join(session_dir, fname)
            with open(fpath, 'w') as f:
                json.dump(data, f, indent=4)
            has_unsaved_changes['flag'] = False
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file: {e}")

    def build_form_structure(data):
        """Build the form structure once and reuse it"""
        if form_built['flag']:
            return  # Form already built

        clear_form()
        row = 0

        # Add Reset button at the top
        header_frame = tk.Frame(form_frame)
        header_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        tk.Label(header_frame, text="Session Info", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w", padx=(10, 0))
        row += 1

        # Build id_command fields
        for key in ["description", "date", "time", "process", "max_retries", "result", "message", "nb_try"]:
            label = tk.Label(form_frame, text=key + ":")
            label.grid(row=row, column=0, sticky="e", padx=(5, 10), pady=(2, 2))
            ent = tk.Entry(form_frame)
            ent.grid(row=row, column=1, sticky="ew", padx=(5, 10), pady=(2, 2))  # Make the entry stretchable
            entries[('id_command', key)] = ent
            form_widgets[('id_command', key)] = (label, ent)
            ent.bind('<KeyRelease>', lambda e: mark_changed())
            row += 1

        # Build subcmd sections - we'll populate dynamically
        form_widgets['subcmd_start_row'] = row
        form_built['flag'] = True

    def populate_subcmd_fields(data, start_row):
        """Populate subcmd fields dynamically"""
        # Clear existing subcmd widgets
        for key in list(entries.keys()):
            if key[0] != 'id_command':
                widget = entries[key]
                if hasattr(widget, 'destroy'):
                    widget.destroy()
                del entries[key]

        # Clear subcmd form widgets
        for key in list(form_widgets.keys()):
            if isinstance(key, tuple) and key[0] != 'id_command':
                widgets = form_widgets[key]
                if isinstance(widgets, tuple):
                    for w in widgets:
                        if hasattr(w, 'destroy'):
                            w.destroy()
                del form_widgets[key]

        row = start_row
        for subcmd in ["eq_solving", "auto_focus", "infinite_focus", "calibration", "goto_solar", "goto_manual", "setup_camera", "setup_wide_camera"]:
            sub = data['command'].get(subcmd, {})
            if not sub:  # Skip if subcmd doesn't exist
                continue
            label = tk.Label(form_frame, text=subcmd, font=("Arial", 10, "bold"))
            label.grid(row=row, column=0, sticky="w", pady=(10, 0), padx=(10, 0))
            form_widgets[f'{subcmd}_header'] = label
            row += 1
            for k, v in sub.items():
                sub_label = tk.Label(form_frame, text="    " + k + ":")
                sub_label.grid(row=row, column=0, sticky="e", padx=(5, 5), pady=(2, 2))
                if k == 'do_action':
                    from tkinter import ttk
                    combo = ttk.Combobox(form_frame, values=["True", "False"], state="readonly")
                    combo.grid(row=row, column=1, sticky="ew", padx=(5, 10), pady=(2, 2))  # Make the combobox stretchable
                    entries[(subcmd, k)] = combo
                    form_widgets[(subcmd, k)] = (sub_label, combo)
                    combo.bind('<<ComboboxSelected>>', lambda e: mark_changed())
                    # Prevent mouse wheel from changing dropdown selection
                    def block_mousewheel(event):
                        return "break"
                    combo.bind('<MouseWheel>', block_mousewheel)
                    combo.bind('<Button-4>', block_mousewheel)
                    combo.bind('<Button-5>', block_mousewheel)
                else:
                    ent = tk.Entry(form_frame)
                    ent.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(2, 2))  # Make the entry stretchable
                    entries[(subcmd, k)] = ent
                    form_widgets[(subcmd, k)] = (sub_label, ent)
                    ent.bind('<KeyRelease>', lambda e: mark_changed())
                row += 1

        # Update the scroll region once after all widgets are added
        update_scrollregion()

    def populate_form(data):
        """Populate form with data - optimized version"""
        # Build form structure if not built
        build_form_structure(data)
        
        # Set reset button command
        def reset_fields():
            id_cmd = data['command']['id_command']
            id_cmd['process'] = 'wait'
            id_cmd['result'] = False
            id_cmd['message'] = ''
            id_cmd['nb_try'] = 1
            # Update the form fields visually
            entries[('id_command', 'process')].delete(0, tk.END)
            entries[('id_command', 'process')].insert(0, 'wait')
            entries[('id_command', 'result')].delete(0, tk.END)
            entries[('id_command', 'result')].insert(0, 'False')
            entries[('id_command', 'message')].delete(0, tk.END)
            entries[('id_command', 'message')].insert(0, '')
            entries[('id_command', 'nb_try')].delete(0, tk.END)
            entries[('id_command', 'nb_try')].insert(0, '1')
            save_json()
                
        # Populate id_command fields
        id_cmd = data['command']['id_command']
        for key in ["description", "date", "time", "process", "max_retries", "result", "message", "nb_try"]:
            if ('id_command', key) in entries:
                widget = entries[('id_command', key)]
                widget.delete(0, tk.END)
                val = id_cmd.get(key, "")
                widget.insert(0, str(val))
        
        # Populate subcmd fields
        populate_subcmd_fields(data, form_widgets['subcmd_start_row'])
        
        # Set subcmd values
        for subcmd in ["eq_solving", "auto_focus", "infinite_focus", "calibration", "goto_solar", "goto_manual", "setup_camera", "setup_wide_camera"]:
            sub = data['command'].get(subcmd, {})
            for k, v in sub.items():
                if (subcmd, k) in entries:
                    widget = entries[(subcmd, k)]
                    if k == 'do_action':
                        widget.set("True" if v else "False")
                    else:
                        if hasattr(widget, 'delete'):
                            widget.delete(0, tk.END)
                            widget.insert(0, str(v))
    
    # Update the scroll region after populating the form
    update_scrollregion()

    def on_select(event):
        # Save any pending changes before switching files
        save_json()
        
        selection = listbox.curselection()
        if not selection:
            return
            
        fname = listbox.get(selection[0])
        
        # Don't reload if same file is selected
        if selected_file['name'] == fname:
            return
        
        # Show loading indicator
        if not form_built['flag']:
            loading_label = tk.Label(form_frame, text="Loading...", font=("Arial", 12))
            loading_label.pack()
            form_frame.update_idletasks()
        
        fpath = os.path.join(session_dir, fname)
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
            selected_file['name'] = fname
            selected_file['data'] = data
            populate_form(data)
            has_unsaved_changes['flag'] = False  # Reset change flag after loading
        except Exception as e:
            clear_form()
            refresh_list()

    # Add event binding to detect when listbox loses selection
    def on_listbox_focus_out(event):
        # Save when listbox loses focus (indicating user might be switching tabs)
        save_json()
    
    listbox.bind('<FocusOut>', on_listbox_focus_out)
    listbox.bind('<<ListboxSelect>>', on_select)

    def on_listbox_double_click(event):
        selection = listbox.curselection()
        if not selection:
            return
        old_fname = listbox.get(selection[0])
        fpath_old = os.path.join(session_dir, old_fname)
        # Prompt for new filename
        from tkinter import simpledialog
        new_fname = simpledialog.askstring("Rename File", f"Enter new filename for '{old_fname}':", initialvalue=old_fname)
        if not new_fname or new_fname == old_fname:
            return
        # Validate filename
        if not re.match(r'^[\w\-. ]+\.json$', new_fname):
            messagebox.showerror("Invalid Filename", "Filename must end with .json and contain only letters, numbers, dashes, underscores, spaces, or dots.")
            return
        fpath_new = os.path.join(session_dir, new_fname)
        if os.path.exists(fpath_new):
            messagebox.showerror("File Exists", f"A file named '{new_fname}' already exists.")
            return
        try:
            os.rename(fpath_old, fpath_new)
            # If the currently selected file is being renamed, update selected_file
            if selected_file['name'] == old_fname:
                selected_file['name'] = new_fname
            refresh_list()
            # Reselect the renamed file
            idx = None
            for i in range(listbox.size()):
                if listbox.get(i) == new_fname:
                    idx = i
                    break
            if idx is not None:
                listbox.selection_set(idx)
        except Exception as e:
            messagebox.showerror("Rename Error", f"Could not rename file: {e}")

    listbox.bind('<Double-Button-1>', on_listbox_double_click)
    
    # Also save when the main frame loses focus (tab switch)
    def on_frame_focus_out(event):
        save_json()
    
    frame.bind('<FocusOut>', on_frame_focus_out)
    
    refresh_list()

    button_frame = tk.Frame(parent_tab)
    button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

    def delete_selected_files():
        # Save before deleting
        save_json()
        
        selections = listbox.curselection()
        if not selections:
            messagebox.showwarning("No file selected", "Please select one or more session files to delete.")
            return
        files_to_delete = [listbox.get(i) for i in selections]
        if not files_to_delete:
            return
        count = len(files_to_delete)
        if not messagebox.askyesno("Delete Files", f"Are you sure you want to delete the selected file(s)? ({count} file{'s' if count != 1 else ''} will be deleted)"):
            return
        errors = []
        for fname in files_to_delete:
            fpath = os.path.join(session_dir, fname)
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception as e:
                errors.append(f"{fname}: {e}")
        refresh_list()
        if errors:
            messagebox.showerror("Delete Error", "Some files could not be deleted:\n" + '\n'.join(errors))

    delete_btn = tk.Button(button_frame, text="Delete File(s)", command=delete_selected_files)
    delete_btn.pack(side=tk.LEFT, padx=5)
    refresh_btn = tk.Button(button_frame, text="Refresh List", command=refresh_list)
    refresh_btn.pack(side=tk.LEFT, padx=5)
    rename_label = tk.Label(button_frame, text="Double click filenames to rename", fg="#555555", font=("Arial", 9, "italic"))
    rename_label.pack(side=tk.LEFT, padx=5)

    # Information label to the right of the refresh button
    info_label = tk.Label(button_frame, text="Updates are saved automatically", fg="#555555", font=("Arial", 9, "italic"))
    info_label.pack(side=tk.RIGHT, padx=10)

    # Return a cleanup function that saves on tab close
    def cleanup():
        save_json()
    
    # Return both refresh_list and cleanup for external access
    return refresh_list, cleanup
