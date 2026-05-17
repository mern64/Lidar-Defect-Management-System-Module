(function () {
  'use strict';

  /* ── Toast ──────────────────────────────────────────── */
  function ldmsToast(message, type) {
    type = type || 'success';
    var container = document.getElementById('ldms-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'ldms-toast-container';
      container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:8px;';
      document.body.appendChild(container);
    }
    var toast = document.createElement('div');
    toast.className = 'ldms-toast ' + type;
    var icon = type === 'success' ? 'check-circle' : type === 'error' ? 'times-circle' : 'info-circle';
    toast.innerHTML =
      '<i class="fas fa-' + icon + '" style="color: var(--ldms-toast-' + type + '); font-size: 1.2rem;"></i>' +
      '<span>' + message + '</span>';
    var isLight = document.body.classList.contains('light-mode');
    toast.style.background = isLight ? 'var(--ldms-toast-bg-light)' : 'var(--ldms-toast-bg-dark)';
    toast.style.color = isLight ? 'var(--ldms-toast-text-light)' : 'var(--ldms-toast-text-dark)';
    toast.style.boxShadow = isLight ? '0 4px 20px rgba(0,0,0,0.12)' : '0 16px 36px rgba(0,0,0,0.35)';
    container.appendChild(toast);
    setTimeout(function () {
      toast.style.animation = 'ldms-slide-in 0.3s ease-out reverse';
      setTimeout(function () { toast.remove(); }, 300);
    }, 3500);
  }

  /* ── Flash messages → toasts ────────────────────────── */
  function ldmsFlashToasts() {
    var container = document.getElementById('ldms-flash-data');
    if (!container) return;
    var raw = container.getAttribute('data-messages');
    if (!raw || raw === '[]' || raw === "''") return;
    try {
      var messages = JSON.parse(raw);
      if (!messages || !messages.length) return;
      messages.forEach(function (m) { ldmsToast(m[1], m[0]); });
    } catch (e) { /* ignore */ }
  }

  /* ── Theme ───────────────────────────────────────────── */
  function ldmsApplyTheme() {
    var theme = localStorage.getItem('ldms-theme') || localStorage.getItem('theme') || 'light';
    if (!localStorage.getItem('ldms-theme') && localStorage.getItem('theme-set') !== '1') {
      theme = 'light';
    }
    document.body.classList.toggle('light-mode', theme === 'light');
  }
  function ldmsToggleTheme() {
    var body = document.body;
    var current = localStorage.getItem('ldms-theme') || 'light';
    var theme = current === 'dark' ? 'light' : 'dark';
    body.classList.toggle('light-mode', theme === 'light');
    localStorage.setItem('ldms-theme', theme);
    localStorage.setItem('theme', theme);
    localStorage.setItem('theme-set', '1');
  }
  window.ldmsToggleTheme = ldmsToggleTheme;

  /* ── Lightbox ────────────────────────────────────────── */
  window.ldmsOpenLightbox = function (src) {
    var lb = document.getElementById('ldms-lightbox');
    var img = document.getElementById('ldms-lightbox-img');
    if (lb && img) { img.src = src; lb.classList.add('active'); document.body.style.overflow = 'hidden'; }
  };
  window.ldmsCloseLightbox = function () {
    var lb = document.getElementById('ldms-lightbox');
    if (lb) { lb.classList.remove('active'); document.body.style.overflow = 'auto'; }
  };

  /* ── Loading overlay ─────────────────────────────────── */
  window.ldmsShowLoader = function (msg) {
    var el = document.getElementById('ldms-loader');
    if (el) {
      var t = el.querySelector('.ldms-loader-text');
      if (t && msg) t.textContent = msg;
      el.classList.add('active');
    }
  };
  window.ldmsHideLoader = function () {
    var el = document.getElementById('ldms-loader');
    if (el) el.classList.remove('active');
  };

  /* ── Confirm dialog (SweetAlert2) ────────────────────── */
  window.ldmsConfirm = function (options) {
    return new Promise(function (resolve) {
      function _show() {
        var isLight = document.body.classList.contains('light-mode');
        var iconColor = options.icon === 'error' ? '#ef4444' : '#f59e0b';
        resolve(Swal.fire({
          title: options.title || 'Are you sure?',
          text: options.text || '',
          icon: options.icon || 'warning',
          showCancelButton: true,
          confirmButtonColor: options.confirmColor || '#ef4444',
          cancelButtonColor: '#6b7280',
          confirmButtonText: options.confirmText || 'Yes',
          cancelButtonText: 'Cancel',
          reverseButtons: true,
          focusCancel: true,
          customClass: {
            popup: 'ldms-swal',
            title: 'ldms-swal-title',
            htmlContainer: 'ldms-swal-text',
            confirmButton: 'ldms-swal-confirm',
            cancelButton: 'ldms-swal-cancel',
            icon: 'ldms-swal-icon',
          },
        }));
      }
      if (typeof Swal !== 'undefined') return _show();
      var chk = setInterval(function () {
        if (typeof Swal !== 'undefined') { clearInterval(chk); _show(); }
      }, 50);
    });
  };

  /* ── Clipboard ───────────────────────────────────────── */
  window.ldmsCopy = function (text) {
    navigator.clipboard.writeText(text).then(function () {
      ldmsToast('Copied to clipboard!', 'success');
    }).catch(function () {
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta);
      ldmsToast('Copied to clipboard!', 'success');
    });
  };

  /* ── NProgress (HTMX integration) ────────────────────── */
  if (typeof htmx !== 'undefined') {
    var npCount = 0;
    htmx.on('htmx:beforeSend', function (e) {
      npCount++; if (npCount === 1) NProgress.start();
      /* Add skeleton overlay to target */
      var target = e.detail.target;
      if (target) target.classList.add('ldms-skeleton-loading');
    });
    htmx.on('htmx:afterSwap', function (e) {
      npCount = Math.max(0, npCount - 1); if (npCount === 0) NProgress.done();
      var target = e.detail.target;
      if (target) target.classList.remove('ldms-skeleton-loading');
    });

    htmx.on('htmx:sendError', function () { npCount = 0; NProgress.done(); });
    htmx.on('htmx:timeout', function () { npCount = 0; NProgress.done(); });
    /* Re-init Alpine after HTMX content swap */
    htmx.on('htmx:afterSettle', function () {
      if (typeof Alpine !== 'undefined') {
        Alpine.initTree(document.body);
      }
    });
  }

  /* ── Hamburger nav toggle ────────────────────────────── */
  window.ldmsToggleNav = function () {
    var menu = document.getElementById('ldms-nav-menu');
    if (menu) menu.classList.toggle('open');
  };

  /* ── Page fade-in ────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    document.body.classList.add('ldms-page-transition');
  });

  /* ── Global keydown ──────────────────────────────────── */
  var _gBuffer = false;
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      _gBuffer = false;
      var drawer = document.querySelector('.defect-drawer.active');
      if (drawer && window.closeDefectDrawer) { window.closeDefectDrawer(); e.preventDefault(); }
      var modal = document.querySelector('.modal-overlay.active');
      if (modal && window.closeModal) { window.closeModal(); e.preventDefault(); }
      var lightbox = document.getElementById('ldms-lightbox');
      if (lightbox && lightbox.classList.contains('active')) { ldmsCloseLightbox(); e.preventDefault(); }
      return;
    }
    if (e.key === 'g' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
      _gBuffer = true;
      setTimeout(function () { _gBuffer = false; }, 800);
      return;
    }
    if (_gBuffer && e.key === 's') {
      _gBuffer = false;
      e.preventDefault();
      var searchModal = document.getElementById('ldms-search-modal');
      var searchInput = searchModal && searchModal.querySelector('input');
      if (searchInput) { searchInput.focus(); }
      return;
    }
    if (e.key === 'n' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
      var addBtn = document.querySelector('[data-shortcut="new-defect"]');
      if (addBtn) { e.preventDefault(); addBtn.click(); return; }
    }
  });

  /* ── DOM ready ───────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    ldmsApplyTheme();
    ldmsFlashToasts();
    var themeBtn = document.getElementById('ldms-theme-btn');
    if (themeBtn) themeBtn.addEventListener('click', ldmsToggleTheme);
    var lbClose = document.getElementById('ldms-lightbox-close');
    if (lbClose) lbClose.addEventListener('click', ldmsCloseLightbox);
    var lb = document.getElementById('ldms-lightbox');
    if (lb) lb.addEventListener('click', ldmsCloseLightbox);
    document.querySelectorAll('form').forEach(function (f) {
      f.addEventListener('submit', function () {
        ldmsShowLoader('Submitting and processing…');
        f.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (btn) {
          btn.disabled = true;
          btn.setAttribute('aria-busy', 'true');
          /* Add spinner to button */
          if (btn.tagName === 'BUTTON' && !btn.querySelector('.ldms-btn-spinner')) {
            var sp = document.createElement('i');
            sp.className = 'fas fa-spinner fa-spin ldms-btn-spinner';
            sp.style.marginRight = '6px';
            btn.insertBefore(sp, btn.firstChild);
          }
        });
      });
    });
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        var opts = {
          title: el.getAttribute('data-confirm-title') || 'Are you sure?',
          text: el.getAttribute('data-confirm') || '',
          icon: el.getAttribute('data-confirm-icon') || 'warning',
          confirmText: el.getAttribute('data-confirm-btn') || 'Confirm',
        };
        ldmsConfirm(opts).then(function (result) {
          if (result.isConfirmed) {
            if (el.tagName === 'A') window.location.href = el.href;
            else if (el.tagName === 'BUTTON' || el.tagName === 'INPUT') {
              var form = el.closest('form');
              if (form) form.submit();
            }
          }
        });
      });
    });
  });

  /* ── Password Visibility Toggle ───────────────── */ 
  window.ldmsTogglePw = function(id) {
    var inp = document.getElementById(id);
    if (!inp) return;
    var btn = inp.parentElement.querySelector('.ldms-pw-toggle i');
    if (inp.type === 'password') {
      inp.type = 'text';
      if (btn) { btn.className = 'fas fa-eye-slash'; }
    } else {
      inp.type = 'password';
      if (btn) { btn.className = 'fas fa-eye'; }
    }
  };

  /* Expose for inline use */
  window.ldmsToast = ldmsToast;
})();
