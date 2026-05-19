export interface CurrentUser {
  readonly id: string;
  readonly name: string;
  readonly email: string;
  readonly initials: string;
  readonly avatarColor: string;
}

// TODO(auth): replace this hard-coded identity with a real session lookup —
// remove when the backend ships an authenticated /api/me endpoint and a
// session hook wraps the app shell.
export const CURRENT_USER: CurrentUser = {
  id: "freddy",
  name: "freddy",
  email: "freddy@llm-w.dev",
  initials: "FS",
  avatarColor: "oklch(0.78 0.14 300)",
};
