import datetime

def normalize_expiration(exp):
    """
    Accepts datetime, date, or string (YYYY-MM-DD or YYYY-MM-DD:*)
    Returns normalized YYYY-MM-DD:0 string (for internal key format)
    """
    if isinstance(exp, (datetime.date, datetime.datetime)):
        return f"{exp:%Y-%m-%d}:0"

    if isinstance(exp, str):
        return exp.split(":")[0] + ":0"

    raise ValueError(f"Invalid expiration: {exp}")

def format_expiration_with_days(exp):
    """
    Accepts datetime, date, or string (YYYY-MM-DD or YYYY-MM-DD:*)
    Returns formatted YYYY-MM-DD:DAYS string where DAYS is the actual days to expiration
    """
    today = datetime.date.today()
    
    if isinstance(exp, (datetime.date, datetime.datetime)):
        if isinstance(exp, datetime.datetime):
            exp_date = exp.date()
        else:
            exp_date = exp
        days = (exp_date - today).days
        return f"{exp_date:%Y-%m-%d}:{max(days, 0)}"
    
    if isinstance(exp, str):
        # Extract date part
        date_str = exp.split(":")[0]
        try:
            exp_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            days = (exp_date - today).days
            return f"{date_str}:{max(days, 0)}"
        except ValueError:
            # If parsing fails, return with 0 days
            return f"{date_str}:0"
    
    raise ValueError(f"Invalid expiration: {exp}")
