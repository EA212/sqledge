import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import pymysql
from datetime import datetime
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import json
import jieba
from collections import defaultdict
from zhipuai import ZhipuAI
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import time
import traceback

# 解决字体警告
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "sans-serif"]
plt.rcParams.update({"font.sans-serif": ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]})
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib.font_manager")
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.")

class AdvancedZhipuAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("智谱清言 - 高级分析工具")
        self.root.geometry("1300x800")
        self.root.minsize(1100, 700)
        
        # 核心配置
        self.queue = queue.Queue()
        self.running = True
        self.analysis_in_progress = False
        self.concurrent_workers = 1  # 默认并发数
        self.max_retries = 3  # API调用最大重试次数
        self.api_timeout = 60  # API超时时间(秒)
        
        # 配置参数
        self.db_config = {
            "host": "192.168.1.13",
            "port": 3307,
            "user": "root",
            "password": "123456",
            "database": "xiaozhi_esp32_server",
            "table": "ai_agent_chat_history"
        }
        
        # 智谱配置
        self.zhipu_api_key = "9dc472d5002f4058a85230e6ab676b27.uaIsT7o4C2CNCiBd"
        self.zhipu_model = "glm-4.5-x"
        self.MAX_AI_CHARS = 6000  # 单个批次最大字符数
        
        # 数据存储与锁
        self.conn = None
        self.current_mac = None
        self.processed_ids = defaultdict(int)
        self.analysis_results = defaultdict(dict)
        self.all_macs = []
        self.data_lock = threading.Lock()
        self.executor = None  # 线程池执行器
        
        # 持久化路径
        self.RESULTS_DIR = "analysis_results"
        os.makedirs(self.RESULTS_DIR, exist_ok=True)
        
        # 创建界面
        self._create_widgets()
        self._load_processed_records()
        self._load_persistent_results()
        self._connect_database()
        
        # 启动队列处理循环
        self._process_queue()
        
        print("程序初始化完成，使用模型: glm-4.5-flash")
    
    def _create_widgets(self):
        # 主容器
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧MAC区域
        left_frame = ttk.Frame(main_container, width=280)
        main_container.add(left_frame, weight=1)
        
        # 并发设置
        concurrent_frame = ttk.Frame(left_frame, padding=5)
        concurrent_frame.pack(fill=tk.X)
        ttk.Label(concurrent_frame, text="并发数:").pack(side=tk.LEFT, padx=5)
        self.concurrent_var = tk.IntVar(value=self.concurrent_workers)
        ttk.Entry(concurrent_frame, textvariable=self.concurrent_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(concurrent_frame, text="设置", command=self.set_concurrent_workers).pack(side=tk.LEFT, padx=5)
        
        # 搜索框
        search_frame = ttk.Frame(left_frame, padding=5)
        search_frame.pack(fill=tk.X)
        ttk.Label(search_frame, text="搜索MAC:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # MAC列表
        ttk.Label(left_frame, text="MAC地址列表", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=5, pady=5)
        self.mac_frame = ttk.Frame(left_frame)
        self.mac_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        self.mac_scrollbar = ttk.Scrollbar(self.mac_frame)
        self.mac_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.mac_listbox = tk.Listbox(
            self.mac_frame, yscrollcommand=self.mac_scrollbar.set,
            selectmode=tk.SINGLE, font=("SimHei", 10)
        )
        self.mac_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.mac_scrollbar.config(command=self.mac_listbox.yview)
        self.mac_listbox.bind('<<ListboxSelect>>', self.on_mac_selected)
        
        # 操作按钮
        left_bottom_frame = ttk.Frame(left_frame, padding=5)
        left_bottom_frame.pack(fill=tk.X)
        ttk.Button(left_bottom_frame, text="刷新列表", command=self.refresh_mac_list).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.analyze_btn = ttk.Button(left_bottom_frame, text="分析新增记录", command=self.start_analyze_thread)
        self.analyze_btn.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)
        
        # 一键分析所有MAC按钮
        self.analyze_all_btn = ttk.Button(left_frame, text="一键分析所有MAC", command=self.start_analyze_all_thread)
        self.analyze_all_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # API设置区域
        api_frame = ttk.LabelFrame(left_frame, text="API设置", padding=5)
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(api_frame, text="修改智谱API密钥", command=self.set_zhipu_key).pack(fill=tk.X, pady=2)
        
        # API超时设置
        ttk.Label(api_frame, text="API超时(秒):").pack(anchor=tk.W, padx=5, pady=2)
        self.timeout_var = tk.IntVar(value=self.api_timeout)
        ttk.Entry(api_frame, textvariable=self.timeout_var, width=10).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Button(api_frame, text="设置超时", command=self.set_api_timeout).pack(fill=tk.X, pady=2)
        
        # 重试次数设置
        ttk.Label(api_frame, text="重试次数:").pack(anchor=tk.W, padx=5, pady=2)
        self.retry_var = tk.IntVar(value=self.max_retries)
        ttk.Entry(api_frame, textvariable=self.retry_var, width=10).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Button(api_frame, text="设置重试", command=self.set_max_retries).pack(fill=tk.X, pady=2)
        
        # 右侧分析结果区域
        right_notebook = ttk.Notebook(main_container)
        main_container.add(right_notebook, weight=4)
        
        # 标签页
        self.chat_tab = ttk.Frame(right_notebook)
        self.hotwords_tab = ttk.Frame(right_notebook)
        self.mood_tab = ttk.Frame(right_notebook)
        self.health_tab = ttk.Frame(right_notebook)
        self.economic_tab = ttk.Frame(right_notebook)
        self.shopping_tab = ttk.Frame(right_notebook)
        self.log_tab = ttk.Frame(right_notebook)
        
        right_notebook.add(self.chat_tab, text="聊天记录")
        right_notebook.add(self.hotwords_tab, text="热词分析")
        right_notebook.add(self.mood_tab, text="心情分析")
        right_notebook.add(self.health_tab, text="健康状况")
        right_notebook.add(self.economic_tab, text="经济情况")
        right_notebook.add(self.shopping_tab, text="购物需求")
        right_notebook.add(self.log_tab, text="API交互日志")
        
        # 初始化标签页内容
        self._init_chat_tab()
        self._init_hotwords_tab()
        self._init_analysis_tabs()
        self._init_log_tab()
        
        # 状态栏和进度条
        self.status_var = tk.StringVar(value="未连接数据库")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.progress_frame = ttk.Frame(self.root, height=20)
        self.progress_frame.pack(fill=tk.X, padx=5, pady=2)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, mode='determinate')
        self.progress_bar.pack(fill=tk.X)
    
    def _init_chat_tab(self):
        self.chat_title = ttk.Label(self.chat_tab, text="请选择MAC地址", font=("Arial", 10, "bold"))
        self.chat_title.pack(anchor=tk.W, padx=10, pady=10)
        chat_frame = ttk.Frame(self.chat_tab)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.chat_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=("SimHei", 10))
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        self.chat_area.config(state=tk.DISABLED)
    
    def _init_hotwords_tab(self):
        frame = ttk.Frame(self.hotwords_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.hotwords_fig = Figure(figsize=(8, 6), dpi=100)
        self.hotwords_ax1 = self.hotwords_fig.add_subplot(121)
        self.hotwords_ax2 = self.hotwords_fig.add_subplot(122)
        self.hotwords_canvas = FigureCanvasTkAgg(self.hotwords_fig, master=frame)
        self.hotwords_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._reset_hotword_plots()
    
    def _init_analysis_tabs(self):
        self.mood_text = self._create_analysis_text(self.mood_tab)
        self.health_text = self._create_analysis_text(self.health_tab)
        self.economic_text = self._create_analysis_text(self.economic_tab)
        self.shopping_text = self._create_analysis_text(self.shopping_tab)
    
    def _init_log_tab(self):
        frame = ttk.Frame(self.log_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("SimHei", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.insert(tk.END, "API交互日志将显示在这里...\n")
        self.log_area.config(state=tk.DISABLED)
    
    def _create_analysis_text(self, parent):
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("SimHei", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, "暂无分析结果，请选择MAC并分析新增记录...")
        text.config(state=tk.DISABLED)
        return text
    
    # 配置设置方法
    def set_concurrent_workers(self):
        try:
            value = self.concurrent_var.get()
            if value < 1 or value > 10:
                messagebox.showwarning("警告", "并发数应在1-10之间")
                return
            self.concurrent_workers = value
            if self.executor:
                self.executor.shutdown(wait=True)
                self.executor = ThreadPoolExecutor(max_workers=self.concurrent_workers)
            messagebox.showinfo("成功", f"并发数已设置为: {self.concurrent_workers}")
            self._log(f"并发数已设置为: {self.concurrent_workers}")
        except Exception as e:
            messagebox.showerror("错误", f"设置失败: {str(e)}")
    
    def set_api_timeout(self):
        try:
            value = self.timeout_var.get()
            if value < 10 or value > 300:
                messagebox.showwarning("警告", "超时时间应在10-300秒之间")
                return
            self.api_timeout = value
            messagebox.showinfo("成功", f"API超时已设置为: {self.api_timeout}秒")
            self._log(f"API超时已设置为: {self.api_timeout}秒")
        except Exception as e:
            messagebox.showerror("错误", f"设置失败: {str(e)}")
    
    def set_max_retries(self):
        try:
            value = self.retry_var.get()
            if value < 1 or value > 10:
                messagebox.showwarning("警告", "重试次数应在1-10之间")
                return
            self.max_retries = value
            messagebox.showinfo("成功", f"最大重试次数已设置为: {self.max_retries}")
            self._log(f"最大重试次数已设置为: {self.max_retries}")
        except Exception as e:
            messagebox.showerror("错误", f"设置失败: {str(e)}")
    
    # 队列处理函数
    def _process_queue(self):
        """处理子线程发送的消息，更新UI"""
        while not self.queue.empty():
            try:
                message = self.queue.get_nowait()
                msg_type = message.get('type')
                
                if msg_type == 'log':
                    self._log(message.get('content'))
                elif msg_type == 'status':
                    self.status_var.set(message.get('content'))
                elif msg_type == 'progress':
                    self.progress_var.set(message.get('value'))
                elif msg_type == 'refresh_results':
                    self._display_analysis_results()
                    self.refresh_mac_list()
                elif msg_type == 'analysis_complete':
                    self.analysis_in_progress = False
                    self.analyze_btn.config(state=tk.NORMAL)
                    self.analyze_all_btn.config(state=tk.NORMAL)
                    self.progress_var.set(0)
                    messagebox.showinfo("完成", message.get('content'))
                elif msg_type == 'error':
                    self.analysis_in_progress = False
                    self.analyze_btn.config(state=tk.NORMAL)
                    self.analyze_all_btn.config(state=tk.NORMAL)
                    self.progress_var.set(0)
                    messagebox.showerror("错误", message.get('content'))
                
            except Exception as e:
                self._log(f"队列处理错误: {str(e)}")
        
        if self.running:
            self.root.after(100, self._process_queue)
    
    # 日志输出方法
    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        print(log_message.strip())
        
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, log_message)
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
    
    # 发送消息到队列
    def _send_to_queue(self, msg_type, **kwargs):
        message = {'type': msg_type,** kwargs}
        self.queue.put(message)
    
    # 数据加载与持久化
    def _sanitize_mac_filename(self, mac):
        return re.sub(r'[:/]', '-', mac)
    
    def _load_processed_records(self):
        if os.path.exists("processed_records.json"):
            try:
                with open("processed_records.json", "r", encoding="utf-8") as f:
                    with self.data_lock:
                        self.processed_ids = defaultdict(int, json.load(f))
                self._log(f"加载已处理记录: {dict(self.processed_ids)}")
            except Exception as e:
                self._log(f"加载已处理记录失败: {str(e)}")
                with self.data_lock:
                    self.processed_ids = defaultdict(int)
    
    def _save_processed_records(self):
        try:
            with self.data_lock:
                data = dict(self.processed_ids)
            with open("processed_records.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            self._log(f"保存已处理记录: {data}")
        except Exception as e:
            self._log(f"保存已处理记录失败: {str(e)}")
    
    def _load_persistent_results(self):
        try:
            if not os.path.exists(self.RESULTS_DIR):
                return
                
            with self.data_lock:
                self.analysis_results.clear()
                
            for filename in os.listdir(self.RESULTS_DIR):
                if filename.endswith(".json"):
                    mac = self._sanitize_mac_filename(filename[:-5])
                    with open(os.path.join(self.RESULTS_DIR, filename), "r", encoding="utf-8") as f:
                        result = json.load(f)
                        with self.data_lock:
                            self.analysis_results[mac] = result
            
            with self.data_lock:
                count = len(self.analysis_results)
            self._log(f"加载持久化结果，共{count}个MAC地址")
        except Exception as e:
            self._log(f"加载持久化结果失败: {str(e)}")
    
    def _save_persistent_results(self, mac):
        try:
            with self.data_lock:
                if mac not in self.analysis_results:
                    return
                data = self.analysis_results[mac]
            
            sanitized_mac = self._sanitize_mac_filename(mac)
            filename = f"{sanitized_mac}.json"
            with open(os.path.join(self.RESULTS_DIR, filename), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log(f"已持久化MAC {mac} 的分析结果")
        except Exception as e:
            self._log(f"持久化MAC {mac} 结果失败: {str(e)}")
    
    # 数据库操作
    def _connect_database(self):
        try:
            self.conn = pymysql.connect(
                host=self.db_config["host"],
                port=self.db_config["port"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
                charset="utf8mb4"
            )
            self.refresh_mac_list()
            self.status_var.set(f"已连接到数据库，共{len(self.all_macs)}个MAC地址")
            self._log("数据库连接成功")
        except Exception as e:
            messagebox.showerror("连接失败", f"数据库错误: {str(e)}")
            self.status_var.set("数据库连接失败")
            self._log(f"数据库连接失败: {str(e)}")
    
    def refresh_mac_list(self):
        if not self.conn:
            return
        try:
            self.mac_listbox.delete(0, tk.END)
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT DISTINCT mac_address FROM {self.db_config['table']} WHERE mac_address IS NOT NULL ORDER BY mac_address")
                macs = [mac[0] for mac in cursor.fetchall() if mac[0]]
                
                with self.data_lock:
                    self.all_macs = macs
                
                for mac in macs:
                    with self.data_lock:
                        status = "（已分析）" if self.processed_ids.get(mac, 0) > 0 else ""
                    self.mac_listbox.insert(tk.END, f"{mac} {status}")
            
            with self.data_lock:
                count = len(self.all_macs)
            self.status_var.set(f"MAC列表已刷新，共{count}个地址")
            self._log(f"刷新MAC列表，共{count}个地址")
        except Exception as e:
            messagebox.showerror("错误", f"刷新MAC列表失败: {str(e)}")
            self._log(f"刷新MAC列表失败: {str(e)}")
    
    # 搜索功能实现
    def _on_search_changed(self, *args):
        search_text = self.search_var.get().lower()
        self.mac_listbox.delete(0, tk.END)
        
        with self.data_lock:
            macs = self.all_macs.copy()
        
        if not search_text:
            for mac in macs:
                with self.data_lock:
                    status = "（已分析）" if self.processed_ids.get(mac, 0) > 0 else ""
                self.mac_listbox.insert(tk.END, f"{mac} {status}")
        else:
            filtered = [mac for mac in macs if search_text in mac.lower()]
            for mac in filtered:
                with self.data_lock:
                    status = "（已分析）" if self.processed_ids.get(mac, 0) > 0 else ""
                self.mac_listbox.insert(tk.END, f"{mac} {status}")
    
    # 聊天记录处理
    def on_mac_selected(self, event=None):
        selection = self.mac_listbox.curselection()
        if not selection:
            return
        selected_text = self.mac_listbox.get(selection[0])
        self.current_mac = selected_text.split("（")[0].strip()
        self.chat_title.config(text=f"MAC地址: {self.current_mac} 的聊天记录")
        self._load_chat_records()
        self._display_analysis_results()
        self._log(f"选中MAC地址: {self.current_mac}")
    
    def _load_chat_records(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT id, content, created_at FROM {self.db_config['table']} "
                    f"WHERE mac_address = %s ORDER BY created_at ASC",
                    (self.current_mac,)
                )
                self.chat_records = cursor.fetchall()
                self._display_chat_records()
                self._log(f"为MAC {self.current_mac} 加载了{len(self.chat_records)}条聊天记录")
        except Exception as e:
            messagebox.showerror("错误", f"加载聊天记录失败: {str(e)}")
            self._log(f"加载MAC {self.current_mac} 聊天记录失败: {str(e)}")
    
    def _display_chat_records(self):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        if not self.chat_records:
            self.chat_area.insert(tk.END, "该MAC地址无聊天记录")
            self.chat_area.config(state=tk.DISABLED)
            return
        
        with self.data_lock:
            last_processed_id = self.processed_ids.get(self.current_mac, 0)
        
        for record_id, content, created_at in self.chat_records:
            time_str = created_at.strftime("%Y-%m-%d %H:%M") if isinstance(created_at, datetime) else str(created_at)
            status = "【已分析】" if record_id <= last_processed_id else "【未分析】"
            self.chat_area.insert(tk.END, f"[{time_str}] {status}\n", "time")
            self.chat_area.insert(tk.END, f"{content}\n\n", "content")
        
        self.chat_area.tag_config("time", foreground="#666666", font=("SimHei", 9))
        self.chat_area.tag_config("content", font=("SimHei", 10))
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
    
    # 启动分析线程
    def start_analyze_thread(self):
        if not self.current_mac:
            messagebox.showwarning("提示", "请先选择一个MAC地址")
            return
        
        if self.analysis_in_progress:
            messagebox.showinfo("提示", "已有分析任务在运行中，请等待完成")
            return
        
        self.analysis_in_progress = True
        self.analyze_btn.config(state=tk.DISABLED)
        self.analyze_all_btn.config(state=tk.DISABLED)
        
        threading.Thread(target=self._analyze_current_mac_thread, daemon=True).start()
    
    # 启动一键分析所有MAC的线程
    def start_analyze_all_thread(self):
        with self.data_lock:
            mac_count = len(self.all_macs)
        
        if mac_count == 0:
            messagebox.showinfo("提示", "没有MAC地址可分析")
            return
        
        if self.analysis_in_progress:
            messagebox.showinfo("提示", "已有分析任务在运行中，请等待完成")
            return
        
        confirm = messagebox.askyesno("确认", f"即将分析所有{mac_count}个MAC地址，使用{self.concurrent_workers}个并发线程，可能需要较长时间，是否继续？")
        if not confirm:
            return
        
        self.analysis_in_progress = True
        self.analyze_btn.config(state=tk.DISABLED)
        self.analyze_all_btn.config(state=tk.DISABLED)
        
        threading.Thread(target=self._analyze_all_macs_thread, daemon=True).start()
    
    # 子线程：分析当前选中的MAC
    def _analyze_current_mac_thread(self):
        try:
            mac = self.current_mac
            self._send_to_queue('status', content=f"开始分析 {mac} 的新增记录")
            self._send_to_queue('log', content=f"开始分析MAC {mac} 的新增记录")
            
            try:
                with self.conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT id, content, created_at FROM {self.db_config['table']} "
                        f"WHERE mac_address = %s ORDER BY created_at ASC",
                        (mac,)
                    )
                    chat_records = cursor.fetchall()
            except Exception as e:
                self._send_to_queue('error', content=f"加载记录失败: {str(e)}")
                return
            
            with self.data_lock:
                last_id = self.processed_ids.get(mac, 0)
            new_records = [r for r in chat_records if r[0] > last_id]
            
            if not new_records:
                self._send_to_queue('analysis_complete', content=f"MAC {mac} 无新增记录需要分析")
                return
            
            self._send_to_queue('log', content=f"发现{len(new_records)}条新增记录")
            self._analyze_mac_records(mac, new_records)
            
            self._send_to_queue('refresh_results')
            self._send_to_queue('analysis_complete', content=f"MAC {mac} 分析完成，共处理{len(new_records)}条记录")
            
        except Exception as e:
            self._send_to_queue('error', content=f"分析失败: {str(e)}")
            self._send_to_queue('log', content=f"分析线程错误: {traceback.format_exc()}")
    
    # 子线程：分析所有MAC（使用线程池）
    def _analyze_all_macs_thread(self):
        try:
            with self.data_lock:
                macs = self.all_macs.copy()
                total = len(macs)
            
            self._send_to_queue('status', content=f"开始分析所有MAC（共{total}个，并发数: {self.concurrent_workers}）")
            self._send_to_queue('log', content=f"开始分析所有{total}个MAC地址，并发数: {self.concurrent_workers}")
            
            # 初始化线程池
            self.executor = ThreadPoolExecutor(max_workers=self.concurrent_workers)
            futures = []
            success_count = 0
            fail_count = 0
            
            # 提交所有任务
            for mac in macs:
                if not self.running:
                    break
                futures.append(self.executor.submit(self._process_single_mac, mac))
            
            # 处理结果
            for i, future in enumerate(as_completed(futures)):
                if not self.running:
                    break
                    
                progress = ((i + 1) / total) * 100
                self._send_to_queue('progress', value=progress)
                
                try:
                    result = future.result()
                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    fail_count += 1
                    self._send_to_queue('log', content=f"MAC处理失败: {str(e)}")
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            self.executor = None
            
            self._send_to_queue('progress', value=100)
            self._send_to_queue('refresh_results')
            self._send_to_queue('analysis_complete', 
                               content=f"所有MAC分析完成，成功{success_count}个，失败{fail_count}个")
            
        except Exception as e:
            self._send_to_queue('error', content=f"批量分析失败: {str(e)}")
            self._send_to_queue('log', content=f"批量分析线程错误: {traceback.format_exc()}")
            if self.executor:
                self.executor.shutdown(wait=True)
                self.executor = None
    
    # 线程池任务：处理单个MAC
    def _process_single_mac(self, mac):
        try:
            self._send_to_queue('log', content=f"开始处理MAC: {mac}")
            
            # 加载该MAC的记录
            with self.conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT id, content, created_at FROM {self.db_config['table']} "
                    f"WHERE mac_address = %s ORDER BY created_at ASC",
                    (mac,)
                )
                chat_records = cursor.fetchall()
            
            # 检查新增记录
            with self.data_lock:
                last_id = self.processed_ids.get(mac, 0)
            new_records = [r for r in chat_records if r[0] > last_id]
            
            if not new_records:
                self._send_to_queue('log', content=f"MAC {mac} 无新增记录需要分析")
                return True
            
            # 分析该MAC
            self._analyze_mac_records(mac, new_records)
            self._send_to_queue('log', content=f"MAC {mac} 分析完成")
            return True
            
        except Exception as e:
            self._send_to_queue('log', content=f"MAC {mac} 处理失败: {str(e)}")
            return False
    
    # 分析单个MAC的记录
    def _analyze_mac_records(self, mac, new_records):
        # 1. 合并新增记录为文本
        full_text = "\n".join([f"[{r[2]}] {r[1]}" for r in new_records])
        self._send_to_queue('log', content=f"MAC {mac} 新增记录合并后总长度: {len(full_text)}字符")
        
        # 2. 按AI最大处理字数分块
        chunks = self._split_text_by_chars(full_text, self.MAX_AI_CHARS)
        chunk_count = len(chunks)
        self._send_to_queue('log', content=f"MAC {mac} 文本分块完成，共{chunk_count}块")
        
        # 3. 逐块分析并合并结果（每次都是新对话）
        for i, chunk in enumerate(chunks):
            self._send_to_queue('status', content=f"分析 {mac} 第{i+1}/{chunk_count}块...")
            self._send_to_queue('log', content=f"MAC {mac} 开始分析第{i+1}块（长度: {len(chunk)}字符）")
            
            # 调用智谱API（带重试机制）
            ai_result = self._call_zhipu_analysis_with_retry(chunk)
            
            # 合并结果
            self._merge_analysis_results(mac, ai_result)
            self._send_to_queue('log', content=f"MAC {mac} 第{i+1}块分析完成，已合并结果")
        
        # 4. 更新处理状态并持久化
        max_record_id = max(r[0] for r in new_records)
        with self.data_lock:
            self.processed_ids[mac] = max_record_id
        self._save_processed_records()
        self._save_persistent_results(mac)
    
    def _split_text_by_chars(self, text, max_chars):
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + max_chars, text_len)
            
            if end < text_len:
                split_pos = text.rfind('\n', start, end)
                if split_pos != -1:
                    end = split_pos + 1
            
            chunks.append(text[start:end].strip())
            start = end
        
        return chunks
    
    # 带重试机制的API调用
    def _call_zhipu_analysis_with_retry(self, content):
        """带超时和重试机制的API调用，每次都是新对话"""
        for attempt in range(self.max_retries):
            try:
                return self._call_zhipu_analysis(content)
            except Exception as e:
                self._send_to_queue('log', content=f"API调用尝试 {attempt+1}/{self.max_retries} 失败: {str(e)}")
                if attempt < self.max_retries - 1:
                    # 重试前等待一段时间（指数退避）
                    wait_time = (attempt + 1) * 2  # 1*2, 2*2, 3*2...秒
                    self._send_to_queue('log', content=f"将在 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        # 所有重试都失败
        raise Exception(f"API调用超过最大重试次数 ({self.max_retries}次)")
    
    def _call_zhipu_analysis(self, content):
        """调用智谱API分析单块文本，每次创建新对话"""
        try:
            client = ZhipuAI(api_key=self.zhipu_api_key)
            
            prompt = f"""
            请分析以下聊天记录，提取并总结以下信息，返回JSON格式：
            1. hot_words：热词列表（多个词，按出现频率排序，格式：["词1", "词2"...]，无则返回空列表）
            2. mood：心情分析（一句话总结，无则返回"无"）
            3. health：健康状况（记录提到的身体部位问题，格式：["部位1: 问题", "部位2: 问题"...]，无则返回空列表）
            4. economic：经济情况（一句话总结，无则返回"无"）
            5. shopping_needs：潜在购物需求（多个需求，格式：["需求1", "需求2"...]，无则返回空列表）
            
            注意：
            - 只有明确提到的信息才记录，未提到的维度返回对应"无"或空列表
            - 不要添加额外字段，严格按照上述格式返回JSON，不要有多余文字
            
            聊天记录：
            {content}
            """
            
            # 发送API调用信息（每次都是新对话，不携带历史上下文）
            self._send_to_queue('log', content=f"发送新对话到API（前200字符）: {prompt[:200]}...")
            
            # 调用API，设置超时
            response = client.chat.completions.create(
                model=self.zhipu_model,
                messages=[{"role": "user", "content": prompt}],  # 每次都是新对话
                timeout=self.api_timeout
            )
            
            # 解析结果
            result_text = response.choices[0].message.content.strip()
            self._send_to_queue('log', content=f"API返回结果（前200字符）: {result_text[:200]}...")
            
            # 处理可能的markdown格式
            if result_text.startswith("```json") and result_text.endswith("```"):
                result_text = result_text[7:-3].strip()
            
            return json.loads(result_text)
            
        except Exception as e:
            self._send_to_queue('log', content=f"API调用错误: {str(e)}")
            raise
    
    def _merge_analysis_results(self, mac, new_result):
        """合并新分析结果"""
        with self.data_lock:
            current_results = self.analysis_results.get(mac, {}).copy()
            
            # 合并热词（去重）
            current_hot = current_results.get("hot_words", [])
            new_hot = new_result.get("hot_words", [])
            merged_hot = current_hot + [w for w in new_hot if w not in current_hot]
            
            # 合并健康状况（去重）
            current_health = current_results.get("health", [])
            new_health = new_result.get("health", [])
            merged_health = current_health + [h for h in new_health if h not in current_health]
            
            # 合并购物需求（去重）
            current_shopping = current_results.get("shopping_needs", [])
            new_shopping = new_result.get("shopping_needs", [])
            merged_shopping = current_shopping + [s for s in new_shopping if s not in current_shopping]
            
            # 更新结果
            self.analysis_results[mac] = {
                "hot_words": merged_hot,
                "mood": new_result["mood"] if new_result["mood"] != "无" else current_results.get("mood", "无"),
                "health": merged_health,
                "economic": new_result["economic"] if new_result["economic"] != "无" else current_results.get("economic", "无"),
                "shopping_needs": merged_shopping
            }
    
    # 结果展示
    def _display_analysis_results(self):
        if not self.current_mac:
            return
        
        with self.data_lock:
            if self.current_mac not in self.analysis_results:
                return
            res = self.analysis_results[self.current_mac].copy()
        
        self._log(f"展示MAC {self.current_mac} 的分析结果")
        
        # 热词分析
        self._update_hotword_plots(res["hot_words"])
        
        # 心情分析
        self._update_analysis_text(self.mood_text, "心情分析", res["mood"])
        
        # 健康状况
        self._update_analysis_text(self.health_text, "健康状况", 
                                  "\n- ".join(res["health"]) if res["health"] else "无提到健康问题")
        
        # 经济情况
        self._update_analysis_text(self.economic_text, "经济情况", res["economic"])
        
        # 购物需求
        self._update_analysis_text(self.shopping_text, "潜在购物需求", 
                                  "\n- ".join(res["shopping_needs"]) if res["shopping_needs"] else "无潜在购物需求")
    
    def _update_hotword_plots(self, hot_words):
        self.hotwords_ax1.clear()
        self.hotwords_ax2.clear()
        
        if not hot_words:
            self.hotwords_ax1.text(0.5, 0.5, "无热词信息", ha='center', va='center', transform=self.hotwords_ax1.transAxes)
            self.hotwords_ax2.text(0.5, 0.5, "无热词信息", ha='center', va='center', transform=self.hotwords_ax2.transAxes)
        else:
            # 柱状图（取前10个热词）
            top_words = hot_words[:10]
            counts = list(range(len(top_words), 0, -1))
            self.hotwords_ax1.barh(top_words, counts, color='#4CAF50')
            self.hotwords_ax1.set_title("热词频率TOP10")
            
            # 词云
            from wordcloud import WordCloud
            wordcloud = WordCloud(
                width=400, 
                height=300, 
                background_color='white', 
                font_path=self._get_font_path()
            ).generate(" ".join(hot_words))
            self.hotwords_ax2.imshow(wordcloud)
            self.hotwords_ax2.axis('off')
            self.hotwords_ax2.set_title("热词词云")
        
        self.hotwords_fig.tight_layout()
        self.hotwords_canvas.draw()
    
    def _get_font_path(self):
        try:
            font_paths = [
                "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
                "C:/Windows/Fonts/msyh.ttc",   # Windows 微软雅黑
                "/System/Library/Fonts/PingFang.ttc",  # macOS 苹方
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"  # Linux
            ]
            
            for path in font_paths:
                if os.path.exists(path):
                    return path
        except:
            pass
        return None
    
    def _update_analysis_text(self, text_widget, title, content):
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, f"{title}:\n\n", "title")
        text_widget.insert(tk.END, content if content != "无" else "无相关信息", "content")
        text_widget.tag_config("title", font=("SimHei", 10, "bold"))
        text_widget.tag_config("content", font=("SimHei", 10))
        text_widget.config(state=tk.DISABLED)
    
    def _reset_hotword_plots(self):
        self.hotwords_ax1.clear()
        self.hotwords_ax2.clear()
        self.hotwords_ax1.text(0.5, 0.5, "请选择MAC并分析新增记录", ha='center', va='center', transform=self.hotwords_ax1.transAxes)
        self.hotwords_ax2.text(0.5, 0.5, "词云将显示在此处", ha='center', va='center', transform=self.hotwords_ax2.transAxes)
        self.hotwords_canvas.draw()
    
    def set_zhipu_key(self):
        key = simpledialog.askstring("智谱配置", "请输入智谱清言API密钥:", show='*', initialvalue=self.zhipu_api_key)
        if key:
            self.zhipu_api_key = key
            messagebox.showinfo("配置成功", "智谱API密钥已更新")
            self._log("智谱API密钥更新成功")
    
    def on_close(self):
        """关闭窗口时的清理工作"""
        self.running = False
        self.analysis_in_progress = False
        
        # 关闭线程池
        if self.executor:
            self._log("正在关闭线程池...")
            self.executor.shutdown(wait=False, cancel_futures=True)
        
        # 关闭数据库连接
        if self.conn:
            self.conn.close()
        
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AdvancedZhipuAnalyzer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    
