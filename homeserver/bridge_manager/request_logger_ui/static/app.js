/* ============================================================
   Bridge Manager — Request Logger UI  (app.js)
   Vanilla JS only — no dependencies.
   ============================================================ */

(function () {
  "use strict";

  // ── Theme ────────────────────────────────────────────────────

  const THEME_KEY = "bm_inspector_theme";

  function getStoredTheme() {
    try { return localStorage.getItem(THEME_KEY) || "light"; }
    catch { return "light"; }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "dark" ? "☀ Light" : "☾ Dark";
    try { localStorage.setItem(THEME_KEY, theme); } catch {}
    // Also set a cookie so the server can render the correct initial theme
    document.cookie = `bm_inspector_theme=${theme};path=/;max-age=31536000`;
  }

  // Apply immediately on load (before paint) to avoid flash
  applyTheme(getStoredTheme());

  document.addEventListener("DOMContentLoaded", function () {
    // Re-apply in case server rendered a different default
    applyTheme(getStoredTheme());

    const themeBtn = document.getElementById("theme-toggle");
    if (themeBtn) {
      themeBtn.addEventListener("click", function () {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        applyTheme(current === "dark" ? "light" : "dark");
      });
    }

    // ── Pullover ───────────────────────────────────────────────

    const pullover     = document.getElementById("pullover");
    const preRawIn     = document.getElementById("pre-raw-in");
    const preRawOut    = document.getElementById("pre-raw-out");
    const preResponse  = document.getElementById("pre-response");
    const pulloverClose = document.getElementById("pullover-close");
    let activeRow = null;

    function escapeHTML(str) {
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function syntaxHighlight(raw) {
      if (!raw || raw === "null" || raw === "") return "(empty)";
      let json;
      try {
        const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
        json = JSON.stringify(parsed, null, 2);
      } catch {
        return escapeHTML(raw);
      }
      return escapeHTML(json).replace(
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
        function (match) {
          let cls = "json-number";
          if (/^"/.test(match)) {
            cls = /:$/.test(match) ? "json-key" : "json-string";
          } else if (/true|false/.test(match)) {
            cls = "json-boolean";
          } else if (/null/.test(match)) {
            cls = "json-null";
          }
          return `<span class="${cls}">${match}</span>`;
        }
      );
    }

    function decodeAttr(el, name) {
      // Attributes come HTML-escaped; the browser already unescapes when we
      // read .dataset or getAttribute, so we just return the value directly.
      return el.getAttribute(name) || "";
    }

    function openPullover(tr) {
      if (activeRow) activeRow.classList.remove("active-row");
      activeRow = tr;
      tr.classList.add("active-row");

      preRawIn.innerHTML    = syntaxHighlight(decodeAttr(tr, "data-raw-in"));
      preRawOut.innerHTML   = syntaxHighlight(decodeAttr(tr, "data-raw-out"));
      preResponse.innerHTML = syntaxHighlight(decodeAttr(tr, "data-response"));

      pullover.classList.add("open");
    }

    function closePullover() {
      pullover.classList.remove("open");
      if (activeRow) {
        activeRow.classList.remove("active-row");
        activeRow = null;
      }
    }

    // Row click
    document.querySelectorAll("tbody tr[data-raw-in]").forEach(function (tr) {
      tr.addEventListener("click", function (e) {
        if (activeRow === tr && pullover.classList.contains("open")) {
          closePullover();
        } else {
          openPullover(tr);
        }
      });
    });

    // Close button
    if (pulloverClose) pulloverClose.addEventListener("click", closePullover);

    // ESC to close
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePullover();
    });

    // ── Vertical resize (drag top edge to change height) ──────
    const resizeHandle = document.getElementById("pullover-resize");
    let isResizingV = false;
    let resizeStartY, resizeStartH;

    if (resizeHandle) {
      resizeHandle.addEventListener("mousedown", function (e) {
        isResizingV = true;
        resizeStartY = e.clientY;
        resizeStartH = pullover.getBoundingClientRect().height;
        pullover.classList.add("resizing");
        e.preventDefault();
      });
    }

    document.addEventListener("mousemove", function (e) {
      if (!isResizingV) return;
      const delta = resizeStartY - e.clientY;
      const newH = Math.max(120, Math.min(window.innerHeight - 60, resizeStartH + delta));
      pullover.style.height = newH + "px";
    });

    document.addEventListener("mouseup", function () {
      if (isResizingV) {
        isResizingV = false;
        pullover.classList.remove("resizing");
      }
    });

    // ── Horizontal resize (drag dividers between panels) ──────
    let isResizingH = false;
    let hPanelLeft, hPanelRight;
    let hStartX, hStartLeftW, hStartRightW, hTotalW;

    document.querySelectorAll(".panel-divider").forEach(function (divider) {
      divider.addEventListener("mousedown", function (e) {
        const panelsEl = document.getElementById("pullover-panels");
        const panels   = Array.from(panelsEl.querySelectorAll(".pullover-panel"));
        const dividers = Array.from(panelsEl.querySelectorAll(".panel-divider"));
        const idx = dividers.indexOf(divider);
        hPanelLeft  = panels[idx];
        hPanelRight = panels[idx + 1];
        hStartX       = e.clientX;
        hStartLeftW   = hPanelLeft.getBoundingClientRect().width;
        hStartRightW  = hPanelRight.getBoundingClientRect().width;
        hTotalW       = panelsEl.getBoundingClientRect().width;
        isResizingH   = true;
        divider.classList.add("active");
        e.preventDefault();
      });
    });

    document.addEventListener("mousemove", function (e) {
      if (!isResizingH) return;
      const delta    = e.clientX - hStartX;
      const newLeftW  = Math.max(60, hStartLeftW + delta);
      const newRightW = Math.max(60, hStartRightW - delta);
      hPanelLeft.style.flex  = "0 0 " + (newLeftW / hTotalW * 100).toFixed(2) + "%";
      hPanelRight.style.flex = "0 0 " + (newRightW / hTotalW * 100).toFixed(2) + "%";
    });

    document.addEventListener("mouseup", function () {
      if (isResizingH) {
        isResizingH = false;
        document.querySelectorAll(".panel-divider").forEach(function (d) {
          d.classList.remove("active");
        });
      }
    });

    // ── Column manager ─────────────────────────────────────────

    const colPanel      = document.getElementById("col-panel");
    const colPanelBtn   = document.getElementById("col-panel-btn");
    const colList       = document.getElementById("col-list");
    const saveLayoutBtn = document.getElementById("save-layout-btn");
    const cancelColBtn  = document.getElementById("cancel-col-btn");

    if (colPanelBtn) {
      colPanelBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        colPanel.classList.toggle("open");
      });
    }

    if (cancelColBtn) {
      cancelColBtn.addEventListener("click", function () {
        colPanel.classList.remove("open");
      });
    }

    document.addEventListener("click", function (e) {
      if (colPanel && !colPanel.contains(e.target) && e.target !== colPanelBtn) {
        colPanel.classList.remove("open");
      }
    });

    // ── Drag-to-reorder ─────────────────────────────────────────

    let dragSrc = null;

    function onDragStart(e) {
      dragSrc = this;
      this.style.opacity = "0.5";
      e.dataTransfer.effectAllowed = "move";
    }

    function onDragEnd() {
      this.style.opacity = "";
      document.querySelectorAll(".col-item").forEach(function (li) {
        li.classList.remove("drag-over");
      });
    }

    function onDragOver(e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      document.querySelectorAll(".col-item").forEach(function (li) {
        li.classList.remove("drag-over");
      });
      this.classList.add("drag-over");
      return false;
    }

    function onDrop(e) {
      e.stopPropagation();
      if (dragSrc !== this) {
        // Insert dragSrc before this
        colList.insertBefore(dragSrc, this);
      }
      return false;
    }

    function addDragHandlers(li) {
      li.setAttribute("draggable", "true");
      li.addEventListener("dragstart", onDragStart);
      li.addEventListener("dragend",   onDragEnd);
      li.addEventListener("dragover",  onDragOver);
      li.addEventListener("drop",      onDrop);
    }

    if (colList) {
      colList.querySelectorAll(".col-item").forEach(addDragHandlers);
    }

    // ── Save layout ────────────────────────────────────────────

    if (saveLayoutBtn) {
      saveLayoutBtn.addEventListener("click", function () {
        const items = colList.querySelectorAll(".col-item");
        const columns = Array.from(items).map(function (li) {
          const cb    = li.querySelector('input[type="checkbox"]');
          const label = li.querySelector("label").childNodes;
          // Last text node of the label is the column display name
          let labelText = "";
          label.forEach(function (node) {
            if (node.nodeType === Node.TEXT_NODE) {
              const t = node.textContent.trim();
              if (t) labelText = t;
            }
          });
          return {
            key:     li.getAttribute("data-key"),
            label:   labelText,
            visible: cb ? cb.checked : true,
          };
        });

        fetch("/layout", {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ columns }),
        })
          .then(function (res) {
            if (res.ok) {
              colPanel.classList.remove("open");
              window.location.reload();
            } else {
              alert("Failed to save layout.");
            }
          })
          .catch(function () {
            alert("Failed to save layout — server unreachable.");
          });
      });
    }

    // ── Filter reset ────────────────────────────────────────────

    const resetBtn = document.getElementById("filter-reset");
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        window.location.href = "/";
      });
    }

    // ── Method / status badge rendering ────────────────────────
    // The server renders plain text in <td> cells; we enhance in place.

    const METHOD_COLS  = new Set(); // we'll detect by column header
    const STATUS_COLS  = new Set();

    const headers = document.querySelectorAll("thead th");
    headers.forEach(function (th, idx) {
      const key = th.getAttribute("data-key");
      if (key === "method")      METHOD_COLS.add(idx);
      if (key === "status_code") STATUS_COLS.add(idx);
    });

    document.querySelectorAll("tbody tr").forEach(function (tr) {
      const cells = tr.querySelectorAll("td");
      METHOD_COLS.forEach(function (idx) {
        const td = cells[idx];
        if (!td) return;
        const m = td.textContent.trim().toUpperCase();
        if (m) {
          td.innerHTML = `<span class="method-badge method-${m}">${m}</span>`;
        }
      });
      STATUS_COLS.forEach(function (idx) {
        const td = cells[idx];
        if (!td) return;
        const code = parseInt(td.textContent.trim(), 10);
        if (!isNaN(code)) {
          const cls = code < 300 ? "status-2xx"
                    : code < 400 ? "status-3xx"
                    : code < 500 ? "status-4xx"
                    : "status-5xx";
          td.innerHTML = `<span class="status-badge ${cls}">${code}</span>`;
        }
      });
    });

  }); // DOMContentLoaded

})();
