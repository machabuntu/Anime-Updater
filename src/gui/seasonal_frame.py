"""
Seasonal Anime Frame - Browse anime by season with filters and one-click Plan to Watch
"""

import tkinter as tk
from tkinter import ttk
import threading
import webbrowser
import datetime
from typing import Dict, List, Any, Optional


class SeasonalFrame(ttk.Frame):
    """Frame for browsing seasonal anime"""

    SEASONS = ["Winter", "Spring", "Summer", "Fall"]

    SORT_OPTIONS_SHIKIMORI = {
        "Score": "ranked",
        "Popularity": "popularity",
        "Name": "name",
    }

    SORT_OPTIONS_MAL = {
        "Score": "anime_score",
        "Popularity": "anime_num_list_users",
        "Name": "_client_side",
    }

    KIND_FILTER = {
        "All": None,
        "TV": "tv",
        "Movie": "movie",
        "OVA": "ova",
        "ONA": "ona",
        "Special": "special",
        "Music": "music",
    }

    STATUS_FILTER = {
        "All": None,
        "Ongoing": ("ongoing", "currently_airing"),
        "Finished": ("released", "finished_airing"),
        "Announced": ("anons", "not_yet_aired"),
    }

    LIST_FILTER = {
        "All": None,
        "Not in list": False,
        "In list": True,
    }

    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.seasonal_data: List[Dict[str, Any]] = []
        self.filtered_data: List[Dict[str, Any]] = []
        self.item_data: Dict[str, Dict[str, Any]] = {}
        self._loading = False

        self._create_widgets()

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        now = datetime.datetime.now()
        current_year = now.year
        month = now.month
        if month in (1, 2, 3):
            current_season = "Winter"
        elif month in (4, 5, 6):
            current_season = "Spring"
        elif month in (7, 8, 9):
            current_season = "Summer"
        else:
            current_season = "Fall"

        # --- Controls bar ---
        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(controls, text="Year:").pack(side=tk.LEFT, padx=(0, 3))
        self.year_var = tk.IntVar(value=current_year)
        year_spin = ttk.Spinbox(
            controls, from_=1970, to=current_year + 1,
            textvariable=self.year_var, width=6, state="readonly")
        year_spin.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(controls, text="Season:").pack(side=tk.LEFT, padx=(0, 3))
        self.season_var = tk.StringVar(value=current_season)
        season_combo = ttk.Combobox(
            controls, textvariable=self.season_var,
            values=self.SEASONS, state="readonly", width=8)
        season_combo.pack(side=tk.LEFT, padx=(0, 10))

        self.load_button = ttk.Button(controls, text="Load", command=self._load_seasonal)
        self.load_button.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(controls, text="Sort:").pack(side=tk.LEFT, padx=(0, 3))
        self.sort_var = tk.StringVar(value="Popularity")
        sort_combo = ttk.Combobox(
            controls, textvariable=self.sort_var,
            values=list(self.SORT_OPTIONS_SHIKIMORI.keys()),
            state="readonly", width=12)
        sort_combo.pack(side=tk.LEFT)
        sort_combo.bind("<<ComboboxSelected>>", lambda _: self._apply_filters())

        # --- Filters bar ---
        filters = ttk.Frame(self)
        filters.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(filters, text="Type:").pack(side=tk.LEFT, padx=(0, 3))
        self.kind_var = tk.StringVar(value="All")
        kind_combo = ttk.Combobox(
            filters, textvariable=self.kind_var,
            values=list(self.KIND_FILTER.keys()),
            state="readonly", width=8)
        kind_combo.pack(side=tk.LEFT, padx=(0, 10))
        kind_combo.bind("<<ComboboxSelected>>", lambda _: self._apply_filters())

        ttk.Label(filters, text="Status:").pack(side=tk.LEFT, padx=(0, 3))
        self.status_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(
            filters, textvariable=self.status_var,
            values=list(self.STATUS_FILTER.keys()),
            state="readonly", width=10)
        status_combo.pack(side=tk.LEFT, padx=(0, 10))
        status_combo.bind("<<ComboboxSelected>>", lambda _: self._apply_filters())

        ttk.Label(filters, text="In my list:").pack(side=tk.LEFT, padx=(0, 3))
        self.list_var = tk.StringVar(value="All")
        list_combo = ttk.Combobox(
            filters, textvariable=self.list_var,
            values=list(self.LIST_FILTER.keys()),
            state="readonly", width=10)
        list_combo.pack(side=tk.LEFT)
        list_combo.bind("<<ComboboxSelected>>", lambda _: self._apply_filters())

        # --- Results treeview ---
        tree_container = ttk.Frame(self)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        columns = ("Name", "Score", "Type", "Episodes", "Status")
        self.tree = ttk.Treeview(
            tree_container, columns=columns, show="tree headings", height=18)

        self.tree.heading("#0", text="", anchor=tk.W)
        self.tree.column("#0", width=0, stretch=False)

        col_defs = [
            ("Name", "Name", 350, tk.W),
            ("Score", "Score", 60, tk.CENTER),
            ("Type", "Type", 70, tk.W),
            ("Episodes", "Ep.", 50, tk.CENTER),
            ("Status", "Status", 100, tk.W),
        ]
        for col_id, heading, width, anchor in col_defs:
            self.tree.heading(
                col_id, text=heading, anchor=anchor,
                command=lambda c=col_id: self._sort_column(c))
            self.tree.column(col_id, width=width, anchor=anchor)

        v_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Tag for non-released anime
        modern_style = getattr(self.main_window, 'modern_style', None)
        if modern_style and modern_style.is_dark_theme():
            highlight_color = "#1A3A52"
        else:
            highlight_color = "#D6E9FF"
        self.tree.tag_configure("non_released", background=highlight_color)
        self.tree.tag_configure("in_list", foreground="gray")

        # Context menu
        self._create_context_menu()
        self.tree.bind("<Button-3>", self._show_context_menu)

        # --- Bottom bar ---
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.ptw_button = ttk.Button(
            bottom, text="Add to Plan to Watch",
            command=self._add_plan_to_watch, state=tk.DISABLED)
        self.ptw_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(bottom, text="Select a season and click Load")
        self.status_label.pack(side=tk.LEFT, padx=(15, 0))

    def _create_context_menu(self):
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        try:
            service_name = self.main_window.get_active_client().SERVICE_NAME
        except Exception:
            service_name = "Service"
        self.context_menu.add_command(
            label=f"Open on {service_name}", command=self._open_on_service)
        self.context_menu.add_command(
            label="Add to Plan to Watch", command=self._add_plan_to_watch)

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            # Refresh service name label
            try:
                service_name = self.main_window.get_active_client().SERVICE_NAME
                self.context_menu.entryconfig(0, label=f"Open on {service_name}")
            except Exception:
                pass
            self.context_menu.post(event.x_root, event.y_root)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_seasonal(self):
        if self._loading:
            return
        self._loading = True

        year = self.year_var.get()
        season = self.season_var.get().lower()
        sort_label = self.sort_var.get()

        self.load_button.config(state=tk.DISABLED, text="Loading...")
        self.ptw_button.config(state=tk.DISABLED)
        self.status_label.config(text=f"Loading {season.capitalize()} {year}...")

        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_data.clear()
        self.seasonal_data.clear()
        self.filtered_data.clear()

        def fetch():
            try:
                client = self.main_window.get_active_client()
                is_mal = getattr(client, 'SERVICE_KEY', '') == 'mal'

                if is_mal:
                    sort_key = self.SORT_OPTIONS_MAL.get(sort_label, 'anime_num_list_users')
                    if sort_key == '_client_side':
                        sort_key = 'anime_num_list_users'
                    results = client.get_seasonal_anime(year, season, sort=sort_key)
                else:
                    sort_key = self.SORT_OPTIONS_SHIKIMORI.get(sort_label, 'ranked')
                    results = client.get_seasonal_anime(year, season, sort=sort_key)

                self.after(0, lambda: self._on_data_loaded(results, sort_label))
            except Exception as e:
                self.after(0, lambda: self._on_load_error(str(e)))

        threading.Thread(target=fetch, daemon=True).start()

    def _on_data_loaded(self, results: List[Dict[str, Any]], sort_label: str):
        self._loading = False
        self.load_button.config(state=tk.NORMAL, text="Load")
        self.seasonal_data = results or []

        if sort_label == "Name":
            self.seasonal_data.sort(key=lambda a: (a.get('name') or '').lower())

        self._apply_filters()

    def _on_load_error(self, error: str):
        self._loading = False
        self.load_button.config(state=tk.NORMAL, text="Load")
        self.status_label.config(text=f"Error: {error}")

    # ------------------------------------------------------------------
    # Filtering & display
    # ------------------------------------------------------------------

    def _apply_filters(self):
        kind_key = self.KIND_FILTER.get(self.kind_var.get())
        status_vals = self.STATUS_FILTER.get(self.status_var.get())
        list_filter = self.LIST_FILTER.get(self.list_var.get())

        filtered: List[Dict[str, Any]] = []
        for anime in self.seasonal_data:
            # Kind filter
            if kind_key:
                anime_kind = (anime.get('kind') or '').lower()
                if anime_kind != kind_key:
                    continue

            # Status filter
            if status_vals is not None:
                anime_status = (anime.get('status') or '').lower()
                if anime_status not in status_vals:
                    continue

            # List filter
            if list_filter is not None:
                in_list = self._is_anime_in_list(anime.get('id', 0))
                if list_filter and not in_list:
                    continue
                if not list_filter and in_list:
                    continue

            filtered.append(anime)

        # Client-side sort when requested
        sort_label = self.sort_var.get()
        if sort_label == "Name":
            filtered.sort(key=lambda a: (a.get('name') or '').lower())
        elif sort_label == "Score":
            filtered.sort(key=lambda a: float(a.get('score') or 0), reverse=True)

        self.filtered_data = filtered
        self._populate_tree()

    def _populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_data.clear()

        for anime in self.filtered_data:
            name = anime.get('name', 'Unknown')
            score_raw = anime.get('score', '0')
            try:
                score_val = float(score_raw)
                score = f"{score_val:.2f}" if score_val else "-"
            except (ValueError, TypeError):
                score = str(score_raw) if score_raw else "-"
            kind = (anime.get('kind') or '').upper()
            episodes = anime.get('episodes', 0) or '-'
            raw_status = (anime.get('status') or '').lower()
            status_display = self._format_status(raw_status)

            tags: list[str] = []
            if raw_status and raw_status not in ('released', 'finished_airing'):
                tags.append('non_released')
            if self._is_anime_in_list(anime.get('id', 0)):
                tags.append('in_list')

            item_id = self.tree.insert(
                "", tk.END,
                values=(name, score, kind, episodes, status_display),
                tags=tags)
            self.item_data[item_id] = anime

        count = len(self.filtered_data)
        total = len(self.seasonal_data)
        if count == total:
            self.status_label.config(text=f"{count} anime")
        else:
            self.status_label.config(text=f"{count} anime shown (of {total} total)")

        if count > 0:
            self.ptw_button.config(state=tk.NORMAL)
        else:
            self.ptw_button.config(state=tk.DISABLED)

    @staticmethod
    def _format_status(raw: str) -> str:
        mapping = {
            'released': 'Finished',
            'finished_airing': 'Finished',
            'ongoing': 'Ongoing',
            'currently_airing': 'Ongoing',
            'anons': 'Announced',
            'not_yet_aired': 'Announced',
        }
        return mapping.get(raw, raw.replace('_', ' ').title() if raw else '-')

    # ------------------------------------------------------------------
    # Column sorting (client-side)
    # ------------------------------------------------------------------

    _sort_reverse: Dict[str, bool] = {}

    def _sort_column(self, col: str):
        reverse = self._sort_reverse.get(col, False)

        def sort_key(item):
            k, _ = item
            if col == "Score":
                try:
                    return float(k) if k and k != '-' else -1.0
                except (ValueError, TypeError):
                    return -1.0
            if col == "Episodes":
                try:
                    return int(k) if k and k != '-' else -1
                except (ValueError, TypeError):
                    return -1
            return k.lower() if k else ''

        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        items.sort(key=sort_key, reverse=reverse)

        for idx, (_, k) in enumerate(items):
            self.tree.move(k, '', idx)

        self._sort_reverse[col] = not reverse

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_on_service(self):
        selection = self.tree.selection()
        if not selection:
            return
        anime = self.item_data.get(selection[0])
        if not anime:
            return
        client = self.main_window.get_active_client()
        url = anime.get('url', '')
        if url.startswith('/'):
            url = f"{client.SERVICE_URL}{url}"
        if url:
            webbrowser.open(url)

    def _add_plan_to_watch(self):
        selection = self.tree.selection()
        if not selection:
            self.main_window._set_status("Select an anime first")
            return

        item = selection[0]
        anime = self.item_data.get(item)
        if not anime:
            return

        anime_id = anime.get('id')
        anime_name = anime.get('name', 'Unknown')

        if not anime_id:
            return

        if self._is_anime_in_list(anime_id):
            self.main_window._set_status(f"'{anime_name}' is already in your list")
            return

        self.ptw_button.config(state=tk.DISABLED, text="Adding...")
        self.main_window._set_status(f"Adding '{anime_name}' to Plan to Watch...")

        def do_add():
            try:
                client = self.main_window.get_active_client()
                result = client.add_anime_to_list(anime_id, 'planned')

                if result:
                    anime_entry = {
                        'id': result.get('id', anime_id),
                        'anime': anime,
                        'status': 'planned',
                        'episodes': 0,
                        'score': 0,
                        'rewatches': 0,
                    }
                    self.after(0, lambda: self._on_added(anime_name, anime_id, anime_entry))
                else:
                    self.after(0, lambda: self.main_window._set_status(
                        f"Failed to add '{anime_name}'"))
            except Exception as e:
                self.after(0, lambda: self.main_window._set_status(
                    f"Error: {e}"))
            finally:
                self.after(0, lambda: self.ptw_button.config(
                    state=tk.NORMAL, text="Add to Plan to Watch"))

        threading.Thread(target=do_add, daemon=True).start()

    def _on_added(self, name: str, anime_id: int, anime_entry: Dict[str, Any]):
        self.main_window._set_status(f"'{name}' added to Plan to Watch")
        self.main_window._add_anime_cache_and_reload(anime_entry)
        self._mark_in_list(anime_id)

    def _mark_in_list(self, anime_id: int):
        """Visually mark a row as already in list after adding."""
        for item_id, anime in self.item_data.items():
            if anime.get('id') == anime_id:
                current_tags = list(self.tree.item(item_id, 'tags') or [])
                if 'in_list' not in current_tags:
                    current_tags.append('in_list')
                    self.tree.item(item_id, tags=current_tags)
                break

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_anime_in_list(self, anime_id: int) -> bool:
        anime_list_data = self.main_window.get_anime_list_data()
        for status_list in anime_list_data.values():
            for entry in status_list:
                if (entry.get('anime') or {}).get('id') == anime_id:
                    return True
        return False
