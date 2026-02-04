import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import pymysql
from datetime import datetime
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import openai
import json
from wordcloud import WordCloud
import jieba
import time
from collections import defaultdict

# 设置中文字体
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]

class IncrementalAIAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("增量式AI聊天记录分析工具")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # 数据库配置
        self.db_config = {
            "host": "192.168.1.13",
            "port": 3307,
            "user": "root",
            "password": "123456",
            "database": "xiaozhi_esp32_server",
            "table": "ai_agent_chat_history"
        }
        
        # OpenAI配置
        self.openai_api_key = ""
        self.openai_model = "gpt-3.5-turbo"
        
        # 核心状态管理
        self.conn = None
        self.current_mac = None
        self.processed_ids = defaultdict(int)  # 记录每个MAC已处理的最后一条记录ID {mac: last_id}
        self.analysis_results = defaultdict(dict)  # 存储分析结果 {mac: {维度: 结果}}
        
        # 界面组件
        self._create_widgets()
        self._load_processed_records()  # 加载已处理记录ID
        self._connect_database()
        
    def _create_widgets(self):
        # 主容器
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧MAC区域
        left_frame = ttk.Frame(main_container, width=250)
        main_container.add(left_frame, weight=1)
        
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
        ttk.Button(left_bottom_frame, text="分析新增记录", command=self.analyze_new_records).pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)
        ttk.Button(left_frame, text="设置OpenAI密钥", command=self.set_openai_key).pack(fill=tk.X, padx=5, pady=5)
        
        # 右侧分析结果区域
        right_notebook = ttk.Notebook(main_container)
        main_container.add(right_notebook, weight=4)
        
        # 标签页：聊天记录、热词、心情、健康、经济、购物需求
        self.chat_tab = ttk.Frame(right_notebook)
        self.hotwords_tab = ttk.Frame(right_notebook)
        self.mood_tab = ttk.Frame(right_notebook)
        self.health_tab = ttk.Frame(right_notebook)
        self.economic_tab = ttk.Frame(right_notebook)
        self.shopping_tab = ttk.Frame(right_notebook)
        
        right_notebook.add(self.chat_tab, text="聊天记录")
        right_notebook.add(self.hotwords_tab, text="热词分析")
        right_notebook.add(self.mood_tab, text="心情分析")
        right_notebook.add(self.health_tab, text="健康状况")
        right_notebook.add(self.economic_tab, text="经济情况")
        right_notebook.add(self.shopping_tab, text="购物需求")
        
        # 初始化标签页内容
        self._init_chat_tab()
        self._init_hotwords_tab()
        self._init_analysis_tabs()
        
        # 状态栏
        self.status_var = tk.StringVar(value="未连接数据库")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
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
        self.hotwords_ax1 = self.hotwords_fig.add_subplot(121)  # 柱状图
        self.hotwords_ax2 = self.hotwords_fig.add_subplot(122)  # 词云
        self.hotwords_canvas = FigureCanvasTkAgg(self.hotwords_fig, master=frame)
        self.hotwords_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._reset_hotword_plots()
    
    def _init_analysis_tabs(self):
        # 初始化各分析标签页的文本区域
        self.mood_text = self._create_analysis_text(self.mood_tab)
        self.health_text = self._create_analysis_text(self.health_tab)
        self.economic_text = self._create_analysis_text(self.economic_tab)
        self.shopping_text = self._create_analysis_text(self.shopping_tab)
    
    def _create_analysis_text(self, parent):
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("SimHei", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, "暂无分析结果，请选择MAC并分析新增记录...")
        text.config(state=tk.DISABLED)
        return text
    
    def _load_processed_records(self):
        """加载已处理的记录ID（避免重复分析）"""
        if os.path.exists("processed_records.json"):
            try:
                with open("processed_records.json", "r", encoding="utf-8") as f:
                    self.processed_ids = defaultdict(int, json.load(f))
            except:
                self.processed_ids = defaultdict(int)
    
    def _save_processed_records(self):
        """保存已处理的记录ID"""
        with open("processed_records.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.processed_ids), f, ensure_ascii=False)
    
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
        except Exception as e:
            messagebox.showerror("连接失败", f"数据库错误: {str(e)}")
            self.status_var.set("数据库连接失败")
    
    def refresh_mac_list(self):
        if not self.conn:
            return
        try:
            self.mac_listbox.delete(0, tk.END)
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT DISTINCT mac_address FROM {self.db_config['table']} WHERE mac_address IS NOT NULL ORDER BY mac_address")
                self.all_macs = [mac[0] for mac in cursor.fetchall() if mac[0]]
                for mac in self.all_macs:
                    # 显示已处理状态
                    status = "（已分析）" if self.processed_ids.get(mac, 0) > 0 else ""
                    self.mac_listbox.insert(tk.END, f"{mac} {status}")
            self.status_var.set(f"MAC列表已刷新，共{len(self.all_macs)}个地址")
        except Exception as e:
            messagebox.showerror("错误", f"刷新MAC列表失败: {str(e)}")
    
    def _on_search_changed(self, *args):
        search_text = self.search_var.get().lower()
        self.mac_listbox.delete(0, tk.END)
        filtered = [mac for mac in self.all_macs if search_text in mac.lower()]
        for mac in filtered:
            status = "（已分析）" if self.processed_ids.get(mac, 0) > 0 else ""
            self.mac_listbox.insert(tk.END, f"{mac} {status}")
    
    def on_mac_selected(self, event=None):
        selection = self.mac_listbox.curselection()
        if not selection:
            return
        # 提取MAC地址（去除状态后缀）
        selected_text = self.mac_listbox.get(selection[0])
        self.current_mac = selected_text.split("（")[0].strip()
        self.chat_title.config(text=f"MAC地址: {self.current_mac} 的聊天记录")
        self._load_chat_records()
        self._display_analysis_results()
    
    def _load_chat_records(self):
        """加载该MAC的所有聊天记录（含已分析和未分析）"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT id, content, created_at FROM {self.db_config['table']} "
                    f"WHERE mac_address = %s ORDER BY created_at ASC",
                    (self.current_mac,)
                )
                self.chat_records = cursor.fetchall()  # (id, content, created_at)
                self._display_chat_records()
        except Exception as e:
            messagebox.showerror("错误", f"加载聊天记录失败: {str(e)}")
    
    def _display_chat_records(self):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        if not self.chat_records:
            self.chat_area.insert(tk.END, "该MAC地址无聊天记录")
            self.chat_area.config(state=tk.DISABLED)
            return
        
        last_processed_id = self.processed_ids.get(self.current_mac, 0)
        for record_id, content, created_at in self.chat_records:
            time_str = created_at.strftime("%Y-%m-%d %H:%M") if isinstance(created_at, datetime) else str(created_at)
            # 标记已分析/未分析
            status = "【已分析】" if record_id <= last_processed_id else "【未分析】"
            self.chat_area.insert(tk.END, f"[{time_str}] {status}\n", "time")
            self.chat_area.insert(tk.END, f"{content}\n\n", "content")
        
        self.chat_area.tag_config("time", foreground="#666666", font=("SimHei", 9))
        self.chat_area.tag_config("content", font=("SimHei", 10))
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
    
    def analyze_new_records(self):
        """分析新增的聊天记录（递归分段发送）"""
        if not self.current_mac:
            messagebox.showwarning("提示", "请先选择一个MAC地址")
            return
        if not self.openai_api_key:
            self.set_openai_key()
            if not self.openai_api_key:
                return
        
        # 获取未分析的记录
        last_id = self.processed_ids.get(self.current_mac, 0)
        new_records = [r for r in self.chat_records if r[0] > last_id]
        if not new_records:
            messagebox.showinfo("提示", "无新增记录需要分析")
            return
        
        self.status_var.set(f"开始分析 {self.current_mac} 的新增记录（共{len(new_records)}条）")
        self.root.update()
        
        try:
            # 递归分段发送（每5条一段，避免超过token限制）
            self._recursive_send(new_records, 0, 5)
            # 更新已处理ID
            self.processed_ids[self.current_mac] = max(r[0] for r in new_records)
            self._save_processed_records()
            # 刷新显示
            self.refresh_mac_list()
            self._display_analysis_results()
            self.status_var.set(f"分析完成，已处理{len(new_records)}条新记录")
        except Exception as e:
            messagebox.showerror("分析失败", f"AI分析出错: {str(e)}")
            self.status_var.set("分析失败")
    
    def _recursive_send(self, records, start_idx, batch_size):
        """递归分段发送记录给AI"""
        if start_idx >= len(records):
            return
        
        # 提取当前批次记录
        batch = records[start_idx:start_idx + batch_size]
        batch_content = "\n".join([f"[{r[2]}] {r[1]}" for r in batch])  # (id, content, created_at)
        
        # 调用AI分析
        ai_result = self._call_ai_analysis(batch_content)
        
        # 合并分析结果
        self._merge_analysis_results(ai_result)
        
        # 处理下一批
        self.status_var.set(f"已分析{min(start_idx + batch_size, len(records))}/{len(records)}条记录")
        self.root.update()
        self._recursive_send(records, start_idx + batch_size, batch_size)
    
    def _call_ai_analysis(self, content):
        """调用OpenAI进行分析，使用结构化提示词"""
        openai.api_key = self.openai_api_key
        
        # 核心提示词：定义分析维度和返回格式
        prompt = f"""
        请分析以下聊天记录，提取并总结以下信息，返回JSON格式：
        1. hot_words：热词列表（多个词，按出现频率排序，格式：["词1", "词2"...]，无则返回空列表）
        2. mood：心情分析（一句话总结，无则返回"无"）
        3. health：健康状况（记录提到的身体部位问题，格式：["部位1: 问题", "部位2: 问题"...]，无则返回空列表）
        4. economic：经济情况（一句话总结，无则返回"无"）
        5. shopping_needs：潜在购物需求（多个需求，格式：["需求1", "需求2"...]，无则返回空列表）
        
        注意：
        - 只有明确提到的信息才记录，未提到的维度返回对应"无"或空列表
        - 热词和需求支持多个条目
        - 不要添加额外字段，严格按照上述格式返回JSON
        
        聊天记录：
        {content}
        """
        
        # 调用AI
        response = openai.ChatCompletion.create(
            model=self.openai_model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 解析返回结果
        try:
            return json.loads(response.choices[0].message["content"].strip())
        except:
            raise ValueError("AI返回格式错误，无法解析")
    
    def _merge_analysis_results(self, new_result):
        """合并新分析结果到总结果（去重）"""
        current_results = self.analysis_results.get(self.current_mac, {})
        
        # 合并热词（去重并保持顺序）
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
        
        # 更新结果（心情和经济情况取最新）
        self.analysis_results[self.current_mac] = {
            "hot_words": merged_hot,
            "mood": new_result.get("mood") if new_result.get("mood") != "无" else current_results.get("mood", "无"),
            "health": merged_health,
            "economic": new_result.get("economic") if new_result.get("economic") != "无" else current_results.get("economic", "无"),
            "shopping_needs": merged_shopping
        }
    
    def _display_analysis_results(self):
        """展示分析结果（无信息项不显示）"""
        if not self.current_mac or self.current_mac not in self.analysis_results:
            return
        
        res = self.analysis_results[self.current_mac]
        
        # 热词分析
        self._update_hotword_plots(res["hot_words"])
        
        # 心情分析
        self._update_analysis_text(self.mood_text, "心情分析", res["mood"])
        
        # 健康状况
        self._update_analysis_text(self.health_text, "健康状况", res["health"] if res["health"] else "无提到健康问题")
        
        # 经济情况
        self._update_analysis_text(self.economic_text, "经济情况", res["economic"])
        
        # 购物需求
        self._update_analysis_text(self.shopping_text, "潜在购物需求", 
                                  "\n- ".join(res["shopping_needs"]) if res["shopping_needs"] else "无潜在购物需求")
    
    def _update_hotword_plots(self, hot_words):
        """更新热词图表（柱状图+词云）"""
        self.hotwords_ax1.clear()
        self.hotwords_ax2.clear()
        
        if not hot_words:
            self.hotwords_ax1.text(0.5, 0.5, "无热词信息", ha='center', va='center', transform=self.hotwords_ax1.transAxes)
            self.hotwords_ax2.text(0.5, 0.5, "无热词信息", ha='center', va='center', transform=self.hotwords_ax2.transAxes)
        else:
            # 柱状图（取前10个热词）
            top_words = hot_words[:10]
            counts = list(range(len(top_words), 0, -1))  # 模拟频率（实际可按出现次数）
            self.hotwords_ax1.barh(top_words, counts, color='skyblue')
            self.hotwords_ax1.set_title("热词频率TOP10")
            
            # 词云
            wordcloud = WordCloud(width=400, height=300, background_color='white', font_path=None).generate(" ".join(hot_words))
            self.hotwords_ax2.imshow(wordcloud)
            self.hotwords_ax2.axis('off')
            self.hotwords_ax2.set_title("热词词云")
        
        self.hotwords_fig.tight_layout()
        self.hotwords_canvas.draw()
    
    def _update_analysis_text(self, text_widget, title, content):
        """更新分析文本区域"""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, f"{title}:\n\n", "title")
        if isinstance(content, list) and content:
            text_widget.insert(tk.END, "- " + "\n- ".join(content), "content")
        else:
            text_widget.insert(tk.END, content if content != "无" else "无相关信息", "content")
        text_widget.tag_config("title", font=("SimHei", 10, "bold"))
        text_widget.tag_config("content", font=("SimHei", 10))
        text_widget.config(state=tk.DISABLED)
    
    def _reset_hotword_plots(self):
        """重置热词图表"""
        self.hotwords_ax1.clear()
        self.hotwords_ax2.clear()
        self.hotwords_ax1.text(0.5, 0.5, "请选择MAC并分析新增记录", ha='center', va='center', transform=self.hotwords_ax1.transAxes)
        self.hotwords_ax2.text(0.5, 0.5, "词云将显示在此处", ha='center', va='center', transform=self.hotwords_ax2.transAxes)
        self.hotwords_canvas.draw()
    
    def set_openai_key(self):
        """设置OpenAI密钥"""
        key = simpledialog.askstring("OpenAI配置", "请输入OpenAI API密钥:", show='*')
        if key:
            self.openai_api_key = key
            messagebox.showinfo("配置成功", "OpenAI密钥已保存")

if __name__ == "__main__":
    root = tk.Tk()
    app = IncrementalAIAnalyzer(root)
    root.mainloop()
    