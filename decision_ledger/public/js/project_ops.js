frappe.pages['project-ops'].on_page_load = async function(wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Project Ops Dashboard',
    single_column: true
  });

  // Root container
  const root = $('<div id="qcs-project-ops" class="p-4"></div>').appendTo(page.body);

  // Lightweight styles for a sleeker look
  const style = document.createElement('style');
  style.textContent = `
    .qcs-card { border: 1px solid var(--border-color, #e5e7eb); border-radius: 12px; background: var(--card-bg, #fff); transition: box-shadow .2s ease, transform .1s ease; }
    .qcs-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,.07); transform: translateY(-2px); }
    .qcs-card-header { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
    .qcs-title { font-size: 1.05rem; font-weight: 700; margin: 0; color: var(--heading-color, #111827); }
    .qcs-subtle { color: var(--text-muted, #6b7280); }
    .qcs-pill { padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; display:inline-flex; align-items:center; gap:6px; }
    .qcs-pill.open { background:#ECFDF5; color:#065F46; }        /* green */
    .qcs-pill.onhold { background:#FFF7ED; color:#9A3412; }     /* amber */
    .qcs-pill.completed { background:#EFF6FF; color:#1D4ED8; }  /* blue */
    .qcs-pill.cancelled { background:#FEF2F2; color:#B91C1C; }  /* red */
    .qcs-kpis { display:grid; grid-template-columns: repeat(12, 1fr); gap: 8px; }
    .qcs-kpi { grid-column: span 4; background: var(--bg-color, #F9FAFB); border-radius: 10px; padding:10px 12px; }
    .qcs-kpi .label { font-size:12px; color: var(--text-muted, #6b7280); margin-bottom:2px; }
    .qcs-kpi .value { font-weight:700; }
    .qcs-progress { height:8px; border-radius: 999px; background: var(--control-bg, #eef2f7); overflow:hidden; }
    .qcs-progress > div { height:100%; border-radius:999px; transition: width .3s ease; }
    .qcs-progress.ok { background:#ECFDF5; } .qcs-progress.ok > div { background:#10B981; }
    .qcs-progress.warn { background:#FFFBEB; } .qcs-progress.warn > div { background:#F59E0B; }
    .qcs-progress.danger { background:#FEF2F2; } .qcs-progress.danger > div { background:#EF4444; }
    .qcs-avatars { display:flex; flex-wrap:wrap; gap:6px; }
    .qcs-avatar { width:28px; height:28px; border-radius:50%; background: var(--control-bg-on-dark, #EEF2FF); color: var(--text-color, #3730A3); display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; border:1px solid var(--border-color, #e5e7eb); }
    .qcs-more { font-size:12px; color: var(--text-muted, #6b7280); padding-left:2px; }
    @media (max-width: 992px) { .qcs-kpi { grid-column: span 6; } }
    @media (max-width: 640px) { .qcs-kpi { grid-column: span 12; } }
  `;
  document.head.appendChild(style);

  // Load Vue 3 ESM from CDN (works on Frappe Cloud; if CSP blocks, see note below)
  const mod = await import('https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js');
  const { createApp, ref, computed, onMounted } = mod;

  createApp({
    setup() {
      const loading = ref(false);
      const rows = ref([]);
      const q = ref('');
      const status = ref('');
      const sortBy = ref('recent'); // 'recent' | 'budget' | 'open_tasks'

      const displayRows = computed(() => {
        const s = (q.value || '').toLowerCase();
        const filtered = rows.value.filter(r => {
          const hit = !s || (r.name.toLowerCase().includes(s) || (r.project_name||'').toLowerCase().includes(s));
          const st = !status.value || r.status === status.value;
          return hit && st;
        });
        // sorting
        return [...filtered].sort((a,b) => {
          if (sortBy.value === 'budget') {
            const pa = pct(a.cost.spent, a.cost.budget), pb = pct(b.cost.spent, b.cost.budget);
            return pb - pa; // highest usage first
          }
          if (sortBy.value === 'open_tasks') {
            return (b.tasks.open||0) - (a.tasks.open||0);
          }
          // recent (by modified proxy: assume order already recent) – keep existing order
          return 0;
        });
      });

      async function fetchData() {
        loading.value = true;
        try {
          const resp = await frappe.call({
            method: 'decision_ledger.api.get_projects_overview',
            args: { search: q.value, status: status.value, limit: 100 }
          });
          rows.value = (resp.message && resp.message.data) || [];
        } finally {
          loading.value = false;
        }
      }

      function fmtHours(h) { return (h || 0).toFixed(1); }
      function pct(a, b) {
        const A = Number(a||0), B = Number(b||0);
        if (!B) return 0;
        return Math.min(100, Math.round((A/B)*100));
      }

      function statusPill(s) {
        if (!s) return 'qcs-pill';
        const k = s.toLowerCase().replace(/\s+/g,'');
        return `qcs-pill ${k}`;
      }
      function initials(u) {
        if (!u) return '?';
        const name = (u.split('@')[0] || u).replace(/[^a-zA-Z0-9]/g,' ');
        const parts = name.trim().split(' ').filter(Boolean);
        const a = (parts[0]||'')[0] || '';
        const b = (parts[1]||'')[0] || (parts[0]||'')[1] || '';
        return (a + (b||'')).toUpperCase();
      }
      function budgetClass(p) {
        const v = pct(p.cost.spent, p.cost.budget);
        if (v >= 90) return 'qcs-progress danger';
        if (v >= 70) return 'qcs-progress warn';
        return 'qcs-progress ok';
      }
      function topAssignees(arr, n=5) {
        return (arr || []).slice(0, n);
      }
      function openProject(name) {
        window.location.href = `/app/project/${name}`;
      }

      onMounted(fetchData);

      return { loading, rows, displayRows, q, status, sortBy, fetchData, fmtHours, pct, statusPill, initials, budgetClass, topAssignees, openProject };
    },
    template: `
      <div class="mb-4 d-flex gap-2 align-items-end flex-wrap">
        <div>
          <label class="form-label">Search</label>
          <input v-model="q" @keyup.enter="fetchData" class="form-control" placeholder="Project name or code" />
        </div>
        <div>
          <label class="form-label">Status</label>
          <select v-model="status" @change="fetchData" class="form-select">
            <option value="">All</option>
            <option>Open</option>
            <option>Completed</option>
            <option>Cancelled</option>
            <option>On Hold</option>
          </select>
        </div>
        <div>
          <label class="form-label">Sort by</label>
          <select v-model="sortBy" class="form-select">
            <option value="recent">Recent</option>
            <option value="budget">Budget Usage</option>
            <option value="open_tasks">Open Tasks</option>
          </select>
        </div>
        <div class="ms-auto">
          <button class="btn btn-primary" @click="fetchData">
            <span v-if="!loading">Refresh</span>
            <span v-else>Loading…</span>
          </button>
        </div>
      </div>

      <div class="grid" style="display:grid; grid-template-columns: repeat(12, 1fr); gap: 12px;">
        <div v-for="p in displayRows" :key="p.name" class="qcs-card p-3" style="grid-column: span 6; cursor:pointer;" @click="openProject(p.name)">
          <div class="qcs-card-header">
            <div>
              <p class="qcs-title mb-1">{{ p.project_name || p.name }}</p>
              <div class="qcs-subtle small">{{ p.name }} · {{ p.company }}</div>
              <div class="qcs-subtle small" v-if="p.manager">PM: {{ p.manager }}</div>
            </div>
            <div class="text-end">
              <span :class="statusPill(p.status)">{{ p.status }}</span>
            </div>
          </div>

          <hr class="my-2"/>

          <div class="qcs-kpis">
            <div class="qcs-kpi">
              <div class="label">Tasks</div>
              <div class="value">{{ p.tasks.open }} / {{ p.tasks.total }} open</div>
              <div class="qcs-subtle small">Closed: {{ p.tasks.closed }}</div>
              <div class="qcs-progress mt-2 ok">
                <div :style="{ width: pct(p.tasks.closed, p.tasks.total)+'%' }"></div>
              </div>
              <div class="qcs-subtle small mt-1">Progress: {{ pct(p.tasks.closed, p.tasks.total) }}%</div>
            </div>

            <div class="qcs-kpi">
              <div class="label">Hours Spent</div>
              <div class="value">{{ fmtHours(p.hours) }}</div>
            </div>

            <div class="qcs-kpi">
              <div class="label">Cost</div>
              <div class="value">AED {{ (p.cost.spent||0).toLocaleString() }}</div>
              <div class="qcs-subtle small" v-if="p.cost.budget">Budget: AED {{ (p.cost.budget||0).toLocaleString() }}</div>
              <div class="qcs-progress mt-2" :class="budgetClass(p)" v-if="p.cost.budget">
                <div :style="{ width: pct(p.cost.spent, p.cost.budget)+'%' }"></div>
              </div>
              <div class="qcs-subtle small mt-1" v-if="p.cost.budget">Usage: {{ pct(p.cost.spent, p.cost.budget) }}%</div>
            </div>
          </div>

          <div class="mt-3">
            <div class="qcs-subtle small mb-1">Assignees</div>
            <div class="qcs-avatars">
              <div v-for="u in topAssignees(p.assignees, 6)" :key="u" class="qcs-avatar" :title="u">{{ initials(u) }}</div>
              <div v-if="(p.assignees?.length||0) > 6" class="qcs-more">+{{ p.assignees.length - 6 }} more</div>
              <span v-if="!p.assignees || !p.assignees.length" class="text-muted">—</span>
            </div>
          </div>
        </div>
      </div>
    `
  }).mount('#qcs-project-ops');
};