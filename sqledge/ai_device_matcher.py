import sys
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QTableWidget,
                            QTableWidgetItem, QLabel, QLineEdit, QDialog, QFormLayout,
                            QGroupBox, QDateEdit, QCheckBox, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QDateTime, QDate
from PyQt5.QtGui import QFont, QBrush, QColor
from db_utils import DBConfig, DBManager, DataProcessor

class DBConfigDialog(QDialog):
    """数据库连接配置对话框"""
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("数据库连接配置")
        self.setFixedSize(350, 250)
        
        # 如果有配置则使用，否则使用默认值
        self.config = config if config else DBConfig.load_config()
        
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.host_edit = QLineEdit(self.config["host"])
        self.port_edit = QLineEdit(str(self.config["port"]))
        self.user_edit = QLineEdit(self.config["user"])
        self.password_edit = QLineEdit(self.config["password"])
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.db_edit = QLineEdit(self.config["database"])
        self.table_edit = QLineEdit(self.config["table"])
        
        form_layout.addRow("主机:", self.host_edit)
        form_layout.addRow("端口:", self.port_edit)
        form_layout.addRow("用户名:", self.user_edit)
        form_layout.addRow("密码:", self.password_edit)
        form_layout.addRow("数据库名:", self.db_edit)
        form_layout.addRow("表名:", self.table_edit)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        
        self.test_btn.clicked.connect(self.test_connection)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(form_layout)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def get_config(self):
        """获取配置信息"""
        return {
            "host": self.host_edit.text(),
            "port": int(self.port_edit.text()) if self.port_edit.text() else 3306,
            "user": self.user_edit.text(),
            "password": self.password_edit.text(),
            "database": self.db_edit.text(),
            "table": self.table_edit.text(),
            "last_csv_path": self.config.get("last_csv_path", ""),
            "export_columns": self.config.get("export_columns", [])
        }
        
    def test_connection(self):
        """测试数据库连接"""
        config = self.get_config()
        db_manager = DBManager(config)
        success, msg = db_manager.test_connection()
        if success:
            QMessageBox.information(self, "成功", "数据库连接测试成功！")
        else:
            QMessageBox.critical(self, "错误", f"连接失败：{msg}")

class ColumnSelectionDialog(QDialog):
    """列选择对话框，用于选择要导出的列"""
    def __init__(self, parent=None, columns=None, selected_columns=None):
        super().__init__(parent)
        self.setWindowTitle("选择要导出的列")
        self.resize(300, 400)
        
        self.columns = columns if columns else []
        self.selected_columns = selected_columns if selected_columns else self.columns.copy()
        
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # 添加滚动区域，方便处理多个列
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # 创建复选框
        self.checkboxes = {}
        for column in self.columns:
            checkbox = QCheckBox(column)
            checkbox.setChecked(column in self.selected_columns)
            self.checkboxes[column] = checkbox
            scroll_layout.addWidget(checkbox)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.deselect_all_btn = QPushButton("全不选")
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        
        self.select_all_btn.clicked.connect(self.select_all)
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.deselect_all_btn)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addWidget(QLabel("请选择要导出的列："))
        layout.addWidget(scroll_area)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def select_all(self):
        """全选所有列"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
            
    def deselect_all(self):
        """取消选择所有列"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
            
    def get_selected_columns(self):
        """获取选中的列"""
        return [col for col, checkbox in self.checkboxes.items() if checkbox.isChecked()]

