/* ============================================================
   BJFU 课表 — 前端逻辑（设计参考 VaporTang 版）
   - 拉取 /api/course + /api/meta
   - 网格渲染：7 个节次块 × 7 天，连续节次自动合并
   - 课程色板按课程名哈希取色，深浅色主题自适应
   - 周切换（select / 上周 / 下周 / 今天）
   - 进行中 / 下一节 高亮（每 30s 刷新）
   - 点击卡片弹详情（支持一格多门课）
   ============================================================ */
(function () {
  "use strict";

  var WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

  // 节次块：与强智课表一致，服务端按此分块渲染
  var BLOCKS = [
    { label: "1-2", start: 1, end: 2 },
    { label: "3-4", start: 3, end: 4 },
    { label: "5", start: 5, end: 5 },
    { label: "6-7", start: 6, end: 7 },
    { label: "8-9", start: 8, end: 9 },
    { label: "10-11", start: 10, end: 11 },
    { label: "12", start: 12, end: 12 },
  ];

  // 课程色板（浅色底 + 深色描边），按课程名哈希稳定取色
  var PALETTE = [
    { bg: "#EBF3F5", border: "#789CA4" }, { bg: "#F2F4E6", border: "#94A660" },
    { bg: "#F7ECEC", border: "#BA7C81" }, { bg: "#F5F0E6", border: "#B59B6D" },
    { bg: "#EAEFF4", border: "#7991A8" }, { bg: "#EFEDF5", border: "#8A82A3" },
    { bg: "#F6EFEA", border: "#BD8F75" }, { bg: "#E9F5ED", border: "#72A584" },
    { bg: "#F7EBED", border: "#B87A89" }, { bg: "#EFF4E6", border: "#8C9E63" },
    { bg: "#F4ECEF", border: "#A67C92" }, { bg: "#EBF4F5", border: "#6EA0A6" },
    { bg: "#F4F1E6", border: "#A89F82" }, { bg: "#F6EDE8", border: "#B58778" },
    { bg: "#EAEAE8", border: "#8A8C86" }, { bg: "#E8F1EE", border: "#6B968B" },
  ];

  var REFRESH_MS = 30 * 1000;

  var state = {
    courses: [],
    meta: null,
    week: 1,
    todayWeek: 1,
    curDay: 1,       // 今天星期 1-7
    curSection: 0,   // 当前节次（0 = 未上课）
    firstRender: true,
    manualSwitch: false,
  };

  var grid = document.getElementById("grid");
  var weekSelect = document.getElementById("weekSelect");
  var modal = document.getElementById("courseModal");

  /* ---------------- 工具 ---------------- */

  // "2026-09-07" -> Date（本地时区）
  function parseDate(s) {
    var p = s.split("-");
    return new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10));
  }

  function dayOfWeek(d) { return (d.getDay() + 6) % 7 + 1; }

  function weekOf(date, firstMonday) {
    var diff = Math.floor((date - firstMonday) / 86400000);
    return Math.max(1, Math.floor(diff / 7) + 1);
  }

  function mondayOf(week, firstMonday) {
    var d = new Date(firstMonday.getTime());
    d.setDate(d.getDate() + (week - 1) * 7);
    return d;
  }

  function formatMonthDay(d) { return (d.getMonth() + 1) + "/" + d.getDate(); }

  // 该课程在指定周是否上课（支持单双周与精确周次）
  function hasClassInWeek(c, w) {
    if (c.week_type === "odd" && w % 2 === 0) return false;
    if (c.week_type === "even" && w % 2 === 1) return false;
    if (w < c.start_week || w > c.end_week) return false;
    if (c.weeks && c.weeks.indexOf(w) === -1) return false;
    return true;
  }

  // 周次文字："1-16周" / "1,3,5周" / "1-16周·单周"
  function weeksLabel(c) {
    var w = c.weeks || [];
    var text;
    if (w.length >= 3 && w[w.length - 1] - w[0] + 1 === w.length) {
      text = w[0] + "-" + w[w.length - 1] + "周";
    } else if (w.length > 0) {
      text = w.join(",") + "周";
    } else {
      text = (c.start_week || 1) + "-" + (c.end_week || 1) + "周";
    }
    if (c.week_type === "odd") text += "·单周";
    if (c.week_type === "even") text += "·双周";
    return text;
  }

  function sectionLabel(c) {
    return c.start_section === c.end_section
      ? "第" + c.start_section + "节"
      : "第" + c.start_section + "-" + c.end_section + "节";
  }

  // 当前节次：把当前时间映射到节（根据 meta.sections）
  function currentSection(now, sections) {
    var m = now.getHours() * 60 + now.getMinutes();
    var idx = -1;
    for (var i = 0; i < sections.length; i++) {
      var sp = sections[i][0].split(":");
      var start = parseInt(sp[0], 10) * 60 + parseInt(sp[1], 10);
      if (m >= start) idx = i; else break;
    }
    return idx + 1;
  }

  /* ---------------- 主题 ---------------- */

  var THEMES = ["light", "dark", "auto"];
  var THEME_ICON = { light: "☀️", dark: "🌙", auto: "🔄" };

  function applyTheme(pref) {
    var isDark = pref === "dark" ||
      (pref === "auto" && window.matchMedia &&
       window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    var meta = document.getElementById("themeColorMeta");
    if (meta) meta.setAttribute("content", isDark ? "#121212" : "#f4f8f4");
  }

  function cycleTheme() {
    var pref = localStorage.getItem("themePref") || "auto";
    var next = THEMES[(THEMES.indexOf(pref) + 1) % THEMES.length];
    localStorage.setItem("themePref", next);
    applyTheme(next);
    document.getElementById("themeBtn").textContent = THEME_ICON[next];
    // 卡片颜色按主题渲染，切换后需重绘
    if (state.meta) setWeek(state.week);
  }

  /* ---------------- 颜色 ---------------- */

  function hexToRgba(hex, alpha) {
    if (!hex) return "transparent";
    if (hex.length === 4) {
      hex = "#" + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3];
    }
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
  }

  // 深色模式下用描边色做半透明底，保证卡片可读
  function applyThemeAdaptation(theme) {
    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    if (isDark) {
      return {
        bg: hexToRgba(theme.border, 0.03),
        border: theme.border,
        textFilter: "brightness(1.35) saturate(1.2)",
      };
    }
    return { bg: theme.bg, border: theme.border, textFilter: "brightness(0.6)" };
  }

  function getCourseColor(name) {
    var theme = { bg: "#f6f6f6", border: "#c8c8c8" };
    if (name) {
      var h = 0;
      for (var i = 0; i < name.length; i++) {
        h = name.charCodeAt(i) + ((h << 5) - h);
      }
      theme = PALETTE[Math.abs(h) % PALETTE.length];
    }
    return applyThemeAdaptation(theme);
  }

  // 一个单元格内课程集合的指纹（用于连续节次合并判断）
  function courseKey(list) {
    if (!list || !list.length) return "EMPTY";
    return list.map(function (c) {
      return [c.name, c.teacher, c.location].join("|");
    }).join("||");
  }

  /* ---------------- 渲染 ---------------- */

  // 某天某节次块内、指定周有课的课程
  function coursesInBlock(day, block, w) {
    return state.courses.filter(function (c) {
      return c.weekday === day &&
        hasClassInWeek(c, w) &&
        c.start_section <= block.end &&
        c.end_section >= block.start;
    });
  }

  function render(w) {
    grid.innerHTML = "";
    var weekStart = mondayOf(w, parseDate(state.meta.first_monday));
    var isMobile = window.innerWidth < 768;
    var now = new Date();
    var isThisWeek = w === state.todayWeek;
    var showAnim = state.firstRender || state.manualSwitch;
    state.firstRender = false;
    state.manualSwitch = false;

    // 左上角
    var corner = document.createElement("div");
    corner.className = "cell header";
    corner.style.gridRow = "1";
    corner.style.gridColumn = "1";
    grid.appendChild(corner);

    // 表头：星期 + 日期（今天高亮）
    WEEKDAYS.forEach(function (n, idx) {
      var dayDate = new Date(weekStart.getTime() + idx * 86400000);
      var isToday = now.toDateString() === dayDate.toDateString();
      var h = document.createElement("div");
      h.className = "cell header";
      h.style.gridRow = "1";
      h.style.gridColumn = String(idx + 2);
      if (isToday) h.style.color = "var(--accent)";
      if (isMobile) {
        h.innerHTML = n + '<br><span style="font-size:10px;font-weight:normal;opacity:0.8">' +
          formatMonthDay(dayDate) + "</span>";
      } else {
        h.innerHTML = n + ' <span style="font-size:12px;font-weight:normal;opacity:0.8">' +
          formatMonthDay(dayDate) + "</span>";
      }
      grid.appendChild(h);
    });

    // 侧边节次块
    BLOCKS.forEach(function (b, i) {
      var p = document.createElement("div");
      p.className = "cell period";
      p.textContent = b.label;
      p.style.gridRow = String(i + 2);
      p.style.gridColumn = "1";
      grid.appendChild(p);
    });

    // 主体：7 列 × 节次块
    for (var day = 0; day < 7; day++) {
      for (var bi = 0; bi < BLOCKS.length; bi++) {
        var baseList = coursesInBlock(day + 1, BLOCKS[bi], w);
        var baseKey = courseKey(baseList);
        var endIdx = bi;

        // 连续节次块课程集合完全相同 -> 合并为一个单元格
        if (baseKey !== "EMPTY") {
          while (endIdx + 1 < BLOCKS.length) {
            var nextList = coursesInBlock(day + 1, BLOCKS[endIdx + 1], w);
            if (courseKey(nextList) !== baseKey) break;
            endIdx += 1;
          }
        }

        var dCell = document.createElement("div");
        dCell.className = "cell";
        dCell.style.gridColumn = String(day + 2);
        dCell.style.gridRow = String(bi + 2) + " / span " + String(endIdx - bi + 1);

        if (baseList.length) {
          var htmlContent = "";
          var animDelay = (day * 0.05 + bi * 0.05).toFixed(2);
          var animStyle = showAnim
            ? "animation: popIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; animation-delay: " +
              animDelay + "s; opacity: 0;"
            : "";

          if (baseList.length === 1) {
            var c1 = baseList[0];
            var theme1 = getCourseColor(c1.name);
            var badge1 = badgeFor(c1, isThisWeek, now);
            htmlContent +=
              '<div class="course" data-idx="' + state.courses.indexOf(c1) + '"' +
              ' style="background-color: ' + theme1.bg + '; border-left-color: ' + theme1.border +
              "; " + animStyle + '">' +
              badge1 +
              '<div class="course-name" style="color: ' + theme1.border + "; filter: " +
              theme1.textFilter + ';">' + esc(c1.name) + "</div>" +
              (c1.location ? '<div class="course-location" style="color: ' + theme1.border +
                "; filter: " + theme1.textFilter + ';">' + esc(c1.location) + "</div>" : "") +
              '<div class="course-meta">' + esc(c1.teacher || "未知") + " · " +
              esc(c1.location || "未知") + "</div>" +
              "</div>";
          } else {
            // 冲突堆叠：显示第一门课 + 数量角标
            var cFirst = baseList[0];
            var theme2 = getCourseColor(cFirst.name);
            htmlContent +=
              '<div class="course stacked" data-idx="' + state.courses.indexOf(cFirst) + '"' +
              ' style="background-color: ' + theme2.bg + '; border-left-color: ' + theme2.border +
              "; " + animStyle + '">' +
              '<div class="conflict-badge">' + baseList.length + "</div>" +
              '<div class="course-name" style="color: ' + theme2.border + "; filter: " +
              theme2.textFilter + ';">' + esc(cFirst.name) + "</div>" +
              (cFirst.location ? '<div class="course-location" style="color: ' + theme2.border +
                "; filter: " + theme2.textFilter + ';">' + esc(cFirst.location) + "</div>" : "") +
              '<div class="course-meta">' + esc(cFirst.teacher || "未知") + " · " +
              esc(cFirst.location || "未知") + "</div>" +
              "</div>";
          }
          dCell.innerHTML = htmlContent;
        }

        grid.appendChild(dCell);
        bi = endIdx; // 跳过已合并的块
      }
    }

    renderWeekInfo(w, weekStart);
  }

  // 进行中 / 下一节角标（仅本周当天）
  function badgeFor(c, isThisWeek, now) {
    if (!isThisWeek || c.weekday !== state.curDay || state.curSection <= 0) return "";
    if (state.curSection >= c.start_section && state.curSection <= c.end_section) {
      return '<span class="course-badge live">进行中</span>';
    }
    return "";
  }

  // 下一节标识：本周今天所有未开始的课程中，开始节次最小者
  function markNextClass() {
    if (state.week !== state.todayWeek || state.curSection <= 0) return;
    var candidates = state.courses.filter(function (c) {
      return c.weekday === state.curDay &&
        hasClassInWeek(c, state.week) &&
        c.start_section > state.curSection;
    });
    if (!candidates.length) return;
    candidates.sort(function (a, b) { return a.start_section - b.start_section; });
    var target = candidates[0];
    var card = grid.querySelector('.course[data-idx="' + state.courses.indexOf(target) + '"]');
    if (card) {
      var b = document.createElement("span");
      b.className = "course-badge next";
      b.textContent = "下一节";
      card.appendChild(b);
    }
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderWeekInfo(w, weekStart) {
    var sun = new Date(weekStart.getTime() + 6 * 86400000);
    document.getElementById("semLabel").textContent =
      state.meta.semester + " · 第" + w + "周 (" + formatMonthDay(weekStart) +
      " - " + formatMonthDay(sun) + ")";
  }

  /* ---------------- 弹窗 ---------------- */

  function openModal(c) {
    var theme = getCourseColor(c.name);
    var weeksText = weeksLabel(c);
    var timeText = WEEKDAYS[c.weekday - 1] + " " + sectionLabel(c);

    document.getElementById("mTitle").textContent = c.name;
    document.getElementById("mTitle").style.color = theme.border;
    var body = document.getElementById("mBody");
    body.className = "modal-body fade-in-content";
    body.innerHTML =
      '<p><strong>教师</strong>' + esc(c.teacher || "—") + "</p>" +
      '<p><strong>地点</strong>' + esc(c.location || "—") + "</p>" +
      "<p><strong>时间</strong>" + esc(timeText) + "</p>" +
      "<p><strong>周次</strong>" + esc(weeksText) + "</p>";
    modal.classList.add("active");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modal.classList.remove("active");
    document.body.style.overflow = "";
  }

  /* ---------------- 周切换 ---------------- */

  function setWeek(w) {
    var max = state.meta ? state.meta.total_weeks : 20;
    state.week = Math.min(Math.max(1, w), max);
    weekSelect.value = String(state.week);
    grid.classList.add("is-switching");
    requestAnimationFrame(function () {
      render(state.week);
      markNextClass();
      requestAnimationFrame(function () { grid.classList.remove("is-switching"); });
    });
  }

  /* ---------------- 初始化 ---------------- */

  function init() {
    var m = state.meta;
    var first = parseDate(m.first_monday);
    var now = new Date();
    state.todayWeek = Math.min(Math.max(1, weekOf(now, first)), m.total_weeks || 20);
    state.curDay = dayOfWeek(now);
    state.curSection = currentSection(now, m.sections);
    state.week = state.todayWeek;

    // 周选择下拉
    for (var w = 1; w <= (m.total_weeks || 20); w++) {
      var opt = document.createElement("option");
      opt.value = String(w);
      opt.textContent = "第" + w + "周";
      weekSelect.appendChild(opt);
    }
    weekSelect.value = String(state.week);

    var pref = localStorage.getItem("themePref") || "auto";
    document.getElementById("themeBtn").textContent = THEME_ICON[pref];

    setWeek(state.week);
  }

  function loadData() {
    return Promise.all([
      fetch("/api/course").then(function (r) {
        if (!r.ok) throw new Error("接口异常 " + r.status);
        return r.json();
      }),
      fetch("/api/meta").then(function (r) { return r.json(); }),
    ]).then(function (res) {
      state.courses = res[0] || [];
      state.meta = res[1];
      init();
    }).catch(function (err) {
      document.getElementById("semLabel").textContent = "加载失败：" + err.message;
    });
  }

  /* ---------------- 事件绑定 ---------------- */

  weekSelect.addEventListener("change", function () {
    state.manualSwitch = true;
    setWeek(parseInt(weekSelect.value, 10));
  });
  document.getElementById("prevWeek").addEventListener("click", function () {
    state.manualSwitch = true;
    setWeek(state.week - 1);
  });
  document.getElementById("nextWeek").addEventListener("click", function () {
    state.manualSwitch = true;
    setWeek(state.week + 1);
  });
  document.getElementById("todayBtn").addEventListener("click", function () {
    state.manualSwitch = true;
    setWeek(state.todayWeek);
  });
  document.getElementById("themeBtn").addEventListener("click", cycleTheme);

  // 卡片点击（事件委托）
  grid.addEventListener("click", function (e) {
    var card = e.target.closest ? e.target.closest(".course") : null;
    if (!card || !grid.contains(card)) return;
    var idx = parseInt(card.getAttribute("data-idx"), 10);
    var c = state.courses[idx];
    if (c) openModal(c);
  });

  document.getElementById("mClose").addEventListener("click", closeModal);
  modal.addEventListener("click", function (e) {
    if (e.target === modal) closeModal();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeModal();
  });

  // 每 30s 刷新"当前节次 / 进行中"状态
  setInterval(function () {
    if (!state.meta) return;
    var now = new Date();
    state.curSection = currentSection(now, state.meta.sections);
    state.curDay = dayOfWeek(now);
    render(state.week);
    markNextClass();
  }, REFRESH_MS);

  loadData();
})();
