import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";
import IndexCard from "../components/IndexCard";

// `note` says what the rating means, so first-time users can pick honestly.
const RATINGS = [
  {
    label: "Again",
    note: "Didn't know it",
    quality: 1,
    key: "1",
    tone: "again",
  },
  { label: "Hard", note: "Got it, slowly", quality: 3, key: "2", tone: "hard" },
  { label: "Good", note: "Knew it", quality: 4, key: "3", tone: "good" },
  { label: "Easy", note: "Instantly", quality: 5, key: "4", tone: "easy" },
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
    <main className="page quiz">
      <Link to="/" className="back-link">
        &larr; All decks
      </Link>

      {!current ? (
        <div className="sheet done">
          <h1 className="sheet-title">
            {reviewed > 0 ? "Session complete" : "Nothing due right now"}
          </h1>
          <p className="lead">
            {reviewed > 0
              ? `You reviewed ${reviewed} card${reviewed === 1 ? "" : "s"}. `
              : ""}
            The next cards in this deck come due on later days.
          </p>
          <div className="deck-actions">
            <Link to="/" className="btn btn-primary">
              Back to decks
            </Link>
            <Link to={`/deck/${deckId}`} className="btn btn-secondary">
              View cards
            </Link>
          </div>
        </div>
      ) : (
        <>
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

          <IndexCard
            front={current.front}
            back={current.back}
            revealed={flipped}
            onToggle={() => setFlipped((f) => !f)}
            depth={queue.length - index - 1}
          />

          {actionError && (
            <p className="error-text" role="alert">
              {actionError}
            </p>
          )}

          {flipped ? (
            <div
              className="rating-row"
              role="group"
              aria-label="How well did you know it?"
            >
              {RATINGS.map((r) => (
                <button
                  key={r.quality}
                  type="button"
                  className={`rate rate-${r.tone}`}
                  onClick={() => rate(r.quality)}
                  disabled={busy}
                >
                  <span className="rate-label">
                    {r.label} <kbd>{r.key}</kbd>
                  </span>
                  <span className="rate-note">{r.note}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="hint center quiz-keys">
              Keys: <kbd>Space</kbd> shows the answer, then <kbd>1</kbd>–
              <kbd>4</kbd> rate it.
            </p>
          )}
        </>
      )}
    </main>
  );
}
