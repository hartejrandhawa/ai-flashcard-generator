import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";

const RATINGS = [
  { label: "Again", quality: 1, key: "1", tone: "again" },
  { label: "Hard", quality: 3, key: "2", tone: "hard" },
  { label: "Good", quality: 4, key: "3", tone: "good" },
  { label: "Easy", quality: 5, key: "4", tone: "easy" },
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

  const advance = useCallback(
    (requeue) => {
      if (requeue) setQueue((q) => [...q, current]); // come back to it this session
      setFlipped(false);
      setIndex((i) => i + 1);
    },
    [current],
  );

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
        advance(quality === 1);
      } catch (err) {
        if (err.status === 409) {
          // Already reviewed elsewhere (another tab or device). Retrying would
          // schedule it twice, so treat it as done and move on.
          submitted.current.add(current.card_id);
          advance(false);
        } else {
          setActionError(err.message); // keep the card on screen so the rating can be retried
        }
      } finally {
        setBusy(false);
      }
    },
    [current, busy, advance],
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
          <h2>{reviewed > 0 ? "Session complete" : "Nothing due"}</h2>
          <p className="empty-state">
            {reviewed > 0
              ? `You reviewed ${reviewed} card${reviewed === 1 ? "" : "s"}. `
              : ""}
            Nothing else is due in this deck. Come back later.
          </p>
          <div className="deck-actions center">
            <Link to="/" className="btn btn-primary">
              Back to decks
            </Link>
            <Link to={`/deck/${deckId}`} className="btn btn-secondary">
              View cards
            </Link>
          </div>
        </div>
      ) : (
        <div className="card quiz-card">
          <div className="quiz-progress">
            <span>
              Card {index + 1} of {queue.length}
            </span>
            <div
              className="progress-track"
              role="progressbar"
              aria-label="Session progress"
              aria-valuemin={0}
              aria-valuemax={queue.length}
              aria-valuenow={index}
            >
              <div
                className="progress-fill"
                style={{ width: `${(index / queue.length) * 100}%` }}
              />
            </div>
          </div>

          <button
            type="button"
            className={`flashcard${flipped ? " is-flipped" : ""}`}
            onClick={() => setFlipped((f) => !f)}
            aria-label={
              flipped
                ? "Answer shown. Press to hide it."
                : "Question. Press to reveal the answer."
            }
          >
            <span className="flashcard-label">Question</span>
            <span className="flashcard-text">{current.front}</span>
            {flipped ? (
              <>
                <span className="flashcard-divider" aria-hidden="true" />
                <span className="flashcard-label">Answer</span>
                <span className="flashcard-text answer">{current.back}</span>
              </>
            ) : (
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
                  className={`rate-${r.tone}`}
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
