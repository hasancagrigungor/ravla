import streamlit as st
import pandas as pd
import datetime

st.title("Termin Süresi Biten Siparişler")

required_columns = [
    'Barkod', 'Paket No', 'Kargo Firması', 'Sipariş Tarihi',
    'Termin Süresinin Bittiği Tarih', 'Kargoya Teslim Tarihi', 'Kargo Kodu',
    'Sipariş Numarası', 'Alıcı', 'Teslimat Adresi', 'İl', 'İlçe',
    'Ürün Adı', 'Fatura Adresi', 'Alıcı - Fatura Adresi', 'Sipariş Statüsü',
    'E-Posta', 'Komisyon Oranı', 'Marka', 'Stok Kodu', 'Adet',
    'Birim Fiyatı', 'Satış Tutarı', 'İndirim Tutarı',
    'Trendyol İndirim Tutarı', 'Faturalanacak Tutar', 'Butik Numarası',
    'Teslim Tarihi', 'Kargodan alınan desi', 'Hesapladığım desi',
    'Faturalanan Kargo Tutarı', 'Alternatif Teslimat Statüsü',
    'Kurumsal Faturalı Sipariş', 'Vergi Kimlik Numarası', 'Vergi Dairesi',
    'Şirket İsmi', 'Fatura', 'Müşteri Sipariş Adedi', 'Mikro İhracat',
    'ETGB No', 'ETGB Tarihi', 'Yaş', 'Cinsiyet', 'Kargo Partner İsmi',
    '2.Teslimat Paketi Statüsü', '2.Teslimat Takip Numarası',
    'Teslimat Numarası', 'Fatura No', 'Fatura Tarihi', 'Ülke',
    'Müşteri Telefon No', 'ETGB Statüsü'
]

try:
    from utils import prepare_page_df
except Exception:
    prepare_page_df = None

if prepare_page_df is None:
    st.error("Hazırlık fonksiyonu bulunamadı. utils.py güncel mi?")
else:
    try:
        raw_df, view_df, mapping = prepare_page_df(required_columns, page_key="termin")
    except ValueError as e:
        st.error(str(e))
        st.stop()

    df = view_df
    # Artık df üzerinde eskiden olduğu gibi devam et
    termin_col = next((c for c in df.columns if c.replace(" ","") == "TerminSüresininBittiğiTarih"), None)
    if not termin_col:
        st.error("'Termin Süresinin Bittiği Tarih' sütunu bulunamadı. Lütfen eşleştirme yapın.")
    else:
        df[termin_col] = pd.to_datetime(df[termin_col], errors='coerce')
        termin_tarihleri = df[termin_col].dropna().dt.date.unique()
        termin_tarihleri = sorted(termin_tarihleri)
        if len(termin_tarihleri) == 0:
            st.warning("Hiç geçerli 'Termin Süresinin Bittiği Tarih' bulunamadı.")
        else:
            selected_date = st.selectbox("Termin Süresinin Bittiği Tarih seçin", termin_tarihleri, index=0)
            termin_tarihleri_gun = df[termin_col].dt.date
            filtered = df[termin_tarihleri_gun == selected_date]
            # Kargoya Teslim Tarihi boş olanları filtreleme seçeneği
            kargoya_col = next((c for c in df.columns if c.replace(" ","") == "KargoyaTeslimTarihi"), None)
            only_missing_kargoya = False
            if kargoya_col:
                only_missing_kargoya = st.checkbox("Sadece 'Kargoya Teslim Tarihi' boş olanlar", value=False)
                if only_missing_kargoya:
                    filtered = filtered[filtered[kargoya_col].isna()]
            toplam_adet = filtered['Adet'].sum() if 'Adet' in filtered.columns else len(filtered)
            st.write(f"Seçilen tarihte termin süresi biten sipariş adedi: {toplam_adet}")
            st.dataframe(filtered)
            import io
            output = io.BytesIO()
            filtered.to_excel(output, index=False)
            output.seek(0)
            st.download_button(
                label="Filtrelenen veriyi Excel olarak indir",
                data=output,
                file_name=f"termin_suresi_bitenler_{selected_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
