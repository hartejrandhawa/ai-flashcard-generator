const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:3001";

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.error || `Request failed (${res.status})`);
  return data;
}

export const api = {
  listDecks: (userId) => request(`/decks?user_id=${encodeURIComponent(userId)}`),
  createDeck: (userId, deckName, notesText) =>
    request("/decks", { method: "POST", body: { user_id: userId, deck_name: deckName, notes_text: notesText } }),
  getDueCards: (deckId) => request(`/decks/${deckId}/due`),
  submitReview: (cardId, quality) =>
    request("/reviews", { method: "POST", body: { card_id: cardId, quality } }),
};
