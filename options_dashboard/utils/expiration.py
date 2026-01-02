import datetime

def normalize_expiration(exp):
    """
    Accepts datetime, date, or string (YYYY-MM-DD or YYYY-MM-DD:*)
    Returns normalized YYYY-MM-DD:0 string
    """
    if isinstance(exp, (datetime.date, datetime.datetime)):
        return f"{exp:%Y-%m-%d}:0"

    if isinstance(exp, str):
        return exp.split(":")[0] + ":0"

    raise ValueError(f"Invalid expiration: {exp}")
