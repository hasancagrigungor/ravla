# app.py
import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime, timedelta, date
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

st.set_page_config(page_title="Sipariş Analizi (Trendyol + Hepsiburada)", layout="wide")
st.title("📦 Sipariş Birleştirici & Analiz Paneli")

# -----------------------------
# Yardımcı Fonksiyonlar
# -----------------------------
COLUMNS_MAP = {
    # Standard -> olası kaynak başlıkları
    "barkod": ["Barkod"],
    "paketno": ["Paket Numarası", "Paket No", "Paket No."],
    "kargo": ["Kargo Firması"],
    "siparis_tarihi": ["Sipariş Tarihi"],
    "kargo_kabul_tarihi": [
        "Kargo Kabul Tarihi",
        "Kargoya Teslim Tarihi",
        "Kargoya Son Teslim Tarihi",  # bazı TY dosyalarında olabilir
    ],
    "kargo_no": ["Kargo Takip No", "Kargo Kodu"],
    "siparis_no": ["Sipariş Numarası"],
    "urun": ["Ürün Adı"],
    "adet": ["Adet"],
    "paket": ["Paket Durumu", "Sipariş Statüsü"],
    "teslim": ["Teslim Tarihi"],
}

def detect_source_from_name(name: str) -> str:
    n = name.lower()
    if "trendyol" in n or "ty" in n:
        return "trendyol"
    if "hepsiburada" in n or "hb" in n or "hepsi" in n:
        return "hepsiburada"
    return "bilinmiyor"

def read_csv_safely(file) -> pd.DataFrame:
    # Hepsiburada çoğu zaman ; ile gelir. Önce ; deneriz, olmazsa , deneriz.
    try:
        df = pd.read_csv(file, sep=";", low_memory=False)
        # Boş/tek kolon geldiyse alternatif dene
        if df.shape[1] <= 1:
            file.seek(0)
            df = pd.read_csv(file, sep=",", low_memory=False)
    except Exception:
        file.seek(0)
        df = pd.read_csv(file, sep=",", low_memory=False)
    return df

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    for std_col, candidates in COLUMNS_MAP.items():
        for c in candidates:
            if c in df.columns:
                out[std_col] = df[c]
                break
        # bulunamazsa oluştur
        if std_col not in out.columns:
            out[std_col] = np.nan
    # tip düzeltmeleri
    # adet
    out["adet"] = pd.to_numeric(out["adet"], errors="coerce").fillna(0).astype(int)
    # string kolonlar
    for c in ["barkod", "paketno", "kargo", "kargo_no", "siparis_no", "urun", "paket"]:
        out[c] = out[c].astype(str).str.strip()
    return out

def parse_dates_inplace(df: pd.DataFrame):
    for col in ["siparis_tarihi", "kargo_kabul_tarihi", "teslim"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True).dt.date

