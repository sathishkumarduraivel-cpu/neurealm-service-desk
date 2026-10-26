/**
 * Brand settings — change these to rename the product everywhere in the UI.
 * Text that mentions the default names is swapped automatically (see i18n/index.tsx).
 */
export const BRAND = {
  product: "Neurealm Service Desk",
  company: "Neurealm",
  ai: "Neurealm AI",
  website: "https://www.neurealm.com",
  signupDomain: "neurealm.com",
};
const DEFAULTS: [string, keyof typeof BRAND][] = [["Neurealm Service Desk", "product"], ["Neurealm AI", "ai"], ["Neurealm", "company"]];
/** Replace default brand names in a string with the configured ones. */
export const brandify = (s: string) => DEFAULTS.reduce((o, [d, k]) => (BRAND[k] === d ? o : o.split(d).join(BRAND[k])), s);
