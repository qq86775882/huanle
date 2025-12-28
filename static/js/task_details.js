// 从页面数据获取初始状态
const initialTaskStatus = document.querySelector('.task-status').dataset.status || 'pending';
let autoRefreshInterval = null;
let isAutoRefreshEnabled = initialTaskStatus === 'running';
let currentTaskStatus = initialTaskStatus;

function updateTaskData() {
    const taskId = document.querySelector('h1').textContent.includes('任务详情') ? 
        document.querySelector('p').textContent.replace('任务ID: ', '') : null;
    
    if (!taskId) return;
    
    fetch(`/api/task/${taskId}/data`)
        .then(response => response.json())
        .then(data => {
            // 更新统计信息
            document.querySelector('.stat-card.total .value').textContent = data.task_info.total_count;
            document.querySelector('.stat-card.completed .value').textContent = data.task_info.completed_count;
            document.querySelector('.stat-card.existing .value').textContent = data.task_info.existing_count;
            document.querySelector('.stat-card.remaining .value').textContent = data.task_info.remaining_count;
            
            // 更新任务状态
            const statusElement = document.querySelector('.task-status');
            statusElement.className = 'task-status';
            statusElement.classList.add(data.task_info.status === 'completed' ? 'status-completed' : 
                                      data.task_info.status === 'stopped' ? 'status-stopped' : 'status-in-progress');
            statusElement.textContent = data.task_info.status === 'completed' ? '✅ 已完成' :
                                      data.task_info.status === 'stopped' ? '🛑 已停止' : '🔄 进行中';
            statusElement.dataset.status = data.task_info.status;
            
            // 更新自动刷新控制
            const autoRefreshCheckbox = document.getElementById('autoRefresh');
            const refreshStatus = document.querySelector('.refresh-status');
            
            if (data.task_info.status === 'completed' || data.task_info.status === 'stopped') {
                // 如果任务已完成或已停止，禁用自动刷新并停止刷新
                autoRefreshCheckbox.checked = false;
                autoRefreshCheckbox.disabled = true;
                refreshStatus.className = 'refresh-status refresh-inactive';
                refreshStatus.textContent = '⏸️ 已暂停';
                isAutoRefreshEnabled = false;
                currentTaskStatus = data.task_info.status;
                
                if (autoRefreshInterval) {
                    clearInterval(autoRefreshInterval);
                    autoRefreshInterval = null;
                }
            } else {
                // 任务仍在运行中
                currentTaskStatus = data.task_info.status;
                if (isAutoRefreshEnabled) {
                    autoRefreshCheckbox.checked = true;
                    refreshStatus.className = 'refresh-status refresh-active';
                    refreshStatus.textContent = '🔄 刷新中';
                } else {
                    autoRefreshCheckbox.checked = false;
                    refreshStatus.className = 'refresh-status refresh-inactive';
                    refreshStatus.textContent = '⏸️ 已暂停';
                }
            }
            
            // 更新表格内容
            const tableBody = document.getElementById('accountsTableBody');
            tableBody.innerHTML = '';
            
            data.accounts.forEach(account => {
                const row = document.createElement('tr');
                
                // 根据状态确定状态文本
                let statusText = '未知';
                let statusClass = 'status-pending';
                if (account[1] === 'pending') {
                    statusText = '⏳ 待处理';
                    statusClass = 'status-pending';
                } else if (account[1] === 'completed') {
                    statusText = '✅ 已完成';
                    statusClass = 'status-completed';
                } else if (account[1] === 'existing') {
                    statusText = '👤 已存在';
                    statusClass = 'status-existing';
                } else if (account[1] === 'failed') {
                    statusText = '❌ 失败';
                    statusClass = 'status-failed';
                }
                
                row.innerHTML = `
                    <td>${account[0]}</td>
                    <td><span class="${statusClass}">${statusText}</span></td>
                    <td>${account[2]}</td>
                    <td>${account[3]}</td>
                `;
                tableBody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error updating task data:', error);
        });
}

function toggleAutoRefresh() {
    const autoRefreshCheckbox = document.getElementById('autoRefresh');
    isAutoRefreshEnabled = autoRefreshCheckbox.checked;
    
    const refreshStatus = document.querySelector('.refresh-status');
    
    if (isAutoRefreshEnabled && currentTaskStatus === 'running') {
        // 启动自动刷新
        if (!autoRefreshInterval) {
            autoRefreshInterval = setInterval(updateTaskData, 3000); // 每3秒刷新一次
        }
        refreshStatus.className = 'refresh-status refresh-active';
        refreshStatus.textContent = '🔄 刷新中';
    } else {
        // 停止自动刷新
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
        refreshStatus.className = 'refresh-status refresh-inactive';
        refreshStatus.textContent = '⏸️ 已暂停';
    }
}

// 页面加载时初始化自动刷新
document.addEventListener('DOMContentLoaded', function() {
    if (isAutoRefreshEnabled && currentTaskStatus === 'running') {
        // 只有在任务状态为运行中时才启动自动刷新
        autoRefreshInterval = setInterval(updateTaskData, 3000); // 每3秒刷新一次
    }
});