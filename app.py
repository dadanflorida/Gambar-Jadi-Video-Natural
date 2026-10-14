import os, tempfile, asyncio, shutil, time
from pathlib import Path
import streamlit as st
from gradio_client import Client, handle_file
import edge_tts
import numpy as np, wave
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip

st.set_page_config(page_title='Gambar Jadi Video Natural', page_icon='🎬', layout='centered')
st.title('🎬 Gambar Jadi Video Natural')
st.write('Buat video bergerak dari gambar, tambahkan narasi bahasa Indonesia, lalu coba sinkronkan gerakan bibir aktor secara otomatis.')
st.info('Versi percobaan: sinkronisasi bibir memakai layanan publik MuseTalk. Layanan gratis bisa antre, membatasi penggunaan, atau sewaktu-waktu tidak tersedia.')
with st.expander('🔑 Token Hugging Face (opsional)', expanded=False):
    st.write('Token Read opsional. Jangan bagikan token kepada siapa pun.')
    hf_token = st.text_input('Hugging Face token', type='password')

image = st.file_uploader('1. Pilih gambar aktor', type=['png','jpg','jpeg','webp'])
motions = {
 'Gerakan natural': 'The subject moves naturally with subtle realistic body motion, natural blinking and breathing, slight environmental movement, realistic physics, smooth continuous motion. Keep the same identity, face, clothes and background. No sudden scene changes.',
 'Orang berjalan': 'The person begins walking naturally at a realistic pace, with believable steps, natural arm swing and body balance. Keep the same identity, face, clothes and background. Smooth continuous motion, realistic physics.',
 'Silat / bela diri': 'The martial artist performs one smooth, realistic silat movement: shifts stance, steps forward, delivers one controlled punch followed by one clear kick, then returns to a balanced guard. Realistic body mechanics, stable anatomy, same face and clothing, no extra limbs.',
 'Angin dan suasana': 'Subtle natural environmental motion: leaves and fabric move gently in the breeze, hair moves slightly, clouds drift slowly, realistic lighting and physics. Keep the main subject and composition consistent.',
 'Produk bergerak': 'A smooth realistic product showcase. The camera remains mostly steady while the product rotates slightly or is revealed by subtle natural movement and changing reflections. Keep the product shape, labels, colors and details unchanged.',
 'Tulis gerakan sendiri': 'CUSTOM'
}
motion_choice = st.selectbox('2. Pilih gerakan', list(motions))
if motion_choice == 'Tulis gerakan sendiri':
    motion_prompt = st.text_area('Jelaskan gerakan', placeholder='Contoh: Aktor menoleh ke kamera lalu mengangguk pelan.')
else:
    motion_prompt = motions[motion_choice]
    st.caption('Instruksi gerakan terpilih:')
    st.write(motion_prompt)
col1, col2 = st.columns(2)
with col1: duration = st.slider('3. Durasi video dasar (detik)', 2.0, 5.0, 4.0, 0.5)
with col2: steps = st.selectbox('Detail gerakan', [4,6,8], index=1, format_func=lambda x:{4:'Cepat',6:'Seimbang',8:'Lebih detail'}[x])

st.divider(); st.subheader('🔊 4. Narasi, suara, dan musik')
narration = st.text_area('Tulis kalimat yang akan diucapkan aktor', placeholder='Contoh: Halo teman-teman, apa kabar hari ini?', height=100)
voice_label = st.selectbox('Pilih suara', ['Perempuan Indonesia','Laki-laki Indonesia'])
voice = 'id-ID-GadisNeural' if voice_label == 'Perempuan Indonesia' else 'id-ID-ArdiNeural'
add_music = st.checkbox('Tambahkan musik latar instrumental bawaan', value=True)
sync_lips = st.checkbox('Coba sinkronkan gerakan bibir dengan narasi (AI)', value=True)
st.caption('Untuk hasil terbaik, gunakan gambar wajah menghadap kamera, mulut terlihat jelas, dan narasi pendek yang kira-kira muat dalam durasi video.')

