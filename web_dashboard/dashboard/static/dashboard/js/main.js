/**
 * dashboard/static/dashboard/js/main.js — UI/UX Redesign v2
 * =====================================================
 * SOC Dashboard interactivity:
 *  - Light/Dark Theme Toggle with localStorage
 *  - Sidebar Collapse/Expand with tooltips
 *  - Toast auto-dismiss with fade-out
 *  - Smooth UX enhancements
 */

document.addEventListener('DOMContentLoaded', () => {

    // ==========================================
    // Theme Toggle
    // ==========================================
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');

    const storedTheme = localStorage.getItem('soc-theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    let currentTheme = storedTheme || (systemPrefersDark ? 'dark' : 'light');

    const applyTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        if (themeIcon) {
            themeIcon.classList.remove('bi-moon-fill', 'bi-sun-fill');
            themeIcon.classList.add(theme === 'dark' ? 'bi-sun-fill' : 'bi-moon-fill');
        }
    };

    applyTheme(currentTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('soc-theme', currentTheme);
            applyTheme(currentTheme);
        });
    }

    // ==========================================
    // Sidebar Collapse with Tooltips
    // ==========================================
    const sidebarDesktop = document.getElementById('sidebar-desktop');
    const sidebarToggleBtn = document.getElementById('sidebar-toggle');
    let sidebarTooltips = [];

    const initSidebarTooltips = () => {
        // Dispose existing tooltips
        sidebarTooltips.forEach(t => t.dispose());
        sidebarTooltips = [];

        if (sidebarDesktop && sidebarDesktop.classList.contains('collapsed')) {
            const links = sidebarDesktop.querySelectorAll('.sidebar-link[title]');
            links.forEach(link => {
                const tip = new bootstrap.Tooltip(link, {
                    placement: 'right',
                    trigger: 'hover',
                    container: 'body'
                });
                sidebarTooltips.push(tip);
            });
        }
    };

    // Restore sidebar state
    const storedSidebarState = localStorage.getItem('soc-sidebar-state');
    if (storedSidebarState === 'collapsed' && sidebarDesktop) {
        sidebarDesktop.classList.add('collapsed');
    }
    initSidebarTooltips();

    if (sidebarToggleBtn && sidebarDesktop) {
        sidebarToggleBtn.addEventListener('click', () => {
            sidebarDesktop.classList.toggle('collapsed');
            localStorage.setItem('soc-sidebar-state',
                sidebarDesktop.classList.contains('collapsed') ? 'collapsed' : 'expanded'
            );
            initSidebarTooltips();
        });
    }

    // ==========================================
    // Toast Auto-Dismiss
    // ==========================================
    const messagesContainer = document.getElementById('messages-container');
    if (messagesContainer) {
        const toasts = messagesContainer.querySelectorAll('.soc-toast');
        toasts.forEach((toast, index) => {
            // Stagger dismiss: 5s + 0.5s per toast
            const delay = 5000 + (index * 500);
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.classList.add('toast-hide');
                    setTimeout(() => toast.remove(), 300);
                }
            }, delay);
        });
    }

    // ==========================================
    // Keyboard Navigation
    // ==========================================
    document.addEventListener('keydown', (e) => {
        // Escape key closes offcanvas
        if (e.key === 'Escape') {
            const offcanvas = document.querySelector('.offcanvas.show');
            if (offcanvas) {
                const bsOffcanvas = bootstrap.Offcanvas.getInstance(offcanvas);
                if (bsOffcanvas) bsOffcanvas.hide();
            }
        }
    });

    // ==========================================
    // Ambient Parallax Effect
    // ==========================================
    const ambientGrid = document.querySelector('.ambient-grid');
    const ambientBlobs = document.querySelectorAll('.ambient-blob');
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    
    if (!prefersReducedMotion && (ambientGrid || ambientBlobs.length > 0)) {
        let mouseX = 0;
        let mouseY = 0;
        let currentX = 0;
        let currentY = 0;
        
        document.addEventListener('mousemove', (e) => {
            mouseX = (e.clientX / window.innerWidth - 0.5) * 30; // Max movement 15px
            mouseY = (e.clientY / window.innerHeight - 0.5) * 30;
        });
        
        // Smooth interpolation
        const renderParallax = () => {
            currentX += (mouseX - currentX) * 0.05;
            currentY += (mouseY - currentY) * 0.05;
            
            if (ambientGrid) {
                ambientGrid.style.transform = `translate(${currentX * 0.5}px, ${currentY * 0.5}px)`;
            }
            
            ambientBlobs.forEach((blob, index) => {
                const factor = (index + 1) * 0.7;
                blob.style.transform = `translate(${-currentX * factor}px, ${-currentY * factor}px)`;
            });
            
            requestAnimationFrame(renderParallax);
        };
        
        requestAnimationFrame(renderParallax);
    }

    // ==========================================
    // Fade-in animation for main content
    // ==========================================
    const mainContent = document.getElementById('main-content');
    if (mainContent) {
        mainContent.classList.add('fade-in-up');
    }
});
