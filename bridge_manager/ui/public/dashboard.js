const qs = (sel) => document.querySelector(sel);
const qsa = (sel) => Array.from(document.querySelectorAll(sel));

// Theme management
document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;
  const savedTheme = localStorage.getItem('theme') || 'light';
  if (savedTheme === 'dark') root.classList.add('theme-dark');
  
  const themeBtn = qs('#toggle-theme');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const isDark = root.classList.toggle('theme-dark');
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
      // Update chart colors
      updateChartTheme();
    });
  }
});

// Chart instances
let trafficChart, errorChart, statusChart, sourceChart, methodChart, pathsChart;

// Theme-aware colors
function getColors() {
  const isDark = document.documentElement.classList.contains('theme-dark');
  return {
    text: isDark ? '#e5e7eb' : '#111',
    grid: isDark ? '#1f2937' : '#e5e7e7',
    primary: '#3b82f6',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    purple: '#8b5cf6',
    cyan: '#06b6d4',
    pink: '#ec4899',
  };
}

function updateChartTheme() {
  const colors = getColors();
  [trafficChart, errorChart, statusChart, sourceChart, methodChart, pathsChart].forEach(chart => {
    if (chart) {
      chart.options.scales?.x && (chart.options.scales.x.ticks.color = colors.text);
      chart.options.scales?.x && (chart.options.scales.x.grid.color = colors.grid);
      chart.options.scales?.y && (chart.options.scales.y.ticks.color = colors.text);
      chart.options.scales?.y && (chart.options.scales.y.grid.color = colors.grid);
      chart.options.plugins.legend.labels.color = colors.text;
      chart.update();
    }
  });
}

