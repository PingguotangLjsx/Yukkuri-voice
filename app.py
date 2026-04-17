import streamlit as st
import os
import random
import concurrent.futures
import time
import tempfile
import subprocess
import wave
import numpy as np
import requests
import re
import shutil
import base64
from urllib.parse import quote
from datetime import datetime
from bs4 import BeautifulSoup

st.set_page_config(page_title="油库里语音生成器", page_icon="🎤", layout="wide")
st.title("🎤 油库里语音生成器 (网页版)")
st.caption("中文 → 空耳片假名 / 日语翻译 → AquesTalk 语音合成")

# ---------- 会话状态 ----------
if "generated_audio_files" not in st.session_state:
    st.session_state.generated_audio_files = []
if "subtitle_file_path" not in st.session_state:
    st.session_state.subtitle_file_path = None
if "output_dir" not in st.session_state:
    st.session_state.output_dir = None
if "zip_data" not in st.session_state:
    st.session_state.zip_data = None
if "zip_name" not in st.session_state:
    st.session_state.zip_name = None
if "logs" not in st.session_state:
    st.session_state.logs = []
if "progress" not in st.session_state:
    st.session_state.progress = 0.0
if "progress_text" not in st.session_state:
    st.session_state.progress_text = "等待开始..."

# ---------- 声线数据 ----------
voice_options = [
    {"value": "aqtk1-f1", "name": "AT1-F1"},
    {"value": "aqtk1-f2", "name": "AT1-F2"},
    {"value": "aqtk1-m1", "name": "AT1-M1"},
    {"value": "aqtk1-m2", "name": "AT1-M2"},
    {"value": "aqtk1-dvd", "name": "AT1-DVD"},
    {"value": "aqtk1-imd1", "name": "AT1-IMD1"},
    {"value": "aqtk1-jgr", "name": "AT1-JGR"},
    {"value": "aqtk1-r1", "name": "AT1-R1"},
    {"value": "aqtk2-rm", "name": "AT2-RM"},
    {"value": "aqtk2-f1c", "name": "AT2-F1C"},
    {"value": "aqtk2-f3a", "name": "AT2-F3A"},
    {"value": "aqtk2-huskey", "name": "AT2-HUSKEY"},
    {"value": "aqtk2-m4b", "name": "AT2-M4B"},
    {"value": "aqtk2-mf1", "name": "AT2-MF1"},
    {"value": "aqtk2-rb2", "name": "AT2-RB2"},
    {"value": "aqtk2-rb3", "name": "AT2-RB3"},
    {"value": "aqtk2-robo", "name": "AT2-ROBO"},
    {"value": "aqtk2-yukkuri", "name": "AT2-YUKKURI"},
    {"value": "aqtk2-f4", "name": "AT2-F4"},
    {"value": "aqtk2-m5", "name": "AT2-M5"},
    {"value": "aqtk2-mf2", "name": "AT2-MF2"},
    {"value": "aqtk2-rm3", "name": "AT2-RM3"},
    {"value": "aqtk10-f1", "name": "AT10-F1"},
    {"value": "aqtk10-f2", "name": "AT10-F2"},
    {"value": "aqtk10-f3", "name": "AT10-F3"},
    {"value": "aqtk10-m1", "name": "AT10-M1"},
    {"value": "aqtk10-m2", "name": "AT10-M2"},
    {"value": "aqtk10-r1", "name": "AT10-R1"},
    {"value": "aqtk10-r2", "name": "AT10-R2"}
]

api_templates = [
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=f1&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=f2&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=m1&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=m2&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=dvd&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=imd1&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=jgr&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk1/koe.mp3?type=r1&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=rm&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=f1c&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=f3a&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=huskey&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=m4b&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=mf1&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=rb2&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=rb3&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=robo&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=yukkuri&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=f4&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=m5&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=mf2&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk2/koe.mp3?type=rm3&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk10/koe.mp3?type=f1e&speed=100&volume=100&pitch=100&accent=100&lmd=100&fsc=100&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk10/koe.mp3?type=f2e&speed=100&volume=100&pitch=77&accent=150&lmd=100&fsc=100&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk10/koe.mp3?type=f1e&speed=80&volume=100&pitch=100&accent=100&lmd=61&fsc=148&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk10/koe.mp3?type=m1e&speed=100&volume=100&pitch=30&accent=100&lmd=100&fsc=100&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk10/koe.mp3?type=m1e&speed=105&volume=100&pitch=45&accent=130&lmd=120&fsc=100&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk10/koe.mp3?type=m1e&speed=100&volume=100&pitch=30&accent=20&lmd=190&fsc=100&kanji={text}",
    "https://www.yukumo.net/api/v2/aqtk10/koe.mp3?type=f2e&speed=70&volume=100&pitch=50&accent=50&lmd=50&fsc=180&kanji={text}"
]

