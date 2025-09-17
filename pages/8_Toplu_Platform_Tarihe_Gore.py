# app.py
import streamlit as st
import pandas as pd
import io
import os
from typing import List, Dict
from datetime import date

st.set_page_config(page_title="Sipariş Birleştir & Tarih/Kaynak Filtresi", layout="wide")
st.title("📦 Sipariş CSV Birleştirici + Tarih & Kaynak Filtresi")

# --- 1) Standart kolon eşleme ---
COLUMNS_MAP: Dict[str, List[str]] = {
    'barkod': ['Barkod'],
    'paket_numarasi': ['Paket Numarası', 'Paket No'],
    'kargo_firmasi': ['Kargo Firması'],
    'siparis_tarihi': ['Sipariş Tarihi'],
    'son_teslim_tarihi': ['Kargoya Son Teslim Tarihi', 'Termin Süresinin Bittiği Tarih'],
    'kargo_takip_no': ['Kargo Takip No', 'Kargo Kodu'],
    'desi': ['Desi', 'Kargodan alınan desi', 'Hesapladığım desi'],
    'kargoya_teslim_tarihi': ['Kargo Kabul Tarihi', 'Kargoya Teslim Tarihi'],
    'siparis_numarasi': ['Sipariş Numarası'],
    'alici': ['Alıcı'],
    'teslimat_adresi': ['Teslimat Adresi'],
    'sehir': ['Şehir', 'İl'],
    'ilce': ['Semt', 'İlçe'],
    'platform_urun_kodu': ['Hepsiburada Ürün Kodu'],
    'stok_kodu': ['Satıcı Stok Kodu', 'Stok Kodu'],
    'urun_adi': ['Ürün Adı'],
    'adet': ['Adet'],
    'birim_fiyat': ['Birim Listeleme Fiyatı', 'Birim Fiyatı'],
    'satis_tutari': ['Faturalandırılacak Birim Satış Fiyatı', 'Faturalandırılacak Satış Fiyatı', 'Satış Tutarı', 'Faturalanacak Tutar'],
    'komisyon_tutari': ['Komisyon Tutarı (KDV Dahil)', 'HB alacağı net Komisyon Tutarı (KDV dahil)'],
    'komisyon_orani': ['Komisyon Oranı'],
    'fatura_adresi': ['Fatura Adresi'],
    'siparis_durumu': ['Paket Durumu', 'Sipariş Statüsü'],
    'teslim_tarihi': ['Teslim Tarihi'],
    'email': ['Alıcı Mail Adresi', 'E-Posta'],
    'etgb_numarasi': ['ETGB Numarası', 'ETGB No'],
    'etgb_tarihi': ['ETGB Tarihi ', 'ETGB Tarihi'],
    'uluslararasi_siparis': ['Uluslararası Sipariş mi?', 'Mikro İhracat']
}

TARGET_DATE_COLS = ["siparis_tarihi", "son_teslim_tarihi", "kargoya_teslim_tarihi"]

# --- 2) Yardımcılar ---
def _to_strio(uploaded_file) -> io.StringIO:
    return io.StringIO(uploaded_file.getvalue().decode("utf-8", errors="ignore"))

@st.cache_data(show_spinner=False)
def read_csv_auto(uploaded_file) -> pd.DataFrame:
    """
    Önce C engine + sep=';' dene; olmazsa python engine + sep=None fallback.
    """
    s1 = _to_strio(uploaded_file)
    try:
        df = pd.read_csv(s1, sep=";", engine="c", low_memory=False, on_bad_lines="skip")
        if len(df.columns) == 1:  # yanlış ayrılmış olabilir
            s2 = _to_strio(uploaded_file)
            df = pd.read_csv(s2, sep=None, engine="python", on_bad_lines="skip")
        return df
    except Exception:
        s3 = _to_strio(uploaded_file)
        return pd.read_csv(s3, sep=None, engine="python", on_bad_lines="skip")

def normalize_columns_keep_all(df: pd.DataFrame, columnsmap: Dict[str, List[str]]) -> pd.DataFrame:
    rename_dict = {}
    for std_col, alt_cols in columnsmap.items():
        for alt in alt_cols:
            if alt in df.columns:
                rename_dict[alt] = std_col
                break
    return df.rename(columns=rename_dict)

