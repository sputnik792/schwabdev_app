import datetime

def time_to_expiration(expiration_str):
    """
    Converts expiration string like 'YYYY-MM-DD:0'
    into time-to-expiration in years.
    """
    try:
        date_str = expiration_str.split(":")[0]
        exp_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.date.today()

        days = (exp_date - today).days

        # Prevent zero / negative time
        return max(days / 365.0, 1 / 365.0)

    except Exception:
        # Fallback ~1 week
        return 7 / 365.0
