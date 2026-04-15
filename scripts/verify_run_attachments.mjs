const base = 'http://127.0.0.1:5000';

async function j(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${JSON.stringify(data)}`);
  }
  return data;
}

async function main() {
  const login = await j(
    await fetch(`${base}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'root', password: 'root' }),
    }),
  );
  const token = login.token;
  const authHeaders = { Authorization: `Bearer ${token}` };
  const jsonHeaders = { ...authHeaders, 'Content-Type': 'application/json' };

  const cases = await j(
    await fetch(`${base}/api/cases/list`, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({}),
    }),
  );
  const c = cases[0];
  if (!c) throw new Error('no cases returned');

  // tiny 1x1 png as multipart
  const pngBase64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/eyJ7p8AAAAASUVORK5CYII=';
  const buf = Buffer.from(pngBase64, 'base64');
  const fd = new FormData();
  fd.append('file', new Blob([buf], { type: 'image/png' }), 'run.png');

  const up = await j(
    await fetch(`${base}/api/upload/asset`, {
      method: 'POST',
      headers: authHeaders,
      body: fd,
    }),
  );

  const payload = {
    id: Number(c.id),
    status: 'fail',
    run_notes: '自动联调：文字+截图',
    run_attachments: [
      {
        file_url: up.file_url,
        original_name: up.original_name,
        uploaded_at: up.uploaded_at,
      },
    ],
    last_run_at: new Date().toLocaleString(),
    executor_name: '联调',
    executor_id: 1,
  };

  await j(
    await fetch(`${base}/api/cases/update`, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  );

  const detail = await j(
    await fetch(`${base}/api/cases/detail`, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ id: Number(c.id) }),
    }),
  );

  console.log(
    JSON.stringify(
      {
        caseId: c.id,
        run_notes: detail.run_notes,
        run_attachments: detail.run_attachments,
      },
      null,
      2,
    ),
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

