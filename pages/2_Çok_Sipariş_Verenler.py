# ==================== pages/2_Çok_Sipariş_Verenler.py ====================
import streamlit as st
import altair as alt
from utils import get_df, buyer_summary, BUYER_COL, to_excel_bytes

st.set_page_config(page_title="Çok Sipariş Verenler", layout="wide")
st.title("👤 Birden Fazla Sipariş Veren Alıcılar")

df = get_df()
if df is None or df.empty:
    st.warning("Önce Ana Sayfa'dan veri yükleyin.")
    st.stop()

summary = buyer_summary(df)

col1, col2 = st.columns([1, 2])
with col1:
    # Eşik değeri
    min_orders = st.number_input("Farklı sipariş adedi", min_value=1, step=1, value=2)
with col2:
    # Karşılaştırma türü
    cmp = st.radio("Karşılaştırma", ["≥", "=", "≤", ">"], index=0, horizontal=True)

# Filtreleme
if cmp == "≥":
    summary_f = summary[summary["Farklı Sipariş Sayısı"] >= min_orders].copy()
elif cmp == ">":
    summary_f = summary[summary["Farklı Sipariş Sayısı"] > min_orders].copy()
elif cmp == "=":
    summary_f = summary[summary["Farklı Sipariş Sayısı"] == min_orders].copy()
else:  # "≤"
    summary_f = summary[summary["Farklı Sipariş Sayısı"] <= min_orders].copy()

# Sıralama
sort_options = ["Farklı Sipariş Sayısı", "Toplam Adet"] + (
    ["Toplam Tutar"] if "Toplam Tutar" in summary_f.columns else []
)
sort_by = st.selectbox("Sırala", options=sort_options, index=0)
ascending = st.toggle("Artan sırala", value=False)
summary_f = summary_f.sort_values(sort_by, ascending=ascending)

st.write(f"Koşulu sağlayan alıcı sayısı: **{len(summary_f):,}**")
st.dataframe(summary_f, use_container_width=True, height=420)

st.download_button(
    "Excel indir (çok sipariş verenler özet)",
    data=to_excel_bytes(summary_f),
    file_name="cok_siparis_verenler_ozet.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# Grafik: Top N çubuk grafiği (veri varsa)
if len(summary_f) > 0:
    top_n = st.slider(
        "Grafikte gösterilecek üst sıra (N)",
        min_value=1,
        max_value=min(100, len(summary_f)),
        value=min(20, len(summary_f)),
    )
    gdf = summary_f.head(top_n)
    chart = (
        alt.Chart(gdf)
        .mark_bar()
        .encode(
            x=alt.X(f"{BUYER_COL}:N", sort=None, title="Alıcı"),
            y=alt.Y(f"{sort_by}:Q"),
            tooltip=[BUYER_COL, sort_by],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Seçtiğin koşulu sağlayan alıcı bulunamadı.")
