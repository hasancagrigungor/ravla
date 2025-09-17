# =============== pages/6_Raporlar_Excel_İndir.py ===============
import streamlit as st
from utils import (
    get_df, buyer_summary, orders_with_many_products, buyers_over_total_qty,
    ORDER_COL, PRODUCT_COL, BUYER_COL, QTY_COL, to_excel_bytes, prepare_page_df
)

st.set_page_config(page_title="Raporlar — Excel İndir", layout="wide")
st.title("📥 Raporlar — Toplu Excel İndir")

required_cols = [ORDER_COL, PRODUCT_COL, BUYER_COL, QTY_COL]
try:
    raw_df, df, mapping = prepare_page_df(required_cols, page_key="raporlar")
except Exception as e:
    st.warning(str(e))
    st.stop()
if df is None or df.empty:
    st.warning("Veri bulunamadı veya boş.")
    st.stop()

st.subheader("Parametreler")
col1, col2, col3 = st.columns(3)
with col1:
    min_items = st.number_input("(1) Çok ürünlü siparişte min. farklı ürün", min_value=2, step=1, value=2)
with col2:
    min_orders = st.number_input("(2) Çok sipariş verenler için min. sipariş sayısı", min_value=2, step=1, value=2)
with col3:
    min_total_qty = st.number_input("(3) Toplam adet eşiği (alıcı)", min_value=1, step=1, value=10)

# Hesaplar
cok_urun = orders_with_many_products(df)
cok_urun = cok_urun[cok_urun["Farklı Ürün Sayısı"] >= min_items]
cok_urun_detay = df.merge(cok_urun[[ORDER_COL]], on=ORDER_COL, how="inner")

cok_siparis = buyer_summary(df)
cok_siparis = cok_siparis[cok_siparis["Farklı Sipariş Sayısı"] >= min_orders]

toplam_adet = buyers_over_total_qty(df)
toplam_adet = toplam_adet[toplam_adet["Toplam Adet"] >= min_total_qty]

sheets = {
    "CokUrunlu_Siparis_Ozet": cok_urun,
    "CokUrunlu_Siparis_Detay": cok_urun_detay,
    "CokSiparisVerenler_Ozet": cok_siparis,
    "ToplamAdet_Esigi": toplam_adet,
}

excel_bytes = to_excel_bytes(sheets)

st.download_button(
    "Excel indir (Toplu Rapor)",
    data=excel_bytes,
    file_name="toplu_raporlar.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.markdown("""
**İçerik**  
- `CokUrunlu_Siparis_Ozet`: Sipariş no başına farklı ürün sayısı ≥ eşiği geçenler  
- `CokUrunlu_Siparis_Detay`: Yukarıdakilerin satır detayları  
- `CokSiparisVerenler_Ozet`: Alıcı bazında farklı sipariş sayısı/Toplam Adet(/Toplam Tutar)  
- `ToplamAdet_Esigi`: Alıcı bazında toplam Adet ≥ eşiği geçenler
""")