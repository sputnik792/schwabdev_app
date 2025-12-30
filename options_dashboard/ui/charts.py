import matplotlib.pyplot as plt

def plot_exposure(df, title, zero_gamma=None):
    fig, ax = plt.subplots(figsize=(9,6))

    calls = df[df["Type"]=="CALL"]
    puts  = df[df["Type"]=="PUT"]

    ax.bar(calls["Strike"], calls["Exposure_Bn"], color="green", label="CALL")
    ax.bar(puts["Strike"], puts["Exposure_Bn"], color="red", label="PUT")

    ax.axhline(0, color="black")

    if zero_gamma:
        ax.axvline(zero_gamma, linestyle="--", color="purple", label="Dealer Flip")

    ax.set_title(title)
    ax.set_ylabel("Exposure (Bn)")
    ax.set_xlabel("Strike")

    ax.legend()
    ax.grid(alpha=0.3)

    return fig
