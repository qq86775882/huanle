from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import tempfile
from flask_app import register, create_task_with_phones, execute_task, get_db_connection, get_pending_tasks, get_task_stats, get_pending_accounts, stop_task, restart_task, delete_task
import threading
import signal
import sys

app = Flask(__name__, static_folder='static')
app.secret_key = 'your-secret-key-here'  # Change this to a random secret key

# 存储正在运行的任务线程
running_tasks = {}

def start_pending_tasks():
    """启动应用时检查并继续执行未完成的任务"""
    pending_tasks = get_pending_tasks()
    for task in pending_tasks:
        task_id, invite_code, password, min_delay, max_delay = task
        # 获取任务统计信息
        stats = get_task_stats(task_id)
        if stats and stats['status'] not in ['completed', 'stopped']:
            # 创建并启动任务线程
            thread = threading.Thread(target=execute_task, args=(task_id,))
            thread.daemon = True  # 设置为守护线程
            thread.start()
            running_tasks[task_id] = thread
            print(f"继续执行未完成的任务: {task_id}")


def signal_handler(sig, frame):
    """处理程序退出信号"""
    print('正在停止所有任务...')
    # 等待所有任务线程结束
    for task_id, thread in running_tasks.items():
        if thread.is_alive():
            print(f'正在等待任务 {task_id} 结束...')
            # 注意：由于Python的限制，我们无法强制终止线程
            # 这里只是记录正在等待
    print('所有任务已停止，正在关闭服务...')
    sys.exit(0)


@app.route('/')
def index():
    # 获取所有任务列表
    connection = get_db_connection()
    tasks = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, invite_code, password, total_count, completed_count, existing_count, status, created_at FROM tasks ORDER BY created_at DESC")
            task_rows = cursor.fetchall()
            
            # 为每个任务获取统计信息
            for task_row in task_rows:
                task_id = task_row[0]
                stats = get_task_stats(task_id)
                if stats:
                    tasks.append({
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'total_count': stats['total_count'],
                        'completed_count': stats['completed_count'],
                        'existing_count': stats['existing_count'],
                        'remaining_count': stats['remaining_count'],
                        'status': stats['status'],
                        'created_at': task_row[7].strftime('%Y-%m-%d %H:%M:%S') if task_row[7] else ''
                    })
                else:
                    # 如果没有统计信息，使用默认值
                    existing_count = task_row[5] or 0
                    remaining_count = max(0, task_row[3] - task_row[4] - existing_count) if task_row[3] is not None and task_row[4] is not None else 0
                    tasks.append({
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'total_count': task_row[3],
                        'completed_count': task_row[4],
                        'existing_count': existing_count,
                        'remaining_count': remaining_count,
                        'status': task_row[6],
                        'created_at': task_row[7].strftime('%Y-%m-%d %H:%M:%S') if task_row[7] else ''
                    })
    finally:
        connection.close()
    
    return render_template('index.html', tasks=tasks)


@app.route('/create_task', methods=['POST'])
def create_task_route():
    # 获取表单数据
    invite_code = request.form.get('invite_code')
    password = request.form.get('password')
    min_delay = int(request.form.get('min_delay', 1))
    max_delay = int(request.form.get('max_delay', 5))
    
    # 获取多行文本输入的手机号
    phone_text = request.form.get('phone_text', '')
    phones = [line.strip() for line in phone_text.split('\n') if line.strip()]
    
    if not phones:
        flash('请至少输入一个手机号')
        return redirect(url_for('index'))
    
    # 创建任务并保存手机号
    task_id = create_task_with_phones(invite_code, password, min_delay, max_delay, phones)
    
    # 创建并启动任务线程
    thread = threading.Thread(target=execute_task, args=(task_id,))
    thread.daemon = True  # 设置为守护线程
    thread.start()
    running_tasks[task_id] = thread
    
    flash(f'任务创建成功，任务ID: {task_id}')
    return redirect(url_for('index'))


