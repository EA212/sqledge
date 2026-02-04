import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import pymysql
from matplotlib.figure import Figure
import numpy as np

# 设置中文字体支持
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]

class ESP32DataBrowser:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Server 数据库浏览器")
        self.root.geometry("1400x800")
        
        # 数据库连接参数
        self.db_config = {
            "host": "192.168.1.13",
            "port": 3307,
            "user": "root",
            "password": "123456",
            "database": "xiaozhi_esp32_server"
        }
        
        # 数据库连接对象
        self.conn = None
        self.current_table = None
        self.df = None
        
        # 创建界面布局
        self._create_layout()
        
    def _create_layout(self):
        # 顶部控制区
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)
        
        ttk.Button(top_frame, text="连接数据库", command=self.connect_database).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="刷新数据", command=self.refresh_data).pack(side=tk.LEFT, padx=5)
        self.status_var = tk.StringVar(value="未连接数据库")
        ttk.Label(top_frame, textvariable=self.status_var).pack(side=tk.RIGHT, padx=20)
        
        # 主内容区
        main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左侧表结构树
        left_frame = ttk.Frame(main_frame, width=250)
        main_frame.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="数据库表结构", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        # 表结构树
        self.tree = ttk.Treeview(left_frame)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_table_select)
        
        # 右侧数据展示区
        right_frame = ttk.Frame(main_frame)
        main_frame.add(right_frame, weight=4)
        
        # 右侧顶部控制
        right_top_frame = ttk.Frame(right_frame)
        right_top_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(right_top_frame, text="表数据:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.table_name_var = tk.StringVar(value="未选择表")
        ttk.Label(right_top_frame, textvariable=self.table_name_var).pack(side=tk.LEFT, padx=10)
        ttk.Button(right_top_frame, text="生成图表", command=self.generate_chart).pack(side=tk.RIGHT, padx=10)
        
        # 数据表格
        table_frame = ttk.Frame(right_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        self.data_tree = ttk.Treeview(table_frame)
        self.data_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.data_tree.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x = ttk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.data_tree.xview)
        scrollbar_x.pack(fill=tk.X)
        
        self.data_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 图表展示区
        self.chart_frame = ttk.LabelFrame(right_frame, text="数据图表")
        self.chart_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.chart_placeholder = ttk.Label(self.chart_frame, text="选择表并点击生成图表")
        self.chart_placeholder.pack(fill=tk.BOTH, expand=True)
        
    def connect_database(self):
        """连接数据库并加载表结构"""
        try:
            self.conn = pymysql.connect(
                host=self.db_config["host"],
                port=self.db_config["port"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
                charset="utf8mb4"
            )
            
            # 清空树
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            # 添加数据库节点
            db_node = self.tree.insert("", tk.END, text=self.db_config["database"], open=True)
            
            # 获取所有表
            with self.conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    self.tree.insert(db_node, tk.END, text=table_name, tags=("table",))
                
            self.status_var.set(f"已连接到 {self.db_config['database']}")
            messagebox.showinfo("成功", "数据库连接成功")
            
        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {str(e)}")
            self.status_var.set("连接失败")
    
    def refresh_data(self):
        """刷新数据"""
        if not self.conn:
            messagebox.showwarning("警告", "请先连接数据库")
            return
            
        # 重新加载表结构
        self.connect_database()
        
        # 如果有选中的表，重新加载数据
        if self.current_table:
            self.load_table_data(self.current_table)
    
    def on_table_select(self, event):
        """当选择表时加载数据"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = selection[0]
        table_name = self.tree.item(item, "text")
        
        # 检查是否是表节点
        if "table" in self.tree.item(item, "tags"):
            self.current_table = table_name
            self.table_name_var.set(table_name)
            self.load_table_data(table_name)
    
    def load_table_data(self, table_name):
        """加载指定表的数据"""
        try:
            # 清空数据表格
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
            
            # 获取表结构
            with self.conn.cursor() as cursor:
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                column_names = [col[0] for col in columns]
                
                # 设置数据表格列
                self.data_tree["columns"] = column_names
                for col in column_names:
                    self.data_tree.heading(col, text=col)
                    self.data_tree.column(col, width=100)
                
                # 获取表数据（限制前100行）
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 100")
                data = cursor.fetchall()
                
                # 填充数据
                for row in data:
                    self.data_tree.insert("", tk.END, values=row)
                
                # 保存为DataFrame用于图表生成
                self.df = pd.DataFrame(data, columns=column_names)
                
            # 清空图表区
            for widget in self.chart_frame.winfo_children():
                widget.destroy()
            ttk.Label(self.chart_frame, text="选择表并点击生成图表").pack(fill=tk.BOTH, expand=True)
            
        except Exception as e:
            messagebox.showerror("错误", f"加载数据失败: {str(e)}")
    
    def generate_chart(self):
        """根据当前表数据生成图表"""
        if not self.current_table or self.df is None:
            messagebox.showwarning("警告", "请先选择表并加载数据")
            return
            
        # 清空图表区
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        # 根据不同表生成不同图表
        try:
            fig = Figure(figsize=(8, 4), dpi=100)
            
            if self.current_table == "ai_agent_chat_history":
                # 聊天记录表：按MAC地址统计对话次数
                if "mac_address" in self.df.columns:
                    ax = fig.add_subplot(111)
                    mac_counts = self.df["mac_address"].value_counts()
                    mac_counts.plot(kind="bar", ax=ax)
                    ax.set_title("各MAC地址对话次数统计")
                    ax.set_xlabel("MAC地址")
                    ax.set_ylabel("对话次数")
                    plt.xticks(rotation=45, ha="right")
            
            elif self.current_table in ["ai_device", "sys_user"]:
                # 设备表/用户表：简单统计
                if "status" in self.df.columns:
                    ax = fig.add_subplot(111)
                    status_counts = self.df["status"].value_counts()
                    status_counts.plot(kind="pie", ax=ax, autopct='%1.1f%%')
                    ax.set_title("设备/用户状态分布")
            
            else:
                # 通用：记录数时间分布（如果有时间字段）
                time_columns = [col for col in self.df.columns if "time" in col or "date" in col or "created" in col]
                if time_columns:
                    ax = fig.add_subplot(111)
                    time_col = time_columns[0]
                    # 尝试转换为日期时间
                    try:
                        self.df[time_col] = pd.to_datetime(self.df[time_col])
                        self.df[time_col].dt.date.value_counts().sort_index().plot(kind="line", ax=ax)
                        ax.set_title(f"记录数按{time_col}分布")
                        ax.set_xlabel("日期")
                        ax.set_ylabel("记录数")
                        plt.xticks(rotation=45, ha="right")
                    except:
                        pass
            
            # 如果没有生成特定图表，显示记录数统计
            if not fig.axes:
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, f"表 {self.current_table} 包含 {len(self.df)} 条记录", 
                        horizontalalignment='center', verticalalignment='center',
                        transform=ax.transAxes, fontsize=12)
                ax.set_title("表数据统计")
            
            # 显示图表
            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
        except Exception as e:
            messagebox.showerror("错误", f"生成图表失败: {str(e)}")
            ttk.Label(self.chart_frame, text="生成图表失败").pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    root = tk.Tk()
    app = ESP32DataBrowser(root)
    root.mainloop()
