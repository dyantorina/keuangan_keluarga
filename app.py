import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import json
from google import genai

st.set_page_config(
    page_title="Keuangan Rina & Yudi", 
    page_icon="💰", 
    layout="wide"
)

# Sistem Autentikasi Pengguna
def cek_login():
    if "sudah_login" not in st.session_state:
        st.session_state.sudah_login = False
        st.session_state.pengguna_aktif = ""

    # Daftar akun terverifikasi (diambil dari Secrets jika ada, atau fallback lokal)
    if "pengguna" in st.secrets:
        daftar_akun = dict(st.secrets["pengguna"])
    else:
        # Kredensial cadangan untuk uji coba di laptop
        daftar_akun = {
            "rina": "rina123",
            "yudi": "yudi123"
        }

    if not st.session_state.sudah_login:
        st.markdown("<h2 style='text-align: center;'>🔒 Keuangan Rina & Yudi</h2>", unsafe_allow_html=True)
        st.caption("<p style='text-align: center;'>Silakan masuk untuk mengakses buku kas keluarga</p>", unsafe_allow_html=True)
        
        _, col_login, _ = st.columns([1, 1.2, 1])
        with col_login:
            with st.form("form_login"):
                username_input = st.text_input("Username").strip().lower()
                password_input = st.text_input("Password", type="password")
                tombol_masuk = st.form_submit_button("Masuk", use_container_width=True)

                if tombol_masuk:
                    if username_input in daftar_akun and daftar_akun[username_input] == password_input:
                        st.session_state.sudah_login = True
                        st.session_state.pengguna_aktif = username_input.capitalize()
                        st.rerun()
                    else:
                        st.error("Username atau Password tidak sesuai!")
        st.stop()

# Jalankan pengecekan login di awal
cek_login()

# Sidebar: Info Pengguna & Tombol Keluar
with st.sidebar:
    st.write(f"👤 Masuk sebagai: **{st.session_state.pengguna_aktif}**")
    if st.button("Keluar (Logout)", use_container_width=True):
        st.session_state.sudah_login = False
        st.session_state.pengguna_aktif = ""
        st.rerun()

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def buka_sheet():
    if "gcp_service_account" in st.secrets:
        creds_info = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, SCOPE)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("kunci.json", SCOPE)
        
    client = gspread.authorize(creds)
    spreadsheet = client.open("keuangan_keluarga")
    return spreadsheet.get_worksheet(0)

sheet = buka_sheet()

def muat_data():
    try:
        records = sheet.get_all_records()
        kolom_wajib = ["Nomor", "Tanggal", "Uraian", "Pemasukan", "Pengeluaran", "Saldo Akhir"]
        if not records:
            return pd.DataFrame(columns=kolom_wajib)
        
        df = pd.DataFrame(records)
        df["Nomor"] = pd.to_numeric(df["Nomor"], errors="coerce").fillna(0).astype(int)
        df["Tanggal_DT"] = pd.to_datetime(df["Tanggal"], errors="coerce")
        df["Pemasukan"] = pd.to_numeric(df["Pemasukan"], errors="coerce").fillna(0)
        df["Pengeluaran"] = pd.to_numeric(df["Pengeluaran"], errors="coerce").fillna(0)
        df["Saldo Akhir"] = pd.to_numeric(df["Saldo Akhir"], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=["Nomor", "Tanggal", "Uraian", "Pemasukan", "Pengeluaran", "Saldo Akhir"])

def perbarui_ulang_spreadsheet(df_baru):
    df_baru = df_baru.reset_index(drop=True)
    df_baru["Nomor"] = df_baru.index + 1
    
    saldo_kumulatif = 0.0
    daftar_saldo = []
    for _, baris in df_baru.iterrows():
        saldo_kumulatif += baris["Pemasukan"] - baris["Pengeluaran"]
        daftar_saldo.append(saldo_kumulatif)
    df_baru["Saldo Akhir"] = daftar_saldo

    kolom_header = ["Nomor", "Tanggal", "Uraian", "Pemasukan", "Pengeluaran", "Saldo Akhir"]
    data_tulis = [kolom_header] + df_baru[kolom_header].values.tolist()
    
    sheet.clear()
    sheet.update(range_name="A1", values=data_tulis)

st.title("💰 Buku Kas Keuangan Rina & Yudi")
st.caption("Tersimpan langsung di Google Drive Spreadsheet")

