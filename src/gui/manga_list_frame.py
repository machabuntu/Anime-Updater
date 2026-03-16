"""
Manga List Frame for Anime Updater
Displays and manages user's manga list with filtering and editing capabilities
"""

import tkinter as tk
from tkinter import ttk, messagebox
try:
    from tkinter import simpledialog
except ImportError:
    import tkinter.simpledialog as simpledialog
import threading
import webbrowser
from typing import Dict, List, Any, Optional

class MangaListFrame(ttk.Frame):
    """Frame for displaying and managing manga list"""
    
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.manga_data: Dict[str, List[Dict[str, Any]]] = {}
        self.item_data = {}  # Mapping from tree items to manga data
        
        # Current filter/tab state
        self.current_status = 'watching'  # Default to reading (watching in API)
        
        # Sorting state
        self.sort_column = None
        self.sort_reverse = False
        
        self._create_widgets()
        
    def _create_widgets(self):
        """Create manga list widgets"""
        # Status tabs (no rewatching tab for manga)
        self._create_status_tabs()
        
        # Filters frame
        self._create_filters()
        
        # Manga list treeview
        self._create_manga_tree()
        
    def _create_status_tabs(self):
        """Create status tabs for filtering by manga status"""
        self.status_tabs = ttk.Notebook(self, style='TNotebook')
        self.status_tabs.pack(fill=tk.X, pady=(0, 5))
        
        # Status order (no rewatching for manga)
        # Note: API uses 'watching' for currently reading manga
        status_order = ['watching', 'planned', 'completed', 'on_hold', 'dropped']
        status_names = {
            'watching': 'Reading',
            'planned': 'Plan to Read', 
            'completed': 'Completed',
            'on_hold': 'On Hold',
            'dropped': 'Dropped'
        }
        
        self.status_frames = {}
        
        for status in status_order:
            # Create frame for each status
            frame = ttk.Frame(self.status_tabs)
            self.status_frames[status] = frame
            
            # Add tab with initial count
            tab_text = f"{status_names[status]} [0]"
            self.status_tabs.add(frame, text=tab_text)
        
        # Bind tab change event
        self.status_tabs.bind("<<NotebookTabChanged>>", self._on_status_tab_changed)
    
    def _on_status_tab_changed(self, event=None):
        """Handle status tab change"""
        current_tab = self.status_tabs.index(self.status_tabs.select())
        status_order = ['watching', 'planned', 'completed', 'on_hold', 'dropped']
        
        if 0 <= current_tab < len(status_order):
            self.current_status = status_order[current_tab]
            self._populate_tree()
    
    def _create_filters(self):
        """Create filter controls"""
        filters_frame = ttk.Frame(self)
        filters_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Search filter
        ttk.Label(filters_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filters_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        search_entry.bind('<KeyRelease>', self._filter_changed)
        
        # Year filter
        ttk.Label(filters_frame, text="Year:").pack(side=tk.LEFT, padx=(10, 5))
        
        self.year_var = tk.StringVar(value="All")
        self.year_combo = ttk.Combobox(filters_frame, textvariable=self.year_var,
                                      values=["All"], width=8, state="readonly")
        self.year_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.year_combo.bind('<<ComboboxSelected>>', self._filter_changed)
        
        # Score filter  
        ttk.Label(filters_frame, text="Score:").pack(side=tk.LEFT, padx=(10, 5))
        
        self.score_var = tk.StringVar(value="All")
        score_combo = ttk.Combobox(filters_frame, textvariable=self.score_var,
                                  values=["All", "Not Scored", "9+ Excellent", "8+ Great", 
                                         "7+ Good", "6+ Fine", "5+ Average", "4+ Bad", "1+ Awful"],
                                  width=12, state="readonly")
        score_combo.pack(side=tk.LEFT, padx=(0, 10))
        score_combo.bind('<<ComboboxSelected>>', self._filter_changed)
        
        # Clear filters button
        ttk.Button(filters_frame, text="Clear All", 
                  command=self._clear_all_filters).pack(side=tk.LEFT, padx=(10, 0))
    
    def _create_manga_tree(self):
        """Create manga list treeview"""
        # Container frame for treeview and scrollbars
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Create treeview with manga-specific columns (separate chapters and volumes)
        columns = ("Name", "Status", "Chapters", "Volumes", "Score", "Year")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", 
                                style='Modern.Treeview')
        
        # Configure column headings and widths
        self.tree.heading("Name", text="Manga Name ↕", command=lambda: self._sort_column("Name"))
        self.tree.heading("Status", text="Status ↕", command=lambda: self._sort_column("Status"))
        self.tree.heading("Chapters", text="Chapters ↕", command=lambda: self._sort_column("Chapters"))
        self.tree.heading("Volumes", text="Volumes ↕", command=lambda: self._sort_column("Volumes"))
        self.tree.heading("Score", text="Score ↕", command=lambda: self._sort_column("Score"))
        self.tree.heading("Year", text="Year ↕", command=lambda: self._sort_column("Year"))
        
        # Set column widths
        self.tree.column("Name", width=300, minwidth=200)
        self.tree.column("Status", width=120, minwidth=100)
        self.tree.column("Chapters", width=100, minwidth=80)
        self.tree.column("Volumes", width=100, minwidth=80)
        self.tree.column("Score", width=80, minwidth=60)
        self.tree.column("Year", width=80, minwidth=60)
        
        # Create scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind selection change to update info panel
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        
        # Context menu for advanced options
        self._create_context_menu()
        self.tree.bind("<Button-3>", self._show_context_menu)
    
    def _create_context_menu(self):
        """Create context menu for treeview"""
        self.context_menu = tk.Menu(self, tearoff=0)
        service_name = getattr(self.main_window.get_active_client(), 'SERVICE_NAME', 'Shikimori')
        self.context_menu.add_command(label=f"Open on {service_name}", command=self._open_on_service)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Mark as Reading", command=lambda: self._change_status_via_main_window("watching"))
        self.context_menu.add_command(label="Mark as Completed", command=lambda: self._change_status_via_main_window("completed"))
        self.context_menu.add_command(label="Mark as On Hold", command=lambda: self._change_status_via_main_window("on_hold"))
        self.context_menu.add_command(label="Mark as Dropped", command=lambda: self._change_status_via_main_window("dropped"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Add Comment", command=self._add_comment)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Remove from List", command=self._remove_manga)
    
    def _show_context_menu(self, event):
        """Show context menu"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def _filter_changed(self, event=None):
        """Handle filter changes"""
        self._update_filter_options()
        self._populate_tree()
    
    def _clear_all_filters(self):
        """Clear all filters"""
        self.search_var.set("")
        self.year_var.set("All")
        self.score_var.set("All")
        self._populate_tree()
        
    def _sort_column(self, column):
        """Sort tree by column"""
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        # Update column headers to show sort direction
        self._update_column_headers()
        
        # Re-populate with sorting
        self._populate_tree()
    
    def _update_column_headers(self):
        """Update column headers to show sort direction"""
        headers = {
            "Name": "Manga Name",
            "Status": "Status", 
            "Chapters": "Chapters",
            "Volumes": "Volumes",
            "Score": "Score",
            "Year": "Year"
        }
        
        for col, base_text in headers.items():
            if col == self.sort_column:
                arrow = " ↑" if not self.sort_reverse else " ↓"
                text = base_text + arrow
            else:
                text = base_text + " ↕"
            self.tree.heading(col, text=text)
    
    def _update_filter_options(self):
        """Update filter dropdown options based on current data"""
        if not self.manga_data:
            return
        
        # Collect all unique years
        years = set()
        
        for manga_list in self.manga_data.values():
            for manga_entry in manga_list:
                manga = manga_entry.get('manga', {})
                
                # Extract year
                aired_on = manga.get('aired_on', '')
                if aired_on and len(aired_on) >= 4:
                    years.add(aired_on[:4])
        
        # Update year dropdown
        year_values = ["All"] + sorted(years, reverse=True)
        self.year_combo['values'] = year_values
    
    def _on_selection_changed(self, event=None):
        """Update info panel when selection changes"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            manga_entry = self.item_data.get(item)
            self.main_window.set_selected_manga(manga_entry)
        else:
            self.main_window.set_selected_manga(None)
    
    def update_list(self, manga_data: Dict[str, List[Dict[str, Any]]]):
        """Update manga list data and refresh display"""
        self.manga_data = manga_data
        self.item_data.clear()  # Clear existing item data
        self._populate_tree()
    
    def clear_list(self):
        """Clear manga list"""
        self.manga_data.clear()
        self._populate_tree()
    
    def _populate_tree(self):
        """Populate treeview with filtered manga data"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not self.manga_data:
            self._update_tab_counters({})
            return
        
        # Get filter values
        search_filter = self.search_var.get().lower() if hasattr(self, 'search_var') else ''
        year_filter = self.year_var.get() if hasattr(self, 'year_var') else 'All'
        score_filter = self.score_var.get() if hasattr(self, 'score_var') else 'All'
        
        filtered_data = []
        
        # Status mapping for reverse lookup
        status_map = {v: k for k, v in self.main_window.get_active_client().MANGA_STATUSES.items()}
        
        item_count = 0
        
        # Collect counters for all statuses
        status_counters = {}
        
        # Process each status group
        for status_key, manga_list in self.manga_data.items():
            status_display = self.main_window.get_active_client().MANGA_STATUSES.get(status_key, status_key)
            
            # Skip if not the current tab's status
            if status_key != self.current_status:
                # Still count for tab counter
                filtered_count = self._count_filtered_manga(manga_list, search_filter, year_filter, score_filter)
                status_counters[status_key] = filtered_count
                continue
            
            # Count filtered items for current tab
            filtered_count = self._count_filtered_manga(manga_list, search_filter, year_filter, score_filter)
            status_counters[status_key] = filtered_count
            
            # Add items for this status
            for manga_entry in manga_list:
                manga = manga_entry.get('manga', {})
                if not manga:
                    continue
                
                # Apply search filter
                manga_name = manga.get('name', '')
                if search_filter and search_filter not in manga_name.lower():
                    continue
                
                # Apply year filter
                aired_on = manga.get('aired_on', '')
                year = aired_on[:4] if aired_on else '-'
                if year_filter != "All" and year != year_filter:
                    continue
                
                # Apply score filter
                score = manga_entry.get('score', 0) or 0
                if score_filter != "All":
                    if score_filter == "Not Scored":
                        if score > 0:
                            continue
                    else:
                        try:
                            score_threshold = int(score_filter[0])
                            if score_threshold and score < score_threshold:
                                continue
                        except (ValueError, IndexError):
                            continue

                # Prepare display values for manga (separate chapters and volumes)
                chapters = manga_entry.get('chapters', 0)
                total_chapters = manga.get('chapters', '?')
                volumes = manga_entry.get('volumes', 0)
                total_volumes = manga.get('volumes', '?')
                
                # Show chapters and volumes in separate columns
                chapters_display = f"{chapters}/{total_chapters}"
                volumes_display = f"{volumes}/{total_volumes}"
                score_display = score if score > 0 else "-"
                
                # Collect filtered data for sorting
                filtered_data.append((
                    manga_name,
                    status_display,
                    chapters_display,
                    volumes_display,
                    score_display,
                    year,
                    manga_entry
                ))
        
        # Sort data
        if self.sort_column:
            columns = ("Name", "Status", "Chapters", "Volumes", "Score", "Year")
            col_index = columns.index(self.sort_column)
            
            # Custom sorting for different column types
            if self.sort_column == "Score":
                # Sort by numeric score, treating "-" as 0
                filtered_data.sort(key=lambda x: 0 if x[col_index] == "-" else float(x[col_index]), reverse=self.sort_reverse)
            elif self.sort_column == "Chapters":
                # Sort by current chapter number
                filtered_data.sort(key=lambda x: int(x[col_index].split('/')[0]), reverse=self.sort_reverse)
            elif self.sort_column == "Volumes":
                # Sort by current volume number
                filtered_data.sort(key=lambda x: int(x[col_index].split('/')[0]), reverse=self.sort_reverse)
            elif self.sort_column == "Year":
                # Sort by year, treating "-" as 0
                filtered_data.sort(key=lambda x: 0 if x[col_index] == "-" else int(x[col_index]), reverse=self.sort_reverse)
            else:
                # Default string sorting
                filtered_data.sort(key=lambda x: x[col_index], reverse=self.sort_reverse)
        else:
            # Sort by name by default
            filtered_data.sort(key=lambda x: x[0])  # Sort by Name (index 0)
        
        # Insert sorted and filtered data into the tree
        for values in filtered_data:
            manga_entry = values[-1]  # Last element is the manga entry
            
            # Extract display values (excluding manga_entry at the end)
            display_values = values[:-1]  # Name, Status, Chapters, Volumes, Score, Year
            
            item_id = self.tree.insert("", tk.END, values=display_values)
            self.item_data[item_id] = manga_entry
            item_count += 1
        
        # Count all other statuses for tab counters
        for status_key, manga_list in self.manga_data.items():
            if status_key not in status_counters:
                filtered_count = self._count_filtered_manga(manga_list, search_filter, year_filter, score_filter)
                status_counters[status_key] = filtered_count
        
        # Update tab counters
        self._update_tab_counters(status_counters)
    
    def _count_filtered_manga(self, manga_list, search_filter, year_filter, score_filter):
        """Count manga that match the current filters"""
        count = 0
        for manga_entry in manga_list:
            manga = manga_entry.get('manga', {})
            if not manga:
                continue
            
            # Apply search filter
            manga_name = manga.get('name', '')
            if search_filter and search_filter not in manga_name.lower():
                continue
            
            # Apply year filter
            aired_on = manga.get('aired_on', '')
            year = aired_on[:4] if aired_on else '-'
            if year_filter != "All" and year != year_filter:
                continue
            
            # Apply score filter
            score = manga_entry.get('score', 0) or 0
            if score_filter != "All":
                if score_filter == "Not Scored":
                    if score > 0:
                        continue
                else:
                    try:
                        score_threshold = int(score_filter[0])
                        if score_threshold and score < score_threshold:
                            continue
                    except (ValueError, IndexError):
                        continue
            
            count += 1
        return count
    
    def _update_tab_counters(self, status_counters):
        """Update the counter display on each tab"""
        status_order = ['watching', 'planned', 'completed', 'on_hold', 'dropped']
        
        for i, status in enumerate(status_order):
            count = status_counters.get(status, 0)
            status_display = self.main_window.get_active_client().MANGA_STATUSES.get(status, status)
            self.status_tabs.tab(i, text=f"{status_display} [{count}]")
    
    def _get_selected_manga(self) -> Optional[Dict[str, Any]]:
        """Get currently selected manga data"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a manga from the list")
            return None
        
        item = selection[0]
        return self.item_data.get(item)
    
    def _edit_manga(self, event=None):
        """Edit selected manga"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        # Create edit dialog
        dialog = MangaEditDialog(self, manga_entry, self.main_window)
        self.wait_window(dialog.dialog)
        
        # Refresh list if changes were made
        if dialog.changes_made:
            pass
    
    def _update_progress(self):
        """Update progress for selected manga"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        current_chapters = manga_entry.get('chapters', 0)
        total_chapters = manga_entry['manga'].get('chapters', 0)
        
        new_chapters = simpledialog.askinteger(
            "Update Progress",
            f"Current progress: {current_chapters}/{total_chapters or '?'} chapters\n"
            f"Enter new chapter count:",
            initialvalue=current_chapters,
            minvalue=0,
            maxvalue=total_chapters or 9999
        )
        
        if new_chapters is not None and new_chapters != current_chapters:
            self._update_manga_data(manga_entry, chapters=new_chapters)
    
    def _set_score(self):
        """Set score for selected manga"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        current_score = manga_entry.get('score', 0)
        
        new_score = simpledialog.askinteger(
            "Set Score",
            f"Current score: {current_score or 'Not scored'}\n"
            f"Enter new score (1-10, or 0 to remove):",
            initialvalue=current_score,
            minvalue=0,
            maxvalue=10
        )
        
        if new_score is not None and new_score != current_score:
            self._update_manga_data(manga_entry, score=new_score)
    
    def _change_status(self, new_status: str):
        """Change status of selected manga"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        self._update_manga_data(manga_entry, status=new_status)
    
    def _change_status_via_main_window(self, new_status: str):
        """Change status using main window's mechanism (includes proper notifications)"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        # Set the manga as selected in main window and trigger status change
        self.main_window.set_selected_manga(manga_entry)
        
        # Update the compact status combo to the new status for proper UI update
        if new_status in self.main_window.get_active_client().MANGA_STATUSES:
            status_display = self.main_window.get_active_client().MANGA_STATUSES[new_status]
            self.main_window.compact_status_var.set(status_display)
        
        # Trigger the main window's status update method
        self.main_window._update_status(new_status)
    
    def _remove_manga(self):
        """Remove selected manga from list"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        manga_name = manga_entry['manga'].get('name', 'Unknown')
        
        if messagebox.askyesno("Confirm Removal", 
                              f"Are you sure you want to remove '{manga_name}' from your list?"):
            
            def remove_manga():
                try:
                    rate_id = manga_entry['id']
                    success = self.main_window.get_active_client().delete_manga_from_list(rate_id)
                    
                    if success:
                        self.after(0, lambda: messagebox.showinfo("Success", f"'{manga_name}' removed from list"))
                        self.after(0, self.main_window.refresh_manga_list)
                    else:
                        self.after(0, lambda: messagebox.showerror("Error", f"Failed to remove '{manga_name}'"))
                        
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Error", f"Error removing manga: {str(e)}"))
            
            threading.Thread(target=remove_manga, daemon=True).start()
    
    def _update_manga_data(self, manga_entry: Dict[str, Any], **updates):
        """Update manga data on the active service"""
        def update_data():
            try:
                rate_id = manga_entry['id']
                manga_name = manga_entry['manga'].get('name', 'Unknown')
                
                success = self.main_window.get_active_client().update_manga_progress(
                    rate_id, **updates)
                
                if success:
                    # Check if this is a comment update and send telegram notification
                    if 'text' in updates or 'text_html' in updates:
                        comment_text = updates.get('text', '') or updates.get('text_html', '')
                        if comment_text and hasattr(self.main_window, 'telegram_notifier'):
                            username = getattr(self.main_window, 'current_user', {}).get('nickname', 'Unknown')
                            manga_url = manga_entry['manga'].get('url', '')
                            self.main_window.telegram_notifier.send_comment_update(
                                manga_name, comment_text, username, manga_url
                            )
                    else:
                        # Only show popup for non-comment updates
                        self.after(0, lambda: messagebox.showinfo("Success", f"'{manga_name}' updated successfully"))
                    
                    # Update cache directly and reload from cache
                    manga_id = manga_entry['id']
                    self.after(0, lambda: self.main_window._update_manga_cache_and_reload(manga_id, updates))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", f"Failed to update '{manga_name}'"))
                    
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Error updating manga: {str(e)}"))
        
        threading.Thread(target=update_data, daemon=True).start()
    
    def _add_comment(self):
        """Add comment to selected manga"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        manga_name = manga_entry['manga'].get('name', 'Unknown')
        current_comment = manga_entry.get('text', '') or manga_entry.get('text_html', '')
        
        # Create comment dialog
        dialog = MangaCommentDialog(self, manga_name, current_comment)
        self.wait_window(dialog.dialog)
        
        # If comment was saved, update the manga
        if dialog.comment_saved and dialog.comment_text is not None:
            comment_text = dialog.comment_text.strip()
            
            # Update both text and text_html fields
            updates = {
                'text': comment_text,
                'text_html': comment_text  # For now, store same text in both fields
            }
            
            self._update_manga_data(manga_entry, **updates)
    
    def _open_on_service(self):
        """Open selected manga on the active service's website"""
        manga_entry = self._get_selected_manga()
        if not manga_entry:
            return
        
        manga_data = manga_entry.get('manga', {})
        manga_url = manga_data.get('url')
        client = self.main_window.get_active_client()
        
        if manga_url:
            if manga_url.startswith('/'):
                manga_url = client.SERVICE_URL + manga_url
            
            try:
                webbrowser.open(manga_url)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open browser: {str(e)}")
        else:
            messagebox.showwarning("Warning", "No URL found for this manga")


