function goToTaskDetails(taskId) {
    window.location.href = '/task/' + taskId;
}

function stopTask(taskId) {
    if (confirm('确定要停止这个任务吗？')) {
        fetch(`/stop_task/${taskId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('任务已停止');
                location.reload(); // 重新加载页面以更新状态
            } else {
                alert('停止任务失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('停止任务时发生错误');
        });
    }
}

function restartTask(taskId) {
    if (confirm('确定要重新开始这个任务吗？')) {
        fetch(`/restart_task/${taskId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('任务已重新开始');
                location.reload(); // 重新加载页面以更新状态
            } else {
                alert('重新开始任务失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('重新开始任务时发生错误');
        });
    }
}

function deleteTask(taskId) {
    if (confirm('确定要删除这个任务吗？此操作不可撤销！')) {
        fetch(`/delete_task/${taskId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('任务已删除');
                location.reload(); // 重新加载页面以更新状态
            } else {
                alert('删除任务失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('删除任务时发生错误');
        });
    }
}

function openModal() {
    document.getElementById('taskModal').style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    document.getElementById('taskModal').style.display = 'none';
    document.body.style.overflow = 'auto';
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('taskModal');
    if (event.target === modal) {
        closeModal();
    }
}

// ESC键关闭模态框
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeModal();
    }
});