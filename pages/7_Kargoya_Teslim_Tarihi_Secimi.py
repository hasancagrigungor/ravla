import streamlit as st
import pandas as pd
from utils import prepare_page_df, to_excel_bytes

st.set_page_config(page_title="Kargoya Teslim Tarihi Seçimi", layout="wide")
st.title("📦 Kargoya Teslim Tarihi Seçimi — Çoklu Tarih & Ürün Dağılımı")

# Required columns for this page
required_cols = ["Kargoya Teslim Tarihi", "Paket No", "Ürün Adı", "Adet"]
try:
    raw_df, df, mapping = prepare_page_df(required_cols, page_key="kargoya_teslim")
except Exception as e:
    st.warning(str(e))
    st.stop()

# Ensure datetime
kargoya_col = next((c for c in df.columns if str(c).replace(" ", "") == "KargoyaTeslimTarihi" or c == "Kargoya Teslim Tarihi"), None)
if not kargoya_col:
    st.error("'Kargoya Teslim Tarihi' sütunu bulunamadı. Lütfen eşleştirme yapın.")
    st.stop()

# Convert ALL date columns to datetime.date for consistent formatting with Streamlit
date_keywords = ["tarih", "tarihi", "date", "time"]
for col in df.columns:
    col_lower = str(col).lower()
    if any(keyword in col_lower for keyword in date_keywords):
        try:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        except:
            pass  # Skip if conversion fails

if df[kargoya_col].dropna().empty:
    st.warning("Kargoya Teslim Tarihi sütununda geçerli tarih bulunamadı.")

available_dates = sorted(df[kargoya_col].dropna().unique())
if not available_dates:
    st.info("Veride seçilebilir 'Kargoya Teslim Tarihi' yok.")
    st.stop()

sel_dates = st.multiselect("Kargoya Teslim Tarihi(ler) seçin", options=available_dates, default=available_dates[:1])
only_selected = df[df[kargoya_col].isin(sel_dates)] if sel_dates else pd.DataFrame(columns=df.columns)

# Göster: kullanılabilir tarihlerin listesi (dataframe olarak)
st.write("### Kullanılabilir Kargoya Teslim Tarihleri")
st.dataframe(pd.DataFrame({"date": available_dates}), use_container_width=True, height=150)

# Göster: filtrelenmiş satırlar
st.write("### Filtrelenmiş Satırlar")
st.dataframe(only_selected, use_container_width=True, height=300)

# Package count distribution: count unique Paket No per Sipariş Numarası (veya per Paket No?)
# We interpret "bazılarında 1 bazılarında 2..." as number of distinct Paket No per order (Sipariş Numarası)
order_col = "Sipariş Numarası" if "Sipariş Numarası" in df.columns else None
paket_col = "Paket No" if "Paket No" in df.columns else None

st.subheader("Genel Özet")
if sel_dates:
    total_qty = only_selected["Adet"].sum() if "Adet" in only_selected.columns else len(only_selected)
    st.metric("Seçilen tarihlerde toplam Adet", f"{int(total_qty):,}")

    # Paket sayısına göre dağılım (sipariş başına paket sayısı)
    if order_col and paket_col and order_col in only_selected.columns and paket_col in only_selected.columns:
        pkg_per_order = only_selected.groupby(order_col)[paket_col].nunique().reset_index(name="Paket Sayısı")
        dist = pkg_per_order["Paket Sayısı"].value_counts().sort_index()
        st.write("### Paket Sayısı Dağılımı (Sipariş başına)")
        st.dataframe(dist.rename("Sipariş Sayısı").reset_index().rename(columns={"index":"Paket Sayısı"}), use_container_width=True)
    else:
        st.info("Paket sayısı dağılımı için 'Sipariş Numarası' veya 'Paket No' sütunu bulunamadı.")

    # Ürün bazında adetler; ürün isimleri içinde "/" ile ayrılmış çoklu ürünleri ayır
    st.write("### Ürün Bazında Toplam Adet (isimleri '/' ile ayrılmış olanlar parçalanır)")
    prod_col = "Ürün Adı" if "Ürün Adı" in only_selected.columns else None
    qty_col = "Adet" if "Adet" in only_selected.columns else None
    if prod_col and qty_col:
        # Split product names that contain '/'
        rows = []
        for _, r in only_selected[[prod_col, qty_col]].dropna().iterrows():
            name = str(r[prod_col])
            qty = r[qty_col] if pd.notna(r[qty_col]) else 0
            parts = [p.strip() for p in name.split("/") if p.strip()]
            if len(parts) <= 1:
                rows.append({"product": name, "qty": qty})
            else:
                # If multiple products in one cell, try to split qty evenly if possible, else keep as-is per part
                per = qty // len(parts) if isinstance(qty, (int, float)) and qty >= len(parts) else None
                if per:
                    for p in parts:
                        rows.append({"product": p, "qty": per})
                else:
                    # fallback: assign the whole qty to each product (user can adjust)
                    for p in parts:
                        rows.append({"product": p, "qty": qty})
        pdf = pd.DataFrame(rows)
        if not pdf.empty:
            agg = pdf.groupby("product")["qty"].sum().reset_index().sort_values("qty", ascending=False)
            st.dataframe(agg, use_container_width=True)
            st.download_button("Excel indir (ürün dağılım)", data=to_excel_bytes(agg), file_name="kargoya_urun_dagilim.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Seçili tarihlerde ürün-veri bulunamadı.")
    else:
        st.info("Ürün bazlı dağılım için 'Ürün Adı' veya 'Adet' sütunu bulunamadı.")

    # Ayrıca hangi tarihte hangi üründen kaç adet gerektiği tablosu
    st.write("### Tarih-Ürün Kırılımı")
    if prod_col and qty_col:
        only_selected["_date"] = only_selected[kargoya_col]  # Already converted to date above
        # Expand product splitting similar to above, but keep date
        rows = []
        for _, r in only_selected[["_date", prod_col, qty_col]].dropna().iterrows():
            name = str(r[prod_col])
            qty = r[qty_col] if pd.notna(r[qty_col]) else 0
            parts = [p.strip() for p in name.split("/") if p.strip()]
            if len(parts) <= 1:
                rows.append({"date": r["_date"], "product": name, "qty": qty})
            else:
                per = qty // len(parts) if isinstance(qty, (int, float)) and qty >= len(parts) else None
                if per:
                    for p in parts:
                        rows.append({"date": r["_date"], "product": p, "qty": per})
                else:
                    for p in parts:
                        rows.append({"date": r["_date"], "product": p, "qty": qty})
        tdf = pd.DataFrame(rows)
        if not tdf.empty:
            tagg = tdf.groupby(["date", "product"]) ["qty"].sum().reset_index().sort_values(["date", "qty"], ascending=[True, False])
            st.dataframe(tagg, use_container_width=True, height=400)
            st.download_button("Excel indir (tarih-ürün kırılım)", data=to_excel_bytes(tagg), file_name="kargoya_tarih_urun_kirilim.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Tarih-ürün kırılımı için veri yok.")
    else:
        st.info("Tarih-ürün kırılımı için gerekli sütunlar eksik.")

else:
    st.info("Lütfen en az bir tarih seçin.")
