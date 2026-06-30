/**
 * dashboard/static/dashboard/js/theme.js — Phase 12
 * =====================================================
 * Theme color resolver for Chart.js integration.
 *
 * Provides a centralized palette that reads CSS custom properties
 * from the active theme (light/dark) and notifies registered
 * callbacks when the theme changes.
 *
 * USAGE:
 *   import: <script src="theme.js"></script> (before charts.js)
 *   const colors = SOCTheme.getColors();
 *   SOCTheme.onThemeChange((newColors) => { ... });
 *
 * DESIGN:
 *   - Reads computed CSS variables from document.documentElement.
 *   - Uses MutationObserver on <html> data-theme attribute.
 *   - No direct DOM manipulation — pure color resolution.
 */

const SOCTheme = (() => {
    'use strict';

    // Registered theme-change callbacks
    const _listeners = [];

    /**
     * Read a CSS custom property value from the document root.
     * @param {string} varName - CSS variable name (e.g., '--soc-danger')
     * @returns {string} The computed value
     */
    const _getCSSVar = (varName) => {
        return getComputedStyle(document.documentElement)
            .getPropertyValue(varName)
            .trim();
    };

    /**
     * Get the current theme name.
     * @returns {'dark'|'light'}
     */
    const getCurrentTheme = () => {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    };

    /**
     * Build the full color palette from current CSS variables.
     * Returns semantic colors for use in Chart.js datasets.
     *
     * @returns {Object} Color palette
     */
    const getColors = () => {
        const theme = getCurrentTheme();

        return {
            // Semantic severity colors
            critical: _getCSSVar('--soc-danger'),
            high: _getCSSVar('--soc-warning'),
            medium: _getCSSVar('--soc-info'),
            low: _getCSSVar('--soc-text-muted'),

            // Semantic severity colors (with alpha for fills)
            criticalAlpha: _alphaize(_getCSSVar('--soc-danger'), 0.2),
            highAlpha: _alphaize(_getCSSVar('--soc-warning'), 0.2),
            mediumAlpha: _alphaize(_getCSSVar('--soc-info'), 0.2),
            lowAlpha: _alphaize(_getCSSVar('--soc-text-muted'), 0.15),

            // UI colors
            accent: _getCSSVar('--soc-accent'),
            accentAlpha: _alphaize(_getCSSVar('--soc-accent'), 0.15),
            success: _getCSSVar('--soc-success'),
            successAlpha: _alphaize(_getCSSVar('--soc-success'), 0.15),
            danger: _getCSSVar('--soc-danger'),
            dangerAlpha: _alphaize(_getCSSVar('--soc-danger'), 0.15),
            warning: _getCSSVar('--soc-warning'),
            info: _getCSSVar('--soc-info'),

            // Text colors
            textPrimary: _getCSSVar('--soc-text-primary'),
            textSecondary: _getCSSVar('--soc-text-secondary'),
            textMuted: _getCSSVar('--soc-text-muted'),

            // Surface / Grid
            surface: _getCSSVar('--soc-bg-surface'),
            border: _getCSSVar('--soc-border'),
            gridColor: theme === 'dark'
                ? 'rgba(255, 255, 255, 0.06)'
                : 'rgba(0, 0, 0, 0.06)',
            gridZeroColor: theme === 'dark'
                ? 'rgba(255, 255, 255, 0.1)'
                : 'rgba(0, 0, 0, 0.1)',

            // Tooltip
            tooltipBg: theme === 'dark'
                ? 'rgba(17, 24, 39, 0.95)'
                : 'rgba(255, 255, 255, 0.97)',
            tooltipText: theme === 'dark' ? '#f1f5f9' : '#0f172a',
            tooltipBorder: theme === 'dark'
                ? 'rgba(255, 255, 255, 0.1)'
                : 'rgba(0, 0, 0, 0.1)',

            // Chart-specific palette (for multi-series)
            palette: theme === 'dark'
                ? ['#38bdf8', '#8b5cf6', '#10b981', '#f59e0b', '#f43f5e',
                   '#60a5fa', '#a78bfa', '#34d399', '#fbbf24', '#fb7185']
                : ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626',
                   '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'],

            // Current theme identifier
            theme: theme,
        };
    };

    /**
     * Convert a hex or CSS color to rgba with given alpha.
     * @param {string} color - Hex color (e.g., '#38bdf8') or CSS color
     * @param {number} alpha - Alpha value (0-1)
     * @returns {string} RGBA color string
     */
    const _alphaize = (color, alpha) => {
        // Handle hex colors
        if (color.startsWith('#')) {
            const hex = color.replace('#', '');
            const r = parseInt(hex.substring(0, 2), 16);
            const g = parseInt(hex.substring(2, 4), 16);
            const b = parseInt(hex.substring(4, 6), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        }
        // Handle rgb() format
        const match = color.match(/\d+/g);
        if (match && match.length >= 3) {
            return `rgba(${match[0]}, ${match[1]}, ${match[2]}, ${alpha})`;
        }
        return color;
    };

    /**
     * Register a callback for theme changes.
     * Callback receives the new color palette as its argument.
     *
     * @param {Function} callback - fn(colors)
     */
    const onThemeChange = (callback) => {
        if (typeof callback === 'function') {
            _listeners.push(callback);
        }
    };

    /**
     * Notify all registered listeners with the new palette.
     */
    const _notifyListeners = () => {
        // Use requestAnimationFrame to let CSS variables update first
        requestAnimationFrame(() => {
            const colors = getColors();
            _listeners.forEach(cb => {
                try {
                    cb(colors);
                } catch (err) {
                    console.error('[SOCTheme] Listener error:', err);
                }
            });
        });
    };

    // ==========================================
    // MutationObserver: watch data-theme changes
    // ==========================================
    const _observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (
                mutation.type === 'attributes' &&
                mutation.attributeName === 'data-theme'
            ) {
                _notifyListeners();
                break;
            }
        }
    });

    // Start observing when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            _observer.observe(document.documentElement, {
                attributes: true,
                attributeFilter: ['data-theme'],
            });
        });
    } else {
        _observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme'],
        });
    }

    // Public API
    return {
        getColors,
        getCurrentTheme,
        onThemeChange,
    };
})();
