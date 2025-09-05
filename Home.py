
# ============================== Home.py ==============================
import streamlit as st
import pandas as pd
from utils import (
    load_and_clean_excel, set_df, get_df, get_file_name, to_excel_bytes,
    ORDER_COL, BUYER_COL, PRODUCT_COL, QTY_COL, AMOUNT_COL
)

st.set_page_config(page_title="Sipariş Analiz Aracı", layout="wide")
st.title("📦 Sipariş Analiz Aracı — Ana Sayfa")

st.markdown(
    """
    **Not:** *Müşteri Sipariş Adedi* kolonu **kullanılmaz**. Tüm metrikler uygulama tarafından hesaplanır.
    """
)

up = st.file_uploader("Excel dosyası yükle (.xlsx)", type=["xlsx"], key="uploader")
if up:
    df = load_and_clean_excel(up.read())
    if df.empty:
        st.error("Geçerli veri bulunamadı. Dosya sayfalarında beklenen kolonlar yok olabilir.")
    else:
        set_df(df, file_name=up.name)
        st.success(f"{len(df):,} satır yüklendi: **{up.name}**")
        st.dataframe(df.head(50), use_container_width=True, height=320)

        # Hızlı metrikler
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Toplam Satır", f"{len(df):,}")
        with col2:
            st.metric("Farklı Alıcı", f"{df[BUYER_COL].nunique():,}")
        with col3:
            st.metric("Farklı Sipariş No", f"{df[ORDER_COL].nunique():,}")
        with col4:
            st.metric("Farklı Ürün", f"{df[PRODUCT_COL].nunique():,}")

        # Temiz veri Excel indirme
        xls = to_excel_bytes(df)
        st.download_button(
            "Temizlenmiş Veri (Excel)",
            data=xls,
            file_name=(get_file_name("veri.xlsx").replace(".xlsx", "") + "_clean.xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Başlamak için bir Excel dosyası yükleyin. Ardından üst menüden sayfalar arasında gezinebilirsiniz.")

