from dataclasses import dataclass
from typing import Dict
import pandas as pd
import datetime

@dataclass
class TickerState:
    symbol: str
    price: float
    exp_data_map: Dict[str, pd.DataFrame]
    last_updated: datetime.datetime
    is_csv: bool = False
