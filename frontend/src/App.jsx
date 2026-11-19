import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, Outlet } from "react-router-dom";
import {
  handleCallback,
  isConfigured,
  isLoggedIn,
  login,
  logout,
} from "./auth";
import Home from "./pages/Home";
import Deck from "./pages/Deck";
import Quiz from "./pages/Quiz";
import "./App.css";

function Layout() {
  return (
    <>
      <nav className="topbar">
        <Link to="/" className="brand">
          Flashcard Generator
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
    <div className="page">
      <div className="card centered">
        <h2>{title}</h2>
        {children}
      </div>
    </div>
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
  if (status === "out") {
    return (
      <Notice title="Welcome">
        <p className="empty-state">
          Sign in to create and study your flashcard decks.
        </p>
        {error && <p className="error-text">{error}</p>}
        <button type="button" className="btn btn-primary" onClick={login}>
          Sign in or create an account
        </button>
      </Notice>
    );
  }

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