NEGATIVE = 'static image, frozen motion, flicker, blurry, distorted face, deformed hands, extra fingers, extra limbs, changing clothes, changing identity, sudden scene change, text, watermark'

def new_client(space, token):
    return Client(space, hf_token=token.strip()) if token and token.strip() else Client(space)
def generate_wan_with_retry(
    img_path, motion_prompt, steps, duration, token, status, bar
):
    errors = []

    for attempt in range(1, 3):
        try:
            if attempt == 1:
                status.info(
                    "Menghubungkan ke Wan 2.2 dan membuat video. "
                    "Mohon tunggu..."
                )
                bar.progress(15)
            else:
                status.warning(
                    "Percobaan pertama gagal. "
                    "Menunggu 8 detik sebelum mencoba kembali..."
                )
                time.sleep(8)
                status.info("Mencoba kembali menghubungkan ke Wan 2.2...")
                bar.progress(20)

            wan = new_client(
                "zerogpu-aoti/wan2-2-fp8da-aoti-faster",
                token
            )

            result = wan.predict(
                handle_file(img_path),
                motion_prompt,
                int(steps),
                NEGATIVE,
                float(duration),
                1.0,
                1.0,
                42,
                True,
                api_name="/generate_video"
            )

            base = result[0] if isinstance(result, (list, tuple)) else result

            if isinstance(base, dict):
                base = base.get("path") or base.get("name")

            if not base or not os.path.exists(str(base)):
                raise RuntimeError(
                    f"Video tidak ditemukan pada hasil layanan: {result}"
                )

            return str(base)

        except Exception as e:
            errors.append(
                f"Percobaan {attempt}/2: {type(e).__name__}: {e}"
            )

    raise RuntimeError(
        "Wan 2.2 gagal setelah dua percobaan.\n\n"
        + "\n\n".join(errors)
    )
async def save_tts(text, voice, path):
    await edge_tts.Communicate(text=text, voice=voice).save(path)

def make_music(path, seconds, sr=22050):
    n = max(1, int(seconds*sr)); t = np.arange(n, dtype=np.float32)/sr
    sound = (0.10*np.sin(2*np.pi*220*t) + 0.07*np.sin(2*np.pi*277.18*t) + 0.06*np.sin(2*np.pi*329.63*t) + 0.025*np.sin(2*np.pi*440*t))
    env = np.clip(np.minimum(1, t/0.6)*np.minimum(1, (seconds-t)/0.6), 0, 1)
    sound *= env*(0.65+0.35*np.sin(2*np.pi*0.12*t))
    pcm = np.int16(np.clip(sound*9000, -32768, 32767))
    with wave.open(path,'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr); f.writeframes(pcm.tobytes())

def mux_audio(video_path, voice_path, music_path, output_path, with_music):
    video = VideoFileClip(video_path)
    voice_clip = AudioFileClip(voice_path)
    length = min(video.duration, voice_clip.duration)
    tracks = [voice_clip.subclipped(0, length).with_volume_scaled(1.0)]
    music_clip = None
    if with_music and os.path.exists(music_path):
        music_clip = AudioFileClip(music_path)
        tracks.append(music_clip.subclipped(0, min(video.duration, music_clip.duration)).with_volume_scaled(0.15))
    mix = CompositeAudioClip(tracks)
    final = video.with_audio(mix)
    final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=video.fps or 25, logger=None)
    final.close(); video.close(); voice_clip.close(); mix.close()
    if music_clip: music_clip.close()

