# 📦 Proje yapısı
#
# Streamlit çok sayfalı uygulama (pages klasörü ile)
#
# ├── requirements.txt
# ├── utils.py
# ├── Home.py
# └── pages/
#     ├── 1_Çok_Ürünlü_Siparişler.py
#     ├── 2_Çok_Sipariş_Verenler.py
#     ├── 3_Toplam_Miktar_Eşiği.py
#     ├── 4_Aynı_Ürünü_Farklı_Siparişlerde_Alanlar.py
#     ├── 5_Harita_Ürün_Bazlı_Görselleştirme.py
#     └── 6_Raporlar_Excel_İndir.py
#
# Çalıştırma:
#   pip install -r requirements.txt
#   streamlit run Home.py

# ========================= requirements.txt =========================
# İçerik:
# streamlit>=1.36
# pandas>=2.2
# openpyxl>=3.1
# geopy>=2.4
# pydeck>=0.9
# altair>=5.3
# numpy>=1.26

# ============================== utils.py ==============================
import io
import re
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

# ---- Sabit kolonlar ----
ORDER_COL = "Sipariş Numarası"
BUYER_COL = "Alıcı"
ADDR_COLS = ["Teslimat Adresi", "İl", "İlçe"]
PRODUCT_COL = "Ürün Adı"
QTY_COL = "Adet"
AMOUNT_COL = "Faturalanacak Tutar"
IGNORED_COL = "Müşteri Sipariş Adedi"  # asla kullanılmaz

ALL_COLS = [ORDER_COL, BUYER_COL, *ADDR_COLS, PRODUCT_COL, QTY_COL, AMOUNT_COL, IGNORED_COL]

# ---- Yardımcılar ----
def norm_text(x: str) -> str:
    if pd.isna(x):
        return x
    x = re.sub(r"\s+", " ", str(x)).strip()
    return x


def to_number(x):
    if pd.isna(x):
        return None
    s = str(x)
    s = s.replace("₺", "").replace("TL", "").strip()
    # 1.234,56 → 1234.56 ; 1,234.56 → 1234.56
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        try:
            import re as _re
            return float(_re.sub(r"[^0-9\.-]", "", s))
        except Exception:
            return None


@st.cache_data(show_spinner=False)
def load_and_clean_excel(file_bytes: bytes) -> pd.DataFrame:
    """Tüm sheet'leri okur, birleştirir, normalize eder."""
    all_sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
    dfs = []
    for _, df in all_sheets.items():
        if not isinstance(df, pd.DataFrame):
            continue
        df = df.dropna(how="all")
        keep = [c for c in ALL_COLS if c in df.columns]
        if not keep:
            continue
        df = df[keep].copy()

        # Normalizasyon
        if BUYER_COL in df.columns:
            df[BUYER_COL] = df[BUYER_COL].map(norm_text).astype(str).str.title()
        if ORDER_COL in df.columns:
            df[ORDER_COL] = df[ORDER_COL].map(norm_text).astype(str)
        if PRODUCT_COL in df.columns:
            df[PRODUCT_COL] = df[PRODUCT_COL].map(norm_text).astype(str)
        if QTY_COL in df.columns:
            df[QTY_COL] = pd.to_numeric(df[QTY_COL], errors="coerce").fillna(0).astype(int)
        if AMOUNT_COL in df.columns:
            df[AMOUNT_COL] = df[AMOUNT_COL].apply(to_number)

        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    final_df = pd.concat(dfs, ignore_index=True)
    final_df = final_df.dropna(how="all")
    return final_df