# Formulir Input Transaksi
with st.expander("➕ Tambah Transaksi Baru", expanded=False):
    with st.form("form_kas", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tgl_input = st.date_input("Tanggal", value=date.today())
            jenis = st.selectbox("Jenis Transaksi", ["Pemasukan", "Pengeluaran"])
        with col2:
            keterangan = st.text_input("Uraian / Keterangan", placeholder="Contoh: Belanja bulanan, Gaji, dll.")
            nominal = st.number_input("Nominal (Rp)", min_value=0.0, step=10000.0, format="%.2f")

        simpan = st.form_submit_button("Simpan Transaksi")

        if simpan:
            if not keterangan.strip():
                st.error("Uraian transaksi wajib diisi!")
            elif nominal <= 0:
                st.error("Nominal transaksi harus lebih dari 0!")
            else:
                with st.spinner("Menyimpan ke Google Drive..."):
                    df_sekarang = muat_data()
                    no_urut = len(df_sekarang) + 1
                    masuk = nominal if jenis == "Pemasukan" else 0.0
                    keluar = nominal if jenis == "Pengeluaran" else 0.0
                    
                    saldo_sebelumnya = df_sekarang["Saldo Akhir"].iloc[-1] if not df_sekarang.empty else 0.0
                    saldo_baru = saldo_sebelumnya + masuk - keluar
                    
                    baris_baru = [int(no_urut), str(tgl_input), keterangan, masuk, keluar, saldo_baru]
                    sheet.append_row(baris_baru)
                    st.success("Transaksi berhasil dicatat!")
                    st.rerun()

# Formulir Hapus Transaksi
df_kas = muat_data()

if not df_kas.empty:
    with st.expander("🗑️ Hapus Transaksi (Koreksi Kesalahan Input)", expanded=False):
        st.write("Pilih transaksi yang ingin dihapus. Saldo dan nomor urut transaksi setelahnya akan dihitung ulang secara otomatis.")
        
        pilihan_transaksi = {
            f"No. {row['Nomor']} | {row['Tanggal']} | {row['Uraian']} (Rp {row['Pemasukan'] if row['Pemasukan'] > 0 else row['Pengeluaran']:,.2f})": row['Nomor']
            for _, row in df_kas.iterrows()
        }
        
        pilihan_teks = st.selectbox("Pilih Transaksi:", list(pilihan_transaksi.keys()))
        nomor_target = pilihan_transaksi[pilihan_teks]

        col_h1, col_h2 = st.columns([1, 4])
        with col_h1:
            tombol_hapus = st.button("Hapus Transaksi Ini", type="primary")

        if tombol_hapus:
            with st.spinner("Menghapus data dan menghitung ulang saldo..."):
                df_sisa = df_kas[df_kas["Nomor"] != nomor_target].copy()
                perbarui_ulang_spreadsheet(df_sisa)
                st.success(f"Transaksi No. {nomor_target} berhasil dihapus!")
                st.rerun()

# Filter dan Visualisasi
if not df_kas.empty and "Tanggal_DT" in df_kas.columns and df_kas["Tanggal_DT"].notnull().any():
    st.markdown("---")
    st.subheader("🔍 Filter Data & Cetak Laporan")

    mode_filter = st.radio("Pilih Mode Tampilan:", ["Bulanan", "Rentang Tanggal (Maks 30 Hari)"], horizontal=True)

    df_terfilter = df_kas.copy()

    if mode_filter == "Bulanan":
        df_kas["Bulan_Tahun"] = df_kas["Tanggal_DT"].dt.strftime("%Y-%m")
        daftar_bulan = sorted(df_kas["Bulan_Tahun"].dropna().unique(), reverse=True)
        pilihan_bulan = st.selectbox("Pilih Periode Bulan:", daftar_bulan)
        df_terfilter = df_kas[df_kas["Bulan_Tahun"] == pilihan_bulan]
        judul_periode = f"Periode Bulan: {pilihan_bulan}"
    else:
        c_tgl1, c_tgl2 = st.columns(2)
        hari_ini = date.today()
        with c_tgl1:
            tgl_mulai = st.date_input("Tanggal Mulai", value=hari_ini - timedelta(days=7))
        with c_tgl2:
            tgl_akhir = st.date_input("Tanggal Akhir", value=hari_ini)

        selisih_hari = (tgl_akhir - tgl_mulai).days

        if selisih_hari < 0:
            st.error("Tanggal akhir tidak boleh lebih awal dari tanggal mulai!")
            df_terfilter = pd.DataFrame()
            judul_periode = ""
        elif selisih_hari > 30:
            st.warning(f"Rentang dipilih adalah {selisih_hari} hari. Maksimal batas laporan adalah 30 hari!")
            df_terfilter = pd.DataFrame()
            judul_periode = ""
        else:
            df_terfilter = df_kas[
                (df_kas["Tanggal_DT"].dt.date >= tgl_mulai) & 
                (df_kas["Tanggal_DT"].dt.date <= tgl_akhir)
            ]
            judul_periode = f"Rentang: {tgl_mulai} s/d {tgl_akhir} ({selisih_hari + 1} Hari)"

    if not df_terfilter.empty:
        total_masuk = df_terfilter["Pemasukan"].sum()
        total_keluar = df_terfilter["Pengeluaran"].sum()
        saldo_akhir_periode = df_terfilter["Saldo Akhir"].iloc[-1]

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Pemasukan", f"Rp {total_masuk:,.2f}")
        m2.metric("Total Pengeluaran", f"Rp {total_keluar:,.2f}")
        m3.metric("Saldo Akhir Periode", f"Rp {saldo_akhir_periode:,.2f}")

        # Visualisasi
        st.markdown("---")
        st.subheader("📊 Analisis Visual Keuangan")

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.markdown("**Komposisi Kas (Pemasukan vs Pengeluaran)**")
            if total_masuk > 0 or total_keluar > 0:
                df_pie = pd.DataFrame({
                    "Kategori": ["Pemasukan", "Pengeluaran"],
                    "Nominal": [total_masuk, total_keluar]
                })
                fig_pie = px.pie(
                    df_pie,
                    names="Kategori",
                    values="Nominal",
                    hole=0.45,
                    color="Kategori",
                    color_discrete_map={
                        "Pemasukan": "#00E676",
                        "Pengeluaran": "#FF3366"
                    }
                )
                fig_pie.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                    marker=dict(line=dict(color="#FFFFFF", width=2))
                )
                fig_pie.update_layout(showlegend=True, margin=dict(t=20, b=20, l=10, r=10))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Belum ada nominal transaksi untuk divisualisasikan.")

        with col_g2:
            st.markdown("**Tren Transaksi Harian**")
            df_grafik = df_terfilter.groupby("Tanggal")[["Pemasukan", "Pengeluaran"]].sum()
            st.bar_chart(df_grafik)

        # Tabel Riwayat
        st.markdown("---")
        st.subheader("📋 Rincian Transaksi")
        
        kolom_tampil = ["Nomor", "Tanggal", "Uraian", "Pemasukan", "Pengeluaran", "Saldo Akhir"]
        df_format = df_terfilter[kolom_tampil].copy()
        
        # Format Cetak HTML
        html_tabel = df_format.to_html(index=False, classes='tabel-kas', border=1)
        html_print = f"""
        <html>
        <head>
            <title>Laporan Keuangan Rina & Yudi</title>
            <style>
                body {{ font-family: sans-serif; padding: 20px; }}
                h2, h4 {{ margin: 5px 0; text-align: center; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #333; padding: 8px; text-align: left; font-size: 12px; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h2>LAPORAN KAS KELUARGA RINA & YUDI</h2>
            <h4>{judul_periode}</h4>
            <p><strong>Total Pemasukan:</strong> Rp {total_masuk:,.2f} | <strong>Total Pengeluaran:</strong> Rp {total_keluar:,.2f} | <strong>Saldo:</strong> Rp {saldo_akhir_periode:,.2f}</p>
            {html_tabel}
            <script>window.print();</script>
        </body>
        </html>
        """
        
        st.download_button(
            label="🖨️ Siapkan Laporan Cetak",
            data=html_print,
            file_name=f"Laporan_Kas_{date.today()}.html",
            mime="text/html"
        )

        df_format["Pemasukan"] = df_format["Pemasukan"].apply(lambda x: f"Rp {x:,.2f}")
        df_format["Pengeluaran"] = df_format["Pengeluaran"].apply(lambda x: f"Rp {x:,.2f}")
        df_format["Saldo Akhir"] = df_format["Saldo Akhir"].apply(lambda x: f"Rp {x:,.2f}")
        st.dataframe(df_format, use_container_width=True, hide_index=True)
        # Tombol Analisis Otomatis AI
        st.markdown("---")
        st.subheader("💡 Analisis Penghematan Otomatis (AI)")
        st.caption("Klik tombol di bawah untuk meminta saran cerdas pemangkasan pos boros berdasarkan riwayat 30 hari ini.")

        if st.button("🤖 Jalankan Analisis Penghematan AI", type="primary"):
            if "GEMINI_API_KEY" not in st.secrets:
                st.error("Kunci API Gemini belum dimasukkan di menu Secrets!")
            else:
                with st.spinner("Sedang membaca data kas dan menyusun strategi penghematan..."):
                    try:
                        # Siapkan ringkasan data transaksi
                        ringkasan_transaksi = df_format.to_string(index=False)
                        
                        prompt_analisis = f"""
                        Kamu adalah perencana keuangan keluarga profesional untuk keluarga Rina & Yudi.
                        Berikut adalah data transaksi kas 30 hari terakhir:
                        
                        {ringkasan_transaksi}
                        
                        Total Pemasukan: Rp {total_masuk:,.2f}
                        Total Pengeluaran: Rp {total_keluar:,.2f}
                        Saldo Akhir: Rp {saldo_akhir_periode:,.2f}
                        
                        Tolong berikan analisis singkat, ramah, dan solutif dengan format:
                        1. Ringkasan Kondisi Kas (Kesehatan cashflow bulan ini)
                        2. Identifikasi Kebocoran / Pengeluaran Terbesar (Apa saja pos yang paling menyedot saldo)
                        3. Rekomendasi Penghematan Konkret (Langkah praktis memangkas biaya tanpa mengorbankan kebutuhan pokok)
                        4. Target Alokasi Tabungan/Dana Darurat untuk bulan berikutnya.
                        """
                        
                        client_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        response = client_ai.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=prompt_analisis
                        )
                        
                        st.success("Analisis selesai disusun!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Terjadi kendala saat menghubungi AI: {e}")

    else:
        st.info("Tidak ada transaksi pada periode yang dipilih.")
else:
    st.info("Belum ada data transaksi tersimpan di Google Sheet. Tambahkan transaksi pertama di atas.")