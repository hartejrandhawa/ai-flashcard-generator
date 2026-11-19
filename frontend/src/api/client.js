import { clearSession, getIdToken, login } from "../auth";

const API_BASE = (
  import.meta.env.VITE_API_BASE || "http://localhost:3001"
).replace(/\/$/, "");

// The user's local calendar date (YYYY-MM-DD). The server schedules reviews
// against this so "due today" follows the user's day instead of UTC.
export function localToday() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

async function request(path, { method = "GET", body } = {}) {
  const token = await getIdToken();
  if (!token) {
    login();
    throw new Error("Your session has expired. Redirecting to sign in...");
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: { "Content-Type": "application/json", Authorization: token },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error(
      "Can't reach the server. Check your connection and try again.",
    );
  }

  if (res.status === 401) {
    clearSession();
    login();
    throw new Error("Your session has expired. Redirecting to sign in...");
  }

  const data = await res.json().catch(() => null);
  if (!res.ok)
    throw new Error(
      data?.error || data?.message || `Request failed (${res.status})`,
    );
  return data;
}

export const api = {
  listDecks: () => request(`/decks?today=${localToday()}`),
  createDeck: (deckName, notesText) =>
    request("/decks", {
      method: "POST",
      body: { deck_name: deckName, notes_text: notesText },
    }),
  renameDeck: (deckId, deckName) =>
    request(`/decks/${deckId}`, {
      method: "PATCH",
      body: { deck_name: deckName },
    }),
  deleteDeck: (deckId) => request(`/decks/${deckId}`, { method: "DELETE" }),
  getDeckCards: (deckId) => request(`/decks/${deckId}/cards`),
  getDueCards: (deckId) =>
    request(`/decks/${deckId}/due?today=${localToday()}`),
  submitReview: (cardId, quality) =>
    request("/reviews", {
      method: "POST",
      body: { card_id: cardId, quality, today: localToday() },
    }),
  updateCard: (cardId, front, back) =>
    request(`/cards/${cardId}`, { method: "PATCH", body: { front, back } }),
  deleteCard: (cardId) => request(`/cards/${cardId}`, { method: "DELETE" }),
};
