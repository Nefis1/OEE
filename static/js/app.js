// static/js/app.js
class OEEDashboard {
    constructor() {
        this.minuteHeatmap = null;
        this.oeeGauge = null;
        this.minuteData = this.createEmptyMinuteData();
        this.lastProductionCount = null;
        this.lastPowerValue = 0;
        this.updateInterval = 3000;
        this.zoomLevel = 1;
        this.visibleHours = 24; // Показывать все 24 часа по умолчанию
        this.currentView = 'all'; // 'all' или 'shift'

        this.initCharts();
        this.loadHistoricalData();
        this.startAutoUpdate();
        this.setupScrollHint();
    }

    createEmptyMinuteData() {
        return Array.from({ length: 24 }, () => new Array(60).fill(0));
    }

    async loadHistoricalData() {
        try {
            const response = await fetch('/api/minute_power');
            const data = await response.json();

            if (data.minute_power) {
                this.minuteData = data.minute_power;
                this.updateMinuteHeatmap();
            }
        } catch (error) {
            console.error('Ошибка загрузки исторических данных:', error);
        }
    }

    initCharts() {
        const heatmapCtx = document.getElementById('minuteHeatmap');
        if (heatmapCtx) {
            // Устанавливаем фиксированную ширину для обеспечения прокрутки
            heatmapCtx.style.width = '2400px'; // 24 часа * 100px на час

            const hourLabels = Array.from({ length: 24 }, (_, i) =>
                i.toString().padStart(2, '0')
            );

            // Создаем данные для графика - группируем по минутам
            const datasets = [];
            for (let minute = 0; minute < 60; minute++) {
                datasets.push({
                    label: `Минута ${minute}`,
                    data: Array(24).fill(0),
                    backgroundColor: Array(24).fill('rgba(52, 152, 219, 0.6)'),
                    borderColor: Array(24).fill('#3498db'),
                    borderWidth: 0.5,
                    borderRadius: 2,
                    borderSkipped: false,
                    categoryPercentage: 0.9,
                    barPercentage: 0.8 / 60, // 60 минут распределяем по ширине бара
                });
            }

            this.minuteHeatmap = new Chart(heatmapCtx, {
                type: 'bar',
                data: {
                    labels: hourLabels,
                    datasets: datasets
                },
                options: {
                    responsive: false, // Важно: отключаем responsive для ручного управления размером
                    maintainAspectRatio: false,
                    indexAxis: 'x',
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                title: (context) => {
                                    const hour = context[0].dataIndex;
                                    const minute = context[0].datasetIndex;
                                    return `Время: ${hour}:${minute.toString().padStart(2, '0')}`;
                                },
                                label: (context) => {
                                    const power = context.raw;
                                    return `Мощность: ${power} шт/мин`;
                                },
                                afterLabel: (context) => {
                                    const hour = context.dataIndex;
                                    const currentHour = new Date().getHours();
                                    if (hour === currentHour) {
                                        return '🕒 Текущий час';
                                    }
                                    return null;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Часы суток',
                                font: {
                                    size: 12,
                                    weight: 'bold'
                                }
                            },
                            grid: {
                                display: true,
                                color: 'rgba(0,0,0,0.05)'
                            },
                            stacked: true
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Произв. мощность (шт/мин)',
                                font: {
                                    size: 12,
                                    weight: 'bold'
                                }
                            },
                            beginAtZero: true,
                            suggestedMax: 50,
                            grid: {
                                color: 'rgba(0,0,0,0.1)'
                            },
                            ticks: {
                                stepSize: 10
                            }
                        }
                    },
                    animation: {
                        duration: 800,
                        easing: 'easeOutQuart'
                    },
                    interaction: {
                        mode: 'nearest',
                        intersect: false
                    }
                }
            });

            // Инициализируем размер графика
            this.updateChartSize();
        }

        // OEE Gauge (оставляем как было)
        const gaugeCtx = document.getElementById('oeeGauge');
        if (gaugeCtx) {
            this.oeeGauge = new Chart(gaugeCtx, {
                type: 'doughnut',
                data: {
                    labels: ['OEE', ''],
                    datasets: [{
                        data: [0, 100],
                        backgroundColor: ['#27ae60', '#ecf0f1'],
                        borderWidth: 0,
                        circumference: 180,
                        rotation: -90
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            enabled: false
                        }
                    }
                }
            });
        }
    }

    updateChartSize() {
        if (!this.minuteHeatmap) return;

        const chartWrapper = document.querySelector('.chart-wrapper');
        if (chartWrapper) {
            const baseWidth = 2400; // Базовая ширина для 24 часов
            const newWidth = baseWidth * this.zoomLevel;

            this.minuteHeatmap.canvas.style.width = newWidth + 'px';
            this.minuteHeatmap.canvas.style.height = '380px';

            // Обновляем видимость часов в зависимости от текущего вида
            this.updateVisibleHours();

            this.minuteHeatmap.update('resize');
        }
    }

    updateVisibleHours() {
        if (!this.minuteHeatmap) return;

        const totalHours = 24;
        let startHour = 0;
        let endHour = totalHours;

        if (this.currentView === 'shift') {
            const now = new Date();
            const currentHour = now.getHours();
            // Показываем 8 часов вокруг текущего времени
            startHour = Math.max(0, currentHour - 4);
            endHour = Math.min(totalHours, currentHour + 4);
            this.visibleHours = endHour - startHour;
        } else {
            this.visibleHours = totalHours;
        }

        // Прокручиваем к текущему часу
        this.scrollToCurrentHour();
    }

    scrollToCurrentHour() {
        const chartWrapper = document.querySelector('.chart-wrapper');
        if (chartWrapper) {
            const now = new Date();
            const currentHour = now.getHours();
            const hourWidth = (2400 * this.zoomLevel) / 24;
            const scrollPosition = Math.max(0, (currentHour * hourWidth) - (chartWrapper.clientWidth / 2));

            chartWrapper.scrollTo({
                left: scrollPosition,
                behavior: 'smooth'
            });
        }
    }

    setupScrollHint() {
        const chartWrapper = document.querySelector('.chart-wrapper');
        if (chartWrapper) {
            // Убираем подсказку прокрутки через 5 секунд
            setTimeout(() => {
                const existingHint = document.querySelector('.scroll-hint');
                if (existingHint) {
                    existingHint.remove();
                }
            }, 5000);
        }
    }

    zoomIn() {
        this.zoomLevel = Math.min(this.zoomLevel * 1.5, 4);
        this.updateZoomDisplay();
        this.updateChartSize();
    }

    zoomOut() {
        this.zoomLevel = Math.max(this.zoomLevel / 1.5, 0.5);
        this.updateZoomDisplay();
        this.updateChartSize();
    }

    updateZoomDisplay() {
        const zoomLevelEl = document.getElementById('zoom-level');
        if (zoomLevelEl) {
            zoomLevelEl.textContent = `${this.zoomLevel.toFixed(1)}x`;
        }
    }

    showAllHours() {
        this.currentView = 'all';
        this.zoomLevel = 1;
        this.updateZoomDisplay();
        this.updateChartSize();

        // Прокручиваем к началу
        const chartWrapper = document.querySelector('.chart-wrapper');
        if (chartWrapper) {
            chartWrapper.scrollTo({ left: 0, behavior: 'smooth' });
        }
    }

    showCurrentShift() {
        this.currentView = 'shift';
        this.zoomLevel = 2;
        this.updateZoomDisplay();
        this.updateChartSize();
    }

    updateMinuteHeatmap() {
        if (!this.minuteHeatmap) return;

        const currentTime = new Date();
        const currentHour = currentTime.getHours();
        const currentMinute = currentTime.getMinutes();

        // Обновляем данные для каждой минуты
        for (let minute = 0; minute < 60; minute++) {
            const minuteData = [];
            for (let hour = 0; hour < 24; hour++) {
                minuteData.push(this.minuteData[hour]?.[minute] || 0);
            }

            if (this.minuteHeatmap.data.datasets[minute]) {
                this.minuteHeatmap.data.datasets[minute].data = minuteData;
                this.minuteHeatmap.data.datasets[minute].backgroundColor =
                    this.getMinuteColors(minuteData, currentHour, minute, currentMinute);
            }
        }

        const maxPower = this.getMaxPower();
        this.minuteHeatmap.options.scales.y.suggestedMax = Math.max(maxPower * 1.1, 20);
        this.updatePowerLegend(maxPower);
        this.updateCurrentTime();

        this.minuteHeatmap.update('active');
    }

    getMinuteColors(minuteData, currentHour, minute, currentMinute) {
        const maxPower = this.getMaxPower();

        return minuteData.map((power, hour) => {
            if (power === 0) return 'rgba(149, 165, 166, 0.2)';

            const ratio = power / maxPower;
            let color;

            if (ratio < 0.3) {
                color = [46, 204, 113];
            } else if (ratio < 0.7) {
                color = [241, 196, 15];
            } else {
                color = [231, 76, 60];
            }

            let opacity = 0.5;
            if (hour === currentHour && minute === currentMinute) {
                opacity = 0.9;
            } else if (hour === currentHour) {
                opacity = 0.7;
            }

            return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${opacity})`;
        });
    }

    getMaxPower() {
        let max = 0;
        for (let hour = 0; hour < 24; hour++) {
            for (let minute = 0; minute < 60; minute++) {
                max = Math.max(max, this.minuteData[hour]?.[minute] || 0);
            }
        }
        return Math.max(max, 1);
    }

    updatePowerLegend(maxPower) {
        const maxPowerLabel = document.getElementById('max-power-label');
        if (maxPowerLabel) {
            maxPowerLabel.textContent = `${Math.ceil(maxPower)}+ шт/мин`;
        }
    }

    updateCurrentTime() {
        const currentTimeEl = document.getElementById('current-time');
        if (currentTimeEl) {
            const now = new Date();
            currentTimeEl.textContent = now.toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            });
        }
    }

    // ... остальные методы (updateDashboard, updateKPIs, updatePowerKPI и т.д.) остаются без изменений ...
    // ВАЖНО: Сохраните все остальные методы из предыдущей версии без изменений

    async updateDashboard() {
        try {
            const response = await fetch('/api/current_data');
            const data = await response.json();

            if (data.production_data && data.oee_data) {
                this.updateKPIs(data);
                this.updateProductionData(data);
                this.updateOEEGauge(data.oee_data);
                this.updateDowntimeAlert(data.downtime_status);
                this.updateShiftInfo(data.shift_info);
                this.updateLastUpdate(data.last_update);
            }
        } catch (error) {
            console.error('Ошибка обновления данных:', error);
        }
    }

    updateKPIs(data) {
        // OEE
        const oeeValue = document.getElementById('oee-value');
        if (oeeValue) {
            oeeValue.textContent = `${data.oee_data.oee_percentage}%`;
            this.setOeeClass(oeeValue, data.oee_data.oee_percentage);
        }

        // Availability
        const availabilityEl = document.getElementById('availability-value');
        if (availabilityEl) {
            availabilityEl.textContent = `${data.oee_data.availability}%`;
        }

        // Performance
        const performanceEl = document.getElementById('performance-value');
        if (performanceEl) {
            performanceEl.textContent = `${data.oee_data.performance}%`;
        }

        // Quality
        const qualityEl = document.getElementById('quality-value');
        if (qualityEl) {
            qualityEl.textContent = `${data.oee_data.quality}%`;
        }

        // Production
        const productionEl = document.getElementById('production-value');
        if (productionEl && data.production_data.ivams_total) {
            productionEl.textContent = `${data.production_data.ivams_total.toLocaleString()} шт`;
        }

        // Current Power
        this.updatePowerKPI(data);
    }

    updatePowerKPI(data) {
        const powerKpiEl = document.getElementById('current-power-kpi');
        const powerStatusEl = document.getElementById('power-status');

        if (!powerKpiEl || !powerStatusEl || !data.production_data) return;

        const currentProduction = data.production_data.ivams_total;
        let currentPower = 0;

        if (this.lastProductionCount !== null && currentProduction > this.lastProductionCount) {
            const produced = currentProduction - this.lastProductionCount;
            currentPower = Math.round(produced * 20);
        }

        powerKpiEl.textContent = `${currentPower} шт/мин`;

        let powerClass = 'idle';
        let statusText = 'Оборудование остановлено';

        if (currentPower > 0) {
            if (currentPower >= 30) {
                powerClass = 'high';
                statusText = 'Высокая производительность';
            } else if (currentPower >= 15) {
                powerClass = 'medium';
                statusText = 'Стабильная работа';
            } else {
                powerClass = 'low';
                statusText = 'Низкая производительность';
            }
        }

        powerKpiEl.className = `kpi-value power-value ${powerClass}`;
        powerStatusEl.textContent = statusText;

        if (currentPower !== this.lastPowerValue) {
            powerKpiEl.classList.add('power-changing');
            setTimeout(() => {
                powerKpiEl.classList.remove('power-changing');
            }, 500);
        }

        this.lastPowerValue = currentPower;
        this.lastProductionCount = currentProduction;
        this.updateMinuteData(currentPower);
    }

    updateMinuteData(currentPower) {
        const now = new Date();
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();

        if (currentPower > this.minuteData[currentHour]?.[currentMinute]) {
            if (!this.minuteData[currentHour]) {
                this.minuteData[currentHour] = new Array(60).fill(0);
            }
            this.minuteData[currentHour][currentMinute] = currentPower;
            this.updateMinuteHeatmap();
        }
    }

    updateProductionData(data) {
        const powerValueEl = document.getElementById('current-power-value');
        if (powerValueEl && this.lastPowerValue !== undefined) {
            powerValueEl.textContent = this.lastPowerValue;
        }
    }

    setOeeClass(element, value) {
        element.className = 'kpi-value ';
        if (value >= 85) {
            element.classList.add('oee-excellent');
        } else if (value >= 65) {
            element.classList.add('oee-good');
        } else {
            element.classList.add('oee-poor');
        }
    }

    updateOEEGauge(oeeData) {
        if (!this.oeeGauge) return;

        this.oeeGauge.data.datasets[0].data = [
            oeeData.oee_percentage,
            100 - oeeData.oee_percentage
        ];

        const color = oeeData.oee_percentage >= 85 ? '#27ae60' :
            oeeData.oee_percentage >= 65 ? '#f39c12' : '#e74c3c';

        this.oeeGauge.data.datasets[0].backgroundColor = [color, '#ecf0f1'];
        this.oeeGauge.update();
    }

    updateDowntimeAlert(downtimeStatus) {
        const alertElement = document.getElementById('downtime-alert');
        if (alertElement) {
            if (downtimeStatus && downtimeStatus.is_downtime) {
                alertElement.style.display = 'block';
            } else {
                alertElement.style.display = 'none';
            }
        }
    }

    updateShiftInfo(shiftInfo) {
        if (shiftInfo) {
            const shiftValue = document.getElementById('shift-value');
            const shiftTime = document.getElementById('shift-time');

            if (shiftValue) {
                shiftValue.textContent = `Смена ${shiftInfo.number}`;
            }

            if (shiftTime && shiftInfo.start && shiftInfo.end) {
                const startTime = shiftInfo.start.slice(0, 5);
                const endTime = shiftInfo.end.slice(0, 5);
                shiftTime.textContent = `${startTime} - ${endTime}`;
            }
        }
    }

    updateLastUpdate(timestamp) {
        if (timestamp) {
            const date = new Date(timestamp);
            const timeString = date.toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            const lastUpdateEl = document.getElementById('last-update');
            if (lastUpdateEl) {
                lastUpdateEl.textContent = `Последнее обновление: ${timeString}`;
            }
        }
    }

    startAutoUpdate() {
        this.updateDashboard();
        setInterval(() => {
            this.updateDashboard();
        }, this.updateInterval);
    }
}

// Запускаем dashboard когда страница загружена
document.addEventListener('DOMContentLoaded', function () {
    window.dashboard = new OEEDashboard();
});