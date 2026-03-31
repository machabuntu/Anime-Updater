"""
Anime List Frame - Displays user's anime list with editing capabilities
"""

import tkinter as tk
from tkinter import ttk, messagebox
try:
    from tkinter import simpledialog
except ImportError:
    import tkinter.simpledialog as simpledialog
from typing import Dict, List, Any, Optional
import threading
import webbrowser

class AnimeListFrame(ttk.Frame):
    """Frame for displaying and managing anime list"""
    
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.anime_data: Dict[str, List[Dict[str, Any]]] = {}
        self.item_data: Dict[str, Dict[str, Any]] = {}  # Store anime data by item ID
        self.sort_column = None
        self.sort_reverse = False
        self.filtered_data = []  # Store filtered data for sorting
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create frame widgets"""
        # Create main filter frame first (above tabs)
        self._create_filters()
        
        # Status tabs (replacing dropdown) - just the tab bar, no content inside
        self.status_tabs = ttk.Notebook(self)
        self.status_tabs.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        # Create empty tab frames for each status (we won't put content in them)
        self.tab_frames = {}
        self.tab_counters = {}
        status_order = ['watching', 'planned', 'completed', 'on_hold', 'dropped', 'rewatching']
        
        for status in status_order:
            status_display = self.main_window.get_active_client().STATUSES.get(status, status)
            
            # Create empty frame for this tab (content will be outside)
            tab_frame = ttk.Frame(self.status_tabs)
            self.tab_frames[status] = tab_frame
            
            # Add tab with counter placeholder
            self.status_tabs.add(tab_frame, text=f"{status_display} [0]")
            
            # Store counter reference
            self.tab_counters[status] = 0
        
        # Set default to watching tab
        self.status_tabs.select(0)
        self.current_status = 'watching'
        
        # Bind tab change event
        self.status_tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        # Create tree content directly below tabs
        self._create_tab_content()
        
    def _on_tab_changed(self, event=None):
        """Handle tab change"""
        current_tab_index = self.status_tabs.index(self.status_tabs.select())
        status_order = ['watching', 'planned', 'completed', 'on_hold', 'dropped', 'rewatching']
        self.current_status = status_order[current_tab_index]
        self._populate_tree()
    
    def _create_filters(self):
        """Create filter controls"""
        # Filter controls frame (outside of tabs)
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Advanced Search Filters
        # Name search
        ttk.Label(filter_frame, text="Name:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=15)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        search_entry.bind("<KeyRelease>", self._filter_changed)
        
        # Year filter
        ttk.Label(filter_frame, text="Year:").pack(side=tk.LEFT, padx=(0, 5))
        self.year_var = tk.StringVar(value="All")
        year_combo = ttk.Combobox(filter_frame, textvariable=self.year_var, width=8, state="readonly")
        year_combo.pack(side=tk.LEFT, padx=(0, 10))
        year_combo.bind("<<ComboboxSelected>>", self._filter_changed)
        
        # Type filter (static values)
        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=(0, 5))
        self.type_var = tk.StringVar(value="All")
        self.type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var,
                                      values=["All", "TV", "Movie", "OVA", "ONA", "Special", "Music"],
                                      width=8, state="readonly")
        self.type_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.type_combo.bind("<<ComboboxSelected>>", self._filter_changed)
        
        # Score filter
        ttk.Label(filter_frame, text="Score:").pack(side=tk.LEFT, padx=(0, 5))
        self.score_var = tk.StringVar(value="All")
        score_combo = ttk.Combobox(filter_frame, textvariable=self.score_var,
                                  values=["All", "Not Scored", "1+", "2+", "3+", "4+", "5+", "6+", "7+", "8+", "9+", "10"],
                                  width=8, state="readonly")
        score_combo.pack(side=tk.LEFT, padx=(0, 10))
        score_combo.bind("<<ComboboxSelected>>", self._filter_changed)
        
        # Store combo boxes for updating
        self.year_combo = year_combo
        self.score_combo = score_combo
        
        # Clear filters button
        ttk.Button(filter_frame, text="Clear All", command=self._clear_all_filters).pack(side=tk.LEFT)
    
    def _create_tab_content(self):
        """Create content for each tab"""
        # For now, we'll use the main tree for all tabs
        # The filtering will be handled in _populate_tree based on current_status
        
        # Treeview with scrollbars (fill remaining space below tabs)
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Create treeview
        columns = ("Name", "Status", "Progress", "Score", "Type", "Year")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=15)
        
        # Configure tags for anime status coloring
        self._configure_anime_status_tags()
        
        # Configure columns with sorting
        self.tree.heading("#0", text="", anchor=tk.W)
        self.tree.column("#0", width=0, stretch=False)  # Hide tree column
        
        self.tree.heading("Name", text="Anime Name ↕", anchor=tk.W, command=lambda: self._sort_column("Name"))
        self.tree.column("Name", width=300, anchor=tk.W)
        
        self.tree.heading("Status", text="Status ↕", anchor=tk.W, command=lambda: self._sort_column("Status"))
        self.tree.column("Status", width=100, anchor=tk.W)
        
        self.tree.heading("Progress", text="Progress ↕", anchor=tk.CENTER, command=lambda: self._sort_column("Progress"))
        self.tree.column("Progress", width=80, anchor=tk.CENTER)
        
        self.tree.heading("Score", text="Score ↕", anchor=tk.CENTER, command=lambda: self._sort_column("Score"))
        self.tree.column("Score", width=60, anchor=tk.CENTER)
        
        self.tree.heading("Type", text="Type ↕", anchor=tk.W, command=lambda: self._sort_column("Type"))
        self.tree.column("Type", width=80, anchor=tk.W)
        
        self.tree.heading("Year", text="Year ↕", anchor=tk.CENTER, command=lambda: self._sort_column("Year"))
        self.tree.column("Year", width=60, anchor=tk.CENTER)
        
        # Scrollbars
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
    
    def _configure_anime_status_tags(self):
        """Configure tags for anime status coloring based on current theme"""
        # Get the modern style instance from main window to check theme
        modern_style = getattr(self.main_window, 'modern_style', None)
        
        if modern_style and modern_style.is_dark_theme():
            # Dark theme - use a darker, more subtle blue
            highlight_color = "#1A3A52"  # Dark blue-gray that works well on dark backgrounds
        else:
            # Light theme - use the original bright blue
            highlight_color = "#D6E9FF"  # Light blue for light theme
        
        self.tree.tag_configure("non_released", background=highlight_color)
        
        # Context menu for advanced options
        self._create_context_menu()
        self.tree.bind("<Button-3>", self._show_context_menu)
    
    def _create_context_menu(self):
        """Create context menu for treeview"""
        self.context_menu = tk.Menu(self, tearoff=0)
        service_name = getattr(self.main_window.get_active_client(), 'SERVICE_NAME', 'Shikimori')
        self.context_menu.add_command(label=f"Open on {service_name}", command=self._open_on_service)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Mark as Watching", command=lambda: self._change_status_via_main_window("watching"))
        self.context_menu.add_command(label="Mark as Completed", command=lambda: self._change_status_via_main_window("completed"))
        self.context_menu.add_command(label="Mark as On Hold", command=lambda: self._change_status_via_main_window("on_hold"))
        self.context_menu.add_command(label="Mark as Dropped", command=lambda: self._change_status_via_main_window("dropped"))
        self.context_menu.add_command(label="Mark as Rewatching", command=lambda: self._change_status_via_main_window("rewatching"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Add Comment", command=self._add_comment)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Remove from List", command=self._remove_anime)
    
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
        self.type_var.set("All")
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
            "Name": "Anime Name",
            "Status": "Status", 
            "Progress": "Progress",
            "Score": "Score",
            "Type": "Type",
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
        if not self.anime_data:
            return
        
        # Collect all unique years and types
        years = set()
        types = set()
        
        for anime_list in self.anime_data.values():
            for anime_entry in anime_list:
                anime = anime_entry.get('anime', {})
                
                # Extract year
                aired_on = anime.get('aired_on', '')
                if aired_on and len(aired_on) >= 4:
                    years.add(aired_on[:4])
                
                # Extract type
                kind = anime.get('kind', '')
                if kind:
                    types.add(kind.upper())
        
        # Update year dropdown
        year_values = ["All"] + sorted(years, reverse=True)
        self.year_combo['values'] = year_values
        
        # Note: Type dropdown uses static values and is not updated dynamically
    
    def _on_selection_changed(self, event=None):
        """Update info panel when selection changes"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            anime_entry = self.item_data.get(item)
            self.main_window.set_selected_anime(anime_entry)
        else:
            self.main_window.set_selected_anime(None)
    
    def update_list(self, anime_data: Dict[str, List[Dict[str, Any]]]):
        """Update anime list data and refresh display"""
        self.anime_data = anime_data
        self.item_data.clear()  # Clear existing item data
        self._populate_tree()
    
    def clear_list(self):
        """Clear anime list"""
        self.anime_data.clear()
        self._populate_tree()
    
    def _populate_tree(self):
        """Populate treeview with filtered anime data"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not self.anime_data:
            self._update_tab_counters({})
            return
        
        # Get filter values
        search_filter = self.search_var.get().lower() if hasattr(self, 'search_var') else ''
        year_filter = self.year_var.get() if hasattr(self, 'year_var') else 'All'
        type_filter = self.type_var.get() if hasattr(self, 'type_var') else 'All'
        score_filter = self.score_var.get() if hasattr(self, 'score_var') else 'All'
        
        filtered_data = []
        
        # Status mapping for reverse lookup
        status_map = {v: k for k, v in self.main_window.get_active_client().STATUSES.items()}
        
        item_count = 0
        
        # Collect counters for all statuses
        status_counters = {}
        
        # Process each status group
        for status_key, anime_list in self.anime_data.items():
            status_display = self.main_window.get_active_client().STATUSES.get(status_key, status_key)
            
            # Skip if not the current tab's status
            if status_key != self.current_status:
                # Still count for tab counter
                filtered_count = self._count_filtered_anime(anime_list, search_filter, year_filter, type_filter, score_filter)
                status_counters[status_key] = filtered_count
                continue
            
            # Count filtered items for current tab
            filtered_count = self._count_filtered_anime(anime_list, search_filter, year_filter, type_filter, score_filter)
            status_counters[status_key] = filtered_count
            
            # Add items for this status
            for anime_entry in anime_list:
                anime = anime_entry.get('anime', {})
                if not anime:
                    continue
                
                # Apply search filter
                anime_name = anime.get('name', '')
                if search_filter and search_filter not in anime_name.lower():
                    continue
                
                # Apply year filter
                aired_on = anime.get('aired_on', '')
                year = aired_on[:4] if aired_on else '-'
                if year_filter != "All" and year != year_filter:
                    continue
                
                # Apply type filter
                anime_type = anime.get('kind', '').upper()
                if type_filter != "All" and anime_type != type_filter:
                    continue
                
                # Apply score filter
                score = anime_entry.get('score', 0) or 0
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

                # Prepare display values
                progress = f"{anime_entry.get('episodes', 0)}/{anime.get('episodes', '?')}"
                score_display = score if score > 0 else "-"
                
                # Collect filtered data for sorting
                filtered_data.append((
                    anime_name,
                    status_display,
                    progress,
                    score_display,
                    anime_type,
                    year,
                    anime_entry
                ))
        
        # Sort data
        if self.sort_column:
            columns = ("Name", "Status", "Progress", "Score", "Type", "Year")
            col_index = columns.index(self.sort_column)
            
            # Custom sorting for different column types
            if self.sort_column == "Score":
                # Sort by numeric score, treating "-" as 0
                filtered_data.sort(key=lambda x: 0 if x[col_index] == "-" else float(x[col_index]), reverse=self.sort_reverse)
            elif self.sort_column == "Progress":
                # Sort by current episode number
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
            anime_entry = values[-1]  # Last element is the anime entry
            
            # Determine if anime should be colored based on its status
            tags = []
            anime_id = anime_entry.get('anime', {}).get('id')
            
            if anime_id and hasattr(self.main_window, 'anime_matcher'):
                detailed_cache = getattr(self.main_window.anime_matcher, 'detailed_anime_cache', {})
                
                if anime_id in detailed_cache:
                    anime_status = detailed_cache[anime_id].get('status', '').lower()
                    
                    # Color anime that are not released (ongoing, announced, etc.)
                    if anime_status and anime_status not in ('released', 'finished_airing'):
                        tags.append('non_released')
            
            item_id = self.tree.insert("", tk.END, values=values[:-1], tags=tags)
            self.item_data[item_id] = values[-1]
            item_count += 1
        
        # Count all other statuses for tab counters
        for status_key, anime_list in self.anime_data.items():
            if status_key not in status_counters:
                filtered_count = self._count_filtered_anime(anime_list, search_filter, year_filter, type_filter, score_filter)
                status_counters[status_key] = filtered_count
        
        # Update tab counters
        self._update_tab_counters(status_counters)
    
    def _count_filtered_anime(self, anime_list, search_filter, year_filter, type_filter, score_filter):
        """Count anime that match the current filters"""
        count = 0
        for anime_entry in anime_list:
            anime = anime_entry.get('anime', {})
            if not anime:
                continue
            
            # Apply search filter
            anime_name = anime.get('name', '')
            if search_filter and search_filter not in anime_name.lower():
                continue
            
            # Apply year filter
            aired_on = anime.get('aired_on', '')
            year = aired_on[:4] if aired_on else '-'
            if year_filter != "All" and year != year_filter:
                continue
            
            # Apply type filter
            anime_type = anime.get('kind', '').upper()
            if type_filter != "All" and anime_type != type_filter:
                continue
            
            # Apply score filter
            score = anime_entry.get('score', 0) or 0
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
        status_order = ['watching', 'planned', 'completed', 'on_hold', 'dropped', 'rewatching']
        
        for i, status in enumerate(status_order):
            count = status_counters.get(status, 0)
            status_display = self.main_window.get_active_client().STATUSES.get(status, status)
            self.status_tabs.tab(i, text=f"{status_display} [{count}]")
    
    def _get_selected_anime(self) -> Optional[Dict[str, Any]]:
        """Get currently selected anime data"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an anime from the list")
            return None
        
        item = selection[0]
        return self.item_data.get(item)
    
    def _edit_anime(self, event=None):
        """Edit selected anime"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        # Create edit dialog
        dialog = AnimeEditDialog(self, anime_entry, self.main_window)
        self.wait_window(dialog.dialog)
        
        # Refresh list if changes were made
        if dialog.changes_made:
            # For edit dialog, we'll update cache when the dialog saves
            # The dialog will call _update_cache_and_reload itself
            pass
    
    def _update_progress(self):
        """Update progress for selected anime"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        current_episodes = anime_entry.get('episodes', 0)
        total_episodes = anime_entry['anime'].get('episodes', 0)
        
        new_episodes = simpledialog.askinteger(
            "Update Progress",
            f"Current progress: {current_episodes}/{total_episodes or '?'}\\n"
            f"Enter new episode count:",
            initialvalue=current_episodes,
            minvalue=0,
            maxvalue=total_episodes or 9999
        )
        
        if new_episodes is not None and new_episodes != current_episodes:
            self._update_anime_data(anime_entry, episodes=new_episodes)
    
    def _set_score(self):
        """Set score for selected anime"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        current_score = anime_entry.get('score', 0)
        
        new_score = simpledialog.askinteger(
            "Set Score",
            f"Current score: {current_score or 'Not scored'}\\n"
            f"Enter new score (1-10, or 0 to remove):",
            initialvalue=current_score,
            minvalue=0,
            maxvalue=10
        )
        
        if new_score is not None and new_score != current_score:
            self._update_anime_data(anime_entry, score=new_score)
    
    def _change_status(self, new_status: str):
        """Change status of selected anime"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        self._update_anime_data(anime_entry, status=new_status)
    
    def _change_status_via_main_window(self, new_status: str):
        """Change status using main window's mechanism (includes proper notifications)"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        # Set the anime as selected in main window and trigger status change
        self.main_window.set_selected_anime(anime_entry)
        
        # Update the compact status combo to the new status for proper UI update
        if new_status in self.main_window.get_active_client().STATUSES:
            status_display = self.main_window.get_active_client().STATUSES[new_status]
            self.main_window.compact_status_var.set(status_display)
        
        # Trigger the main window's status update method
        self.main_window._update_status(new_status)
    
    def _remove_anime(self):
        """Remove selected anime from list"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        anime_name = anime_entry['anime'].get('name', 'Unknown')
        
        if messagebox.askyesno("Confirm Removal", 
                              f"Are you sure you want to remove '{anime_name}' from your list?"):
            
            def remove_anime():
                try:
                    rate_id = anime_entry['id']
                    success = self.main_window.get_active_client().delete_anime_from_list(rate_id)
                    
                    if success:
                        self.after(0, lambda: messagebox.showinfo("Success", f"'{anime_name}' removed from list"))
                        self.after(0, self.main_window.refresh_anime_list)
                    else:
                        self.after(0, lambda: messagebox.showerror("Error", f"Failed to remove '{anime_name}'"))
                        
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Error", f"Error removing anime: {str(e)}"))
            
            threading.Thread(target=remove_anime, daemon=True).start()
    
    def _update_anime_data(self, anime_entry: Dict[str, Any], **updates):
        """Update anime data on the active service"""
        def update_data():
            try:
                rate_id = anime_entry['id']
                anime_name = anime_entry['anime'].get('name', 'Unknown')
                
                success = self.main_window.get_active_client().update_anime_progress(
                    rate_id, **updates)
                
                if success:
                    # Check if this is a comment update and send telegram notification
                    if 'text' in updates or 'text_html' in updates:
                        comment_text = updates.get('text', '') or updates.get('text_html', '')
                        if comment_text and hasattr(self.main_window, 'telegram_notifier'):
                            username = getattr(self.main_window, 'current_user', {}).get('nickname', 'Unknown')
                            anime_url = anime_entry['anime'].get('url', '')
                            self.main_window.telegram_notifier.send_comment_update(
                                anime_name, comment_text, username, anime_url
                            )
                    else:
                        # Only show popup for non-comment updates
                        self.after(0, lambda: messagebox.showinfo("Success", f"'{anime_name}' updated successfully"))
                    
                    # Update cache directly and reload from cache
                    anime_id = anime_entry['id']
                    self.after(0, lambda: self.main_window._update_cache_and_reload(anime_id, updates))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", f"Failed to update '{anime_name}'"))
                    
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Error updating anime: {str(e)}"))
        
        threading.Thread(target=update_data, daemon=True).start()
    
    def _add_comment(self):
        """Add comment to selected anime"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        anime_name = anime_entry['anime'].get('name', 'Unknown')
        current_comment = anime_entry.get('text', '') or anime_entry.get('text_html', '')
        
        # Create comment dialog
        dialog = CommentDialog(self, anime_name, current_comment)
        self.wait_window(dialog.dialog)
        
        # If comment was saved, update the anime
        if dialog.comment_saved and dialog.comment_text is not None:
            comment_text = dialog.comment_text.strip()
            
            # Update both text and text_html fields
            updates = {
                'text': comment_text,
                'text_html': comment_text  # For now, store same text in both fields
            }
            
            self._update_anime_data(anime_entry, **updates)
    
    def _open_on_service(self):
        """Open selected anime on the active service's website"""
        anime_entry = self._get_selected_anime()
        if not anime_entry:
            return
        
        anime_data = anime_entry.get('anime', {})
        anime_url = anime_data.get('url')
        client = self.main_window.get_active_client()
        
        if anime_url:
            if anime_url.startswith('/'):
                anime_url = client.SERVICE_URL + anime_url
            
            try:
                webbrowser.open(anime_url)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open browser: {str(e)}")
        else:
            messagebox.showwarning("Warning", "No URL found for this anime")
    
    def _find_and_update_anime_entry(self, anime_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find and update anime entry in the main data structure"""
        anime_list_data = self.main_window.get_anime_list_data()
        
        for status_key, anime_list in anime_list_data.items():
            for entry in anime_list:
                if entry.get('id') == anime_id:
                    # Update the actual entry in the data structure
                    entry.update(updates)
                    return entry
        
        return None
    
    def _sync_item_data_with_updated_entry(self, updated_entry: Dict[str, Any]):
        """Sync item_data with the updated entry to maintain reference consistency"""
        anime_id = updated_entry.get('id')
        if not anime_id:
            return
            
        # Find and update the item_data reference to point to the updated entry
        for item_id, entry in self.item_data.items():
            if entry.get('id') == anime_id:
                self.item_data[item_id] = updated_entry
                break


class AnimeEditDialog:
    """Dialog for editing anime details"""
    
    def __init__(self, parent, anime_entry: Dict[str, Any], main_window):
        self.parent = parent
        self.anime_entry = anime_entry
        self.main_window = main_window
        self.changes_made = False
        
        anime = anime_entry['anime']
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit - {anime.get('name', 'Unknown')}")
        self.dialog.geometry("400x300")
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
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - 300) // 2
        self.dialog.geometry(f"400x300+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        anime = self.anime_entry['anime']
        
        # Anime name (read-only)
        ttk.Label(main_frame, text="Anime:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        ttk.Label(main_frame, text=anime.get('name', 'Unknown'), 
                 font=("Arial", 10, "bold")).grid(row=0, column=1, sticky=tk.W, pady=(0, 5))
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var,
                                   values=list(self.main_window.get_active_client().STATUSES.values()),
                                   state="readonly", width=20)
        status_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Set current status
        current_status = self.anime_entry.get('status', '')
        if current_status in self.main_window.get_active_client().STATUSES:
            self.status_var.set(self.main_window.get_active_client().STATUSES[current_status])
        
        # Episodes
        ttk.Label(main_frame, text="Episodes:").grid(row=2, column=0, sticky=tk.W, pady=5)
        episodes_frame = ttk.Frame(main_frame)
        episodes_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        self.episodes_var = tk.IntVar(value=self.anime_entry.get('episodes', 0))
        episodes_spin = ttk.Spinbox(episodes_frame, textvariable=self.episodes_var,
                                   from_=0, to=anime.get('episodes', 9999), width=10)
        episodes_spin.pack(side=tk.LEFT)
        
        total_episodes = anime.get('episodes', 0)
        if total_episodes:
            ttk.Label(episodes_frame, text=f"/ {total_episodes}").pack(side=tk.LEFT, padx=(5, 0))
        
        # Score
        ttk.Label(main_frame, text="Score:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.score_var = tk.IntVar(value=self.anime_entry.get('score', 0))
        score_spin = ttk.Spinbox(main_frame, textvariable=self.score_var,
                                from_=0, to=10, width=10)
        score_spin.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Save", command=self._save_changes).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)
        
        # Configure grid weights
        main_frame.grid_columnconfigure(1, weight=1)
    
    def _save_changes(self):
        """Save changes to anime"""
        # Get new values
        new_status_display = self.status_var.get()
        new_episodes = self.episodes_var.get()
        new_score = self.score_var.get()
        
        # Convert status display back to API key
        status_map = {v: k for k, v in self.main_window.get_active_client().STATUSES.items()}
        new_status = status_map.get(new_status_display)
        
        # Check for changes
        current_status = self.anime_entry.get('status', '')
        current_episodes = self.anime_entry.get('episodes', 0)
        current_score = self.anime_entry.get('score', 0)
        
        updates = {}
        if new_status != current_status:
            updates['status'] = new_status
        if new_episodes != current_episodes:
            updates['episodes'] = new_episodes
        if new_score != current_score:
            updates['score'] = new_score
        
        if not updates:
            self.dialog.destroy()
            return
        
        # Apply updates
        def update_anime():
            try:
                rate_id = self.anime_entry['id']
                success = self.main_window.get_active_client().update_anime_progress(
                    rate_id, **updates)
                
                if success:
                    self.changes_made = True
                    # Update cache directly and reload from cache
                    anime_id = self.anime_entry['id']
                    self.dialog.after(0, lambda: self.parent.main_window._update_cache_and_reload(anime_id, updates))
                    self.dialog.after(0, self.dialog.destroy)
                else:
                    self.dialog.after(0, lambda: messagebox.showerror("Error", "Failed to update anime"))
                    
            except Exception as e:
                self.dialog.after(0, lambda: messagebox.showerror("Error", f"Error updating anime: {str(e)}"))
        
        threading.Thread(target=update_anime, daemon=True).start()


class CommentDialog:
    """Dialog for adding/editing comments"""
    
    def __init__(self, parent, anime_name, current_comment=""):
        self.parent = parent
        self.anime_name = anime_name
        self.current_comment = current_comment
        self.comment_saved = False
        self.comment_text = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Comment - {anime_name}")
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
        title_label = ttk.Label(main_frame, text=f"Comment for: {self.anime_name}", 
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
