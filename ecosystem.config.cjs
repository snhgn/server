const fs = require('fs');
const path = require('path');

// 加载 .env 文件
const envPath = path.join('/home/a/snhgn.me', '.env');
const envFile = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';

const envVars = {};
envFile.split('\n').forEach(line => {
  line = line.trim();
  if (!line || line.startsWith('#')) return;
  const idx = line.indexOf('=');
  if (idx === -1) return;
  const key = line.slice(0, idx).trim();
  const val = line.slice(idx + 1).trim();
  envVars[key] = val;
});

module.exports = {
  apps: [
    {
      name: 'snhgn-me',
      script: './dist/server/entry.mjs',
      cwd: '/home/a/snhgn.me',
      env: {
        NODE_ENV: 'production',
        HOST: '0.0.0.0',
        PORT: 4321,
        ...envVars,
      },
      instances: 1,
      autorestart: true,
      max_memory_restart: '512M',
      error_file: '/home/a/.pm2/logs/snhgn-me-error.log',
      out_file: '/home/a/.pm2/logs/snhgn-me-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
