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

function DeckCard({ deck, onRemove }) {
  if (deck.status === "generating") {
    return (
      <div className="deck-card">
        <h3>{deck.deck_name}</h3>
        <p className="status-line">
          <span className="spinner" aria-hidden="true" /> Generating
          flashcards...
        </p>
      </div>
    );
  }

  if (deck.status === "failed") {
    return (
      <div className="deck-card deck-failed">
        <h3>{deck.deck_name}</h3>
        <p className="error-text">{deck.error || "Generation failed."}</p>
        <button
          type="button"
          className="btn btn-quiet"
          onClick={() => onRemove(deck)}
        >
          Remove
        </button>
      </div>
    );
  }

  return (
    <div className="deck-card">
      <h3>{deck.deck_name}</h3>
      <p>
        {deck.card_count} cards &middot; {deck.due_count} due
      </p>
      <div className="deck-actions">
        {deck.due_count > 0 ? (
          <Link to={`/quiz/${deck.deck_id}`} className="btn btn-primary">
            Study {deck.due_count}
          </Link>
        ) : (
          <span className="btn btn-disabled">Nothing due</span>
        )}
        <Link to={`/deck/${deck.deck_id}`} className="btn btn-secondary">
          Cards
        </Link>
      </div>
    </div>
  );
}

export default function Home() {
  const [decks, setDecks] = useState(null); // null until the first load finishes
  const [loadError, setLoadError] = useState(null);
  const [deckName, setDeckName] = useState("");
  const [notesText, setNotesText] = useState("");
  const [fileName, setFileName] = useState(null);
  const [reading, setReading] = useState(false);
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

  async function handleFileChange(e) {
    const file = e.target.files[0];
    e.target.value = ""; // lets the same file be picked again later
    if (!file) return;
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

  return (
    <div className="page">
      <form className="card create-form" onSubmit={handleCreate}>
        <h2>New deck</h2>
        <input
          placeholder="Deck name (e.g. Biology Chapter 4)"
          value={deckName}
          maxLength={MAX_DECK_NAME_CHARS}
          onChange={(e) => setDeckName(e.target.value)}
          required
        />

        <label className="upload-zone">
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
            <span className="upload-hint">Upload a PDF or .txt file</span>
          )}
        </label>

        <textarea
          placeholder="...or paste your notes directly here"
          value={notesText}
          onChange={(e) => setNotesText(e.target.value)}
          rows={8}
        />
        <p className={overLimit ? "error-text" : "hint"}>
          {notesText.length.toLocaleString()} /{" "}
          {MAX_NOTES_CHARS.toLocaleString()} characters
          {overLimit &&
            " - too long. Trim the notes or split them into several decks."}
        </p>

        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={!canSubmit}>
          {submitting ? "Starting..." : "Generate flashcards"}
        </button>
      </form>

      {notice && (
        <div className="notice" role="status">
          <span>
            <strong>{notice.name}</strong> is ready with {notice.count} cards.
          </span>
          <Link to={`/deck/${notice.deckId}`}>Review the cards</Link>
        </div>
      )}

      <div className="card">
        <h2>Your decks</h2>
        {loadError && (
          <p className="error-text" role="alert">
            {loadError}{" "}
            <button type="button" className="link-button" onClick={loadDecks}>
              Retry
            </button>
          </p>
        )}
        {decks === null ? (
          !loadError && <p className="empty-state">Loading...</p>
        ) : decks.length === 0 ? (
          <p className="empty-state">No decks yet — create one above.</p>
        ) : (
          <div className="deck-list">
            {decks.map((d) => (
              <DeckCard key={d.deck_id} deck={d} onRemove={handleRemove} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
