import { useEffect, useRef } from "react";

/**
 * Backdrop + panel with the two behaviours a POS modal needs on a tablet:
 * Escape closes it, and focus starts inside so the on-screen keyboard lands on
 * the right field.
 */
export default function Modal({ children, onClose, labelledBy }) {
  const panelRef = useRef(null);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape" && onClose) onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    const focusable = panelRef.current?.querySelector(
      "input, button:not([disabled])",
    );
    focusable?.focus();
  }, []);

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && onClose) onClose();
      }}
    >
      <div
        className="modal pop"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        ref={panelRef}
      >
        {children}
      </div>
    </div>
  );
}
