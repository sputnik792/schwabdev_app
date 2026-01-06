import tkinter as tk
from tkinter import ttk
import webbrowser
import os
from pathlib import Path

from ui import dialogs
from config_loader import APP_KEY, CALLBACK_URL, save_api_config
from data.schwab_auth import (
    run_oauth_subprocess,
    create_authenticated_client
)

# Path to API config file (same location as config_loader.py)
from pathlib import Path
_CONFIG_DIR = Path(__file__).resolve().parent.parent
API_CONFIG_FILE = _CONFIG_DIR / "api_config.json"


class AuthMenu(tk.Frame):
    def __init__(self, root, on_authenticated):
        super().__init__(root)
        self.on_authenticated = on_authenticated
        self.root = root

        tk.Label(
            self,
            text="Schwab Authentication",
            font=("Arial", 16, "bold")
        ).pack(pady=12)

        self.status = tk.StringVar(value="Status: Not authenticated")
        tk.Label(self, textvariable=self.status).pack(pady=6)

        # Check if API credentials exist
        has_credentials = API_CONFIG_FILE.exists() and APP_KEY and APP_KEY.strip()
        
        # Add API Credentials button (enabled if no credentials)
        self.add_credentials_btn = ttk.Button(
            self,
            text="Add API Credentials",
            command=self.add_api_credentials,
            state="normal" if not has_credentials else "disabled"
        )
        self.add_credentials_btn.pack(pady=6)

        # Start Login button (disabled if no credentials)
        self.start_login_btn = ttk.Button(
            self,
            text="Start Schwab Login",
            command=self.start_login,
            state="normal" if has_credentials else "disabled"
        )
        self.start_login_btn.pack(pady=6)

        tk.Label(
            self,
            text="Paste the FULL redirect URL here:"
        ).pack(pady=(12, 4))

        self.url_box = tk.Text(self, height=4, width=90)
        self.url_box.pack(padx=10)

        # Complete Login button (disabled if no credentials)
        self.complete_login_btn = ttk.Button(
            self,
            text="Complete Login",
            command=self.complete_login,
            state="normal" if has_credentials else "disabled"
        )
        self.complete_login_btn.pack(pady=10)

        self.pack(fill="both", expand=True)

    def add_api_credentials(self):
        """Open window to add API credentials"""
        import customtkinter as ctk
        import json
        
        # Create api_config.json if it doesn't exist
        if not API_CONFIG_FILE.exists():
            initial_config = {
                "APP_KEY": "",
                "SECRET": "",
                "CALLBACK_URL": "https://127.0.0.1"
            }
            try:
                with open(API_CONFIG_FILE, "w") as f:
                    json.dump(initial_config, f, indent=2)
            except Exception as e:
                dialogs.error("Error", f"Failed to create api_config.json: {str(e)}")
                return
        
        # Create credentials window
        cred_win = ctk.CTkToplevel(self.root)
        cred_win.title("Add API Credentials")
        cred_win.geometry("500x250")
        cred_win.resizable(False, False)
        cred_win.transient(self.root)
        cred_win.lift()
        cred_win.focus()
        cred_win.grab_set()
        
        # Center the window
        cred_win.update_idletasks()
        screen_w = cred_win.winfo_screenwidth()
        screen_h = cred_win.winfo_screenheight()
        win_w = cred_win.winfo_width()
        win_h = cred_win.winfo_height()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        cred_win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # Main container
        main_frame = ctk.CTkFrame(cred_win)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # App Key
        ctk.CTkLabel(main_frame, text="App Key:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 5))
        app_key_var = tk.StringVar()
        app_key_entry = ctk.CTkEntry(main_frame, textvariable=app_key_var, width=450)
        app_key_entry.pack(fill="x", pady=(0, 15))
        
        # Secret Key with show/hide toggle
        secret_label_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        secret_label_frame.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(secret_label_frame, text="Secret Key:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        show_secret_var = tk.BooleanVar(value=False)
        def toggle_secret_visibility():
            if show_secret_var.get():
                secret_entry.configure(show="")
                show_secret_btn.configure(text="Hide")
            else:
                secret_entry.configure(show="*")
                show_secret_btn.configure(text="Show")
        
        show_secret_btn = ctk.CTkButton(
            secret_label_frame,
            text="Show",
            command=lambda: (show_secret_var.set(not show_secret_var.get()), toggle_secret_visibility()),
            width=60,
            height=25
        )
        show_secret_btn.pack(side="right", padx=(10, 0))
        
        secret_var = tk.StringVar()
        secret_entry = ctk.CTkEntry(main_frame, textvariable=secret_var, width=450, show="*")
        secret_entry.pack(fill="x", pady=(0, 20))
        
        # Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x")
        
        def confirm_credentials():
            new_app_key = app_key_var.get().strip()
            new_secret = secret_var.get().strip()
            
            if not new_app_key or not new_secret:
                dialogs.warning("Invalid Input", "Both App Key and Secret Key are required.")
                return
            
            # Save to api_config.json
            try:
                success = save_api_config(new_app_key, new_secret, "https://127.0.0.1")
                if success:
                    # Reload config_loader to pick up new values
                    from config_loader import reload_config
                    reload_config()
                    
                    # Update button states
                    self.add_credentials_btn.configure(state="disabled")
                    self.start_login_btn.configure(state="normal")
                    self.complete_login_btn.configure(state="normal")
                    
                    cred_win.destroy()
                    dialogs.show_timed_message(
                        self.root,
                        "Credentials Saved",
                        "API credentials have been saved. You can now start the login process.",
                        duration_ms=3000
                    )
                else:
                    dialogs.error("Error", "Failed to save API credentials.")
            except Exception as e:
                dialogs.error("Error", f"Failed to save credentials: {str(e)}")
        
        confirm_btn = ctk.CTkButton(
            button_frame,
            text="Confirm",
            command=confirm_credentials,
            width=150
        )
        confirm_btn.pack(side="left", padx=5)
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=cred_win.destroy,
            width=150
        )
        cancel_btn.pack(side="right", padx=5)
        
        # Focus on app key entry
        app_key_entry.focus()
    
    def start_login(self):
        # Reload config to get latest APP_KEY
        import config_loader
        config_loader.reload_config()
        # Access values directly from module after reload
        APP_KEY = config_loader.APP_KEY
        CALLBACK_URL = config_loader.CALLBACK_URL
        
        if not APP_KEY or not APP_KEY.strip():
            dialogs.warning("No Credentials", "Please add API credentials first.")
            return
        
        auth_url = (
            "https://api.schwabapi.com/v1/oauth/authorize"
            f"?client_id={APP_KEY}"
            f"&redirect_uri={CALLBACK_URL}"
            "&response_type=code"
        )

        webbrowser.open(auth_url)
        self.status.set("Status: Login started — complete in browser")

    def complete_login(self):
        # Reload config to get latest credentials
        from config_loader import reload_config
        reload_config()
        
        redirect_url = self.url_box.get("1.0", "end").strip()
        if not redirect_url:
            dialogs.warning("Missing URL", "Paste the redirect URL.")
            return

        try:
            self.status.set("Status: Completing OAuth...")
            run_oauth_subprocess(redirect_url)

            client = create_authenticated_client()
            self.status.set("Status: Authenticated")
            self.on_authenticated(client)

        except Exception as e:
            dialogs.error("Authentication Failed", str(e))
