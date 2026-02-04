import pymysql
import json
import os
import time
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDateTime, QDate

class DBConfig:
    """数据库配置管理类，负责配置的保存和加载"""
    CONFIG_FILE = "db_config.json"
    
    @staticmethod
    def load_config():
        """加载保存的配置"""
        if os.path.exists(DBConfig.CONFIG_FILE):
            try:
                with open(DBConfig.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置失败: {e}")
        return {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "",
            "database": "",
            "table": "ai_device",
            "last_csv_path": "",
            "export_columns": []
        }
    
    @staticmethod
    def save_config(config):
        """保存配置到文件"""
        try:
            with open(DBConfig.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

class DBManager:
    """数据库管理类，负责数据库连接和操作"""
    def __init__(self, config):
        self.config = config
        self.cache = {
            "data": None,
            "columns": None,
            "last_refresh": None,
            "record_count": 0
        }
    
    def test_connection(self):
        """测试数据库连接"""
        try:
            conn = pymysql.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"]
            )
            conn.close()
            return True, "连接成功"
        except Exception as e:
            return False, str(e)
    
    def refresh_data(self, date_from, date_to, parent=None):
        """刷新数据库数据，带缓存机制"""
        try:
            # 连接数据库
            conn = pymysql.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"]
            )
            
            # 构建查询SQL
            table_name = self.config["table"]
            date_from_str = date_from.toString("yyyy-MM-dd")
            date_to_str = date_to.toString("yyyy-MM-dd")
            
            # 查询表结构获取字段名
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE {table_name}")
            columns = [column[0] for column in cursor.fetchall()]
            
            # 查询数据，按create_date排序（最新的在前）
            query_sql = f"SELECT * FROM {table_name} WHERE create_date BETWEEN '{date_from_str}' AND '{date_to_str}' ORDER BY create_date DESC"
            cursor.execute(query_sql)
            data = cursor.fetchall()
            
            # 计算更新的数据量
            old_count = self.cache["record_count"]
            new_count = len(data)
            changed_count = abs(new_count - old_count)
            
            # 更新缓存
            self.cache = {
                "data": data,
                "columns": columns,
                "last_refresh": QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss"),
                "record_count": new_count
            }
            
            # 关闭连接
            cursor.close()
            conn.close()
            
            return True, f"成功加载 {new_count} 条数据，更新了 {changed_count} 条", self.cache
        
        except Exception as e:
            error_msg = f"加载数据失败：{str(e)}"
            if parent:
                QMessageBox.critical(parent, "错误", error_msg)
            return False, error_msg, None
    
    def get_cached_data(self):
        """获取缓存的数据"""
        return self.cache
    
    def clear_cache(self):
        """清除缓存"""
        self.cache = {
            "data": None,
            "columns": None,
            "last_refresh": None,
            "record_count": 0
        }

class DataProcessor:
    """数据处理类，负责数据匹配和转换"""
    @staticmethod
    def match_data(db_data, db_columns, csv_data, disabled_rows):
        """匹配数据库数据和CSV数据"""
        try:
            # 筛选启用的数据库记录
            enabled_db_rows = [
                row for idx, row in enumerate(db_data) 
                if idx not in disabled_rows
            ]
            
            # 按顺序匹配，有多少匹配多少
            match_count = min(len(enabled_db_rows), len(csv_data))
            
            # 构建结果数据 - 把password和device_code放在前面
            result_data = []
            
            # 新的列顺序：password, device_code 在前，然后是数据库列
            result_columns = ["password", "device_code"] + db_columns
            
            for i in range(match_count):
                db_row = enabled_db_rows[i]
                csv_row = csv_data.iloc[i]
                
                # 转换数据库行数据为字典
                db_dict = dict(zip(db_columns, db_row))
                
                # 构建结果行，确保password和device_code在前面
                result_row = {
                    "password": csv_row["password"],
                    "device_code": csv_row["device_code"]
                }
                result_row.update(db_dict)
                
                result_data.append(result_row)
                
            return {
                "columns": result_columns,
                "data": result_data,
                "count": match_count
            }
            
        except Exception as e:
            print(f"数据匹配失败：{str(e)}")
            return None
    
    @staticmethod
    def export_to_csv(data, columns, file_path, selected_columns=None):
        """导出数据到CSV，支持选择列"""
        try:
            import pandas as pd
            
            # 如果指定了要导出的列，则筛选
            if selected_columns and all(col in columns for col in selected_columns):
                df = pd.DataFrame(data)[selected_columns]
            else:
                df = pd.DataFrame(data)
            
            # 保存CSV
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
            return True, f"成功导出 {len(data)} 条记录到 {file_path}"
        except Exception as e:
            return False, f"导出失败：{str(e)}"
    