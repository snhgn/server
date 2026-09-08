/**
 * BJFU 课表前端系统 (VaporTang 风格复刻与移动端专属调优)
 * 采用 7 节次块（1-2, 3-4, 5, 6-7, 8-9, 10-11, 12）建模，连续节次自动合并
 * 移动端信息栏深度压缩，确保 10-11 节晚间课程无需滑动全屏立显
 */
(function () {
  'use strict';

  // --- 调色板与配色系统 ---
  const COLOR_PALETTE = [
    { bg: '#EBF3F5', border: '#789CA4' },
    { bg: '#F2F4E6', border: '#94A660' },
    { bg: '#F7ECEC', border: '#BA7C81' },
    { bg: '#F5F0E6', border: '#B59B6D' },
    { bg: '#EAEFF4', border: '#7991A8' },
    { bg: '#EFEDF5', border: '#8A82A3' },
    { bg: '#F6EFEA', border: '#BD8F75' },
    { bg: '#E9F5ED', border: '#72A584' },
    { bg: '#F7EBED', border: '#B87A89' },
    { bg: '#EFF4E6', border: '#8C9E63' },
    { bg: '#F4ECEF', border: '#A67C92' },
    { bg: '#EBF4F5', border: '#6EA0A6' },
    { bg: '#F4F1E6', border: '#A89F82' },
    { bg: '#F6EDE8', border: '#B58778' },
    { bg: '#EAEAE8', border: '#8A8C86' },
    { bg: '#E8F1EE', border: '#6B968B' }
  ];

  // --- 7 节次块定义（与教务排课一致：5节与6-7节独立，10-11节与12节独立，连续块自动合并跨行）---
  const BLOCKS = [
    { label: '1-2', start: 1, end: 2, time: '08:00 - 09:35' },
    { label: '3-4', start: 3, end: 4, time: '10:05 - 11:40' },
    { label: '5', start: 5, end: 5, time: '13:30 - 14:15' },
    { label: '6-7', start: 6, end: 7, time: '14:20 - 15:55' },
    { label: '8-9', start: 8, end: 9, time: '16:15 - 17:50' },
    { label: '10-11', start: 10, end: 11, time: '18:40 - 20:15' },
    { label: '12', start: 12, end: 12, time: '20:20 - 21:05' }
  ];

  const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

  // --- 全局状态 ---
  let rawSchedule = null;
  let allCourses = [];
  let maxWeek = 20;
  let currentWeek = 1;
  let termStartDate = new Date('2026-09-07T00:00:00');
  let isFirstRender = true;
  let isManualSwitch = false;
  let weekSwitching = false;

  // --- DOM 节点 ---
  const grid = document.getElementById('grid');
  const semLabel = document.getElementById('semLabel');
  const weekSelect = document.getElementById('weekSelect');
  const prevWeekBtn = document.getElementById('prevWeek');
  const nextWeekBtn = document.getElementById('nextWeek');
  const todayBtn = document.getElementById('todayBtn');
  const themeBtn = document.getElementById('themeBtn');
  const modalOverlay = document.getElementById('courseModal');
  const mTitle = document.getElementById('mTitle');
  const mBody = document.getElementById('mBody');
  const mClose = document.getElementById('mClose');

  // --- 工具函数 ---
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function hexToRgba(hex, alpha) {
    if (!hex) return 'transparent';
    let c = hex.replace('#', '');
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    const r = parseInt(c.slice(0, 2), 16);
    const g = parseInt(c.slice(2, 4), 16);
    const b = parseInt(c.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function applyThemeAdaptation(hexTheme) {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
      return {
        bg: hexToRgba(hexTheme.border, 0.12),
        border: hexTheme.border,
        textFilter: 'brightness(1.4) saturate(1.15)'
      };
    }
    return {
      bg: hexTheme.bg,
      border: hexTheme.border,
      textFilter: 'brightness(0.65)'
    };
  }

  function getCourseColor(courseName) {
    let theme = { bg: '#f6f6f6', border: '#c8c8c8' };
    if (courseName) {
      let hash = 0;
      for (let i = 0; i < courseName.length; i++) {
        hash = courseName.charCodeAt(i) + ((hash << 5) - hash);
      }
      theme = COLOR_PALETTE[Math.abs(hash) % COLOR_PALETTE.length];
    }
    return applyThemeAdaptation(theme);
  }

  function parseWeeks(weeksText) {
    if (!weeksText) return [];
    const text = String(weeksText).trim();
    const isOddOnly = text.includes('单');
    const isEvenOnly = text.includes('双');
    const clean = text.replace(/\(.*\)/g, '').replace(/周/g, '').trim();
    if (!clean) return [];

    const parts = clean.split(/[,，]/);
    const weeks = [];
    parts.forEach(part => {
      const p = part.trim();
      if (!p) return;
      if (p.includes('-')) {
        const nums = p.split('-').map(s => parseInt(s, 10)).filter(n => !Number.isNaN(n));
        if (nums.length === 2) {
          const [start, end] = nums;
          for (let w = start; w <= end; w++) {
            if (isOddOnly && w % 2 === 0) continue;
            if (isEvenOnly && w % 2 !== 0) continue;
            weeks.push(w);
          }
        }
      } else {
        const w = parseInt(p, 10);
        if (!Number.isNaN(w)) weeks.push(w);
      }
    });
    return Array.from(new Set(weeks)).sort((a, b) => a - b);
  }

  function computeCurrentWeek() {
    const now = new Date();
    if (Number.isNaN(termStartDate.getTime())) return 1;
    if (now < termStartDate) return 1;
    const diffDays = Math.floor((now - termStartDate) / (24 * 60 * 60 * 1000));
    const w = Math.floor(diffDays / 7) + 1;
    return Math.min(Math.max(1, w), maxWeek);
  }

  function courseKey(list) {
    if (!list || !list.length) return 'EMPTY';
    return list.map(c => [c.name, c.teacher, c.room || c.location].join('|')).join('||');
  }

  function coursesInBlock(day, block, w) {
    return allCourses.filter(c => {
      const matchDay = (c.day === day || c.weekday === day);
      if (!matchDay) return false;
      const wList = c.week_list || parseWeeks(c.weeks);
      if (!wList.includes(w)) return false;
      const cStart = c.start ?? c.start_section ?? 1;
      const cEnd = c.end ?? c.end_section ?? cStart;
      return cStart <= block.end && cEnd >= block.start;
    });
  }

  // --- 课表渲染主入口 ---
  function render(week) {
    if (!grid) return;
    grid.innerHTML = '';

    const weekStart = new Date(termStartDate.getTime() + (week - 1) * 7 * 24 * 60 * 60 * 1000);
    const today = new Date();
    const todayStr = today.toDateString();

    // 1. 左上角空白单元格
    const corner = document.createElement('div');
    corner.className = 'cell header';
    corner.style.gridRow = '1';
    corner.style.gridColumn = '1';
    grid.appendChild(corner);

    // 2. 渲染顶部 7 天表头
    WEEKDAYS.forEach((name, idx) => {
      const dayDate = new Date(weekStart.getTime() + idx * 24 * 60 * 60 * 1000);
      const isToday = (todayStr === dayDate.toDateString());
      const dateStr = (dayDate.getMonth() + 1) + '/' + String(dayDate.getDate()).padStart(2, '0');

      const h = document.createElement('div');
      h.className = 'cell header' + (isToday ? ' today' : '');
      h.innerHTML = `
        <span class="day-name">${name}</span>
        <span class="day-date">${dateStr}</span>
      `;
      h.style.gridRow = '1';
      h.style.gridColumn = String(idx + 2);
      grid.appendChild(h);
    });

    // 3. 渲染左侧 7 个节次块
    BLOCKS.forEach((b, i) => {
      const pCell = document.createElement('div');
      pCell.className = 'cell period';
      pCell.textContent = b.label;
      pCell.style.gridRow = String(i + 2);
      pCell.style.gridColumn = '1';
      grid.appendChild(pCell);
    });

    // 4. 渲染主体网格 (7天 x 7节次块，连续节次相同自动跨行合并)
    for (let day = 0; day < 7; day++) {
      for (let bi = 0; bi < BLOCKS.length; bi++) {
        const baseList = coursesInBlock(day + 1, BLOCKS[bi], week);
        const baseKey = courseKey(baseList);
        let endIdx = bi;

        if (baseKey !== 'EMPTY') {
          while (endIdx + 1 < BLOCKS.length) {
            const nextList = coursesInBlock(day + 1, BLOCKS[endIdx + 1], week);
            if (courseKey(nextList) !== baseKey) break;
            endIdx += 1;
          }
        }

        const dCell = document.createElement('div');
        dCell.className = 'cell';
        dCell.style.gridColumn = String(day + 2);
        dCell.style.gridRow = String(bi + 2) + ' / span ' + String(endIdx - bi + 1);

        if (baseList.length > 0) {
          const firstCourse = baseList[0];
          const theme = getCourseColor(firstCourse.name);
          const animDelay = ((day * 0.03) + (bi * 0.03)).toFixed(2);
          const showAnim = isFirstRender || isManualSwitch;
          const animStyle = showAnim
            ? `animation: popIn 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; animation-delay: ${animDelay}s; opacity: 0;`
            : '';

          const isStacked = baseList.length > 1;
          const card = document.createElement('div');
          card.className = 'course' + (isStacked ? ' stacked' : '');
          card.style.backgroundColor = theme.bg;
          card.style.borderLeftColor = theme.border;
          if (animStyle) card.style.cssText += animStyle;

          let innerHtml = '';
          if (isStacked) {
            innerHtml += `<div class="conflict-badge">${baseList.length}</div>`;
          }

          const loc = firstCourse.room || firstCourse.location;
          innerHtml += `
            <div class="course-name" style="color: ${theme.border}; filter: ${theme.textFilter};">${escapeHtml(firstCourse.name)}</div>
            ${loc && loc !== '待定' ? `<div class="course-location" style="color: ${theme.border}; filter: ${theme.textFilter};">@${escapeHtml(loc)}</div>` : ''}
            <div class="course-meta">${escapeHtml(firstCourse.teacher)} · @${escapeHtml(loc)}</div>
          `;

          card.innerHTML = innerHtml;
          card.addEventListener('click', () => openCourseModal(baseList));
          dCell.appendChild(card);
        }

        grid.appendChild(dCell);
        bi = endIdx;
      }
    }

    isFirstRender = false;
    isManualSwitch = false;
  }

  // --- 切换周次 ---
  function setWeek(w) {
    const target = Math.max(1, Math.min(maxWeek, w));
    if (weekSelect) weekSelect.value = target;
    if (semLabel && rawSchedule) {
      const semText = rawSchedule.semester || '2026-2027-1';
      semLabel.textContent = `${semText} (第${target}周)`;
    }
    grid.classList.add('is-switching');
    requestAnimationFrame(() => {
      render(target);
      requestAnimationFrame(() => {
        grid.classList.remove('is-switching');
      });
    });
  }

  // --- 弹窗逻辑 ---
  function computeCourseProgress(courseName) {
    if (!courseName) return { percent: 0, current: 0, total: 0 };
    const sessions = [];
    allCourses.forEach(c => {
      if (c.name === courseName) {
        const wList = c.week_list || parseWeeks(c.weeks);
        wList.forEach(w => {
          sessions.push({ week: w, day: c.day || c.weekday, start: c.start });
        });
      }
    });

    if (!sessions.length) return { percent: 0, current: 0, total: 0 };

    const selectedW = parseInt(weekSelect ? weekSelect.value : currentWeek, 10);
    const nowW = Number.isNaN(selectedW) ? currentWeek : selectedW;

    const completed = sessions.filter(s => s.week < nowW).length;
    const percent = Math.min(100, Math.max(0, Math.round((completed / sessions.length) * 100)));
    return { percent, current: completed, total: sessions.length };
  }

  function openCourseModal(courses) {
    if (!courses || !courses.length) return;

    mTitle.textContent = courses.length > 1 ? `重叠课程 (${courses.length})` : courses[0].name;
    mBody.innerHTML = '';

    courses.forEach((c) => {
      const prog = computeCourseProgress(c.name);
      const item = document.createElement('div');
      item.className = 'modal-course-item fade-in-content';

      const loc = c.room || c.location || '待定';
      const secStart = c.start ?? c.start_section ?? 1;
      const secEnd = c.end ?? c.end_section ?? secStart;

      item.innerHTML = `
        ${courses.length > 1 ? `<h3 style="margin: 0 0 10px; font-size: 16px; color: var(--accent);">${escapeHtml(c.name)}</h3>` : ''}
        <p><strong>教 师</strong><span>${escapeHtml(c.teacher || '待定')}</span></p>
        <p><strong>教 室</strong><span>${escapeHtml(loc)}</span></p>
        <p><strong>节 次</strong><span>第${secStart}-${secEnd}节</span></p>
        <p><strong>周 次</strong><span>${escapeHtml(c.weeks || '未知')}</span></p>
        <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border-color);">
          <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); margin-bottom: 6px;">
            <span>学期进度</span>
            <span>已上 ${prog.current} / 共 ${prog.total} 节 (${prog.percent}%)</span>
          </div>
          <div style="height: 6px; background: var(--border-color); border-radius: 999px; overflow: hidden;">
            <div style="height: 100%; width: ${prog.percent}%; background: var(--accent); border-radius: 999px; transition: width 0.4s ease;"></div>
          </div>
        </div>
      `;

      mBody.appendChild(item);
    });

    modalOverlay.classList.add('active');
  }

  function closeModal() {
    modalOverlay.classList.remove('active');
  }

  if (mClose) mClose.addEventListener('click', closeModal);
  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeModal();
    });
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalOverlay.classList.contains('active')) {
      closeModal();
    }
  });

  // --- 主题切换 ---
  function updateTheme(theme) {
    const isDark = theme === 'dark';
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    localStorage.setItem('themePref', isDark ? 'dark' : 'light');

    const meta = document.getElementById('themeColorMeta');
    if (meta) meta.setAttribute('content', isDark ? '#121212' : '#f4f8f4');

    if (themeBtn) {
      themeBtn.textContent = isDark ? '☀️' : '🌙';
      themeBtn.title = isDark ? '切换浅色模式' : '切换深色模式';
    }

    render(parseInt(weekSelect.value, 10) || currentWeek);
  }

  if (themeBtn) {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    themeBtn.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
    themeBtn.addEventListener('click', () => {
      const active = document.documentElement.getAttribute('data-theme') === 'dark';
      updateTheme(active ? 'light' : 'dark');
    });
  }

  // --- 移动端触控跟手与弹性左右滑动切换 ---
  let startX = 0;
  let startY = 0;
  let isTracking = false;
  let isHorizontalSwipe = false;
  let isVerticalScroll = false;
  let currentTranslateX = 0;
  let touchStartTime = 0;

  function resetGridPosition() {
    grid.style.transition = 'transform 300ms cubic-bezier(0.25, 0.46, 0.45, 0.94)';
    grid.style.transform = 'translateX(0px)';
  }

  function doHorizontalSwitch(targetWeek, direction) {
    if (weekSwitching) return;
    weekSwitching = true;

    const screenW = window.innerWidth;
    const exitX = direction === 'left' ? -screenW * 0.28 : screenW * 0.28;

    grid.style.transition = 'transform 180ms ease-out, opacity 180ms ease-out';
    grid.style.transform = `translateX(${exitX}px)`;
    grid.style.opacity = '0';

    setTimeout(() => {
      setWeek(targetWeek);
      const enterX = direction === 'left' ? screenW * 0.28 : -screenW * 0.28;
      grid.style.transition = 'none';
      grid.style.transform = `translateX(${enterX}px)`;

      void grid.offsetWidth;

      grid.style.transition = 'transform 260ms cubic-bezier(0.25, 0.46, 0.45, 0.94), opacity 260ms ease-out';
      grid.style.transform = 'translateX(0px)';
      grid.style.opacity = '1';

      setTimeout(() => {
        weekSwitching = false;
        grid.style.transition = '';
      }, 260);
    }, 180);
  }

  if (grid) {
    grid.addEventListener('touchstart', (e) => {
      if (e.touches.length !== 1 || weekSwitching) return;
      const touch = e.touches[0];
      startX = touch.clientX;
      startY = touch.clientY;
      touchStartTime = e.timeStamp;
      isTracking = true;
      isHorizontalSwipe = false;
      isVerticalScroll = false;
      currentTranslateX = 0;
      grid.style.transition = 'none';
    }, { passive: true });

    grid.addEventListener('touchmove', (e) => {
      if (!isTracking || e.touches.length !== 1) return;
      const touch = e.touches[0];
      const dx = touch.clientX - startX;
      const dy = touch.clientY - startY;

      if (!isHorizontalSwipe && !isVerticalScroll) {
        if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
          if (Math.abs(dx) > Math.abs(dy) * 1.25) {
            isHorizontalSwipe = true;
          } else {
            isVerticalScroll = true;
          }
        }
      }

      if (isHorizontalSwipe) {
        if (e.cancelable) e.preventDefault();
        const curW = parseInt(weekSelect.value, 10);
        let dampening = 1;

        if ((curW === 1 && dx > 0) || (curW === maxWeek && dx < 0)) {
          dampening = 0.25;
        }

        currentTranslateX = dx * dampening;
        grid.style.transform = `translateX(${currentTranslateX}px)`;
      }
    }, { passive: false });

    grid.addEventListener('touchend', (e) => {
      if (!isTracking) return;
      isTracking = false;

      if (!isHorizontalSwipe || isVerticalScroll) {
        resetGridPosition();
        return;
      }

      const dx = currentTranslateX;
      const curW = parseInt(weekSelect.value, 10);
      const threshold = window.innerWidth * 0.18;
      const fastSwipe = Math.abs(dx) > 35 && (e.timeStamp - touchStartTime < 260);

      if (Math.abs(dx) > threshold || fastSwipe) {
        if (dx < 0 && curW < maxWeek) {
          doHorizontalSwitch(curW + 1, 'left');
        } else if (dx > 0 && curW > 1) {
          doHorizontalSwitch(curW - 1, 'right');
        } else {
          resetGridPosition();
        }
      } else {
        resetGridPosition();
      }
    }, { passive: true });

    grid.addEventListener('touchcancel', () => {
      if (isTracking) resetGridPosition();
      isTracking = false;
      isHorizontalSwipe = false;
      isVerticalScroll = false;
    }, { passive: true });
  }

  // --- 控件绑定 ---
  if (weekSelect) {
    weekSelect.addEventListener('change', () => {
      isManualSwitch = true;
      setWeek(parseInt(weekSelect.value, 10));
    });
  }

  if (prevWeekBtn) {
    prevWeekBtn.addEventListener('click', () => {
      isManualSwitch = true;
      setWeek(parseInt(weekSelect.value, 10) - 1);
    });
  }

  if (nextWeekBtn) {
    nextWeekBtn.addEventListener('click', () => {
      isManualSwitch = true;
      setWeek(parseInt(weekSelect.value, 10) + 1);
    });
  }

  if (todayBtn) {
    todayBtn.addEventListener('click', () => {
      isManualSwitch = true;
      setWeek(currentWeek);
    });
  }

  window.addEventListener('resize', () => {
    render(parseInt(weekSelect.value, 10) || currentWeek);
  });

  // --- 数据拉取与初始化 ---
  async function fetchScheduleData() {
    const params = new URLSearchParams(window.location.search);
    const user = params.get('user') || params.get('student_id');
    const t = Date.now();

    const urls = [];
    if (user && user.trim()) {
      // URL 参数指定了学号，直接查询
      const u = user.trim();
      if (/^\d{8,}$/.test(u)) {
        urls.push(`/api/schedule/query?student_id=${encodeURIComponent(u)}&_t=${t}`);
      }
      urls.push(`/api/schedule/view/${encodeURIComponent(u)}?_t=${t}`);
    } else {
      // 1. 尝试当前登录用户
      urls.push(`/api/schedule/current?_t=${t}`);
      // 2. 尝试本地保存的学号（用户之前同步过）
      const savedSid = localStorage.getItem('bjfu-student-id');
      if (savedSid && savedSid.trim()) {
        urls.push(`/api/schedule/query?student_id=${encodeURIComponent(savedSid.trim())}&_t=${t}`);
      }
      // ❌ 不再 fallback 到任何演示/共享账号
      // 如果用户从未同步过自己的课表，返回 null → 显示同步表单
    }

    let payload = null;
    for (const url of urls) {
      try {
        const res = await fetch(url, { credentials: 'include' });
        if (res.ok) {
          payload = await res.json();
          if (payload && (payload.courses || payload.data)) {
            break;
          }
        }
      } catch (err) {
        console.warn(`Fetch error for ${url}:`, err);
      }
    }

    return payload;
  }

  // --- 同步课表（调用后端教务抓取） ---
  async function syncSchedule(studentId, password) {
    const syncStatus = document.getElementById('syncStatus');
    const syncBtn = document.getElementById('syncBtn');
    if (syncStatus) { syncStatus.textContent = '正在同步课表，请稍候…'; syncStatus.className = 'sync-status loading'; }
    if (syncBtn) syncBtn.disabled = true;

    try {
      const res = await fetch('/api/schedule/get', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ student_id: studentId, password: password, force: true })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '同步失败' }));
        throw new Error(err.detail || err.message || '同步失败');
      }

      const data = await res.json();
      // 持久化学号到本地
      localStorage.setItem('bjfu-student-id', studentId);
      localStorage.setItem('bjfu-sync-time', new Date().toISOString());

      if (syncStatus) { syncStatus.textContent = '同步成功！正在刷新课表…'; syncStatus.className = 'sync-status success'; }

      // 隐藏同步表单，显示课表
      const syncPanel = document.getElementById('syncPanel');
      if (syncPanel) syncPanel.style.display = 'none';
      document.querySelector('header').style.display = '';
      grid.style.display = '';

      initSchedule(data);
    } catch (e) {
      if (syncStatus) { syncStatus.textContent = '❌ ' + e.message; syncStatus.className = 'sync-status error'; }
    } finally {
      if (syncBtn) syncBtn.disabled = false;
    }
  }

  // --- 显示同步登录表单 ---
  function showSyncForm() {
    // 隐藏课表网格和顶部控件
    document.querySelector('header').style.display = 'none';
    grid.style.display = 'none';

    // 创建同步面板
    let syncPanel = document.getElementById('syncPanel');
    if (!syncPanel) {
      syncPanel = document.createElement('div');
      syncPanel.id = 'syncPanel';
      syncPanel.innerHTML = `
        <div class="sync-card">
          <div class="sync-icon">🌲</div>
          <h2>BJFU 课表</h2>
          <p class="sync-desc">输入你的教务系统学号和密码，同步你的个人课表</p>
          <form id="syncForm" autocomplete="off">
            <input type="text" id="syncStudentId" placeholder="学号（如 260101208）"
                   pattern="\\d{8,}" required autocomplete="username" inputmode="numeric">
            <input type="password" id="syncPassword" placeholder="教务系统密码"
                   required autocomplete="current-password">
            <button type="submit" id="syncBtn">同步课表</button>
          </form>
          <div id="syncStatus" class="sync-status"></div>
          <p class="sync-hint">密码仅用于一次性登录教务系统抓取课表，不会被存储</p>
        </div>
      `;
      document.querySelector('.wrap').appendChild(syncPanel);

      document.getElementById('syncForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const sid = document.getElementById('syncStudentId').value.trim();
        const pwd = document.getElementById('syncPassword').value;
        if (sid && pwd) syncSchedule(sid, pwd);
      });
    }
    syncPanel.style.display = 'flex';
  }

  function initSchedule(data) {
    if (!data || !(data.courses || data.data) ||
        ((data.courses || data.data || []).length === 0)) {
      // 无课表数据 → 展示同步表单
      showSyncForm();
      return;
    }

    rawSchedule = data;
    allCourses = data.courses || data.data || [];

    // 计算最大周次
    let detectedMax = 20;
    allCourses.forEach(c => {
      const wList = parseWeeks(c.weeks);
      wList.forEach(w => { if (w > detectedMax) detectedMax = w; });
    });
    maxWeek = detectedMax;

    // 填充下拉选项
    if (weekSelect) {
      weekSelect.innerHTML = '';
      for (let w = 1; w <= maxWeek; w++) {
        const opt = document.createElement('option');
        opt.value = w;
        opt.textContent = `第${w}周`;
        weekSelect.appendChild(opt);
      }
    }

    // 计算当前周（支持 URL 传入 ?week=2 覆盖）
    const params = new URLSearchParams(window.location.search);
    const specifiedWeek = parseInt(params.get('week'), 10);
    const calculatedCurrent = computeCurrentWeek();
    currentWeek = (!Number.isNaN(specifiedWeek) && specifiedWeek >= 1 && specifiedWeek <= maxWeek)
      ? specifiedWeek
      : calculatedCurrent;

    if (weekSelect) weekSelect.value = currentWeek;

    // 状态标签
    if (semLabel) {
      const semText = data.semester || '2026-2027-1';
      semLabel.textContent = `${semText} (第${currentWeek}周)`;
    }

    // 渲染
    render(currentWeek);
  }

  // 启动初始化
  (async function start() {
    try {
      const data = await fetchScheduleData();
      initSchedule(data);
    } catch (e) {
      console.error('初始化课表失败:', e);
      if (semLabel) semLabel.textContent = '加载课表失败，请刷新重试';
    }
  })();
})();
