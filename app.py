import asyncio
import os
import shutil
import tempfile
import wave

import edge_tts
import numpy as np
import streamlit as st
from gradio_client import Client, handle_file
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip

st.set_page_config(page_title="Gambar Jadi Video Natural", page_icon="🎬", layout="centered")
st.title("🎬 Gambar Jadi Video Natural")
st.write("Ubah satu gambar menjadi klip video dengan gerakan AI, lalu tambahkan narasi bahasa Indonesia dan musik latar.")
st.info("Mesin video memakai Wan 2.2 di Hugging Face. Layanan gratis dapat memiliki antrean dan batas pemakaian. Narasi memakai layanan online Edge TTS; musik latar sederhana dibuat langsung oleh aplikasi.")

with st.expander("🔑 Token Hugging Face (opsional)", expanded=False):
    st.write("Token gratis dengan izin Read dapat membantu menghubungkan akun Hugging Face. Jangan bagikan token kepada siapa pun.")
    hf_token = st.text_input("Hugging Face token", type="password")

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
    st.caption("Instruksi gerakan:")
    st.write(motion_prompt)

col1, col2 = st.columns(2)
with col1:
    duration = st.slider("3. Durasi video AI", min_value=2.0, max_value=5.0, value=3.5, step=0.5)
with col2:
    quality_steps = st.selectbox("Kecepatan / detail", options=[4, 6, 8], index=1, format_func=lambda x: {4: "Cepat", 6: "Seimbang", 8: "Lebih detail (lebih lama)"}[x])

st.subheader("🔊 4. Suara dan musik")
narration_text = st.text_area("Teks narasi (opsional)", placeholder="Contoh: Inilah gerakan silat yang dilakukan dengan tenang dan terkontrol.", height=90, help="Jika diisi, aplikasi mencoba membuat suara bahasa Indonesia. Jika kosong, video tetap bisa memakai musik saja.")
add_music = st.checkbox("Tambahkan musik latar instrumental bawaan", value=True)
if add_music:
    st.caption("Musik instrumental sederhana dibuat oleh aplikasi, tanpa perlu mengunggah file musik.")
voice_choice = st.selectbox("Suara narasi", options=[("Perempuan Indonesia", "id-ID-GadisNeural"), ("Laki-laki Indonesia", "id-ID-ArdiNeural")], format_func=lambda item: item[0])[1]
negative_prompt = "static image, frozen motion, flicker, blurry, distorted face, deformed hands, extra fingers, extra limbs, changing clothes, changing identity, sudden scene change, text, watermark"