def kpi_metrics(df_filtered: pd.DataFrame):
    # Toplam Alışveriş (unique paket)
    toplam_alisveris = df_filtered["paketno"].nunique()
    # Toplam Ürün (unique urun)
    toplam_urun = df_filtered["urun"].nunique()
    # Toplam Adet
    toplam_adet = df_filtered["adet"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("🧾 Toplam Alışveriş (Paket)", f"{toplam_alisveris}")
    c2.metric("🛍️ Toplam Ürün (Benzersiz)", f"{toplam_urun}")
    c3.metric("📦 Toplam Adet", f"{toplam_adet:,}".replace(",", "."))

def build_pdf(df_filtered: pd.DataFrame, df_daily: pd.DataFrame, df_top_urun: pd.DataFrame, chosen_date_col: str) -> bytes:
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # Sayfa 1: KPI'lar
        fig = plt.figure(figsize=(8.27, 11.69))  # A4 portre
        plt.axis('off')
        plt.text(0.5, 0.95, "Sipariş Analiz Özeti", ha='center', fontsize=18, fontweight='bold')
        plt.text(0.5, 0.91, f"Tarih Alanı: {chosen_date_col}", ha='center', fontsize=10)

        toplam_alisveris = df_filtered["paketno"].nunique()
        toplam_urun = df_filtered["urun"].nunique()
        toplam_adet = int(df_filtered["adet"].sum())

        txt = (
            f"Toplam Alışveriş (Paket): {toplam_alisveris}\n"
            f"Toplam Ürün (Benzersiz): {toplam_urun}\n"
            f"Toplam Adet: {toplam_adet}\n"
            f"Trendyol/Hepsiburada Kırılımı:\n"
        )
        plt.text(0.1, 0.80, txt, va='top', fontsize=12)

        if "kaynak" in df_filtered.columns:
            brk = df_filtered.groupby("kaynak").agg(
                paket_sayisi=("paketno", "nunique"),
                adet=("adet", "sum")
            ).reset_index()
            tbl_text = "\n".join([f"- {r.kaynak}: paket={r.paket_sayisi}, adet={r.adet}" for _, r in brk.iterrows()])
            plt.text(0.1, 0.63, tbl_text if not brk.empty else "- veri yok", va='top', fontsize=12)

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # Sayfa 2: Top 10 ürün bar
        if not df_top_urun.empty:
            fig = plt.figure(figsize=(11.69, 8.27))  # A4 yatay
            top10 = df_top_urun.head(10)
            plt.barh(top10["urun"][::-1], top10["adet_toplam"][::-1])
            plt.title("En Çok Satan 10 Ürün (Adet)")
            plt.xlabel("Adet")
            plt.ylabel("Ürün")
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

        # Sayfa 3: Günlük satış (adet) çizgi
        if not df_daily.empty:
            fig = plt.figure(figsize=(11.69, 8.27))
            plt.plot(df_daily[chosen_date_col], df_daily["adet"], marker="o")
            plt.title("Günlere Göre Toplam Adet")
            plt.xlabel("Tarih")
            plt.ylabel("Adet")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    buf.seek(0)
    return buf.read()

# -----------------------------
# Sidebar: Yükleme & Kontroller
# -----------------------------

st.subheader("⚙️ Ayarlar")  # Artık ana gövde içinde

# ---- 1) Dosya yükleme (tek satırda tam genişlik) ----
uploaded = st.file_uploader(
    "CSV dosyalarını yükleyin (çoklu seçim desteklenir)",
    type=["csv"],
    accept_multiple_files=True,
    help="Dosya adında 'trendyol' veya 'hb/hepsiburada' geçerse kaynak otomatik atanır."
)

# ---- 2) Tarih ve filtre ayarları (yan yana kolonlar) ----
today = date.today()
default_start = today - timedelta(days=30)

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    date_col_choice = st.selectbox(
        "📅 Tarih filtresi kolon",
        options=["siparis_tarihi", "kargo_kabul_tarihi", "teslim"],
        index=0,
        help="Seçilen kolon tarih aralığı filtresinde kullanılacaktır."
    )

with col2:
    start_date = st.date_input("Başlangıç", value=default_start)

with col3:
    end_date = st.date_input("Bitiş", value=today)

# Hata kontrolü
if start_date > end_date:
    st.error("❌ Başlangıç tarihi, bitiş tarihinden büyük olamaz.")

# -----------------------------
# Veri Yükleme & Birleştirme
# -----------------------------
all_rows = []

if uploaded:
    for uf in uploaded:
        src = detect_source_from_name(uf.name)
        df_raw = read_csv_safely(uf)
        df_norm = normalize_columns(df_raw)
        parse_dates_inplace(df_norm)
        df_norm["kaynak"] = src
        all_rows.append(df_norm)

if all_rows:
    df = pd.concat(all_rows, ignore_index=True)

    # Tarih filtresi
    if date_col_choice not in df.columns:
        st.warning(f"Seçilen tarih kolonu '{date_col_choice}' veride bulunamadı. Otomatik 'siparis_tarihi' denenecek.")
        effective_date_col = "siparis_tarihi"
    else:
        effective_date_col = date_col_choice

    # sadece tarih değeri olan satırlar
    df = df[~df[effective_date_col].isna()].copy()

    mask = (df[effective_date_col] >= start_date) & (df[effective_date_col] <= end_date)
    df_filtered = df.loc[mask].copy()

    # Paket özelinde unique (ilk görülen)
    dfg = df_filtered.sort_values(by=[effective_date_col]).drop_duplicates(subset=["paketno"], keep="first")

    # Üst KPI'lar
    kpi_metrics(df_filtered)

    # Alt bölüm: grafikler ve tablolar
    st.subheader("📈 Analizler")

    # Günlük toplamlara göre tablo/çizgi
    if not df_filtered.empty:
        daily = df_filtered.groupby(effective_date_col, as_index=False).agg(
            paket_sayisi=("paketno", "nunique"),
            adet=("adet", "sum")
        )
        # En çok satan ürünler (adet)
        top_urun = df_filtered.groupby("urun", as_index=False).agg(adet_toplam=("adet", "sum")).sort_values("adet_toplam", ascending=False)

        # Layout
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Günlere Göre Toplam Adet**")
            st.line_chart(
                data=daily.set_index(effective_date_col)["adet"],
                use_container_width=True
            )
        with c2:
            st.markdown("**En Çok Satan 10 Ürün (Adet)**")
            st.bar_chart(
                data=top_urun.head(10).set_index("urun")["adet_toplam"],
                use_container_width=True
            )

        # Kaynak kırılımı
        st.markdown("### 🧩 Kaynak Kırılımı")
        by_src = df_filtered.groupby("kaynak", as_index=False).agg(
            paket_sayisi=("paketno", "nunique"),
            adet=("adet", "sum")
        )
        st.dataframe(by_src, use_container_width=True)

        # Tablolar
        with st.expander("🔎 Satır Bazlı (Filtrelenmiş)"):
            st.dataframe(df_filtered, use_container_width=True)
        with st.expander("📦 Paket Bazlı (Unique)"):
            st.dataframe(dfg, use_container_width=True)
        with st.expander("📅 Günlük Özet"):
            st.dataframe(daily, use_container_width=True)
        with st.expander("🏷️ Ürün Özet (Adet)"):
            st.dataframe(top_urun, use_container_width=True)

        # İndirme: Excel
        xbuf = io.BytesIO()
        with pd.ExcelWriter(xbuf, engine="xlsxwriter") as writer:
            df_filtered.to_excel(writer, index=False, sheet_name="satirlar")
            dfg.to_excel(writer, index=False, sheet_name="paketler")
            daily.to_excel(writer, index=False, sheet_name="gunluk_ozet")
            top_urun.to_excel(writer, index=False, sheet_name="urun_ozet")
            by_src.to_excel(writer, index=False, sheet_name="kaynak_ozet")
        xbuf.seek(0)
        st.download_button(
            label="⬇️ Excel indir",
            data=xbuf.getvalue(),
            file_name=f"siparis_analiz_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # İndirme: PDF (KPI + 2 grafik)
        pdf_bytes = build_pdf(
            df_filtered=df_filtered,
            df_daily=daily.rename(columns={effective_date_col: "tarih"}).rename(columns={"tarih": effective_date_col}),
            df_top_urun=top_urun,
            chosen_date_col=effective_date_col
        )
        st.download_button(
            label="⬇️ PDF indir (KPI + Grafikler)",
            data=pdf_bytes,
            file_name=f"siparis_ozet_{start_date}_{end_date}.pdf",
            mime="application/pdf"
        )

    else:
        st.info("Seçtiğiniz tarih aralığında veri bulunamadı. Tarih aralığını genişletmeyi deneyin.")

else:
    st.info("Başlamak için soldan CSV dosyalarınızı yükleyin. Dosya adında 'trendyol' veya 'hb/hepsiburada' geçerse kaynak otomatik atanır.")
