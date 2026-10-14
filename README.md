# Gambar Jadi Video Natural

Aplikasi Streamlit untuk mengubah gambar menjadi klip video dengan model image-to-video Wan 2.2 yang di-host di Hugging Face Spaces.

## Berkas
- `app.py` — aplikasi utama
- `requirements.txt` — daftar pustaka Python

## Menjalankan
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy ke Streamlit Community Cloud
1. Buat repository GitHub baru.
2. Unggah `app.py` dan `requirements.txt` ke halaman utama repository.
3. Buka Streamlit Community Cloud dan pilih **New app**.
4. Pilih repository, lalu pilih `app.py` sebagai Main file path.
5. Deploy.

## Catatan
- Model video berjalan pada Space publik Hugging Face `zerogpu-aoti/wan2-2-fp8da-aoti-faster`.
- Layanan publik dapat mengalami antrean, perubahan API, atau batas kuota. Tidak ada jaminan penggunaan gratis tanpa batas.
- Token Hugging Face bersifat opsional di aplikasi; jika digunakan, buat token dengan izin Read dan jangan bagikan kepada orang lain.
