'use strict';

// ============================================================
//  Jerry MITM Proxy — HTTP + SOCKS5 + SSL Interception
//  Tự động patch file cache_res / avatar khi tải về
//  Không cần npm — chạy: node server.js
// ============================================================

const net   = require('net');
const tls   = require('tls');
const http  = require('http');
const https = require('https');
const fs    = require('fs');
const path  = require('path');
const { execFileSync } = require('child_process');

const PORT   = process.env.PORT || 8080;
const CA_DIR = path.join(__dirname, '.ca');

// ============================================================
//  HEX PATCH ENGINE — dữ liệu thật từ Make_Data_V1.9.0.5
// ============================================================
const AIM_BODY_BONES = [
  'bone_Hips_Dummy','bone_RightClav','bone_LeftThumb2','bone_RightAnkle','bone_Spine',
  'bone_RightMiddle1','bone_Left_Spine_Backpack','bone_LeftLeg','bone_Hips','bone_LeftMiddle2',
  'bone_RightArm','bone_RightToe','bone_LeftThumb1','bone_LeftAnkle','bone_LeftHand',
  'bone_RightThumb1','bone_LeftF_Hips_Weapon','bone_LeftForeArm','bone_Spine1','bone_RightThumb2',
  'bone_LeftArm','bone_RightForeArm','bone_LeftMiddle1','bone_RightLegUpper','bone_LeftLegUpper',
  'bone_Right_Spine_Weapon','bone_RightIndex1','bone_RightLeg','bone_LeftToe','bone_RightMiddle2',
  'bone_LeftClav','bone_Right_Hips_Weapon','bone_RightHand','bone_Left_Spine_Weapon','bone_LeftIndex1',
  'bone_RightIndex2','bone_LeftIndex2',
];

// cache_res patches (CACHE_HEX_CONFIG từ Make Data)
const CACHE_PATCHES = [
  // AIM Body — curve injection
  { name:'AIM Body 1', find:'226e1f3f5300000000000000',                  replace:'226E1F3F53000000000000000000000000000000000000000000000000000000000100000059DFCA3DE48C023E000000001DBB143E' },
  { name:'AIM Body 2', find:'bf9fb489cd0000000000000000000000',           replace:'BF9FB489CD00000000000000000000000000000000000000000000000000000000010000003E11CB3D7283053E000000006D27103E' },
  // Nhẹ Tâm (cache_res)
  { name:'Nhẹ Tâm 1', find:'a8e7713de48c023e00000000dc5239bd',           replace:'64dfca3de48c023e000000009f48623d' },
  { name:'Nhẹ Tâm 2', find:'724b723d7283053e00000000180427bd',           replace:'3111cb3d7283053e00000000bdf94f3d' },
];

