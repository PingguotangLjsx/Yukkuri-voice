import sys
import os
import random
import concurrent.futures
import threading
import math

# 静默检查并导入必要的模块
try:
    from bs4 import BeautifulSoup
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from bs4 import BeautifulSoup
    except Exception:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("无法导入 BeautifulSoup4，程序将退出")
            sys.exit(1)

try:
    import requests
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import requests
    except Exception:
        try:
            import requests
        except ImportError:
            print("无法导入 requests，程序将退出")
            sys.exit(1)

# 导入customtkinter用于现代化UI
try:
    import customtkinter as ctk
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import customtkinter as ctk
    except Exception:
        try:
            import customtkinter as ctk
        except ImportError:
            import tkinter as tk
            from tkinter import ttk, messagebox, scrolledtext
            ctk = None

if ctk is None:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext

import re
import json
from urllib.parse import quote
from datetime import datetime
import time
import wave
import numpy as np
import io

# 添加资源路径处理函数
def resource_path(relative_path):
    """获取资源的绝对路径，适用于开发和PyInstaller打包后"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# 获取应用程序根目录
def get_app_root():
    """获取应用程序根目录，适用于开发和PyInstaller打包后"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(".")

def get_ffmpeg_path():
    """获取 ffmpeg 可执行文件路径"""
    import shutil

    # 优先检查程序目录下的 ffmpeg.exe
    app_root = get_app_root()
    local_ffmpeg = os.path.join(app_root, 'ffmpeg.exe')
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    # 检查程序目录下的 ffmpeg 子目录
    ffmpeg_subdir = os.path.join(app_root, 'ffmpeg', 'ffmpeg.exe')
    if os.path.exists(ffmpeg_subdir):
        return ffmpeg_subdir

    # 检查系统 PATH 中是否有 ffmpeg
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path

    # 检查常见的安装路径
    common_paths = [
        r'G:\ffmpeg-2025-12-22-git-c50e5c7778-full_build\bin\ffmpeg.exe',
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    return None

def log_error(error_message):
    """记录错误到日志文件"""
    try:
        error_log_path = os.path.join(get_app_root(), "error_log.txt")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()}: {error_message}\n")
    except Exception as e:
        print(f"无法写入错误日志: {e}")

def change_pitch_audio(audio_data, sample_rate, pitch_factor):
    """
    调整音频音程（音高）- 核心算法
    使用线性插值算法改变音频播放速度，从而调整音高
    
    Args:
        audio_data: 音频数据（字节串）
        sample_rate: 采样率（Hz）
        pitch_factor: 音程调整因子 (0-300，100为原音)
                       <100: 降低音高，>100: 提高音高
    
    Returns:
        调整后的音频数据（字节串）
    """
    try:
        if pitch_factor == 100:
            return audio_data  # 100% 不做调整

        # 将字节数据转换为numpy数组
        if isinstance(audio_data, bytes):
            # 假设是16位PCM音频
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
        else:
            # 如果已经是数组，直接使用
            audio_array = audio_data

        # 计算调整后的长度
        original_length = len(audio_array)
        new_length = int(original_length * (100 / pitch_factor))

        # 创建调整后的数组
        new_audio = np.zeros(new_length, dtype=np.int16)

        # 简单的音高调整算法：通过插值改变播放速度
        for i in range(new_length):
            # 计算原始位置
            original_pos = i * (pitch_factor / 100)

            if original_pos < original_length - 1:
                # 线性插值
                lower = int(original_pos)
                upper = lower + 1
                weight = original_pos - lower

                new_audio[i] = int(audio_array[lower] * (1 - weight) + audio_array[upper] * weight)
            elif original_pos < original_length:
                # 最后一个样本
                new_audio[i] = audio_array[int(original_pos)]

        # 将numpy数组转换回字节
        return new_audio.tobytes()
    except Exception as e:
        log_error(f"调整音程时出错: {str(e)}")
        return audio_data





