"""
Search Frame - Search for anime and add to list
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Any, Optional
import threading

class SearchFrame(ttk.Frame):
    """Frame for searching and adding anime"""
    
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.search_results: List[Dict[str, Any]] = []
        self.item_data: Dict[str, Dict[str, Any]] = {}  # Store anime data by item ID
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create frame widgets"""
        # Search controls
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(search_frame, text="Search anime:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 5))
        search_entry.bind("<Return>", self._search_anime)
        
        self.search_button = ttk.Button(search_frame, text="Search", command=self._search_anime)
        self.search_button.pack(side=tk.LEFT)
        
        # Results frame
        results_frame = ttk.LabelFrame(self, text="Search Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Treeview for results
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ("Name", "Type", "Episodes", "Year")
        self.results_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=12)
        
        # Configure columns
        self.results_tree.heading("#0", text="", anchor=tk.W)
        self.results_tree.column("#0", width=0, stretch=False)
        
        self.results_tree.heading("Name", text="Anime Name", anchor=tk.W, command=lambda: self._sort_tree('Name', False))
        self.results_tree.column("Name", width=300, anchor=tk.W)
        
        self.results_tree.heading("Type", text="Type", anchor=tk.W, command=lambda: self._sort_tree('Type', False))
        self.results_tree.column("Type", width=80, anchor=tk.W)
        
        self.results_tree.heading("Episodes", text="Episodes", anchor=tk.CENTER, command=lambda: self._sort_tree('Episodes', False))
        self.results_tree.column("Episodes", width=80, anchor=tk.CENTER)
        
        self.results_tree.heading("Year", text="Year", anchor=tk.CENTER, command=lambda: self._sort_tree('Year', False))
        self.results_tree.column("Year", width=60, anchor=tk.CENTER)
        
        # Scrollbars for results
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack results treeview and scrollbars
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click
        self.results_tree.bind("<Double-1>", self._add_selected_anime)
        
        # Add controls
        add_frame = ttk.Frame(results_frame)
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(add_frame, text="Add to list as:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_var = tk.StringVar(value="Plan to Watch")
        status_combo = ttk.Combobox(add_frame, textvariable=self.status_var,
                                   values=list(self.main_window.get_active_client().STATUSES.values()),
                                   state="readonly", width=15)
        status_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        self.add_button = ttk.Button(add_frame, text="Add Selected", 
                                    command=self._add_selected_anime, state=tk.DISABLED)
        self.add_button.pack(side=tk.LEFT)
        
        # Status label
        self.status_label = ttk.Label(self, text="Enter search term and click Search")
        self.status_label.pack(pady=5)
    
    def _search_anime(self, event=None):
        """Search for anime"""
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Warning", "Please enter a search term")
            return
        
        # Disable search button and show loading
        self.search_button.config(state=tk.DISABLED, text="Searching...")
        self.status_label.config(text="Searching...")
        self.add_button.config(state=tk.DISABLED)
        
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        def search_thread():
            try:
                # Perform search
                results = self.main_window.get_active_client().search_anime(query)
                
                # Update UI on main thread
                self.after(0, lambda: self._display_results(results))
                
            except Exception as e:
                self.after(0, lambda: self._search_error(str(e)))
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def _display_results(self, results: List[Dict[str, Any]]):
        """Display search results"""
        self.search_results = results
        
        # Re-enable search button
        self.search_button.config(state=tk.NORMAL, text="Search")
        
        if not results:
            self.status_label.config(text="No results found")
            return
        
        # Filter out None values and anime already in user's list
        filtered_results = []
        for anime in results:
            # Skip None values
            if anime is None:
                continue
                
            anime_id = anime.get('id')
            if anime_id and not self._is_anime_in_list(anime_id):
                filtered_results.append(anime)
        
        # Update status with filtered count
        total_results = len(results)
        filtered_count = len(filtered_results)
        hidden_count = total_results - filtered_count
        
        if hidden_count > 0:
            self.status_label.config(text=f"Found {filtered_count} results ({hidden_count} already in your list)")
        else:
            self.status_label.config(text=f"Found {filtered_count} results")
        
        if not filtered_results:
            if hidden_count > 0:
                self.status_label.config(text="All search results are already in your list")
            return
        
        # Populate results tree with filtered results
        for anime in filtered_results:
            # Additional safety check (should not be needed after the fix above, but just in case)
            if anime is None:
                continue
                
            name = anime.get('name', 'Unknown')
            anime_type = anime.get('kind', '').upper() if anime.get('kind') else ''
            episodes = anime.get('episodes', 0) or '-'
            year = anime.get('aired_on', '')[:4] if anime.get('aired_on') else '-'
            
            item_id = self.results_tree.insert("", tk.END, values=(
                name, anime_type, episodes, year
            ))
            
            # Store anime data for later use
            self.item_data[item_id] = anime
        
        # Enable add button only if there are results to add
        if filtered_results:
            self.add_button.config(state=tk.NORMAL)
    
    def _sort_tree(self, col, reverse):
        """Sort tree contents when column heading is clicked"""
        def sort_key(item):
            key, _ = item
            if col in ['Episodes', 'Year']:
                # Handle numeric sorting for Episodes and Year
                try:
                    if key == '-' or key == '':
                        return -1 if col == 'Episodes' else 0
                    return int(key)
                except (ValueError, TypeError):
                    return -1 if col == 'Episodes' else 0
            else:
                # String sorting for Name and Type
                return key.lower() if key else ''
        
        l = [(self.results_tree.set(k, col), k) for k in self.results_tree.get_children('')]
        l.sort(key=sort_key, reverse=reverse)

        for index, (val, k) in enumerate(l):
            self.results_tree.move(k, '', index)

        # Reverse sort next time
        self.results_tree.heading(col, command=lambda: self._sort_tree(col, not reverse))

    def _search_error(self, error_msg: str):
        """Handle search error"""
        self.search_button.config(state=tk.NORMAL, text="Search")
        self.status_label.config(text="Search failed")
        messagebox.showerror("Search Error", f"Failed to search: {error_msg}")
    
    def _add_selected_anime(self, event=None):
        """Add selected anime to user's list"""
        selection = self.results_tree.selection()
        if not selection:
            self.main_window._set_status("Please select an anime to add")
            return
        
        item = selection[0]
        anime_data = self.item_data.get(item)
        
        if not anime_data:
            self.main_window._set_status("Could not get anime data")
            return
        
        # Get status to add as
        status_display = self.status_var.get()
        status_map = {v: k for k, v in self.main_window.get_active_client().STATUSES.items()}
        status_key = status_map.get(status_display, 'planned')
        
        anime_name = anime_data.get('name', 'Unknown')
        anime_id = anime_data.get('id')
        
        if not anime_id:
            self.main_window._set_status("Invalid anime ID")
            return
        
        # Check if anime is already in user's list
        if self._is_anime_in_list(anime_id):
            self.main_window._set_status(f"'{anime_name}' is already in your list")
            return
        
        # Disable add button during operation
        self.add_button.config(state=tk.DISABLED, text="Adding...")
        self.main_window._set_status(f"Adding '{anime_name}' to your list...")
        
        def add_anime():
            try:
                # Add anime to list
                result = self.main_window.get_active_client().add_anime_to_list(anime_id, status_key)
                
                if result:
                    # Success - show status message and add to cache
                    self.after(0, lambda: self.main_window._set_status(
                        f"'{anime_name}' added to your list as {status_display}"))
                    
                    # Add to cache instead of full refresh
                    anime_entry = {
                        'id': result.get('id', anime_id),
                        'anime': anime_data,
                        'status': status_key,
                        'episodes': 0,
                        'score': 0,
                        'rewatches': 0
                    }
                    self.after(0, lambda: self.main_window._add_anime_cache_and_reload(anime_entry))
                    
                    # Remove the added anime from search results
                    self.after(0, lambda: self._remove_anime_from_results(anime_id))
                else:
                    self.after(0, lambda: self.main_window._set_status(
                        f"Failed to add '{anime_name}' to your list"))
                
            except Exception as e:
                self.after(0, lambda: self.main_window._set_status(
                    f"Error adding anime: {str(e)}"))
            
            finally:
                self.after(0, lambda: self.add_button.config(state=tk.NORMAL, text="Add Selected"))
        
        threading.Thread(target=add_anime, daemon=True).start()
    
    def _is_anime_in_list(self, anime_id: int) -> bool:
        """Check if anime is already in user's list"""
        anime_list_data = self.main_window.get_anime_list_data()
        
        for status_list in anime_list_data.values():
            for anime_entry in status_list:
                anime = anime_entry.get('anime', {})
                if anime.get('id') == anime_id:
                    return True
        
        return False
    
    def _remove_anime_from_results(self, anime_id: int):
        """Remove anime from search results after adding to list"""
        items_to_remove = []
        
        # Find items to remove
        for item_id in self.results_tree.get_children():
            anime_data = self.item_data.get(item_id)
            if anime_data and anime_data.get('id') == anime_id:
                items_to_remove.append(item_id)
        
        # Remove items from tree and item_data
        for item_id in items_to_remove:
            self.results_tree.delete(item_id)
            if item_id in self.item_data:
                del self.item_data[item_id]
        
        # Update status label with new count
        remaining_count = len(self.results_tree.get_children())
        if remaining_count == 0:
            self.status_label.config(text="No more results to add")
            self.add_button.config(state=tk.DISABLED)
        else:
            # Update the count in the status label
            current_text = self.status_label.cget('text')
            if 'Found' in current_text:
                # Extract the count and update it
                parts = current_text.split(' ')
                if len(parts) >= 2:
                    self.status_label.config(text=f"Found {remaining_count} results")
