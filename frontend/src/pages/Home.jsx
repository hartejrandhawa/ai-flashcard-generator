import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import {
  MAX_DECK_NAME_CHARS,
  MAX_FILE_BYTES,
  MAX_NOTES_CHARS,
} from "../lib/limits";
import { extractPdfText } from "../lib/pdf";

const POLL_MS = 3000;

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// Each deck is drawn as a small stack of index cards.
function DeckTile({ deck, onRemove }) {
  if (deck.status === "generating") {
    return (
      <article className="deck-tile is-generating">
        <h3>{deck.deck_name}</h3>
        <p className="status-line">
          <span className="spinner" aria-hidden="true" /> Claude is writing the
          cards. This takes up to a minute.
        </p>
      </article>
    );
  }

  if (deck.status === "failed") {
    return (
      <article className="deck-tile is-failed">
        <h3>{deck.deck_name}</h3>
        <p className="error-text">{deck.error || "Generation failed."}</p>
        <div className="deck-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => onRemove(deck)}
          >
            Remove
          </button>
        </div>
      </article>
    );
  }

  return (
    <article className="deck-tile">
      <h3>
        <Link to={`/deck/${deck.deck_id}`}>{deck.deck_name}</Link>
      </h3>
      <p className="deck-meta">
        {plural(deck.card_count, "card")}
        {deck.due_count > 0 ? (
          <mark>{deck.due_count} due</mark>
        ) : (
          <span>all caught up</span>
        )}
      </p>
      <div className="deck-actions">
        {deck.due_count > 0 && (
          <Link to={`/quiz/${deck.deck_id}`} className="btn btn-primary">
            Study
          </Link>
        )}
        <Link to={`/deck/${deck.deck_id}`} className="btn btn-secondary">
          View cards
        </Link>
      </div>
    </article>
  );
}

