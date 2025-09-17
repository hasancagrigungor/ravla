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
import sqlite3
import time
from pathlib import Path

# ---- Sabit kolonlar ----
ORDER_COL = "Sipariş Numarası"
BUYER_COL = "Alıcı"
ADDR_COLS = ["Teslimat Adresi", "İl", "İlçe"]
PRODUCT_COL = "Ürün Adı"
QTY_COL = "Adet"
AMOUNT_COL = "Faturalanacak Tutar"
IGNORED_COL = "Müşteri Sipariş Adedi"  # asla kullanılmaz

ALL_COLS = [ORDER_COL, BUYER_COL, *ADDR_COLS, PRODUCT_COL, QTY_COL, AMOUNT_COL, IGNORED_COL]

# Termin Süresi Bitenler sayfası için gerekli kolonlar
TERMIN_COLS = [
    'Barkod', 'Paket No', 'Kargo Firması', 'Sipariş Tarihi',
    'Termin Süresinin Bittiği Tarih', 'Kargoya Teslim Tarihi', 'Kargo Kodu',
    'Sipariş Numarası', 'Alıcı', 'Teslimat Adresi', 'İl', 'İlçe',
    'Ürün Adı', 'Fatura Adresi', 'Alıcı - Fatura Adresi', 'Sipariş Statüsü',
    'E-Posta', 'Komisyon Oranı', 'Marka', 'Stok Kodu', 'Adet',
    'Birim Fiyatı', 'Satış Tutarı', 'İndirim Tutarı',
    'Trendyol İndirim Tutarı', 'Faturalanacak Tutar', 'Butik Numarası',
    'Teslim Tarihi', 'Kargodan alınan desi', 'Hesapladığım desi',
    'Faturalanan Kargo Tutarı', 'Alternatif Teslimat Statüsü',
    'Kurumsal Faturalı Sipariş', 'Vergi Kimlik Numarası', 'Vergi Dairesi',
    'Şirket İsmi', 'Fatura', 'Müşteri Sipariş Adedi', 'Mikro İhracat',
    'ETGB No', 'ETGB Tarihi', 'Yaş', 'Cinsiyet', 'Kargo Partner İsmi',
    '2.Teslimat Paketi Statüsü', '2.Teslimat Takip Numarası',
    'Teslimat Numarası', 'Fatura No', 'Fatura Tarihi', 'Ülke',
    'Müşteri Telefon No', 'ETGB Statüsü'
]

def is_termin_excel(df: pd.DataFrame) -> bool:
    """Excel dosyası Termin Süresi Bitenler formatında mı?"""
    return all(col in df.columns for col in TERMIN_COLS)

# ---- Yardımcılar ----
def norm_text(x: str) -> str:
    if pd.isna(x):
        return x
    x = re.sub(r"\s+", " ", str(x)).strip()
    return x