class AIDeviceMatcher(QMainWindow):
    """AI设备数据匹配主窗口"""
    def __init__(self):
        super().__init__()
        
        # 加载配置
        self.config = DBConfig.load_config()
        
        # 数据缓存
        self.db_manager = DBManager(self.config)
        self.local_csv_data = None
        self.matched_data = None
        
        # 记录禁用状态
        self.disabled_rows = set()  # 存储被禁用的行索引
        
        # 初始化界面
        self.initUI()
        
    def initUI(self):
        """初始化用户界面"""
        self.setWindowTitle("AI设备数据匹配工具")
        self.setGeometry(100, 100, 1200, 700)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部控制区
        control_layout = QHBoxLayout()
        
        # 数据库连接按钮
        self.db_connect_btn = QPushButton("数据库连接配置")
        self.db_connect_btn.clicked.connect(self.show_db_config)
        
        # 刷新数据按钮
        self.refresh_btn = QPushButton("刷新数据库数据")
        self.refresh_btn.clicked.connect(self.refresh_db_data)
        self.refresh_btn.setEnabled(bool(self.config.get("database")))
        
        # 选择本地CSV按钮
        self.select_csv_btn = QPushButton("选择本地CSV文件")
        self.select_csv_btn.clicked.connect(self.select_local_csv)
        
        # 匹配数据按钮
        self.match_btn = QPushButton("匹配数据（预览）")
        self.match_btn.clicked.connect(self.match_data)
        self.match_btn.setEnabled(False)
        
        # 导出CSV按钮
        self.export_btn = QPushButton("导出CSV")
        self.export_btn.clicked.connect(self.export_data)
        self.export_btn.setEnabled(False)
        
        # 刷新时间显示
        self.refresh_time_label = QLabel("最后刷新: 未刷新")
        
        control_layout.addWidget(self.db_connect_btn)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(self.select_csv_btn)
        control_layout.addWidget(self.match_btn)
        control_layout.addWidget(self.export_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.refresh_time_label)
        
        # 添加控制区到主布局
        main_layout.addLayout(control_layout)
        
        # 创建标签页控件
        self.tabs = QTabWidget()
        
        # 数据库数据标签页
        self.db_tab = QWidget()
        self.init_db_tab()
        self.tabs.addTab(self.db_tab, "数据库数据")
        
        # 本地CSV数据标签页
        self.csv_tab = QWidget()
        self.init_csv_tab()
        self.tabs.addTab(self.csv_tab, "本地CSV数据")
        
        # 匹配结果标签页
        self.result_tab = QWidget()
        self.init_result_tab()
        self.tabs.addTab(self.result_tab, "匹配结果")
        
        # 添加标签页到主布局
        main_layout.addWidget(self.tabs)
        
    def init_db_tab(self):
        """初始化数据库数据标签页"""
        layout = QVBoxLayout(self.db_tab)
        
        # 提示信息
        self.db_hint_label = QLabel("提示：点击行可切换启用/禁用状态（灰色为禁用）")
        layout.addWidget(self.db_hint_label)
        
        # 查询条件区域
        filter_group = QGroupBox("查询条件")
        filter_layout = QHBoxLayout()
        
        self.date_from_edit = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_to_edit = QDateEdit(QDate.currentDate())
        self.date_to_edit.setDisplayFormat("yyyy-MM-dd")
        
        filter_layout.addWidget(QLabel("创建日期从:"))
        filter_layout.addWidget(self.date_from_edit)
        filter_layout.addWidget(QLabel("到:"))
        filter_layout.addWidget(self.date_to_edit)
        filter_layout.addStretch()
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # 数据库数据表格
        self.db_table = QTableWidget()
        self.db_table.setAlternatingRowColors(True)
        self.db_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.db_table.cellClicked.connect(self.toggle_row_status)  # 点击单元格触发行状态切换
        layout.addWidget(self.db_table)
        
    def init_csv_tab(self):
        """初始化本地CSV数据标签页"""
        layout = QVBoxLayout(self.csv_tab)
        
        # CSV文件路径显示
        self.csv_path_label = QLabel("未选择CSV文件")
        if self.config.get("last_csv_path"):
            self.csv_path_label.setText(f"上次选择: {self.config['last_csv_path']}")
        layout.addWidget(self.csv_path_label)
        
        # CSV数据表格
        self.csv_table = QTableWidget()
        self.csv_table.setAlternatingRowColors(True)
        self.csv_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.csv_table)
        
    def init_result_tab(self):
        """初始化匹配结果标签页"""
        layout = QVBoxLayout(self.result_tab)
        
        # 结果控制区
        result_control_layout = QHBoxLayout()
        
        self.select_columns_btn = QPushButton("选择导出列")
        self.select_columns_btn.clicked.connect(self.show_column_selection)
        self.select_columns_btn.setEnabled(False)
        
        result_control_layout.addWidget(self.select_columns_btn)
        result_control_layout.addStretch()
        
        # 结果信息
        self.result_info_label = QLabel("请先完成数据匹配")
        layout.addWidget(self.result_info_label)
        
        layout.addLayout(result_control_layout)
        
        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.result_table)
        
    def toggle_row_status(self, row, col):
        """切换行的启用/禁用状态"""
        if row < 0 or row >= self.db_table.rowCount():
            return
            
        # 切换行状态
        if row in self.disabled_rows:
            self.disabled_rows.remove(row)
            # 恢复正常颜色
            for c in range(self.db_table.columnCount()):
                item = self.db_table.item(row, c)
                if item:
                    item.setForeground(QBrush(QColor(0, 0, 0)))
        else:
            self.disabled_rows.add(row)
            # 设置为灰色
            for c in range(self.db_table.columnCount()):
                item = self.db_table.item(row, c)
                if item:
                    item.setForeground(QBrush(QColor(128, 128, 128)))
    
    def show_db_config(self):
        """显示数据库配置对话框"""
        dialog = DBConfigDialog(self, self.config)
        if dialog.exec_():
            self.config = dialog.get_config()
            self.db_manager = DBManager(self.config)
            self.refresh_btn.setEnabled(True)
            DBConfig.save_config(self.config)
            QMessageBox.information(self, "成功", "数据库配置已保存")
            
    def refresh_db_data(self):
        """刷新数据库数据"""
        if not self.config.get("database"):
            QMessageBox.warning(self, "警告", "请先配置数据库连接")
            return
            
        try:
            # 显示加载中提示
            QMessageBox.information(self, "提示", "正在从数据库加载数据...")
            
            # 刷新数据
            success, msg, cache = self.db_manager.refresh_data(
                self.date_from_edit.date(), 
                self.date_to_edit.date(), 
                self
            )
            
            if success:
                # 重置禁用状态
                self.disabled_rows = set()
                
                # 更新表格显示
                self.update_db_table(cache["columns"], cache["data"])
                
                # 更新刷新时间
                self.refresh_time_label.setText(f"最后刷新: {cache['last_refresh']}")
                
                QMessageBox.information(self, "成功", msg)
                
                # 如果已经加载了CSV数据，启用匹配按钮
                if self.local_csv_data is not None:
                    self.match_btn.setEnabled(True)
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载数据失败：{str(e)}")
            
    def update_db_table(self, columns, data):
        """更新数据库表格显示"""
        if not data:
            self.db_table.setRowCount(0)
            self.db_table.setColumnCount(0)
            return
            
        # 设置表格列数和表头
        self.db_table.setColumnCount(len(columns))
        self.db_table.setHorizontalHeaderLabels(columns)
        
        # 设置表格行数和数据
        self.db_table.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data) if cell_data is not None else "")
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 禁止编辑
                self.db_table.setItem(row_idx, col_idx, item)
                
        # 调整列宽
        self.db_table.resizeColumnsToContents()
        
    def select_local_csv(self):
        """选择本地CSV文件"""
        initial_dir = os.path.dirname(self.config.get("last_csv_path", "")) if self.config.get("last_csv_path") else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择本地CSV文件", initial_dir, "CSV Files (*.csv)"
        )
        
        if path:
            try:
                # 读取CSV文件
                self.local_csv_data = pd.read_csv(path)
                
                # 验证CSV格式
                required_columns = ["password", "device_code"]
                if not all(col in self.local_csv_data.columns for col in required_columns):
                    raise ValueError("CSV文件必须包含 'password' 和 'device_code' 列")
                
                # 更新界面显示
                self.csv_path_label.setText(f"已选择: {path}")
                self.update_csv_table()
                
                # 保存最后使用的CSV路径
                self.config["last_csv_path"] = path
                DBConfig.save_config(self.config)
                
                # 如果已经加载了数据库数据，启用匹配按钮
                cache = self.db_manager.get_cached_data()
                if cache["data"] is not None:
                    self.match_btn.setEnabled(True)
                    
                QMessageBox.information(self, "成功", f"成功加载CSV文件，共 {len(self.local_csv_data)} 条记录")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载CSV文件失败：{str(e)}")
                self.local_csv_data = None
                
    def update_csv_table(self):
        """更新CSV表格显示"""
        if self.local_csv_data is None:
            self.csv_table.setRowCount(0)
            self.csv_table.setColumnCount(0)
            return
            
        # 设置表格列数和表头
        columns = self.local_csv_data.columns.tolist()
        self.csv_table.setColumnCount(len(columns))
        self.csv_table.setHorizontalHeaderLabels(columns)
        
        # 设置表格行数和数据
        self.csv_table.setRowCount(len(self.local_csv_data))
        for row_idx, row_data in self.local_csv_data.iterrows():
            for col_idx, col_name in enumerate(columns):
                item = QTableWidgetItem(str(row_data[col_name]) if pd.notna(row_data[col_name]) else "")
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 禁止编辑
                self.csv_table.setItem(row_idx, col_idx, item)
                
        # 调整列宽
        self.csv_table.resizeColumnsToContents()
        
    def match_data(self):
        """匹配数据并预览结果"""
        cache = self.db_manager.get_cached_data()
        
        if cache["data"] is None or self.local_csv_data is None:
            QMessageBox.warning(self, "警告", "请先加载数据库数据和本地CSV数据")
            return
            
        try:
            # 匹配数据
            self.matched_data = DataProcessor.match_data(
                cache["data"], 
                cache["columns"], 
                self.local_csv_data, 
                self.disabled_rows
            )
            
            if not self.matched_data:
                QMessageBox.warning(self, "警告", "数据匹配失败，请重试")
                return
                
            # 更新结果表格
            self.update_result_table()
            
            # 启用导出和列选择按钮
            self.export_btn.setEnabled(True)
            self.select_columns_btn.setEnabled(True)
            
            # 切换到结果标签页
            self.tabs.setCurrentIndex(2)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据匹配失败：{str(e)}")
            
    def update_result_table(self):
        """更新结果表格显示"""
        if not self.matched_data:
            return
            
        columns = self.matched_data["columns"]
        data = self.matched_data["data"]
        
        # 更新信息标签
        self.result_info_label.setText(f"匹配成功，共 {len(data)} 条记录")
        
        # 设置表格列数和表头
        self.result_table.setColumnCount(len(columns))
        self.result_table.setHorizontalHeaderLabels(columns)
        
        # 设置表格行数和数据
        self.result_table.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            for col_idx, col_name in enumerate(columns):
                item = QTableWidgetItem(str(row_data[col_name]) if row_data[col_name] is not None else "")
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 禁止编辑
                self.result_table.setItem(row_idx, col_idx, item)
                
        # 调整列宽
        self.result_table.resizeColumnsToContents()
        
    def show_column_selection(self):
        """显示列选择对话框"""
        if not self.matched_data:
            return
            
        # 获取当前选中的列（从配置中加载）
        selected_columns = self.config.get("export_columns", self.matched_data["columns"])
        
        # 显示对话框
        dialog = ColumnSelectionDialog(
            self, 
            self.matched_data["columns"],
            selected_columns
        )
        
        if dialog.exec_():
            # 保存选中的列
            self.config["export_columns"] = dialog.get_selected_columns()
            DBConfig.save_config(self.config)
            
    def export_data(self):
        """导出匹配结果为CSV"""
        if not self.matched_data:
            return
            
        # 获取选中的列
        selected_columns = self.config.get("export_columns", self.matched_data["columns"])
        
        # 确保至少选择了一列
        if not selected_columns:
            QMessageBox.warning(self, "警告", "请至少选择一列导出")
            self.show_column_selection()
            return
            
        # 获取保存路径
        default_filename = f"device_matched_result_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        initial_dir = os.path.dirname(self.config.get("last_csv_path", "")) if self.config.get("last_csv_path") else ""
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存匹配结果", 
            os.path.join(initial_dir, default_filename), 
            "CSV Files (*.csv)"
        )
        
        if save_path:
            # 执行导出
            success, msg = DataProcessor.export_to_csv(
                self.matched_data["data"],
                self.matched_data["columns"],
                save_path,
                selected_columns
            )
            
            if success:
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.critical(self, "错误", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 设置中文字体
    font = QFont("SimHei")
    app.setFont(font)
    
    window = AIDeviceMatcher()
    window.show()
    sys.exit(app.exec_())
    