def add_source_column(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()
    df["kaynak"] = source_name
    return df

def parse_datetime_series(sr: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(sr):
        s = sr
    else:
        s = pd.to_datetime(sr, errors="coerce", dayfirst=True, infer_datetime_format=True)
        if s.notna().sum() == 0 and pd.api.types.is_numeric_dtype(sr):
            try:
                s = pd.to_datetime("1899-12-30") + pd.to_timedelta(sr, unit="D")
            except Exception:
                pass
    try:
        s = s.dt.tz_localize(None)
    except Exception:
        pass
    return s

def ensure_target_dates(df: pd.DataFrame, target_cols: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in target_cols:
        if col in df.columns:
            parsed = parse_datetime_series(df[col])
            df[col] = parsed
            df[f"_parsed_dt_{col}"] = parsed.dt.normalize()
    return df

# --- 3) Dosyaları oku & birleştir ---
uploaded_files = st.file_uploader("CSV dosyalarını yükle (çoklu)", type=["csv"], accept_multiple_files=True)
if not uploaded_files:
    st.info("👆 CSV dosyalarını yükle.")
    st.stop()

dfs = []
for uf in uploaded_files:
    try:
        raw = read_csv_auto(uf)
    except Exception as e:
        st.error(f"{uf.name} okunamadı: {e}")
        continue
    df_norm = normalize_columns_keep_all(raw, COLUMNS_MAP)
    df_norm = add_source_column(df_norm, os.path.basename(uf.name))
    dfs.append(df_norm)

if not dfs:
    st.error("Hiç dosya yüklenemedi.")
    st.stop()

df = pd.concat(dfs, ignore_index=True)

df = ensure_target_dates(df, TARGET_DATE_COLS)

st.success(f"✅ Birleştirildi: {df.shape[0]} satır, {df.shape[1]} kolon")
with st.expander("Birleşik DataFrame – ilk 200 satır"):
    st.dataframe(df.head(200), use_container_width=True)

# --- 4) Tarih kolonu seçimi ---
st.subheader("⏱️ Filtre Seçenekleri")

available_dt_cols = [c for c in TARGET_DATE_COLS if c in df.columns and df[c].notna().any()]
if not available_dt_cols:
    st.error("Hedef tarih kolonlarından hiçbiri bulunamadı.")
    st.stop()

default_idx = 0
if "siparis_tarihi" in available_dt_cols:
    default_idx = available_dt_cols.index("siparis_tarihi")

selected_dt_col = st.selectbox("Tarih kolonu seç:", available_dt_cols, index=default_idx)

parsed_helper_col = f"_parsed_dt_{selected_dt_col}"
if parsed_helper_col not in df.columns or df[parsed_helper_col].notna().sum() == 0:
    st.error(f"Seçilen kolonda geçerli tarih yok: {selected_dt_col}")
    st.stop()

min_date = df[parsed_helper_col].min().date()
max_date = df[parsed_helper_col].max().date()

today = date.today()
def clamp(d: date) -> date:
    if d < min_date: return min_date
    if d > max_date: return max_date
    return d

default_start = clamp(today)
default_end = clamp(today)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Başlangıç Tarihi", value=default_start, min_value=min_date, max_value=max_date)
with col2:
    end_date = st.date_input("Bitiş Tarihi", value=default_end, min_value=min_date, max_value=max_date)

if start_date > end_date:
    st.warning("Başlangıç tarihi bitişten büyük. Bitiş tarihi başlangıca eşitlendi.")
    end_date = start_date

# --- 5) Kaynak filtresi ---
all_sources = sorted(df["kaynak"].dropna().unique().tolist()) if "kaynak" in df.columns else []
selected_sources = st.multiselect("Kaynak seç (boş = hepsi):", all_sources, default=all_sources)

# --- 6) Filtre uygula ---
mask_date = (df[parsed_helper_col] >= pd.to_datetime(start_date)) & \
            (df[parsed_helper_col] <= pd.to_datetime(end_date))

mask_source = True
if selected_sources:
    mask_source = df["kaynak"].isin(selected_sources)

df_filtered = df.loc[mask_date & mask_source].copy()

# ✅ Tekilleştirme checkbox'ı
unique_only = st.checkbox("🔁 Sipariş Numarasına Göre Tekilleştir (Son Kaydı Tut)", value=False)
if unique_only and "siparis_numarasi" in df_filtered.columns:
    if selected_dt_col in df_filtered.columns:
        df_filtered = df_filtered.sort_values(selected_dt_col)
    df_filtered = df_filtered.drop_duplicates(subset="siparis_numarasi", keep="last")

# --- Debug / Diagnostik ---
with st.expander("🔎 Parse Diagnostiği"):
    diag = {}
    for c in available_dt_cols:
        diag[c] = {
            "non_null": int(df[c].notna().sum()),
            "null": int(df[c].isna().sum()),
            "min": str(df[c].min()) if df[c].notna().any() else None,
            "max": str(df[c].max()) if df[c].notna().any() else None,
        }
    st.json(diag)

st.info(f"📅 {start_date} — {end_date} | Kaynak: {', '.join(selected_sources) if selected_sources else 'Tümü'} | "
        f"Eşleşen satır: {df_filtered.shape[0]}")
st.dataframe(df_filtered, use_container_width=True, height=450)

# --- 7) Görselleştirme ---
st.subheader("📊 Günlük Sipariş Grafiği")
if not df_filtered.empty:
    daily_counts = df_filtered.groupby(df_filtered[parsed_helper_col].dt.date).size()
    st.bar_chart(daily_counts)
else:
    st.warning("Filtre sonrası veri yok.")

# --- 8) CSV İndirme ---
@st.cache_data(show_spinner=False)
def to_csv_bytes(_df: pd.DataFrame) -> bytes:
    return _df.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇️ Filtrelenmiş CSV",
    data=to_csv_bytes(df_filtered),
    file_name=f"filtered_{selected_dt_col}_{start_date}_{end_date}.csv",
    mime="text/csv"
)
