"""Independent tool windows: click to raise, never permanently on top."""


def make_independent(win) -> None:
    """Let this window stack normally. Clicking it brings only this window forward."""
    try:
        win.attributes("-topmost", False)
    except Exception:
        pass
    try:
        win.transient("")
    except Exception:
        pass

    def _raise(_event=None):
        try:
            if not win.winfo_exists():
                return
            win.attributes("-topmost", False)
            win.lift()
        except Exception:
            pass

    win.bind("<FocusIn>", _raise)
    win.bind("<ButtonPress-1>", _raise)
    try:
        win.bind("<Map>", lambda _e: win.attributes("-topmost", False))
    except Exception:
        pass
