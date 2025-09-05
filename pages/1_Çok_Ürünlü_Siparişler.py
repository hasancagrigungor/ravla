# ====================== pages/1_Çok_Ürünlü_Siparişler.py ======================
import streamlit as st
import altair as alt
from utils import get_df, ORDER_COL, PRODUCT_COL, to_excel_bytes

st.set_page_config(page_title="Çok Ürünlü Siparişler", layout="wide")
st.title("🧺 Tek Siparişte Birden Fazla Ürün")

df = get_df()
if df is None or df.empty:
    st.warning("Önce Ana Sayfa'dan veri yükleyin.")
    st.stop()

min_items = st.number_input("Minimum farklı ürün sayısı", min_value=2, step=1, value=2)

grp = df.groupby(ORDER_COL)[PRODUCT_COL].nunique().reset_index(name="Farklı Ürün Sayısı")
mask = grp["Farklı Ürün Sayısı"] >= min_items
many_orders = grp[mask]

st.write(f"Koşulu sağlayan sipariş: **{len(many_orders):,}**")

if len(many_orders) > 0:
    detay = df.merge(many_orders[[ORDER_COL]], on=ORDER_COL, how="inner")
    st.dataframe(detay.sort_values([ORDER_COL, PRODUCT_COL]), use_container_width=True, height=420)

    # Excel indir
    st.download_button(
        "Excel indir (çok ürünlü siparişler)",
        data=to_excel_bytes(detay),
        file_name="cok_urunlu_siparisler.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Mantıklı grafik: Farklı ürün sayısına göre sipariş sayısı
    dist = grp.groupby("Farklı Ürün Sayısı")[ORDER_COL].nunique().reset_index(name="Sipariş Sayısı")
    chart = (
        alt.Chart(dist)
        .mark_bar()
        .encode(x="Farklı Ürün Sayısı:O", y="Sipariş Sayısı:Q", tooltip=["Farklı Ürün Sayısı", "Sipariş Sayısı"])
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Koşulu sağlayan sipariş bulunamadı.")

