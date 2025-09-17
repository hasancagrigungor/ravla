# ==================== pages/3_Toplam_Miktar_Eşiği.py ====================
import streamlit as st
import altair as alt
from utils import get_df, buyers_over_total_qty, BUYER_COL, to_excel_bytes, prepare_page_df, QTY_COL

st.set_page_config(page_title="Toplam Miktar Eşiği", layout="wide")
st.title("📈 Toplam Adet Eşiğini Aşan Alıcılar")

required_cols = [BUYER_COL, QTY_COL]
try:
    raw_df, df, mapping = prepare_page_df(required_cols, page_key="toplam_adet_esigi")
except Exception as e:
    st.warning(str(e))
    st.stop()
if df is None or df.empty:
    st.warning("Veri bulunamadı veya boş.")
    st.stop()

over = buyers_over_total_qty(df)
min_total = st.number_input("Minimum toplam adet (alıcı bazında)", min_value=1, step=1, value=10)
over_f = over[over["Toplam Adet"] >= min_total].sort_values("Toplam Adet", ascending=False)

st.write(f"Koşulu sağlayan alıcı sayısı: **{len(over_f):,}**")
st.dataframe(over_f, use_container_width=True, height=420)

st.download_button(
    "Excel indir (toplam adet eşiği)",
    data=to_excel_bytes(over_f),
    file_name="toplam_adet_esigi.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# Grafik: Top N çubuk grafiği
top_n = st.slider("Grafikte gösterilecek üst sıra (N)", min_value=5, max_value=min(100, len(over_f) if len(over_f)>0 else 5), value=min(20, len(over_f) if len(over_f)>0 else 5))
if len(over_f) > 0:
    gdf = over_f.head(top_n)
    chart = (
        alt.Chart(gdf)
        .mark_bar()
        .encode(x=alt.X("Alıcı:N", sort=None), y=alt.Y("Toplam Adet:Q"), tooltip=["Alıcı", "Toplam Adet"])
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)

