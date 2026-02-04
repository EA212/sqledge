import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import platform

try:
    import pandas as pd
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

from db_operations import DatabaseOperations

class DatabaseTool:
    def __init__(self, root):
        self.root = root
        self.root.title("数据库管理与同步工具")
        self.root.geometry("1400x800")
        self.root.minsize(1200, 700)
        
        # 确保中文显示正常
        self.setup_fonts()
        
        # 数据库操作工具
        self.db_ops = DatabaseOperations()
        
        # 连接配置
        self.connections = {}  # 保存可复用的连接配置
        self.active_connection = {"source": None, "target": None}
        self.connection_file = "connections.json"
        
        # 创建界面组件
        self.create_widgets()
        
        # 加载连接配置
        self.load_connections()

    def setup_fonts(self):
        """设置字体以确保中文显示正常"""
        system = platform.system()
        if system == "Windows":
            self.default_font = ("SimHei", 10)
        elif system == "Darwin":  # macOS
            self.default_font = ("Heiti TC", 10)
        else:  # Linux等其他系统
            self.default_font = ("WenQuanYi Micro Hei", 10)

    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建菜单栏
        self.create_menu()
        
        # 状态标签
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.source_status_var = tk.StringVar(value="源数据库: 未连接")
        self.target_status_var = tk.StringVar(value="目标数据库: 未连接")
        
        ttk.Label(status_frame, textvariable=self.source_status_var, font=self.default_font).pack(side=tk.LEFT, padx=10)
        ttk.Label(status_frame, textvariable=self.target_status_var, font=self.default_font).pack(side=tk.LEFT, padx=10)
        
        # 操作按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="加载源数据库数据", command=self.load_source_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="同步到目标数据库", command=self.sync_to_target).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="加载目标数据库数据", command=self.load_target_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空目标表数据", command=self.clear_target_table).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑字段备注", command=self.edit_field_notes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出源数据", command=lambda: self.export_data("source")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出目标数据", command=lambda: self.export_data("target")).pack(side=tk.LEFT, padx=5)
        
        # 数据展示区域 - 使用Notebook创建分页视图，解决表格显示问题
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 源数据库数据表格页
        source_frame = ttk.Frame(notebook)
        notebook.add(source_frame, text="源数据库数据")
        
        ttk.Label(source_frame, text="源数据库 - ai_device 表数据", 
                 font=(self.default_font[0], 12, "bold")).pack(anchor=tk.W, pady=(5, 5))
        
        # 源数据表格容器
        source_table_frame = ttk.Frame(source_frame)
        source_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 源表格滚动条
        source_scroll_x = ttk.Scrollbar(source_table_frame, orient=tk.HORIZONTAL)
        source_scroll_y = ttk.Scrollbar(source_table_frame, orient=tk.VERTICAL)
        
        self.source_tree = ttk.Treeview(
            source_table_frame,
            columns=[],
            show="headings",
            yscrollcommand=source_scroll_y.set,
            xscrollcommand=source_scroll_x.set,
            selectmode="extended"
        )
        
        source_scroll_y.config(command=self.source_tree.yview)
        source_scroll_x.config(command=self.source_tree.xview)
        
        # 网格布局放置表格和滚动条
        self.source_tree.grid(row=0, column=0, sticky=tk.NSEW)
        source_scroll_y.grid(row=0, column=1, sticky=tk.NS)
        source_scroll_x.grid(row=1, column=0, sticky=tk.EW)
        
        # 设置权重，使表格可以随窗口拉伸
        source_table_frame.rowconfigure(0, weight=1)
        source_table_frame.columnconfigure(0, weight=1)
        
        # 目标数据库数据表格页
        target_frame = ttk.Frame(notebook)
        notebook.add(target_frame, text="目标数据库数据")
        
        ttk.Label(target_frame, text="目标数据库 - 同步后的数据", 
                 font=(self.default_font[0], 12, "bold")).pack(anchor=tk.W, pady=(5, 5))
        
        # 目标数据表格容器
        target_table_frame = ttk.Frame(target_frame)
        target_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 目标表格滚动条
        target_scroll_x = ttk.Scrollbar(target_table_frame, orient=tk.HORIZONTAL)
        target_scroll_y = ttk.Scrollbar(target_table_frame, orient=tk.VERTICAL)
        
        self.target_tree = ttk.Treeview(
            target_table_frame,
            columns=[],
            show="headings",
            yscrollcommand=target_scroll_y.set,
            xscrollcommand=target_scroll_x.set,
            selectmode="extended"
        )
        
        # 目标表格支持双击编辑
        self.target_tree.bind("<Double-1>", self.edit_target_cell)
        
        target_scroll_y.config(command=self.target_tree.yview)
        target_scroll_x.config(command=self.target_tree.xview)
        
        # 网格布局放置表格和滚动条
        self.target_tree.grid(row=0, column=0, sticky=tk.NSEW)
        target_scroll_y.grid(row=0, column=1, sticky=tk.NS)
        target_scroll_x.grid(row=1, column=0, sticky=tk.EW)
        
        # 设置权重
        target_table_frame.rowconfigure(0, weight=1)
        target_table_frame.columnconfigure(0, weight=1)

    def create_menu(self):
        # 创建菜单栏
        menubar = tk.Menu(self.root)
        
        # 数据库连接菜单
        db_menu = tk.Menu(menubar, tearoff=0)
        
        # 源数据库子菜单
        source_menu = tk.Menu(db_menu, tearoff=0)
        source_menu.add_command(label="新建源数据库连接", command=lambda: self.create_new_connection("source"))
        source_menu.add_separator()
        self.source_conn_menu = tk.Menu(source_menu, tearoff=0)
        source_menu.add_cascade(label="选择源数据库连接", menu=self.source_conn_menu)
        source_menu.add_command(label="断开源数据库连接", command=lambda: self.disconnect_database("source"))
        
        # 目标数据库子菜单
        target_menu = tk.Menu(db_menu, tearoff=0)
        target_menu.add_command(label="新建目标数据库连接", command=lambda: self.create_new_connection("target"))
        target_menu.add_separator()
        self.target_conn_menu = tk.Menu(target_menu, tearoff=0)
        target_menu.add_cascade(label="选择目标数据库连接", menu=self.target_conn_menu)
        target_menu.add_command(label="断开目标数据库连接", command=lambda: self.disconnect_database("target"))
        
        db_menu.add_cascade(label="源数据库", menu=source_menu)
        db_menu.add_cascade(label="目标数据库", menu=target_menu)
        db_menu.add_separator()
        db_menu.add_command(label="管理连接配置", command=self.manage_connections)
        
        # 添加菜单到菜单栏
        menubar.add_cascade(label="数据库", menu=db_menu)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self.show_about)
        help_menu.add_command(label="使用帮助", command=self.show_help)
        menubar.add_cascade(label="帮助", menu=help_menu)
        
        # 设置菜单栏
        self.root.config(menu=menubar)

    def create_new_connection(self, conn_type):
        """创建新的数据库连接配置"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"新建{('源' if conn_type == 'source' else '目标')}数据库连接")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        dialog.geometry(f"+{x}+{y}")
        
        # 连接名称
        ttk.Label(dialog, text="连接名称:", font=self.default_font).grid(row=0, column=0, sticky=tk.W, pady=8, padx=20)
        name_var = tk.StringVar(value=f"{('源' if conn_type == 'source' else '目标')}数据库连接")
        ttk.Entry(dialog, textvariable=name_var, width=30).grid(row=0, column=1, pady=8)
        
        # 主机
        ttk.Label(dialog, text="主机地址:", font=self.default_font).grid(row=1, column=0, sticky=tk.W, pady=5, padx=20)
        host_var = tk.StringVar(value="192.168.1.13")
        ttk.Entry(dialog, textvariable=host_var, width=30).grid(row=1, column=1, pady=5)
        
        # 端口
        ttk.Label(dialog, text="端口:", font=self.default_font).grid(row=2, column=0, sticky=tk.W, pady=5, padx=20)
        port_var = tk.StringVar(value="3307")
        ttk.Entry(dialog, textvariable=port_var, width=30).grid(row=2, column=1, pady=5)
        
        # 用户名
        ttk.Label(dialog, text="用户名:", font=self.default_font).grid(row=3, column=0, sticky=tk.W, pady=5, padx=20)
        user_var = tk.StringVar(value="root")
        ttk.Entry(dialog, textvariable=user_var, width=30).grid(row=3, column=1, pady=5)
        
        # 密码
        ttk.Label(dialog, text="密码:", font=self.default_font).grid(row=4, column=0, sticky=tk.W, pady=5, padx=20)
        pass_var = tk.StringVar(value="123456")
        ttk.Entry(dialog, textvariable=pass_var, show="*", width=30).grid(row=4, column=1, pady=5)
        
        # 数据库名
        ttk.Label(dialog, text="数据库名:", font=self.default_font).grid(row=5, column=0, sticky=tk.W, pady=5, padx=20)
        db_var = tk.StringVar(value="xiaozhi_esp32_server" if conn_type == "source" else "aintech-hoster")
        ttk.Entry(dialog, textvariable=db_var, width=30).grid(row=5, column=1, pady=5)
        
        # 按钮
        def save_connection():
            conn_name = name_var.get().strip()
            if not conn_name:
                messagebox.showwarning("输入错误", "连接名称不能为空")
                return
                
            if conn_name in self.connections:
                if not messagebox.askyesno("确认覆盖", f"连接 '{conn_name}' 已存在，是否覆盖？"):
                    return
            
            # 保存连接配置
            self.connections[conn_name] = {
                "type": conn_type,
                "host": host_var.get(),
                "port": port_var.get(),
                "user": user_var.get(),
                "password": pass_var.get(),
                "database": db_var.get()
            }
            
            # 保存到文件
            self.save_connections()
            
            # 更新菜单
            self.update_connection_menus()
            
            # 询问是否立即连接
            if messagebox.askyesno("连接提示", f"是否立即使用 '{conn_name}' 连接？"):
                self.connect_to_database(conn_type, conn_name)
                
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=15)
        
        ttk.Button(btn_frame, text="保存", command=save_connection).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def update_connection_menus(self):
        """更新连接菜单"""
        # 清空现有菜单
        for item in self.source_conn_menu.winfo_children():
            self.source_conn_menu.delete(item)
        
        for item in self.target_conn_menu.winfo_children():
            self.target_conn_menu.delete(item)
        
        # 按类型添加连接
        source_connections = [name for name, conn in self.connections.items() if conn["type"] == "source"]
        target_connections = [name for name, conn in self.connections.items() if conn["type"] == "target"]
        
        # 添加源数据库连接
        if not source_connections:
            self.source_conn_menu.add_command(label="无可用连接", state="disabled")
        else:
            for name in source_connections:
                # 使用默认参数方式传递当前name值，修复变量引用问题
                self.source_conn_menu.add_command(
                    label=name,
                    command=lambda n=name: self.connect_to_database("source", n)
                )
        
        # 添加目标数据库连接
        if not target_connections:
            self.target_conn_menu.add_command(label="无可用连接", state="disabled")
        else:
            for name in target_connections:
                self.target_conn_menu.add_command(
                    label=name,
                    command=lambda n=name: self.connect_to_database("target", n)
                )

    def connect_to_database(self, conn_type, conn_name):
        """连接到指定的数据库"""
        if conn_name not in self.connections:
            messagebox.showerror("错误", f"连接 '{conn_name}' 不存在")
            return
            
        conn_info = self.connections[conn_name]
        
        # 调用数据库操作类的连接方法
        if conn_type == "source":
            success, msg = self.db_ops.connect_source_db(
                conn_info["host"],
                conn_info["port"],
                conn_info["user"],
                conn_info["password"],
                conn_info["database"]
            )
            if success:
                self.active_connection["source"] = conn_name
                self.source_status_var.set(f"源数据库: 已连接到 {conn_name}")
        else:
            success, msg = self.db_ops.connect_target_db(
                conn_info["host"],
                conn_info["port"],
                conn_info["user"],
                conn_info["password"],
                conn_info["database"]
            )
            if success:
                self.active_connection["target"] = conn_name
                self.target_status_var.set(f"目标数据库: 已连接到 {conn_name}")
        
        # 更新菜单
        self.update_connection_menus()
        
        # 显示结果
        if success:
            messagebox.showinfo("连接成功", msg)
        else:
            messagebox.showerror("连接失败", msg)

    def disconnect_database(self, conn_type):
        """断开数据库连接"""
        if conn_type == "source":
            self.active_connection["source"] = None
            self.source_status_var.set("源数据库: 未连接")
        else:
            self.active_connection["target"] = None
            self.target_status_var.set("目标数据库: 未连接")
        
        # 调用数据库操作类的断开连接方法
        self.db_ops.close_connections()
        
        # 更新菜单
        self.update_connection_menus()
        messagebox.showinfo("已断开连接", f"{('源' if conn_type == 'source' else '目标')}数据库连接已断开")

    def manage_connections(self):
        """管理数据库连接配置"""
        dialog = tk.Toplevel(self.root)
        dialog.title("管理数据库连接")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 连接列表
        ttk.Label(dialog, text="保存的数据库连接:", font=(self.default_font[0], 10, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 列表框
        self.conn_listbox = tk.Listbox(frame, font=self.default_font, width=50, height=15)
        self.conn_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.conn_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.conn_listbox.config(yscrollcommand=scrollbar.set)
        
        # 刷新列表
        self.refresh_conn_listbox()
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="新建连接", command=lambda: [dialog.destroy(), self.create_new_connection("source")]).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="编辑连接", command=lambda: self.edit_connection(dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除连接", command=self.delete_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def refresh_conn_listbox(self):
        """刷新连接列表框"""
        self.conn_listbox.delete(0, tk.END)
        for name, conn in self.connections.items():
            conn_type = "源数据库" if conn["type"] == "source" else "目标数据库"
            self.conn_listbox.insert(tk.END, f"{name} ({conn_type})")

    def edit_connection(self, parent_dialog):
        """编辑选中的连接"""
        selected = self.conn_listbox.curselection()
        if not selected:
            messagebox.showwarning("未选择", "请先选择一个连接")
            return
            
        selected_text = self.conn_listbox.get(selected[0])
        conn_name = selected_text.split(" (")[0]
        
        if conn_name not in self.connections:
            return
            
        conn_info = self.connections[conn_name]
        
        # 关闭管理窗口
        parent_dialog.destroy()
        
        # 打开编辑连接窗口
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑连接: {conn_name}")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 连接名称
        ttk.Label(dialog, text="连接名称:", font=self.default_font).grid(row=0, column=0, sticky=tk.W, pady=8, padx=20)
        name_var = tk.StringVar(value=conn_name)
        ttk.Entry(dialog, textvariable=name_var, width=30).grid(row=0, column=1, pady=8)
        
        # 主机
        ttk.Label(dialog, text="主机地址:", font=self.default_font).grid(row=1, column=0, sticky=tk.W, pady=5, padx=20)
        host_var = tk.StringVar(value=conn_info["host"])
        ttk.Entry(dialog, textvariable=host_var, width=30).grid(row=1, column=1, pady=5)
        
        # 端口
        ttk.Label(dialog, text="端口:", font=self.default_font).grid(row=2, column=0, sticky=tk.W, pady=5, padx=20)
        port_var = tk.StringVar(value=conn_info["port"])
        ttk.Entry(dialog, textvariable=port_var, width=30).grid(row=2, column=1, pady=5)
        
        # 用户名
        ttk.Label(dialog, text="用户名:", font=self.default_font).grid(row=3, column=0, sticky=tk.W, pady=5, padx=20)
        user_var = tk.StringVar(value=conn_info["user"])
        ttk.Entry(dialog, textvariable=user_var, width=30).grid(row=3, column=1, pady=5)
        
        # 密码
        ttk.Label(dialog, text="密码:", font=self.default_font).grid(row=4, column=0, sticky=tk.W, pady=5, padx=20)
        pass_var = tk.StringVar(value=conn_info["password"])
        ttk.Entry(dialog, textvariable=pass_var, show="*", width=30).grid(row=4, column=1, pady=5)
        
        # 数据库名
        ttk.Label(dialog, text="数据库名:", font=self.default_font).grid(row=5, column=0, sticky=tk.W, pady=5, padx=20)
        db_var = tk.StringVar(value=conn_info["database"])
        ttk.Entry(dialog, textvariable=db_var, width=30).grid(row=5, column=1, pady=5)
        
        # 连接类型（不可编辑）
        ttk.Label(dialog, text="连接类型:", font=self.default_font).grid(row=6, column=0, sticky=tk.W, pady=5, padx=20)
        type_var = tk.StringVar(value="源数据库" if conn_info["type"] == "source" else "目标数据库")
        ttk.Label(dialog, textvariable=type_var, font=self.default_font).grid(row=6, column=1, sticky=tk.W, pady=5)
        
        # 按钮
        def save_edited_connection():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("输入错误", "连接名称不能为空")
                return
                
            # 如果名称改变且新名称已存在
            if new_name != conn_name and new_name in self.connections:
                if not messagebox.askyesno("确认覆盖", f"连接 '{new_name}' 已存在，是否覆盖？"):
                    return
            
            # 删除旧连接
            del self.connections[conn_name]
            
            # 保存新连接配置
            self.connections[new_name] = {
                "type": conn_info["type"],
                "host": host_var.get(),
                "port": port_var.get(),
                "user": user_var.get(),
                "password": pass_var.get(),
                "database": db_var.get()
            }
            
            # 更新活动连接引用
            if self.active_connection["source"] == conn_name:
                self.active_connection["source"] = new_name
            if self.active_connection["target"] == conn_name:
                self.active_connection["target"] = new_name
            
            # 保存到文件
            self.save_connections()
            
            # 更新菜单
            self.update_connection_menus()
            
            dialog.destroy()
            messagebox.showinfo("保存成功", "连接已更新")
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=15)
        
        ttk.Button(btn_frame, text="保存", command=save_edited_connection).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def delete_connection(self):
        """删除选中的连接"""
        selected = self.conn_listbox.curselection()
        if not selected:
            messagebox.showwarning("未选择", "请先选择一个连接")
            return
            
        selected_text = self.conn_listbox.get(selected[0])
        conn_name = selected_text.split(" (")[0]
        
        if conn_name not in self.connections:
            return
            
        # 检查是否是活动连接
        if (self.active_connection["source"] == conn_name or 
            self.active_connection["target"] == conn_name):
            if not messagebox.askyesno("确认删除", 
                                      f"连接 '{conn_name}' 正在使用中，删除将断开连接。\n确定要删除吗？"):
                return
                
            # 断开连接
            if self.active_connection["source"] == conn_name:
                self.disconnect_database("source")
            if self.active_connection["target"] == conn_name:
                self.disconnect_database("target")
        
        else:
            if not messagebox.askyesno("确认删除", f"确定要删除连接 '{conn_name}' 吗？"):
                return
        
        # 删除连接
        del self.connections[conn_name]
        
        # 保存到文件
        self.save_connections()
        
        # 刷新列表
        self.refresh_conn_listbox()

    def load_source_data(self):
        """从源数据库加载数据"""
        data, msg = self.db_ops.load_source_data()
        if data is None:
            messagebox.showwarning("操作提示", msg)
            return
        
        # 清空现有表格
        for item in self.source_tree.get_children():
            self.source_tree.delete(item)
        
        # 重置表格样式，解决变白问题
        self.source_tree["style"] = ""
        
        # 设置列（包含备注）
        if data:
            columns = list(data[0].keys())
            self.source_tree["columns"] = columns
            
            for col in columns:
                # 显示字段名和备注
                display_name = self.db_ops.get_field_display_name("ai_device", col)
                self.source_tree.heading(col, text=display_name)
                self.source_tree.column(col, width=120, anchor=tk.CENTER)
        
        # 填充数据
        for row in data:
            values = [str(row[col]) if row[col] is not None else "" for col in columns]
            self.source_tree.insert("", tk.END, values=values)
        
        messagebox.showinfo("加载成功", msg)

    def load_target_data(self):
        """从目标数据库加载数据"""
        data, msg = self.db_ops.load_target_data()
        if data is None:
            messagebox.showwarning("操作提示", msg)
            return
        
        # 清空现有表格
        for item in self.target_tree.get_children():
            self.target_tree.delete(item)
        
        # 重置表格样式，解决变白问题
        self.target_tree["style"] = ""
        
        # 设置列（包含备注）
        if data:
            columns = list(data[0].keys())
            self.target_tree["columns"] = columns
            
            for col in columns:
                # 显示字段名和备注
                display_name = self.db_ops.get_field_display_name("ai_device", col)
                self.target_tree.heading(col, text=display_name)
                self.target_tree.column(col, width=120, anchor=tk.CENTER)
        
        # 填充数据
        for row in data:
            values = [str(row[col]) if row[col] is not None else "" for col in columns]
            self.target_tree.insert("", tk.END, values=values, iid=row['id'])
        
        messagebox.showinfo("加载成功", msg)

    def edit_field_notes(self):
        """编辑字段备注对话框"""
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑字段备注")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(dialog)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建框架放置字段和备注
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        frame.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=frame.yview)
        
        # 创建画布放置内容
        canvas = tk.Canvas(frame)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建内部框架放置所有控件
        inner_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        
        # 获取表的所有字段
        fields = ["id", "user_id", "mac_address", "last_connected_at", 
                  "auto_update", "board", "alias", "agent_id", 
                  "app_version", "sort", "creator", "create_date", 
                  "updater", "update_date", "device_code", "password", "login_time"]
        
        # 存储备注输入框的引用
        note_entries = {}
        
        # 为每个字段创建标签和输入框
        for i, field in enumerate(fields):
            ttk.Label(inner_frame, text=f"{field}:", font=self.default_font).grid(row=i, column=0, sticky=tk.W, pady=3, padx=5)
            note_var = tk.StringVar()
            # 设置现有备注
            if "ai_device" in self.db_ops.field_notes and field in self.db_ops.field_notes["ai_device"]:
                note_var.set(self.db_ops.field_notes["ai_device"][field])
            
            entry = ttk.Entry(inner_frame, textvariable=note_var, width=40)
            entry.grid(row=i, column=1, sticky=tk.W, pady=3, padx=5)
            note_entries[field] = note_var
        
        # 配置网格权重
        inner_frame.columnconfigure(1, weight=1)
        
        # 更新滚动区域
        inner_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 保存按钮
        def save_notes():
            for field, var in note_entries.items():
                self.db_ops.update_field_note("ai_device", field, var.get())
            
            # 保存配置
            self.db_ops.save_config()
            
            # 刷新表格显示
            self.load_source_data()
            self.load_target_data()
            dialog.destroy()
            messagebox.showinfo("保存成功", "字段备注已更新")
        
        ttk.Button(dialog, text="保存备注", command=save_notes).pack(pady=10)

    def edit_target_cell(self, event):
        """编辑目标数据库表格单元格"""
        # 获取点击位置
        region = self.target_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
            
        # 获取单元格信息
        row_id = self.target_tree.identify_row(event.y)
        if not row_id:  # 确保行ID有效
            return
            
        column = self.target_tree.identify_column(event.x)
        column_index = int(column.replace('#', '')) - 1
        columns = self.target_tree["columns"]
        if column_index >= len(columns):
            return
            
        column_name = columns[column_index]
        
        # 不允许编辑主键和系统字段
        if column_name in ["id", "device_code", "create_date"]:
            messagebox.showinfo("提示", f"字段 {column_name} 不允许编辑")
            return
        
        # 获取当前值
        try:
            current_value = self.target_tree.item(row_id, "values")[column_index]
        except IndexError:
            return
            
        # 创建编辑框
        x, y, width, height = self.target_tree.bbox(row_id, column)
        if not (x and y and width and height):  # 确保获取到有效坐标
            return
            
        edit_window = tk.Toplevel(self.root)
        edit_window.geometry(f"{width}x{height}+{self.target_tree.winfo_rootx() + x}+{self.target_tree.winfo_rooty() + y}")
        edit_window.overrideredirect(True)  # 无边框窗口
        
        edit_var = tk.StringVar(value=current_value)
        edit_entry = ttk.Entry(edit_window, textvariable=edit_var)
        edit_entry.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        edit_entry.focus_set()
        edit_entry.select_range(0, tk.END)
        
        # 保存编辑
        def save_edit():
            new_value = edit_var.get()
            # 更新表格显示
            values = list(self.target_tree.item(row_id, "values"))
            values[column_index] = new_value
            self.target_tree.item(row_id, values=values)
            
            # 更新数据库
            success, msg = self.db_ops.update_target_cell(row_id, column_name, new_value)
            if not success:
                messagebox.showerror("更新失败", msg)
                # 恢复原始值
                values[column_index] = current_value
                self.target_tree.item(row_id, values=values)
                
            edit_window.destroy()
        
        # 绑定回车保存和失去焦点关闭
        edit_entry.bind("<Return>", lambda e: save_edit())
        edit_entry.bind("<FocusOut>", lambda e: edit_window.destroy())
        edit_window.bind("<Escape>", lambda e: edit_window.destroy())

    def sync_to_target(self):
        """同步数据到目标数据库"""
        success, msg = self.db_ops.sync_to_target()
        if success:
            messagebox.showinfo("同步结果", msg)
            self.load_target_data()  # 刷新目标数据库数据显示
        else:
            messagebox.showerror("同步失败", msg)

    def clear_target_table(self):
        """清空目标表数据"""
        if messagebox.askyesno("确认清空", "确定要清空目标数据库中的ai_device表数据吗？\n此操作不可恢复！"):
            success, msg = self.db_ops.clear_target_table()
            if success:
                messagebox.showinfo("操作结果", msg)
                self.load_target_data()  # 刷新显示
            else:
                messagebox.showerror("操作失败", msg)

    def export_data(self, data_type):
        """导出数据为Excel、CSV或TXT"""
        # 确定要导出的数据
        if data_type == "source":
            tree = self.source_tree
            title = "源数据库数据"
        else:
            tree = self.target_tree
            title = "目标数据库数据"
            
        if not tree.get_children():
            messagebox.showwarning("无数据", f"请先加载{title}再导出！")
            return
        
        # 获取文件路径
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV文件", "*.csv"),
                ("文本文件", "*.txt"),
                ("Excel文件", "*.xlsx"),
                ("所有文件", "*.*")
            ],
            title=f"导出{title}"
        )
        
        if not file_path:
            return
        
        try:
            # 获取列名（包含备注）
            columns = [tree.heading(col, "text") for col in tree["columns"]]
            
            # 准备数据
            export_data = []
            for item in tree.get_children():
                export_data.append(tree.item(item, "values"))
            
            # 导出为Excel
            if file_path.endswith((".xlsx", ".xls")):
                if not EXCEL_SUPPORT:
                    messagebox.showwarning("缺少依赖", "导出Excel需要安装pandas和openpyxl库。\n是否改用CSV格式导出？")
                    return
                    
                # 使用pandas导出Excel
                df = pd.DataFrame(export_data, columns=columns)
                # 确保日期格式正确
                for col in columns:
                    if any(keyword in col.lower() for keyword in ['date', 'time', '时间', '日期']):
                        try:
                            df[col] = pd.to_datetime(df[col], errors='ignore')
                        except:
                            pass
                            
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo("导出成功", f"{title}已成功导出到:\n{file_path}")
                return
            
            # 调用数据库操作类的导出方法（CSV或TXT）
            success, msg = self.db_ops.export_data(export_data, columns, file_path)
            if success:
                messagebox.showinfo("导出成功", msg)
            else:
                messagebox.showerror("导出失败", msg)
                
        except Exception as e:
            messagebox.showerror("导出失败", f"导出数据时发生错误: {str(e)}")

    def load_connections(self):
        """加载保存的数据库连接配置"""
        if os.path.exists(self.connection_file):
            try:
                with open(self.connection_file, 'r', encoding='utf-8') as f:
                    self.connections = json.load(f)
                
                # 更新菜单
                self.update_connection_menus()
            except Exception as e:
                messagebox.showerror("加载配置失败", f"读取连接配置文件时出错: {str(e)}")

    def save_connections(self):
        """保存数据库连接配置"""
        try:
            with open(self.connection_file, 'w', encoding='utf-8') as f:
                json.dump(self.connections, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("保存配置失败", f"写入连接配置文件时出错: {str(e)}")
            return False

    def show_about(self):
        """显示关于对话框"""
        messagebox.showinfo("关于", "数据库管理与同步工具\n版本: 1.1\n用于管理和同步设备数据库信息")

    def show_help(self):
        """显示帮助对话框"""
        help_window = tk.Toplevel(self.root)
        help_window.title("使用帮助")
        help_window.geometry("600x400")
        help_window.transient(self.root)
        help_window.grab_set()
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(help_window)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 文本框显示帮助信息
        help_text = tk.Text(help_window, wrap=tk.WORD, font=self.default_font, padx=10, pady=10, yscrollcommand=scrollbar.set)
        help_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=help_text.yview)
        
        # 帮助内容
        help_content = """数据库管理与同步工具使用帮助:

1. 数据库连接:
   - 在"数据库"菜单中可以创建、选择和管理数据库连接
   - 源数据库用于读取数据，目标数据库用于写入和修改数据
   - 连接配置会自动保存，下次可以直接复用

2. 数据操作:
   - 点击"加载源数据库数据"或"加载目标数据库数据"按钮获取数据
   - 双击目标数据库表格的单元格可以编辑数据（部分字段不可编辑）
   - 点击"同步数据"将源数据库数据同步到目标数据库

3. 字段备注:
   - 点击"编辑字段备注"按钮为字段添加说明
   - 备注会显示在对应字段的表头中，方便理解字段含义

4. 数据导出:
   - 支持导出为CSV、TXT和Excel格式
   - 导出的文件包含带有备注的字段标题
   - 导出Excel需要安装pandas和openpyxl库

5. 注意事项:
   - 源数据库为只读模式，不能直接修改
   - 同步数据时会自动生成设备码和密码
   - 敏感字段（如id、device_code）不允许编辑
"""
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)  # 设置为只读

    def on_closing(self):
        """关闭窗口时断开数据库连接"""
        self.db_ops.close_connections()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DatabaseTool(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
