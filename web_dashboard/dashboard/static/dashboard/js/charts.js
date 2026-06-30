/**
 * dashboard/static/dashboard/js/charts.js — Phase 12
 * =====================================================
 * Chart.js factory for the SOC Dashboard.
 *
 * Provides a `SOCCharts` namespace with factory methods for creating
 * themed Chart.js instances. Each chart type is pre-configured with
 * SOC design system colors, fonts, and interaction patterns.
 *
 * USAGE:
 *   const ctx = document.getElementById('my-chart').getContext('2d');
 *   const chart = SOCCharts.createDoughnut(ctx, { ... });
 *   // Later: chart.destroy();
 *
 * DEPENDENCIES:
 *   - Chart.js 4.x (loaded via CDN)
 *   - SOCTheme (theme.js, must be loaded first)
 *
 * DESIGN:
 *   - All charts use SOCTheme.getColors() for theming.
 *   - No global Chart.defaults mutation — each chart is self-contained.
 *   - Factory pattern allows easy creation and destruction for theme changes.
 */

const SOCCharts = (() => {
    'use strict';

    /**
     * Common chart options shared across all chart types.
     * @param {Object} colors - Color palette from SOCTheme
     * @returns {Object} Base Chart.js options
     */
    const _baseOptions = (colors) => ({
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: 600,
            easing: 'easeOutQuart',
        },
        plugins: {
            legend: {
                display: true,
                position: 'bottom',
                labels: {
                    color: colors.textSecondary,
                    font: {
                        family: "'Inter', sans-serif",
                        size: 11,
                        weight: '500',
                    },
                    padding: 16,
                    usePointStyle: true,
                    pointStyleWidth: 8,
                    boxWidth: 8,
                    boxHeight: 8,
                },
            },
            tooltip: {
                backgroundColor: colors.tooltipBg,
                titleColor: colors.tooltipText,
                bodyColor: colors.tooltipText,
                borderColor: colors.tooltipBorder,
                borderWidth: 1,
                padding: 12,
                cornerRadius: 8,
                titleFont: {
                    family: "'Inter', sans-serif",
                    size: 12,
                    weight: '600',
                },
                bodyFont: {
                    family: "'Inter', sans-serif",
                    size: 12,
                    weight: '400',
                },
                displayColors: true,
                boxWidth: 8,
                boxHeight: 8,
                boxPadding: 4,
                usePointStyle: true,
            },
        },
    });

    /**
     * Common scale options for cartesian charts.
     * @param {Object} colors - Color palette
     * @returns {Object} Scale configuration
     */
    const _scaleOptions = (colors) => ({
        x: {
            grid: {
                color: colors.gridColor,
                drawBorder: false,
            },
            ticks: {
                color: colors.textMuted,
                font: {
                    family: "'Inter', sans-serif",
                    size: 11,
                },
                maxRotation: 45,
                autoSkip: true,
                maxTicksLimit: 12,
            },
            border: {
                display: false,
            },
        },
        y: {
            grid: {
                color: colors.gridColor,
                drawBorder: false,
            },
            ticks: {
                color: colors.textMuted,
                font: {
                    family: "'Inter', sans-serif",
                    size: 11,
                },
                padding: 8,
            },
            border: {
                display: false,
            },
            beginAtZero: true,
        },
    });

    /**
     * Format a date string for chart labels.
     * @param {string} dateStr - ISO date string (YYYY-MM-DD)
     * @returns {string} Formatted label (e.g., "Jun 15")
     */
    const _formatDate = (dateStr) => {
        try {
            const date = new Date(dateStr + 'T00:00:00');
            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
            });
        } catch {
            return dateStr;
        }
    };

    // ==========================================
    // Factory Methods
    // ==========================================

    /**
     * Create a doughnut chart (severity distribution, analysis status).
     *
     * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
     * @param {Object} config
     * @param {string[]} config.labels - Segment labels
     * @param {number[]} config.data - Segment values
     * @param {string[]} config.colors - Background colors
     * @param {string[]} [config.borderColors] - Border colors
     * @param {string} [config.centerText] - Optional center text
     * @returns {Chart} Chart.js instance
     */
    const createDoughnut = (ctx, config) => {
        const themeColors = SOCTheme.getColors();
        const options = _baseOptions(themeColors);

        // Customize for doughnut
        options.cutout = '68%';
        options.plugins.legend.position = 'right';
        options.plugins.legend.labels.padding = 12;

        // Center text plugin
        const centerTextPlugin = config.centerText ? {
            id: 'centerText',
            afterDraw(chart) {
                const { ctx: chartCtx, chartArea } = chart;
                const centerX = (chartArea.left + chartArea.right) / 2;
                const centerY = (chartArea.top + chartArea.bottom) / 2;

                chartCtx.save();
                chartCtx.textAlign = 'center';
                chartCtx.textBaseline = 'middle';

                // Value
                chartCtx.font = "700 24px 'Inter', sans-serif";
                chartCtx.fillStyle = themeColors.textPrimary;
                const total = config.data.reduce((a, b) => a + b, 0);
                chartCtx.fillText(total.toLocaleString(), centerX, centerY - 8);

                // Label
                chartCtx.font = "500 11px 'Inter', sans-serif";
                chartCtx.fillStyle = themeColors.textMuted;
                chartCtx.fillText(config.centerText, centerX, centerY + 14);

                chartCtx.restore();
            },
        } : null;

        return new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: config.labels,
                datasets: [{
                    data: config.data,
                    backgroundColor: config.colors,
                    borderColor: config.borderColors || config.colors.map(
                        c => c.replace(/[\d.]+\)$/, '0.3)')
                    ),
                    borderWidth: 2,
                    hoverBorderWidth: 3,
                    hoverOffset: 4,
                    spacing: 2,
                    borderRadius: 3,
                }],
            },
            options,
            plugins: centerTextPlugin ? [centerTextPlugin] : [],
        });
    };

    /**
     * Create a line/area chart (anomalies over time, trends).
     *
     * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
     * @param {Object} config
     * @param {string[]} config.labels - X-axis labels
     * @param {Object[]} config.datasets - Array of dataset configs
     * @param {boolean} [config.stacked] - Stack datasets
     * @param {boolean} [config.fill] - Fill area under line
     * @returns {Chart} Chart.js instance
     */
    const createLine = (ctx, config) => {
        const themeColors = SOCTheme.getColors();
        const options = _baseOptions(themeColors);

        options.scales = _scaleOptions(themeColors);

        if (config.stacked) {
            options.scales.y.stacked = true;
            options.scales.x.stacked = true;
        }

        // Interaction
        options.interaction = {
            mode: 'index',
            intersect: false,
        };

        // Format datasets with SOC styling
        const datasets = config.datasets.map((ds, i) => ({
            label: ds.label,
            data: ds.data,
            borderColor: ds.color || themeColors.palette[i],
            backgroundColor: ds.fillColor || (config.fill
                ? (ds.color || themeColors.palette[i]).replace(')', ', 0.1)').replace('rgb(', 'rgba(')
                : 'transparent'),
            borderWidth: 2,
            pointRadius: ds.data.length > 30 ? 0 : 3,
            pointHoverRadius: 5,
            pointBackgroundColor: ds.color || themeColors.palette[i],
            pointBorderColor: themeColors.surface || '#fff',
            pointBorderWidth: 2,
            tension: 0.4,
            fill: config.fill || false,
        }));

        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: config.labels,
                datasets,
            },
            options,
        });
    };

    /**
     * Create a bar chart (event distribution, login comparison).
     *
     * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
     * @param {Object} config
     * @param {string[]} config.labels - X-axis labels
     * @param {Object[]} config.datasets - Array of dataset configs
     * @param {boolean} [config.stacked] - Stack bars
     * @param {boolean} [config.horizontal] - Horizontal bars
     * @returns {Chart} Chart.js instance
     */
    const createBar = (ctx, config) => {
        const themeColors = SOCTheme.getColors();
        const options = _baseOptions(themeColors);

        options.scales = _scaleOptions(themeColors);

        if (config.stacked) {
            options.scales.y.stacked = true;
            options.scales.x.stacked = true;
        }

        if (config.horizontal) {
            options.indexAxis = 'y';
            options.scales.x.ticks.maxRotation = 0;
        }

        // Format datasets
        const datasets = config.datasets.map((ds, i) => ({
            label: ds.label,
            data: ds.data,
            backgroundColor: ds.color || themeColors.palette[i],
            borderColor: 'transparent',
            borderWidth: 0,
            borderRadius: 4,
            borderSkipped: false,
            maxBarThickness: config.horizontal ? 18 : 40,
            hoverBackgroundColor: ds.hoverColor || ds.color || themeColors.palette[i],
        }));

        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: config.labels,
                datasets,
            },
            options,
        });
    };

    // Public API
    return {
        createDoughnut,
        createLine,
        createBar,
    };
})();
