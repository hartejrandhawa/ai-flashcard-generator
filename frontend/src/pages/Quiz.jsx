import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";

const RATINGS = [
  { label: "Again", quality: 1, key: "1" },
  { label: "Hard", quality: 3, key: "2" },
  { label: "Good", quality: 4, key: "3" },
  { label: "Easy", quality: 5, key: "4" },
];

export default function Quiz() {
  const { deckId } = useParams();
  const [queue, setQueue] = useState([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [reviewed, setReviewed] = useState(0);
  // Cards whose schedule was already updated this session.
  const submitted = useRef(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await api.getDueCards(deckId);
      setQueue(res.due_cards);
      setIndex(0);
      setFlipped(false);
      setReviewed(0);
      submitted.current = new Set();
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  }, [deckId]);

  useEffect(() => {
    load();
  }, [load]);

  const current = queue[index];

  const rate = useCallback(
    async (quality) => {
      // `busy` stops a double-click from submitting the same card twice.
      if (!current || busy) return;
      setBusy(true);
      setActionError(null);
      try {
        // Only the first answer to a card updates its schedule. Seeing it again
        // after "Again" is practice and must not reschedule it a second time.
        if (!submitted.current.has(current.card_id)) {
          await api.submitReview(current.card_id, quality);
          submitted.current.add(current.card_id);
          setReviewed((n) => n + 1);
        }
        if (quality === 1) setQueue((q) => [...q, current]); // come back to it this session
        setFlipped(false);
        setIndex((i) => i + 1);
      } catch (err) {
        setActionError(err.message); // keep the card on screen so the rating can be retried
      } finally {
        setBusy(false);
      }
    },
    [current, busy],
  );

  // Keyboard: space/enter flips (when nothing is focused), 1-4 rate.
  useEffect(() => {
    function onKeyDown(e) {
      if (!current || e.metaKey || e.ctrlKey || e.altKey) return;
      if (
        (e.key === " " || e.key === "Enter") &&
        document.activeElement === document.body
      ) {
        e.preventDefault();
        setFlipped((f) => !f);
      } else if (flipped) {
        const rating = RATINGS.find((r) => r.key === e.key);
        if (rating) rate(rating.quality);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [current, flipped, rate]);

  if (loading)
    return (
      <div className="page">
        <p className="empty-state">Loading...</p>
      </div>
    );

  if (loadError) {
    return (
      <div className="page">
        <Link to="/" className="back-link">
          &larr; All decks
        </Link>
        <p className="error-text" role="alert">
          {loadError}{" "}
          <button type="button" className="link-button" onClick={load}>
            Retry
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="page">
      <Link to="/" className="back-link">
        &larr; All decks
      </Link>

      {!current ? (
        <div className="card centered">
          <h2>All done for now</h2>
          <p className="empty-state">
            {reviewed > 0
              ? `You reviewed ${reviewed} card${reviewed === 1 ? "" : "s"}. `
              : ""}
            Nothing else is due in this deck — come back later.
          </p>
          <button type="button" className="btn btn-secondary" onClick={load}>
            Check again
          </button>
        </div>
      ) : (
        <div className="card quiz-card">
          <p className="quiz-progress">
            Card {index + 1} of {queue.length}
          </p>
          <button
            type="button"
            className="flashcard"
            onClick={() => setFlipped((f) => !f)}
            aria-label={
              flipped
                ? "Answer. Press to show the question."
                : "Question. Press to reveal the answer."
            }
          >
            <span className="flashcard-label">
              {flipped ? "Answer" : "Question"}
            </span>
            <span className="flashcard-text">
              {flipped ? current.back : current.front}
            </span>
            {!flipped && (
              <span className="flip-hint">
                Click or press space to reveal the answer
              </span>
            )}
          </button>

          {actionError && (
            <p className="error-text" role="alert">
              {actionError}
            </p>
          )}

          {flipped && (
            <div className="rating-row">
              {RATINGS.map((r) => (
                <button
                  key={r.quality}
                  type="button"
                  onClick={() => rate(r.quality)}
                  disabled={busy}
                >
                  {r.label} <span className="key-hint">{r.key}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
