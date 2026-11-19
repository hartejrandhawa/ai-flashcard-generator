import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, Outlet } from "react-router-dom";
import {
  handleCallback,
  isConfigured,
  isLoggedIn,
  login,
  logout,
} from "./auth";
import IndexCard from "./components/IndexCard";
import Home from "./pages/Home";
import Deck from "./pages/Deck";
import Quiz from "./pages/Quiz";
import "./App.css";

function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark" aria-hidden="true" />
      Flashcard Generator
    </span>
  );
}

function Layout() {
  return (
    <>
      <nav className="topbar">
        <Link to="/" className="brand-link">
          <Brand />
        </Link>
        <button type="button" className="btn btn-quiet" onClick={logout}>
          Sign out
        </button>
      </nav>
      <Outlet />
    </>
  );
}

function Notice({ title, children }) {
  return (
    <div className="page page-narrow">
      <div className="sheet">
        <h2 className="sheet-title">{title}</h2>
        {children}
      </div>
    </div>
  );
}

function Welcome({ error }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <>
      <nav className="topbar">
        <Brand />
      </nav>
      <main className="page welcome">
        <div className="welcome-copy">
          <h1>Turn your notes into flashcards</h1>
          <p className="lead">
            Upload lecture notes or a PDF and Claude writes the cards. Spaced
            repetition then brings each card back just before you'd forget it.
          </p>
          {error && (
            <p className="error-text" role="alert">
              {error}
            </p>
          )}
          <button
            type="button"
            className="btn btn-primary btn-lg"
            onClick={login}
          >
            Sign in or create an account
          </button>
        </div>
        <div className="welcome-demo">
          <IndexCard
            front="Which organelle produces most of a cell's ATP?"
            back="The mitochondrion, through cellular respiration."
            revealed={revealed}
            onToggle={() => setRevealed((r) => !r)}
            depth={2}
            hint="Tap to see the answer"
          />
          <p className="demo-caption">A card generated from biology notes.</p>
        </div>
      </main>
    </>
  );
}

export default function App() {
  const [status, setStatus] = useState(
    isConfigured() ? "loading" : "unconfigured",
  );
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isConfigured()) return;
    // Finishes a sign-in if we were just redirected back with ?code=...
    handleCallback()
      .catch((err) => setError(err.message))
      .finally(() => setStatus(isLoggedIn() ? "in" : "out"));
  }, []);

  if (status === "unconfigured") {
    return (
      <Notice title="Sign-in isn't configured">
        <p className="empty-state">
          Copy <code>frontend/.env.example</code> to <code>frontend/.env</code>{" "}
          and fill in the values printed by <code>sam deploy</code> (
          <code>VITE_API_BASE</code>, <code>VITE_COGNITO_DOMAIN</code>,{" "}
          <code>VITE_COGNITO_CLIENT_ID</code>), then restart the dev server.
        </p>
      </Notice>
    );
  }
  if (status === "loading") return <Notice title="Signing you in..." />;
  if (status === "out") return <Welcome error={error} />;

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/deck/:deckId" element={<Deck />} />
          <Route path="/quiz/:deckId" element={<Quiz />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