# ---------- 工具函数 ----------
def get_ffmpeg_path():
    import shutil
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
    common_paths = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
    return None

def change_pitch_audio(audio_data, sample_rate, pitch_factor):
    try:
        if pitch_factor == 100:
            return audio_data
        if isinstance(audio_data, bytes):
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
        else:
            audio_array = audio_data
        original_length = len(audio_array)
        new_length = int(original_length * (100 / pitch_factor))
        new_audio = np.zeros(new_length, dtype=np.int16)
        for i in range(new_length):
            original_pos = i * (pitch_factor / 100)
            if original_pos < original_length - 1:
                lower = int(original_pos)
                upper = lower + 1
                weight = original_pos - lower
                new_audio[i] = int(audio_array[lower] * (1 - weight) + audio_array[upper] * weight)
            elif original_pos < original_length:
                new_audio[i] = audio_array[int(original_pos)]
        return new_audio.tobytes()
    except Exception:
        return audio_data

def process_audio_pitch_in_memory(audio_data, pitch_factor):
    temp_files = []
    try:
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            return None
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(audio_data)
            temp_in = f.name
            temp_files.append(temp_in)
        temp_wav = tempfile.mktemp(suffix='.wav')
        temp_files.append(temp_wav)
        subprocess.run([
            ffmpeg_path, '-i', temp_in, '-acodec', 'pcm_s16le',
            '-ar', '44100', '-ac', '1', '-y', temp_wav
        ], capture_output=True, check=True)
        with wave.open(temp_wav, 'rb') as wav:
            frames = wav.readframes(-1)
            sr = wav.getframerate()
        adj = change_pitch_audio(frames, sr, pitch_factor)
        temp_adj_wav = tempfile.mktemp(suffix='.wav')
        temp_files.append(temp_adj_wav)
        with wave.open(temp_adj_wav, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sr)
            wav.writeframes(adj)
        temp_out = tempfile.mktemp(suffix='.mp3')
        temp_files.append(temp_out)
        subprocess.run([
            ffmpeg_path, '-i', temp_adj_wav, '-acodec', 'libmp3lame',
            '-ab', '64k', '-y', temp_out
        ], capture_output=True, check=True)
        with open(temp_out, 'rb') as f:
            return f.read()
    except Exception:
        return None
    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except:
                pass