export default function Home() {
  const [decks, setDecks] = useState(null); // null until the first load finishes
  const [loadError, setLoadError] = useState(null);
  const [deckName, setDeckName] = useState("");
  const [notesText, setNotesText] = useState("");
  const [fileName, setFileName] = useState(null);
  const [reading, setReading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  // Decks started during this visit, so we can announce when they finish.
  const watched = useRef(new Map());

  const loadDecks = useCallback(async () => {
    try {
      const res = await api.listDecks();
      setDecks(res.decks);
      setLoadError(null);
      for (const deck of res.decks) {
        if (!watched.current.has(deck.deck_id) || deck.status === "generating")
          continue;
        watched.current.delete(deck.deck_id);
        if (deck.status === "ready")
          setNotice({
            deckId: deck.deck_id,
            name: deck.deck_name,
            count: deck.card_count,
          });
      }
    } catch (err) {
      setLoadError(err.message);
    }
  }, []);

  useEffect(() => {
    loadDecks();
  }, [loadDecks]);

  // Generation runs in the background on the server, so poll while any deck is in progress.
  const anyGenerating = decks?.some((d) => d.status === "generating") ?? false;
  useEffect(() => {
    if (!anyGenerating) return;
    const timer = setInterval(loadDecks, POLL_MS);
    return () => clearInterval(timer);
  }, [anyGenerating, loadDecks]);

  function handleFileChange(e) {
    const file = e.target.files[0];
    e.target.value = ""; // lets the same file be picked again later
    if (file) readFile(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) readFile(file);
  }

  async function readFile(file) {
    setError(null);

    const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
    const isText = file.type.startsWith("text/") || /\.txt$/i.test(file.name);
    if (!isPdf && !isText)
      return setError("Only PDF and .txt files are supported.");
    if (file.size > MAX_FILE_BYTES)
      return setError("That file is too large (20 MB maximum).");

    setReading(true);
    try {
      const text = isPdf ? await extractPdfText(file) : await file.text();
      if (!text.trim()) {
        setFileName(null);
        return setError(
          isPdf
            ? "No text found in that PDF. Scanned or image-only PDFs need OCR first."
            : "That file is empty.",
        );
      }
      setFileName(file.name);
      setNotesText(text);
      if (!deckName.trim())
        setDeckName(
          file.name.replace(/\.[^.]+$/, "").slice(0, MAX_DECK_NAME_CHARS),
        );
    } catch (err) {
      setError(`Couldn't read ${file.name}: ${err.message}`);
    } finally {
      setReading(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      const res = await api.createDeck(deckName.trim(), notesText);
      watched.current.set(res.deck_id, true);
      setDeckName("");
      setNotesText("");
      setFileName(null);
      await loadDecks();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemove(deck) {
    try {
      await api.deleteDeck(deck.deck_id);
      await loadDecks();
    } catch (err) {
      setLoadError(err.message);
    }
  }

  const overLimit = notesText.length > MAX_NOTES_CHARS;
  const canSubmit =
    !submitting &&
    !reading &&
    deckName.trim() &&
    notesText.trim() &&
    !overLimit;

  const totalDue = decks?.reduce((sum, d) => sum + (d.due_count || 0), 0) ?? 0;

  return (
    <main className="page home">
      {notice && (
        <div className="notice" role="status">
          <span>
            <strong>{notice.name}</strong> is ready with{" "}
            {plural(notice.count, "card")}.
          </span>
          <Link to={`/deck/${notice.deckId}`}>Check the cards</Link>
        </div>
      )}

      {/* Decks come first: studying is the everyday job, creating is occasional. */}
      <section className="decks-section" aria-labelledby="decks-heading">
        <header className="section-head">
          <h1 id="decks-heading">Your decks</h1>
          {decks && decks.length > 0 && (
            <p className="section-sub">
              {totalDue > 0 ? (
                <>
                  <mark>{plural(totalDue, "card")}</mark> due today
                </>
              ) : (
                "Nothing due today. New cards appear as soon as a deck is ready."
              )}
            </p>
          )}
        </header>

        {loadError && (
          <p className="error-text" role="alert">
            {loadError}{" "}
            <button type="button" className="link-button" onClick={loadDecks}>
              Retry
            </button>
          </p>
        )}
        {decks === null ? (
          !loadError && <p className="empty-state">Loading your decks...</p>
        ) : decks.length === 0 ? (
          <div className="empty-deck">
            <p>No decks yet.</p>
            <p className="hint">
              Paste your notes or upload a PDF in New deck to make your first
              one.
            </p>
          </div>
        ) : (
          <div className="deck-list">
            {decks.map((d) => (
              <DeckTile key={d.deck_id} deck={d} onRemove={handleRemove} />
            ))}
          </div>
        )}
      </section>

      <form className="sheet create-form" onSubmit={handleCreate}>
        <h2 className="sheet-title">New deck</h2>
        <label className="field">
          <span>Deck name</span>
          <input
            placeholder="Biology, chapter 4"
            value={deckName}
            maxLength={MAX_DECK_NAME_CHARS}
            onChange={(e) => setDeckName(e.target.value)}
            required
          />
        </label>

        <label
          className={`upload-zone${dragging ? " is-dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            onChange={handleFileChange}
            hidden
          />
          {reading ? (
            <span className="upload-hint">Reading file...</span>
          ) : fileName ? (
            <span className="file-name">{fileName}</span>
          ) : (
            <span className="upload-hint">
              <strong>Choose a PDF or .txt file</strong> or drop it here
            </span>
          )}
        </label>

        <label className="field">
          <span>Or paste your notes</span>
          <textarea
            value={notesText}
            onChange={(e) => setNotesText(e.target.value)}
            rows={9}
          />
        </label>
        <p className={overLimit ? "error-text" : "hint"}>
          {notesText.length.toLocaleString()} of{" "}
          {MAX_NOTES_CHARS.toLocaleString()} characters
          {overLimit &&
            ". That's too long: trim the notes or split them into several decks."}
        </p>

        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          className="btn btn-primary btn-lg btn-block"
          disabled={!canSubmit}
        >
          {submitting ? "Starting..." : "Generate flashcards"}
        </button>
        {!canSubmit && !submitting && !reading && !overLimit && (
          <p className="hint center">
            {!deckName.trim()
              ? "Add a deck name to continue."
              : "Add some notes to continue."}
          </p>
        )}
      </form>
    </main>
  );
}
