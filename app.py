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
    page_icon="💳", 
    layout="wide"
)

# Custom Styling (CSS)
st.markdown("""
<style>
    /* Latar tombol dan aksen */
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    /* Kartu metrik kustom */
    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 14px;
        padding: 16px 20px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    }
    .metric-title {
        font-size: 0.85rem;
        color: #9aa0a6;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-value-masuk {
        font-size: 1.45rem;
        font-weight: 700;
        color: #00E676;
    }
    .metric-value-keluar {
        font-size: 1.45rem;
        font-weight: 700;
        color: #FF5252;
    }
    .metric-value-saldo {
        font-size: 1.55rem;
        font-weight: 800;
        color: #448AFF;
    }
    /* Badge pengguna di header */
    .user-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        background-color: rgba(68, 138, 255, 0.15);
        color: #82B1FF;
        font-size: 0.85rem;
        font-weight: 600;
        border: 1px solid rgba(68, 138, 255, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# Sistem Login
def cek_login():
    if "sudah_login" not in st.session_state:
        st.session_state.sudah_login = False
        st.session_state.pengguna_aktif = ""

    if "pengguna" in st.secrets:
        daftar_akun = dict(st.secrets["pengguna"])
    else:
        daftar_akun = {"rina": "rina123", "yudi": "yudi123"}

    if not st.session_state.sudah_login:
        st.markdown("<br><h1 style='text-align: center;'>🔒 Keuangan Rina & Yudi</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Silakan masuk dengan akun terdaftar</p>", unsafe_allow_html=True)
        
        _, col_login, _ = st.columns([1, 1.2, 1])
        with col_login:
            with st.form("form_login"):
                username_input = st.text_input("Username").strip().lower()
                password_input = st.text_input("Password", type="password")
                tombol_masuk = st.form_submit_button("Masuk ke Buku Kas", use_container_width=True)

                if tombol_masuk:
                    if username_input in daftar_akun and daftar_akun[username_input] == password_input:
                        st.session_state.sudah_login = True
                        st.session_state.pengguna_aktif = username_input.capitalize()
                        st.rerun()
                    else:
                        st.error("Username atau Password tidak sesuai!")
        st.stop()

cek_login()

# Sidebar
with st.sidebar:
    st.markdown("### 👤 Akun Masuk")
    st.markdown(f"<span class='user-badge'>{st.session_state.pengguna_aktif}</span>", unsafe_allow_html=True)
    st.markdown("---")
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

# Header Utama
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.title("💳 Dasbor Kas Rina & Yudi")
    st.caption("Data tersinkronisasi otomatis dengan Google Spreadsheet")
with col_head2:
    st.markdown("<div style='text-align: right; padding-top: 15px;'>", unsafe_allow_html=True)
    st.markdown(f"Status: **Aktif ({st.session_state.pengguna_aktif})**")
    st.markdown("</div>", unsafe_allow_html=True)

# Bagian Input Transaksi
with st.expander("➕ Tambah Transaksi Kas", expanded=False):
    with st.form("form_kas", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tgl_input = st.date_input("Tanggal Transaksi", value=date.today())
            jenis = st.selectbox("Arus Kas", ["Pemasukan", "Pengeluaran"])
        with col2:
            keterangan = st.text_input("Keterangan / Pos Belanja", placeholder="Contoh: Belanja dapur, internet, gaji")
            nominal = st.number_input("Nominal (Rp)", min_value=0.0, step=10000.0, format="%.2f")

        simpan = st.form_submit_button("Simpan Data ke Kas", use_container_width=True)

        if simpan:
            if not keterangan.strip():
                st.error("Uraian transaksi wajib diisi!")
            elif nominal <= 0:
                st.error("Nominal transaksi harus lebih dari 0!")
            else:
                with st.spinner("Mencatat data ke cloud..."):
                    df_sekarang = muat_data()
                    no_urut = len(df_sekarang) + 1
                    masuk = nominal if jenis == "Pemasukan" else 0.0
                    keluar = nominal if jenis == "Pengeluaran" else 0.0
                    
                    saldo_sebelumnya = df_sekarang["Saldo Akhir"].iloc[-1] if not df_sekarang.empty else 0.0
                    saldo_baru = saldo_sebelumnya + masuk - keluar
                    
                    baris_baru = [int(no_urut), str(tgl_input), keterangan, masuk, keluar, saldo_baru]
                    sheet.append_row(baris_baru)
                    st.success("Transaksi tersimpan!")
                    st.rerun()

df_kas = muat_data()

# Hapus Transaksi
if not df_kas.empty:
    with st.expander("🗑️ Koreksi / Hapus Transaksi", expanded=False):
        pilihan_transaksi = {
            f"No. {row['Nomor']} | {row['Tanggal']} | {row['Uraian']} (Rp {row['Pemasukan'] if row['Pemasukan'] > 0 else row['Pengeluaran']:,.2f})": row['Nomor']
            for _, row in df_kas.iterrows()
        }
        pilihan_teks = st.selectbox("Pilih item yang ingin dihapus:", list(pilihan_transaksi.keys()))
        nomor_target = pilihan_transaksi[pilihan_teks]

        if st.button("Hapus Item Terpilih", type="primary"):
            with st.spinner("Memperbarui saldo..."):
                df_sisa = df_kas[df_kas["Nomor"] != nomor_target].copy()
                perbarui_ulang_spreadsheet(df_sisa)
                st.success(f"Item No. {nomor_target} berhasil dihapus!")
                st.rerun()

# Filter & Ringkasan Metrik Kartu Modern
if not df_kas.empty and "Tanggal_DT" in df_kas.columns and df_kas["Tanggal_DT"].notnull().any():
    st.markdown("---")
    
    col_filter_header, col_mode = st.columns([1, 2])
    with col_filter_header:
        st.subheader("📊 Laporan & Filter")
    with col_mode:
        mode_filter = st.radio("Pilih Filter Tampilan:", ["Bulanan", "Rentang Tanggal (Maks 30 Hari)"], horizontal=True)

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
            tgl_mulai = st.date_input("Mulai", value=hari_ini - timedelta(days=7))
        with c_tgl2:
            tgl_akhir = st.date_input("Sampai", value=hari_ini)

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

        # Kartu Metrik Modern
        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Total Pemasukan</div>
                <div class='metric-value-masuk'>Rp {total_masuk:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with k2:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Total Pengeluaran</div>
                <div class='metric-value-keluar'>Rp {total_keluar:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with k3:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Saldo Periode Ini</div>
                <div class='metric-value-saldo'>Rp {saldo_akhir_periode:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Grafik Interaktif
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.markdown("**Komposisi Kas Masuk vs Keluar**")
            if total_masuk > 0 or total_keluar > 0:
                df_pie = pd.DataFrame({
                    "Kategori": ["Pemasukan", "Pengeluaran"],
                    "Nominal": [total_masuk, total_keluar]
                })
                fig_pie = px.pie(
                    df_pie,
                    names="Kategori",
                    values="Nominal",
                    hole=0.55,
                    color="Kategori",
                    color_discrete_map={
                        "Pemasukan": "#00E676",
                        "Pengeluaran": "#FF5252"
                    }
                )
                fig_pie.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                    marker=dict(line=dict(color="#1e1e1e", width=2))
                )
                fig_pie.update_layout(
                    showlegend=False, 
                    margin=dict(t=20, b=20, l=10, r=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Belum ada angka transaksi untuk divisualisasikan.")

        with col_g2:
            st.markdown("**Tren Transaksi Harian**")
            df_grafik = df_terfilter.groupby("Tanggal")[["Pemasukan", "Pengeluaran"]].sum()
            st.bar_chart(df_grafik, color=["#00E676", "#FF5252"])

        # Tabel Riwayat
        st.markdown("---")
        st.subheader("📋 Rincian Transaksi Kas")
        
        kolom_tampil = ["Nomor", "Tanggal", "Uraian", "Pemasukan", "Pengeluaran", "Saldo Akhir"]
        df_format = df_terfilter[kolom_tampil].copy()
        
        html_tabel = df_format.to_html(index=False, classes='tabel-kas', border=1)
        html_print = f"""
        <html>
        <head>
            <title>Laporan Kas Keuangan</title>
            <style>
                body {{ font-family: sans-serif; padding: 24px; }}
                h2, h4 {{ margin: 6px 0; text-align: center; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #444; padding: 10px; text-align: left; font-size: 13px; }}
                th {{ background-color: #f5f5f5; }}
            </style>
        </head>
        <body>
            <h2>LAPORAN KAS RINA & YUDI</h2>
            <h4>{judul_periode}</h4>
            <p><strong>Total Pemasukan:</strong> Rp {total_masuk:,.2f} | <strong>Total Pengeluaran:</strong> Rp {total_keluar:,.2f} | <strong>Saldo:</strong> Rp {saldo_akhir_periode:,.2f}</p>
            {html_tabel}
            <script>window.print();</script>
        </body>
        </html>
        """
        
        st.download_button(
            label="🖨️ Cetak / Unduh Laporan",
            data=html_print,
            file_name=f"Laporan_Kas_{date.today()}.html",
            mime="text/html"
        )

        df_format["Pemasukan"] = df_format["Pemasukan"].apply(lambda x: f"Rp {x:,.2f}")
        df_format["Pengeluaran"] = df_format["Pengeluaran"].apply(lambda x: f"Rp {x:,.2f}")
        df_format["Saldo Akhir"] = df_format["Saldo Akhir"].apply(lambda x: f"Rp {x:,.2f}")
        st.dataframe(df_format, use_container_width=True, hide_index=True)

        # Analisis Cerdas Gemini AI
        st.markdown("---")
        st.subheader("✨ Konsultan Kas Pintar (AI)")
        st.caption("Menganalisis pola transaksi kas periode ini dan memberi solusi penghematan konkret.")

        if st.button("🤖 Evaluasi Keuangan Sekarang", type="primary", use_container_width=True):
            if "GEMINI_API_KEY" not in st.secrets:
                st.error("Kunci API Gemini belum dipasang di Secrets!")
            else:
                with st.spinner("AI sedang membaca data kas dan menyusun strategi cerdas..."):
                    try:
                        ringkasan_transaksi = df_format.to_string(index=False)
                        
                        prompt_analisis = f"""
                        Kamu adalah penasihat keuangan pribadi keluarga Rina & Yudi yang cerdas, praktis, dan ramah.
                        Berikut data arus kas mereka:
                        
                        {ringkasan_transaksi}
                        
                        Total Pemasukan: Rp {total_masuk:,.2f}
                        Total Pengeluaran: Rp {total_keluar:,.2f}
                        Saldo Akhir: Rp {saldo_akhir_periode:,.2f}
                        
                        Berikan analisis ringkas dan terarah dengan poin berikut:
                        1. 🩺 Diagnosis Kesehatan Kas (Sehat / Pas-pasan / Kritis beserta alasannya)
                        2. 🚨 Pos Pengeluaran Paling Dominan & Kebocoran Halus
                        3. 💡 Saran Penghematan Konkret yang Bisa Langsung Dilakukan
                        4. 🎯 Rekomendasi Alokasi Tabungan/Investasi
                        """
                        
                        client_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        response = client_ai.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=prompt_analisis
                        )
                        
                        st.success("Evaluasi kas selesai!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Gagal memuat analisis: {e}")

    else:
        st.info("Tidak ada data transaksi pada rentang waktu yang dipilih.")
else:
    st.info("Data di Google Sheets masih kosong. Silakan catat transaksi perdana pada formulir di atas.")