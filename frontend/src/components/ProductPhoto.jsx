import { useState } from "react";

/** Category tints, so a photo-less menu still reads at a glance. */
const TINTS = {
  Tiffin: "oklch(0.94 0.04 152)",
  Snacks: "oklch(0.94 0.05 70)",
  Beverages: "oklch(0.94 0.04 250)",
  Meals: "oklch(0.94 0.05 30)",
};

/**
 * Renders the product photo when there is one. Drop the handoff images into
 * `public/photos/` and they appear; until then each card falls back to a
 * category-tinted monogram rather than a broken-image icon.
 */
export default function ProductPhoto({ product }) {
  const [failed, setFailed] = useState(false);
  const showImage = product.photo_url && !failed;

  if (showImage) {
    return (
      <img
        src={product.photo_url}
        alt=""
        loading="lazy"
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <div
      className="photo-fallback"
      style={{ background: TINTS[product.category] || "var(--surface-sunk-alt)" }}
      aria-hidden="true"
    >
      {product.name.slice(0, 2)}
    </div>
  );
}