// avatar patches (HEX_CONFIG từ Make Data)
const AVATAR_PATCHES = [
  // AIM Cân
  { name:'AIM Cân',      find:'4C7B5ABD0A5766BB1E2148BA2AC2CF3B96FB283DE8B117BDE3997F3F0400803F0100803FFCFF7F3F10000000626F6E655F4C6566745F576561706F6E23AAA6B8460ACD70', replace:'170E743FEA5B66BB100448BAC6BFCF3B0DFC283D03B217BDE5997F3F0000604100006041000060410F000000626F6E655F5370696E6531000000000023AAA6B8B2F71FA4' },
  // AIM Drag
  { name:'AIM Drag',     find:'F9B4316974EB4C7B5ABD0A5766BB1E2148BA2AC2CF3B96FB283DE8B117BDE3997F3F0400803F0100803FFCFF7F3F10000000626F6E655F4C6566745F576561706F6E23AAA6B8460ACD706BF908BE00000000000000008BDD9C30ECCFFFB28BDD1C3DECCF7F3F0000803F0000803F0000803F10000000', replace:'F9B4316974EBE10AC0BE55DC98BD69C5D6B300000000AFEC2B40BD3706B7931A5AB7761CC73F761CC73F761CC73F10000000626F6E655F486561640000000000000023AAA6B8B2F71FA46BF908BE00000000000000008BDD9C30ECCFFFB28BDD1C3DECCF7F3F0000803F0000803F0000803F10000000' },
  // Avatar AimLock
  { name:'AimLock',      find:'F9B4316974EB4C7B5ABD0A5766BB1E2148BA2AC2CF3B96FB283DE8B117BDE3997F3F0400803F0100803FFCFF7F3F10000000626F6E655F4C6566745F576561706F6E23AAA6B8460ACD706BF908BE00000000000000008BDD9C30ECCFFFB28BDD1C3DECCF7F3F0000803F0000803F0000803F10000000', replace:'F9B4316974EBD7339CBEBAD7C93CBD3706B600000000AFEC2B40BD3706B7931A5AB7761CC73F761CC73F761CC73F10000000626F6E655F486561640000000000000023AAA6B8B2F71FA46BF908BE00000000000000008BDD9C30ECCFFFB28BDD1C3DECCF7F3F0000803F0000803F0000803F10000000' },
  // AIM Bụng
  { name:'AIM Bụng 1',  find:'4C7B5ABD0A5766BB1E2148BA2AC2CF3B96FB283DE8B117BDE3997F3F0400803F0100803FFCFF7F3F10000000626F6E655F4C6566745F576561706F6E23AAA6B8460ACD70', replace:'7DAE36BD24977FBBB7C8CCB12AC2CF3BEEA34240E8B117BDE3997F3F721CC73F721CC73F721CC73F10000000626F6E655F486561640000000000000023AAA6B8B2F71FA4' },
  { name:'AIM Bụng 2',  find:'7BD5FEBD6BF1AEBCDA658FB338C2152A1FCD043542A636BE0DE57B3F0100803F0100803F0000803F09000000626F6E655F4E65636BA158C305B2F71FA4', replace:'7BD5FEBD6BF1AEBCDA658FB338C2152A1FCD043542A636BE0DE57B3F0100803F295C8F3F295C8F3F09000000626F6E655F4E65636BA158C305B2F71FA4' },
  // Antena Tay
  { name:'Antena Tay 1', find:'16080EBFCD0B13BD9FC9543F866885BEE6D354BF37B37F3D3E5E0DBF64CD093F2C5603BDDA557FBF7D0E84BD6556653D0000000000000000000000000000803F', replace:'16080EBFCD0B13BD9FC9543F866885BEE6D354BF37B37F3D3E5E0DBF64CD093F2C5603BDDA557FBF7D0E84BD6556653D0000000000000000000000000000FA43' },
  { name:'Antena Tay 2', find:'B4828F3E3AB11A3E02AD723F6BA5E0BEDE28713F12F7153E31909ABEF0DED33ECADB3CBEFB447A3F7F61CFBD11F82D3D0000000000000000000000000000803F', replace:'B4828F3E3AB11A3E02AD723F6BA5E0BEDE28713F12F7153E31909ABEF0DED33ECADB3CBEFB447A3F7F61CFBD11F82D3D0000000000000000000000000000FA43' },
];

function h2b(hex) {
  const s = hex.replace(/[^0-9A-Fa-f]/g, '');
  if (s.length % 2 !== 0) return null;
  const b = Buffer.allocUnsafe(s.length / 2);
  for (let i = 0; i < s.length; i += 2) b[i >> 1] = parseInt(s.substr(i, 2), 16);
  return b;
}

function applyHexPatches(buf, patches) {
  let hits = 0;
  for (const p of patches) {
    const find    = h2b(p.find);
    const replace = h2b(p.replace);
    if (!find || !replace) continue;
    for (let i = 0; i <= buf.length - find.length; i++) {
      let ok = true;
      for (let j = 0; j < find.length; j++) if (buf[i + j] !== find[j]) { ok = false; break; }
      if (ok) {
        replace.copy(buf, i, 0, Math.min(replace.length, buf.length - i));
        hits++; i += replace.length - 1;
      }
    }
  }
  return hits;
}

function applyAimBodyBones(buf) {
  let hits = 0;
  for (const bone of AIM_BODY_BONES) {
    const search  = Buffer.from(bone, 'latin1');
    const replace = Buffer.alloc(bone.length, 0);
    for (let i = 0; i <= buf.length - search.length; i++) {
      if (buf.subarray(i, i + search.length).equals(search)) {
        replace.copy(buf, i); hits++; i += search.length - 1;
      }
    }
  }
  return hits;
}

