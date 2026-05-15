import numpy as np
import pandas as pd
import hashlib


class DfChecker():
    def __init__(self):
        pass
    
    @staticmethod
    def hash(df: pd.DataFrame, float_precision: int = 10) -> str:
        """
        Two DataFrames produce the same hash if they only differ in:
            - column order
            - row order
            - NaN placement (treated consistently)
            - float representation noise (0.30000000004)
            - dtype differences (1 vs 1.0)
        """

        df = df.copy()

        # 1. Sort columns (ignore column order)
        df = df.reindex(sorted(df.columns), axis=1)

        # 2. Normalize floats to avoid precision noise
        float_cols = df.select_dtypes(include=["float", "Float64"]).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].round(float_precision)

        # 3. Normalize missing values without breaking dtypes
        df = df.where(~df.isna(), np.nan)

        # 4. Hash rows
        row_hashes = pd.util.hash_pandas_object(df, index=False)

        # 5. Ignore row order
        row_hashes = np.sort(row_hashes.values)

        # 6. Final deterministic hash
        return hashlib.md5(row_hashes.tobytes()).hexdigest()
      
    def are_equal(self, df1: pd.DataFrame, df2: pd.DataFrame) -> bool:
        return self.hash(df1) == self.hash(df2)

    def compare_with_hash(self, df1: pd.DataFrame, hash_string: str) -> bool:
        df_hash = self.hash(df1)
        return df_hash == hash_string