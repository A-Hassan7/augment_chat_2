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
    const { source, method, homeserver_id, bridge_id, limit = '100', since, status } = req.query;

    const clauses = [];
    const params = [];

    if (source) { clauses.push('source = $' + (params.push(source))); }
    if (method) { clauses.push('method = $' + (params.push(method))); }
    if (homeserver_id) { clauses.push('homeserver_id = $' + (params.push(Number(homeserver_id)))); }
    if (bridge_id) { clauses.push('bridge_id = $' + (params.push(Number(bridge_id)))); }
    if (since) { clauses.push('inbound_at >= $' + (params.push(new Date(since)))); }
    if (status === '200') { clauses.push('response_status = 200'); }
    else if (status === 'non-200') { clauses.push('response_status IS NOT NULL AND response_status != 200'); }

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

// Stats endpoints for dashboard
// Time-series traffic: requests by time bucket
app.get('/api/stats/traffic', async (req, res) => {
  try {
    const { interval = 'hour', range = '24h' } = req.query;
    
    // Map interval to postgres date_trunc
    const truncMap = { second: 'second', minute: 'minute', hour: 'hour', day: 'day' };
    const trunc = truncMap[interval] || 'hour';
    
    // Map range to time offset
    const rangeMap = { '1h': '1 hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days' };
    const offset = rangeMap[range] || '24 hours';
    
    const sql = `
      SELECT date_trunc($1, inbound_at) AS time_bucket, COUNT(*) AS count
      FROM bridge_manager.requests
      WHERE inbound_at >= NOW() - INTERVAL '${offset}'
      GROUP BY time_bucket
      ORDER BY time_bucket ASC;
    `;
    const { rows } = await pool.query(sql, [trunc]);
    res.json(rows);
  } catch (err) {
    console.error('Error fetching traffic stats:', err);
    res.status(500).json({ error: 'Failed to fetch traffic stats' });
  }
});

// Status code breakdown
app.get('/api/stats/status', async (req, res) => {
  try {
    const { timeRange = '24h' } = req.query;
    const rangeMap = { '1h': '1 hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days', 'all': '100 years' };
    const offset = rangeMap[timeRange] || '24 hours';
    
    const sql = `
      SELECT 
        CASE 
          WHEN response_status = 200 THEN '200'
          WHEN response_status >= 400 AND response_status < 500 THEN '4xx'
          WHEN response_status >= 500 THEN '5xx'
          ELSE 'Other'
        END AS status_group,
        COUNT(*) AS count
      FROM bridge_manager.requests
      WHERE response_status IS NOT NULL
        AND inbound_at >= NOW() - INTERVAL '${offset}'
      GROUP BY status_group
      ORDER BY status_group;
    `;
    const { rows } = await pool.query(sql);
    res.json(rows);
  } catch (err) {
    console.error('Error fetching status stats:', err);
    res.status(500).json({ error: 'Failed to fetch status stats' });
  }
});

// Source split
app.get('/api/stats/source', async (req, res) => {
  try {
    const { timeRange = '24h' } = req.query;
    const rangeMap = { '1h': '1 hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days', 'all': '100 years' };
    const offset = rangeMap[timeRange] || '24 hours';
    
    const sql = `
      SELECT source, COUNT(*) AS count
      FROM bridge_manager.requests
      WHERE source IS NOT NULL
        AND inbound_at >= NOW() - INTERVAL '${offset}'
      GROUP BY source
      ORDER BY count DESC;
    `;
    const { rows } = await pool.query(sql);
    res.json(rows);
  } catch (err) {
    console.error('Error fetching source stats:', err);
    res.status(500).json({ error: 'Failed to fetch source stats' });
  }
});

// Method distribution
app.get('/api/stats/method', async (req, res) => {
  try {
    const { timeRange = '24h' } = req.query;
    const rangeMap = { '1h': '1 hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days', 'all': '100 years' };
    const offset = rangeMap[timeRange] || '24 hours';
    
    const sql = `
      SELECT method, COUNT(*) AS count
      FROM bridge_manager.requests
      WHERE method IS NOT NULL
        AND inbound_at >= NOW() - INTERVAL '${offset}'
      GROUP BY method
      ORDER BY count DESC;
    `;
    const { rows } = await pool.query(sql);
    res.json(rows);
  } catch (err) {
    console.error('Error fetching method stats:', err);
    res.status(500).json({ error: 'Failed to fetch method stats' });
  }
});

// Top 10 paths
app.get('/api/stats/paths', async (req, res) => {
  try {
    const { timeRange = '24h' } = req.query;
    const rangeMap = { '1h': '1 hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days', 'all': '100 years' };
    const offset = rangeMap[timeRange] || '24 hours';
    
    const sql = `
      SELECT path, COUNT(*) AS count
      FROM bridge_manager.requests
      WHERE path IS NOT NULL
        AND inbound_at >= NOW() - INTERVAL '${offset}'
      GROUP BY path
      ORDER BY count DESC
      LIMIT 10;
    `;
    const { rows } = await pool.query(sql);
    res.json(rows);
  } catch (err) {
    console.error('Error fetching path stats:', err);
    res.status(500).json({ error: 'Failed to fetch path stats' });
  }
});

// Error rate timeline
app.get('/api/stats/errors', async (req, res) => {
  try {
    const { interval = 'hour', range = '24h' } = req.query;
    
    const truncMap = { second: 'second', minute: 'minute', hour: 'hour', day: 'day' };
    const trunc = truncMap[interval] || 'hour';
    
    const rangeMap = { '1h': '1 hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days' };
    const offset = rangeMap[range] || '24 hours';
    
    const sql = `
      SELECT 
        date_trunc($1, inbound_at) AS time_bucket,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE response_status >= 400) AS errors,
        ROUND(100.0 * COUNT(*) FILTER (WHERE response_status >= 400) / NULLIF(COUNT(*), 0), 2) AS error_rate
      FROM bridge_manager.requests
      WHERE inbound_at >= NOW() - INTERVAL '${offset}'
      GROUP BY time_bucket
      ORDER BY time_bucket ASC;
    `;
    const { rows } = await pool.query(sql, [trunc]);
    res.json(rows);
  } catch (err) {
    console.error('Error fetching error stats:', err);
    res.status(500).json({ error: 'Failed to fetch error stats' });
  }
});

// Fallback to index.html for the UI
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Bridge Requests UI listening on http://localhost:${PORT}`);
});