def to_excel_bytes(dfs: Dict[str, pd.DataFrame] | pd.DataFrame, filename: Optional[str] = None) -> bytes:
    """Tek DF veya {sheet_name: DF} sözlüğünü xlsx byte'ına çevirir."""
    buf = io.BytesIO()
    if isinstance(dfs, pd.DataFrame):
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            dfs.to_excel(writer, index=False, sheet_name="Sheet1")
    else:
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet, df in dfs.items():
                # Excel sheet adı 31 karakteri aşmamalı
                sheet_name = str(sheet)[:31] if sheet else "Sheet"
                df.to_excel(writer, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.read()


# ---- Oturum veri paylaşımı ----
SESSION_DF_KEY = "__MAIN_DF__"
SESSION_FILE_NAME = "__FILE_NAME__"


def set_df(df: pd.DataFrame, file_name: str | None = None):
    st.session_state[SESSION_DF_KEY] = df
    if file_name:
        st.session_state[SESSION_FILE_NAME] = file_name


def get_df() -> Optional[pd.DataFrame]:
    return st.session_state.get(SESSION_DF_KEY)


def get_file_name(default: str = "veri.xlsx") -> str:
    return st.session_state.get(SESSION_FILE_NAME, default)


# ---- Hazır özetler/hesaplar ----
@st.cache_data(show_spinner=False)
def buyer_summary(df: pd.DataFrame) -> pd.DataFrame:
    base = df[[BUYER_COL, ORDER_COL]].drop_duplicates()
    order_counts = base.groupby(BUYER_COL)[ORDER_COL].nunique().rename("Farklı Sipariş Sayısı")
    qty_sum = df.groupby(BUYER_COL)[QTY_COL].sum().rename("Toplam Adet")
    if AMOUNT_COL in df.columns:
        amount_sum = df.groupby(BUYER_COL)[AMOUNT_COL].sum().rename("Toplam Tutar")
        out = pd.concat([order_counts, qty_sum, amount_sum], axis=1).reset_index()
    else:
        out = pd.concat([order_counts, qty_sum], axis=1).reset_index()
    return out.fillna(0)


@st.cache_data(show_spinner=False)
def orders_with_many_products(df: pd.DataFrame) -> pd.DataFrame:
    grp = df.groupby(ORDER_COL)[PRODUCT_COL].nunique().reset_index(name="Farklı Ürün Sayısı")
    return grp


@st.cache_data(show_spinner=False)
def buyers_over_total_qty(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(BUYER_COL)[QTY_COL].sum().reset_index(name="Toplam Adet")


@st.cache_data(show_spinner=False)
def same_product_across_distinct_orders(df: pd.DataFrame, products: List[str]) -> pd.DataFrame:
    sub = df[df[PRODUCT_COL].isin(products)][[BUYER_COL, PRODUCT_COL, ORDER_COL]].drop_duplicates()
    out = (
        sub.groupby([BUYER_COL, PRODUCT_COL])[ORDER_COL]
        .nunique()
        .reset_index(name="Farklı Sipariş Sayısı")
    )
    return out


# ---- Geocoding ----
@st.cache_data(show_spinner=True)
def geocode_unique_addresses(addresses: List[str], provider: str = "ArcGIS") -> pd.DataFrame:
    """Adres listesi → lat/lon. provider: 'ArcGIS' (varsayılan) veya 'Nominatim'."""
    from geopy.extra.rate_limiter import RateLimiter
    if provider == "Nominatim":
        from geopy.geocoders import Nominatim
        geocoder = Nominatim(user_agent="streamlit-addr-geocoder")
        rate = RateLimiter(geocoder.geocode, min_delay_seconds=1.0)
    else:
        from geopy.geocoders import ArcGIS
        geocoder = ArcGIS(timeout=10)
        rate = RateLimiter(geocoder.geocode, min_delay_seconds=0.2)

    rows = []
    for a in addresses:
        if not a or not str(a).strip():
            rows.append({"address": a, "lat": None, "lon": None})
            continue
        try:
            loc = rate(a)
            if loc:
                rows.append({"address": a, "lat": loc.latitude, "lon": loc.longitude})
            else:
                rows.append({"address": a, "lat": None, "lon": None})
        except Exception:
            rows.append({"address": a, "lat": None, "lon": None})
    return pd.DataFrame(rows)


def build_full_address(df: pd.DataFrame, use_fields: List[str]) -> pd.Series:
    parts = [df[c].fillna("") if c in df.columns else "" for c in use_fields]
    # "Adres, İlçe, İl" şeklinde birleştir
    ser = (
        pd.DataFrame({i: p for i, p in enumerate(parts)})
        .astype(str)
        .apply(lambda r: ", ".join([x for x in r.tolist() if x and str(x).strip()]), axis=1)
        .map(norm_text)
    )
    return ser

