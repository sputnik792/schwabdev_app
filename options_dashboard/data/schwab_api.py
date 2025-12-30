def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg or "401" in msg:
            raise RuntimeError("AUTH_REQUIRED")
        raise