class MangaEditDialog:
    """Dialog for editing manga details"""
    
    def __init__(self, parent, manga_entry: Dict[str, Any], main_window):
        self.parent = parent
        self.manga_entry = manga_entry
        self.main_window = main_window
        self.changes_made = False
        
        manga = manga_entry['manga']
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit - {manga.get('name', 'Unknown')}")
        self.dialog.geometry("400x350")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self._center_dialog()
        
        self._create_widgets()
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 400) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - 350) // 2
        self.dialog.geometry(f"400x350+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        manga = self.manga_entry['manga']
        
        # Manga name (read-only)
        ttk.Label(main_frame, text="Manga:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        ttk.Label(main_frame, text=manga.get('name', 'Unknown'), 
                 font=("Arial", 10, "bold")).grid(row=0, column=1, sticky=tk.W, pady=(0, 5))
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var,
                                   values=list(self.main_window.get_active_client().MANGA_STATUSES.values()),
                                   state="readonly", width=20)
        status_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Set current status
        current_status = self.manga_entry.get('status', '')
        if current_status in self.main_window.get_active_client().MANGA_STATUSES:
            self.status_var.set(self.main_window.get_active_client().MANGA_STATUSES[current_status])
        
        # Chapters
        ttk.Label(main_frame, text="Chapters:").grid(row=2, column=0, sticky=tk.W, pady=5)
        chapters_frame = ttk.Frame(main_frame)
        chapters_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        self.chapters_var = tk.IntVar(value=self.manga_entry.get('chapters', 0))
        chapters_spin = ttk.Spinbox(chapters_frame, textvariable=self.chapters_var,
                                   from_=0, to=manga.get('chapters', 9999), width=10)
        chapters_spin.pack(side=tk.LEFT)
        
        total_chapters = manga.get('chapters', 0)
        if total_chapters:
            ttk.Label(chapters_frame, text=f"/ {total_chapters}").pack(side=tk.LEFT, padx=(5, 0))
        
        # Volumes
        ttk.Label(main_frame, text="Volumes:").grid(row=3, column=0, sticky=tk.W, pady=5)
        volumes_frame = ttk.Frame(main_frame)
        volumes_frame.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        self.volumes_var = tk.IntVar(value=self.manga_entry.get('volumes', 0))
        volumes_spin = ttk.Spinbox(volumes_frame, textvariable=self.volumes_var,
                                  from_=0, to=manga.get('volumes', 9999), width=10)
        volumes_spin.pack(side=tk.LEFT)
        
        total_volumes = manga.get('volumes', 0)
        if total_volumes:
            ttk.Label(volumes_frame, text=f"/ {total_volumes}").pack(side=tk.LEFT, padx=(5, 0))
        
        # Score
        ttk.Label(main_frame, text="Score:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.score_var = tk.IntVar(value=self.manga_entry.get('score', 0))
        score_spin = ttk.Spinbox(main_frame, textvariable=self.score_var,
                                from_=0, to=10, width=10)
        score_spin.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Save", command=self._save_changes).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)
        
        # Configure grid weights
        main_frame.grid_columnconfigure(1, weight=1)
    
    def _save_changes(self):
        """Save changes to manga"""
        # Get new values
        new_status_display = self.status_var.get()
        new_chapters = self.chapters_var.get()
        new_volumes = self.volumes_var.get()
        new_score = self.score_var.get()
        
        # Convert status display back to API key
        status_map = {v: k for k, v in self.main_window.get_active_client().MANGA_STATUSES.items()}
        new_status = status_map.get(new_status_display)
        
        # Check what changed
        changes = {}
        if new_chapters != self.manga_entry.get('chapters', 0):
            changes['chapters'] = new_chapters
        if new_volumes != self.manga_entry.get('volumes', 0):
            changes['volumes'] = new_volumes
        if new_score != self.manga_entry.get('score', 0):
            changes['score'] = new_score
        if new_status != self.manga_entry.get('status'):
            changes['status'] = new_status
        
        if changes:
            def update_manga():
                try:
                    rate_id = self.manga_entry['id']
                    manga_name = self.manga_entry['manga'].get('name', 'Unknown')
                    
                    success = self.main_window.get_active_client().update_manga_progress(
                        rate_id, **changes)
                    
                    if success:
                        self.changes_made = True
                        # Update cache and reload
                        manga_id = self.manga_entry['id']
                        self.main_window._update_manga_cache_and_reload(manga_id, changes)
                        
                        self.dialog.after(0, lambda: messagebox.showinfo("Success", f"'{manga_name}' updated successfully"))
                        self.dialog.after(0, self.dialog.destroy)
                    else:
                        self.dialog.after(0, lambda: messagebox.showerror("Error", f"Failed to update '{manga_name}'"))
                        
                except Exception as e:
                    self.dialog.after(0, lambda: messagebox.showerror("Error", f"Error updating manga: {str(e)}"))
            
            threading.Thread(target=update_manga, daemon=True).start()
        else:
            self.dialog.destroy()


class MangaCommentDialog:
    """Dialog for adding/editing manga comments"""
    
    def __init__(self, parent, manga_name, current_comment=""):
        self.parent = parent
        self.manga_name = manga_name
        self.current_comment = current_comment
        self.comment_saved = False
        self.comment_text = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Comment - {manga_name}")
        self.dialog.geometry("500x100")  # Start small, will be resized dynamically
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self._center_dialog()
        
        self._create_widgets()
        
        # Calculate and set dynamic height after all content is added
        self.dialog.after(1, self._set_dynamic_height)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 500) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - 400) // 2
        self.dialog.geometry(f"500x400+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text=f"Comment for: {self.manga_name}", 
                               font=("Arial", 12, "bold"))
        title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Text area with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.text_widget = tk.Text(text_frame, wrap=tk.WORD, width=60, height=15)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Insert current comment
        if self.current_comment:
            self.text_widget.insert(tk.END, self.current_comment)
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(buttons_frame, text="Save", command=self._save_comment).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(buttons_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(buttons_frame, text="Clear", command=self._clear_comment).pack(side=tk.LEFT)
        
        # Focus on text widget
        self.text_widget.focus_set()
    
    def _save_comment(self):
        """Save the comment"""
        self.comment_text = self.text_widget.get("1.0", tk.END).strip()
        self.comment_saved = True
        self.dialog.destroy()
    
    def _clear_comment(self):
        """Clear the comment text"""
        self.text_widget.delete("1.0", tk.END)
    
    def _set_dynamic_height(self):
        """Calculate and set dynamic height based on content"""
        try:
            # Update all widgets to get accurate measurements
            self.dialog.update_idletasks()
            
            # Get the required height of the main frame
            main_frame = self.dialog.winfo_children()[0]  # First child is main_frame
            required_height = main_frame.winfo_reqheight() + 40  # Add padding
            
            # Set minimum height and maximum height
            min_height = 300
            max_height = 600
            final_height = max(min_height, min(max_height, required_height))
            
            # Update geometry with new height
            x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 500) // 2
            y = self.parent.winfo_rooty() + (self.parent.winfo_height() - final_height) // 2
            self.dialog.geometry(f"500x{final_height}+{x}+{y}")
            
        except Exception as e:
            # Fallback to fixed height if calculation fails
            print(f"Error calculating dynamic height: {e}")
            self.dialog.geometry("500x400")
