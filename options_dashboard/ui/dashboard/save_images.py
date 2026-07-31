import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import io

from ui import dialogs
from ui.dashboard.charts_controller import (
    has_active_chart_windows,
    regenerate_chart_data
)
from ui.charts import embed_matplotlib_chart


def parse_chart_title(title: str) -> dict:
    """Parse chart window title into symbol, expiration date, and generation time."""
    symbol = title.split()[0] if title else ""
    date_part = ""
    time_part = ""

    if " - " in title:
        rest = title.split(" - ", 1)[1]
        if " | " in rest:
            date_part, time_part = rest.split(" | ", 1)
        else:
            date_part = rest

    return {
        "symbol": symbol.strip(),
        "date": date_part.strip(),
        "time": time_part.strip(),
        "title": title,
    }


def get_all_active_charts(self):
    """Get all active chart windows with their symbol/date/time combinations."""
    charts = []
    seen_windows = set()

    def add_chart(window, title):
        if window in seen_windows:
            return
        parsed = parse_chart_title(title)
        if not parsed["symbol"]:
            return
        seen_windows.add(window)
        charts.append({
            "symbol": parsed["symbol"],
            "date": parsed["date"],
            "time": parsed["time"],
            "window": window,
            "title": title,
        })

    if hasattr(self, "_chart_windows") and self._chart_windows:
        for win in self._chart_windows:
            try:
                if win.winfo_exists():
                    title = win.title()
                    if any(k in title for k in ("Exposure", "Heston", "Analysis", "Chart")):
                        add_chart(win, title)
            except Exception:
                pass

    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                try:
                    if child.winfo_exists():
                        title = child.title()
                        if any(k in title for k in ("Exposure", "Heston", "Analysis", "Chart")):
                            add_chart(child, title)
                except Exception:
                    pass
    except Exception:
        pass

    charts.sort(key=lambda c: (c["symbol"].upper(), c["date"]))
    return charts


def chart_list_label(chart: dict) -> str:
    """Display label: ticker / expiration / generation time."""
    time_part = chart.get("time") or "—"
    return f"{chart['symbol']} / {chart['date']} / {time_part}"


def find_matching_expiration(self, symbol, date):
    """Find full expiration key for a symbol and date."""
    if symbol not in self.ticker_data:
        return None

    state = self.ticker_data[symbol]
    if not state or not state.exp_data_map:
        return None

    for exp in state.exp_data_map.keys():
        exp_date = exp.split(":")[0] if ":" in exp else exp
        if exp_date == date:
            return exp
    return None


def render_chart_figure(self, symbol, date):
    """Build a matplotlib Figure for the given symbol and expiration date."""
    matching_exp = find_matching_expiration(self, symbol, date)
    if not matching_exp:
        return None

    chart_data = regenerate_chart_data(self, symbol, matching_exp)
    if not chart_data:
        return None

    from ui.charts import compute_bar_width, compute_xticks

    fig = Figure(figsize=(9, 6), dpi=100)
    ax = fig.add_subplot(111)

    df_plot = chart_data["df_plot"]
    calls = df_plot[df_plot["Type"] == "CALL"]
    puts = df_plot[df_plot["Type"] == "PUT"]
    strikes = sorted(df_plot["Strike"].unique())
    bar_width = compute_bar_width(strikes)

    ax.bar(
        calls["Strike"],
        calls["Exposure_Bn"],
        width=bar_width,
        color="#2ECC71",
        edgecolor="black",
        linewidth=0.6,
        label="CALL",
    )
    ax.bar(
        puts["Strike"],
        puts["Exposure_Bn"],
        width=bar_width,
        color="#E74C3C",
        edgecolor="black",
        linewidth=0.6,
        label="PUT",
    )
    ax.axhline(0, color="black", linewidth=1)

    if chart_data["zero_gamma"]:
        ax.axvline(
            chart_data["zero_gamma"],
            color="purple",
            linestyle="--",
            linewidth=1.5,
            label="Dealer Flip",
        )

    current_time = datetime.now().strftime("%I:%M %p")
    ax.set_title(
        f"{symbol} {chart_data['model_name']} Exposure ({date}) | {current_time}",
        fontsize=14,
    )
    ax.set_xlabel("Strike Price", fontsize=12)
    ax.set_ylabel(f"{chart_data['model_name']} Exposure (Bn)", fontsize=12)
    xticks = compute_xticks(strikes)
    ax.set_xticks(xticks)
    ax.ticklabel_format(style="plain", axis="x")
    ax.set_xlim(min(strikes), max(strikes))
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend()
    return fig


