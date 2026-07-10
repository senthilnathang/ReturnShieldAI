// Lightweight inline SVG icon set (no external dependency).
const icon = (path) => ({
  props: { class: { type: String, default: 'h-5 w-5' } },
  template: `<svg :class="class" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`,
})

export const Store = icon('<path d="M3 9l1-5h16l1 5"/><path d="M4 9v11h16V9"/><path d="M9 13h6"/>')
export const ShoppingBag = icon('<path d="M6 2l-3 4v3a3 3 0 0 0 6 0V6"/><path d="M6 9a3 3 0 0 0 6 0V6"/><path d="M12 9a3 3 0 0 0 6 0V6"/><path d="M18 6l-1-4H7L6 6"/><path d="M5 9v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/>')
export const ShoppingCart = icon('<circle cx="9" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2 3h3l2.6 13.4a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.6L22 7H6"/>')
export const Package = icon('<path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M3.3 7L12 12l8.7-5"/><path d="M12 22V12"/>')
export const LogOut = icon('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>')
export const Plus = icon('<path d="M12 5v14M5 12h14"/>')
export const Minus = icon('<path d="M5 12h14"/>')
export const Trash = icon('<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>')
export const Check = icon('<path d="M20 6L9 17l-5-5"/>')
export const CheckCircle = icon('<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>')
export const ArrowLeft = icon('<path d="M19 12H5M12 19l-7-7 7-7"/>')
export const ArrowRight = icon('<path d="M5 12h14M12 5l7 7-7 7"/>')
export const Upload = icon('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>')
export const Shield = icon('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>')
export const Image = icon('<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5L5 21"/>')
export const Loader = icon('<path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/>')
export const AlertTriangle = icon('<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>')