def to_number(x):
    """
    Para/metin -> float
    Desteklenen örnekler:
      - "1.234,56"  (TR) -> 1234.56
      - "1,234.56"  (EN) -> 1234.56
      - "1234,56"   (virgül ondalık) -> 1234.56
      - "1234.56"   (nokta ondalık)  -> 1234.56
      - "2.000"     (binlik nokta, ondalıksız) -> 2000.0
      - "2,000"     (binlik virgül, ondalıksız) -> 2000.0
      - "₺1.234,56", "1.234,56 TL" vs.
    """
    import re
    if pd.isna(x):
        return None

    s = str(x).strip()
    if not s:
        return None

    # Para birimi ve boşluk temizliği
    s = s.replace("₺", "").replace("TL", "").replace("TRY", "").strip()

    # Sadece rakam, nokta, virgül, eksi, artı tut
    s = re.sub(r"[^0-9,.\-+]", "", s)

    if not s:
        return None

    # 1) Hem nokta hem virgül varsa: TR mi EN mi ayırt et
    if "," in s and "." in s:
        # TR kalıbı: 1.234,56  (binlik=., ondalık=,)
        if re.fullmatch(r"\d{1,3}(\.\d{3})+,\d{2}", s) or re.fullmatch(r"\d+,\d{2}", s):
            s = s.replace(".", "").replace(",", ".")
            try:
                return float(s)
            except Exception:
                return None
        # EN kalıbı: 1,234.56  (binlik=,, ondalık=.)
        if re.fullmatch(r"\d{1,3}(,\d{3})+\.\d{2}", s) or re.fullmatch(r"\d+\.\d{2}", s):
            s = s.replace(",", "")
            try:
                return float(s)
            except Exception:
                return None
        # Belirsiz: son ayıracı ondalık varsay
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma > last_dot:
            # , ondalık; . binlik
            s = s.replace(".", "").replace(",", ".")
        else:
            # . ondalık; , binlik
            s = s.replace(",", "")
        try:
            return float(s)
        except Exception:
            return None

    # 2) Sadece virgül varsa (çoğunlukla ondalık virgül)
    if "," in s:
        # Eğer son 3 karakter içinde virgül ve ardından 1-2 rakam varsa ondalık kabul et
        if re.fullmatch(r"\d+,\d{1,2}", s):
            s = s.replace(",", ".")
            try:
                return float(s)
            except Exception:
                return None
        # Yoksa muhtemelen binlik virgül: tamamen virgülleri kaldır
        try:
            return float(s.replace(",", ""))
        except Exception:
            return None

    # 3) Sadece nokta varsa
    if "." in s:
        # Eğer son 3 karakter içinde nokta ve ardından 1-2 rakam varsa ondalık kabul et
        if re.fullmatch(r"\d+\.\d{1,2}", s):
            try:
                return float(s)
            except Exception:
                return None
        # Yoksa binlik noktaları kaldır
        try:
            return float(s.replace(".", ""))
        except Exception:
            return None

    # 4) Sade rakam
    try:
        return float(s)
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
SESSION_RAW_DF_KEY = "__RAW_DF__"
SESSION_RAW_SHEETS_KEY = "__RAW_SHEETS__"


def set_df(df: pd.DataFrame, file_name: str | None = None):
    st.session_state[SESSION_DF_KEY] = df
    if file_name:
        st.session_state[SESSION_FILE_NAME] = file_name


def set_raw_df(raw_df: pd.DataFrame, sheets: dict | None = None, file_name: str | None = None):
    """Store raw/unmodified dataframe (or combined raw) and optionally raw sheets dict in session."""
    st.session_state[SESSION_RAW_DF_KEY] = raw_df
    if sheets is not None:
        st.session_state[SESSION_RAW_SHEETS_KEY] = sheets
    if file_name:
        st.session_state[SESSION_FILE_NAME] = file_name


def get_df() -> Optional[pd.DataFrame]:
    return st.session_state.get(SESSION_DF_KEY)


def get_raw_df() -> Optional[pd.DataFrame]:
    return st.session_state.get(SESSION_RAW_DF_KEY)


def get_raw_sheets() -> Optional[dict]:
    return st.session_state.get(SESSION_RAW_SHEETS_KEY)


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


# ----------------- Geocode cache (SQLite) -----------------
DB_PATH = Path(__file__).parent / "geocode_cache.sqlite"