function patchBinary(data) {
  const buf = Buffer.from(data);
  let total = 0;
  total += applyAimBodyBones(buf);
  total += applyHexPatches(buf, CACHE_PATCHES);
  total += applyHexPatches(buf, AVATAR_PATCHES);
  return { buf, total };
}

function isBinaryResponse(headers) {
  const ct = (headers['content-type'] || '').toLowerCase();
  return ct === '' || ct.includes('octet-stream') || ct.includes('binary')
    || ct.includes('x-unity') || ct.includes('application/zip');
}

// ============================================================
//  CA & CERT GENERATION (dùng openssl có sẵn trên Linux)
// ============================================================
const certCache = new Map();

function ensureCA() {
  fs.mkdirSync(CA_DIR, { recursive: true });
  const caKey  = path.join(CA_DIR, 'ca.key');
  const caCert = path.join(CA_DIR, 'ca.crt');
  if (!fs.existsSync(caKey)) {
    log('Tạo CA key...');
    execFileSync('openssl', ['genrsa', '-out', caKey, '2048'], { stdio: 'pipe' });
  }
  if (!fs.existsSync(caCert)) {
    log('Tạo CA cert...');
    execFileSync('openssl', ['req', '-new', '-x509', '-days', '3650',
      '-key', caKey, '-out', caCert,
      '-subj', '/CN=Jerry Proxy CA/O=Jerry Tool/C=VN'], { stdio: 'pipe' });
  }
  log('CA cert sẵn sàng: ' + caCert);
  return { caKey, caCert };
}

function getHostCert(hostname) {
  if (certCache.has(hostname)) return certCache.get(hostname);

  const safeHost = hostname.replace(/[^a-zA-Z0-9._-]/g, '_');
  const keyFile  = path.join(CA_DIR, `${safeHost}.key`);
  const crtFile  = path.join(CA_DIR, `${safeHost}.crt`);
  const csrFile  = path.join(CA_DIR, `${safeHost}.csr`);
  const extFile  = path.join(CA_DIR, `${safeHost}.ext`);
  const caKey    = path.join(CA_DIR, 'ca.key');
  const caCert   = path.join(CA_DIR, 'ca.crt');

  if (!fs.existsSync(crtFile)) {
    execFileSync('openssl', ['genrsa', '-out', keyFile, '2048'], { stdio: 'pipe' });
    execFileSync('openssl', ['req', '-new', '-key', keyFile, '-out', csrFile,
      '-subj', `/CN=${hostname}`], { stdio: 'pipe' });
    const san = `authorityKeyIdentifier=keyid,issuer\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:${hostname},DNS:*.${hostname}`;
    fs.writeFileSync(extFile, san);
    execFileSync('openssl', ['x509', '-req', '-days', '825',
      '-in', csrFile, '-CA', caCert, '-CAkey', caKey, '-CAcreateserial',
      '-out', crtFile, '-extfile', extFile], { stdio: 'pipe' });
  }

  const result = { key: fs.readFileSync(keyFile), cert: fs.readFileSync(crtFile) };
  certCache.set(hostname, result);
  return result;
}

// ============================================================
//  TIỆN ÍCH
// ============================================================
function log(msg) { console.log(`[${new Date().toISOString().slice(11,19)}] ${msg}`); }

function pipe2(a, b) {
  a.pipe(b); b.pipe(a);
  a.on('error', () => b.destroy());
  b.on('error', () => a.destroy());
  a.on('close',  () => b.destroy());
  b.on('close',  () => a.destroy());
}

function readN(socket, n) {
  return new Promise((resolve) => {
    const chunks = []; let got = 0;
    socket.resume();
    const onData = (c) => {
      chunks.push(c); got += c.length;
      if (got >= n) {
        socket.pause();
        socket.removeListener('data', onData);
        socket.removeListener('error', onErr);
        socket.removeListener('close', onErr);
        resolve(Buffer.concat(chunks).slice(0, n));
      }
    };
    const onErr = () => {
      socket.removeListener('data', onData);
      socket.removeListener('error', onErr);
      socket.removeListener('close', onErr);
      resolve(null);
    };
    socket.on('data', onData);
    socket.on('error', onErr);
    socket.on('close', onErr);
  });
}

