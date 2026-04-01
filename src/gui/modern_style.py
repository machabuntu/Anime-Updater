"""
Modern styling for tkinter GUI with Windows 11 aesthetic
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

class ModernStyle:
    """Apply modern Windows 11-style theming to tkinter"""
    
    # Windows 11 light theme color palette
    LIGHT_COLORS = {
        # Background colors
        'bg_primary': '#F3F3F3',        # Light gray background
        'bg_secondary': '#FAFAFA',      # Even lighter background
        'bg_dark': '#2D2D30',           # Dark mode background
        'bg_card': '#FFFFFF',           # Card/panel background
        
        # Accent colors (Windows 11 blue)
        'accent': '#0078D4',            # Primary blue
        'accent_hover': '#106EBE',      # Darker blue for hover
        'accent_light': '#E1F5FE',      # Light blue background
        
        # Text colors
        'text_primary': '#323130',      # Main text color
        'text_secondary': '#605E5C',    # Secondary text
        'text_disabled': '#A19F9D',     # Disabled text
        'text_white': '#FFFFFF',        # White text
        
        # Border and surface colors
        'border': '#EDEBE9',            # Light border
        'border_focus': '#0078D4',      # Focused border (accent)
        'surface': '#F8F8F8',           # Surface color
        'divider': '#E1DFDD',           # Divider lines
        
        # Status colors
        'success': '#107C10',           # Green
        'warning': '#FF8C00',           # Orange
        'error': '#D13438',             # Red
    }
    
    # Windows 11 dark theme color palette
    DARK_COLORS = {
        # Background colors
        'bg_primary': '#202020',        # Dark gray background
        'bg_secondary': '#2D2D30',      # Darker background
        'bg_dark': '#1E1E1E',           # Very dark background
        'bg_card': '#2D2D30',           # Card/panel background
        
        # Accent colors (Windows 11 blue)
        'accent': '#0078D4',            # Primary blue
        'accent_hover': '#106EBE',      # Darker blue for hover
        'accent_light': '#1F3A51',      # Dark blue background
        
        # Text colors
        'text_primary': '#FFFFFF',      # Main text color (white)
        'text_secondary': '#CCCCCC',    # Secondary text (light gray)
        'text_disabled': '#888888',     # Disabled text
        'text_white': '#FFFFFF',        # White text
        
        # Border and surface colors
        'border': '#404040',            # Dark border
        'border_focus': '#0078D4',      # Focused border (accent)
        'surface': '#383838',           # Surface color
        'divider': '#404040',           # Divider lines
        
        # Status colors
        'success': '#107C10',           # Green
        'warning': '#FF8C00',           # Orange
        'error': '#D13438',             # Red
    }
    
    def __init__(self, root, dark_theme=False):
        self.root = root
        self.style = ttk.Style(root)
        self.dark_theme = dark_theme
        self.COLORS = self.DARK_COLORS if dark_theme else self.LIGHT_COLORS
        self._setup_theme()
        self._configure_root()
    
    def _setup_theme(self):
        """Setup modern theme for ttk widgets"""
        
        # Use clam theme as base for better color control
        self.style.theme_use('clam')
        
        # Configure all default TTK styles to use our colors
        self.style.configure('.',
                           background=self.COLORS['bg_primary'],
                           foreground=self.COLORS['text_primary'],
                           bordercolor=self.COLORS['border'],
                           darkcolor=self.COLORS['border'],
                           lightcolor=self.COLORS['bg_card'],
                           troughcolor=self.COLORS['surface'],
                           focuscolor=self.COLORS['border_focus'],
                           selectbackground=self.COLORS['accent'],
                           selectforeground=self.COLORS['text_white'],
                           selectborderwidth=0,
                           insertcolor=self.COLORS['text_primary'])
        
        # Configure Frame
        self.style.configure('TFrame',
                           background=self.COLORS['bg_primary'],
                           relief='flat',
                           borderwidth=0)
        
        self.style.configure('Modern.TFrame',
                           background=self.COLORS['bg_primary'],
                           relief='flat',
                           borderwidth=0)
        
        # Configure Card Frame (elevated appearance)
        self.style.configure('Card.TFrame',
                           background=self.COLORS['bg_card'],
                           relief='flat',
                           borderwidth=1)
        
        # Configure LabelFrame with modern look
        self.style.configure('Modern.TLabelframe',
                           background=self.COLORS['bg_card'],
                           relief='flat',
                           borderwidth=1,
                           lightcolor=self.COLORS['border'],
                           darkcolor=self.COLORS['border'])
        
        self.style.configure('Modern.TLabelframe.Label',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           font=('Segoe UI', 9, 'bold'))
        
        # Configure modern buttons
        self.style.configure('Modern.TButton',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           borderwidth=1,
                           focuscolor='none',
                           font=('Segoe UI', 9),
                           relief='flat')
        
        # Accent button style
        self.style.configure('Accent.TButton',
                           background=self.COLORS['accent'],
                           foreground=self.COLORS['text_white'],
                           borderwidth=0,
                           focuscolor='none',
                           font=('Segoe UI', 9, 'bold'),
                           relief='flat')
        
        # Configure Modern.TButton states
        self.style.map('Modern.TButton',
                      background=[('active', self.COLORS['surface']),
                                ('pressed', self.COLORS['accent']),
                                ('!active', self.COLORS['bg_card'])],
                      foreground=[('active', self.COLORS['text_primary']),
                                ('pressed', self.COLORS['text_white']),
                                ('!active', self.COLORS['text_primary'])],
                      relief=[('pressed', 'flat'),
                             ('!pressed', 'flat')])
        
        # Configure Accent button states
        self.style.map('Accent.TButton',
                      background=[('active', self.COLORS['accent_hover']),
                                ('pressed', self.COLORS['accent_hover']),
                                ('!active', self.COLORS['accent'])],
                      foreground=[('active', self.COLORS['text_white']),
                                ('pressed', self.COLORS['text_white']),
                                ('!active', self.COLORS['text_white'])],
                      relief=[('pressed', 'flat'),
                             ('!pressed', 'flat')])
        
        # Configure Entry widgets
        self.style.configure('Modern.TEntry',
                           borderwidth=1,
                           relief='flat',
                           insertwidth=1,
                           font=('Segoe UI', 9))
        
        # Configure Combobox
        self.style.configure('Modern.TCombobox',
                           borderwidth=1,
                           relief='flat',
                           font=('Segoe UI', 9))
        
        # Configure Labels
        self.style.configure('Modern.TLabel',
                           background=self.COLORS['bg_primary'],
                           foreground=self.COLORS['text_primary'],
                           font=('Segoe UI', 9))
        
        self.style.configure('Heading.TLabel',
                           background=self.COLORS['bg_primary'],
                           foreground=self.COLORS['text_primary'],
                           font=('Segoe UI', 12, 'bold'))
        
        self.style.configure('Secondary.TLabel',
                           background=self.COLORS['bg_primary'],
                           foreground=self.COLORS['text_secondary'],
                           font=('Segoe UI', 8))
        
        # Configure Notebook
        self.style.configure('Modern.TNotebook',
                           background=self.COLORS['bg_primary'],
                           borderwidth=0,
                           tabmargins=[0, 0, 0, 0])
        
        self.style.configure('Modern.TNotebook.Tab',
                           background=self.COLORS['bg_secondary'],
                           foreground=self.COLORS['text_primary'],
                           padding=[12, 6],
                           font=('Segoe UI', 9))
        
        # Compute row height from actual font metrics so rows never overlap
        tree_font = tkfont.Font(self.root, ('Segoe UI', 9))
        tree_row_height = tree_font.metrics('linespace') + 4
        
        # Configure Treeview for modern look
        self.style.configure('Modern.Treeview',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           fieldbackground=self.COLORS['bg_card'],
                           borderwidth=1,
                           relief='flat',
                           font=('Segoe UI', 9),
                           rowheight=tree_row_height)
        
        self.style.configure('Modern.Treeview.Heading',
                           background=self.COLORS['bg_secondary'],
                           foreground=self.COLORS['text_primary'],
                           font=('Segoe UI', 9, 'bold'),
                           relief='flat',
                           borderwidth=1)
        
        # Configure Progressbar
        self.style.configure('Modern.Horizontal.TProgressbar',
                           background=self.COLORS['accent'],
                           troughcolor=self.COLORS['surface'],
                           borderwidth=0,
                           lightcolor=self.COLORS['accent'],
                           darkcolor=self.COLORS['accent'])
        
        # Configure ALL default TTK widgets to use our theme
        # This ensures that widgets without explicit styles still look themed
        self.style.configure('TLabel',
                           background=self.COLORS['bg_primary'],
                           foreground=self.COLORS['text_primary'],
                           font=('Segoe UI', 9))
        
        self.style.configure('TLabelframe',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           relief='flat',
                           borderwidth=1,
                           lightcolor=self.COLORS['border'],
                           darkcolor=self.COLORS['border'])
        
        self.style.configure('TLabelframe.Label',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           font=('Segoe UI', 9, 'bold'))
        
        self.style.configure('TButton',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           borderwidth=1,
                           focuscolor='none',
                           font=('Segoe UI', 9),
                           relief='flat')
        
        # Configure button states
        self.style.map('TButton',
                      background=[('active', self.COLORS['surface']),
                                ('pressed', self.COLORS['accent']),
                                ('!active', self.COLORS['bg_card'])],
                      foreground=[('active', self.COLORS['text_primary']),
                                ('pressed', self.COLORS['text_white']),
                                ('!active', self.COLORS['text_primary'])],
                      relief=[('pressed', 'flat'),
                             ('!pressed', 'flat')])
        
        self.style.configure('TEntry',
                           fieldbackground=self.COLORS['bg_card'],
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           borderwidth=1,
                           relief='flat',
                           insertwidth=1,
                           insertcolor=self.COLORS['text_primary'],
                           font=('Segoe UI', 9))
        
        # Configure entry states
        self.style.map('TEntry',
                      fieldbackground=[('disabled', self.COLORS['surface']),
                                     ('!disabled', self.COLORS['bg_card'])],
                      foreground=[('disabled', self.COLORS['text_disabled']),
                                ('!disabled', self.COLORS['text_primary'])])
        
        self.style.configure('TCombobox',
                           fieldbackground=self.COLORS['bg_card'],
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           borderwidth=1,
                           relief='flat',
                           arrowcolor=self.COLORS['text_primary'],
                           font=('Segoe UI', 9))
        
        # Configure combobox states
        self.style.map('TCombobox',
                      fieldbackground=[('readonly', self.COLORS['bg_card']),
                                     ('disabled', self.COLORS['surface']),
                                     ('!readonly', self.COLORS['bg_card'])],
                      background=[('readonly', self.COLORS['bg_card']),
                                ('disabled', self.COLORS['surface']),
                                ('!readonly', self.COLORS['bg_card'])],
                      foreground=[('readonly', self.COLORS['text_primary']),
                                ('disabled', self.COLORS['text_disabled']),
                                ('!readonly', self.COLORS['text_primary'])],
                      arrowcolor=[('disabled', self.COLORS['text_disabled']),
                                ('!disabled', self.COLORS['text_primary'])])
        
        self.style.configure('TNotebook',
                           background=self.COLORS['bg_primary'],
                           borderwidth=0,
                           tabmargins=[0, 0, 0, 0])
        
        # Configure tab styles with consistent sizing and darker colors
        self.style.configure('TNotebook.Tab',
                           background=self.COLORS['surface'],
                           foreground=self.COLORS['text_primary'],
                           padding=[12, 6],
                           font=('Segoe UI', 9))
        
        # Configure selected tab to be slightly lighter with forced consistent sizing
        self.style.map('TNotebook.Tab',
                      background=[('selected', self.COLORS['bg_card']),
                                ('!selected', self.COLORS['surface'])],
                      foreground=[('selected', self.COLORS['text_primary']),
                                ('!selected', self.COLORS['text_primary'])],
                      expand=[('selected', [0, 0, 0, 0]),
                             ('!selected', [0, 0, 0, 0])],
                      padding=[('selected', [12, 6, 12, 6]),
                              ('!selected', [12, 6, 12, 6])])
        
        self.style.configure('Treeview',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           fieldbackground=self.COLORS['bg_card'],
                           borderwidth=1,
                           relief='flat',
                           font=('Segoe UI', 9),
                           rowheight=tree_row_height)
        
        self.style.configure('Treeview.Heading',
                           background=self.COLORS['bg_secondary'],
                           foreground=self.COLORS['text_primary'],
                           font=('Segoe UI', 9, 'bold'),
                           relief='flat',
                           borderwidth=1)
        
        self.style.configure('TScrollbar',
                           background=self.COLORS['surface'],
                           troughcolor=self.COLORS['bg_primary'],
                           bordercolor=self.COLORS['border'],
                           arrowcolor=self.COLORS['text_primary'],
                           darkcolor=self.COLORS['surface'],
                           lightcolor=self.COLORS['surface'])
        
        # Configure scrollbar states
        self.style.map('TScrollbar',
                      background=[('disabled', self.COLORS['bg_primary']),
                                ('active', self.COLORS['surface']),
                                ('!active', self.COLORS['surface'])],
                      troughcolor=[('disabled', self.COLORS['bg_primary']),
                                 ('active', self.COLORS['bg_primary']),
                                 ('!active', self.COLORS['bg_primary'])],
                      arrowcolor=[('disabled', self.COLORS['text_disabled']),
                                ('active', self.COLORS['text_primary']),
                                ('!active', self.COLORS['text_primary'])])
        
        self.style.configure('TSpinbox',
                           fieldbackground=self.COLORS['bg_card'],
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           borderwidth=1,
                           relief='flat',
                           arrowcolor=self.COLORS['text_primary'],
                           font=('Segoe UI', 9))
        
        self.style.configure('TCheckbutton',
                           background=self.COLORS['bg_primary'],
                           foreground=self.COLORS['text_primary'],
                           focuscolor='none',
                           font=('Segoe UI', 9))
        
        # Configure checkbutton hover states with theme-appropriate colors
        hover_bg = self.COLORS['surface'] if self.dark_theme else self.COLORS['accent_light']
        self.style.map('TCheckbutton',
                      background=[('active', hover_bg),
                                ('!active', self.COLORS['bg_primary'])],
                      foreground=[('active', self.COLORS['text_primary']),
                                ('!active', self.COLORS['text_primary'])])
        
        self.style.configure('TRadiobutton',
                           background=self.COLORS['bg_primary'],
                           foreground=self.COLORS['text_primary'],
                           focuscolor='none',
                           font=('Segoe UI', 9))
        
        # Configure radiobutton hover states with theme-appropriate colors
        self.style.map('TRadiobutton',
                      background=[('active', hover_bg),
                                ('!active', self.COLORS['bg_primary'])],
                      foreground=[('active', self.COLORS['text_primary']),
                                ('!active', self.COLORS['text_primary'])])
        
        # Configure Menubutton
        self.style.configure('TMenubutton',
                           background=self.COLORS['bg_card'],
                           foreground=self.COLORS['text_primary'],
                           borderwidth=1,
                           focuscolor='none',
                           font=('Segoe UI', 9),
                           relief='flat',
                           arrowcolor=self.COLORS['text_primary'])
        
        # Configure menubutton states
        self.style.map('TMenubutton',
                      background=[('active', self.COLORS['surface']),
                                ('pressed', self.COLORS['accent']),
                                ('!active', self.COLORS['bg_card'])],
                      foreground=[('active', self.COLORS['text_primary']),
                                ('pressed', self.COLORS['text_white']),
                                ('!active', self.COLORS['text_primary'])],
                      arrowcolor=[('active', self.COLORS['text_primary']),
                                ('pressed', self.COLORS['text_white']),
                                ('!active', self.COLORS['text_primary'])])
    
    def _configure_root(self):
        """Configure root window appearance"""
        self.root.configure(bg=self.COLORS['bg_primary'])
        
        # Apply Windows title bar theme if available
        self._apply_title_bar_theme()
    
    def _apply_title_bar_theme(self):
        """Apply dark/light theme to Windows title bar"""
        try:
            import platform
            if platform.system() == 'Windows':
                try:
                    import ctypes
                    from ctypes import wintypes
                    
                    # Get window handle
                    hwnd = int(self.root.wm_frame(), 16)
                    
                    # Windows 10/11 dark mode API
                    # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                    
                    # Set dark mode (1 for dark, 0 for light)
                    value = 1 if self.dark_theme else 0
                    
                    # Try to call DwmSetWindowAttribute
                    try:
                        dwmapi = ctypes.windll.dwmapi
                        dwmapi.DwmSetWindowAttribute(
                            hwnd,
                            DWMWA_USE_IMMERSIVE_DARK_MODE,
                            ctypes.byref(ctypes.c_int(value)),
                            ctypes.sizeof(ctypes.c_int)
                        )
                    except:
                        # Fallback for older Windows versions
                        # Try alternative attribute value
                        DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
                        try:
                            dwmapi.DwmSetWindowAttribute(
                                hwnd,
                                DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
                                ctypes.byref(ctypes.c_int(value)),
                                ctypes.sizeof(ctypes.c_int)
                            )
                        except:
                            pass
                except Exception as e:
                    # Silently fail if Windows API not available
                    pass
        except:
            pass
    
    def create_card_frame(self, parent, **kwargs):
        """Create a card-style frame with elevation effect"""
        frame = ttk.Frame(parent, style='Card.TFrame', **kwargs)
        return frame
    
    def create_section_frame(self, parent, title=None, **kwargs):
        """Create a section frame with optional title"""
        if title:
            frame = ttk.LabelFrame(parent, text=title, style='Modern.TLabelframe', **kwargs)
        else:
            frame = ttk.Frame(parent, style='Modern.TFrame', **kwargs)
        return frame
    
    def create_toolbar_frame(self, parent, **kwargs):
        """Create a toolbar-style frame"""
        frame = ttk.Frame(parent, style='Modern.TFrame', **kwargs)
        frame.configure(relief='flat', borderwidth=0)
        return frame
    
    def apply_hover_effect(self, widget, hover_color=None):
        """Apply hover effect to a widget"""
        if hover_color is None:
            hover_color = self.COLORS['surface']
        
        original_bg = widget.cget('background') if hasattr(widget, 'cget') else self.COLORS['bg_card']
        
        def on_enter(e):
            widget.configure(background=hover_color)
        
        def on_leave(e):
            widget.configure(background=original_bg)
        
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
    
    def get_color(self, color_name):
        """Get a color from the palette"""
        return self.COLORS.get(color_name, '#000000')
    
    def switch_theme(self, dark_theme=None):
        """Switch between light and dark themes"""
        if dark_theme is None:
            dark_theme = not self.dark_theme
        
        self.dark_theme = dark_theme
        self.COLORS = self.DARK_COLORS if dark_theme else self.LIGHT_COLORS
        
        # Reapply all styles
        self._setup_theme()
        self._configure_root()
        
        # Apply title bar theme
        self._apply_title_bar_theme()
        
        # Force refresh of all widgets
        self._refresh_all_widgets()
    
    def _refresh_all_widgets(self):
        """Recursively refresh all widgets to apply new theme"""
        def refresh_widget(widget):
            try:
                # Update widget backgrounds
                if hasattr(widget, 'configure'):
                    widget_type = str(type(widget))
                    try:
                        # Handle different widget types
                        if 'Tk' in widget_type or 'Toplevel' in widget_type:
                            widget.configure(bg=self.COLORS['bg_primary'])
                        elif 'Frame' in widget_type and 'ttk' not in widget_type:
                            widget.configure(bg=self.COLORS['bg_primary'])
                        elif 'Text' in widget_type:
                            widget.configure(bg=self.COLORS['bg_card'], 
                                           fg=self.COLORS['text_primary'],
                                           selectbackground=self.COLORS['accent'],
                                           selectforeground=self.COLORS['text_white'],
                                           insertbackground=self.COLORS['text_primary'])
                        elif 'Menu' in widget_type:
                            self.configure_menu(widget)
                    except:
                        pass
                
                # Recursively update children
                try:
                    for child in widget.winfo_children():
                        refresh_widget(child)
                except:
                    pass
            except:
                pass
        
        refresh_widget(self.root)
    
    def configure_menu(self, menu):
        """Configure a tkinter Menu widget with dark theme colors"""
        try:
            menu.configure(
                bg=self.COLORS['bg_card'],
                fg=self.COLORS['text_primary'],
                activebackground=self.COLORS['accent'],
                activeforeground=self.COLORS['text_white'],
                selectcolor=self.COLORS['accent'],
                relief='flat',
                borderwidth=1,
                font=('Segoe UI', 9)
            )
        except Exception as e:
            # Silently ignore any configuration errors
            pass
    
    def is_dark_theme(self):
        """Check if dark theme is currently active"""
        return self.dark_theme

class ModernScrollableFrame(ttk.Frame):
    """A modern scrollable frame widget"""
    
    def __init__(self, parent, style_manager=None, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.style_manager = style_manager
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Apply modern styling
        if style_manager:
            self.canvas.configure(bg=style_manager.get_color('bg_primary'))
        
        # Pack elements
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        self.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

def apply_modern_style(root):
    """Convenience function to apply modern styling to a tkinter root"""
    return ModernStyle(root)
