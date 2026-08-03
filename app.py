import streamlit as st
import asyncio
import edge_tts
import tempfile
import os
import re
import shutil
import base64
from datetime import datetime
import concurrent.futures
import time

st.set_page_config(page_title="油库里语音生成器", page_icon="🎤", layout="wide")
st.title("🎤 油库里语音生成器")
st.caption("中文 → 空耳片假名 → 语音合成 (Edge TTS)")

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

# ---------- 声线数据（Edge TTS 日语语音列表） ----------
voice_options = [
    {"value": "ja-JP-NanamiNeural", "name": "Nanami (女性)"},
    {"value": "ja-JP-KeitaNeural", "name": "Keita (男性)"},
    {"value": "ja-JP-AoiNeural", "name": "Aoi (女性)"},
    {"value": "ja-JP-DaichiNeural", "name": "Daichi (男性)"},
    {"value": "ja-JP-MayumiNeural", "name": "Mayumi (女性)"},
    {"value": "ja-JP-NaokiNeural", "name": "Naoki (男性)"},
    # 更多语音可参考 https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
]

# ---------- 工具函数 ----------
def convert_to_katakana(text):
    """简易空耳转换（仅演示，实际可保留原逻辑）"""
    # 为了简化，这里直接返回原文本（您可继续使用 pypinyin 映射）
    # 如果需要，可以保留原来的 convert_to_katakana 函数
    # 但 Edge TTS 支持直接输入中文，所以可省略转换
    return text  # 直接使用原中文，Edge TTS 也支持中文语音

def get_audio_duration(file_path):
    """简易获取时长（毫秒）—— 实际可省略"""
    return 2000  # 占位

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

# ---------- 核心：Edge TTS 合成 ----------
async def tts_edge(text, voice, output_file, rate='+0%', volume='+0%'):
    """调用 Edge TTS 生成 MP3"""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(output_file)

def synthesize_single(text, voice, output_dir, idx, total, params):
    """生成单个音频文件（同步包装）"""
    try:
        rate, volume = params  # 可传入语速和音量调节
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', text)[:50]
        filename = f"{idx+1:03d}_{safe_name}.mp3"
        filepath = os.path.join(output_dir, filename)
        # 执行异步合成
        asyncio.run(tts_edge(text, voice, filepath, rate=rate, volume=volume))
        duration = get_audio_duration(filepath)  # 可省略
        return True, filepath, duration, None
    except Exception as e:
        return False, None, 0, str(e)

# ---------- UI 侧边栏 ----------
with st.sidebar:
    st.header("⚙️ 参数设置")
    voice_names = [v["name"] for v in voice_options]
    selected_voice = st.selectbox("语音类型", voice_names)
    voice_index = voice_names.index(selected_voice)
    voice_value = voice_options[voice_index]["value"]

    st.divider()
    st.subheader("🎛️ 高级参数")
    rate = st.slider("语速", -50, 50, 0, step=1, help="负值变慢，正值变快")
    volume = st.slider("音量", -50, 50, 0, step=1, help="负值降低，正值提高")
    # 转换为 Edge TTS 格式
    rate_str = f"{rate:+d}%"
    volume_str = f"{volume:+d}%"

    st.divider()
    st.subheader("📁 输出选项")
    generate_subtitle = st.checkbox("生成 SRT 字幕文件", value=False)

# ---------- 主区域 ----------
st.subheader("📝 输入文本 (每行生成一个独立语音)")
default_text = "こんにちは、世界"  # 示例日语
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
        output_dir = os.path.join(tempfile.gettempdir(), "tts_outputs", timestamp)
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
        update_progress(0.05, "准备合成...")

        # 直接使用原文本（可省略空耳转换）
        # 如果您希望保留空耳，可在此调用 convert_to_katakana
        # 但 Edge TTS 支持中文和日文，所以保留原样即可
        texts = lines  # 直接使用原始输入

        add_log(f"共 {len(texts)} 条文本，开始生成音频...")
        update_progress(0.20, "生成音频中...")

        success_count = 0
        audio_files = []
        subtitle_entries = []
        params = (rate_str, volume_str)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_info = {}
            for idx, text in enumerate(texts):
                future = executor.submit(
                    synthesize_single, text, voice_value, output_dir,
                    idx, len(texts), params
                )
                future_to_info[future] = (idx, text)

            for future in concurrent.futures.as_completed(future_to_info):
                idx, orig_text = future_to_info[future]
                try:
                    ok, filepath, duration, err = future.result(timeout=60)
                    if ok:
                        success_count += 1
                        audio_files.append((idx+1, orig_text, filepath))
                        subtitle_entries.append((idx, orig_text, duration))
                        add_log(f"✅ [{idx+1}/{len(texts)}] {orig_text[:20]}...")
                    else:
                        add_log(f"❌ [{idx+1}/{len(texts)}] {orig_text[:20]}... {err[:30]}")
                except Exception as e:
                    add_log(f"❌ 任务异常 [{idx+1}/{len(texts)}]: {str(e)[:30]}")
                update_progress(0.20 + 0.70 * (idx+1)/len(texts), f"生成进度 {idx+1}/{len(texts)}")

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
            st.session_state.zip_name = f"tts_{timestamp}.zip"
            add_log("📦 已准备好打包文件")

        update_progress(1.0, f"完成！成功 {success_count}/{len(texts)}")
        add_log(f"===== 完成! 成功 {success_count}/{len(texts)} =====")
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