// ============================================================
//  FORWARD REQUEST + PATCH RESPONSE
// ============================================================
function forwardRequest(req, res, targetHost) {
  const isHttps = req.socket instanceof tls.TLSSocket;
  const proto   = isHttps ? https : http;
  const port    = isHttps ? 443 : 80;

  const options = {
    hostname: targetHost,
    port,
    path    : req.url,
    method  : req.method,
    headers : { ...req.headers, host: targetHost },
    rejectUnauthorized: false, // trust tất cả cert phía server
  };

  const proxyReq = proto.request(options, (proxyRes) => {
    const shouldPatch = isBinaryResponse(proxyRes.headers);
    const chunks = [];

    proxyRes.on('data', (c) => chunks.push(c));
    proxyRes.on('end', () => {
      const raw = Buffer.concat(chunks);

      if (shouldPatch && raw.length > 0) {
        const { buf, total } = patchBinary(raw);
        if (total > 0) {
          log(`PATCH ${targetHost}${req.url} — ${total} thay thế`);
          const headers = { ...proxyRes.headers, 'content-length': buf.length.toString() };
          delete headers['transfer-encoding'];
          res.writeHead(proxyRes.statusCode, headers);
          res.end(buf);
          return;
        }
      }

      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      res.end(raw);
    });
  });

  proxyReq.on('error', () => { try { res.writeHead(502); res.end(); } catch {} });

  req.on('data', (c) => proxyReq.write(c));
  req.on('end', () => proxyReq.end());
}

// ============================================================
//  MITM HTTPS — wrap socket TLS rồi dùng http.Server để parse
// ============================================================
function mitmHttps(rawSocket, targetHost) {
  let hostCert;
  try { hostCert = getHostCert(targetHost); }
  catch (e) { log(`Lỗi tạo cert cho ${targetHost}: ${e.message}`); rawSocket.destroy(); return; }

  const tlsSock = new tls.TLSSocket(rawSocket, {
    isServer : true,
    key      : hostCert.key,
    cert     : hostCert.cert,
  });
  tlsSock.on('error', () => {});

  // Tạo HTTP server ảo, kết nối trực tiếp vào tlsSock
  const fakeServer = http.createServer((req, res) => {
    log(`MITM ${targetHost}${req.url}`);
    forwardRequest(req, res, targetHost);
  });
  fakeServer.emit('connection', tlsSock);
}

// ============================================================
//  HTTP HANDLER
// ============================================================
function handleHttp(socket, firstChunk) {
  const text      = firstChunk.toString('utf8', 0, Math.min(firstChunk.length, 4096));
  const firstLine = text.split('\r\n')[0] || '';

  // Serve CA cert — user trỏ trình duyệt đến http://proxy-ip:port/ca.crt
  if (firstLine.startsWith('GET /ca.crt')) {
    try {
      const ca = fs.readFileSync(path.join(CA_DIR, 'ca.crt'));
      socket.write(
        `HTTP/1.1 200 OK\r\nContent-Type: application/x-x509-ca-cert\r\nContent-Disposition: attachment; filename="jerry-ca.crt"\r\nContent-Length: ${ca.length}\r\n\r\n`
      );
      socket.write(ca);
    } catch { socket.write('HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n'); }
    socket.end();
    log(`Đã serve CA cert cho ${socket.remoteAddress}`);
    return;
  }

  if (!firstLine.startsWith('CONNECT ')) {
    socket.write('HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n');
    socket.end();
    return;
  }

  const target = firstLine.split(' ')[1] || '';
  const colon  = target.lastIndexOf(':');
  const host   = target.slice(0, colon);
  const port   = parseInt(target.slice(colon + 1)) || 443;

  if (port === 443) {
    socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
    mitmHttps(socket, host);
  } else {
    // TCP tunnel cho port khác
    socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
    const remote = net.connect(port, host, () => pipe2(socket, remote));
    remote.on('error', () => { try { socket.write('HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n'); } catch {} socket.end(); });
    log(`TUNNEL ${host}:${port}`);
  }
}

