export interface CurrentUser {
  readonly id: string;
  readonly name: string;
  readonly email: string;
  readonly initials: string;
  readonly avatarColor: string;
}

export const CURRENT_USER: CurrentUser = {
  id: "freddy",
  name: "freddy",
  email: "freddy@llm-w.dev",
  initials: "FS",
  avatarColor: "oklch(0.78 0.14 300)",
};
