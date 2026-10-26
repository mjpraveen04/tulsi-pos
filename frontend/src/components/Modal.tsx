import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

export interface ModalProps {
  children: ReactNode;
  onClose?: () => void;
  labelledBy?: string;
}

/**
 * Backdrop + panel with the two behaviours a POS modal needs on a tablet:
 * Escape closes it, and focus starts inside so the on-screen keyboard lands on
 * the right field.
 */
export default function Modal({ children, onClose, labelledBy }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && onClose) onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    const focusable = panelRef.current?.querySelector<HTMLElement>(
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