// ============================================================
//  SOCKS5 HANDLER
// ============================================================
async function handleSocks5(socket) {
  const nmBuf = await readN(socket, 1);
  if (!nmBuf) { socket.destroy(); return; }
  const nm = nmBuf[0];
  if (nm > 0) await readN(socket, nm);
  socket.write(Buffer.from([0x05, 0x00])); // No Auth

  const hdr = await readN(socket, 4);
  if (!hdr || hdr[1] !== 0x01) { socket.write(Buffer.from([0x05, 0x07, 0x00, 0x01, 0,0,0,0, 0,0])); socket.destroy(); return; }

  let host, port;
  const atyp = hdr[3];

  if (atyp === 0x01) {
    const d = await readN(socket, 6); if (!d) { socket.destroy(); return; }
    host = `${d[0]}.${d[1]}.${d[2]}.${d[3]}`; port = d.readUInt16BE(4);
  } else if (atyp === 0x03) {
    const lb = await readN(socket, 1); if (!lb) { socket.destroy(); return; }
    const db = await readN(socket, lb[0] + 2); if (!db) { socket.destroy(); return; }
    host = db.slice(0, lb[0]).toString(); port = db.readUInt16BE(lb[0]);
  } else if (atyp === 0x04) {
    const d = await readN(socket, 18); if (!d) { socket.destroy(); return; }
    const p = []; for (let i = 0; i < 8; i++) p.push(d.readUInt16BE(i*2).toString(16));
    host = p.join(':'); port = d.readUInt16BE(16);
  } else {
    socket.write(Buffer.from([0x05, 0x08, 0x00, 0x01, 0,0,0,0, 0,0])); socket.destroy(); return;
  }

  if (port === 443) {
    socket.write(Buffer.from([0x05, 0x00, 0x00, 0x01, 0,0,0,0, 0,0]));
    mitmHttps(socket, host);
    log(`SOCKS5 MITM ${host}:${port}`);
  } else {
    const remote = net.connect(port, host, () => {
      socket.write(Buffer.from([0x05, 0x00, 0x00, 0x01, 0,0,0,0, 0,0]));
      pipe2(socket, remote);
    });
    remote.on('error', () => { try { socket.write(Buffer.from([0x05, 0x05, 0x00, 0x01, 0,0,0,0, 0,0])); } catch {} socket.destroy(); });
    log(`SOCKS5 TUNNEL ${host}:${port}`);
  }
}

// ============================================================
//  MAIN SERVER
// ============================================================
ensureCA();

const server = net.createServer((socket) => {
  socket.on('error', () => {});
  socket.setTimeout(60000, () => socket.destroy());
  socket.pause();

  socket.once('data', (chunk) => {
    socket.pause();
    if (chunk[0] === 0x05) {
      handleSocks5(socket).catch(() => socket.destroy());
    } else {
      handleHttp(socket, chunk);
    }
  });
});

server.on('error', (e) => console.error('Server error:', e.message));

server.listen(PORT, '0.0.0.0', () => {
  const caCert = path.join(CA_DIR, 'ca.crt');
  console.log('');
  console.log('  ╔══════════════════════════════════════════════════╗');
  console.log('  ║   Jerry MITM Proxy — Patch file tự động        ║');
  console.log(`  ║   Port: ${String(PORT).padEnd(41)}║`);
  console.log('  ╚══════════════════════════════════════════════════╝');
  console.log('');
  console.log('  Patch engine:');
  console.log('    Bones     :', AIM_BODY_BONES.length, 'bones');
  console.log('    Cache hex :', CACHE_PATCHES.length, 'patches');
  console.log('    Avatar hex:', AVATAR_PATCHES.length, 'patches');
  console.log('');
  console.log('  CA cert:');
  console.log('   ', caCert);
  console.log('');
  console.log('  ┌── Cách dùng ─────────────────────────────────────┐');
  console.log('  │ 1. Deploy lên Railway → lấy TCP hostname:port    │');
  console.log('  │ 2. Cài proxy trên điện thoại (HTTP hoặc SOCKS5) │');
  console.log('  │ 3. Mở trình duyệt → http://<host>:<port>/ca.crt │');
  console.log('  │    Tải về rồi cài CA cert vào điện thoại        │');
  console.log('  │ 4. Bật proxy → mở game → cache tải về tự patch  │');
  console.log('  └──────────────────────────────────────────────────┘');
  console.log('');
});
