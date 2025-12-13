import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import dotenv from 'dotenv';
import pg from 'pg';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load root .env for DB configs used by bridge_manager
// Expected keys: DRIVERNAME, HOST, PORT, USERNAME, PASSWORD, DATABASE
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const { Pool } = pg;

// Only support Postgres for now
if (!process.env.DRIVERNAME || !process.env.DRIVERNAME.includes('postgres')) {
  console.warn('Warning: DRIVERNAME not set to postgres; defaulting to postgres');
}

const pool = new Pool({
  host: process.env.HOST,
  port: Number(process.env.PORT || 5432),
  user: process.env.USERNAME,
  password: process.env.PASSWORD,
  database: process.env.DATABASE,
});

const app = express();
const PORT = process.env.BRIDGE_REQUESTS_UI_PORT || 3050;

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// Simple health check
app.get('/health', (req, res) => res.json({ ok: true }));

// List requests with optional filters
// /api/requests?source=&method=&homeserver_id=&bridge_id=&limit=&since=
app.get('/api/requests', async (req, res) => {
  try {
    const { source, method, homeserver_id, bridge_id, limit = '100', since } = req.query;

    const clauses = [];
    const params = [];

    if (source) { clauses.push('source = $' + (params.push(source))); }
    if (method) { clauses.push('method = $' + (params.push(method))); }
    if (homeserver_id) { clauses.push('homeserver_id = $' + (params.push(Number(homeserver_id)))); }
    if (bridge_id) { clauses.push('bridge_id = $' + (params.push(Number(bridge_id)))); }
    if (since) { clauses.push('inbound_at >= $' + (params.push(new Date(since)))); }

    const where = clauses.length ? ('WHERE ' + clauses.join(' AND ')) : '';
    const limitParamIndex = params.push(Number(limit));

    const sql = `
      SELECT id, source, homeserver_id, bridge_id, method, path,
             inbound_request, outbound_request, response, response_status,
             inbound_at, outbound_at, response_at, created_at
      FROM bridge_manager.requests
      ${where}
      ORDER BY inbound_at DESC NULLS LAST
      LIMIT $${limitParamIndex};
    `;

    const { rows } = await pool.query(sql, params);
    res.json(rows);
  } catch (err) {
    console.error('Error fetching requests:', err);
    res.status(500).json({ error: 'Failed to fetch requests' });
  }
});

// Get single request details
app.get('/api/requests/:id', async (req, res) => {
  try {
    const id = Number(req.params.id);
    const sql = `
      SELECT id, source, homeserver_id, bridge_id, method, path,
             inbound_request, outbound_request, response, response_status,
             inbound_at, outbound_at, response_at, created_at
      FROM bridge_manager.requests
      WHERE id = $1;
    `;
    const { rows } = await pool.query(sql, [id]);
    if (!rows.length) return res.status(404).json({ error: 'Not found' });
    res.json(rows[0]);
  } catch (err) {
    console.error('Error fetching request by id:', err);
    res.status(500).json({ error: 'Failed to fetch request' });
  }
});

// Fallback to index.html for the UI
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Bridge Requests UI listening on http://localhost:${PORT}`);
});
