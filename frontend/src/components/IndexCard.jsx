// A paper index card: the question sits in the header above the red line, and
// the answer is written on the ruled lines once revealed. `depth` draws card
// edges behind it, so the stack shows roughly how many cards are left.
export default function IndexCard({
  front,
  back,
  revealed,
  onToggle,
  depth = 0,
  hint = "Tap or press space to show the answer",
}) {
  return (
    <div className={`card-stack depth-${Math.max(0, Math.min(depth, 2))}`}>
      <button
        type="button"
        className={`index-card${revealed ? " is-revealed" : ""}`}
        onClick={onToggle}
        aria-expanded={revealed}
      >
        <span className="ic-front">{front}</span>
        <span className="ic-lines">
          {revealed ? (
            <span className="ic-back">{back}</span>
          ) : (
            <span className="ic-hint">{hint}</span>
          )}
        </span>
      </button>
    </div>
  );
}
