/**
 * BJFU 课表 — 登录页逻辑
 * 处理表单提交、凭据存取、主题切换
 */
(function () {
  'use strict';

  const STORAGE_KEY_SID = 'bjfu-student-id';
  const STORAGE_KEY_PWD = 'bjfu-saved-password';
  const STORAGE_KEY_SAVE = 'bjfu-save-credentials';

  // DOM
  const form = document.getElementById('loginForm');
  const sidInput = document.getElementById('studentId');
  const pwdInput = document.getElementById('password');
  const saveCheck = document.getElementById('saveCredentials');
  const submitBtn = document.getElementById('submitBtn');
  const btnText = document.getElementById('btnText');
  const btnSpinner = document.getElementById('btnSpinner');
  const statusMsg = document.getElementById('statusMsg');
  const togglePwd = document.getElementById('togglePwd');
  const eyeIcon = document.getElementById('eyeIcon');
  const themeBtn = document.getElementById('themeBtn');

  // --- 恢复保存的凭据 ---
  function restoreCredentials() {
    const savedSave = localStorage.getItem(STORAGE_KEY_SAVE);
    if (savedSave === 'true') {
      saveCheck.checked = true;
      const sid = localStorage.getItem(STORAGE_KEY_SID);
      const pwd = localStorage.getItem(STORAGE_KEY_PWD);
      if (sid) sidInput.value = sid;
      if (pwd) pwdInput.value = pwd;
    } else {
      // 即使不勾选记住，也恢复学号（学号总是保存的）
      const sid = localStorage.getItem(STORAGE_KEY_SID);
      if (sid) sidInput.value = sid;
    }
  }

  // --- 保存或清除凭据 ---
  function persistCredentials(studentId) {
    localStorage.setItem(STORAGE_KEY_SID, studentId);
    if (saveCheck.checked) {
      localStorage.setItem(STORAGE_KEY_SAVE, 'true');
      localStorage.setItem(STORAGE_KEY_PWD, pwdInput.value);
    } else {
      localStorage.removeItem(STORAGE_KEY_SAVE);
      localStorage.removeItem(STORAGE_KEY_PWD);
    }
  }

  // --- 显示状态消息 ---
  function showStatus(text, type) {
    statusMsg.textContent = text;
    statusMsg.className = 'status-msg ' + (type || '');
  }

  // --- 设置按钮 loading 状态 ---
  function setLoading(loading) {
    submitBtn.disabled = loading;
    if (loading) {
      btnText.textContent = '正在同步…';
      btnSpinner.classList.remove('hidden');
      submitBtn.classList.add('loading');
    } else {
      btnText.textContent = '同步课表';
      btnSpinner.classList.add('hidden');
      submitBtn.classList.remove('loading');
    }
  }

  // --- 提交表单 ---
  async function handleSubmit(e) {
    e.preventDefault();

    const studentId = sidInput.value.trim();
    const password = pwdInput.value;

    if (!studentId) {
      showStatus('请输入学号', 'error');
      sidInput.focus();
      return;
    }
    if (!password) {
      showStatus('请输入密码', 'error');
      pwdInput.focus();
      return;
    }

    setLoading(true);
    showStatus('正在登录教务系统并同步课表，请稍候…', 'loading');

    try {
      const res = await fetch('/api/schedule/get', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          student_id: studentId,
          password: password,
          force: true
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '同步失败' }));
        throw new Error(err.detail || err.message || '同步失败');
      }

      const data = await res.json();

      // 确认有课表数据
      if (!data.courses || data.courses.length === 0) {
        throw new Error('当前学期暂无课表数据');
      }

      // 保存凭据（按用户选择）
      persistCredentials(studentId);
      localStorage.setItem('bjfu-sync-time', new Date().toISOString());

      showStatus('✅ 同步成功！正在跳转到课表…', 'success');

      // 延迟跳转，让用户看到成功提示
      setTimeout(() => {
        window.location.href = './';
      }, 600);

    } catch (err) {
      showStatus('❌ ' + err.message, 'error');
      setLoading(false);
    }
  }

  // --- 密码显示/隐藏切换 ---
  function togglePasswordVisibility() {
    const isPassword = pwdInput.type === 'password';
    pwdInput.type = isPassword ? 'text' : 'password';
    // 切换图标：睁眼 ↔ 闭眼
    if (isPassword) {
      eyeIcon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
    } else {
      eyeIcon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
    }
  }

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
  }

  // --- 初始化 ---
  restoreCredentials();

  // 主题按钮
  if (themeBtn) {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    themeBtn.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
    themeBtn.addEventListener('click', () => {
      const active = document.documentElement.getAttribute('data-theme') === 'dark';
      updateTheme(active ? 'light' : 'dark');
    });
  }

  // 密码可见性切换
  if (togglePwd) {
    togglePwd.addEventListener('click', togglePasswordVisibility);
  }

  // 表单提交
  if (form) {
    form.addEventListener('submit', handleSubmit);
  }

  // 如果用户已经有 session cookie 且有课表，直接跳转到课表页
  (async function checkExistingSession() {
    try {
      const res = await fetch('/api/schedule/current?_t=' + Date.now(), {
        credentials: 'include'
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.courses && data.courses.length > 0) {
          window.location.replace('./');
          return;
        }
      }
    } catch {
      // ignore
    }
  })();
})();
