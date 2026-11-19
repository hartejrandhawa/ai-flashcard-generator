import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { cardsToCsv, downloadCsv, safeFilename } from "../lib/csv";
import { MAX_DECK_NAME_CHARS } from "../lib/limits";

const POLL_MS = 3000;
const MAX_FRONT = 500; // keep in sync with backend/lambda_functions/common.py
const MAX_BACK = 1500;

export default function Deck() {
  const { deckId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [renaming, setRenaming] = useState(null); // string while editing the name
  const [editing, setEditing] = useState(null); // { card_id, front, back } while editing a card
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api.getDeckCards(deckId));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [deckId]);

  useEffect(() => {
    load();
  }, [load]);

  const generating = data?.deck.status === "generating";
  useEffect(() => {
    if (!generating) return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [generating, load]);

  // Runs a mutation with a shared busy flag and error display.
  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const saveName = () =>
    run(async () => {
      const name = renaming.trim();
      if (!name) return setRenaming(null);
      await api.renameDeck(deckId, name);
      setData((d) => ({ ...d, deck: { ...d.deck, deck_name: name } }));
      setRenaming(null);
    });

  const removeDeck = () => {
    if (
      !window.confirm(
        `Delete "${data.deck.deck_name}" and all of its cards? This can't be undone.`,
      )
    )
      return;
    run(async () => {
      await api.deleteDeck(deckId);
      navigate("/");
    });
  };

  const saveCard = () =>
    run(async () => {
      const { card_id, front, back } = editing;
      const saved = await api.updateCard(card_id, front, back);
      setData((d) => ({
        ...d,
        cards: d.cards.map((c) =>
          c.card_id === card_id
            ? { ...c, front: saved.front, back: saved.back }
            : c,
        ),
      }));
      setEditing(null);
    });

  const removeCard = (card) => {
    if (!window.confirm("Delete this card?")) return;
    run(async () => {
      await api.deleteCard(card.card_id);
      setData((d) => ({
        ...d,
        cards: d.cards.filter((c) => c.card_id !== card.card_id),
      }));
    });
  };

  if (!data) {
    return (
      <div className="page">
        <Link to="/" className="back-link">
          &larr; All decks
        </Link>
        {error ? (
          <p className="error-text" role="alert">
            {error}{" "}
            <button type="button" className="link-button" onClick={load}>
              Retry
            </button>
          </p>
        ) : (
          <p className="empty-state">Loading...</p>
        )}
      </div>
    );
  }

  const { deck, cards } = data;
  const canEdit = deck.status === "ready";

  return (
    <main className="page deck-page">
      <Link to="/" className="back-link">
        &larr; All decks
      </Link>

      <header className="deck-header">
        {renaming === null ? (
          <div className="deck-title-row">
            <h1 className="deck-title">{deck.deck_name}</h1>
            {canEdit && (
              <button
                type="button"
                className="btn btn-quiet"
                onClick={() => setRenaming(deck.deck_name)}
              >
                Rename
              </button>
            )}
          </div>
        ) : (
          <form
            className="deck-title-row"
            onSubmit={(e) => {
              e.preventDefault();
              saveName();
            }}
          >
            <input
              className="title-input"
              value={renaming}
              maxLength={MAX_DECK_NAME_CHARS}
              onChange={(e) => setRenaming(e.target.value)}
              autoFocus
              aria-label="Deck name"
            />
            <button type="submit" className="btn btn-primary" disabled={busy}>
              Save
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => setRenaming(null)}
            >
              Cancel
            </button>
          </form>
        )}

        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}

        {canEdit && (
          <p className="section-sub">
            {cards.length} card{cards.length === 1 ? "" : "s"}. Check them over
            and fix anything Claude got wrong before you study.
          </p>
        )}
        {generating && (
          <p className="status-line">
            <span className="spinner" aria-hidden="true" /> Claude is writing
            the cards. This page updates when they're ready.
          </p>
        )}
        {deck.status === "failed" && (
          <p className="error-text">{deck.error || "Generation failed."}</p>
        )}

        <div className="deck-actions">
          {canEdit && cards.length > 0 && (
            <Link to={`/quiz/${deckId}`} className="btn btn-primary">
              Study
            </Link>
          )}
          {canEdit && cards.length > 0 && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() =>
                downloadCsv(safeFilename(deck.deck_name), cardsToCsv(cards))
              }
            >
              Export CSV
            </button>
          )}
          <button
            type="button"
            className="btn btn-danger"
            onClick={removeDeck}
            disabled={busy}
          >
            Delete deck
          </button>
        </div>
      </header>

      {canEdit && (
        <div className="sheet">
          {cards.length === 0 && (
            <p className="empty-state">This deck has no cards.</p>
          )}
          <ul className="card-rows">
            {cards.map((c) =>
              editing?.card_id === c.card_id ? (
                <li key={c.card_id} className="card-row editing">
                  <label>
                    Front
                    <textarea
                      value={editing.front}
                      maxLength={MAX_FRONT}
                      rows={2}
                      onChange={(e) =>
                        setEditing({ ...editing, front: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Back
                    <textarea
                      value={editing.back}
                      maxLength={MAX_BACK}
                      rows={3}
                      onChange={(e) =>
                        setEditing({ ...editing, back: e.target.value })
                      }
                    />
                  </label>
                  <div className="deck-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={saveCard}
                      disabled={
                        busy || !editing.front.trim() || !editing.back.trim()
                      }
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="btn btn-quiet"
                      onClick={() => setEditing(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </li>
              ) : (
                <li key={c.card_id} className="card-row">
                  <p className="row-front">{c.front}</p>
                  <p className="row-back">{c.back}</p>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="btn btn-quiet"
                      onClick={() => setEditing({ ...c })}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-quiet"
                      onClick={() => removeCard(c)}
                      disabled={busy}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ),
            )}
          </ul>
        </div>
      )}
    </main>
  );
}
