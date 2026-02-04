import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import pymysql
from datetime import datetime, date
import os
from collections import defaultdict

class MacChatViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("MAC地址聊天记录查看器")
        self.root.geometry("1000x600")
        self.root.minsize(800, 500)
        
        # 数据库配置
        self.db_config = {
            "host": "192.168.1.13",
            "port": 8306,
            "user": "root",
            "password": "123456",
            "database": "xiaozhi_esp32_server",
            "table": "ai_agent_chat_history"
        }
        
        self.conn = None
        self.current_mac = None
        self.chat_records = []  # 所有记录
        self.date_grouped_records = defaultdict(list)  # 按日期分组的记录
        self.all_macs = []  # 存储所有mac地址
        self.date_positions = {}  # 存储每个日期在文本框中的位置
        
        # 创建界面
        self._create_widgets()
        self._connect_database()
        
    def _create_widgets(self):
        # 主容器
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧MAC地址区域
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
        
        # MAC列表滚动条
        self.mac_scrollbar = ttk.Scrollbar(self.mac_frame)
        self.mac_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # MAC列表框
        self.mac_listbox = tk.Listbox(
            self.mac_frame, 
            yscrollcommand=self.mac_scrollbar.set,
            selectmode=tk.SINGLE,
            font=("SimHei", 10)
        )
        self.mac_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.mac_scrollbar.config(command=self.mac_listbox.yview)
        
        # 绑定列表点击事件
        self.mac_listbox.bind('<<ListboxSelect>>', self.on_mac_selected)
        
        # 左侧底部按钮
        left_bottom_frame = ttk.Frame(left_frame, padding=5)
        left_bottom_frame.pack(fill=tk.X)
        
        ttk.Button(left_bottom_frame, text="刷新列表", command=self.refresh_mac_list).pack(fill=tk.X)
        
        # 右侧聊天区域
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=3)
        
        # 右侧顶部 - 标题和操作区
        right_top_frame = ttk.Frame(right_frame, padding=5)
        right_top_frame.pack(fill=tk.X)
        
        self.chat_title = ttk.Label(right_top_frame, text="请选择一个MAC地址查看聊天记录", font=("Arial", 10, "bold"))
        self.chat_title.pack(side=tk.LEFT, padx=5)
        
        # 日期选择下拉框
        date_frame = ttk.Frame(right_top_frame)
        date_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(date_frame, text="选择日期:").pack(side=tk.LEFT, padx=5)
        self.date_combobox = ttk.Combobox(date_frame, state="readonly", width=12)
        self.date_combobox.pack(side=tk.LEFT)
        self.date_combobox.bind("<<ComboboxSelected>>", self.on_date_selected)
        
        ttk.Button(right_top_frame, text="导出为TXT", command=self.export_to_txt).pack(side=tk.RIGHT, padx=5)
        
        # 聊天内容区域
        chat_frame = ttk.Frame(right_frame, padding=5)
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chat_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=("SimHei", 10))
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        self.chat_area.config(state=tk.DISABLED)  # 初始为只读
        
        # 状态栏
        self.status_var = tk.StringVar(value="未连接数据库")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def _connect_database(self):
        """连接数据库并加载MAC地址列表"""
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
            self.status_var.set(f"已连接到 {self.db_config['database']}")
            
        except Exception as e:
            messagebox.showerror("连接失败", f"数据库连接错误: {str(e)}")
            self.status_var.set("数据库连接失败")
    
    def refresh_mac_list(self):
        """刷新MAC地址列表"""
        if not self.conn:
            return
            
        try:
            # 清空现有列表
            self.mac_listbox.delete(0, tk.END)
            self.all_macs = []
            
            # 查询所有不重复的MAC地址
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT DISTINCT mac_address FROM {self.db_config['table']} WHERE mac_address IS NOT NULL ORDER BY mac_address")
                macs = cursor.fetchall()
                
                # 提取MAC地址列表
                self.all_macs = [mac[0] for mac in macs if mac[0]]
                
                # 添加到列表框
                for mac in self.all_macs:
                    self.mac_listbox.insert(tk.END, mac)
                
                self.status_var.set(f"找到 {len(self.all_macs)} 个MAC地址")
                
        except Exception as e:
            messagebox.showerror("错误", f"获取MAC列表失败: {str(e)}")
    
    def _on_search_changed(self, *args):
        """处理搜索框内容变化，实现模糊搜索"""
        search_text = self.search_var.get().lower()
        
        # 清空列表
        self.mac_listbox.delete(0, tk.END)
        
        # 过滤并显示匹配的MAC地址
        if search_text:
            filtered_macs = [mac for mac in self.all_macs if search_text in mac.lower()]
            for mac in filtered_macs:
                self.mac_listbox.insert(tk.END, mac)
            self.status_var.set(f"搜索到 {len(filtered_macs)} 个匹配的MAC地址")
        else:
            # 搜索为空时显示所有MAC
            for mac in self.all_macs:
                self.mac_listbox.insert(tk.END, mac)
            self.status_var.set(f"找到 {len(self.all_macs)} 个MAC地址")
    
    def on_mac_selected(self, event=None):
        """当选择MAC地址时加载对应的聊天记录"""
        selection = self.mac_listbox.curselection()
        if not selection:
            return
            
        self.current_mac = self.mac_listbox.get(selection[0])
        if not self.current_mac:
            return
            
        self.chat_title.config(text=f"MAC地址: {self.current_mac} 的聊天记录")
        
        # 加载聊天记录
        try:
            with self.conn.cursor() as cursor:
                # 按时间升序查询该MAC的所有聊天记录
                cursor.execute(
                    f"SELECT content, created_at FROM {self.db_config['table']} "
                    f"WHERE mac_address = %s ORDER BY created_at ASC",
                    (self.current_mac,)
                )
                self.chat_records = cursor.fetchall()
                
                # 按日期分组
                self.date_grouped_records = defaultdict(list)
                for content, created_at in self.chat_records:
                    if isinstance(created_at, datetime):
                        record_date = created_at.date()
                    else:
                        try:
                            # 尝试解析字符串格式的时间
                            dt = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S.%f")
                            record_date = dt.date()
                        except:
                            record_date = date.today()
                            
                    self.date_grouped_records[record_date].append((content, created_at))
                
                # 更新日期选择下拉框
                self._update_date_combobox()
                
                # 显示聊天记录
                self._display_chat_records()
                
                self.status_var.set(f"已加载 {len(self.chat_records)} 条聊天记录，分布在 {len(self.date_grouped_records)} 天")
                
        except Exception as e:
            messagebox.showerror("错误", f"加载聊天记录失败: {str(e)}")
    
    def _update_date_combobox(self):
        """更新日期选择下拉框"""
        # 清空现有选项
        self.date_combobox['values'] = []
        
        # 添加日期选项
        dates = sorted(self.date_grouped_records.keys(), reverse=True)  # 最新的日期在前面
        date_strings = [d.strftime("%Y-%m-%d") for d in dates]
        
        if date_strings:
            self.date_combobox['values'] = date_strings
            # 默认选中第一个（最新的日期）
            self.date_combobox.current(0)
    
    def on_date_selected(self, event=None):
        """跳转到选中日期的记录"""
        selected_date_str = self.date_combobox.get()
        if not selected_date_str:
            return
            
        # 查找该日期在文本框中的位置并滚动过去
        if selected_date_str in self.date_positions:
            position = self.date_positions[selected_date_str]
            self.chat_area.see(position)
            # 高亮显示日期行
            self.chat_area.tag_remove("highlight", 1.0, tk.END)
            self.chat_area.tag_add("highlight", position, f"{position}+1l")
    
    def _display_chat_records(self):
        """在聊天区域显示记录，按日期分割"""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        self.date_positions = {}  # 重置日期位置记录
        
        # 清除之前的标签配置
        self.chat_area.tag_remove("date", 1.0, tk.END)
        self.chat_area.tag_remove("time", 1.0, tk.END)
        self.chat_area.tag_remove("content", 1.0, tk.END)
        self.chat_area.tag_remove("highlight", 1.0, tk.END)
        
        if not self.date_grouped_records:
            self.chat_area.insert(tk.END, "该MAC地址没有聊天记录")
            self.chat_area.config(state=tk.DISABLED)
            return
        
        # 按日期降序显示（最新的日期在前面）
        for record_date in sorted(self.date_grouped_records.keys(), reverse=True):
            date_str = record_date.strftime("%Y-%m-%d")
            
            # 记录当前插入位置（日期行的位置）
            current_position = self.chat_area.index(tk.END)
            self.date_positions[date_str] = current_position
            
            # 添加日期分割线
            self.chat_area.insert(tk.END, f"==================== {date_str} ====================\n", "date")
            
            # 添加当天的记录
            for content, created_at in self.date_grouped_records[record_date]:
                # 格式化时间
                if isinstance(created_at, datetime):
                    time_str = created_at.strftime("%H:%M:%S")
                else:
                    try:
                        dt = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S.%f")
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = "未知时间"
                
                # 聊天记录样式（时间 + 内容）
                self.chat_area.insert(tk.END, f"[{time_str}]  ", "time")
                self.chat_area.insert(tk.END, f"{content}\n", "content")
            
            # 每天的记录之间添加空行
            self.chat_area.insert(tk.END, "\n")
        
        # 设置文本样式
        self.chat_area.tag_config("date", foreground="#FFFFFF", background="#3498db", 
                                 font=("SimHei", 10, "bold"), justify=tk.CENTER)
        self.chat_area.tag_config("time", foreground="#666666", font=("SimHei", 9))
        self.chat_area.tag_config("content", font=("SimHei", 10))
        self.chat_area.tag_config("highlight", background="#ffffcc")  # 日期选中高亮
        
        # 滚动到底部
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
    
    def export_to_txt(self):
        """将当前MAC地址的聊天记录导出为TXT文件"""
        if not self.current_mac or not self.chat_records:
            messagebox.showwarning("提示", "请先选择一个有聊天记录的MAC地址")
            return
            
        # 提示保存路径
        default_filename = f"chat_history_{self.current_mac.replace(':', '-')}_{datetime.now().strftime('%Y%m%d')}.txt"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=default_filename
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"MAC地址: {self.current_mac} 的聊天记录\n")
                f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"记录总数: {len(self.chat_records)}\n")
                f.write(f"日期范围: {min(self.date_grouped_records.keys()).strftime('%Y-%m-%d')} 至 {max(self.date_grouped_records.keys()).strftime('%Y-%m-%d')}\n")
                f.write("=" * 80 + "\n\n")
                
                # 按日期导出
                for record_date in sorted(self.date_grouped_records.keys(), reverse=True):
                    date_str = record_date.strftime("%Y-%m-%d")
                    f.write(f"==================== {date_str} ====================\n\n")
                    
                    for content, created_at in self.date_grouped_records[record_date]:
                        if isinstance(created_at, datetime):
                            time_str = created_at.strftime("%H:%M:%S")
                        else:
                            time_str = "未知时间"
                            
                        f.write(f"[{time_str}]  {content}\n")
                    
                    f.write("\n")
            
            messagebox.showinfo("导出成功", f"聊天记录已成功导出到:\n{file_path}")
            self.status_var.set(f"聊天记录已导出到 {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("导出失败", f"保存文件时出错: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MacChatViewer(root)
    root.mainloop()
