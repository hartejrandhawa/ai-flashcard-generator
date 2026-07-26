import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as pdfjsLib from "pdfjs-dist";
import pdfjsWorker from "pdfjs-dist/build/pdf.worker.mjs?url";
import { api } from "../api/client";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

const USER_ID_KEY = "flashcard_user_id";

function getOrCreateUserId() {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = `user_${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

async function extractPdfText(file) {
  const buffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
  let text = "";
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    text += content.items.map((item) => item.str).join(" ") + "\n";
  }
  return text;
}

export default function Home() {
  const [userId] = useState(getOrCreateUserId);
  const [decks, setDecks] = useState([]);
  const [deckName, setDeckName] = useState("");
  const [notesText, setNotesText] = useState("");
  const [fileName, setFileName] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadDecks();
  }, []);

  async function loadDecks() {
    try {
      const res = await api.listDecks(userId);
      setDecks(res.decks);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setFileName(file.name);
    setError(null);

    try {
      if (file.type === "application/pdf") {
        const text = await extractPdfText(file);
        setNotesText(text);
      } else {
        const text = await file.text();
        setNotesText(text);
      }
    } catch (err) {
      setError(`Couldn't read ${file.name}: ${err.message}`);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.createDeck(userId, deckName, notesText);
      setDeckName("");
      setNotesText("");
      setFileName(null);
      loadDecks();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Flashcard Generator</h1>
      </header>

      <form className="card create-form" onSubmit={handleCreate}>
        <h2>New deck</h2>
        <input
          placeholder="Deck name (e.g. Biology Chapter 4)"
          value={deckName}
          onChange={(e) => setDeckName(e.target.value)}
          required
        />

        <label className="upload-zone">
          <input type="file" accept=".pdf,.txt" onChange={handleFileChange} hidden />
          {fileName ? <span className="file-name">{fileName}</span> : <span className="upload-hint">Upload a PDF or .txt file</span>}
        </label>

        <textarea
          placeholder="...or paste your notes directly here"
          value={notesText}
          onChange={(e) => setNotesText(e.target.value)}
          rows={8}
        />

        {error && <p className="error-text">{error}</p>}
        <button type="submit" disabled={loading || !notesText.trim()}>
          {loading ? "Generating flashcards..." : "Generate flashcards"}
        </button>
      </form>

      <div className="card">
        <h2>Your decks</h2>
        {decks.length === 0 ? (
          <p className="empty-state">No decks yet — create one above.</p>
        ) : (
          <div className="deck-list">
            {decks.map((d) => (
              <Link key={d.deck_id} to={`/quiz/${d.deck_id}`} className="deck-card">
                <h3>{d.deck_name}</h3>
                <p>Created {d.created_at}</p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
