import streamlit as st
import pandas as pd
import altair as alt
import os
from streamlit_option_menu import option_menu
import datetime
from sklearn.linear_model import LinearRegression
import numpy as np


class Gider:
    def __init__(self, tarih, aciklama, miktar, kategori="Genel"):
        self.tarih = tarih
        self.aciklama = aciklama
        self.miktar = miktar
        self.kategori = kategori

class GiderTakip:
    def __init__(self, csv_dosya="giderler.csv"):
        self.csv_dosya = csv_dosya
        self.giderler = self.csvden_oku()

    def csvden_oku(self):
        if os.path.exists(self.csv_dosya):
            df = pd.read_csv(self.csv_dosya, encoding='utf-8-sig')
            gider_listesi = []
            for _, satir in df.iterrows():
                gider_listesi.append(Gider(
                    satir["Tarih"], satir["Açıklama"], satir["Miktar"], satir.get("Kategori", "Genel")
                ))
            return gider_listesi
        else:
            return []

    def csvye_kaydet(self):
        data = {
            "Tarih": [g.tarih for g in self.giderler],
            "Açıklama": [g.aciklama for g in self.giderler],
            "Miktar": [g.miktar for g in self.giderler],
            "Kategori": [g.kategori for g in self.giderler]
        }
        df = pd.DataFrame(data)
        df.to_csv("giderler.csv", index=False, encoding='utf-8-sig')

    def gider_ekle(self, gider):
        self.giderler.append(gider)
        self.csvye_kaydet()

    def gider_sil(self, index):
        if 0 <= index < len(self.giderler):
            del self.giderler[index]
            self.csvye_kaydet()
            st.success("Gider başarıyla silindi.")
        else:
            st.error("Geçersiz indeks.")

    def gider_guncelle(self, index, yeni_tarih, yeni_aciklama, yeni_miktar, yeni_kategori):
        if 0 <= index < len(self.giderler):
            self.giderler[index].tarih = yeni_tarih
            self.giderler[index].aciklama = yeni_aciklama
            self.giderler[index].miktar = yeni_miktar
            self.giderler[index].kategori = yeni_kategori
            self.csvye_kaydet()
            st.success("Gider başarıyla güncellendi.")
        else:
            st.error("Geçersiz gider seçimi.")

    def giderleri_goster(self):
        if not self.giderler:
            st.info("Gider bulunamadı.")
        else:
            data = {
                "Tarih": [g.tarih for g in self.giderler],
                "Kategori": [g.kategori for g in self.giderler],
                "Miktar": [g.miktar for g in self.giderler],
                "Açıklama": [g.aciklama for g in self.giderler]
            }
            df = pd.DataFrame(data)

            df["Tarih"] = pd.to_datetime(df["Tarih"], format="%d-%m-%Y", errors="coerce")
            df = df.sort_values("Tarih")

            df["Tarih"] = df["Tarih"].dt.strftime("%d %B %Y")

            df = df[["Tarih", "Kategori", "Miktar", "Açıklama"]]

            st.dataframe(df, hide_index=True)


    def toplam_gider(self):
        if not self.giderler:
            st.info("Gider bulunamadı.")
            return

        toplam = sum(g.miktar for g in self.giderler)
        st.write(f"**Toplam Gider: {toplam:.2f} TL**")

        
        data = {}
        for g in self.giderler:
            data[g.kategori] = data.get(g.kategori, 0) + g.miktar

        df = pd.DataFrame({
            "Kategori": list(data.keys()),
            "Miktar": list(data.values())
        })

        df["KategoriEtiket"] = df.apply(lambda row: f"{row['Kategori']} ({row['Miktar']:.2f} TL)", axis=1)

        chart = alt.Chart(df).mark_arc().encode(
            theta=alt.Theta(field="Miktar", type="quantitative"),
            color=alt.Color(field="KategoriEtiket", type="nominal", legend=alt.Legend(title="Kategori (Toplam)")),
            tooltip=["Kategori", alt.Tooltip("Miktar", format=".2f")]
        ).properties(
            title="Kategori Bazında Giderlerin Pasta Grafiği"
        )

        st.altair_chart(chart, use_container_width=True)



    def kategori_giderleri_goster(self):
        if not self.giderler:
            st.info("Gösterilecek gider bulunamadı.")
            return

        data = {
            "Kategori": [g.kategori for g in self.giderler],
            "Miktar": [g.miktar for g in self.giderler]
        }
        df = pd.DataFrame(data)
        kategori_toplam = df.groupby("Kategori").sum().reset_index()

        chart = alt.Chart(kategori_toplam).mark_bar().encode(
            x=alt.X("Kategori", sort='-y', title="Kategori"),
            y=alt.Y('Miktar', title="Toplam Gider (TL)"),
            tooltip=['Kategori', 'Miktar']
        ).properties(
            title="Kategori Bazlı Toplam Giderler"
        )

        st.altair_chart(chart, use_container_width=True)
        
        kategori_aylik_isiharitasi(self.giderler)

    def aylik_giderler_df(self):
        if not self.giderler:
            return pd.DataFrame()

        data = {
            "Tarih": [g.tarih for g in self.giderler],
            "Miktar": [g.miktar for g in self.giderler]
        }
        df = pd.DataFrame(data)
        df["Tarih"] = pd.to_datetime(df["Tarih"], format="%d-%m-%Y", errors="coerce")
        df = df.dropna(subset=["Tarih"])
        df["Ay"] = df["Tarih"].dt.to_period("M")
        aylik = df.groupby("Ay")["Miktar"].sum().reset_index()
        aylik["Ay"] = aylik["Ay"].dt.to_timestamp()
        return aylik


    def gelecek_aylar_tahmin(self, ay_sayisi=6):
        aylik = self.aylik_giderler_df()
        if aylik.empty or len(aylik) < 3:
            return None, "Yeterli veri yok (en az 3 ay olmalı)."

        baslangic = aylik["Ay"].min()
        aylik["Ay_num"] = (aylik["Ay"] - baslangic).dt.days

        X = aylik[["Ay_num"]]
        y = aylik["Miktar"]

        model = LinearRegression()
        model.fit(X, y)

        son_tarih = aylik["Ay"].max()
        gelecek_aylar = [son_tarih + pd.DateOffset(months=i) for i in range(1, ay_sayisi+1)]
        gelecek_aylar_num = np.array([(x - baslangic).days for x in gelecek_aylar]).reshape(-1, 1)
        tahminler = model.predict(gelecek_aylar_num)

        tahmin_df = pd.DataFrame({
            "Ay": gelecek_aylar,
            "Tahmin (TL)": tahminler
        })

        return tahmin_df, None