def convert_to_katakana(text):
    for attempt in range(3):
        try:
            url = "https://www.ltool.net/chinese-simplified-and-traditional-characters-pinyin-to-katakana-converter-in-simplified-chinese.php"
            data = {'contents': text, 'firstinput': 'OK', 'option': '1', 'optionext': 'zenkaku'}
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': url}
            time.sleep(random.uniform(0.5, 1.5))
            resp = requests.post(url, data=data, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            res_div = soup.find('div', {'id': 'result'})
            if res_div:
                final = res_div.find('div', {'class': 'finalresult'})
                if final:
                    return final.text.strip()
        except:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None

def translate_with_mymemory(text, target_lang='ja', source_lang='zh'):
    url = "https://api.mymemory.translated.net/get"
    params = {'q': text, 'langpair': f'{source_lang}|{target_lang}'}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get('responseStatus') == 200:
            return data['responseData']['translatedText']
    except:
        pass
    return None

def translate_with_google(text):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {'client': 'gtx', 'sl': 'zh-CN', 'tl': 'ja', 'dt': 't', 'q': text}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        result = resp.json()
        if result and len(result) > 0 and result[0]:
            return ''.join([part[0] for part in result[0] if part and part[0]])
    except:
        pass
    return None

def translate_to_japanese(text):
    translated = translate_with_mymemory(text)
    if translated and translated != text:
        return translated
    translated = translate_with_google(text)
    if translated:
        return translated
    return text

def get_audio_duration(file_path):
    try:
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            return 2000
        probe = ffmpeg.replace('ffmpeg', 'ffprobe')
        if not os.path.exists(probe):
            probe = ffmpeg
        cmd = [probe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if out.stdout.strip():
            return int(float(out.stdout.strip()) * 1000)
    except:
        pass
    return 2000

def format_srt_time(ms):
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def build_api_url(text, voice_idx, effect, boyomi, speed, volume):
    base = api_templates[voice_idx]
    enc = quote(text)
    boyomi_str = "true" if boyomi else "false"
    if "aqtk1" in base or "aqtk2" in base:
        url = base.replace("{text}", enc)
        url += f"&effect={effect}&boyomi={boyomi_str}&speed={speed}&volume={volume}"
    else:
        url = base.replace("{text}", enc)
        url = re.sub(r'speed=\d+', f'speed={speed}', url)
        url = re.sub(r'volume=\d+', f'volume={volume}', url)
        url += f"&effect={effect}&boyomi={boyomi_str}"
    return url

def generate_single_audio(conv_text, voice_idx, output_dir, orig_text, idx, total, params):
    effect, boyomi, speed, volume, pitch = params
    try:
        api_url = build_api_url(conv_text, voice_idx, effect, boyomi, speed, volume)
        headers = {'User-Agent': 'Mozilla/5.0'}
        time.sleep(random.uniform(0.2, 0.8))
        resp = requests.get(api_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return False, None, 0, f"HTTP {resp.status_code}"
        audio_data = resp.content
        if pitch != 100:
            adjusted = process_audio_pitch_in_memory(audio_data, pitch)
            if adjusted:
                audio_data = adjusted
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', orig_text)[:50]
        filename = f"{idx+1:03d}_{safe_name}.mp3"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(audio_data)
        duration = get_audio_duration(filepath)
        return True, filepath, duration, None
    except Exception as e:
        return False, None, 0, str(e)

def get_binary_file_downloader_html(bin_data, file_label='下载', file_name='file.mp3', button_style=True):
    b64 = base64.b64encode(bin_data).decode()
    if button_style:
        style = """
            display: inline-block;
            background-color: #f0f2f6;
            color: #31333f;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            text-decoration: none;
            font-weight: 400;
            border: 1px solid #d5dae5;
            margin: 0.2rem 0;
        """
        return f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}" style="{style}">{file_label}</a>'
    else:
        return f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}">⬇️ {file_label}</a>'

# ---------- UI 侧边栏 ----------
with st.sidebar:
    st.header("⚙️ 参数设置")
    convert_mode_label = st.radio("转换模式", ["空耳 (片假名)", "翻译 (日语)"], index=0)
    convert_mode = "空耳" if "空耳" in convert_mode_label else "翻译"

    voice_names = [v["name"] for v in voice_options]
    selected_voice = st.selectbox("语音类型", voice_names)
    voice_index = voice_names.index(selected_voice)

    st.divider()
    st.subheader("🎛️ 高级参数")
    effect_label = st.radio("音效", ["无效果", "回声效果"], index=0, horizontal=True)
    effect = "none" if effect_label == "无效果" else "echo"
    boyomi_label = st.radio("捧读", ["OFF", "ON"], index=0, horizontal=True)
    boyomi = (boyomi_label == "ON")
    speed = st.slider("速度", 50, 300, 100, step=1)
    volume = st.slider("音量", 10, 200, 100, step=1)
    pitch = st.slider("音程", 0, 300, 100, step=1)

    st.divider()
    st.subheader("📁 输出选项")
    generate_subtitle = st.checkbox("生成 SRT 字幕文件", value=False)

# ---------- 主区域 ----------
st.subheader("📝 输入文本 (每行生成一个独立语音)")
default_text = "我喜欢你"
text_input = st.text_area("在此输入文本，一行一条", value=default_text, height=200)

col1, _ = st.columns([1, 2])
with col1:
    if st.button("📊 统计行数", use_container_width=True):
        lines = [l.strip() for l in text_input.split("\n") if l.strip()]
        st.toast(f"共 {len(lines)} 行文本")

st.divider()

progress_bar = st.progress(st.session_state.progress, text=st.session_state.progress_text)
log_placeholder = st.empty()

# ---------- 开始生成 ----------
if st.button("🚀 开始生成", type="primary", use_container_width=True):
    lines = [l.strip() for l in text_input.split("\n") if l.strip()]
    if not lines:
        st.warning("请输入至少一行文本")
    else:
        st.session_state.generated_audio_files = []
        st.session_state.subtitle_file_path = None
        st.session_state.zip_data = None
        st.session_state.zip_name = None
        st.session_state.output_dir = None
        st.session_state.logs = []
        st.session_state.progress = 0.0
        st.session_state.progress_text = "准备中..."

        total = len(lines)
        max_workers = min(total, 10)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(tempfile.gettempdir(), "yukkuri_outputs", timestamp)
        os.makedirs(output_dir, exist_ok=True)
        st.session_state.output_dir = output_dir

        def add_log(msg):
            st.session_state.logs.append(msg)
            log_placeholder.text("\n".join(st.session_state.logs[-10:]))

        def update_progress(val, text):
            st.session_state.progress = val
            st.session_state.progress_text = text
            progress_bar.progress(val, text=text)

        add_log("===== 开始处理 =====")
        add_log(f"使用并发数: {max_workers}")
        update_progress(0.05, "转换文本中...")

        if convert_mode == "空耳":
            convert_func = convert_to_katakana
        else:
            convert_func = translate_to_japanese

        converted = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {executor.submit(convert_func, line): i for i, line in enumerate(lines)}
            for future in concurrent.futures.as_completed(future_to_idx):
                i = future_to_idx[future]
                line = lines[i]
                try:
                    result = future.result(timeout=20)
                    if result:
                        if convert_mode == "空耳":
                            result = re.sub(r'\([^)]*\)', '', result).replace(' ', '')
                        converted.append((i, line, result))
                        add_log(f"✅ 转换 [{i+1}/{total}]: {line[:20]}...")
                    else:
                        add_log(f"❌ 转换失败 [{i+1}/{total}]: {line[:20]}...")
                except Exception as e:
                    add_log(f"❌ 转换异常 [{i+1}/{total}]: {str(e)[:30]}")
                update_progress(0.05 + 0.15 * (len(converted) + len(future_to_idx) - len(converted))/total,
                                f"转换进度 {len(converted)}/{total}")

        if not converted:
            st.error("所有文本转换失败，无法生成音频。")
            st.stop()

        converted.sort(key=lambda x: x[0])
        add_log(f"转换完成，共 {len(converted)} 条，开始生成音频...")
        update_progress(0.20, "生成音频中...")

        success_count = 0
        audio_files = []
        subtitle_entries = []
        params = (effect, boyomi, speed, volume, pitch)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_info = {}
            for idx, (orig_idx, orig_text, conv_text) in enumerate(converted):
                future = executor.submit(
                    generate_single_audio, conv_text, voice_index, output_dir,
                    orig_text, idx, len(converted), params
                )
                future_to_info[future] = (idx, orig_text, orig_idx)

            for future in concurrent.futures.as_completed(future_to_info):
                idx, orig_text, orig_idx = future_to_info[future]
                try:
                    ok, filepath, duration, err = future.result(timeout=60)
                    if ok:
                        success_count += 1
                        audio_files.append((idx+1, orig_text, filepath))
                        subtitle_entries.append((orig_idx, orig_text, duration))
                        add_log(f"✅ [{idx+1}/{len(converted)}] {orig_text[:20]}...")
                    else:
                        add_log(f"❌ [{idx+1}/{len(converted)}] {orig_text[:20]}... {err[:30]}")
                except Exception as e:
                    add_log(f"❌ 任务异常 [{idx+1}/{len(converted)}]: {str(e)[:30]}")
                update_progress(0.20 + 0.70 * (idx+1)/len(converted), f"生成进度 {idx+1}/{len(converted)}")

        audio_files.sort(key=lambda x: x[0])
        st.session_state.generated_audio_files = audio_files

        if generate_subtitle and subtitle_entries:
            subtitle_entries.sort(key=lambda x: x[0])
            srt_path = os.path.join(output_dir, "subtitles.srt")
            with open(srt_path, 'w', encoding='utf-8') as f:
                cur = 0
                for i, (_, txt, dur) in enumerate(subtitle_entries, 1):
                    start = cur
                    end = cur + dur
                    f.write(f"{i}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{txt}\n\n")
                    cur = end + 100
            st.session_state.subtitle_file_path = srt_path
            add_log("📄 字幕文件已生成")

        if audio_files:
            zip_path = output_dir + ".zip"
            shutil.make_archive(output_dir, 'zip', output_dir)
            with open(zip_path, "rb") as f:
                st.session_state.zip_data = f.read()
            st.session_state.zip_name = f"yukkuri_{timestamp}.zip"
            add_log("📦 已准备好打包文件")

        update_progress(1.0, f"完成！成功 {success_count}/{len(converted)}")
        add_log(f"===== 完成! 成功 {success_count}/{len(converted)} =====")
        st.rerun()

log_placeholder.text("\n".join(st.session_state.logs[-10:]))

# ---------- 展示生成结果 ----------
if st.session_state.generated_audio_files:
    st.divider()
    st.subheader("🎵 生成的音频列表")
    st.caption("点击播放试听，或点击链接下载")

    for idx, orig, path in st.session_state.generated_audio_files:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"**{idx}. {orig}**")
        with col2:
            with open(path, "rb") as f:
                st.audio(f.read(), format="audio/mp3")
        with col3:
            with open(path, "rb") as f:
                data = f.read()
            filename = os.path.basename(path)
            st.markdown(
                get_binary_file_downloader_html(data, file_label="下载", file_name=filename, button_style=False),
                unsafe_allow_html=True
            )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.zip_data:
            st.markdown(
                get_binary_file_downloader_html(
                    st.session_state.zip_data,
                    file_label="📦 打包下载全部音频 (ZIP)",
                    file_name=st.session_state.zip_name,
                    button_style=True
                ),
                unsafe_allow_html=True
            )
    with col2:
        if st.session_state.subtitle_file_path and os.path.exists(st.session_state.subtitle_file_path):
            with open(st.session_state.subtitle_file_path, "rb") as f:
                st.download_button(
                    label="📄 下载字幕文件 (SRT)",
                    data=f,
                    file_name="subtitles.srt",
                    mime="text/plain",
                    key="sub_download_unique",
                    use_container_width=True
                )