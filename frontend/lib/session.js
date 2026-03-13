const encoder = new TextEncoder();
let cachedSecretKey = null;

async function getSecretKey() {
  if (cachedSecretKey) return cachedSecretKey;

  const secret = process.env.AUTH_SECRET;
  if (!secret) {
    throw new Error("AUTH_SECRET is not set in environment variables.");
  }
  if (secret.length < 32) {
    throw new Error("AUTH_SECRET must be at least 32 characters long.");
  }

  cachedSecretKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
  return cachedSecretKey;
}

function bufferToHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

function hexToBuffer(hex) {
  const bytes = new Uint8Array(Math.ceil(hex.length / 2));
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
  }
  return bytes.buffer;
}

export async function signSession(payload) {
  const key = await getSecretKey();
  const dataString = JSON.stringify(payload);
  const dataBuffer = encoder.encode(dataString);
  const signatureBuffer = await crypto.subtle.sign("HMAC", key, dataBuffer);
  
  const dataHex = bufferToHex(dataBuffer);
  const signatureHex = bufferToHex(signatureBuffer);
  
  return `${dataHex}.${signatureHex}`;
}

export async function verifySession(token) {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;

  const [dataHex, signatureHex] = parts;
  
  try {
    const key = await getSecretKey();
    const dataBuffer = hexToBuffer(dataHex);
    const signatureBuffer = hexToBuffer(signatureHex);
    
    const isValid = await crypto.subtle.verify("HMAC", key, signatureBuffer, dataBuffer);
    if (!isValid) return null;
    
    const dataString = new TextDecoder().decode(dataBuffer);
    const session = JSON.parse(dataString);
    if (session.exp && session.exp < Date.now()) {
      return null;
    }
    return session;
  } catch (err) {
    return null;
  }
}
