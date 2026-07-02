// Tiny HTTP forwarder: localhost:11434 -> host.openshell.internal:11434
// Runs inside the NemoClaw sandbox. Uses Node fetch which honors HTTP_PROXY.
'use strict';
const http = require('http');

const TARGET = process.env.OLLAMA_FORWARD_TARGET || 'http://host.openshell.internal:11434';
const PORT = parseInt(process.env.OLLAMA_FORWARD_PORT || '11434', 10);
const HOST = '127.0.0.1';

console.log(`[forwarder] target=${TARGET} port=${PORT}`);
console.log(`[forwarder] HTTP_PROXY=${process.env.HTTP_PROXY || '(none)'}`);
console.log(`[forwarder] NODE_USE_ENV_PROXY=${process.env.NODE_USE_ENV_PROXY || '0'}`);

const server = http.createServer(async (req, res) => {
    const url = TARGET + req.url;
    const start = Date.now();
    try {
        const headers = { ...req.headers };
        delete headers.host;
        delete headers.connection;
        delete headers['content-length']; // fetch sets it
        const opts = { method: req.method, headers };
        if (!['GET', 'HEAD'].includes(req.method)) {
            opts.body = req;
            opts.duplex = 'half';
        }
        const up = await fetch(url, opts);
        const ms = Date.now() - start;
        console.log(`[${req.method}] ${req.url} -> ${up.status} (${ms}ms)`);
        const respHeaders = {};
        up.headers.forEach((v, k) => {
            if (!['content-encoding', 'transfer-encoding', 'connection'].includes(k.toLowerCase())) {
                respHeaders[k] = v;
            }
        });
        res.writeHead(up.status, respHeaders);
        if (up.body) {
            const reader = up.body.getReader();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                if (!res.write(value)) await new Promise(r => res.once('drain', r));
            }
        }
        res.end();
    } catch (err) {
        console.error(`[ERR] ${req.method} ${req.url}: ${err.message} (cause: ${err.cause?.code || err.cause?.message || '-'})`);
        if (!res.headersSent) {
            res.writeHead(502, { 'content-type': 'application/json' });
            res.end(JSON.stringify({ error: 'proxy_error', message: err.message }));
        } else {
            res.end();
        }
    }
});

server.listen(PORT, HOST, () => {
    console.log(`[forwarder] listening on http://${HOST}:${PORT}`);
});