if st.button('✨ BUAT VIDEO + NARASI + GERAKAN BIBIR', type='primary', use_container_width=True):
    if image is None: st.error('Pilih gambar aktor terlebih dahulu.')
    elif not narration.strip(): st.error('Tulis narasi terlebih dahulu.')
    elif motion_choice == 'Tulis gerakan sendiri' and not motion_prompt.strip(): st.error('Tuliskan gerakan terlebih dahulu.')
    else:
        work = tempfile.mkdtemp(prefix='gambar_video_')
        img_path = os.path.join(work, 'aktor'+(Path(image.name).suffix or '.png'))
        tts_path = os.path.join(work, 'narasi.mp3'); music_path = os.path.join(work, 'musik.wav')
        base_path = os.path.join(work, 'video_dasar.mp4'); regular_path = os.path.join(work, 'video_narasi.mp4')
        lip_raw_path = os.path.join(work, 'video_lipsync_raw.mp4'); final_path = os.path.join(work, 'video_lipsync.mp4')
        status = st.empty(); bar = st.progress(0)
        try:
            with open(img_path,'wb') as f: f.write(image.getvalue())
            status.info('Tahap 1/4: membuat suara narasi bahasa Indonesia…')
            asyncio.run(save_tts(narration.strip(), voice, tts_path)); bar.progress(10)
            status.info("Tahap 2/4: membuat video bergerak dari gambar...")
            base = generate_wan_with_retry( img_path, motion_prompt, int(steps), float(duration), hf_token, status, bar) 
            shutil.copyfile(base, base_path)
            bar.progress(45)
            clip = VideoFileClip(base_path); video_len = clip.duration; clip.close()
            make_music(music_path, video_len)
            status.info('Membuat versi dengan narasi sebagai cadangan…')
            mux_audio(base_path, tts_path, music_path, regular_path, add_music); bar.progress(65)
            lip_ok = False; lip_error = ''
            if sync_lips:
                try:
                    status.info('Tahap 4/4: mencoba sinkronisasi bibir melalui MuseTalk. Bisa memerlukan waktu…')
                    muse = new_client('trymonolith/MuseTalk', hf_token)
                    # Endpoint arguments follow the public Space UI: audio, video/image, FPS, quality.
                    lip = muse.predict(handle_file(tts_path), handle_file(base_path), 25, 'Medium', api_name='/generate_lipsync_video')
                    lipfile = lip[0] if isinstance(lip,(list,tuple)) else lip
                    if isinstance(lipfile,dict): lipfile = lipfile.get('path') or lipfile.get('name')
                    if not lipfile or not os.path.exists(str(lipfile)): raise RuntimeError(f'MuseTalk tidak mengembalikan video: {lip}')
                    shutil.copyfile(str(lipfile), lip_raw_path)
                    mux_audio(lip_raw_path, tts_path, music_path, final_path, add_music)
                    lip_ok = True; bar.progress(100); status.success('Selesai! Video dengan percobaan gerakan bibir sudah dibuat.')
                except Exception as e:
                    lip_error = str(e)
                    status.warning('Sinkronisasi bibir belum berhasil. Video narasi biasa tetap bisa disimpan.')
            else:
                bar.progress(100); status.success('Selesai! Video dengan narasi sudah dibuat.')
            if lip_ok:
                st.subheader('🎭 Video dengan gerakan bibir AI'); st.video(final_path)
                with open(final_path,'rb') as f: st.download_button('⬇️ Simpan video gerakan bibir', f.read(), file_name='video_bibir_sinkron.mp4', mime='video/mp4', use_container_width=True)
            else:
                st.subheader('🎬 Video dengan narasi'); st.video(regular_path)
                with open(regular_path,'rb') as f: st.download_button('⬇️ Simpan video narasi', f.read(), file_name='video_narasi.mp4', mime='video/mp4', use_container_width=True)
                if lip_error:
                    with st.expander('Detail pesan MuseTalk'): st.code(lip_error)
            with st.expander('Catatan hasil'):
                st.write('Versi ini masih percobaan. Video dasar hanya 2–5 detik; narasi yang lebih panjang bisa terpotong. Sinkronisasi bibir tergantung layanan publik dan kualitas gambar.')
        except Exception as e:
            st.error('Pembuatan video belum berhasil. Layanan AI gratis mungkin antre, membatasi kuota, atau mengubah API.')
            with st.expander('Detail pesan error'): st.code(str(e))

st.divider()
st.caption('Aplikasi memakai layanan AI publik untuk gerakan video dan sinkronisasi bibir. Ketersediaan gratis dan batas penggunaan dapat berubah.')
