// Sign-in with the Cognito hosted page using the OAuth authorization-code flow
// plus PKCE.
//
// Why hand-written instead of a library: the flow is ~100 lines, adds no
// dependency, and a browser app can't keep a client secret anyway, so PKCE
// (a one-time secret proven at token exchange) is what protects the flow.
//
// Why the ID token: API Gateway's Cognito authorizer verifies the ID token,
// and the backend reads the user's `sub` claim from it.
//
// Tokens live in sessionStorage: they vanish when the tab closes and aren't
// shared across tabs, which limits how long a stolen token is useful.

const DOMAIN = (import.meta.env.VITE_COGNITO_DOMAIN || "").replace(/\/$/, "");
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || "";
const TOKENS_KEY = "flashcard_tokens";
const PKCE_KEY = "flashcard_pkce";

const redirectUri = () => `${window.location.origin}/`;

export const isConfigured = () => Boolean(DOMAIN && CLIENT_ID);

function read(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key));
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage blocked: sign-in still works for this page load.
  }
}

function clear(key) {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
}

function base64Url(bytes) {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function randomString(byteLength = 32) {
  return base64Url(crypto.getRandomValues(new Uint8Array(byteLength)));
}

async function sha256Challenge(verifier) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(verifier),
  );
  return base64Url(new Uint8Array(digest));
}

async function tokenRequest(params) {
  const res = await fetch(`${DOMAIN}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: CLIENT_ID, ...params }),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok || !data?.id_token)
    throw new Error(data?.error_description || data?.error || "Sign-in failed");
  return data;
}

function storeTokens(data, previous) {
  write(TOKENS_KEY, {
    idToken: data.id_token,
    // A refresh response doesn't include a new refresh token; keep the old one.
    refreshToken: data.refresh_token || previous?.refreshToken || null,
    expiresAt: Date.now() + data.expires_in * 1000,
  });
}

export async function login() {
  const verifier = randomString(48);
  const state = randomString(16);
  write(PKCE_KEY, { verifier, state });
  const params = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    redirect_uri: redirectUri(),
    scope: "openid email",
    state,
    code_challenge: await sha256Challenge(verifier),
    code_challenge_method: "S256",
  });
  window.location.assign(`${DOMAIN}/oauth2/authorize?${params}`);
}

export function logout() {
  clear(TOKENS_KEY);
  clear(PKCE_KEY);
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: redirectUri(),
  });
  window.location.assign(`${DOMAIN}/logout?${params}`);
}

export function clearSession() {
  clear(TOKENS_KEY);
}

export const isLoggedIn = () => Boolean(read(TOKENS_KEY)?.idToken);

// React StrictMode runs effects twice in development, and an authorization
// code can only be redeemed once, so the exchange is memoised.
let callbackPromise = null;
export function handleCallback() {
  callbackPromise ??= exchangeCodeIfPresent();
  return callbackPromise;
}

async function exchangeCodeIfPresent() {
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const oauthError =
    url.searchParams.get("error_description") || url.searchParams.get("error");

  if (!code && !oauthError) return;

  // Remove the one-time values from the address bar and history right away.
  window.history.replaceState({}, "", url.pathname);

  if (oauthError) throw new Error(oauthError);

  const pkce = read(PKCE_KEY);
  clear(PKCE_KEY);
  // The state value ties this response to the sign-in we started (CSRF defence).
  if (!pkce || pkce.state !== state)
    throw new Error("Sign-in could not be verified. Please try again.");

  storeTokens(
    await tokenRequest({
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri(),
      code_verifier: pkce.verifier,
    }),
  );
}

let refreshing = null;

// A valid ID token, refreshed first if it is about to expire; null if signed out.
export async function getIdToken() {
  const tokens = read(TOKENS_KEY);
  if (!tokens?.idToken) return null;
  if (tokens.expiresAt - Date.now() > 60_000) return tokens.idToken;
  if (!tokens.refreshToken) {
    clear(TOKENS_KEY);
    return null;
  }

  // Several requests can notice the expiry at once; share one refresh.
  refreshing ??= tokenRequest({
    grant_type: "refresh_token",
    refresh_token: tokens.refreshToken,
  })
    .then((data) => {
      storeTokens(data, tokens);
      return data.id_token;
    })
    .catch(() => {
      clear(TOKENS_KEY);
      return null;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}
