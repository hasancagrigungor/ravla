# ======= pages/5_Harita_Ürün_Bazlı_Görselleştirme.py =======
import streamlit as st
import pandas as pd
import pydeck as pdk
from utils import (
    get_df, build_full_address, geocode_unique_addresses, PRODUCT_COL, QTY_COL,
    ORDER_COL, BUYER_COL, to_excel_bytes
)

st.set_page_config(page_title="Harita — Ürün Bazlı", layout="wide")
st.title("🗺️ Haritada Görselleştirme (Ürün Bazlı)")

df = get_df()
if df is None or df.empty:
    st.warning("Önce Ana Sayfa'dan veri yükleyin.")
    st.stop()

# Adres alanlarını seçtirme
st.subheader("Adres Bileşimi")
use_full = st.toggle("Sadece tam Teslimat Adresi kullan", value=False)
if use_full and "Teslimat Adresi" in df.columns:
    addr_series = df["Teslimat Adresi"].fillna("").astype(str)
else:
    use_fields = [c for c in ["Teslimat Adresi", "İlçe", "İl"] if c in df.columns]
    addr_series = build_full_address(df, use_fields)

# Ürün filtresi (çok seçim)
products = sorted(df[PRODUCT_COL].dropna().astype(str).unique())
sel_products = st.multiselect("Ürün(ler) seç (haritaya yansır)", products, default=products[:1])

# Veriyi filtrele ve konumları oluştur
fdf = df[df[PRODUCT_COL].isin(sel_products)].copy()
fdf["__addr__"] = addr_series

# Tekilleştirilmiş adresler
uniq_addrs = sorted(set([a for a in fdf["__addr__"].dropna().astype(str) if a.strip()]))
cap = st.number_input("En fazla kaç benzersiz adres geocode edilsin?", min_value=100, max_value=20000, value=min(5000, len(uniq_addrs)))
uniq_addrs = uniq_addrs[:cap]

provider = st.selectbox("Geocode sağlayıcı", options=["ArcGIS", "Nominatim"], index=0, help="ArcGIS genelde daha stabil ve hızlıdır. Nominatim halka açık ve limitlidir.")

if st.button("Adresleri Koordinata Çevir (Geocode)"):
    geo = geocode_unique_addresses(uniq_addrs, provider=provider)
    st.session_state["__GEO_CACHE__"] = geo

geo = st.session_state.get("__GEO_CACHE__")
if isinstance(geo, pd.DataFrame) and not geo.empty:
    # Join ile koordinatları satırlara bağla
    gdf = fdf.merge(geo, left_on="__addr__", right_on="address", how="left")
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

