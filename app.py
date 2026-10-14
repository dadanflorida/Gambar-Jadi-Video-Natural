import os
import tempfile
import streamlit as st
from gradio_client import Client, handle_file

st.set_page_config(page_title="Gambar Jadi Video Natural", page_icon="🎬", layout="centered")

st.title("🎬 Gambar Jadi Video Natural")
st.write("Ubah satu gambar menjadi klip video dengan gerakan yang dibuat AI—bukan sekadar efek zoom kamera.")
st.info("Mesin video memakai model Wan 2.2 di Hugging Face. Layanan gratis dapat memiliki antrean dan batas pemakaian harian.")

with st.expander("🔑 Token Hugging Face (opsional, disarankan)", expanded=False):
    st.write("Token gratis membantu layanan mengenali akun dan kuota Anda. Buat token dengan izin **Read** di akun Hugging Face, lalu tempel di bawah. Jangan bagikan token kepada siapa pun.")
    hf_token = st.text_input("Hugging Face token", type="password", help="Token hanya digunakan untuk menghubungkan permintaan ini.")

uploaded_image = st.file_uploader("1. Pilih gambar", type=["png", "jpg", "jpeg", "webp"])

motion_options = {
    "Gerakan natural": "The subject moves naturally with subtle realistic body motion, natural blinking and breathing, slight environmental movement, realistic physics, smooth continuous motion. Keep the same identity, face, clothes and background. No sudden scene changes.",
    "Orang berjalan": "The person begins walking naturally at a realistic pace, with believable steps, natural arm swing and body balance. Keep the same identity, face, clothes and background. Smooth continuous motion, realistic physics.",
    "Silat / bela diri": "The martial artist performs one smooth, realistic silat movement: shifts stance, steps forward, delivers one controlled punch followed by one clear kick, then returns to a balanced guard. Realistic body mechanics, stable anatomy, same face and clothing, no extra limbs.",
    "Angin dan suasana": "Subtle natural environmental motion: leaves and fabric move gently in the breeze, hair moves slightly, clouds drift slowly, realistic lighting and physics. Keep the main subject and composition consistent.",
    "Produk bergerak": "A smooth realistic product showcase. The camera remains mostly steady while the product rotates slightly or is revealed by subtle natural movement and changing reflections. Keep the product shape, labels, colors and details unchanged.",
    "Tulis gerakan sendiri": "CUSTOM",
}

motion_choice = st.selectbox("2. Pilih gerakan", list(motion_options.keys()))
if motion_choice == "Tulis gerakan sendiri":
    motion_prompt = st.text_area("Jelaskan gerakan yang diinginkan", placeholder="Contoh: Seorang pria mengangkat tangan, menoleh ke kiri, lalu tersenyum tipis.", height=110)
else:
    motion_prompt = motion_options[motion_choice]
    st.caption("Gerakan yang akan dipakai:")
    st.write(motion_prompt)

col1, col2 = st.columns(2)
with col1:
    duration = st.slider("3. Durasi video", min_value=2.0, max_value=5.0, value=3.5, step=0.5, help="Klip lebih panjang biasanya memerlukan waktu pemrosesan lebih lama.")
with col2:
    quality_steps = st.selectbox("Kecepatan / detail", options=[4, 6, 8], index=1, format_func=lambda x: {4: "Cepat", 6: "Seimbang", 8: "Lebih detail (lebih lama)"}[x])

negative_prompt = "static image, frozen motion, flicker, blurry, distorted face, deformed hands, extra fingers, extra limbs, changing clothes, changing identity, sudden scene change, text, watermark"

if st.button("✨ BUAT VIDEO NATURAL", type="primary", use_container_width=True):
    if uploaded_image is None:
        st.error("Pilih gambar terlebih dahulu.")
    elif not motion_prompt.strip():
        st.error("Tuliskan gerakan yang diinginkan terlebih dahulu.")
    else:
        status = st.empty()
        progress = st.progress(0)
        tmp_image_path = None
        try:
            suffix = os.path.splitext(uploaded_image.name)[1] or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_image.getvalue())
                tmp_image_path = tmp.name

            status.info("Menghubungkan ke mesin video AI Wan 2.2…")
            progress.progress(10)
            space_id = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"
            if hf_token.strip():
                client = Client(space_id, hf_token=hf_token.strip())
            else:
                client = Client(space_id)

            status.info("Mengirim gambar dan instruksi gerakan. Proses bisa memerlukan beberapa menit…")
            progress.progress(25)
            result = client.predict(
                handle_file(tmp_image_path),
                motion_prompt,
                int(quality_steps),
                negative_prompt,
                float(duration),
                1.0,
                1.0,
                42,
                True,
                api_name="/generate_video",
            )
            progress.progress(90)

            video_path = result[0] if isinstance(result, (list, tuple)) else result
            if not video_path or not os.path.exists(video_path):
                raise RuntimeError("Mesin AI tidak mengembalikan berkas video. Coba lagi atau periksa antrean layanan.")

            status.success("Video selesai dibuat!")
            progress.progress(100)
            st.video(video_path)
            with open(video_path, "rb") as f:
                st.download_button("⬇️ Simpan video MP4", data=f.read(), file_name="video_natural.mp4", mime="video/mp4", use_container_width=True)
            st.caption("Catatan: AI dapat mengubah detail kecil pada gambar. Hasil gerakan bergantung pada gambar, instruksi, antrean, dan batas layanan gratis.")
        except Exception as e:
            st.error("Video belum berhasil dibuat. Layanan gratis bisa sedang penuh, berubah, atau membatasi kuota.")
            with st.expander("Detail pesan error"):
                st.code(str(e))
            st.markdown("Jika muncul pesan kuota atau akses, coba lagi nanti atau masukkan token Hugging Face gratis pada bagian di atas.")
        finally:
            if tmp_image_path and os.path.exists(tmp_image_path):
                try:
                    os.remove(tmp_image_path)
                except OSError:
                    pass

st.divider()
st.caption("Dibuat untuk mengubah gambar menjadi gerakan AI sungguhan. Bukan generator efek kamera atau narasi.")
