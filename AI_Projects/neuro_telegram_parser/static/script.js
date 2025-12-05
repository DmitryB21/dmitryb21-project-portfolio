document.addEventListener('DOMContentLoaded', function() {
    // DOM элементы
    const sourceFilesSelect = document.getElementById('source-files');
    const startParseFileBtn = document.getElementById('start-parse-file');
    const searchQueryInput = document.getElementById('search-query');
    const searchButton = document.getElementById('search-button');
    const searchResultsDiv = document.getElementById('search-results');
    const startParseSearchBtn = document.getElementById('start-parse-search');
    const tasksTableBody = document.querySelector('#tasks-table tbody');
    const fileInfoBox = document.getElementById('file-info');
    const totalChannelsSpan = document.getElementById('total-channels');
    const channelLimitInput = document.getElementById('channel-limit');
    
    // Глобальные переменные
    let searchSelection = [];
    const activeTasks = new Set();
    let currentFileChannelsCount = 0;
    let autoRefresh = true;
    let refreshInterval;

    // === 1. Загрузка файлов-источников ===
    async function loadSourceFiles() {
        try {
            const response = await fetch('/api/v1/sources/files');
            const data = await response.json();
            
            if (data.files && data.files.length > 0) {
                sourceFilesSelect.innerHTML = data.files.map(file => 
                    `<option value="${file}">${file}</option>`
                ).join('');
                loadFileInfo(sourceFilesSelect.value);
            } else {
                sourceFilesSelect.innerHTML = '<option value="">Нет доступных файлов</option>';
                fileInfoBox.style.display = 'none';
            }
        } catch (error) {
            console.error('Ошибка загрузки файлов:', error);
            sourceFilesSelect.innerHTML = '<option value="">Ошибка загрузки</option>';
        }
    }

    async function loadFileInfo(fileName) {
        if (!fileName) {
            fileInfoBox.style.display = 'none';
            return;
        }

        try {
            const response = await fetch(`/api/v1/sources/file-info?file=${encodeURIComponent(fileName)}`);
            const data = await response.json();
            
            if (response.ok && data.channel_count !== undefined) {
                currentFileChannelsCount = data.channel_count;
                totalChannelsSpan.textContent = data.channel_count;
                fileInfoBox.style.display = 'block';
                channelLimitInput.max = data.channel_count;
            } else {
                fileInfoBox.style.display = 'none';
                console.error('Ошибка загрузки информации о файле:', data.error);
            }
        } catch (error) {
            fileInfoBox.style.display = 'none';
            console.error('Ошибка загрузки информации о файле:', error);
        }
    }

    sourceFilesSelect.addEventListener('change', () => loadFileInfo(sourceFilesSelect.value));

    // === 2. Запуск парсинга из файла ===
    startParseFileBtn.addEventListener('click', async () => {
        const sourceFile = sourceFilesSelect.value;
        const messageLimit = parseInt(document.getElementById('limit-file').value, 10);
        const channelLimit = parseInt(channelLimitInput.value, 10);

        if (!sourceFile) {
            alert('Пожалуйста, выберите файл источник.');
            return;
        }

        try {
            const response = await fetch('/api/v1/parse/from-file', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_file: sourceFile,
                    limit_per_channel: messageLimit > 0 ? messageLimit : null,
                    channel_limit: channelLimit > 0 ? channelLimit : null
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                addTaskToMonitor(data.task_id, 'Парсинг из файла', {
                    source: sourceFile,
                    messageLimit: messageLimit,
                    channelLimit: channelLimit
                });
                showNotification('Парсинг запущен!', 'success');
            } else {
                alert(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            console.error('Ошибка запуска парсинга:', error);
            alert('Произошла ошибка при запуске парсинга.');
        }
    });

    // === 3. Поиск каналов ===
    const performSearch = async () => {
        const query = searchQueryInput.value.trim();
        
        if (!query) return;
        
        searchResultsDiv.innerHTML = '<i>Поиск...</i>';
        
        try {
            const response = await fetch(`/api/v1/search/channels?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            searchSelection = [];
            startParseSearchBtn.disabled = true;
            
            if (data.results && data.results.length > 0) {
                const resultsHtml = data.results.map((channel, index) => `
                    <div class="search-item">
                        <input type="checkbox" id="channel-${index}" data-channel-index="${index}">
                        <label for="channel-${index}">
                            <strong>${channel.title}</strong>
                            ${channel.username ? `(@${channel.username})` : ''}
                            <small>ID: ${channel.id}</small>
                        </label>
                    </div>
                `).join('');
                
                searchResultsDiv.innerHTML = resultsHtml;
                searchResultsDiv.dataset.channels = JSON.stringify(data.results);
            } else {
                searchResultsDiv.innerHTML = '<i>Каналы не найдены.</i>';
            }
        } catch (error) {
            console.error('Ошибка поиска:', error);
            searchResultsDiv.innerHTML = '<i>Ошибка поиска.</i>';
        }
    };

    searchButton.addEventListener('click', performSearch);
    searchQueryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // === 4. Выбор каналов для парсинга ===
    searchResultsDiv.addEventListener('change', (e) => {
        if (e.target.type === 'checkbox') {
            const allChannels = JSON.parse(searchResultsDiv.dataset.channels || '[]');
            const channelIndex = parseInt(e.target.dataset.channelIndex, 10);
            const channelData = allChannels[channelIndex];

            if (e.target.checked) {
                searchSelection.push(channelData);
            } else {
                searchSelection = searchSelection.filter(c => c.id !== channelData.id);
            }

            startParseSearchBtn.disabled = searchSelection.length === 0;
        }
    });

    // === 5. Запуск ad-hoc парсинга ===
    startParseSearchBtn.addEventListener('click', async () => {
        const limit = parseInt(document.getElementById('limit-search').value, 10);

        if (searchSelection.length === 0) {
            alert('Пожалуйста, выберите каналы для парсинга.');
            return;
        }

        try {
            const response = await fetch('/api/v1/parse/from-search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    channels: searchSelection,
                    limit_per_channel: limit > 0 ? limit : null
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                addTaskToMonitor(data.task_id, 'Ad-hoc парсинг', {
                    channelsCount: searchSelection.length,
                    limit: limit
                });
                
                // Очистка результатов поиска
                searchResultsDiv.innerHTML = '';
                searchSelection = [];
                startParseSearchBtn.disabled = true;
                searchQueryInput.value = '';
                
                showNotification('Ad-hoc парсинг запущен!', 'success');
            } else {
                alert(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            console.error('Ошибка ad-hoc парсинга:', error);
            alert('Произошла ошибка при запуске парсинга.');
        }
    });

    // === 6. Мониторинг задач ===
    function addTaskToMonitor(taskId, type, metadata = {}) {
        const now = new Date().toLocaleString();
        const row = document.createElement('tr');
        row.id = `task-${taskId}`;
        row.className = 'task-row';
        
        row.innerHTML = `
            <td class="task-id">${taskId}</td>
            <td>${type}</td>
            <td class="status queued">Queued</td>
            <td class="progress-cell">
                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                        <div class="progress-text">0%</div>
                    </div>
                    <div class="progress-stage">Инициализация...</div>
                    <div class="progress-details"></div>
                </div>
            </td>
            <td>${now}</td>
            <td class="task-controls">
                <button class="btn-small btn-info" onclick="showTaskDetails('${taskId}')">Детали</button>
                <button class="btn-small btn-danger" onclick="cancelTask('${taskId}')">Отмена</button>
            </td>
        `;
        
        tasksTableBody.prepend(row);
        activeTasks.add(taskId);
    }

    async function updateTasksStatus() {
        if (activeTasks.size === 0) return;

        for (const taskId of activeTasks) {
            try {
                const response = await fetch(`/api/v1/tasks/status/${taskId}`);
                const data = await response.json();
                
                updateTaskRow(taskId, data);
                
                if (['completed', 'failed'].includes(data.status)) {
                    activeTasks.delete(taskId);
                }
            } catch (error) {
                console.error(`Ошибка получения статуса задачи ${taskId}:`, error);
            }
        }
    }

    function updateTaskRow(taskId, statusData) {
        const row = document.getElementById(`task-${taskId}`);
        if (!row) return;

        const statusCell = row.querySelector('.status');
        const progressCell = row.querySelector('.progress-cell');
        
        // Обновление класса строки
        row.className = `task-row ${statusData.status}`;
        
        // Обновление статуса
        statusCell.textContent = getStatusText(statusData.status);
        statusCell.className = `status ${statusData.status}`;
        
        // Обновление прогресса
        updateProgressIndicator(progressCell, statusData);
    }

    function updateProgressIndicator(progressCell, statusData) {
        const progressBar = progressCell.querySelector('.progress-fill');
        const progressText = progressCell.querySelector('.progress-text');
        const progressStage = progressCell.querySelector('.progress-stage');
        const progressDetails = progressCell.querySelector('.progress-details');
        
        const progress = statusData.progress || {};
        
        // Обновление прогресс-бара
        let percentage = 0;
        if (progress.messages_processed && progress.total_messages) {
            percentage = Math.round((progress.messages_processed / progress.total_messages) * 100);
        } else if (progress.channels_scheduled && progress.total_channels) {
            percentage = Math.round((progress.channels_scheduled / progress.total_channels) * 100);
        } else if (statusData.status === 'completed') {
            percentage = 100;
        }
        
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = `${percentage}%`;
        
        // Обновление стадии
        if (progress.stage) {
            progressStage.textContent = getStageText(progress.stage);
        }
        
        // Детали прогресса
        let detailsHtml = '';
        
        if (progress.current_channel) {
            detailsHtml += `<div class="channel-info">
                <div class="channel-name">${progress.current_channel}</div>
            </div>`;
        }
        
        if (progress.messages_processed !== undefined && progress.total_messages !== undefined) {
            detailsHtml += `<div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">${progress.messages_processed}</div>
                    <div class="stat-label">Обработано</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${progress.total_messages}</div>
                    <div class="stat-label">Всего</div>
                </div>
            </div>`;
        }
        
        if (progress.channel_index !== undefined && progress.total_channels) {
            detailsHtml += `<div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">${progress.channel_index + 1}</div>
                    <div class="stat-label">Канал</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${progress.total_channels}</div>
                    <div class="stat-label">Из</div>
                </div>
            </div>`;
        }
        
        if (statusData.error) {
            detailsHtml += `<div class="error-info" style="color: #e74c3c; font-size: 12px; margin-top: 5px;">
                ${statusData.error}
            </div>`;
        }
        
        progressDetails.innerHTML = detailsHtml;
    }

    function getStatusText(status) {
        const statusMap = {
            'queued': 'В очереди',
            'running': 'Выполняется',
            'completed': 'Завершено',
            'failed': 'Ошибка',
            'cancelled': 'Отменено'
        };
        return statusMap[status] || status;
    }

    function getStageText(stage) {
        const stageMap = {
            'initializing': 'Инициализация...',
            'connecting': 'Подключение к Telegram...',
            'parsing_channel': 'Парсинг канала...',
            'saving_metadata': 'Сохранение метаданных...',
            'processing_messages': 'Обработка сообщений...',
            'completed': 'Завершено',
            'loading_channels': 'Загрузка списка каналов...',
            'validating_channels': 'Валидация каналов...',
            'scheduling_tasks': 'Планирование задач...'
        };
        return stageMap[stage] || stage;
    }

    // === 7. Детали задачи (модальное окно) ===
    window.showTaskDetails = async function(taskId) {
        try {
            const response = await fetch(`/api/v1/tasks/status/${taskId}`);
            const data = await response.json();
            
            showTaskModal(taskId, data);
        } catch (error) {
            console.error('Ошибка получения деталей задачи:', error);
            alert('Не удалось загрузить детали задачи.');
        }
    };

    function showTaskModal(taskId, statusData) {
        const modal = document.getElementById('taskModal') || createTaskModal();
        const modalContent = modal.querySelector('.task-details');
        
        modalContent.innerHTML = `
            <div class="detail-section">
                <h4>Основная информация</h4>
                <p><strong>ID задачи:</strong> ${taskId}</p>
                <p><strong>Статус:</strong> ${getStatusText(statusData.status)}</p>
                <p><strong>Время запуска:</strong> ${statusData.start_time ? new Date(statusData.start_time).toLocaleString() : 'Неизвестно'}</p>
                <p><strong>Время обновления:</strong> ${statusData.updated_at ? new Date(statusData.updated_at).toLocaleString() : 'Неизвестно'}</p>
                ${statusData.duration ? `<p><strong>Длительность:</strong> ${Math.round(statusData.duration)} сек</p>` : ''}
            </div>
            
            <div class="detail-section">
                <h4>Прогресс</h4>
                <div id="modal-progress-details"></div>
            </div>
            
            ${statusData.error ? `
                <div class="detail-section">
                    <h4>Ошибка</h4>
                    <p style="color: #e74c3c;">${statusData.error}</p>
                </div>
            ` : ''}
        `;
        
        // Обновление прогресса в модальном окне
        const modalProgressCell = modal.querySelector('#modal-progress-details');
        updateProgressIndicator({ querySelector: () => modalProgressCell }, statusData);
        
        modal.style.display = 'block';
    }

    function createTaskModal() {
        const modal = document.createElement('div');
        modal.id = 'taskModal';
        modal.className = 'modal';
        
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Детали задачи</h3>
                    <span class="close">&times;</span>
                </div>
                <div class="task-details"></div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Закрытие модального окна
        modal.querySelector('.close').onclick = () => modal.style.display = 'none';
        modal.onclick = (e) => {
            if (e.target === modal) modal.style.display = 'none';
        };
        
        return modal;
    }

    // === 8. Отмена задачи ===
    window.cancelTask = function(taskId) {
        if (confirm('Вы уверены, что хотите отменить эту задачу?')) {
            // Здесь можно добавить API для отмены задачи
            console.log(`Отмена задачи ${taskId}`);
            activeTasks.delete(taskId);
        }
    };

    // === 9. Уведомления ===
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 4px;
            color: white;
            font-weight: bold;
            z-index: 9999;
            animation: slideIn 0.3s ease;
            background-color: ${type === 'success' ? '#2ecc71' : type === 'error' ? '#e74c3c' : '#3498db'};
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    // === 10. Автообновление ===
    function startAutoRefresh() {
        if (refreshInterval) clearInterval(refreshInterval);
        refreshInterval = setInterval(updateTasksStatus, 3000); // Обновление каждые 3 секунды
    }

    function stopAutoRefresh() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }
    }

    // === Инициализация ===
    loadSourceFiles();
    startAutoRefresh();
    
    // Обновление при загрузке страницы
    updateTasksStatus();
    
    console.log('Telegram Parser UI инициализирован');
});