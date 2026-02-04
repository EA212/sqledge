import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import pymysql
from datetime import datetime
import os

class MacChatViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("MAC地址聊天记录查看器")
        self.root.geometry("800x600")
        self.root.minsize(600, 500)
        
        # 数据库配置
        self.db_config = {
            "host": "192.168.1.13",
            "port": 3307,
            "user": "root",
            "password": "123456",
            "database": "xiaozhi_esp32_server",
            "table": "ai_agent_chat_history"
        }
        
        self.conn = None
        self.current_mac = None
        self.chat_records = []
        
        # 创建界面
        self._create_widgets()
        self._connect_database()
        
    def _create_widgets(self):
        # 顶部MAC选择区
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="选择MAC地址:").pack(side=tk.LEFT, padx=5)
        
        self.mac_combobox = ttk.Combobox(top_frame, state="readonly", width=30)
        self.mac_combobox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.mac_combobox.bind("<<ComboboxSelected>>", self.on_mac_selected)
        
        self.refresh_btn = ttk.Button(top_frame, text="刷新列表", command=self.refresh_mac_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        self.export_btn = ttk.Button(top_frame, text="导出为TXT", command=self.export_to_txt, state=tk.DISABLED)
        self.export_btn.pack(side=tk.RIGHT, padx=5)
        
        # 聊天记录显示区（模拟聊天界面）
        chat_frame = ttk.Frame(self.root, padding=10)
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        # 聊天记录标题
        self.chat_title = ttk.Label(chat_frame, text="请选择一个MAC地址查看聊天记录", font=("Arial", 10, "bold"))
        self.chat_title.pack(anchor=tk.W, pady=(0, 10))
        
        # 聊天内容区域
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
            self.mac_combobox['values'] = []
            
            # 查询所有不重复的MAC地址
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT DISTINCT mac_address FROM {self.db_config['table']} WHERE mac_address IS NOT NULL ORDER BY mac_address")
                macs = cursor.fetchall()
                
                # 提取MAC地址列表
                mac_list = [mac[0] for mac in macs if mac[0]]
                
                if mac_list:
                    self.mac_combobox['values'] = mac_list
                    self.status_var.set(f"找到 {len(mac_list)} 个MAC地址")
                else:
                    self.status_var.set("未找到任何MAC地址记录")
                    
        except Exception as e:
            messagebox.showerror("错误", f"获取MAC列表失败: {str(e)}")
    
    def on_mac_selected(self, event=None):
        """当选择MAC地址时加载对应的聊天记录"""
        self.current_mac = self.mac_combobox.get()
        if not self.current_mac:
            return
            
        self.chat_title.config(text=f"MAC地址: {self.current_mac} 的聊天记录")
        self.export_btn.config(state=tk.NORMAL)
        
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
                
                # 显示聊天记录
                self._display_chat_records()
                
                self.status_var.set(f"已加载 {len(self.chat_records)} 条聊天记录")
                
        except Exception as e:
            messagebox.showerror("错误", f"加载聊天记录失败: {str(e)}")
    
    def _display_chat_records(self):
        """在聊天区域显示记录（模拟聊天界面样式）"""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        
        if not self.chat_records:
            self.chat_area.insert(tk.END, "该MAC地址没有聊天记录")
            self.chat_area.config(state=tk.DISABLED)
            return
            
        # 格式化显示每条记录
        for content, created_at in self.chat_records:
            # 格式化时间
            time_str = created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_at, datetime) else str(created_at)
            
            # 聊天记录样式（时间 + 内容）
            self.chat_area.insert(tk.END, f"[{time_str}]\n", "time")
            self.chat_area.insert(tk.END, f"{content}\n\n", "content")
        
        # 设置文本样式
        self.chat_area.tag_config("time", foreground="#666666", font=("SimHei", 9))
        self.chat_area.tag_config("content", font=("SimHei", 10))
        
        # 滚动到底部
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
    
    def export_to_txt(self):
        """将当前MAC地址的聊天记录导出为TXT文件"""
        if not self.current_mac or not self.chat_records:
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
                f.write("=" * 50 + "\n\n")
                
                for content, created_at in self.chat_records:
                    time_str = created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_at, datetime) else str(created_at)
                    f.write(f"[{time_str}]\n")
                    f.write(f"{content}\n\n")
            
            messagebox.showinfo("导出成功", f"聊天记录已成功导出到:\n{file_path}")
            self.status_var.set(f"聊天记录已导出到 {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("导出失败", f"保存文件时出错: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MacChatViewer(root)
    root.mainloop()
    