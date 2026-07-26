import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";

const RATINGS = [
  { label: "Again", quality: 1 },
  { label: "Hard", quality: 3 },
  { label: "Good", quality: 4 },
  { label: "Easy", quality: 5 },
];

export default function Quiz() {
  const { deckId } = useParams();
  const [cards, setCards] = useState([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadDueCards();
  }, [deckId]);

  async function loadDueCards() {
    setLoading(true);
    try {
      const res = await api.getDueCards(deckId);
      setCards(res.due_cards);
      setIndex(0);
      setFlipped(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRate(quality) {
    const card = cards[index];
    try {
      await api.submitReview(card.card_id, quality);
    } catch (err) {
      setError(err.message);
      return;
    }
    setFlipped(false);
    setIndex(index + 1);
  }

  if (loading) return <div className="page"><p>Loading...</p></div>;
  if (error) return <div className="page"><p className="error-text">{error}</p></div>;

  const current = cards[index];

  return (
    <div className="page">
      <Link to="/" className="back-link">&larr; All decks</Link>

      {!current ? (
        <div className="card quiz-done">
          <h2>All done for now</h2>
          <p className="empty-state">Nothing else due in this deck — come back later.</p>
        </div>
      ) : (
        <div className="card quiz-card">
          <p className="quiz-progress">{index + 1} of {cards.length} due</p>
          <div className="flashcard" onClick={() => setFlipped(!flipped)}>
            <p className="flashcard-label">{flipped ? "Answer" : "Question"}</p>
            <p className="flashcard-text">{flipped ? current.back : current.front}</p>
            {!flipped && <p className="flip-hint">Click to reveal answer</p>}
          </div>

          {flipped && (
            <div className="rating-row">
              {RATINGS.map((r) => (
                <button key={r.quality} onClick={() => handleRate(r.quality)}>
                  {r.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