def export_chart_to_path(self, symbol, date, file_path, file_format="png"):
    """Export a chart to a file path. Returns True on success."""
    fig = render_chart_figure(self, symbol, date)
    if fig is None:
        return False

    try:
        if file_format == "pdf":
            fig.savefig(file_path, format="pdf", bbox_inches="tight")
        elif file_format == "jpeg":
            fig.savefig(file_path, format="jpeg", dpi=150, bbox_inches="tight")
        else:
            fig.savefig(file_path, format="png", dpi=150, bbox_inches="tight")
        return True
    except Exception:
        return False


def show_save_images_window(self):
    """Show the Save Images window with options"""
    if not has_active_chart_windows(self):
        dialogs.info("No Charts", "No active charts to save.")
        return
    
    # Create main save images window
    save_window = ctk.CTkToplevel(self.root)
    save_window.title("Save Images")
    save_window.geometry("400x280")
    save_window.transient(self.root)
    save_window.grab_set()
    
    # Position near the menu button
    save_window.geometry("+%d+%d" % (self.root.winfo_x() + 50, self.root.winfo_y() + 80))
    
    # Create menu frame
    menu_frame = ctk.CTkFrame(save_window)
    menu_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def option_clicked(option):
        save_window.destroy()
        if option == "Save Individual":
            show_individual_save_window(self)
        elif option == "Save All to PDF Summary":
            save_all_to_pdf(self)
        elif option == "Send Images":
            from ui.dashboard.email_ui import show_send_images_window
            show_send_images_window(self)
    
    # Create option buttons
    individual_btn = ctk.CTkButton(
        menu_frame,
        text="Save Individual",
        command=lambda: option_clicked("Save Individual"),
        width=350,
        height=50,
        font=ctk.CTkFont(size=14)
    )
    individual_btn.pack(pady=10)
    
    pdf_summary_btn = ctk.CTkButton(
        menu_frame,
        text="Save All to PDF Summary",
        command=lambda: option_clicked("Save All to PDF Summary"),
        width=350,
        height=50,
        font=ctk.CTkFont(size=14)
    )
    pdf_summary_btn.pack(pady=10)

    send_images_btn = ctk.CTkButton(
        menu_frame,
        text="Send Images",
        command=lambda: option_clicked("Send Images"),
        width=350,
        height=50,
        font=ctk.CTkFont(size=14),
    )
    send_images_btn.pack(pady=10)


