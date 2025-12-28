import random
import time
import requests
import pymysql
import uuid
from datetime import datetime
import threading
import signal

headers = {
    'authority': 'api.huanmei666.com',
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9',
    'app-client': 'h5-wanlshop',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'origin': 'http://shop143.sxchengyi.cn',
    'pragma': 'no-cache',
    'referer': 'http://shop143.sxchengyi.cn/?wework_cfm_code=NAiz%2FpkZkITIe96%2Bi1m3bSJHjLabuQA1a44v5ufbSM1iJuIuuG3FOhW03XEoC1%2F7zEjMSHRQ5REczaVE0cWvzVIX9eUCURXHs0cbd7b%2FAsJDZ21fupW2qBxMEdVUtbI9H%2Bt4O2ptbKJB',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'sign': '242fdef3c17f1680df24c220e12fe275',
    'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
}

# 用于存储任务停止标志的字典
task_stop_flags = {}

def get_db_connection():
    connection = pymysql.connect(
        host='mysql6.sqlpub.com',
        port=3311,
        user='xiaochaohuo',
        password='2hPj1QwAVr33nsdT',
        database='huo666',
        charset='utf8mb4'
    )
    return connection

def create_task_table():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 创建任务表
            create_task_table_sql = """
            CREATE TABLE IF NOT EXISTS tasks (
                id VARCHAR(36) PRIMARY KEY,
                invite_code VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                min_delay INT DEFAULT 1,
                max_delay INT DEFAULT 5,
                total_count INT DEFAULT 0,
                completed_count INT DEFAULT 0,
                existing_count INT DEFAULT 0,
                status ENUM('pending', 'running', 'completed', 'stopped') DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_task_table_sql)
            
            # 创建账号表
            create_accounts_table_sql = """
            CREATE TABLE IF NOT EXISTS accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id VARCHAR(36),
                mobile VARCHAR(20) NOT NULL,
                status ENUM('pending', 'completed', 'failed', 'existing') DEFAULT 'pending',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
            """
            cursor.execute(create_accounts_table_sql)
            
            # 检查并添加existing_count字段（如果已存在会忽略错误）
            try:
                cursor.execute("ALTER TABLE tasks ADD COLUMN existing_count INT DEFAULT 0")
            except:
                # 如果字段已存在，忽略错误
                pass
            
            # 检查并添加accounts表中的existing状态（如果已存在会忽略错误）
            try:
                cursor.execute("ALTER TABLE accounts ADD COLUMN status ENUM('pending', 'completed', 'failed', 'existing') DEFAULT 'pending'")
            except:
                # 如果字段已存在，忽略错误
                pass
            
            connection.commit()
    finally:
        connection.close()

def create_task_with_phones(invite_code, password, min_delay=1, max_delay=5, phones=None):
    task_id = str(uuid.uuid4())
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 插入任务记录
            insert_task_sql = """
            INSERT INTO tasks (id, invite_code, password, min_delay, max_delay, total_count, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            total_count = len(phones) if phones else 0
            cursor.execute(insert_task_sql, (task_id, invite_code, password, min_delay, max_delay, total_count, 'pending'))
            
            # 如果提供了手机号列表，则一次性插入所有手机号，状态为pending
            if phones:
                for phone in phones:
                    insert_account_sql = """
                    INSERT INTO accounts (task_id, mobile, status)
                    VALUES (%s, %s, %s)
                    """
                    cursor.execute(insert_account_sql, (task_id, phone, 'pending'))
                    
        connection.commit()
    finally:
        connection.close()
    return task_id

def register(mobile, invite_code, password):
    json_data = {
        'mobile': mobile,
        'invite_code': invite_code,
        'password': password,
    }

    response = requests.post('https://api.huanmei666.com/api/wanlshop/user/register', headers=headers, json=json_data).json()
    return response

def execute_task(task_id):
    # 设置任务停止标志
    task_stop_flags[task_id] = False
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 获取任务信息
            cursor.execute("SELECT invite_code, password, min_delay, max_delay FROM tasks WHERE id = %s", (task_id,))
            task = cursor.fetchone()
            
            if not task:
                return False
                
            invite_code, password, min_delay, max_delay = task
            
            # 更新任务状态为运行中
            cursor.execute("UPDATE tasks SET status = 'running' WHERE id = %s", (task_id,))
            connection.commit()
            
            # 获取所有待处理的手机号
            cursor.execute("SELECT id, mobile FROM accounts WHERE task_id = %s AND status = 'pending'", (task_id,))
            pending_accounts = cursor.fetchall()
            
            for account_id, phone in pending_accounts:
                # 检查停止标志
                if task_stop_flags.get(task_id):
                    print(f'任务 {task_id} 已停止')
                    cursor.execute("UPDATE tasks SET status = 'stopped' WHERE id = %s", (task_id,))
                    connection.commit()
                    return False
                
                try:
                    response = register(phone, invite_code, password)
                    msg = response.get('msg', '未知错误')
                    
                    # 根据结果更新账号状态和任务统计
                    if '已经存在' in msg or '已存在' in msg or '已被注册' in msg:
                        # 用户名已存在的情况
                        update_account_sql = """
                        UPDATE accounts 
                        SET status = 'existing', result = %s 
                        WHERE id = %s
                        """
                        cursor.execute(update_account_sql, (msg, account_id))
                        
                        # 更新任务统计信息（增加existing_count）
                        cursor.execute("""
                            UPDATE tasks 
                            SET existing_count = existing_count + 1,
                                status = CASE 
                                    WHEN total_count = completed_count + existing_count + (SELECT COUNT(*) FROM accounts WHERE task_id = %s AND status = 'failed') THEN 'completed'
                                    ELSE 'running'
                                END
                            WHERE id = %s
                        """, (task_id, task_id))
                    else:
                        # 正常完成的情况
                        update_account_sql = """
                        UPDATE accounts 
                        SET status = 'completed', result = %s 
                        WHERE id = %s
                        """
                        cursor.execute(update_account_sql, (msg, account_id))
                        
                        # 更新任务统计信息（增加completed_count）
                        cursor.execute("""
                            UPDATE tasks 
                            SET completed_count = completed_count + 1,
                                status = CASE 
                                    WHEN total_count = completed_count + existing_count + (SELECT COUNT(*) FROM accounts WHERE task_id = %s AND status = 'failed') THEN 'completed'
                                    ELSE 'running'
                                END
                            WHERE id = %s
                        """, (task_id, task_id))
                    
                    connection.commit()
                    
                    print(f'{phone}注册结果：{msg},当前邀请码为：{invite_code},已注册{get_completed_count(task_id)}个账号')
                    
                    # 添加延迟，但如果是用户名已存在则跳过延迟
                    if '已经存在' not in msg and '已存在' not in msg and '已被注册' not in msg:
                        random_time = random.randint(min_delay, max_delay)
                        print('-' * 20, f'延迟{random_time}秒后继续')
                        time.sleep(random_time)
                    else:
                        print('-' * 20, '用户名已存在，跳过延迟')
                    
                except Exception as e:
                    error_msg = f'错误: {str(e)}'
                    
                    # 更新账号状态为失败
                    update_account_sql = """
                    UPDATE accounts 
                    SET status = 'failed', result = %s 
                    WHERE id = %s
                    """
                    cursor.execute(update_account_sql, (error_msg, account_id))
                    
                    # 更新任务统计信息（增加failed_count，这里通过查询获取）
                    cursor.execute("""
                        UPDATE tasks 
                        SET status = CASE 
                            WHEN total_count = completed_count + existing_count + (SELECT COUNT(*) FROM accounts WHERE task_id = %s AND status = 'failed') THEN 'completed'
                            ELSE 'running'
                        END
                        WHERE id = %s
                    """, (task_id, task_id))
                    
                    print(f'{phone}注册失败：{error_msg}')
                    
                    # 即使出错也应用延迟
                    random_time = random.randint(min_delay, max_delay)
                    print('-' * 20, f'延迟{random_time}秒后继续')
                    time.sleep(random_time)
                    
                    # 检查停止标志
                    if task_stop_flags.get(task_id):
                        print(f'任务 {task_id} 已停止')
                        cursor.execute("UPDATE tasks SET status = 'stopped' WHERE id = %s", (task_id,))
                        connection.commit()
                        return False
            
            # 检查任务是否已完成
            cursor.execute("""
                SELECT total_count, completed_count, existing_count,
                (SELECT COUNT(*) FROM accounts WHERE task_id = %s AND status = 'failed') as failed_count
                FROM tasks WHERE id = %s
            """, (task_id, task_id))
            task_stats = cursor.fetchone()
            if task_stats and task_stats[0] == task_stats[1] + task_stats[2] + task_stats[3]:
                cursor.execute("UPDATE tasks SET status = 'completed' WHERE id = %s", (task_id,))
                
            connection.commit()
            return True
    finally:
        connection.close()
        # 清除任务停止标志
        if task_id in task_stop_flags:
            del task_stop_flags[task_id]

def stop_task(task_id):
    """停止指定的任务"""
    task_stop_flags[task_id] = True
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 更新任务状态为已停止
            cursor.execute("UPDATE tasks SET status = 'stopped' WHERE id = %s", (task_id,))
            connection.commit()
    finally:
        connection.close()

def restart_task(task_id):
    """重新开始指定的任务"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 检查任务状态是否为停止
            cursor.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
            result = cursor.fetchone()
            if result and result[0] == 'stopped':
                # 更新任务状态为pending，准备重新开始
                cursor.execute("UPDATE tasks SET status = 'pending' WHERE id = %s", (task_id,))
                connection.commit()
                return True
            return False
    finally:
        connection.close()

def delete_task(task_id):
    """删除指定的任务及其相关数据"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 删除与任务相关的所有账号记录
            cursor.execute("DELETE FROM accounts WHERE task_id = %s", (task_id,))
            # 删除任务记录
            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            connection.commit()
            return True
    except Exception as e:
        print(f"删除任务失败: {str(e)}")
        return False
    finally:
        connection.close()

def get_completed_count(task_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT completed_count FROM tasks WHERE id = %s", (task_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
    finally:
        connection.close()

def get_pending_tasks():
    """获取所有未完成的任务"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, invite_code, password, min_delay, max_delay FROM tasks WHERE status != 'completed' AND status != 'stopped'")
            return cursor.fetchall()
    finally:
        connection.close()

def get_task_stats(task_id):
    """获取任务统计信息"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT t.total_count, t.completed_count, t.existing_count,
                       GREATEST(0, t.total_count - t.completed_count - t.existing_count) as remaining_count,
                       t.status
                FROM tasks t WHERE t.id = %s
            """, (task_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'total_count': result[0],
                    'completed_count': result[1],
                    'existing_count': result[2],
                    'remaining_count': result[3],
                    'status': result[4]
                }
            return None
    finally:
        connection.close()

def get_pending_accounts(task_id):
    """获取任务中待处理的账号"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, mobile FROM accounts WHERE task_id = %s AND status = 'pending'", (task_id,))
            return cursor.fetchall()
    finally:
        connection.close()

# 初始化数据库表
create_task_table()

if __name__ == '__main__':
    print('app.py模块主要用于提供注册功能和数据库操作，如需执行批量注册请使用Flask应用界面')