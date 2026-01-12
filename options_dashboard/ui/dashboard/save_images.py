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


def get_all_active_charts(self):
    """Get all active chart windows with their symbol/date combinations"""
    charts = []
    
    # Get tracked chart windows
    if hasattr(self, '_chart_windows') and self._chart_windows:
        for win in self._chart_windows:
            try:
                if win.winfo_exists():
                    title = win.title()
                    # Parse title: "SYMBOL Model Exposure - DATE | TIME"
                    if "Exposure" in title:
                        parts = title.split(" - ")
                        if len(parts) >= 2:
                            symbol_part = parts[0].split()[0]  # First word is symbol
                            date_part = parts[1].split(" |")[0].strip()
                            charts.append({
                                "symbol": symbol_part,
                                "date": date_part,
                                "window": win,
                                "title": title
                            })
            except:
                pass
    
    # Get untracked chart windows (like Heston charts)
    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                try:
                    if child.winfo_exists():
                        title = child.title()
                        if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                            # Check if not already in charts list
                            if not any(c["window"] == child for c in charts):
                                # Parse title
                                if " - " in title:
                                    parts = title.split(" - ")
                                    if len(parts) >= 2:
                                        symbol_part = parts[0].split()[0]
                                        date_part = parts[1].split(" |")[0].strip()
                                        charts.append({
                                            "symbol": symbol_part,
                                            "date": date_part,
                                            "window": child,
                                            "title": title
                                        })
                except:
                    pass
    except:
        pass
    
    return charts


def show_save_images_window(self):
    """Show the Save Images window with options"""
    if not has_active_chart_windows(self):
        dialogs.info("No Charts", "No active charts to save.")
        return
    
    # Create main save images window
    save_window = ctk.CTkToplevel(self.root)
    save_window.title("Save Images")
    save_window.geometry("400x200")
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
    # Find the full expiration string from ticker_data
    if symbol not in self.ticker_data:
        dialogs.error("Error", f"No data available for {symbol}")
        return
    
    state = self.ticker_data[symbol]
    if not state or not state.exp_data_map:
        dialogs.error("Error", f"No expiration data available for {symbol}")
        return
    
    # Find matching expiration
    matching_exp = None
    for exp in state.exp_data_map.keys():
        exp_date = exp.split(":")[0] if ":" in exp else exp
        if exp_date == date:
            matching_exp = exp
            break
    
    if not matching_exp:
        dialogs.error("Error", f"Could not find expiration data for {symbol} - {date}")
        return
    
    # Regenerate chart data
    chart_data = regenerate_chart_data(self, symbol, matching_exp)
    if not chart_data:
        dialogs.error("Error", f"Could not regenerate chart data for {symbol} - {date}")
        return
    
    # Get file extension
    ext_map = {"png": ".png", "jpeg": ".jpg", "pdf": ".pdf"}
    ext = ext_map.get(file_format, ".png")
    
    # Create default filename
    safe_date = date.replace("/", "-").replace(":", "-")
    default_filename = f"{symbol}_{safe_date}_exposure{ext}"
    
    # Ask user for save location
    file_path = filedialog.asksaveasfilename(
        defaultextension=ext,
        filetypes=[(f"{file_format.upper()} files", f"*{ext}"), ("All files", "*.*")],
        initialfile=default_filename
    )
    
    if not file_path:
        return  # User cancelled
    
    try:
        # Create a new figure for saving
        fig = Figure(figsize=(9, 6), dpi=100)
        ax = fig.add_subplot(111)
        
        # Recreate the chart
        from ui.charts import compute_bar_width, compute_xticks
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
            label="CALL"
        )
        
        ax.bar(
            puts["Strike"],
            puts["Exposure_Bn"],
            width=bar_width,
            color="#E74C3C",
            edgecolor="black",
            linewidth=0.6,
            label="PUT"
        )
        
        ax.axhline(0, color="black", linewidth=1)
        
        if chart_data["zero_gamma"]:
            ax.axvline(
                chart_data["zero_gamma"],
                color="purple",
                linestyle="--",
                linewidth=1.5,
                label="Dealer Flip"
            )
        
        current_time = datetime.now().strftime('%I:%M %p')
        ax.set_title(
            f"{symbol} {chart_data['model_name']} Exposure ({date}) | {current_time}",
            fontsize=14
        )
        ax.set_xlabel("Strike Price", fontsize=12)
        ax.set_ylabel(f"{chart_data['model_name']} Exposure (Bn)", fontsize=12)
        xticks = compute_xticks(strikes)
        ax.set_xticks(xticks)
        ax.ticklabel_format(style="plain", axis="x")
        ax.set_xlim(min(strikes), max(strikes))
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.legend()
        
        # Save the figure
        if file_format == "pdf":
            fig.savefig(file_path, format="pdf", bbox_inches="tight")
        elif file_format == "jpeg":
            fig.savefig(file_path, format="jpeg", dpi=150, bbox_inches="tight")
        else:  # PNG
            fig.savefig(file_path, format="png", dpi=150, bbox_inches="tight")
        
        dialogs.show_timed_message(
            self.root,
            "Success",
            f"Chart saved to:\n{file_path}",
            duration_ms=3000
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
                symbol = chart['symbol']
                date = chart['date']
                
                if symbol not in self.ticker_data:
                    continue
                
                state = self.ticker_data[symbol]
                if not state or not state.exp_data_map:
                    continue
                
                # Find matching expiration
                matching_exp = None
                for exp in state.exp_data_map.keys():
                    exp_date = exp.split(":")[0] if ":" in exp else exp
                    if exp_date == date:
                        matching_exp = exp
                        break
                
                if not matching_exp:
                    continue
                
                # Regenerate chart data
                chart_data = regenerate_chart_data(self, symbol, matching_exp)
                if not chart_data:
                    continue
                
                # Create figure
                fig = Figure(figsize=(9, 6), dpi=100)
                ax = fig.add_subplot(111)
                
                # Recreate the chart
                from ui.charts import compute_bar_width, compute_xticks
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
                    label="CALL"
                )
                
                ax.bar(
                    puts["Strike"],
                    puts["Exposure_Bn"],
                    width=bar_width,
                    color="#E74C3C",
                    edgecolor="black",
                    linewidth=0.6,
                    label="PUT"
                )
                
                ax.axhline(0, color="black", linewidth=1)
                
                if chart_data["zero_gamma"]:
                    ax.axvline(
                        chart_data["zero_gamma"],
                        color="purple",
                        linestyle="--",
                        linewidth=1.5,
                        label="Dealer Flip"
                    )
                
                current_time = datetime.now().strftime('%I:%M %p')
                ax.set_title(
                    f"{symbol} {chart_data['model_name']} Exposure ({date}) | {current_time}",
                    fontsize=14
                )
                ax.set_xlabel("Strike Price", fontsize=12)
                ax.set_ylabel(f"{chart_data['model_name']} Exposure (Bn)", fontsize=12)
                xticks = compute_xticks(strikes)
                ax.set_xticks(xticks)
                ax.ticklabel_format(style="plain", axis="x")
                ax.set_xlim(min(strikes), max(strikes))
                ax.grid(axis="y", linestyle="--", alpha=0.35)
                ax.legend()
                
                # Save page to PDF
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