def show_individual_save_window(self):
    """Show window with list of symbol/date combinations for individual saving"""
    charts = get_all_active_charts(self)
    
    if not charts:
        dialogs.info("No Charts", "No active charts found.")
        return
    
    # Create window with scrollable list
    individual_window = ctk.CTkToplevel(self.root)
    individual_window.title("Save Individual Chart")
    individual_window.geometry("500x600")
    individual_window.transient(self.root)
    individual_window.grab_set()
    
    # Position window
    individual_window.geometry("+%d+%d" % (self.root.winfo_x() + 50, self.root.winfo_y() + 80))
    
    # Label
    label = ctk.CTkLabel(
        individual_window,
        text="Select a chart to save:",
        font=ctk.CTkFont(size=14, weight="bold")
    )
    label.pack(pady=10)
    
    # Scrollable frame for chart buttons
    scrollable_frame = ctk.CTkScrollableFrame(individual_window)
    scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create button for each chart
    for chart in charts:
        chart_label = f"{chart['symbol']} - {chart['date']}"
        
        def make_save_handler(symbol, date):
            def save_chart():
                # Show format selection dialog
                format_window = ctk.CTkToplevel(individual_window)
                format_window.title("Select Format")
                format_window.geometry("300x200")
                format_window.transient(individual_window)
                format_window.grab_set()
                
                format_var = tk.StringVar(value="PNG")
                
                ctk.CTkLabel(
                    format_window,
                    text="Select file format:",
                    font=ctk.CTkFont(size=12, weight="bold")
                ).pack(pady=10)
                
                format_frame = ctk.CTkFrame(format_window)
                format_frame.pack(pady=10)
                
                formats = ["PNG", "JPEG", "PDF"]
                for fmt in formats:
                    ctk.CTkRadioButton(
                        format_frame,
                        text=fmt,
                        variable=format_var,
                        value=fmt,
                        font=ctk.CTkFont(size=12)
                    ).pack(pady=5, anchor="w", padx=20)
                
                def save_with_format():
                    selected_format = format_var.get().lower()
                    format_window.destroy()
                    individual_window.destroy()
                    save_individual_chart(self, symbol, date, selected_format)
                
                ctk.CTkButton(
                    format_window,
                    text="Save",
                    command=save_with_format,
                    width=200
                ).pack(pady=10)
            
            return save_chart
        
        btn = ctk.CTkButton(
            scrollable_frame,
            text=chart_label,
            command=make_save_handler(chart['symbol'], chart['date']),
            width=450,
            height=40,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        btn.pack(pady=5, fill="x")


def save_individual_chart(self, symbol, date, file_format):
    """Save an individual chart to file"""
    ext_map = {"png": ".png", "jpeg": ".jpg", "pdf": ".pdf"}
    ext = ext_map.get(file_format, ".png")
    safe_date = date.replace("/", "-").replace(":", "-")
    default_filename = f"{symbol}_{safe_date}_exposure{ext}"

    file_path = filedialog.asksaveasfilename(
        defaultextension=ext,
        filetypes=[(f"{file_format.upper()} files", f"*{ext}"), ("All files", "*.*")],
        initialfile=default_filename,
    )

    if not file_path:
        return

    try:
        if not export_chart_to_path(self, symbol, date, file_path, file_format):
            dialogs.error("Error", f"Could not export chart for {symbol} - {date}")
            return

        dialogs.show_timed_message(
            self.root,
            "Success",
            f"Chart saved to:\n{file_path}",
            duration_ms=3000,
        )
    except Exception as e:
        dialogs.error("Save Error", f"Failed to save chart:\n{str(e)}")


def save_all_to_pdf(self):
    """Save all charts to a PDF summary"""
    charts = get_all_active_charts(self)
    
    if not charts:
        dialogs.info("No Charts", "No active charts to save.")
        return
    
    # Ask user for save location
    file_path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        initialfile=f"charts_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    
    if not file_path:
        return  # User cancelled
    
    try:
        # Show progress dialog
        progress_window = ctk.CTkToplevel(self.root)
        progress_window.title("Saving PDF")
        progress_window.geometry("400x150")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        progress_label = ctk.CTkLabel(
            progress_window,
            text=f"Saving {len(charts)} charts to PDF...",
            font=ctk.CTkFont(size=12)
        )
        progress_label.pack(pady=20)
        
        progress_bar = ctk.CTkProgressBar(progress_window)
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar.set(0)
        
        progress_window.update()
        
        # Create PDF
        with PdfPages(file_path) as pdf:
            for i, chart in enumerate(charts):
                # Update progress
                progress = (i + 1) / len(charts)
                progress_bar.set(progress)
                progress_label.configure(text=f"Saving chart {i+1} of {len(charts)}: {chart['symbol']} - {chart['date']}")
                progress_window.update()
                
                # Find matching expiration
                symbol = chart["symbol"]
                date = chart["date"]

                fig = render_chart_figure(self, symbol, date)
                if fig is None:
                    continue

                pdf.savefig(fig, bbox_inches="tight")
        
        progress_window.destroy()
        
        dialogs.show_timed_message(
            self.root,
            "Success",
            f"PDF saved with {len(charts)} charts:\n{file_path}",
            duration_ms=3000
        )
        
    except Exception as e:
        if 'progress_window' in locals():
            progress_window.destroy()
        dialogs.error("Save Error", f"Failed to save PDF:\n{str(e)}")