// Fetch helpers
async function fetchStats(endpoint, params = {}) {
  const url = new URL(`/api/stats/${endpoint}`, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  });
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${endpoint}`);
  return res.json();
}

// Chart 1: Traffic over time
let trafficInterval = 'hour';
let trafficRange = '24h';
let globalTimeRange = '24h';

function getGlobalTimeRange() {
  const select = qs('#global-time-filter');
  return select ? select.value : '24h';
}

async function renderTrafficChart() {
  globalTimeRange = getGlobalTimeRange();
  const data = await fetchStats('traffic', { interval: trafficInterval, range: globalTimeRange });
  const colors = getColors();
  
  const ctx = qs('#trafficChart');
  if (trafficChart) trafficChart.destroy();
  
  trafficChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => new Date(d.time_bucket).toLocaleString()),
      datasets: [{
        label: 'Requests',
        data: data.map(d => d.count),
        backgroundColor: colors.primary + '99',
        borderColor: colors.primary,
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: colors.text } }
      },
      scales: {
        x: { ticks: { color: colors.text }, grid: { color: colors.grid } },
        y: { 
          beginAtZero: true,
          ticks: { color: colors.text },
          grid: { color: colors.grid }
        }
      }
    }
  });
}

// Chart 2: Status breakdown
async function renderStatusChart() {
  globalTimeRange = getGlobalTimeRange();
  const data = await fetchStats('status', { timeRange: globalTimeRange });
  const colors = getColors();
  
  const colorMap = {
    '200': colors.success,
    '4xx': colors.warning,
    '5xx': colors.error,
    'Other': colors.text + '66'
  };
  
  const ctx = qs('#statusChart');
  if (statusChart) statusChart.destroy();
  
  statusChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.status_group),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: data.map(d => colorMap[d.status_group] || colors.text),
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: colors.text } }
      }
    }
  });
}

// Chart 3: Source split
async function renderSourceChart() {
  globalTimeRange = getGlobalTimeRange();
  const data = await fetchStats('source', { timeRange: globalTimeRange });
  const colors = getColors();
  
  const ctx = qs('#sourceChart');
  if (sourceChart) sourceChart.destroy();
  
  sourceChart = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: data.map(d => d.source),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: [colors.purple, colors.cyan, colors.pink, colors.warning],
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: colors.text } }
      }
    }
  });
}

// Chart 4: Method distribution
async function renderMethodChart() {
  globalTimeRange = getGlobalTimeRange();
  const data = await fetchStats('method', { timeRange: globalTimeRange });
  const colors = getColors();
  
  const methodColors = {
    'GET': colors.primary,
    'POST': colors.success,
    'PUT': colors.warning,
    'DELETE': colors.error,
    'PATCH': colors.purple,
  };
  
  const ctx = qs('#methodChart');
  if (methodChart) methodChart.destroy();
  
  methodChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.method),
      datasets: [{
        label: 'Requests',
        data: data.map(d => d.count),
        backgroundColor: data.map(d => methodColors[d.method] || colors.text),
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { ticks: { color: colors.text }, grid: { color: colors.grid } },
        y: { 
          beginAtZero: true,
          ticks: { color: colors.text },
          grid: { color: colors.grid }
        }
      }
    }
  });
}

// Chart 5: Top paths
async function renderPathsChart() {
  globalTimeRange = getGlobalTimeRange();
  const data = await fetchStats('paths', { timeRange: globalTimeRange });
  const colors = getColors();
  
  const ctx = qs('#pathsChart');
  if (pathsChart) pathsChart.destroy();
  
  pathsChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.path),
      datasets: [{
        label: 'Requests',
        data: data.map(d => d.count),
        backgroundColor: colors.cyan + '99',
        borderColor: colors.cyan,
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { 
          beginAtZero: true,
          ticks: { color: colors.text },
          grid: { color: colors.grid }
        },
        y: { 
          ticks: { 
            color: colors.text,
            font: { size: 10 }
          },
          grid: { color: colors.grid }
        }
      }
    }
  });
}

// Chart 6: Error rate timeline
let errorInterval = 'hour';
let errorRange = '24h';

async function renderErrorChart() {
  globalTimeRange = getGlobalTimeRange();
  const data = await fetchStats('errors', { interval: errorInterval, range: globalTimeRange });
  const colors = getColors();
  
  const ctx = qs('#errorChart');
  if (errorChart) errorChart.destroy();
  
  errorChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => new Date(d.time_bucket).toLocaleString()),
      datasets: [{
        label: 'Error Rate (%)',
        data: data.map(d => d.error_rate || 0),
        backgroundColor: colors.error + '33',
        borderColor: colors.error,
        borderWidth: 2,
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: colors.text } }
      },
      scales: {
        x: { ticks: { color: colors.text }, grid: { color: colors.grid } },
        y: { 
          beginAtZero: true,
          max: 100,
          ticks: { 
            color: colors.text,
            callback: (val) => val + '%'
          },
          grid: { color: colors.grid }
        }
      }
    }
  });
}

// Initialize all charts
async function initCharts() {
  try {
    await Promise.all([
      renderTrafficChart(),
      renderStatusChart(),
      renderSourceChart(),
      renderMethodChart(),
      renderPathsChart(),
      renderErrorChart(),
    ]);
  } catch (e) {
    console.error('Failed to load charts:', e);
  }
}

// Control handlers for traffic chart
document.addEventListener('DOMContentLoaded', () => {
  // Global time filter
  const globalFilter = qs('#global-time-filter');
  if (globalFilter) {
    globalFilter.addEventListener('change', () => {
      initCharts();
    });
  }

  qsa('.interval-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      qsa('.interval-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      trafficInterval = btn.dataset.interval;
      renderTrafficChart();
    });
  });

  // Error chart controls
  qsa('.error-interval-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      qsa('.error-interval-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      errorInterval = btn.dataset.interval;
      renderErrorChart();
    });
  });

  // Auto-refresh
  let autoRefreshInterval = null;
  let autoRefreshEnabled = false;

  function refreshData() {
    initCharts().catch(e => console.error('Refresh failed:', e));
  }

  function startAutoRefresh() {
    if (autoRefreshInterval) return;
    autoRefreshInterval = setInterval(refreshData, 30000);
    autoRefreshEnabled = true;
    const btn = qs('#toggle-refresh');
    if (btn) btn.textContent = 'Auto-Refresh: ON';
  }

  function stopAutoRefresh() {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
    }
    autoRefreshEnabled = false;
    const btn = qs('#toggle-refresh');
    if (btn) btn.textContent = 'Auto-Refresh: OFF';
  }

  const refreshBtn = qs('#toggle-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (autoRefreshEnabled) {
        stopAutoRefresh();
      } else {
        startAutoRefresh();
      }
    });
  }

  // Pause when hidden
  let wasAutoRefreshEnabled = false;
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && autoRefreshEnabled) {
      wasAutoRefreshEnabled = true;
      stopAutoRefresh();
    } else if (!document.hidden && wasAutoRefreshEnabled) {
      wasAutoRefreshEnabled = false;
      startAutoRefresh();
    }
  });

  // Load charts
  initCharts();
});
