import streamlit as st
import os
import concurrent.futures
import time
import tempfile
import subprocess
import wave
import numpy as np
import re
import shutil
import base64
import zugbruecke.ctypes as ctypes   # <--- 唯一关键改动
from datetime import datetime
import pypinyin
from katakana_map import PINYIN_TO_KATAKANA

st.set_page_config(page_title="油库里语音生成器", page_icon="🎤", layout="wide")
st.title("🎤 油库里语音生成器")
st.caption("中文 → 空耳片假名 → AquesTalk 语音合成")

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

# ---------- 配置：DLL根目录（相对于项目根目录） ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DLL_ROOT = os.path.join(BASE_DIR, "AquesTalkDLLs")

# 若环境变量存在则覆盖（便于灵活配置）
if os.environ.get("AQUESTALK_DLL_ROOT"):
    DLL_ROOT = os.environ["AQUESTALK_DLL_ROOT"]

# ---------- 声线数据（仅保留9个可用音色） ----------
voice_options = [
    {"value": "dvd",   "name": "DVD"},
    {"value": "f1",    "name": "F1"},
    {"value": "f2",    "name": "F2"},
    {"value": "f3",    "name": "F3"},
    {"value": "imd1",  "name": "IMD1"},
    {"value": "jgr",   "name": "JGR"},
    {"value": "m1",    "name": "M1"},
    {"value": "m2",    "name": "M2"},
    {"value": "r1",    "name": "R1"}
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
    if pitch_factor == 100:
        return audio_data
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        return audio_data
    temp_files = []
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            temp_in = f.name
            temp_files.append(temp_in)
        with wave.open(temp_in, 'rb') as wav:
            params = wav.getparams()
            frames = wav.readframes(-1)
            sr = wav.getframerate()
        adjusted = change_pitch_audio(frames, sr, pitch_factor)
        temp_out = tempfile.mktemp(suffix='.wav')
        temp_files.append(temp_out)
        with wave.open(temp_out, 'wb') as wav:
            wav.setparams(params)
            wav.writeframes(adjusted)
        with open(temp_out, 'rb') as f:
            return f.read()
    except Exception:
        return audio_data
    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except:
                pass

def convert_to_katakana(text):
    result = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            py_list = pypinyin.lazy_pinyin(ch)
            if py_list:
                py = py_list[0]
                result.append(PINYIN_TO_KATAKANA.get(py, ch))
            else:
                result.append(ch)
        else:
            result.append(ch)
    result_str = ''.join(result)
    result_str = re.sub(r'\([^)]*\)', '', result_str).replace(' ', '')
    return result_str

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

# ---------- 核心：调用DLL合成语音 ----------
def synthesize_with_aquestalk(text, dll_path, speed=100):
    try:
        dll = ctypes.WinDLL(dll_path)
    except OSError as e:
        st.error(f"加载语音引擎失败: {e}")
        return None, None

    # 尝试多种可能的导出函数名
    func_names = ['AquesTalk_Synthe', '_AquesTalk_Synthe@12', 'AquesTalk_Synthe@12']
    synthe_func = None
    for name in func_names:
        try:
            synthe_func = getattr(dll, name)
            break
        except AttributeError:
            continue
    if synthe_func is None:
        st.error("语音引擎不兼容，请检查 DLL 版本。")
        return None, None

    free_func_names = ['AquesTalk_FreeWave', '_AquesTalk_FreeWave@4']
    free_func = None
    for name in free_func_names:
        try:
            free_func = getattr(dll, name)
            break
        except AttributeError:
            continue

    synthe_func.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    synthe_func.restype = ctypes.POINTER(ctypes.c_ubyte)
    if free_func:
        free_func.argtypes = [ctypes.c_void_p]
        free_func.restype = None

    try:
        text_encoded = text.encode('shift_jis')
    except UnicodeEncodeError as e:
        st.error(f"文本编码失败: {e}")
        return None, None

    audio_size = ctypes.c_int()
    try:
        wav_data_ptr = synthe_func(text_encoded, speed, ctypes.byref(audio_size))
    except Exception as e:
        st.error(f"合成过程出错: {e}")
        return None, None

    if not wav_data_ptr:
        st.error("合成失败，可能包含不支持的字符。")
        return None, None

    wav_bytes = bytes(wav_data_ptr[:audio_size.value])
    if free_func:
        free_func(wav_data_ptr)

    try:
        import io
        with io.BytesIO(wav_bytes) as f:
            with wave.open(f, 'rb') as w:
                sr = w.getframerate()
        return wav_bytes, sr
    except:
        return wav_bytes, 8000

def generate_single_audio(conv_text, voice_value, output_dir, orig_text, idx, total, params):
    _, _, speed, _, pitch = params
    try:
        dll_path = os.path.join(DLL_ROOT, voice_value, "AquesTalk.dll")
        if not os.path.exists(dll_path):
            return False, None, 0, f"语音文件缺失: {dll_path}"

        wav_data, _ = synthesize_with_aquestalk(conv_text, dll_path, speed)
        if wav_data is None:
            return False, None, 0, "合成失败"

        if pitch != 100:
            wav_data = process_audio_pitch_in_memory(wav_data, pitch)

        safe_name = re.sub(r'[<>:"/\\|?*]', '_', orig_text)[:50]
        filename = f"{idx+1:03d}_{safe_name}.wav"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(wav_data)

        duration = get_audio_duration(filepath)
        return True, filepath, duration, None
    except Exception as e:
        return False, None, 0, str(e)

# ---------- UI 侧边栏 ----------
with st.sidebar:
    st.header("⚙️ 参数设置")

    ffmpeg_ok = get_ffmpeg_path() is not None
    if not ffmpeg_ok:
        st.info("💡 音程调节需要 ffmpeg，若未安装则无效。")

    voice_names = [v["name"] for v in voice_options]
    selected_voice = st.selectbox("语音类型", voice_names)
    voice_index = voice_names.index(selected_voice)
    voice_value = voice_options[voice_index]["value"]

    st.divider()
    st.subheader("🎛️ 高级参数")
    speed = st.slider("语速", 50, 300, 100, step=1)
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
        # 重置状态
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
        if not get_ffmpeg_path():
            add_log("提示: ffmpeg 未找到，音程调节将跳过")
        update_progress(0.05, "转换文本中...")

        # 转换空耳
        converted = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {executor.submit(convert_to_katakana, line): i for i, line in enumerate(lines)}
            for future in concurrent.futures.as_completed(future_to_idx):
                i = future_to_idx[future]
                line = lines[i]
                try:
                    result = future.result(timeout=20)
                    if result:
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
        params = (None, None, speed, 100, pitch)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_info = {}
            for idx, (orig_idx, orig_text, conv_text) in enumerate(converted):
                future = executor.submit(
                    generate_single_audio, conv_text, voice_value, output_dir,
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
                st.audio(f.read(), format="audio/wav")
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
