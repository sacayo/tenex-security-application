/** UI-only session cookie. Edge-safe (Web Crypto) so middleware can verify it. */

export const SESSION_COOKIE = "sae_session";
export const SESSION_MAX_AGE = 60 * 60 * 24 * 7;

export function isAuthEnabled(): boolean {
  return Boolean(
    process.env.AUTH_USERNAME &&
      process.env.AUTH_PASSWORD &&
      process.env.AUTH_SECRET,
  );
}

export function sessionCookieOptions(maxAge: number = SESSION_MAX_AGE) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  };
}

function utf8(text: string): BufferSource {
  return new TextEncoder().encode(text);
}

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(value: string): Uint8Array {
  const padded =
    value.replace(/-/g, "+").replace(/_/g, "/") +
    "===".slice((value.length + 3) % 4);
  const binary = atob(padded);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

async function hmacSign(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    utf8(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, utf8(message));
  return toBase64Url(new Uint8Array(signature));
}

function secretsEqual(left: string, right: string): boolean {
  const a = new TextEncoder().encode(left);
  const b = new TextEncoder().encode(right);
  const n = Math.max(a.length, b.length, 1);
  let mismatch = a.length ^ b.length;
  for (let i = 0; i < n; i++) {
    mismatch |= (a[i] ?? 0) ^ (b[i] ?? 0);
  }
  return mismatch === 0;
}

export function credentialsMatch(username: string, password: string): boolean {
  return (
    secretsEqual(username, process.env.AUTH_USERNAME ?? "") &&
    secretsEqual(password, process.env.AUTH_PASSWORD ?? "")
  );
}

export async function createSessionValue(username: string): Promise<string> {
  const secret = process.env.AUTH_SECRET;
  if (!secret) throw new Error("AUTH_SECRET is not set");
  const exp = Math.floor(Date.now() / 1000) + SESSION_MAX_AGE;
  const payload = `${username}.${exp}`;
  const signature = await hmacSign(secret, payload);
  return `${toBase64Url(new TextEncoder().encode(payload))}.${signature}`;
}

export async function verifySessionValue(
  token: string | undefined,
): Promise<boolean> {
  if (!token || !isAuthEnabled()) return false;
  const secret = process.env.AUTH_SECRET;
  if (!secret) return false;

  const split = token.lastIndexOf(".");
  if (split <= 0) return false;
  const payloadB64 = token.slice(0, split);
  const signature = token.slice(split + 1);

  let payload: string;
  try {
    payload = new TextDecoder().decode(fromBase64Url(payloadB64));
  } catch {
    return false;
  }

  const expected = await hmacSign(secret, payload);
  if (!secretsEqual(signature, expected)) return false;

  const expSep = payload.lastIndexOf(".");
  if (expSep <= 0) return false;
  const username = payload.slice(0, expSep);
  const exp = Number(payload.slice(expSep + 1));
  if (!Number.isFinite(exp) || exp * 1000 < Date.now()) return false;
  return secretsEqual(username, process.env.AUTH_USERNAME ?? "");
}
