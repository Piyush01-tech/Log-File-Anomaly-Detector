/**
 * dashboard/static/dashboard/js/dashboard.js — Phase 12
 * =====================================================
 * Page-level analytics orchestrator for the SOC Dashboard.
 *
 * Fetches data from the /api/analytics/ endpoint and renders
 * Chart.js visualizations using the SOCCharts factory. Manages
 * loading skeletons, empty states, and theme change re-renders.
 *
 * DEPENDENCIES:
 *   - Chart.js 4.x (CDN)
 *   - SOCTheme (theme.js)
 *   - SOCCharts (charts.js)
 *
 * LIFECYCLE:
 *   1. DOMContentLoaded → init()
 *   2. Fetch /api/analytics/ → showLoading() during fetch
 *   3. On success → renderAllCharts() → hideLoading()
 *   4. On theme change → destroyAllCharts() → renderAllCharts()
 */

const DashboardAnalytics = (() => {
    'use strict';

    // Store active Chart.js instances for destroy/recreate
    let _charts = {};
    let _analyticsData = null;
    let _isLoading = false;

    /**
     * Initialize the analytics dashboard.
     * Called once on DOMContentLoaded from the home page template.
     */
    const init = () => {
        // Only run on pages with analytics containers
        const analyticsSection = document.getElementById('analytics-section');
        if (!analyticsSection) return;

        // Register theme change handler
        SOCTheme.onThemeChange(_onThemeChange);

        // Fetch data and render charts
        _fetchAndRender();
    };

    /**
     * Fetch analytics data and render all charts.
     */
    const _fetchAndRender = async () => {
        if (_isLoading) return;
        _isLoading = true;

        _showAllLoading();

        try {
            const analyticsSection = document.getElementById('analytics-section');
            const apiUrl = analyticsSection?.dataset?.apiUrl || '/api/analytics/';
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const json = await response.json();

            if (json.status !== 'success') {
                throw new Error(json.message || 'Unknown API error');
            }

            _analyticsData = json.data;
            _renderAllCharts();

        } catch (error) {
            console.error('[DashboardAnalytics] Fetch error:', error);
            _showAllError(error.message);
        } finally {
            _isLoading = false;
            _hideAllLoading();
        }
    };

    /**
     * Destroy all active charts and re-render with current theme colors.
     */
    const _onThemeChange = () => {
        if (!_analyticsData) return;

        _destroyAllCharts();

        // Small delay to let CSS variables update
        setTimeout(() => {
            _renderAllCharts();
        }, 50);
    };

    /**
     * Render all chart visualizations from cached data.
     */
    const _renderAllCharts = () => {
        if (!_analyticsData) return;

        const data = _analyticsData;

        _renderSeverityDistribution(data.severity_distribution);
        _renderAnomaliesOverTime(data.anomalies_over_time);
        _renderLoginTrends(data.login_trends);
        _renderLoginComparison(data.login_trends);
        _renderTopEventIds(data.top_event_ids);
        _renderTopHosts(data.top_hosts);
        _renderAnalysisStatus(data.analysis_status);
        _renderRecentActivity(data.recent_activity);
        _renderSystemHealth(data.system_health);
    };

    /**
     * Destroy all active Chart.js instances.
     */
    const _destroyAllCharts = () => {
        Object.values(_charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        _charts = {};
    };

    // ==========================================
    // Individual Chart Renderers
    // ==========================================

    /**
     * Severity Distribution — Doughnut Chart
     */
    const _renderSeverityDistribution = (data) => {
        const canvas = document.getElementById('chart-severity');
        if (!canvas || !data) return;

        const colors = SOCTheme.getColors();
        const hasData = Object.values(data).some(v => v > 0);

        if (!hasData) {
            _showChartEmpty('chart-severity');
            return;
        }
        _hideChartEmpty('chart-severity');

        _charts['severity'] = SOCCharts.createDoughnut(
            canvas.getContext('2d'),
            {
                labels: ['Critical', 'High', 'Medium', 'Low'],
                data: [data.CRITICAL, data.HIGH, data.MEDIUM, data.LOW],
                colors: [colors.critical, colors.high, colors.medium, colors.low],
                centerText: 'Total',
            }
        );
    };

    /**
     * Anomalies Over Time — Stacked Area Chart
     */
    const _renderAnomaliesOverTime = (data) => {
        const canvas = document.getElementById('chart-anomalies-time');
        if (!canvas || !data) return;

        if (!data.length) {
            _showChartEmpty('chart-anomalies-time');
            return;
        }
        _hideChartEmpty('chart-anomalies-time');

        const colors = SOCTheme.getColors();
        const labels = data.map(d => _formatDate(d.date));

        _charts['anomaliesTime'] = SOCCharts.createLine(
            canvas.getContext('2d'),
            {
                labels,
                datasets: [
                    {
                        label: 'Critical',
                        data: data.map(d => d.critical),
                        color: colors.critical,
                        fillColor: colors.criticalAlpha,
                    },
                    {
                        label: 'High',
                        data: data.map(d => d.high),
                        color: colors.high,
                        fillColor: colors.highAlpha,
                    },
                    {
                        label: 'Medium',
                        data: data.map(d => d.medium),
                        color: colors.medium,
                        fillColor: colors.mediumAlpha,
                    },
                    {
                        label: 'Low',
                        data: data.map(d => d.low),
                        color: colors.low,
                        fillColor: colors.lowAlpha,
                    },
                ],
                stacked: true,
                fill: true,
            }
        );
    };

    /**
     * Failed Login Trend — Line Chart
     */
    const _renderLoginTrends = (data) => {
        const canvas = document.getElementById('chart-login-trend');
        if (!canvas || !data) return;

        if (!data.length) {
            _showChartEmpty('chart-login-trend');
            return;
        }
        _hideChartEmpty('chart-login-trend');

        const colors = SOCTheme.getColors();
        const labels = data.map(d => _formatDate(d.date));

        _charts['loginTrend'] = SOCCharts.createLine(
            canvas.getContext('2d'),
            {
                labels,
                datasets: [
                    {
                        label: 'Failed Logins',
                        data: data.map(d => d.failed),
                        color: colors.danger,
                        fillColor: colors.dangerAlpha,
                    },
                ],
                fill: true,
            }
        );
    };

    /**
     * Successful vs Failed Logins — Stacked Bar Chart
     */
    const _renderLoginComparison = (data) => {
        const canvas = document.getElementById('chart-login-comparison');
        if (!canvas || !data) return;

        if (!data.length) {
            _showChartEmpty('chart-login-comparison');
            return;
        }
        _hideChartEmpty('chart-login-comparison');

        const colors = SOCTheme.getColors();
        const labels = data.map(d => _formatDate(d.date));

        _charts['loginComparison'] = SOCCharts.createBar(
            canvas.getContext('2d'),
            {
                labels,
                datasets: [
                    {
                        label: 'Successful',
                        data: data.map(d => d.success),
                        color: colors.success,
                    },
                    {
                        label: 'Failed',
                        data: data.map(d => d.failed),
                        color: colors.danger,
                    },
                ],
                stacked: true,
            }
        );
    };

    /**
     * Top Event IDs — Horizontal Bar Chart
     */
    const _renderTopEventIds = (data) => {
        const canvas = document.getElementById('chart-top-events');
        if (!canvas || !data) return;

        if (!data.length) {
            _showChartEmpty('chart-top-events');
            return;
        }
        _hideChartEmpty('chart-top-events');

        const colors = SOCTheme.getColors();

        _charts['topEvents'] = SOCCharts.createBar(
            canvas.getContext('2d'),
            {
                labels: data.map(d => d.label),
                datasets: [{
                    label: 'Occurrences',
                    data: data.map(d => d.count),
                    color: colors.palette.slice(0, data.length),
                }],
                horizontal: true,
            }
        );
    };

    /**
     * Top Targeted Hosts — Horizontal Bar Chart
     */
    const _renderTopHosts = (data) => {
        const canvas = document.getElementById('chart-top-hosts');
        if (!canvas || !data) return;

        if (!data.length) {
            _showChartEmpty('chart-top-hosts');
            return;
        }
        _hideChartEmpty('chart-top-hosts');

        const colors = SOCTheme.getColors();

        _charts['topHosts'] = SOCCharts.createBar(
            canvas.getContext('2d'),
            {
                labels: data.map(d => d.hostname),
                datasets: [{
                    label: 'Anomalies',
                    data: data.map(d => d.count),
                    color: colors.accent,
                }],
                horizontal: true,
            }
        );
    };

    /**
     * Analysis Status Distribution — Doughnut Chart
     */
    const _renderAnalysisStatus = (data) => {
        const canvas = document.getElementById('chart-analysis-status');
        if (!canvas || !data) return;

        const hasData = Object.values(data).some(v => v > 0);

        if (!hasData) {
            _showChartEmpty('chart-analysis-status');
            return;
        }
        _hideChartEmpty('chart-analysis-status');

        const colors = SOCTheme.getColors();

        _charts['analysisStatus'] = SOCCharts.createDoughnut(
            canvas.getContext('2d'),
            {
                labels: ['Completed', 'Failed', 'Running', 'Pending'],
                data: [data.COMPLETED, data.FAILED, data.RUNNING, data.PENDING],
                colors: [colors.success, colors.danger, colors.warning, colors.textMuted],
                centerText: 'Jobs',
            }
        );
    };

    /**
     * Recent Activity Timeline — DOM rendering (no chart)
     */
    const _renderRecentActivity = (data) => {
        const container = document.getElementById('activity-timeline');
        if (!container || !data) return;

        if (!data.length) {
            container.innerHTML = `
                <div class="chart-empty-state">
                    <i class="bi bi-clock-history"></i>
                    <p>No recent activity</p>
                </div>
            `;
            return;
        }

        const actionIcons = {
            'Login': 'bi-box-arrow-in-right text-success',
            'Logout': 'bi-box-arrow-right text-muted',
            'Upload': 'bi-cloud-arrow-up text-accent',
            'View': 'bi-eye text-info',
            'Delete': 'bi-trash text-danger',
        };

        let html = '<div class="activity-list">';
        data.forEach(entry => {
            const iconClass = actionIcons[entry.action] || 'bi-activity text-muted';
            const timeAgo = _timeAgo(entry.timestamp);
            html += `
                <div class="activity-item">
                    <div class="activity-icon">
                        <i class="bi ${iconClass}"></i>
                    </div>
                    <div class="activity-content">
                        <div class="activity-text">
                            <strong>${_escapeHtml(entry.user)}</strong>
                            <span class="text-muted">${_escapeHtml(entry.action).toLowerCase()}</span>
                            ${entry.detail ? `<span class="activity-detail">${_escapeHtml(entry.detail)}</span>` : ''}
                        </div>
                        <div class="activity-time">${timeAgo}</div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    };

    /**
     * System Health Summary — DOM rendering (update stat values)
     */
    const _renderSystemHealth = (data) => {
        if (!data) return;

        // Update health metric values if elements exist
        const metrics = {
            'health-success-rate': `${data.success_rate}%`,
            'health-total-samples': data.total_samples.toLocaleString(),
            'health-critical': data.critical_count.toLocaleString(),
            'health-high': data.high_count.toLocaleString(),
        };

        Object.entries(metrics).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) {
                el.textContent = value;
                el.classList.add('metric-loaded');
            }
        });
    };

    // ==========================================
    // Loading & Empty State Management
    // ==========================================

    const _showAllLoading = () => {
        document.querySelectorAll('.chart-skeleton').forEach(el => {
            el.style.display = 'flex';
        });
        document.querySelectorAll('.chart-canvas-wrap').forEach(el => {
            el.style.display = 'none';
        });
    };

    const _hideAllLoading = () => {
        document.querySelectorAll('.chart-skeleton').forEach(el => {
            el.style.display = 'none';
        });
        document.querySelectorAll('.chart-canvas-wrap').forEach(el => {
            el.style.display = 'block';
        });
    };

    const _showChartEmpty = (canvasId) => {
        const card = document.getElementById(canvasId)?.closest('.chart-card');
        if (!card) return;
        const emptyState = card.querySelector('.chart-empty-state');
        const canvasWrap = card.querySelector('.chart-canvas-wrap');
        if (emptyState) emptyState.style.display = 'flex';
        if (canvasWrap) canvasWrap.style.display = 'none';
    };

    const _hideChartEmpty = (canvasId) => {
        const card = document.getElementById(canvasId)?.closest('.chart-card');
        if (!card) return;
        const emptyState = card.querySelector('.chart-empty-state');
        const canvasWrap = card.querySelector('.chart-canvas-wrap');
        if (emptyState) emptyState.style.display = 'none';
        if (canvasWrap) canvasWrap.style.display = 'block';
    };

    const _showAllError = (message) => {
        document.querySelectorAll('.chart-empty-state').forEach(el => {
            el.style.display = 'flex';
            el.innerHTML = `
                <i class="bi bi-exclamation-triangle text-warning"></i>
                <p>Could not load chart data</p>
            `;
        });
    };

    // ==========================================
    // Utility Functions
    // ==========================================

    /**
     * Format a date string for chart labels.
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

    /**
     * Convert an ISO timestamp to a relative time string.
     */
    const _timeAgo = (isoString) => {
        try {
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;

            const diffHours = Math.floor(diffMins / 60);
            if (diffHours < 24) return `${diffHours}h ago`;

            const diffDays = Math.floor(diffHours / 24);
            if (diffDays < 7) return `${diffDays}d ago`;

            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
            });
        } catch {
            return '';
        }
    };

    /**
     * Escape HTML to prevent XSS in dynamic content.
     */
    const _escapeHtml = (str) => {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    /**
     * Refresh analytics data (destroys and re-fetches).
     */
    const refresh = () => {
        _destroyAllCharts();
        _fetchAndRender();
    };

    // Public API
    return {
        init,
        refresh,
    };
})();

// Auto-initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    DashboardAnalytics.init();
});
