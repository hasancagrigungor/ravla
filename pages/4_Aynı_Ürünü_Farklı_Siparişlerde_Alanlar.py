# = pages/4_Aynı_Ürünü_Farklı_Siparişlerde_Alanlar.py =
import streamlit as st
import altair as alt
from utils import get_df, same_product_across_distinct_orders, PRODUCT_COL, BUYER_COL, to_excel_bytes, prepare_page_df, ORDER_COL

st.set_page_config(page_title="Ürün Bazlı Farklı Siparişler", layout="wide")
st.title("🔁 Aynı Ürünü Farklı Siparişlerde Alanlar")

required_cols = [PRODUCT_COL, BUYER_COL, ORDER_COL]
try:
    raw_df, df, mapping = prepare_page_df(required_cols, page_key="urun_farkli_siparis")
except Exception as e:
    st.warning(str(e))
    st.stop()
if df is None or df.empty:
    st.warning("Veri bulunamadı veya boş.")
    st.stop()

products = sorted(df[PRODUCT_COL].dropna().astype(str).unique())
sel_products = st.multiselect("Ürün(ler) seç", options=products, default=products[:1])
min_distinct_orders = st.number_input("Minimum farklı sipariş sayısı", min_value=2, step=1, value=4)

if sel_products:
    table = same_product_across_distinct_orders(df, sel_products)
    table = table[table["Farklı Sipariş Sayısı"] >= min_distinct_orders]
    table = table.sort_values(["Farklı Sipariş Sayısı", BUYER_COL], ascending=[False, True])

    st.write(f"Koşulu sağlayan satır sayısı: **{len(table):,}**")
    st.dataframe(table, use_container_width=True, height=420)

    st.download_button(
        "Excel indir (ürün bazlı farklı siparişler)",
        data=to_excel_bytes(table),
        file_name="urun_bazli_farkli_siparisler.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Grafik: ürün-buyer heatmap mantıklı
    if len(table) > 0:
        # Pivot benzeri görselleştirme
        chart = (
            alt.Chart(table)
            .mark_rect()
            .encode(
                x=alt.X(f"{BUYER_COL}:N", sort=None, title="Alıcı"),
                y=alt.Y(f"{PRODUCT_COL}:N", sort=None, title="Ürün"),
                color=alt.Color("Farklı Sipariş Sayısı:Q"),
                tooltip=[BUYER_COL, PRODUCT_COL, "Farklı Sipariş Sayısı"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
else:
    st.info("En az bir ürün seçiniz.")