@app.route('/tasks')
def get_tasks():
    # 获取所有任务列表
    connection = get_db_connection()
    tasks = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, invite_code, password, total_count, completed_count, existing_count, status, created_at FROM tasks ORDER BY created_at DESC")
            task_rows = cursor.fetchall()
            
            # 为每个任务获取统计信息
            for task_row in task_rows:
                task_id = task_row[0]
                stats = get_task_stats(task_id)
                if stats:
                    tasks.append({
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'total_count': stats['total_count'],
                        'completed_count': stats['completed_count'],
                        'existing_count': stats['existing_count'],
                        'remaining_count': stats['remaining_count'],
                        'status': stats['status'],
                        'created_at': task_row[7].strftime('%Y-%m-%d %H:%M:%S') if task_row[7] else ''
                    })
                else:
                    existing_count = task_row[5] or 0
                    remaining_count = max(0, task_row[3] - task_row[4] - existing_count) if task_row[3] is not None and task_row[4] is not None else 0
                    tasks.append({
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'total_count': task_row[3],
                        'completed_count': task_row[4],
                        'existing_count': existing_count,
                        'remaining_count': remaining_count,
                        'status': task_row[6],
                        'created_at': task_row[7].strftime('%Y-%m-%d %H:%M:%S') if task_row[7] else ''
                    })
    finally:
        connection.close()
    
    return jsonify(tasks)


@app.route('/task/<task_id>')
def get_task_details(task_id):
    # 获取特定任务的详细信息
    connection = get_db_connection()
    task_info = {}
    accounts = []
    total_count = 0
    completed_count = 0
    existing_count = 0
    remaining_count = 0
    is_completed = False
    
    try:
        with connection.cursor() as cursor:
            # 获取任务信息
            cursor.execute("SELECT id, invite_code, password, min_delay, max_delay, total_count, completed_count, existing_count, status, created_at FROM tasks WHERE id = %s", (task_id,))
            task_row = cursor.fetchone()
            
            if task_row:
                stats = get_task_stats(task_id)
                if stats:
                    task_info = {
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'min_delay': task_row[3],
                        'max_delay': task_row[4],
                        'total_count': stats['total_count'],
                        'completed_count': stats['completed_count'],
                        'existing_count': stats['existing_count'],
                        'remaining_count': stats['remaining_count'],
                        'status': stats['status'],
                        'created_at': task_row[9].strftime('%Y-%m-%d %H:%M:%S') if task_row[9] else ''
                    }
                    is_completed = stats['status'] == 'completed'
                else:
                    existing_count = task_row[7] or 0
                    remaining_count = max(0, task_row[5] - task_row[6] - existing_count) if task_row[5] is not None and task_row[6] is not None else 0
                    task_info = {
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'min_delay': task_row[3],
                        'max_delay': task_row[4],
                        'total_count': task_row[5],
                        'completed_count': task_row[6],
                        'existing_count': existing_count,
                        'remaining_count': remaining_count,
                        'status': task_row[8],
                        'created_at': task_row[9].strftime('%Y-%m-%d %H:%M:%S') if task_row[9] else ''
                    }
                    is_completed = task_row[8] == 'completed'
                
                # 获取该任务的账号列表
                cursor.execute("SELECT mobile, status, result, created_at FROM accounts WHERE task_id = %s ORDER BY created_at", (task_id,))
                raw_accounts = cursor.fetchall()
                
                # 格式化账号列表中的时间
                for account in raw_accounts:
                    formatted_account = (
                        account[0],  # mobile
                        account[1],  # status
                        account[2],  # result
                        account[3].strftime('%Y-%m-%d %H:%M:%S') if account[3] else ''  # formatted created_at
                    )
                    accounts.append(formatted_account)
    finally:
        connection.close()
    
    return render_template('task_details.html', 
                           task=task_info, 
                           accounts=accounts, 
                           total_count=task_info.get('total_count', 0), 
                           completed_count=task_info.get('completed_count', 0), 
                           existing_count=task_info.get('existing_count', 0),
                           remaining_count=task_info.get('remaining_count', 0),
                           is_completed=is_completed)


