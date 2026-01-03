"""
Simple test script for the ticker autocomplete feature.
Run this to test the autocomplete widget independently.
"""

import customtkinter as ctk
from ticker_autocomplete import create_ticker_autocomplete_entry


def main():
    # Set appearance mode and theme
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Create root window
    root = ctk.CTk()
    root.title("Ticker Autocomplete Test")
    root.geometry("400x300")
    
    # Create a frame
    frame = ctk.CTkFrame(root)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    # Label
    label = ctk.CTkLabel(frame, text="Enter a stock ticker:", font=ctk.CTkFont(size=14))
    label.pack(pady=(0, 10))
    
    # Create autocomplete entry
    def on_ticker_selected(ticker):
        print(f"Selected ticker: {ticker}")
        result_label.configure(text=f"Selected: {ticker}")
    
    entry, autocomplete = create_ticker_autocomplete_entry(
        root,  # Use root as parent for proper positioning
        width=250,
        height=35,
        max_suggestions=8,
        on_selection=on_ticker_selected,
        placeholder_text="Type ticker symbol..."
    )
    
    # Pack entry in frame
    entry.pack(pady=10)
    
    # Result label
    result_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=12))
    result_label.pack(pady=10)
    
    # Instructions
    instructions = ctk.CTkLabel(
        frame,
        text="Start typing a ticker symbol to see autocomplete suggestions.",
        font=ctk.CTkFont(size=11),
        text_color="gray"
    )
    instructions.pack(pady=20)
    
    root.mainloop()


if __name__ == "__main__":
    main()

