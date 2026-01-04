"""
Ticker Autocomplete Widget

A modular autocomplete feature for stock ticker input.
Shows clickable suggestions as the user types.
"""

import json
import os
import customtkinter as ctk
import tkinter as tk
from typing import List, Optional, Callable
# Import will be done locally to avoid circular imports
# from data.ticker_history import get_ticker_priority, record_ticker_search


class TickerAutocomplete:
    """
    An autocomplete widget for stock ticker input.
    
    Features:
    - Fast prefix-based search using sorted list and binary search
    - Clickable suggestion list
    - Configurable max suggestions
    - Efficient caching of stock symbols
    """
    
    # Cache for loaded symbols
    _symbols_cache: Optional[List[str]] = None
    _symbols_file_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "company_tickers.json"
    )
    
    def __init__(
        self,
        parent,
        entry_widget: ctk.CTkEntry,
        max_suggestions: int = 10,
        on_selection: Optional[Callable[[str], None]] = None,
        case_sensitive: bool = False
    ):
        """
        Initialize the autocomplete widget.
        
        Args:
            parent: Parent widget (usually the root or frame)
            entry_widget: The CTkEntry widget to attach autocomplete to
            max_suggestions: Maximum number of suggestions to show (default: 10)
            on_selection: Optional callback function called when a ticker is selected
            case_sensitive: Whether matching should be case-sensitive (default: False)
        """
        self.parent = parent
        self.entry = entry_widget
        self.max_suggestions = max_suggestions
        self.on_selection = on_selection
        self.case_sensitive = case_sensitive
        
        # Load symbols if not cached
        if TickerAutocomplete._symbols_cache is None:
            TickerAutocomplete._symbols_cache = self._load_symbols()
        
        self.symbols = TickerAutocomplete._symbols_cache
        
        # UI components
        self.suggestion_frame: Optional[ctk.CTkFrame] = None
        self.suggestion_buttons: List[ctk.CTkButton] = []
        self.is_visible = False
        
        # Bind events
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Escape>", self._hide_suggestions)
        
        # Track previous value to avoid unnecessary updates
        self._last_value = ""
    
    @classmethod
    def _load_symbols(cls) -> List[str]:
        """Load stock symbols from JSON file and return as sorted list."""
        try:
            with open(cls._symbols_file_path, 'r') as f:
                symbols = json.load(f)
            # Ensure all symbols are strings and uppercase for case-insensitive matching
            symbols = [str(s).strip().upper() for s in symbols if s]
            # Sort for efficient binary search
            symbols.sort()
            return symbols
        except FileNotFoundError:
            print(f"Warning: Stock symbols file not found: {cls._symbols_file_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing stock symbols JSON: {e}")
            return []
        except Exception as e:
            print(f"Error loading stock symbols: {e}")
            return []
    
    def _find_matches(self, prefix: str) -> List[str]:
        """
        Find all symbols matching the given prefix.
        Uses binary search for efficient prefix matching.
        
        Args:
            prefix: The prefix to search for
            
        Returns:
            List of matching symbols (up to max_suggestions)
        """
        if not prefix:
            return []
        
        if not self.case_sensitive:
            prefix = prefix.upper()
        
        matches = []
        
        # Binary search for the first match
        left = 0
        right = len(self.symbols) - 1
        first_match_idx = -1
        
        while left <= right:
            mid = (left + right) // 2
            symbol = self.symbols[mid]
            compare_symbol = symbol if self.case_sensitive else symbol.upper()
            
            if compare_symbol.startswith(prefix):
                first_match_idx = mid
                right = mid - 1  # Continue searching left for earlier matches
            elif compare_symbol < prefix:
                left = mid + 1
            else:
                right = mid - 1
        
        # If no match found, return empty list
        if first_match_idx == -1:
            return []
        
        # Collect all matches starting from first_match_idx
        for i in range(first_match_idx, len(self.symbols)):
            symbol = self.symbols[i]
            compare_symbol = symbol if self.case_sensitive else symbol.upper()
            
            if compare_symbol.startswith(prefix):
                matches.append(symbol)
                if len(matches) >= self.max_suggestions * 2:  # Get more matches for sorting
                    break
            else:
                # Since list is sorted, we can stop once we pass the prefix
                break
        
        # Sort matches by priority: count (desc), date (desc), alphabetical (asc)
        # Use get_ticker_priority which returns (-count, -days_since_epoch, ticker)
        # This tuple sorts correctly: higher count first, then more recent, then alphabetical
        from data.ticker_history import get_ticker_priority
        matches.sort(key=lambda ticker: get_ticker_priority(ticker))
        
        # Return up to max_suggestions
        return matches[:self.max_suggestions]
    
    def _on_key_release(self, event):
        """Handle key release events in the entry widget."""
        current_value = self.entry.get()
        
        # Ignore arrow keys, Enter, Tab, etc.
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape'):
            return
        
        # Only update if value changed
        if current_value == self._last_value:
            return
        
        self._last_value = current_value
        
        if not current_value:
            self._hide_suggestions()
            return
        
        matches = self._find_matches(current_value)
        
        # Debug output
        # if current_value:
        #     print(f"Searching for '{current_value}': found {len(matches)} matches")
        #     if matches:
        #         print(f"Matches: {matches[:5]}")  # Show first 5
        
        if matches:
            self._show_suggestions(matches)
        else:
            self._hide_suggestions()
    
    def _on_focus_out(self, event):
        """Hide suggestions when entry loses focus."""
        # Small delay to allow button clicks to register
        self.parent.after(150, self._hide_suggestions)
    
    def _show_suggestions(self, matches: List[str]):
        """Display the suggestion list."""
        # Hide existing suggestions first
        self._hide_suggestions()
        
        if not matches:
            return
        
        # Get entry widget position relative to its parent
        entry_x = self.entry.winfo_x()
        entry_y = self.entry.winfo_y()
        entry_width = self.entry.winfo_width()
        entry_height = self.entry.winfo_height()
        
        # Get the parent of the entry (where it's packed)
        entry_parent = self.entry.master
        
        # Create suggestion frame as child of entry's parent with proper width
        self.suggestion_frame = ctk.CTkFrame(
            entry_parent,
            corner_radius=8,
            width=entry_width
        )
        
        # Create buttons for each suggestion
        self.suggestion_buttons = []
        for i, ticker in enumerate(matches):
            btn = ctk.CTkButton(
                self.suggestion_frame,
                text=ticker,
                command=lambda t=ticker: self._select_ticker(t),
                anchor="w",
                height=32,
                font=ctk.CTkFont(size=13)
            )
            btn.pack(fill="x", padx=2, pady=1)
            self.suggestion_buttons.append(btn)
        
        # Position the frame below the entry using place
        # Note: CustomTkinter place() doesn't accept width/height, so we set it in constructor
        y_pos = entry_y + entry_height + 2
        self.suggestion_frame.place(x=entry_x, y=y_pos)
        # Update to ensure proper rendering
        self.suggestion_frame.update_idletasks()
        self.suggestion_frame.lift()
        self.is_visible = True
        print(f"DEBUG: Showing {len(matches)} suggestions at position ({entry_x}, {y_pos}), entry size: {entry_width}x{entry_height}")  # Debug
    
    def _hide_suggestions(self):
        """Hide the suggestion list."""
        if self.suggestion_frame:
            self.suggestion_frame.destroy()
            self.suggestion_frame = None
            self.suggestion_buttons = []
            self.is_visible = False
    
    def _select_ticker(self, ticker: str):
        """Handle ticker selection from suggestion list."""
        self.entry.delete(0, tk.END)
        self.entry.insert(0, ticker)
        self._hide_suggestions()
        
        # Call callback if provided
        if self.on_selection:
            self.on_selection(ticker)
    
    def destroy(self):
        """Clean up the autocomplete widget."""
        self._hide_suggestions()
        # Unbind events
        self.entry.unbind("<KeyRelease>")
        self.entry.unbind("<FocusOut>")
        self.entry.unbind("<Escape>")


def create_ticker_autocomplete_entry(
    parent,
    width: int = 200,
    height: int = 32,
    max_suggestions: int = 10,
    on_selection: Optional[Callable[[str], None]] = None,
    placeholder_text: str = "Enter ticker..."
) -> tuple[ctk.CTkEntry, TickerAutocomplete]:
    """
    Convenience function to create an entry widget with autocomplete.
    
    Args:
        parent: Parent widget
        width: Width of the entry widget
        height: Height of the entry widget
        max_suggestions: Maximum number of suggestions to show
        on_selection: Optional callback when a ticker is selected
        placeholder_text: Placeholder text for the entry
        
    Returns:
        Tuple of (entry_widget, autocomplete_instance)
    """
    entry = ctk.CTkEntry(
        parent,
        width=width,
        height=height,
        placeholder_text=placeholder_text
    )
    
    autocomplete = TickerAutocomplete(
        parent,
        entry,
        max_suggestions=max_suggestions,
        on_selection=on_selection
    )
    
    return entry, autocomplete

