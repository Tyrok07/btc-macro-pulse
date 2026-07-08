diff --git a/data/loader.py b/data/loader.py
index 8c2815902a1ccee383207b1a79ffd69412943d23..d4e84238df1ab9efe51cb21542faa916ffde54e4 100644
--- a/data/loader.py
+++ b/data/loader.py
@@ -1,59 +1,50 @@
+from __future__ import annotations
+
 import pandas as pd
 import streamlit as st
 import yfinance as yf
 
 
 class DataLoader:
-
     SYMBOLS = {
         "GC=F": "Altin",
         "HG=F": "Bakir",
-        "BTC-USD": "Bitcoin"
+        "BTC-USD": "Bitcoin",
     }
 
     @staticmethod
     @st.cache_data(ttl=3600)
-    def load():
+    def load() -> pd.DataFrame:
+        return DataLoader.download(period="8y", interval="1d", multi_level_index=False)
 
-        df = yf.download(
-            list(DataLoader.SYMBOLS.keys()),
-            period="8y",
-            interval="1d",
-            auto_adjust=False,
-            multi_level_index=False,
-            progress=False
-        )
+    @staticmethod
+    def load_recent(period: str = "60d", interval: str = "1d") -> pd.DataFrame:
+        return DataLoader.download(period=period, interval=interval)
 
+    @staticmethod
+    def download(period: str, interval: str, multi_level_index: bool | None = None) -> pd.DataFrame:
+        kwargs = {
+            "period": period,
+            "interval": interval,
+            "auto_adjust": False,
+            "progress": False,
+        }
+        if multi_level_index is not None:
+            kwargs["multi_level_index"] = multi_level_index
+        df = yf.download(list(DataLoader.SYMBOLS.keys()), **kwargs)
+        return DataLoader.normalize(df)
+
+    @staticmethod
+    def normalize(df: pd.DataFrame) -> pd.DataFrame:
         if df.empty:
             return pd.DataFrame()
-
         if isinstance(df.columns, pd.MultiIndex):
-
             if "Close" in df.columns.get_level_values(0):
                 df = df["Close"].copy()
             else:
-                df = df.set_axis(
-                    df.columns.get_level_values(0),
-                    axis=1
-                )
-
+                df = df.set_axis(df.columns.get_level_values(0), axis=1)
         elif "Close" in df.columns:
-
             df = df["Close"]
-
-        df = df.rename(columns={
-            k: v
-            for k, v in DataLoader.SYMBOLS.items()
-            if k in df.columns
-        })
-
-        cols = [
-            c for c in [
-                "Altin",
-                "Bakir",
-                "Bitcoin"
-            ]
-            if c in df.columns
-        ]
-
+        df = df.rename(columns={k: v for k, v in DataLoader.SYMBOLS.items() if k in df.columns})
+        cols = [column for column in ["Altin", "Bakir", "Bitcoin"] if column in df.columns]
         return df[cols].ffill().bfill()