def kategori_aylik_isiharitasi(giderler):
    if not giderler:
        st.info("Gösterilecek gider bulunamadı.")
        return
    
    data = {
        "Tarih": [g.tarih for g in giderler],
        "Kategori": [g.kategori for g in giderler],
        "Miktar": [g.miktar for g in giderler]
    }
    df = pd.DataFrame(data)
    
    df["Tarih"] = pd.to_datetime(df["Tarih"], format="%d-%m-%Y", errors="coerce")
    df = df.dropna(subset=["Tarih"])
    
    df["Ay"] = df["Tarih"].dt.strftime("%Y-%m")
    
    pivot_df = df.groupby(["Kategori", "Ay"])["Miktar"].sum().reset_index()
    
    ay_toplam = pivot_df.groupby("Ay")["Miktar"].sum().reset_index().rename(columns={"Miktar": "AyToplam"})
    
    pivot_df = pivot_df.merge(ay_toplam, on="Ay")
    
    pivot_df["Yuzde"] = (pivot_df["Miktar"] / pivot_df["AyToplam"]) * 100
    
    heatmap = alt.Chart(pivot_df).mark_rect().encode(
        x=alt.X('Ay:O', title='Ay', sort=None),
        y=alt.Y('Kategori:O', title='Kategori'),
        color=alt.Color('Miktar:Q', title='Toplam Gider (TL)', scale=alt.Scale(scheme='reds')),
        tooltip=[
            alt.Tooltip('Kategori:N'),
            alt.Tooltip('Ay:O'),
            alt.Tooltip('Miktar:Q', format=".2f"),
            alt.Tooltip('Yuzde:Q', format=".1f")
        ]
    )
    
    text = alt.Chart(pivot_df).mark_text(color='black', fontWeight='bold').encode(
        x=alt.X('Ay:O'),
        y=alt.Y('Kategori:O'),
        text=alt.Text('Yuzde:Q', format=".1f")
    )
    
    chart = (heatmap + text).properties(
        width=700,
        height=400,
        title="Kategori Bazında Aylık Giderlerin Isı Haritası (%)"
    )
    
    st.altair_chart(chart, use_container_width=True)



