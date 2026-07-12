module.exports = {
  apps: [
    {
      name: 'snhgn-me',
      script: './dist/server/entry.mjs',
      cwd: '/home/a/snhgn.me',
      env: {
        NODE_ENV: 'production',
        HOST: '127.0.0.1',
        PORT: 4321,
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
