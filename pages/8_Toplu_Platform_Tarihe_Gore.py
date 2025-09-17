# app.py
import streamlit as st
import pandas as pd
import io
import os
from typing import List, Dict

st.set_page_config(page_title="Sipariş Birleştir & Tarih/Kaynak Filtresi", layout="wide")

st.title("📦 Sipariş CSV Birleştirici + Tarih & Kaynak Filtresi")

# --- 1) Ayarlar / Sabitler ---
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

# --- 2) Yardımcılar ---
def _to_strio(uploaded_file) -> io.StringIO:
    content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    return io.StringIO(content)

@st.cache_data(show_spinner=False)
def read_csv_auto(uploaded_file) -> pd.DataFrame:
    """CSV'yi önce sep=';' ile oku, kolonlar tekse otomatik sep ile yeniden dene."""
    s1 = _to_strio(uploaded_file)
    try:
        # Öncelikli olarak C engine + sep=";" dene
        df = pd.read_csv(s1, sep=";", on_bad_lines="skip", engine="c", low_memory=False)
        if len(df.columns) == 1:  # Yanlış ayrılmışsa fallback
            s2 = _to_strio(uploaded_file)
            df = pd.read_csv(s2, sep=None, engine="python", on_bad_lines="skip")
        return df
    except Exception:
        # Son fallback: otomatik algı + python engine
        s3 = _to_strio(uploaded_file)
        return pd.read_csv(s3, sep=None, engine="python", on_bad_lines="skip")

def normalize_columns(df: pd.DataFrame, columnsmap: Dict[str, List[str]]) -> pd.DataFrame:
    rename_dict = {}
    for std_col, alt_cols in columnsmap.items():
        for alt in alt_cols:
            if alt in df.columns:
                rename_dict[alt] = std_col
                break
    if not rename_dict:
        return pd.DataFrame()
    return df.rename(columns=rename_dict)[list(rename_dict.values())]

def normalize_date_columns_inplace(df: pd.DataFrame):
    date_cols = [c for c in df.columns if "tarih" in c.lower()]
    for col in date_cols:
        df[col] = df[col].astype(str).str.split().str[0]
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")

def detect_datetime_columns(df: pd.DataFrame, min_ratio: float = 0.2) -> List[str]:
    dt_cols = []
    for col in df.columns:
        ser = df[col]
        if ser.dtype == "O" or pd.api.types.is_string_dtype(ser):
            parsed = pd.to_datetime(ser, errors="coerce", dayfirst=True, infer_datetime_format=True)
            valid_ratio = parsed.notna().sum() / max(len(parsed), 1)
            if valid_ratio >= min_ratio and parsed.nunique(dropna=True) > 1:
                dt_cols.append(col)
    return sorted(dt_cols, key=lambda c: (0 if "tarih" in c.lower() else 1, c))

def add_source_column(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()
    df["kaynak"] = source_name
    return df

# --- 3) Upload ---
uploaded_files = st.file_uploader(
    "CSV dosyalarını yükle (çoklu seçim desteklenir)",
    type=["csv"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("👆 Başlamak için CSV dosyalarını yükle.")
    st.stop()

normalized_list = []
for uf in uploaded_files:
    try:
        df_raw = read_csv_auto(uf)
    except Exception as e:
        st.error(f"{uf.name} okunamadı: {e}")
        continue
    df_norm = normalize_columns(df_raw, COLUMNS_MAP)
    if df_norm.empty:
        st.warning(f"{uf.name}: Eşleşen kolon bulunamadı, atlandı.")
        continue
    df_norm = add_source_column(df_norm, os.path.basename(uf.name))
    normalized_list.append(df_norm)

if not normalized_list:
    st.error("Hiçbir dosyada eşleşen kolon bulunamadı.")
    st.stop()

df = pd.concat(normalized_list, ignore_index=True)
normalize_date_columns_inplace(df)

st.success(f"✅ Birleştirildi: {df.shape[0]} satır, {df.shape[1]} kolon")
with st.expander("Birleşik DataFrame (ilk 200 satır)"):
    st.dataframe(df.head(200), use_container_width=True)

# --- 4) Datetime & Kaynak Filtresi ---
st.subheader("⏱️ Tarih & Kaynak Filtresi")

candidate_dt_cols = detect_datetime_columns(df)
if not candidate_dt_cols:
    st.warning("Datetime parse edilebilir kolon bulunamadı.")
    st.stop()

selected_dt_col = st.selectbox("Datetime kolonu seç:", candidate_dt_cols, index=0)

parsed_dt = pd.to_datetime(df[selected_dt_col], errors="coerce", dayfirst=True, infer_datetime_format=True)
valid_mask = parsed_dt.notna()
min_date, max_date = parsed_dt[valid_mask].min().date(), parsed_dt[valid_mask].max().date()

col1, col2 = st.columns([1, 2])
with col1:
    selected_sources = st.multiselect(
        "Kaynak seç (boş = hepsi):",
        sorted(df["kaynak"].unique()),
        default=list(sorted(df["kaynak"].unique()))
    )
with col2:
    start_date, end_date = st.date_input(
        "Başlangıç / Bitiş Tarihi",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

mask_range = valid_mask & (parsed_dt.dt.date >= start_date) & (parsed_dt.dt.date <= end_date)
mask_source = df["kaynak"].isin(selected_sources) if selected_sources else True
df_filtered = df.loc[mask_range & mask_source].copy()

st.write(f"🔎 **Filtre sonucu:** {df_filtered.shape[0]} satır")

st.dataframe(df_filtered, use_container_width=True, height=450)

# --- 5) Görselleştirme ---
st.subheader("📊 Görselleştirme")
if not df_filtered.empty:
    df_filtered["_dt"] = pd.to_datetime(df_filtered[selected_dt_col], errors="coerce", dayfirst=True)
    daily_counts = df_filtered.groupby(df_filtered["_dt"].dt.date).size()
    st.bar_chart(daily_counts)
else:
    st.warning("Filtre sonrası veri bulunamadı, grafik gösterilemiyor.")

# --- 6) İndirme ---
@st.cache_data(show_spinner=False)
def to_csv_bytes(_df: pd.DataFrame) -> bytes:
    return _df.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇️ Filtrelenmiş CSV'yi indir",
    data=to_csv_bytes(df_filtered),
    file_name=f"siparis_filtresi_{selected_dt_col}_{start_date}_{end_date}.csv",
    mime="text/csv"
)