class ModernVoiceSynthesisApp:
    """
    油库里语音生成器主应用类
    功能：
    1. 支持中文转片假名（空耳模式）
    2. 支持中文转日语翻译（翻译模式）
    3. 多种语音类型选择
    4. 高级参数调整（效果、捧读、速度、音量、音程）
    5. 收藏功能，保存常用配置
    6. 并发处理，提高生成效率
    7. 音程调整功能（0-300范围）
    """
    
    def __init__(self, root):
        """
        初始化应用
        Args:
            root: tkinter根窗口对象
        """
        self.root = root

        # 配置customtkinter
        ctk.set_appearance_mode("System")  # 跟随系统主题
        ctk.set_default_color_theme("blue")  # 蓝色主题

        self.root.title("油库里语音生成器")
        self.root.geometry("1100x800")
        self.root.minsize(1000, 750)

        # 设置窗口图标（如果有）
        try:
            icon_path = resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            log_error(f"设置图标时出错: {str(e)}")

        # 声线列表 - 与您提供的select选项对应
        self.voice_options = [
            {"value": "aqtk1-f1", "name": "语音类型：AT1-F1"},
            {"value": "aqtk1-f2", "name": "语音类型：AT1-F2"},
            {"value": "aqtk1-m1", "name": "语音类型：AT1-M1"},
            {"value": "aqtk1-m2", "name": "语音类型：AT1-M2"},
            {"value": "aqtk1-dvd", "name": "语音类型：AT1-DVD"},
            {"value": "aqtk1-imd1", "name": "语音类型：AT1-IMD1"},
            {"value": "aqtk1-jgr", "name": "语音类型：AT1-JGR"},
            {"value": "aqtk1-r1", "name": "语音类型：AT1-R1"},
            {"value": "aqtk2-rm", "name": "语音类型：AT2-RM"},
            {"value": "aqtk2-f1c", "name": "语音类型：AT2-F1C"},
            {"value": "aqtk2-f3a", "name": "语音类型：AT2-RM"},
            {"value": "aqtk2-huskey", "name": "语音类型：AT2-HUSKEY"},
            {"value": "aqtk2-m4b", "name": "语音类型：AT2-M4B"},
            {"value": "aqtk2-mf1", "name": "语音类型：AT2-MF1"},
            {"value": "aqtk2-rb2", "name": "语音类型：AT2-RB2"},
            {"value": "aqtk2-rb3", "name": "语音类型：AT2-RB3"},
            {"value": "aqtk2-robo", "name": "语音类型：AT2-ROBO"},
            {"value": "aqtk2-yukkuri", "name": "语音类型：AT2-YUKKURI"},
            {"value": "aqtk2-f4", "name": "语音类型：AT2-F4"},
            {"value": "aqtk2-m5", "name": "语音类型：AT2-M5"},
            {"value": "aqtk2-mf2", "name": "语音类型：AT2-MF2"},
            {"value": "aqtk2-rm3", "name": "语音类型：AT2-RM3"},
            {"value": "aqtk10-f1", "name": "语音类型：AT10-F1"},
            {"value": "aqtk10-f2", "name": "语音类型：AT10-F2"},
            {"value": "aqtk10-f3", "name": "语音类型：AT10-F3"},
            {"value": "aqtk10-m1", "name": "语音类型：AT10-M1"},
            {"value": "aqtk10-m2", "name": "语音类型：AT10-M2"},
            {"value": "aqtk10-r1", "name": "语音类型：AT10-R1"},
            {"value": "aqtk10-r2", "name": "语音类型：AT10-R2"}
        ]

        # API模板 - 与您提供的API列表对应
        self.api_templates = [
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

        # 收藏备注列表 - 修改为保存在软件根目录
        self.favorites = []
        app_root = get_app_root()
        self.favorites_file = os.path.join(app_root, "favorites.json")
        self.load_favorites()

        # 高级参数默认值
        self.effect_var = ctk.StringVar(value="none")  # 效果: none或echo
        self.boyomi_var = ctk.BooleanVar(value=False)  # 捧读: false或true
        self.speed_var = ctk.IntVar(value=100)  # 速度: 50-300，默认改为100
        self.volume_var = ctk.IntVar(value=100)  # 音量: 10-200
        self.pitch_var = ctk.IntVar(value=100)  # 音程: 0-300，默认100

        # 字幕生成选项
        self.generate_subtitle_var = ctk.BooleanVar(value=False)  # 是否生成srt字幕文件

        # 并发数设置
        self.convert_concurrent_var = ctk.IntVar(value=3)
        self.generate_concurrent_var = ctk.IntVar(value=5)
        self.unlimited_concurrent_var = ctk.BooleanVar(value=False)  # 无限制并发

        # 转换模式设置
        self.convert_mode_var = ctk.StringVar(value="空耳")  # 转换模式：空耳或日语翻译

        # 进程控制
        self.is_processing = False  # 是否正在处理
        self.current_executor = None  # 当前线程池执行器

        # 收藏锁定状态 - 当使用收藏方案时锁定高级参数
        self.favorite_locked = False  # 是否锁定高级参数
        self.current_favorite = None  # 当前使用的收藏对象
        self.selected_favorite_index = -1  # 当前选中的收藏项索引（用于删除）
        self.favorite_buttons = []  # 收藏项按钮列表

        # 创建UI元素
        self.create_widgets()

        # 处理关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    

    def process_audio_pitch_in_memory(self, audio_data, pitch_factor):
        """
        在内存中处理音频音程调整（用于语音生成）
        audio_data: 原始音频数据（通常是MP3格式）
        pitch_factor: 音程调整因子 (0-300，100为原音)
        返回: 调整后的音频数据（MP3格式）
        """
        temp_files = []
        try:
            import tempfile
            import subprocess
            import wave
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_input:
                temp_input.write(audio_data)
                temp_input_path = temp_input.name
                temp_files.append(temp_input_path)
            
            # 使用ffmpeg转换为WAV
            temp_wav_path = tempfile.mktemp(suffix='.wav')
            temp_files.append(temp_wav_path)

            ffmpeg_path = get_ffmpeg_path()
            if not ffmpeg_path:
                log_error("未找到 ffmpeg，无法调整音程")
                return None

            cmd = [
                ffmpeg_path,
                '-i', temp_input_path,
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '1',
                '-y',
                temp_wav_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                log_error(f"FFmpeg转换失败: {result.stderr}")
                return None
            
            # 读取WAV文件并调整音程
            with wave.open(temp_wav_path, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                frames = wav_file.readframes(-1)
            
            # 调整音程
            adjusted_audio = change_pitch_audio(frames, sample_rate, pitch_factor)
            
            # 保存调整后的音频并转换回MP3
            temp_adjusted_wav = tempfile.mktemp(suffix='.wav')
            temp_files.append(temp_adjusted_wav)
            
            with wave.open(temp_adjusted_wav, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(adjusted_audio)
            
            # 转换回MP3
            temp_output_mp3 = tempfile.mktemp(suffix='.mp3')
            temp_files.append(temp_output_mp3)

            cmd = [
                ffmpeg_path,
                '-i', temp_adjusted_wav,
                '-acodec', 'libmp3lame',
                '-ab', '64k',
                '-y',
                temp_output_mp3
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                log_error(f"MP3转换失败: {result.stderr}")
                return None
            
            # 读取处理后的音频数据
            with open(temp_output_mp3, 'rb') as f:
                return f.read()
                
        except Exception as e:
            log_error(f"内存音程处理失败: {str(e)}")
            return None
        finally:
            # 清理临时文件
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    log_error(f"清理临时文件失败: {e}")

    def on_closing(self):
        """处理窗口关闭事件"""
        # 停止所有正在进行的处理
        self.stop_processing()
        self.save_favorites()
        self.root.destroy()

    def stop_processing(self):
        """停止所有处理"""
        self.is_processing = False
        if self.current_executor:
            self.current_executor.shutdown(wait=False)
        self.generate_btn.configure(state="normal")
        self.progress.stop()
        self.status_var.set("处理已停止")

    def load_favorites(self):
        """加载收藏列表"""
        try:
            if os.path.exists(self.favorites_file):
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
            else:
                self.favorites = []
        except Exception as e:
            log_error(f"加载收藏列表时出错: {str(e)}")
            self.favorites = []

    def save_favorites(self):
        """保存收藏列表"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_error(f"保存收藏列表时出错: {str(e)}")

    def create_widgets(self):
        # 创建主框架
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=10)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 标题
        title_label = ctk.CTkLabel(
            self.main_frame,
            text="油库里语音生成器",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(15, 10))

        # 创建选项卡视图
        self.tabview = ctk.CTkTabview(self.main_frame, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # 添加选项卡
        self.tab1 = self.tabview.add("文本输入")
        self.tab2 = self.tabview.add("语音设置")
        self.tab3 = self.tabview.add("高级参数")
        self.tab4 = self.tabview.add("并发设置")

        # 配置选项卡权重
        self.tab1.grid_columnconfigure(0, weight=1)
        self.tab1.grid_rowconfigure(1, weight=1)

        self.tab2.grid_columnconfigure(0, weight=1)
        self.tab2.grid_rowconfigure(1, weight=1)

        self.tab3.grid_columnconfigure(0, weight=1)
        self.tab4.grid_columnconfigure(0, weight=1)

        # 选项卡1：文本输入
        self.create_tab1()

        # 选项卡2：语音设置
        self.create_tab2()

        # 选项卡3：高级参数
        self.create_tab3()

        # 选项卡4：并发设置
        self.create_tab4()

        # 底部状态栏和操作按钮
        self.create_bottom_bar()

    def create_tab1(self):
        """创建文本输入选项卡"""
        # 转换模式选择
        mode_label = ctk.CTkLabel(
            self.tab1,
            text="转换模式:",
            font=ctk.CTkFont(weight="bold")
        )
        mode_label.grid(row=0, column=0, sticky="w", pady=(5, 5))

        mode_frame = ctk.CTkFrame(self.tab1, fg_color="transparent")
        mode_frame.grid(row=1, column=0, sticky="w", pady=(0, 10))

        # 创建转换模式选项
        self.convert_mode_var = ctk.StringVar(value="空耳")

        mode_katakana = ctk.CTkRadioButton(
            mode_frame,
            text="中文空耳 (转换为片假名)",
            variable=self.convert_mode_var,
            value="空耳",
            font=ctk.CTkFont(size=12)
        )
        mode_katakana.grid(row=0, column=0, sticky="w", padx=(0, 20))

        mode_translate = ctk.CTkRadioButton(
            mode_frame,
            text="中文转日文 (翻译为日语)",
            variable=self.convert_mode_var,
            value="翻译",
            font=ctk.CTkFont(size=12)
        )
        mode_translate.grid(row=0, column=1, sticky="w")

        # 文本输入标签
        text_label = ctk.CTkLabel(
            self.tab1,
            text="请输入文本 (每行将生成单独的语音):",
            font=ctk.CTkFont(weight="bold")
        )
        text_label.grid(row=2, column=0, sticky="w", pady=(10, 5))

        # 文本输入框
        self.text_input = ctk.CTkTextbox(
            self.tab1,
            height=200,
            wrap="word",
            border_width=1,
            corner_radius=5
        )
        self.text_input.grid(row=3, column=0, sticky="nsew", pady=(0, 10))

        # 快速操作按钮
        button_frame = ctk.CTkFrame(self.tab1, fg_color="transparent")
        button_frame.grid(row=4, column=0, sticky="ew", pady=5)
        button_frame.grid_columnconfigure((0, 1), weight=1)

        clear_btn = ctk.CTkButton(
            button_frame,
            text="清空文本",
            command=self.clear_text,
            width=100
        )
        clear_btn.grid(row=0, column=0, padx=5)

        count_btn = ctk.CTkButton(
            button_frame,
            text="统计行数",
            command=self.count_lines,
            width=100
        )
        count_btn.grid(row=0, column=1, padx=5)

        # 字幕生成选项
        self.subtitle_checkbox = ctk.CTkCheckBox(
            self.tab1,
            text="自动生成SRT字幕文件",
            variable=self.generate_subtitle_var,
            onvalue=True,
            offvalue=False
        )
        self.subtitle_checkbox.grid(row=5, column=0, sticky="w", pady=10)

    def create_tab2(self):
        """创建语音设置选项卡"""
        # 声线选择
        voice_label = ctk.CTkLabel(
            self.tab2,
            text="选择语音类型:",
            font=ctk.CTkFont(weight="bold")
        )
        voice_label.grid(row=0, column=0, sticky="w", pady=(5, 5))

        self.voice_var = ctk.StringVar()
        # 获取所有语音选项（包括收藏）
        all_voice_options = self.get_all_voice_options()
        self.voice_combo = ctk.CTkComboBox(
            self.tab2,
            variable=self.voice_var,
            state="readonly",
            values=[opt["display_name"] for opt in all_voice_options],
            command=self.on_voice_selected
        )
        self.voice_combo.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        if all_voice_options:
            self.voice_combo.set(all_voice_options[0]["display_name"])

        # 收藏管理
        favorite_label = ctk.CTkLabel(
            self.tab2,
            text="收藏管理:",
            font=ctk.CTkFont(weight="bold")
        )
        favorite_label.grid(row=2, column=0, sticky="w", pady=(10, 5))

        favorite_frame = ctk.CTkFrame(self.tab2, fg_color="transparent")
        favorite_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        favorite_frame.grid_columnconfigure(0, weight=1)

        note_label = ctk.CTkLabel(favorite_frame, text="备注:")
        note_label.grid(row=0, column=0, sticky="w", padx=(0, 5))

        self.note_var = ctk.StringVar()
        self.note_entry = ctk.CTkEntry(
            favorite_frame,
            textvariable=self.note_var,
            placeholder_text="输入收藏备注"
        )
        self.note_entry.grid(row=0, column=1, sticky="ew", padx=5)

        self.add_favorite_btn = ctk.CTkButton(
            favorite_frame,
            text="添加收藏",
            command=self.add_favorite,
            width=100
        )
        self.add_favorite_btn.grid(row=0, column=2, padx=5)

        self.delete_favorite_btn = ctk.CTkButton(
            favorite_frame,
            text="删除选中",
            command=self.delete_selected_favorite,
            width=100,
            fg_color="#F44336",
            hover_color="#D32F2F"
        )
        self.delete_favorite_btn.grid(row=0, column=3, padx=5)

        # 收藏列表
        favorite_list_label = ctk.CTkLabel(
            self.tab2,
            text="我的收藏 (点击选择):",
            font=ctk.CTkFont(weight="bold")
        )
        favorite_list_label.grid(row=4, column=0, sticky="w", pady=(10, 5))

        # 使用ScrollableFrame替代Textbox，支持点击选择
        self.favorite_scroll_frame = ctk.CTkScrollableFrame(
            self.tab2,
            height=120,
            label_text=""
        )
        self.favorite_scroll_frame.grid(row=5, column=0, sticky="nsew", pady=(0, 10))

        # 添加容器用于存放收藏项按钮
        self.favorite_items_frame = self.favorite_scroll_frame

        # 记录当前选中的收藏项索引
        self.selected_favorite_index = -1

        # 初始化收藏项按钮列表
        self.favorite_buttons = []

        # 更新收藏列表显示
        self.update_favorite_list()

    def get_all_voice_options(self):
        """获取所有语音选项（包括收藏和预设）"""
        all_options = []

        # 添加预设语音选项
        for voice in self.voice_options:
            all_options.append({
                "type": "preset",
                "display_name": voice["name"],
                "value": voice["value"],
                "name": voice["name"]
            })

        # 添加收藏选项
        for i, fav in enumerate(self.favorites):
            all_options.append({
                "type": "favorite",
                "display_name": f"★ {fav['name']}",
                "value": fav["value"],
                "name": fav["name"],
                "params": fav.get("params", {})
            })

        return all_options

    def create_tab3(self):
        """创建高级参数选项卡"""
        # 效果设置
        effect_label = ctk.CTkLabel(
            self.tab3,
            text="音效:",
            font=ctk.CTkFont(weight="bold")
        )
        effect_label.grid(row=0, column=0, sticky="w", pady=(5, 5))

        effect_frame = ctk.CTkFrame(self.tab3, fg_color="transparent")
        effect_frame.grid(row=1, column=0, sticky="ew", pady=5)

        self.none_effect = ctk.CTkRadioButton(
            effect_frame,
            text="无效果",
            variable=self.effect_var,
            value="none",
            command=self.on_effect_changed
        )
        self.none_effect.grid(row=0, column=0, sticky="w", padx=5)

        self.echo_effect = ctk.CTkRadioButton(
            effect_frame,
            text="回声效果",
            variable=self.effect_var,
            value="echo",
            command=self.on_effect_changed
        )
        self.echo_effect.grid(row=0, column=1, sticky="w", padx=5)

        # 捧读设置
        boyomi_label = ctk.CTkLabel(
            self.tab3,
            text="捧读:",
            font=ctk.CTkFont(weight="bold")
        )
        boyomi_label.grid(row=2, column=0, sticky="w", pady=(15, 5))

        boyomi_frame = ctk.CTkFrame(self.tab3, fg_color="transparent")
        boyomi_frame.grid(row=3, column=0, sticky="ew", pady=5)

        self.boyomi_off = ctk.CTkRadioButton(
            boyomi_frame,
            text="OFF",
            variable=self.boyomi_var,
            value=False,
            command=self.on_boyomi_changed
        )
        self.boyomi_off.grid(row=0, column=0, sticky="w", padx=5)

        self.boyomi_on = ctk.CTkRadioButton(
            boyomi_frame,
            text="ON",
            variable=self.boyomi_var,
            value=True,
            command=self.on_boyomi_changed
        )
        self.boyomi_on.grid(row=0, column=1, sticky="w", padx=5)

        # 速度设置
        speed_label = ctk.CTkLabel(
            self.tab3,
            text="速度 (50-300):",
            font=ctk.CTkFont(weight="bold")
        )
        speed_label.grid(row=4, column=0, sticky="w", pady=(15, 5))

        speed_frame = ctk.CTkFrame(self.tab3, fg_color="transparent")
        speed_frame.grid(row=5, column=0, sticky="ew", pady=5)
        speed_frame.grid_columnconfigure(0, weight=1)

        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=50,
            to=300,
            number_of_steps=250,
            variable=self.speed_var,
            command=self.on_speed_changed
        )
        self.speed_slider.grid(row=0, column=0, sticky="ew", padx=5)

        self.speed_value_label = ctk.CTkLabel(speed_frame, text="100")
        self.speed_value_label.grid(row=0, column=1, padx=5)

        # 音量设置
        volume_label = ctk.CTkLabel(
            self.tab3,
            text="音量 (10-200):",
            font=ctk.CTkFont(weight="bold")
        )
        volume_label.grid(row=6, column=0, sticky="w", pady=(15, 5))

        volume_frame = ctk.CTkFrame(self.tab3, fg_color="transparent")
        volume_frame.grid(row=7, column=0, sticky="ew", pady=5)
        volume_frame.grid_columnconfigure(0, weight=1)

        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=10,
            to=200,
            number_of_steps=190,
            variable=self.volume_var,
            command=self.on_volume_changed
        )
        self.volume_slider.grid(row=0, column=0, sticky="ew", padx=5)

        self.volume_value_label = ctk.CTkLabel(volume_frame, text="100")
        self.volume_value_label.grid(row=0, column=1, padx=5)

        # 音程设置
        pitch_label = ctk.CTkLabel(
            self.tab3,
            text="音程 (0-300):",
            font=ctk.CTkFont(weight="bold")
        )
        pitch_label.grid(row=8, column=0, sticky="w", pady=(15, 5))

        pitch_frame = ctk.CTkFrame(self.tab3, fg_color="transparent")
        pitch_frame.grid(row=9, column=0, sticky="ew", pady=5)
        pitch_frame.grid_columnconfigure(0, weight=1)

        self.pitch_slider = ctk.CTkSlider(
            pitch_frame,
            from_=0,
            to=300,
            number_of_steps=300,
            variable=self.pitch_var,
            command=self.on_pitch_changed
        )
        self.pitch_slider.grid(row=0, column=0, sticky="ew", padx=5)

        self.pitch_value_label = ctk.CTkLabel(pitch_frame, text="100")
        self.pitch_value_label.grid(row=0, column=1, padx=5)

        # 重置按钮
        self.reset_btn = ctk.CTkButton(
            self.tab3,
            text="重置为默认值",
            command=self.reset_advanced_params,
            width=120
        )
        self.reset_btn.grid(row=10, column=0, pady=20)

    def create_tab4(self):
        """创建并发设置选项卡"""
        # 并发设置
        concurrent_label = ctk.CTkLabel(
            self.tab4,
            text="并发设置:",
            font=ctk.CTkFont(weight="bold")
        )
        concurrent_label.grid(row=0, column=0, sticky="w", pady=(5, 10))

        # 转换并发数
        convert_frame = ctk.CTkFrame(self.tab4, fg_color="transparent")
        convert_frame.grid(row=1, column=0, sticky="ew", pady=5)
        convert_frame.grid_columnconfigure(1, weight=1)

        convert_label = ctk.CTkLabel(convert_frame, text="转换并发数:")
        convert_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.convert_concurrent_slider = ctk.CTkSlider(
            convert_frame,
            from_=1,
            to=30,  # 最高30
            number_of_steps=29,
            variable=self.convert_concurrent_var,
            command=self.on_convert_slider_changed
        )
        self.convert_concurrent_slider.grid(row=0, column=1, sticky="ew", padx=5)

        self.convert_value_label = ctk.CTkLabel(convert_frame, text="3")
        self.convert_value_label.grid(row=0, column=2, padx=5)

        # 生成并发数
        generate_frame = ctk.CTkFrame(self.tab4, fg_color="transparent")
        generate_frame.grid(row=2, column=0, sticky="ew", pady=5)
        generate_frame.grid_columnconfigure(1, weight=1)

        generate_label = ctk.CTkLabel(generate_frame, text="生成并发数:")
        generate_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.generate_concurrent_slider = ctk.CTkSlider(
            generate_frame,
            from_=1,
            to=30,  # 最高30
            number_of_steps=29,
            variable=self.generate_concurrent_var,
            command=self.on_generate_slider_changed
        )
        self.generate_concurrent_slider.grid(row=0, column=1, sticky="ew", padx=5)

        self.generate_value_label = ctk.CTkLabel(generate_frame, text="5")
        self.generate_value_label.grid(row=0, column=2, padx=5)

        # 无限制并发选项
        unlimited_frame = ctk.CTkFrame(self.tab4, fg_color="transparent")
        unlimited_frame.grid(row=3, column=0, sticky="ew", pady=10)

        self.unlimited_checkbox = ctk.CTkCheckBox(
            unlimited_frame,
            text="无限制并发 (自动根据行数调节)",
            variable=self.unlimited_concurrent_var,
            onvalue=True,
            offvalue=False,
            command=self.on_unlimited_changed
        )
        self.unlimited_checkbox.grid(row=0, column=0, sticky="w")

        # 主题设置
        theme_label = ctk.CTkLabel(
            self.tab4,
            text="界面主题:",
            font=ctk.CTkFont(weight="bold")
        )
        theme_label.grid(row=4, column=0, sticky="w", pady=(20, 10))

        theme_frame = ctk.CTkFrame(self.tab4, fg_color="transparent")
        theme_frame.grid(row=5, column=0, sticky="ew", pady=5)

        self.theme_var = ctk.StringVar(value="System")
        system_theme = ctk.CTkRadioButton(
            theme_frame,
            text="跟随系统",
            variable=self.theme_var,
            value="System",
            command=self.change_theme
        )
        system_theme.grid(row=0, column=0, sticky="w", padx=5)

        light_theme = ctk.CTkRadioButton(
            theme_frame,
            text="浅色模式",
            variable=self.theme_var,
            value="Light",
            command=self.change_theme
        )
        light_theme.grid(row=0, column=1, sticky="w", padx=5)

        dark_theme = ctk.CTkRadioButton(
            theme_frame,
            text="深色模式",
            variable=self.theme_var,
            value="Dark",
            command=self.change_theme
        )
        dark_theme.grid(row=0, column=2, sticky="w", padx=5)

    def create_bottom_bar(self):
        """创建底部状态栏和操作按钮"""
        bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=10, pady=10)

        # 状态信息
        self.status_var = ctk.StringVar(value="就绪")
        status_label = ctk.CTkLabel(
            bottom_frame,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=12)
        )
        status_label.pack(side="left", padx=5)

        # 进度条
        self.progress = ctk.CTkProgressBar(bottom_frame, mode='indeterminate')
        self.progress.pack(side="left", fill="x", expand=True, padx=10)
        self.progress.set(0)

        # 操作按钮
        button_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        button_frame.pack(side="right", padx=5)

        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="停止处理",
            command=self.stop_processing,
            width=80,
            fg_color="#F44336",
            hover_color="#D32F2F",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)

        self.generate_btn = ctk.CTkButton(
            button_frame,
            text="开始生成",
            command=self.start_process,
            height=35,
            font=ctk.CTkFont(weight="bold")
        )
        self.generate_btn.pack(side="left", padx=5)

    def on_speed_changed(self, value):
        """速度滑块变化事件"""
        if self.favorite_locked:
            # 阻止调整并提示用户
            self.speed_var.set(self.current_favorite["params"]["speed"])
            self.speed_value_label.configure(text=str(self.current_favorite["params"]["speed"]))
            self.show_message("提示", "当前使用收藏方案，高级参数已锁定。\n如需调整参数，请切换到其他音色。")
            return
        self.speed_value_label.configure(text=str(int(value)))

    def on_volume_changed(self, value):
        """音量滑块变化事件"""
        if self.favorite_locked:
            # 阻止调整并提示用户
            self.volume_var.set(self.current_favorite["params"]["volume"])
            self.volume_value_label.configure(text=str(self.current_favorite["params"]["volume"]))
            self.show_message("提示", "当前使用收藏方案，高级参数已锁定。\n如需调整参数，请切换到其他音色。")
            return
        self.volume_value_label.configure(text=str(int(value)))

    def on_pitch_changed(self, value):
        """音程滑块变化事件"""
        if self.favorite_locked:
            # 阻止调整并提示用户
            self.pitch_var.set(self.current_favorite["params"]["pitch"])
            self.pitch_value_label.configure(text=str(self.current_favorite["params"]["pitch"]))
            self.show_message("提示", "当前使用收藏方案，高级参数已锁定。\n如需调整参数，请切换到其他音色。")
            return
        self.pitch_value_label.configure(text=str(int(value)))

    def on_effect_changed(self):
        """效果单选按钮变化事件"""
        if self.favorite_locked:
            # 阻止调整并提示用户
            self.effect_var.set(self.current_favorite["params"]["effect"])
            self.show_message("提示", "当前使用收藏方案，高级参数已锁定。\n如需调整参数，请切换到其他音色。")

    def on_boyomi_changed(self):
        """捧读单选按钮变化事件"""
        if self.favorite_locked:
            # 阻止调整并提示用户
            self.boyomi_var.set(self.current_favorite["params"]["boyomi"] == "true")
            self.show_message("提示", "当前使用收藏方案，高级参数已锁定。\n如需调整参数，请切换到其他音色。")

    def on_convert_slider_changed(self, value):
        """转换并发数滑块变化事件"""
        self.convert_value_label.configure(text=str(int(value)))

    def on_generate_slider_changed(self, value):
        """生成并发数滑块变化事件"""
        self.generate_value_label.configure(text=str(int(value)))

    def on_unlimited_changed(self):
        """无限制并发选项变化事件"""
        if self.unlimited_concurrent_var.get():
            # 禁用滑块
            self.convert_concurrent_slider.configure(state="disabled")
            self.generate_concurrent_slider.configure(state="disabled")
            self.convert_value_label.configure(text="自动")
            self.generate_value_label.configure(text="自动")
        else:
            # 启用滑块
            self.convert_concurrent_slider.configure(state="normal")
            self.generate_concurrent_slider.configure(state="normal")
            self.convert_value_label.configure(text=str(self.convert_concurrent_var.get()))
            self.generate_value_label.configure(text=str(self.generate_concurrent_var.get()))

    def change_theme(self):
        """更改界面主题"""
        ctk.set_appearance_mode(self.theme_var.get())

    def reset_advanced_params(self):
        """重置高级参数为默认值"""
        if self.favorite_locked:
            # 如果锁定状态，阻止重置并提示用户
            self.show_message("提示", "当前使用收藏方案，高级参数已锁定。\n如需重置参数，请切换到其他音色。")
            return
        
        self.effect_var.set("none")
        self.boyomi_var.set(False)
        self.speed_var.set(100)  # 默认速度改为100
        self.volume_var.set(100)
        self.pitch_var.set(100)  # 默认音程改为100
        self.speed_value_label.configure(text="100")
        self.volume_value_label.configure(text="100")
        self.pitch_value_label.configure(text="100")
        self.show_message("成功", "高级参数已重置为默认值")

    def clear_text(self):
        """清空文本"""
        self.text_input.delete("1.0", "end")

    def count_lines(self):
        """统计文本行数"""
        text = self.text_input.get("1.0", "end").strip()
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 使用自定义对话框显示结果
        self.show_message("统计结果", f"文本共有 {len(lines)} 行")

    def on_voice_selected(self, choice):
        """
        语音类型选择事件处理
        功能：
        1. 如果选择收藏项（以★开头），自动应用收藏的参数并锁定
        2. 如果选择预设音色，解除参数锁定
        
        Args:
            choice: 用户选择的语音类型名称
        """
        if not choice:
            return

        # 检查是否是收藏项（收藏项以★开头）
        if choice.startswith("★"):
            # 查找对应的收藏
            for fav in self.favorites:
                if f"★ {fav['name']}" == choice:
                    # 应用收藏的高级参数
                    if "params" in fav:
                        params = fav["params"]
                        self.apply_advanced_params(params)
                    
                    # 锁定高级参数，防止用户误操作
                    self.favorite_locked = True
                    self.current_favorite = fav
                    self.lock_advanced_params()

                    # 找到对应的预设语音名称
                    for voice in self.voice_options:
                        if voice["value"] == fav["value"]:
                            self.show_message("提示", f"已加载收藏 '{fav['name']}'\n语音类型: {voice['name']}\n高级参数已锁定，如需调整请切换其他音色")
                            break
                    break
        else:
            # 选择预设音色时，解除锁定
            if self.favorite_locked:
                self.favorite_locked = False
                self.current_favorite = None
                self.unlock_advanced_params()

    def update_favorite_list(self):
        """更新收藏列表显示"""
        # 清除所有现有的收藏按钮
        for btn in self.favorite_buttons:
            btn.destroy()
        self.favorite_buttons.clear()

        if not self.favorites:
            # 显示"暂无收藏"提示
            no_fav_label = ctk.CTkLabel(
                self.favorite_items_frame,
                text="暂无收藏",
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "gray50")
            )
            no_fav_label.pack(pady=10)
            self.favorite_buttons.append(no_fav_label)
        else:
            # 为每个收藏创建可点击的按钮
            for i, fav in enumerate(self.favorites):
                # 显示收藏详细信息
                params = fav.get("params", {})
                params_text = f" 效果:{params.get('effect','none')} 捧读:{params.get('boyomi','false')} 速度:{params.get('speed',100)} 音量:{params.get('volume',100)} 音程:{params.get('pitch',100)}"
                display_text = f"{i+1}. {fav['name']}{params_text}"

                # 创建按钮
                fav_btn = ctk.CTkButton(
                    self.favorite_items_frame,
                    text=display_text,
                    fg_color="transparent",
                    text_color=("black", "white"),
                    hover_color=("gray80", "gray30"),
                    anchor="w",
                    height=40,
                    command=lambda idx=i: self._on_favorite_clicked(idx)
                )
                fav_btn.pack(fill="x", pady=2, padx=5)
                self.favorite_buttons.append(fav_btn)

                # 更新选中状态的显示
                if i == self.selected_favorite_index:
                    fav_btn.configure(fg_color=("gray70", "gray50"))
                else:
                    fav_btn.configure(fg_color="transparent")

    def _on_favorite_clicked(self, index):
        """
        处理收藏项点击事件
        
        参数:
            index: 被点击的收藏项索引
        """
        # 如果点击的是已经选中的，取消选中
        if self.selected_favorite_index == index:
            self.selected_favorite_index = -1
        else:
            # 选中新的收藏项
            self.selected_favorite_index = index

        # 更新所有按钮的显示状态
        for i, btn in enumerate(self.favorite_buttons):
            if isinstance(btn, ctk.CTkButton):
                if i == self.selected_favorite_index:
                    btn.configure(fg_color=("gray70", "gray50"))
                else:
                    btn.configure(fg_color="transparent")

    def get_current_advanced_params(self):
        """获取当前高级参数设置"""
        return {
            "effect": self.effect_var.get(),
            "boyomi": "true" if self.boyomi_var.get() else "false",
            "speed": self.speed_var.get(),
            "volume": self.volume_var.get(),
            "pitch": self.pitch_var.get()
        }

    def apply_advanced_params(self, params):
        """应用高级参数设置"""
        if params:
            self.effect_var.set(params.get("effect", "none"))
            self.boyomi_var.set(params.get("boyomi", "false") == "true")
            self.speed_var.set(params.get("speed", 100))
            self.volume_var.set(params.get("volume", 100))
            self.pitch_var.set(params.get("pitch", 100))
            self.speed_value_label.configure(text=str(self.speed_var.get()))
            self.volume_value_label.configure(text=str(self.volume_var.get()))
            self.pitch_value_label.configure(text=str(self.pitch_var.get()))

    def lock_advanced_params(self):
        """
        锁定高级参数控件
        用途：当使用收藏方案时，防止用户误修改参数
        锁定的控件：效果、捧读、速度、音量、音程、重置按钮
        """
        # 锁定效果单选按钮
        self.none_effect.configure(state="disabled")
        self.echo_effect.configure(state="disabled")
        
        # 锁定捧读单选按钮
        self.boyomi_off.configure(state="disabled")
        self.boyomi_on.configure(state="disabled")
        
        # 锁定滑块
        self.speed_slider.configure(state="disabled")
        self.volume_slider.configure(state="disabled")
        self.pitch_slider.configure(state="disabled")
        
        # 锁定重置按钮
        self.reset_btn.configure(state="disabled")
        
        # 添加锁定提示
        if hasattr(self, 'lock_label'):
            self.lock_label.configure(text="⚠️ 高级参数已锁定（当前使用收藏方案）")
        else:
            self.lock_label = ctk.CTkLabel(
                self.tab3,
                text="⚠️ 高级参数已锁定（当前使用收藏方案）",
                font=ctk.CTkFont(size=12),
                text_color=("gray10", "gray90")
            )
            self.lock_label.grid(row=11, column=0, sticky="w", pady=(10, 0))

    def unlock_advanced_params(self):
        """
        解锁高级参数控件
        用途：切换到预设音色时，允许用户自由调整参数
        """
        # 启用效果单选按钮
        self.none_effect.configure(state="normal")
        self.echo_effect.configure(state="normal")
        
        # 启用捧读单选按钮
        self.boyomi_off.configure(state="normal")
        self.boyomi_on.configure(state="normal")
        
        # 启用滑块
        self.speed_slider.configure(state="normal")
        self.volume_slider.configure(state="normal")
        self.pitch_slider.configure(state="normal")
        
        # 启用重置按钮
        self.reset_btn.configure(state="normal")
        
        # 移除锁定提示
        if hasattr(self, 'lock_label'):
            self.lock_label.grid_forget()
            delattr(self, 'lock_label')

    def add_favorite(self):
        """添加收藏（包含高级参数）"""
        note = self.note_var.get().strip()
        if not note:
            self.show_message("错误", "请输入备注", is_error=True)
            return

        selected_voice = self.voice_combo.get()
        if not selected_voice:
            self.show_message("错误", "请先选择语音类型", is_error=True)
            return

        # 获取语音值（判断是收藏还是预设）
        voice_value = None
        voice_display_name = None

        # 检查是否是收藏项
        if selected_voice.startswith("★"):
            # 从收藏中查找
            for fav in self.favorites:
                if f"★ {fav['name']}" == selected_voice:
                    voice_value = fav["value"]
                    # 查找对应的预设名称
                    for voice in self.voice_options:
                        if voice["value"] == voice_value:
                            voice_display_name = voice["name"]
                            break
                    break
        else:
            # 从预设中查找
            for voice in self.voice_options:
                if voice["name"] == selected_voice:
                    voice_value = voice["value"]
                    voice_display_name = voice["name"]
                    break

        if not voice_value:
            self.show_message("错误", "找不到对应的语音类型", is_error=True)
            return

        # 获取当前高级参数
        advanced_params = self.get_current_advanced_params()

        favorite = {
            "name": note,
            "value": voice_value,
            "display_name": voice_display_name or selected_voice,
            "params": advanced_params,
            "timestamp": datetime.now().isoformat()
        }

        self.favorites.insert(0, favorite)
        self.save_favorites()
        self.update_favorite_list()
        self.note_var.set("")

        # 更新语音选择下拉框
        all_voice_options = self.get_all_voice_options()
        self.voice_combo.configure(values=[opt["display_name"] for opt in all_voice_options])

        self.show_message("成功", "已添加到收藏")

    def delete_selected_favorite(self):
        """删除选中的收藏"""
        # 检查是否选中了收藏项
        if self.selected_favorite_index == -1:
            self.show_message("提示", "请先在收藏列表中点击选择要删除的收藏", is_error=True)
            return

        # 检查索引是否有效
        if self.selected_favorite_index >= len(self.favorites):
            self.show_message("错误", "选中的收藏不存在", is_error=True)
            self.selected_favorite_index = -1
            self.update_favorite_list()
            return

        favorite_index = self.selected_favorite_index
        favorite_name = self.favorites[favorite_index]['name']

        # 创建确认对话框
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("确认删除")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # 确认消息
        message_label = ctk.CTkLabel(
            dialog,
            text=f"确定要删除收藏 '{favorite_name}' 吗？\n此操作无法撤销。",
            font=ctk.CTkFont(size=14),
            wraplength=350
        )
        message_label.pack(pady=(30, 20))

        # 按钮框架
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)

        # 取消按钮
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="取消",
            width=100,
            command=dialog.destroy
        )
        cancel_btn.pack(side="left", padx=10)

        # 确认删除按钮
        confirm_btn = ctk.CTkButton(
            button_frame,
            text="确定删除",
            width=100,
            fg_color="#F44336",
            hover_color="#D32F2F",
            command=lambda: self._confirm_delete(favorite_index, dialog)
        )
        confirm_btn.pack(side="left", padx=10)

    def _confirm_delete(self, favorite_index, dialog):
        """确认删除收藏的内部方法"""
        # 删除收藏
        deleted_favorite = self.favorites.pop(favorite_index)
        self.save_favorites()
        
        # 重置选中状态
        self.selected_favorite_index = -1
        
        # 更新收藏列表显示
        self.update_favorite_list()

        # 更新语音选择下拉框
        all_voice_options = self.get_all_voice_options()
        self.voice_combo.configure(values=[opt["display_name"] for opt in all_voice_options])

        # 如果删除的是当前语音选择中的收藏，切换到第一个选项
        current_voice = self.voice_combo.get()
        if current_voice.startswith("★"):
            if all_voice_options:
                self.voice_combo.set(all_voice_options[0]["display_name"])

        # 关闭对话框
        dialog.destroy()

        # 显示成功消息
        self.show_message("成功", f"已删除收藏 '{deleted_favorite['name']}'")

    def show_message(self, title, message, is_error=False):
        """显示消息对话框"""
        # 创建自定义对话框
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # 图标和消息
        icon_label = ctk.CTkLabel(
            dialog,
            text="⚠️" if is_error else "✅",
            font=ctk.CTkFont(size=24)
        )
        icon_label.pack(pady=(20, 10))

        message_label = ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(size=14),
            wraplength=350
        )
        message_label.pack(pady=10, padx=20)

        # 确定按钮
        ok_button = ctk.CTkButton(
            dialog,
            text="确定",
            command=dialog.destroy,
            width=100
        )
        ok_button.pack(pady=20)

        # 绑定回车键
        dialog.bind('<Return>', lambda e: dialog.destroy())

    def build_api_url(self, text, voice_index):
        """构建API URL，包含所有高级参数（除了音程）"""
        base_url = self.api_templates[voice_index]

        # 获取高级参数（音程单独处理，不加入URL）
        effect = self.effect_var.get()
        boyomi = "true" if self.boyomi_var.get() else "false"
        speed = str(self.speed_var.get())
        volume = str(self.volume_var.get())

        # 编码文本
        encoded_text = quote(text)

        # 检查API类型并构建URL
        if "aqtk1" in base_url or "aqtk2" in base_url:
            # 对于aqtk1和aqtk2 API，添加高级参数
            if "?" in base_url:
                # 如果已经有参数，添加额外参数
                api_url = base_url.replace("{text}", encoded_text)
                api_url += f"&effect={effect}&boyomi={boyomi}&speed={speed}&volume={volume}"
            else:
                # 如果没有参数，添加参数
                api_url = base_url.replace("{text}", encoded_text)
                api_url += f"?effect={effect}&boyomi={boyomi}&speed={speed}&volume={volume}"
        else:
            # 对于aqtk10 API，可能需要替换现有参数或添加新参数
            api_url = base_url.replace("{text}", encoded_text)

            # 替换或添加速度参数
            if "speed=" in api_url:
                api_url = re.sub(r'speed=\d+', f'speed={speed}', api_url)
            else:
                api_url += f"&speed={speed}"

            # 替换或添加音量参数
            if "volume=" in api_url:
                api_url = re.sub(r'volume=\d+', f'volume={volume}', api_url)
            else:
                api_url += f"&volume={volume}"

            # 添加效果和捧读参数
            api_url += f"&effect={effect}&boyomi={boyomi}"

        return api_url

    def calculate_concurrent_workers(self, line_count, base_concurrent):
        """计算实际并发工作线程数"""
        if self.unlimited_concurrent_var.get():
            # 无限制模式，根据行数自动调节
            # 限制最大并发数为行数，但不超过50（避免资源过度消耗）
            return min(line_count, 50)
        else:
            # 有限制模式，使用用户设置的并发数
            return min(base_concurrent, line_count)

    def start_process(self):
        """开始处理流程"""
        if self.is_processing:
            self.show_message("提示", "已有任务正在处理中，请等待完成", is_error=True)
            return

        text = self.text_input.get("1.0", "end").strip()

        # 如果输入框完全为空，则生成"我喜欢你"的语音
        if not text:
            text = "我喜欢你"

        selected_voice = self.voice_combo.get()
        if not selected_voice:
            self.show_message("错误", "请选择声线", is_error=True)
            return

        # 获取转换模式
        convert_mode = self.convert_mode_var.get()

        # 获取并发数
        convert_concurrent = self.convert_concurrent_var.get()
        generate_concurrent = self.generate_concurrent_var.get()

        # 查找voice_index
        voice_index = 0
        selected_voice_value = None

        # 获取选中的语音值
        all_voice_options = self.get_all_voice_options()
        for opt in all_voice_options:
            if opt["display_name"] == selected_voice:
                selected_voice_value = opt["value"]
                break

        if not selected_voice_value:
            self.show_message("错误", "找不到对应的语音类型", is_error=True)
            return

        # 根据语音值查找对应的索引
        for i, voice in enumerate(self.voice_options):
            if voice["value"] == selected_voice_value:
                voice_index = i
                break

        # 设置处理状态
        self.is_processing = True
        self.generate_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # 在新线程中处理，避免UI冻结
        thread = threading.Thread(
            target=self.full_process,
            args=(text, voice_index, convert_mode, convert_concurrent, generate_concurrent)
        )
        thread.daemon = True
        thread.start()

    def full_process(self, text, voice_index, convert_mode, convert_concurrent, generate_concurrent):
        """完整的处理流程：转换文本并生成音频"""
        total_count = 0
        success_count = 0
        output_dir = None
        converted_lines = []
        subtitle_entries = []  # 存储字幕条目

        try:
            self.status_var.set("正在处理...")
            self.progress.start()

            # 分割原始文本行
            original_lines = [line.strip() for line in text.split('\n') if line.strip()]
            total_count = len(original_lines)

            if not original_lines:
                self.status_var.set("没有有效文本行")
                return

            # 计算实际并发数
            actual_convert_concurrent = self.calculate_concurrent_workers(total_count, convert_concurrent)
            actual_generate_concurrent = self.calculate_concurrent_workers(total_count, generate_concurrent)

            self.status_var.set(f"使用并发数: 转换{actual_convert_concurrent}/生成{actual_generate_concurrent}")

            # 创建输出目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            app_root = get_app_root()
            output_dir = os.path.join(app_root, timestamp)
            os.makedirs(output_dir, exist_ok=True)

            # 第一步：并行转换所有文本
            self.status_var.set(f"正在转换文本 (0/{total_count})...")

            # 使用线程池并行转换文本
            with concurrent.futures.ThreadPoolExecutor(max_workers=actual_convert_concurrent) as executor:
                self.current_executor = executor
                # 创建转换任务
                convert_tasks = {
                    executor.submit(self.convert_text, line, convert_mode): (i, line)
                    for i, line in enumerate(original_lines)
                }

                # 处理转换结果
                for future in concurrent.futures.as_completed(convert_tasks):
                    if not self.is_processing:
                        break
                    i, original_line = convert_tasks[future]
                    try:
                        converted_text = future.result()
                        if converted_text:
                            # 根据转换模式处理文本
                            if convert_mode == "空耳":
                                processed_text = self.process_text(converted_text)  # 移除空格和括号
                            else:
                                processed_text = converted_text  # 翻译模式直接使用翻译结果
                            converted_lines.append((i, original_line, processed_text))
                            self.status_var.set(f"正在转换文本 ({len(converted_lines)}/{total_count})...")
                        else:
                            converted_lines.append((i, original_line, None))
                    except Exception as e:
                        log_error(f"转换任务出错: {str(e)}")
                        converted_lines.append((i, original_line, None))

            if not self.is_processing:
                return

            # 按原始顺序排序
            converted_lines.sort(key=lambda x: x[0])

            # 第二步：并行生成音频
            self.status_var.set(f"正在生成音频 (0/{len(converted_lines)})...")

            # 使用线程池并行生成音频
            with concurrent.futures.ThreadPoolExecutor(max_workers=actual_generate_concurrent) as executor:
                self.current_executor = executor
                # 创建生成任务
                generate_tasks = {}
                for i, original_line, processed_text in converted_lines:
                    if not self.is_processing:
                        break
                    if processed_text is not None:
                        task = executor.submit(
                            self.generate_audio,
                            processed_text, voice_index, output_dir,
                            original_line, i+1, total_count
                        )
                        generate_tasks[task] = (i, original_line)

                # 处理生成结果
                for future in concurrent.futures.as_completed(generate_tasks):
                    if not self.is_processing:
                        break
                    i, original_line = generate_tasks[future]
                    try:
                        success, duration = future.result()
                        if success:
                            success_count += 1
                            # 记录字幕条目
                            subtitle_entries.append((i, original_line, duration))
                        self.status_var.set(f"正在生成音频 ({success_count}/{len(generate_tasks)})...")
                    except Exception as e:
                        log_error(f"生成任务出错: {str(e)}")

            if not self.is_processing:
                return

            # 如果启用了字幕生成，创建合并的字幕文件
            if self.generate_subtitle_var.get() and subtitle_entries:
                self.generate_merged_subtitle_file(subtitle_entries, output_dir)

            # 处理完成，显示结果
            if success_count == 0:
                if output_dir and os.path.exists(output_dir):
                    import shutil
                    shutil.rmtree(output_dir)
                self.status_var.set("全部生成失败")
                self.show_message("提示", "所有音频生成都失败了，可能是请求过于频繁，请稍后再试。", is_error=True)
            else:
                self.status_var.set(f"完成! 成功 {success_count}/{total_count}")
                self.show_message("成功", f"音频生成完成！\n总共 {total_count} 个，成功 {success_count} 个，失败 {total_count - success_count} 个。\n音频已保存到: {timestamp}")

        except Exception as e:
            self.status_var.set("处理过程中出错")
            error_msg = f"处理过程中出错: {str(e)}"
            log_error(error_msg)
            self.show_message("错误", error_msg, is_error=True)
        finally:
            self.is_processing = False
            self.current_executor = None
            self.progress.stop()
            self.generate_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def convert_text(self, text, convert_mode):
        """根据转换模式转换文本"""
        if convert_mode == "空耳":
            # 中文转片假名
            return self.convert_to_katakana(text)
        elif convert_mode == "翻译":
            # 中文转日语
            return self.translate_to_japanese(text)
        else:
            return self.convert_to_katakana(text)  # 默认使用空耳模式

    def convert_to_katakana(self, text):
        """将中文文本转换为片假名"""
        # 移除is_processing检查，允许在任何情况下进行转换

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                target_url = "https://www.ltool.net/chinese-simplified-and-traditional-characters-pinyin-to-katakana-converter-in-simplified-chinese.php"

                data = {
                    'contents': text,
                    'firstinput': 'OK',
                    'option': '1',
                    'optionext': 'zenkaku'
                }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': target_url,
                    'Origin': 'https://www.ltool.net',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }

                time.sleep(random.uniform(0.5, 1.5))

                response = requests.post(target_url, data=data, headers=headers, timeout=30)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                result_div = soup.find('div', {'id': 'result'})
                if result_div:
                    final_result = result_div.find('div', {'class': 'finalresult'})
                    if final_result:
                        return final_result.text.strip()

                return None

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    return None
            except Exception as e:
                return None

    def translate_to_japanese(self, text):
        """将中文文本翻译成日语"""
        # 移除is_processing检查，允许在任何情况下进行翻译
        
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # 尝试多种翻译方法
                
                # 方法1: 使用Google翻译的免费API
                try:
                    return self._translate_with_google(text)
                except:
                    pass
                
                # 方法2: 使用有道翻译API
                try:
                    return self._translate_with_youdao(text)
                except:
                    pass
                
                # 方法3: 使用本地简单映射（作为备选）
                return self._translate_with_fallback(text)
                
            except Exception as e:
                log_error(f"翻译尝试 {attempt + 1} 失败: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    # 最后的备选方案：返回原始文本
                    return text

    def _translate_with_google(self, text):
        """使用Google翻译API进行翻译"""
        # 使用Google翻译的免费接口
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'zh',
            'tl': 'ja',
            'dt': 't',
            'q': text
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result and len(result) > 0 and result[0]:
            translated = ""
            for item in result[0]:
                if item and item[0]:
                    translated += item[0]
            return translated if translated else text
        
        return text

    def _translate_with_youdao(self, text):
        """使用有道翻译API进行翻译"""
        target_url = "https://fanyi.youdao.com/translate"
        
        # 生成签名（简化版本）
        import hashlib
        import time
        timestamp = str(int(time.time() * 1000))
        salt = timestamp
        sign_str = f"fanyideskweb{text}{salt}Ygy_4c=r#e#4EX^NUGUc5"
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        
        data = {
            'i': text,
            'from': 'zh-CHS',
            'to': 'ja',
            'smartresult': 'dict',
            'client': 'fanyideskweb',
            'salt': salt,
            'sign': sign,
            'doctype': 'json',
            'version': '2.1',
            'keyfrom': 'fanyi.web',
            'action': 'FY_BY_REALTlME'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://fanyi.youdao.com/',
            'Origin': 'https://fanyi.youdao.com',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest'
        }

        response = requests.post(target_url, data=data, headers=headers, timeout=10)
        response.raise_for_status()

        result_json = response.json()
        if 'translateResult' in result_json:
            translated_text = ""
            for result in result_json['translateResult']:
                for item in result:
                    if 'tgt' in item:
                        translated_text += item['tgt']
            return translated_text if translated_text else text
        
        return text

    def _translate_with_fallback(self, text):
        """本地备选翻译方法"""
        # 简单的中文到日语映射（备选方案）
        translations = {
            "你好": "こんにちは",
            "谢谢": "ありがとう",
            "不客气": "どういたしまして",
            "对不起": "すみません",
            "再见": "さようなら",
            "早上好": "おはようございます",
            "晚上好": "こんばんは",
            "我喜欢你": "あなたが好きです",
            "我爱你": "愛しています",
            "今天": "今日",
            "明天": "明日",
            "昨天": "昨日",
            "天气": "天気",
            "很好": "とても良い",
            "不好": "良くない",
            "什么": "何",
            "哪里": "どこ",
            "什么时候": "いつ",
            "为什么": "なぜ",
            "怎么样": "どうですか"
        }
        
        # 尝试精确匹配
        if text in translations:
            return translations[text]
        
        # 尝试部分匹配
        for chinese, japanese in translations.items():
            if chinese in text:
                text = text.replace(chinese, japanese)
        
        # 如果没有找到匹配，返回原始文本
        return text

    def process_text(self, text):
        """处理文本，移除空格和括号内容（仅用于空耳模式）"""
        processed = re.sub(r'\([^)]*\)', '', text)
        processed = processed.replace(' ', '')
        return processed

    def generate_audio(self, text, voice_index, output_dir, original_text, current, total):
        """生成音频文件，并应用音程调整"""
        if not self.is_processing:
            return False, 0

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            if not self.is_processing:
                return False, 0
            try:
                # 使用构建API URL的方法，包含高级参数（除了音程）
                api_url = self.build_api_url(text, voice_index)

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Range': 'bytes=0-',
                    'Referer': 'https://www.yukumo.net/',
                    'Origin': 'https://www.yukumo.net',
                    'Connection': 'keep-alive',
                }

                time.sleep(random.uniform(0.3, 1.0))

                response = requests.get(api_url, headers=headers, stream=True, timeout=30)
                response.raise_for_status()

                # 获取音频数据
                audio_data = b''
                for chunk in response.iter_content(chunk_size=8192):
                    if not self.is_processing:
                        return False, 0
                    if chunk:
                        audio_data += chunk

                # 应用音程调整（如果音程不是默认值100）
                pitch_factor = self.pitch_var.get()
                if pitch_factor != 100:
                    try:
                        # 使用更完善的音程调整处理
                        adjusted_audio_data = self.process_audio_pitch_in_memory(audio_data, pitch_factor)
                        if adjusted_audio_data:
                            audio_data = adjusted_audio_data
                        else:
                            log_error("音程调整失败，使用原始音频")
                    except Exception as e:
                        log_error(f"音程调整失败: {str(e)}")
                        # 如果调整失败，使用原始音频

                # 获取内容长度以估算音频时长
                content_length = len(audio_data)
                estimated_duration = self.estimate_audio_duration(content_length, original_text)

                safe_filename = re.sub(r'[<>:"/\\|?*]', '_', original_text)
                if len(safe_filename) > 50:
                    safe_filename = safe_filename[:50]

                filename = f"{current:03d}_{safe_filename}.mp3"
                file_path = os.path.join(output_dir, filename)

                with open(file_path, 'wb') as f:
                    f.write(audio_data)

                # 获取音频的实际时长
                actual_duration = self.get_audio_duration(file_path)

                return True, actual_duration

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    return False, 0
            except Exception as e:
                return False, 0

    def estimate_audio_duration(self, content_length, text):
        """估算音频时长"""
        try:
            # 如果无法获取内容长度，使用基于文本长度的估算
            if content_length:
                # 假设平均比特率为 64 kbps (8 KB/s)
                file_size = int(content_length)
                estimated_duration = max(1000, int(file_size / 8000 * 1000))  # 转换为毫秒，最小1秒
            else:
                # 基于文本长度和速度参数的估算
                text_length = len(text)
                speed_factor = self.speed_var.get() / 100.0
                base_duration_per_char = 350  # 每个字符的基础时长（毫秒）
                min_duration = 1000  # 最小音频时长（毫秒）
                estimated_duration = max(min_duration, int(text_length * base_duration_per_char / speed_factor))

            return estimated_duration
        except:
            # 如果估算失败，返回默认值
            return 2000  # 默认2秒

    def get_audio_duration(self, audio_file_path):
        """使用 ffmpeg 获取音频文件的实际时长（毫秒）"""
        try:
            import subprocess
            import re

            ffmpeg_path = get_ffmpeg_path()
            if not ffmpeg_path:
                log_error("未找到 ffmpeg，无法获取音频时长")
                return 2000  # 返回默认值

            # 使用 ffprobe 获取更准确的时长信息
            cmd = [
                ffmpeg_path.replace('ffmpeg.exe', 'ffprobe.exe') if ffmpeg_path.endswith('ffmpeg.exe') else ffmpeg_path,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_file_path
            ]

            # 如果 ffprobe 不存在，使用 ffmpeg
            if not os.path.exists(cmd[0]):
                cmd = [
                    ffmpeg_path,
                    '-i', audio_file_path,
                    '-f', 'null',
                    '-'
                ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # 如果使用 ffprobe，直接获取时长
            if '-show_entries' in cmd:
                try:
                    duration_seconds = float(result.stdout.strip())
                    return int(duration_seconds * 1000)  # 转换为毫秒
                except ValueError:
                    pass

            # 如果使用 ffmpeg，从输出中解析时长
            stderr_output = result.stderr
            # 查找类似 "Duration: 00:00:02.34" 的模式，支持更多格式
            duration_match = re.search(r'Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})', stderr_output)
            if not duration_match:
                # 尝试匹配 "Duration: 00:00:02.345" 格式
                duration_match = re.search(r'Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})', stderr_output)

            if duration_match:
                hours = int(duration_match.group(1))
                minutes = int(duration_match.group(2))
                seconds = int(duration_match.group(3))
                if len(duration_match.group(4)) == 2:
                    centiseconds = int(duration_match.group(4))
                    total_milliseconds = (hours * 3600 + minutes * 60 + seconds) * 1000 + centiseconds * 10
                else:  # 3位小数
                    milliseconds = int(duration_match.group(4))
                    total_milliseconds = (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
                return total_milliseconds
            else:
                log_error(f"无法解析 ffmpeg 输出: {stderr_output[:200]}")
                return 2000

        except Exception as e:
            log_error(f"获取音频时长失败: {str(e)}")
            return 2000  # 默认2秒

    def format_srt_time(self, milliseconds):
        """将毫秒格式化为SRT时间格式 (HH:MM:SS,mmm)"""
        hours = milliseconds // 3600000
        milliseconds %= 3600000
        minutes = milliseconds // 60000
        milliseconds %= 60000
        seconds = milliseconds // 1000
        milliseconds %= 1000

        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def generate_merged_subtitle_file(self, subtitle_entries, output_dir):
        """生成合并的SRT字幕文件"""
        try:
            # 按原始顺序排序
            subtitle_entries.sort(key=lambda x: x[0])

            # 创建合并的字幕文件
            subtitle_file_path = os.path.join(output_dir, "subtitles.srt")

            with open(subtitle_file_path, 'w', encoding='utf-8') as f:
                current_time = 0
                subtitle_index = 1

                for i, original_text, duration in subtitle_entries:
                    # 计算开始和结束时间
                    start_time = current_time
                    end_time = current_time + duration

                    # 写入SRT字幕条目
                    f.write(f"{subtitle_index}\n")
                    f.write(f"{self.format_srt_time(start_time)} --> {self.format_srt_time(end_time)}\n")
                    f.write(f"{original_text}\n\n")

                    # 更新当前时间和序号
                    current_time = end_time + 100  # 添加100毫秒间隔
                    subtitle_index += 1

        except Exception as e:
            log_error(f"生成合并字幕文件时出错: {str(e)}")

# 为了保持兼容性，保留原始类名
VoiceSynthesisApp = ModernVoiceSynthesisApp

if __name__ == "__main__":
    # 使用customtkinter创建主窗口
    try:
        root = ctk.CTk()
        app = VoiceSynthesisApp(root)
        root.mainloop()
    except Exception as e:
        log_error(f"程序启动错误: {str(e)}")
        input("按回车键退出...")