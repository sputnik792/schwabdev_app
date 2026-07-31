"""
Email UI for the options dashboard — contacts viewer and send-images flow.
"""

from __future__ import annotations

import os
import tempfile
import threading
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from style.theme import ACCENT_PRIMARY, TEXT_MUTED, get_fonts
from ui import dialogs
from ui.dashboard.charts_controller import has_active_chart_windows
from ui.dashboard.save_images import (
    chart_list_label,
    export_chart_to_path,
    get_all_active_charts,
)
from utils.email_sender import add_contact, get_contacts, get_main_account, send_email


def _center_window(window, width: int, height: int, root) -> None:
    window.update_idletasks()
    x = root.winfo_x() + max(0, (root.winfo_width() - width) // 2)
    y = root.winfo_y() + max(0, (root.winfo_height() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def _set_checkbox_vars(entries: List[tuple], value: bool) -> None:
    for _item, var in entries:
        var.set(value)


def show_add_contact_dialog(
    parent,
    root,
    *,
    on_added: Optional[Callable[[], None]] = None,
) -> None:
    """Prompt for name + email and append to email_config.json."""
    fonts = get_fonts()

    dialog = ctk.CTkToplevel(root)
    dialog.title("Add Contact")
    dialog.geometry("420x260")
    dialog.transient(root)
    dialog.grab_set()
    _center_window(dialog, 420, 260, root)

    shell = ctk.CTkFrame(dialog, corner_radius=16)
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(shell, text="Add Contact", font=fonts["lg"]).pack(
        anchor="w", padx=12, pady=(12, 4)
    )
    ctk.CTkLabel(
        shell,
        text="Saved to email_config.json",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
    ).pack(anchor="w", padx=12, pady=(0, 12))

    name_var = ctk.StringVar()
    email_var = ctk.StringVar()

    ctk.CTkLabel(shell, text="Name", font=fonts["sm"], anchor="w").pack(
        fill="x", padx=12, pady=(0, 4)
    )
    ctk.CTkEntry(shell, textvariable=name_var, height=34).pack(
        fill="x", padx=12, pady=(0, 10)
    )

    ctk.CTkLabel(shell, text="Email", font=fonts["sm"], anchor="w").pack(
        fill="x", padx=12, pady=(0, 4)
    )
    ctk.CTkEntry(shell, textvariable=email_var, height=34).pack(
        fill="x", padx=12, pady=(0, 12)
    )

    def save_contact():
        name = name_var.get().strip()
        email = email_var.get().strip()
        try:
            add_contact(name, email)
        except ValueError as exc:
            dialogs.warning("Invalid Contact", str(exc))
            return

        dialog.destroy()
        if on_added:
            on_added()
        dialogs.show_timed_message(
            root,
            "Contact Added",
            f"{name} was added to your contacts.",
            duration_ms=2500,
        )

    button_row = ctk.CTkFrame(shell, fg_color="transparent")
    button_row.pack(fill="x", padx=12, pady=(0, 12))

    ctk.CTkButton(
        button_row,
        text="Save",
        command=save_contact,
        width=100,
        height=34,
    ).pack(side="right", padx=(8, 0))

    ctk.CTkButton(
        button_row,
        text="Cancel",
        command=dialog.destroy,
        width=100,
        height=34,
        fg_color="transparent",
        border_width=1,
    ).pack(side="right")


def show_contacts_window(dashboard) -> None:
    """Show saved email contacts in a scrollable dashboard-styled window."""
    fonts = get_fonts()
    main = get_main_account()

    win = ctk.CTkToplevel(dashboard.root)
    win.title("Contacts")
    win.geometry("520x600")
    win.transient(dashboard.root)
    win.grab_set()
    _center_window(win, 520, 600, dashboard.root)

    shell = ctk.CTkFrame(win, corner_radius=16)
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    header = ctk.CTkFrame(shell, fg_color="transparent")
    header.pack(fill="x", padx=12, pady=(12, 4))

    ctk.CTkLabel(header, text="Email Contacts", font=fonts["lg"]).pack(
        side="left"
    )

    ctk.CTkLabel(
        shell,
        text="Contacts saved in email_config.json",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
    ).pack(anchor="w", padx=12, pady=(0, 8))

    scroll = ctk.CTkScrollableFrame(shell)
    scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    main_card = ctk.CTkFrame(scroll, corner_radius=12)
    main_card.pack(fill="x", pady=(0, 10))

    ctk.CTkLabel(
        main_card,
        text="Main Account",
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=ACCENT_PRIMARY,
    ).pack(anchor="w", padx=14, pady=(12, 4))

    main_name_label = ctk.CTkLabel(
        main_card,
        text=f"Name:  {main.get('name') or '—'}",
        font=fonts["md"],
        anchor="w",
    )
    main_name_label.pack(anchor="w", padx=14, pady=2)
    main_email_label = ctk.CTkLabel(
        main_card,
        text=f"Email: {main.get('email') or '—'}",
        font=fonts["md"],
        anchor="w",
    )
    main_email_label.pack(anchor="w", padx=14, pady=(2, 12))

    contacts_header = ctk.CTkFrame(scroll, fg_color="transparent")
    contacts_header.pack(fill="x", pady=(4, 8))

    ctk.CTkLabel(
        contacts_header,
        text="Contacts",
        font=ctk.CTkFont(size=13, weight="bold"),
        anchor="w",
    ).pack(side="left")

    contacts_list_frame = ctk.CTkFrame(scroll, fg_color="transparent")
    contacts_list_frame.pack(fill="x")

    empty_label = ctk.CTkLabel(
        contacts_list_frame,
        text="No contacts saved yet.",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
    )

    def refresh_contacts_list():
        empty_label.pack_forget()
        for widget in contacts_list_frame.winfo_children():
            widget.destroy()

        contacts = get_contacts()
        if not contacts:
            empty_label.pack(anchor="w", padx=8, pady=8)
            return

        for contact in contacts:
            card = ctk.CTkFrame(contacts_list_frame, corner_radius=12)
            card.pack(fill="x", pady=5)

            ctk.CTkLabel(
                card,
                text=contact.get("name") or "Unnamed",
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            ).pack(anchor="w", padx=14, pady=(10, 2))
            ctk.CTkLabel(
                card,
                text=contact.get("email") or "—",
                font=fonts["sm"],
                text_color=TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w", padx=14, pady=(0, 10))

    refresh_contacts_list()

    def open_add_contact():
        show_add_contact_dialog(
            win,
            dashboard.root,
            on_added=refresh_contacts_list,
        )

    ctk.CTkButton(
        header,
        text="Add Contact",
        command=open_add_contact,
        width=120,
        height=32,
        font=fonts["sm"],
    ).pack(side="right")

    button_row = ctk.CTkFrame(shell, fg_color="transparent")
    button_row.pack(fill="x", padx=12, pady=(0, 12))

    ctk.CTkButton(
        button_row,
        text="Add Contact",
        command=open_add_contact,
        width=120,
        height=34,
    ).pack(side="left")

    ctk.CTkButton(
        button_row,
        text="Close",
        command=win.destroy,
        width=120,
        height=34,
        fg_color="transparent",
        border_width=1,
    ).pack(side="right")


def show_send_images_window(dashboard) -> None:
    """Dual-panel window to email active chart images to selected contacts."""
    if not has_active_chart_windows(dashboard):
        dialogs.info("No Charts", "No active charts to send.")
        return

    main = get_main_account()
    if not main.get("app_password"):
        dialogs.error(
            "Email Not Configured",
            "No Gmail app password found.\n\n"
            "Add your credentials to email_config.json before sending images.",
        )
        return

    contacts = get_contacts()
    if not contacts:
        dialogs.warning(
            "No Contacts",
            "No contacts found.\n\n"
            "Open Contacts from the menu and add a recipient first.",
        )
        return

    charts = get_all_active_charts(dashboard)
    if not charts:
        dialogs.info("No Charts", "No active charts found.")
        return

    fonts = get_fonts()
    tickers = sorted({chart["symbol"].upper() for chart in charts})

    win = ctk.CTkToplevel(dashboard.root)
    win.title("Send Images")
    win.geometry("920x660")
    win.transient(dashboard.root)
    win.grab_set()
    _center_window(win, 920, 660, dashboard.root)

    shell = ctk.CTkFrame(win, corner_radius=16)
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(
        shell,
        text="Send Chart Images",
        font=fonts["lg"],
    ).pack(anchor="w", padx=12, pady=(12, 4))

    ctk.CTkLabel(
        shell,
        text="Select recipients and charts, then click Send.",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
    ).pack(anchor="w", padx=12, pady=(0, 12))

    panels = ctk.CTkFrame(shell, fg_color="transparent")
    panels.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    panels.grid_columnconfigure(0, weight=1)
    panels.grid_columnconfigure(1, weight=1)
    panels.grid_rowconfigure(0, weight=1)

    # Left — contacts
    left = ctk.CTkFrame(panels, corner_radius=12)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

    contacts_top = ctk.CTkFrame(left, fg_color="transparent")
    contacts_top.pack(fill="x", padx=12, pady=(12, 6))

    ctk.CTkLabel(
        contacts_top,
        text="Contacts",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left")

    contacts_scroll = ctk.CTkScrollableFrame(left)
    contacts_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    contact_vars: List[tuple] = []

    def rebuild_contact_checkboxes():
        for widget in contacts_scroll.winfo_children():
            widget.destroy()
        contact_vars.clear()

        for contact in get_contacts():
            var = ctk.BooleanVar(value=False)
            contact_vars.append((contact, var))
            ctk.CTkCheckBox(
                contacts_scroll,
                text=f"{contact.get('name', 'Contact')} — {contact.get('email', '')}",
                variable=var,
                font=fonts["sm"],
            ).pack(fill="x", pady=4, anchor="w")

    rebuild_contact_checkboxes()

    def deselect_all_contacts():
        _set_checkbox_vars(contact_vars, False)

    ctk.CTkButton(
        contacts_top,
        text="Deselect All",
        command=deselect_all_contacts,
        width=100,
        height=28,
        font=fonts["sm"],
        fg_color="transparent",
        border_width=1,
    ).pack(side="right")

    def open_add_contact_from_send():
        show_add_contact_dialog(
            win,
            dashboard.root,
            on_added=rebuild_contact_checkboxes,
        )

    ctk.CTkButton(
        contacts_top,
        text="Add Contact",
        command=open_add_contact_from_send,
        width=100,
        height=28,
        font=fonts["sm"],
    ).pack(side="right", padx=(0, 6))

    # Right — charts
    right = ctk.CTkFrame(panels, corner_radius=12)
    right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    charts_top = ctk.CTkFrame(right, fg_color="transparent")
    charts_top.pack(fill="x", padx=12, pady=(12, 6))

    ctk.CTkLabel(
        charts_top,
        text="Active Charts",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left")

    ctk.CTkButton(
        charts_top,
        text="Deselect All",
        command=lambda: _set_checkbox_vars(chart_vars, False),
        width=100,
        height=28,
        font=fonts["sm"],
        fg_color="transparent",
        border_width=1,
    ).pack(side="right")

    ticker_bar = ctk.CTkFrame(right, fg_color="transparent")
    ticker_bar.pack(fill="x", padx=10, pady=(0, 6))

    ctk.CTkLabel(
        ticker_bar,
        text="Select ticker:",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
    ).pack(side="left", padx=(2, 8))

    charts_scroll = ctk.CTkScrollableFrame(right)
    charts_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    chart_vars: List[tuple] = []
    for chart in charts:
        var = ctk.BooleanVar(value=True)
        chart_vars.append((chart, var))
        ctk.CTkCheckBox(
            charts_scroll,
            text=chart_list_label(chart),
            variable=var,
            font=fonts["sm"],
        ).pack(fill="x", pady=4, anchor="w")

    def select_charts_for_ticker(ticker: str):
        ticker_upper = ticker.upper()
        for chart, var in chart_vars:
            if chart["symbol"].upper() == ticker_upper:
                var.set(True)

    ticker_buttons_row = ctk.CTkScrollableFrame(
        ticker_bar,
        orientation="horizontal",
        height=36,
        fg_color="transparent",
    )
    ticker_buttons_row.pack(side="left", fill="x", expand=True)

    for ticker in tickers:
        ctk.CTkButton(
            ticker_buttons_row,
            text=ticker,
            command=lambda t=ticker: select_charts_for_ticker(t),
            width=max(52, len(ticker) * 12),
            height=28,
            font=fonts["sm"],
            fg_color=("gray80", "gray28"),
            hover_color=("gray70", "gray35"),
        ).pack(side="left", padx=3)

    def _export_selected_charts(selected_charts: List[Dict]) -> List[str]:
        paths: List[str] = []
        temp_dir = tempfile.mkdtemp(prefix="od_charts_")

        for chart in selected_charts:
            symbol = chart["symbol"]
            date = chart["date"]
            safe_date = date.replace("/", "-").replace(":", "-")
            file_path = os.path.join(
                temp_dir,
                f"{symbol}_{safe_date}_exposure.png",
            )
            if export_chart_to_path(dashboard, symbol, date, file_path, "png"):
                paths.append(file_path)
        return paths

    def _cleanup_temp_files(paths: List[str]) -> None:
        seen_dirs = set()
        for path in paths:
            seen_dirs.add(os.path.dirname(path))
        for path in paths:
            try:
                os.unlink(path)
            except OSError:
                pass
        for directory in seen_dirs:
            try:
                os.rmdir(directory)
            except OSError:
                pass

    def on_send():
        selected_contacts = [
            contact for contact, var in contact_vars if var.get()
        ]
        selected_charts = [chart for chart, var in chart_vars if var.get()]

        if not selected_contacts:
            dialogs.warning("No Recipients", "Select at least one contact.")
            return
        if not selected_charts:
            dialogs.warning("No Charts", "Select at least one chart to send.")
            return

        send_btn.configure(state="disabled")
        sending_dialog = dialogs.show_fetching_dialog(
            dashboard.root,
            "Sending",
            "Sending...",
        )

        def worker():
            temp_paths: List[str] = []
            error_message = None
            sent_count = 0
            image_count = 0

            try:
                temp_paths = _export_selected_charts(selected_charts)
                image_count = len(temp_paths)
                if not temp_paths:
                    raise RuntimeError("Could not export any selected charts.")

                chart_summary = ", ".join(
                    chart_list_label(c) for c in selected_charts[:3]
                )
                if len(selected_charts) > 3:
                    chart_summary += f" (+{len(selected_charts) - 3} more)"

                for contact in selected_contacts:
                    name = contact.get("name") or "there"
                    send_email(
                        subject=f"Options Dashboard Charts ({len(temp_paths)} images)",
                        body=(
                            f"Hi {name},\n\n"
                            f"Attached are {len(temp_paths)} chart image(s) from "
                            f"Options Dashboard.\n\n"
                            f"Charts: {chart_summary}\n"
                        ),
                        receiver_email=contact.get("email"),
                        attachment_paths=list(temp_paths),
                    )
                    sent_count += 1
            except Exception as exc:
                error_message = str(exc)
            finally:
                _cleanup_temp_files(temp_paths)

            def finish():
                try:
                    if sending_dialog.winfo_exists():
                        sending_dialog.destroy()
                except Exception:
                    pass
                send_btn.configure(state="normal")

                if error_message:
                    dialogs.error("Send Failed", error_message)
                else:
                    dialogs.show_timed_message(
                        dashboard.root,
                        "Images Sent!",
                        f"Sent {image_count} image(s) to {sent_count} contact(s).",
                        duration_ms=3000,
                    )
                    win.destroy()

            dashboard.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    button_row = ctk.CTkFrame(shell, fg_color="transparent")
    button_row.pack(fill="x", padx=8, pady=(4, 12))

    send_btn = ctk.CTkButton(
        button_row,
        text="Send",
        command=on_send,
        width=140,
        height=38,
        font=ctk.CTkFont(size=14, weight="bold"),
    )
    send_btn.pack(side="right", padx=(8, 0))

    ctk.CTkButton(
        button_row,
        text="Cancel",
        command=win.destroy,
        width=120,
        height=38,
        fg_color="transparent",
        border_width=1,
    ).pack(side="right")
