(function () {
  const sidebar    = document.getElementById('sidebar');
  const overlay    = document.getElementById('sidebarOverlay');
  const toggle     = document.getElementById('sidebarToggle');
  const mainContent = document.getElementById('mainContent');
  const TABLET_MIN = 769, TABLET_MAX = 1024;

  // ── Breakpoint helpers ──────────────────────────────────────
  const isMobile = () => window.innerWidth <= 768;
  const isTablet = () => window.innerWidth >= TABLET_MIN && window.innerWidth <= TABLET_MAX;

  // ── Open ────────────────────────────────────────────────────
  function openSidebar() {
    sidebar.classList.add(isMobile() ? 'open' : 'expanded');
    if (isMobile()) {
      overlay.classList.add('show');
      document.body.style.overflow = 'hidden';
    } else if (isTablet()) {
      mainContent.classList.add('sidebar-open');
    }
    toggle.setAttribute('aria-expanded', 'true');
    document.getElementById('toggleIcon').className = 'bi bi-x-lg';
  }
  window.openSidebar = openSidebar;

  // ── Close ───────────────────────────────────────────────────
  function closeSidebar() {
    sidebar.classList.remove('open', 'expanded');
    overlay.classList.remove('show');
    document.body.style.overflow = '';
    mainContent.classList.remove('sidebar-open');
    toggle.setAttribute('aria-expanded', 'false');
    document.getElementById('toggleIcon').className = 'bi bi-list';
  }
  window.closeSidebar = closeSidebar;

  // ── Close only on mobile (tablet keeps state) ───────────────
  function closeSidebarOnMobile() {
    if (isMobile()) closeSidebar();
  }
  window.closeSidebarOnMobile = closeSidebarOnMobile;

  // ── Toggle ──────────────────────────────────────────────────
  toggle.addEventListener('click', function () {
    const isOpenMobile  = isMobile()  && sidebar.classList.contains('open');
    const isOpenTablet  = isTablet()  && sidebar.classList.contains('expanded');
    if (isOpenMobile || isOpenTablet) {
      closeSidebar();
    } else {
      openSidebar();
    }
  });

  // ── Keyboard: Escape closes ─────────────────────────────────
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSidebar();
  });

  // ── Touch swipe (mobile) ────────────────────────────────────
  let touchStartX = null;
  document.addEventListener('touchstart', function (e) {
    touchStartX = e.touches[0].clientX;
  }, { passive: true });

  document.addEventListener('touchend', function (e) {
    if (touchStartX === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (isMobile()) {
      if (dx > 60 && touchStartX < 30) openSidebar();   // swipe right from edge
      if (dx < -60 && sidebar.classList.contains('open')) closeSidebar();
    }
    touchStartX = null;
  }, { passive: true });

  // ── Resize: clean up stale state ───────────────────────────
  let resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      if (window.innerWidth > 1024) {
        // Desktop: reset everything
        sidebar.classList.remove('open', 'expanded');
        overlay.classList.remove('show');
        document.body.style.overflow = '';
        mainContent.classList.remove('sidebar-open');
        document.getElementById('toggleIcon').className = 'bi bi-list';
        toggle.setAttribute('aria-expanded', 'false');
      } else if (isTablet()) {
        // Tablet: kill mobile state
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
        document.body.style.overflow = '';
      } else if (isMobile()) {
        // Mobile: kill tablet state
        sidebar.classList.remove('expanded');
        mainContent.classList.remove('sidebar-open');
      }
    }, 100);
  });

  // ── Notification polling ────────────────────────────────────
  function fetchNotifCount() {
    fetch('{{ url_for("notifications.unread_count") }}')
      .then(r => r.json())
      .then(data => {
        document.querySelectorAll('.notif-badge').forEach(b => {
          if (data.count > 0) {
            b.textContent = data.count > 9 ? '9+' : data.count;
            b.classList.remove('d-none');
          } else {
            b.classList.add('d-none');
          }
        });
        // Bottom nav dot
        const dot = document.getElementById('bottomNavDot');
        if (dot) dot.style.display = data.count > 0 ? 'block' : 'none';
      }).catch(() => {});
  }
  fetchNotifCount();
  setInterval(fetchNotifCount, 30000);

  // ── Cart count polling (external users only) ───────────────
  function fetchCartCount() {
    fetch('/cart/count')
      .then(r => r.json())
      .then(data => {
        const count = data.count || 0;
        // Topbar badge
        const tb = document.getElementById('cartBadge');
        if (tb) { tb.textContent = count; tb.classList.toggle('d-none', count === 0); }
        // Sidebar badge
        const sb = document.getElementById('cartBadgeSide');
        if (sb) { sb.textContent = count; sb.classList.toggle('d-none', count === 0); }
        // Bottom nav badge
        const bb = document.getElementById('cartBadgeBottom');
        if (bb) { bb.textContent = count; bb.style.display = count > 0 ? 'flex' : 'none'; }
      }).catch(() => {});
  }
  // Only poll if user appears to be external (cart elements exist)
  if (document.getElementById('cartBadge') || document.getElementById('cartBadgeSide')) {
    fetchCartCount();
    setInterval(fetchCartCount, 15000);
  }
})();
