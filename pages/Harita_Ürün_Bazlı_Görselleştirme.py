# ======= pages/5_Harita_Ürün_Bazlı_Görselleştirme.py =======
import streamlit as st
import pandas as pd
import pydeck as pdk
from utils import (
    get_df, build_full_address, geocode_unique_addresses, geocode_il_ilce, PRODUCT_COL, QTY_COL,
    ORDER_COL, BUYER_COL, to_excel_bytes, prepare_page_df
)

st.set_page_config(page_title="Harita — Ürün Bazlı", layout="wide")
st.title("🗺️ Haritada Görselleştirme (Ürün Bazlı)")

required_cols = ["İl", "İlçe", PRODUCT_COL, QTY_COL]
try:
    raw_df, df, mapping = prepare_page_df(required_cols, page_key="harita")
except Exception as e:
    st.warning(str(e))
    st.stop()
if df is None or df.empty:
    st.warning("Veri bulunamadı veya boş.")
    st.stop()

# Sadece İl ve İlçe bazlı çalışacağız (daha hızlı)
st.info("Harita yalnızca İl ve İlçe bazında çalışır (hızlı). Eksik İl/İlçe olan satırlar atılabilir.")
use_fields = [c for c in ["İl", "İlçe"] if c in df.columns]
if len(use_fields) < 1:
    st.error("Veride 'İl' veya 'İlçe' sütunu bulunamadı.")
    st.stop()
addr_series = build_full_address(df, use_fields)

# Ürün filtresi (çok seçim)
products = sorted(df[PRODUCT_COL].dropna().astype(str).unique())
sel_products = st.multiselect("Ürün(ler) seç (haritaya yansır)", products, default=products[:1])

# Veriyi filtrele ve konumları oluştur
fdf = df[df[PRODUCT_COL].isin(sel_products)].copy()
fdf["__il__"] = fdf[[c for c in ["İl", "İlçe"] if c in fdf.columns][0]] if "İl" in fdf.columns else None
fdf["__ilce__"] = fdf[[c for c in ["İlçe", "İl"] if c in fdf.columns][0]] if "İlçe" in fdf.columns else None

# Tekilleştirilen il-ilçe çiftleri
pairs = sorted(set([(str(x).strip(), str(y).strip()) for x, y in zip(fdf["İl"].fillna(""), fdf["İlçe"].fillna("")) if str(x).strip() or str(y).strip()]))
cap = st.number_input("En fazla kaç benzersiz il-ilçe geocode edilsin?", min_value=10, max_value=20000, value=min(1000, len(pairs)))
pairs = pairs[:cap]

provider = st.selectbox("Geocode sağlayıcı", options=["ArcGIS", "Nominatim"], index=0, help="ArcGIS genelde daha stabil ve hızlıdır. Nominatim halka açık ve limitlidir.")

if st.button("İl-İlçe Koordinatlarını Al (Cache kullanılır)"):
    geo_pairs = geocode_il_ilce(pairs, provider=provider)
    st.session_state["__GEO_CACHE__"] = geo_pairs

geo_pairs = st.session_state.get("__GEO_CACHE__")
if isinstance(geo_pairs, pd.DataFrame) and not geo_pairs.empty:
    # Join ile koordinatları satırlara bağla: önce il-ilçe -> lat/lon
    geo_pairs = geo_pairs.dropna(subset=["lat", "lon"])  # koordinatı olmayanları at
    gdf = fdf.merge(geo_pairs, left_on=["İl", "İlçe"], right_on=["il", "ilce"], how="left")
    gdf = gdf.dropna(subset=["lat", "lon"])  # koordinatı olmayanları at

    st.success(f"Haritada gösterilecek satır: {len(gdf):,}")

    # Ürün bazında adetleri toplayıp nokta yarıçapını ölçekle
    # (Aynı adres+ürün için toplanmış nokta)
    agg = (
        gdf.groupby(["address", "lat", "lon", PRODUCT_COL])[QTY_COL]
        .sum()
        .reset_index(name="Toplam Adet")
    )

    # PyDeck gösterim
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=agg,
        get_position="[lon, lat]",
        get_radius="100 + 20 * sqrt(Toplam Adet)",
        radius_min_pixels=3,
        radius_max_pixels=60,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(latitude=float(agg["lat"].mean()), longitude=float(agg["lon"].mean()), zoom=5)
    deck = pdk.Deck(layers=[layer], initial_view_state=view_state, map_style="mapbox://styles/mapbox/light-v9")
    st.pydeck_chart(deck)

    # Excel indir (koordinatlı veri)
    st.download_button(
        "Excel indir (koordinatlı veri)",
        data=to_excel_bytes(agg),
        file_name="koordinatli_urun_verisi.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Koordinat üretmek için 'Adresleri Koordinata Çevir' butonunu kullanın.")