def main():
    
    st.title("Gider Takip Uygulaması")

    takip = GiderTakip()

    with st.sidebar:
        secim = option_menu(
            menu_title=None,
            options=["Gider Ekle", "Giderleri Göster", "Gider Sil", "Gider Düzenle", "Kategori Bazlı İstatistikler", "Kümülatif Harcama İstatistikleri", "Gelecek Aylar İçin Tahmin"],
            icons=["plus", "list", "trash", "pencil", "currency-dollar", "bar-chart", "calendar-check"],
            menu_icon="cast",
            default_index=0,
            orientation="vertical"
        )



    kategoriler = [
        "Otomotiv", "Faturalar", "Kıyafet", "Eğlence", "Gıda", "Yakıt",
        "Genel", "Hediyeler", "Sağlık", "Tatil", "Ev", "Çocuklar",
        "Alışveriş", "Spor"
    ]

    if secim == "Gider Ekle":
        with st.form("gider_ekle_formu", clear_on_submit=True):
            tarih = st.date_input("Tarih")
            kategori = st.selectbox("Kategori", kategoriler)
            miktar = st.text_input("Miktar (TL)")
            aciklama = st.text_input("Açıklama")

            submit = st.form_submit_button("Ekle")
            if submit:
                try:
                    miktar_float = float(miktar)
                    yeni_gider = Gider(tarih.strftime("%d-%m-%Y"), aciklama, miktar_float, kategori)
                    takip.gider_ekle(yeni_gider)
                    st.success("Gider başarıyla eklendi.")
                except ValueError:
                    st.error("Miktar geçerli bir sayı olmalı.")


    elif secim == "Giderleri Göster":
        takip.giderleri_goster()

    elif secim == "Gider Sil":
        if not takip.giderler:
            st.info("Silinecek gider bulunamadı.")
        else:
            secenekler = [f"{g.tarih} - {g.kategori} - {g.miktar:.2f} TL - {g.aciklama}" for g in takip.giderler]
            secilen = st.selectbox("Silmek istediğiniz gideri seçin:", secenekler)
            if st.button("Sil"):
                index = secenekler.index(secilen)
                takip.gider_sil(index)
    elif secim == "Gider Düzenle":
        if not takip.giderler:
            st.info("Düzenlenecek gider bulunamadı.")
        else:
            secenekler = [f"{g.tarih} - {g.kategori} - {g.miktar:.2f} TL - {g.aciklama}" for g in takip.giderler]
            secilen_index = st.selectbox("Düzenlemek istediğiniz gideri seçin:", range(len(secenekler)), format_func=lambda x: secenekler[x])

            gider = takip.giderler[secilen_index]

            with st.form("gider_duzenle_formu"):
                tarih = st.date_input("Tarih", value=pd.to_datetime(gider.tarih, format="%d-%m-%Y"))
                kategori = st.selectbox("Kategori", kategoriler, index=kategoriler.index(gider.kategori) if gider.kategori in kategoriler else 0)
                miktar = st.text_input("Miktar (TL)", value=str(gider.miktar))
                aciklama = st.text_input("Açıklama", value=gider.aciklama)

                submit = st.form_submit_button("Güncelle")
                if submit:
                    try:
                        miktar_float = float(miktar)
                        takip.gider_guncelle(
                            secilen_index,
                            tarih.strftime("%d-%m-%Y"),
                            aciklama,
                            miktar_float,
                            kategori
                        )
                    except ValueError:
                        st.error("Miktar geçerli bir sayı olmalı.")


    elif secim == "Kategori Bazlı İstatistikler":
        takip.toplam_gider()
        takip.kategori_giderleri_goster()

    elif secim == "Kümülatif Harcama İstatistikleri":
        st.header("Kümülatif Harcama İstatistikleri")
        aylik = takip.aylik_giderler_df()
        
        if aylik.empty:
            st.info("Gösterilecek veri yok.")
        else:
            aylik = aylik.sort_values("Ay")
            aylik["Kümülatif"] = aylik["Miktar"].cumsum()

            toplam_harcama = aylik["Miktar"].sum()
            st.subheader(f"Toplam Harcama: {toplam_harcama:.2f} TL")

            st.markdown("#### Aylık Harcamalar")
            aylik_tablo = aylik.copy()
            aylik_tablo["Ay"] = aylik_tablo["Ay"].dt.strftime("%B %Y")
            st.dataframe(aylik_tablo[["Ay", "Miktar"]].rename(columns={"Miktar": "Aylık Harcama (TL)"}), use_container_width=True, hide_index = True)

            line = alt.Chart(aylik).mark_line(point=True).encode(
                x=alt.X('Ay:T', title='Ay', axis=alt.Axis(format='%b %Y')),
                y=alt.Y('Kümülatif:Q', title='Kümülatif Gider (TL)'),
                tooltip=[
                    alt.Tooltip('Ay:T', title='Ay', format='%B %Y'),
                    alt.Tooltip('Miktar:Q', title='Aylık Harcama (TL)', format='.2f'),
                    alt.Tooltip('Kümülatif:Q', title='Kümülatif Harcama (TL)', format='.2f')
                ]
            ).properties(title="Kümülatif Giderlerin Zamanla Değişimi")

            st.altair_chart(line, use_container_width=True)


    elif secim == "Gelecek Aylar İçin Tahmin":
        tahmin_df, hata = takip.gelecek_aylar_tahmin()
        if hata:
            st.info(hata)
        else:
            st.subheader("Gelecek Aylara Ait Gider Tahminleri (TL)")
            tahmin_df["Ay"] = tahmin_df["Ay"].dt.strftime("%B %Y")
            st.dataframe(tahmin_df, hide_index = True)

if __name__ == "__main__":
    main()