def create_builtin_music(output_path, duration_seconds, sample_rate=24000):
    """Buat musik latar ambient sederhana secara offline."""
    duration_seconds = max(float(duration_seconds), 1.0)
    count = int(sample_rate * duration_seconds)
    t = np.arange(count, dtype=np.float32) / sample_rate
    roots = [220.00, 261.63, 196.00, 174.61]
    music = np.zeros(count, dtype=np.float32)
    for i, start in enumerate(np.arange(0, duration_seconds, 4.0)):
        end = min(start + 4.0, duration_seconds)
        left, right = int(start * sample_rate), int(end * sample_rate)
        local_t = t[left:right] - start
        root = roots[i % len(roots)]
        envelope = np.minimum(np.minimum(local_t / 0.8, 1.0), np.minimum((end - start - local_t) / 0.8, 1.0))
        envelope = np.clip(envelope, 0.0, 1.0)
        chord = np.sin(2*np.pi*root*local_t) + 0.55*np.sin(2*np.pi*root*1.25*local_t) + 0.35*np.sin(2*np.pi*root*1.5*local_t)
        music[left:right] += 0.10 * chord * envelope
    fade = min(int(sample_rate * 0.5), count // 2)
    if fade > 0:
        music[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        music[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    peak = float(np.max(np.abs(music))) if count else 0.0
    if peak > 0:
        music = music / max(peak, 1e-6) * 0.22
    pcm = (np.clip(music, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(output_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


async def create_indonesian_narration(text, voice, output_path):
    await edge_tts.Communicate(text=text, voice=voice).save(output_path)


def make_final_video(source_video, narration_text, voice, add_music, work_dir):
    video = VideoFileClip(source_video)
    audio_clips = []
    warnings = []
    final_path = os.path.join(work_dir, "video_dengan_audio.mp4")
    try:
        if narration_text.strip():
            narration_path = os.path.join(work_dir, "narasi.mp3")
            try:
                asyncio.run(create_indonesian_narration(narration_text.strip(), voice, narration_path))
                narration_clip = AudioFileClip(narration_path)
                if narration_clip.duration > video.duration:
                    narration_clip = narration_clip.subclipped(0, video.duration)
                audio_clips.append(narration_clip.with_volume_scaled(1.0))
            except Exception as exc:
                warnings.append("Narasi otomatis gagal dibuat; video tetap diproses. Detail: " + str(exc))
        if add_music:
            music_path = os.path.join(work_dir, "musik_bawaan.wav")
            create_builtin_music(music_path, video.duration)
            audio_clips.append(AudioFileClip(music_path).with_volume_scaled(0.28))
        final_video = video.with_audio(CompositeAudioClip(audio_clips).with_duration(video.duration)) if audio_clips else video
        final_video.write_videofile(final_path, codec="libx264", audio_codec="aac" if audio_clips else None, fps=video.fps or 24, logger=None, preset="ultrafast")
        if final_video is not video:
            final_video.close()
        return final_path, warnings
    finally:
        video.close()
        for clip in audio_clips:
            try:
                clip.close()
            except Exception:
                pass


if st.button("✨ BUAT VIDEO NATURAL", type="primary", use_container_width=True):
    if uploaded_image is None:
        st.error("Pilih gambar terlebih dahulu.")
    elif not motion_prompt.strip():
        st.error("Tuliskan gerakan yang diinginkan terlebih dahulu.")
    else:
        work_dir = tempfile.mkdtemp(prefix="gambar_video_")
        try:
            suffix = os.path.splitext(uploaded_image.name)[1] or ".png"
            tmp_image_path = os.path.join(work_dir, "gambar" + suffix)
            with open(tmp_image_path, "wb") as tmp:
                tmp.write(uploaded_image.getvalue())
            status = st.empty()
            progress = st.progress(0)
            status.info("Menghubungkan ke mesin video AI Wan 2.2…")
            progress.progress(10)
            space_id = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"
            client = Client(space_id, hf_token=hf_token.strip()) if hf_token.strip() else Client(space_id)
            status.info("Mengirim gambar dan instruksi gerakan ke AI… Proses dapat memerlukan beberapa menit.")
            progress.progress(25)
            result = client.predict(handle_file(tmp_image_path), motion_prompt, int(quality_steps), negative_prompt, float(duration), 1.0, 1.0, 42, True, api_name="/generate_video")
            progress.progress(75)
            video_path = result[0] if isinstance(result, (list, tuple)) else result
            if not video_path or not os.path.exists(video_path):
                raise RuntimeError("Mesin AI tidak mengembalikan berkas video. Coba lagi atau periksa antrean layanan.")
            status.info("Menambahkan suara dan musik ke video…")
            final_path, warnings = make_final_video(video_path, narration_text, voice_choice, add_music, work_dir)
            progress.progress(100)
            status.success("Video selesai dibuat!")
            for warning in warnings:
                st.warning(warning)
            st.video(final_path)
            with open(final_path, "rb") as f:
                st.download_button("⬇️ Simpan video MP4 dengan audio", data=f.read(), file_name="video_natural_dengan_audio.mp4", mime="video/mp4", use_container_width=True)
            st.caption("Musik bawaan berupa instrumental ambient sederhana. Kualitas gerakan tetap bergantung pada gambar, instruksi, model AI, antrean, dan batas layanan gratis.")
        except Exception as e:
            st.error("Video belum berhasil dibuat. Layanan gratis atau proses audio bisa sedang bermasalah.")
            with st.expander("Detail pesan error"):
                st.code(str(e))
            st.markdown("Jika masalahnya antrean atau akses Hugging Face, coba lagi nanti. Jika error muncul saat menambahkan audio, lihat Detail pesan error.")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

st.divider()
st.caption("Aplikasi ini membuat gerakan dengan AI, lalu menambahkan audio secara terpisah.")
