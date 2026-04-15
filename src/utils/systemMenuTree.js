/**
 * 多系统下菜单路径可能重名，树统计与筛选以 system_id 为唯一归属。
 */

/** @returns {number|null} */
export function parseRowSystemId(row) {
  if (!row || typeof row !== 'object') return null;
  const v = row.system_id;
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

/**
 * 是否属于当前选中的系统（仅用 system_id，与系统管理中的主键一致）。
 * @param {number|null} activeSid
 */
export function rowBelongsToSystemId(row, activeSid) {
  if (activeSid == null) return true;
  const n = parseRowSystemId(row);
  return n !== null && n === activeSid;
}

/**
 * 树分组键：有 system_id 时一律用 id:N，避免与其它系统同名菜单混在一起。
 */
export function historySystemKey(h) {
  if (!h || typeof h !== 'object') return 'name:默认系统';
  const id = h.system_id;
  if (id != null && String(id).trim() !== '') {
    const n = Number(id);
    if (!Number.isNaN(n)) return `id:${n}`;
  }
  const nm = String(h.system_name || '').trim() || '默认系统';
  return `name:${nm}`;
}

/**
 * 系统根节点展示名：id:N 优先用系统注册表 name；否则退回记录里的 system_name。
 * @param {object[]} records
 * @param {Array<{id:number,name?:string}>|null|undefined} systemsRegistry 来自 /api/systems/list
 */
export function buildSystemLabelMap(records, systemsRegistry = null) {
  const base = Array.isArray(records) ? records : [];
  const skList = [...new Set(base.map((r) => historySystemKey(r)))];

  const registryNameById = new Map();
  if (Array.isArray(systemsRegistry)) {
    for (const s of systemsRegistry) {
      const id = Number(s?.id);
      const nm = String(s?.name || '').trim();
      if (!Number.isNaN(id) && nm) registryNameById.set(id, nm);
    }
  }

  const skToNames = new Map();
  for (const r of base) {
    const sk = historySystemKey(r);
    const nm = String(r.system_name || '').trim() || '默认系统';
    if (!skToNames.has(sk)) skToNames.set(sk, new Set());
    skToNames.get(sk).add(nm);
  }

  const preferred = new Map();
  for (const sk of skList) {
    if (sk.startsWith('id:')) {
      const id = Number(sk.slice(3));
      if (!Number.isNaN(id) && registryNameById.has(id)) {
        preferred.set(sk, registryNameById.get(id));
        continue;
      }
    }
    const set = skToNames.get(sk);
    const primary = set && set.size ? [...set].sort()[0] : '默认系统';
    preferred.set(sk, primary);
  }

  const nameToSks = new Map();
  for (const sk of skList) {
    const p = preferred.get(sk);
    if (!nameToSks.has(p)) nameToSks.set(p, []);
    nameToSks.get(p).push(sk);
  }
  const labels = new Map();
  for (const [name, sks] of nameToSks) {
    if (sks.length === 1) {
      labels.set(sks[0], name);
    } else {
      for (const sk of sks) {
        const idPart = sk.startsWith('id:') ? sk.slice(3) : sk.replace(/^name:/, '');
        labels.set(sk, `${name} (#${idPart})`);
      }
    }
  }
  return labels;
}
