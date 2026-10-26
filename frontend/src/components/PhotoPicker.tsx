import { useRef, useState } from "react";

import type { Product } from "../types";

const ACCEPT = "image/png,image/jpeg,image/webp";

export interface PhotoPickerProps {
  product: Product;
  onUpload: (file: File) => void;
  onRemove: () => void;
  busy: boolean;
}

/**
 * The photo cell on an Inventory row: tap to pick an image, tap the × to remove
 * it. The server re-encodes and validates whatever is chosen, so this only has
 * to hint at the accepted types.
 */
export default function PhotoPicker({ product, onUpload, onRemove, busy }: PhotoPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [hovered, setHovered] = useState(false);

  const hasPhoto = Boolean(product.photo_url);
  const label = hasPhoto ? `Change the photo for ${product.name}` : `Add a photo for ${product.name}`;

  return (
    <div
      style={{ position: "relative", width: 44, height: 44 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          // Reset first so picking the same file twice still fires onChange.
          event.target.value = "";
          if (file) onUpload(file);
        }}
      />

      <button
        type="button"
        title={label}
        aria-label={label}
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        style={{
          width: 44,
          height: 44,
          padding: 0,
          borderRadius: 10,
          overflow: "hidden",
          border: hasPhoto ? "1px solid rgba(0,0,0,.12)" : "1px dashed rgba(0,0,0,.25)",
          background: hasPhoto ? "var(--surface)" : "var(--surface-sunk-alt)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: busy ? 0.5 : 1,
        }}
      >
        {hasPhoto ? (
          <img
            src={product.photo_url ?? undefined}
            alt=""
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        ) : (
          <span style={{ fontSize: 17, fontWeight: 700, color: "var(--ink-faint)" }}>+</span>
        )}
      </button>

      {hasPhoto && hovered && !busy && (
        <button
          type="button"
          title={`Remove the photo for ${product.name}`}
          aria-label={`Remove the photo for ${product.name}`}
          onClick={onRemove}
          style={{
            position: "absolute",
            top: -6,
            right: -6,
            width: 20,
            height: 20,
            borderRadius: "50%",
            border: "1px solid rgba(0,0,0,.12)",
            background: "var(--surface)",
            color: "var(--danger-ink)",
            fontSize: 12,
            fontWeight: 800,
            lineHeight: 1,
            padding: 0,
            boxShadow: "0 1px 3px rgba(0,0,0,.2)",
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}