def init_geo_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS geo_cache (
            id INTEGER PRIMARY KEY,
            il TEXT,
            ilce TEXT,
            address TEXT,
            lat REAL,
            lon REAL,
            provider TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(il, ilce, provider)
        )
        """
    )
    con.commit()
    con.close()


def get_cached_coords(il: str, ilce: str, provider: str = "ArcGIS") -> tuple | None:
    init_geo_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT lat, lon, address FROM geo_cache WHERE il=? AND ilce=? AND provider=?", (il, ilce, provider))
    row = cur.fetchone()
    con.close()
    if row:
        return (row[0], row[1], row[2])
    return None


def set_cached_coords(il: str, ilce: str, address: str, lat: float, lon: float, provider: str = "ArcGIS"):
    init_geo_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    try:
        cur.execute(
            "INSERT OR REPLACE INTO geo_cache (il, ilce, address, lat, lon, provider) VALUES (?, ?, ?, ?, ?, ?)",
            (il, ilce, address, lat, lon, provider),
        )
        con.commit()
    finally:
        con.close()


def geocode_il_ilce(pairs: List[tuple], provider: str = "ArcGIS", sleep: float = 0.2) -> pd.DataFrame:
    """pairs: list of (il, ilce). Returns DataFrame with il, ilce, address, lat, lon.
    Uses SQLite cache to avoid re-geocoding existing rows."""
    results = []
    # prepare geocoder
    if provider == "Nominatim":
        from geopy.geocoders import Nominatim
        geocoder = Nominatim(user_agent="streamlit-addr-geocoder")
        rate_sleep = 1.0
    else:
        from geopy.geocoders import ArcGIS
        geocoder = ArcGIS(timeout=10)
        rate_sleep = sleep

    for il, ilce in pairs:
        il_s = str(il).strip() if pd.notna(il) else ""
        ilce_s = str(ilce).strip() if pd.notna(ilce) else ""
        if not il_s and not ilce_s:
            continue
        cache = get_cached_coords(il_s, ilce_s, provider=provider)
        if cache:
            lat, lon, address = cache[0], cache[1], cache[2]
            results.append({"il": il_s, "ilce": ilce_s, "address": address, "lat": lat, "lon": lon})
            continue

        # build simple query: "İlçe, İl, Türkiye"
        query = f"{ilce_s}, {il_s}, Türkiye" if ilce_s else f"{il_s}, Türkiye"
        try:
            loc = geocoder.geocode(query)
            if loc:
                lat, lon = float(loc.latitude), float(loc.longitude)
                address = loc.address if hasattr(loc, "address") else query
                set_cached_coords(il_s, ilce_s, address, lat, lon, provider=provider)
                results.append({"il": il_s, "ilce": ilce_s, "address": address, "lat": lat, "lon": lon})
            else:
                results.append({"il": il_s, "ilce": ilce_s, "address": None, "lat": None, "lon": None})
        except Exception:
            results.append({"il": il_s, "ilce": ilce_s, "address": None, "lat": None, "lon": None})
        time.sleep(rate_sleep)

    return pd.DataFrame(results)


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


def prepare_page_df(required_cols: List[str], page_key: str = "page") -> tuple:
    """Return (raw_df, view_df, mapping) for a page.

    - raw_df: the complete original dataframe from session (get_raw_df)
    - view_df: a DataFrame view that contains all raw columns plus aliases for required_cols
    - mapping: dict(required_col -> chosen existing column or None)

    If raw_df is missing, raises ValueError.
    If some required cols are missing, shows UI to let user map existing columns to required names.
    """
    raw = get_raw_df()
    if raw is None or raw.empty:
        raise ValueError("Ham veri bulunamadı. Lütfen Ana Sayfa'dan dosya yükleyin.")

    # Normalize raw column names
    raw_cols = [str(c).strip() for c in raw.columns]
    mapping = {}
    view = raw.copy()

    for rc in required_cols:
        if rc in view.columns:
            mapping[rc] = rc
            continue
        # Offer mapping UI: allow user to pick an existing column to serve as rc
        opts = ["<none>"] + raw_cols
        sel = st.selectbox(f"{page_key}: '{rc}' bulunamadı — eşleştirmek için bir sütun seçin (veya <none>)", opts, key=f"map_{page_key}_{rc}")
        if sel and sel != "<none>":
            mapping[rc] = sel
            # create alias column name if different
            if sel in view.columns:
                view[rc] = view[sel]
        else:
            mapping[rc] = None

    return raw, view, mapping

