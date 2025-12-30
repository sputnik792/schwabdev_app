import pandas as pd

def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg or "401" in msg or "authentication" in msg:
            raise RuntimeError("AUTH_REQUIRED")
        raise


def fetch_stock_price(client, symbol):
    try:
        resp = safe_call(client.quotes, symbol)
        data = resp.json()

        sym = data.get(symbol.upper(), {})
        price = (
            sym.get("quote", {}).get("lastPrice")
            or sym.get("regular", {}).get("regularMarketLastPrice")
            or sym.get("extended", {}).get("lastPrice")
            or sym.get("quote", {}).get("mark")
            or 0.0
        )
        return float(price)

    except RuntimeError:
        raise
    except Exception:
        return 0.0


def fetch_option_chain(client, symbol, strike_count=40):
    try:
        resp = safe_call(
            client.option_chains,
            symbol=symbol.upper(),
            contractType="ALL",
            strikeCount=strike_count,
            includeUnderlyingQuote=True
        )

        data = resp.json()

        calls = data.get("callExpDateMap", {})
        puts  = data.get("putExpDateMap", {})

        expirations = sorted(set(calls.keys()) | set(puts.keys()))
        exp_data_map = {}

        for exp in expirations:
            call_rows = []
            put_rows  = []

            if exp in calls:
                for strike, opts in calls[exp].items():
                    opt = opts[0]
                    call_rows.append({
                        "Strike": float(strike),
                        "Bid_Call": opt.get("bid", 0.0),
                        "Ask_Call": opt.get("ask", 0.0),
                        "Delta_Call": opt.get("delta", 0.0),
                        "Theta_Call": opt.get("theta", 0.0),
                        "Gamma_Call": opt.get("gamma", 0.0),
                        "IV_Call": opt.get("volatility", 0.0),
                        "OI_Call": opt.get("openInterest", 0.0),
                    })

            if exp in puts:
                for strike, opts in puts[exp].items():
                    opt = opts[0]
                    put_rows.append({
                        "Strike": float(strike),
                        "Bid_Put": opt.get("bid", 0.0),
                        "Ask_Put": opt.get("ask", 0.0),
                        "Delta_Put": opt.get("delta", 0.0),
                        "Theta_Put": opt.get("theta", 0.0),
                        "Gamma_Put": opt.get("gamma", 0.0),
                        "IV_Put": opt.get("volatility", 0.0),
                        "OI_Put": opt.get("openInterest", 0.0),
                    })

            df_calls = pd.DataFrame(call_rows)
            df_puts  = pd.DataFrame(put_rows)

            if not df_calls.empty:
                df_calls = df_calls.sort_values("Strike")
            if not df_puts.empty:
                df_puts = df_puts.sort_values("Strike")

            df = pd.merge(df_calls, df_puts, on="Strike", how="outer").fillna("")
            exp_data_map[exp] = df

        return exp_data_map, expirations

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"FETCH_FAILED: {e}")
