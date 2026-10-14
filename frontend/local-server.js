const fs = require('fs');
const http = require('http');
const path = require('path');

const root = __dirname;
const port = Number(process.env.FRONTEND_PORT || 3000);
const host = process.env.FRONTEND_HOST || '::1';

const contentTypes = {
  '.css': 'text/css',
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.json': 'application/json',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

http.createServer((req, res) => {
  let routePath = decodeURIComponent(req.url.split('?')[0]);
  if (routePath === '/' || routePath === '') routePath = '/index.html';

  const filePath = path.normalize(path.join(root, routePath));
  if (!filePath.startsWith(root)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }

    res.writeHead(200, {
      'Content-Type': contentTypes[path.extname(filePath)] || 'application/octet-stream',
    });
    res.end(data);
  });
}).listen(port, host, () => {
  console.log(`Frontend running on http://localhost:${port}`);
});