@app.route('/api/task/<task_id>/data')
def get_task_data(task_id):
    # 专门用于返回任务数据的API端点，供前端AJAX请求使用
    connection = get_db_connection()
    task_info = {}
    accounts = []
    total_count = 0
    completed_count = 0
    existing_count = 0
    remaining_count = 0
    is_completed = False
    
    try:
        with connection.cursor() as cursor:
            # 获取任务信息
            cursor.execute("SELECT id, invite_code, password, min_delay, max_delay, total_count, completed_count, existing_count, status, created_at FROM tasks WHERE id = %s", (task_id,))
            task_row = cursor.fetchone()
            
            if task_row:
                stats = get_task_stats(task_id)
                if stats:
                    task_info = {
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'min_delay': task_row[3],
                        'max_delay': task_row[4],
                        'total_count': stats['total_count'],
                        'completed_count': stats['completed_count'],
                        'existing_count': stats['existing_count'],
                        'remaining_count': stats['remaining_count'],
                        'status': stats['status'],
                        'created_at': task_row[9].strftime('%Y-%m-%d %H:%M:%S') if task_row[9] else ''
                    }
                    is_completed = stats['status'] == 'completed'
                else:
                    existing_count = task_row[7] or 0
                    remaining_count = max(0, task_row[5] - task_row[6] - existing_count) if task_row[5] is not None and task_row[6] is not None else 0
                    task_info = {
                        'id': task_row[0],
                        'invite_code': task_row[1],
                        'password': task_row[2],
                        'min_delay': task_row[3],
                        'max_delay': task_row[4],
                        'total_count': task_row[5],
                        'completed_count': task_row[6],
                        'existing_count': existing_count,
                        'remaining_count': remaining_count,
                        'status': task_row[8],
                        'created_at': task_row[9].strftime('%Y-%m-%d %H:%M:%S') if task_row[9] else ''
                    }
                    is_completed = task_row[8] == 'completed'
                
                # 获取该任务的账号列表
                cursor.execute("SELECT mobile, status, result, created_at FROM accounts WHERE task_id = %s ORDER BY created_at", (task_id,))
                raw_accounts = cursor.fetchall()
                
                # 格式化账号列表中的时间
                for account in raw_accounts:
                    formatted_account = (
                        account[0],  # mobile
                        account[1],  # status
                        account[2],  # result
                        account[3].strftime('%Y-%m-%d %H:%M:%S') if account[3] else ''  # formatted created_at
                    )
                    accounts.append(formatted_account)
    finally:
        connection.close()
    
    return jsonify({
        'task_info': task_info,
        'accounts': accounts,
        'total_count': task_info.get('total_count', 0),
        'completed_count': task_info.get('completed_count', 0),
        'existing_count': task_info.get('existing_count', 0),
        'remaining_count': task_info.get('remaining_count', 0),
        'is_completed': is_completed
    })


@app.route('/stop_task/<task_id>', methods=['POST'])
def stop_task_route(task_id):
    """停止指定的任务"""
    try:
        stop_task(task_id)
        return jsonify({'success': True, 'message': '任务已停止'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/restart_task/<task_id>', methods=['POST'])
def restart_task_route(task_id):
    """重新开始指定的任务"""
    try:
        if restart_task(task_id):
            # 重新启动任务线程
            thread = threading.Thread(target=execute_task, args=(task_id,))
            thread.daemon = True  # 设置为守护线程
            thread.start()
            running_tasks[task_id] = thread
            return jsonify({'success': True, 'message': '任务已重新开始'})
        else:
            return jsonify({'success': False, 'message': '任务无法重新开始'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/delete_task/<task_id>', methods=['POST'])
def delete_task_route(task_id):
    """删除指定的任务"""
    try:
        # 首先停止任务（如果正在运行）
        stop_task(task_id)
        
        # 等待一段时间确保任务线程停止
        import time
        time.sleep(0.1)
        
        # 删除任务
        if delete_task(task_id):
            return jsonify({'success': True, 'message': '任务已删除'})
        else:
            return jsonify({'success': False, 'message': '任务删除失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动应用时检查并继续执行未完成的任务
    start_pending_tasks()
    try:
        app.run(debug=True, host='0.0.0.0', port=20294)
    except KeyboardInterrupt:
        signal_handler(None, None)