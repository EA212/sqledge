import pymysql
from pymysql.cursors import DictCursor
import os
import json
import csv
import random
import string
from datetime import datetime

class DatabaseOperations:
    def __init__(self):
        # 数据库连接对象
        self.source_conn = None
        self.target_conn = None
        
        # 配置文件路径
        self.config_file = "db_config.json"
        
        # 字段备注存储 - 结构: {表名: {字段名: 备注}}
        self.field_notes = {}
        
        # 加载配置
        self.load_config()

    def connect_source_db(self, host, port, user, password, database):
        """连接源数据库"""
        try:
            # 关闭现有连接
            if self.source_conn:
                self.source_conn.close()
                
            self.source_conn = pymysql.connect(
                host=host,
                port=int(port) if port else 3306,
                user=user,
                password=password,
                database=database,
                cursorclass=DictCursor,
                charset='utf8mb4'
            )
            return True, f"已成功连接到源数据库: {database}"
        except Exception as e:
            return False, f"源数据库连接失败: {str(e)}"

    def connect_target_db(self, host, port, user, password, database):
        """连接目标数据库"""
        try:
            # 关闭现有连接
            if self.target_conn:
                self.target_conn.close()
                
            self.target_conn = pymysql.connect(
                host=host,
                port=int(port) if port else 3306,
                user=user,
                password=password,
                database=database,
                cursorclass=DictCursor,
                charset='utf8mb4'
            )
            
            # 确保目标表存在
            self.create_target_table_if_not_exists()
            
            return True, f"已成功连接到目标数据库: {database}"
        except Exception as e:
            return False, f"目标数据库连接失败: {str(e)}"

    def create_target_table_if_not_exists(self):
        """创建目标表（如果不存在）"""
        if not self.target_conn:
            return
            
        try:
            with self.target_conn.cursor() as cursor:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS ai_device (
                    id varchar(32) NOT NULL PRIMARY KEY,
                    user_id bigint,
                    mac_address varchar(50),
                    last_connected_at datetime,
                    auto_update tinyint unsigned DEFAULT 0,
                    board varchar(50),
                    alias varchar(64),
                    agent_id varchar(32),
                    app_version varchar(20),
                    sort int unsigned DEFAULT 0,
                    creator bigint,
                    create_date datetime,
                    updater bigint,
                    update_date datetime,
                    device_code varchar(4) NOT NULL,
                    password varchar(4) NOT NULL,
                    login_time datetime
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                cursor.execute(create_table_sql)
                self.target_conn.commit()
        except Exception as e:
            print(f"创建目标表失败: {str(e)}")
            self.target_conn.rollback()

    def load_source_data(self):
        """从源数据库加载数据"""
        if not self.source_conn:
            return None, "请先连接源数据库"
            
        try:
            with self.source_conn.cursor() as cursor:
                cursor.execute("SELECT * FROM ai_device ORDER BY create_date ASC")
                data = cursor.fetchall()
                return data, f"已加载 {len(data)} 条源数据"
        except Exception as e:
            return None, f"加载源数据失败: {str(e)}"

    def load_target_data(self):
        """从目标数据库加载数据"""
        if not self.target_conn:
            return None, "请先连接目标数据库"
            
        try:
            with self.target_conn.cursor() as cursor:
                cursor.execute("SELECT * FROM ai_device ORDER BY create_date ASC")
                data = cursor.fetchall()
                return data, f"已加载 {len(data)} 条目标数据"
        except Exception as e:
            return None, f"加载目标数据失败: {str(e)}"

    def update_target_cell(self, row_id, column_name, new_value):
        """更新目标数据库中的单元格值"""
        if not self.target_conn:
            return False, "请先连接目标数据库"
            
        try:
            with self.target_conn.cursor() as cursor:
                # 转换空字符串为NULL
                if new_value.strip() == "":
                    new_value = None
                    
                # 特殊处理日期字段
                if column_name in ["last_connected_at", "update_date", "login_time"]:
                    if new_value and not self.is_valid_datetime(new_value):
                        return False, "日期时间格式不正确，应为YYYY-MM-DD HH:MM:SS"
                
                # 执行更新
                sql = f"UPDATE ai_device SET {column_name} = %s, update_date = NOW() WHERE id = %s"
                affected_rows = cursor.execute(sql, (new_value, row_id))
                
                # 提交事务
                self.target_conn.commit()
                
                if affected_rows == 0:
                    return False, "未找到对应记录或值未发生变化"
                    
                return True, "数据已更新"
                
        except Exception as e:
            self.target_conn.rollback()
            return False, f"更新失败: {str(e)}"

    def sync_to_target(self):
        """同步数据到目标数据库"""
        if not self.source_conn or not self.target_conn:
            return False, "请先连接源数据库和目标数据库"
            
        try:
            # 获取源数据
            with self.source_conn.cursor() as source_cursor:
                source_cursor.execute("SELECT * FROM ai_device ORDER BY create_date ASC")
                source_data = source_cursor.fetchall()
                
                if not source_data:
                    return True, "源数据库中没有数据可同步"
            
            # 获取目标数据库中已有的最大设备码
            max_code = 0
            with self.target_conn.cursor() as target_cursor:
                target_cursor.execute("SELECT MAX(device_code) as max_code FROM ai_device")
                result = target_cursor.fetchone()
                if result['max_code'] and result['max_code'].isdigit():
                    max_code = int(result['max_code'])
            
            # 准备要插入的数据
            insert_count = 0
            with self.target_conn.cursor() as target_cursor:
                for row in source_data:
                    # 检查记录是否已存在
                    target_cursor.execute("SELECT id FROM ai_device WHERE id = %s", (row['id'],))
                    if target_cursor.fetchone():
                        continue  # 已存在则跳过
                    
                    # 生成设备码（0001, 0002...）
                    max_code += 1
                    device_code = f"{max_code:04d}"
                    
                    # 生成随机密码
                    password = self.generate_random_password()
                    
                    # 创建插入SQL
                    columns = list(row.keys())
                    columns.extend(['device_code', 'password', 'login_time'])
                    
                    placeholders = ', '.join(['%s'] * len(columns))
                    column_names = ', '.join(columns)
                    
                    values = [row[col] for col in row.keys()]
                    values.extend([device_code, password, None])  # login_time初始为NULL
                    
                    sql = f"INSERT INTO ai_device ({column_names}) VALUES ({placeholders})"
                    target_cursor.execute(sql, values)
                    insert_count += 1
                
                self.target_conn.commit()
            
            return True, f"成功同步 {insert_count} 条新数据到目标数据库"
        except Exception as e:
            self.target_conn.rollback()
            return False, f"同步过程中发生错误: {str(e)}"

    def clear_target_table(self):
        """清空目标表数据"""
        if not self.target_conn:
            return False, "请先连接目标数据库"
            
        try:
            with self.target_conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE ai_device")
                self.target_conn.commit()
            return True, "已成功清空目标表数据"
        except Exception as e:
            self.target_conn.rollback()
            return False, f"清空表时发生错误: {str(e)}"

    def export_data(self, data, columns, file_path):
        """导出数据到文件"""
        try:
            # 导出为CSV
            if file_path.endswith(".csv"):
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:  # 使用utf-8-sig确保中文正常显示
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(data)
                return True, f"数据已成功导出到:\n{file_path}"
            
            # 导出为TXT
            elif file_path.endswith(".txt"):
                with open(file_path, 'w', encoding='utf-8') as f:
                    # 写入表头
                    f.write('\t'.join(columns) + '\n')
                    # 写入数据
                    for row in data:
                        f.write('\t'.join(map(str, row)) + '\n')
                return True, f"数据已成功导出到:\n{file_path}"
            
            # 不支持的格式
            else:
                return False, f"不支持的文件格式: {os.path.splitext(file_path)[1]}"
                
        except Exception as e:
            return False, f"导出数据时发生错误: {str(e)}"

    def get_field_display_name(self, table_name, field_name):
        """获取带备注的字段显示名"""
        if table_name in self.field_notes and field_name in self.field_notes[table_name]:
            note = self.field_notes[table_name][field_name]
            if note.strip():
                return f"{field_name} ({note})"
        
        return field_name

    def update_field_note(self, table_name, field_name, note):
        """更新字段备注"""
        if table_name not in self.field_notes:
            self.field_notes[table_name] = {}
            
        self.field_notes[table_name][field_name] = note.strip()

    def save_config(self, source_config=None, target_config=None):
        """保存配置信息"""
        try:
            config = {
                "field_notes": self.field_notes
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存配置失败: {str(e)}")
            return False

    def load_config(self):
        """加载配置信息"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if "field_notes" in config:
                        self.field_notes = config["field_notes"]
            except Exception as e:
                print(f"加载配置失败: {str(e)}")

    def generate_random_password(self):
        """生成4位随机密码（数字和字母混合）"""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(4))

    def is_valid_datetime(self, value):
        """验证日期时间格式"""
        try:
            datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return True
        except ValueError:
            try:
                # 尝试仅日期格式
                datetime.strptime(value, "%Y-%m-%d")
                return True
            except ValueError:
                return False

    def close_connections(self):
        """关闭所有数据库连接"""
        if self.source_conn:
            try:
                self.source_conn.close()
            except:
                pass
                
        if self.target_conn:
            try:
                self.target_conn.close()
            except:
                pass
