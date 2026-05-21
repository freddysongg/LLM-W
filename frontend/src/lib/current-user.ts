export interface CurrentUser {
  readonly id: string;
  readonly name: string;
  readonly email: string;
  readonly initials: string;
  readonly avatarColor: string;
}

const MAX_INITIALS_CHARS = 2;
const AVATAR_HUE_DEGREES = 360;
const AVATAR_LIGHTNESS = 0.78;
const AVATAR_CHROMA = 0.14;

export function deriveInitials({ name }: { name: string }): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return "?";
  }
  const letters = words.slice(0, MAX_INITIALS_CHARS).map((word) => word[0] ?? "");
  return letters.join("").toUpperCase();
}

export function deriveAvatarColor({ id }: { id: string }): string {
  let hash = 0;
  for (let charIndex = 0; charIndex < id.length; charIndex += 1) {
    hash = (hash * 31 + id.charCodeAt(charIndex)) >>> 0;
  }
  const hue = hash % AVATAR_HUE_DEGREES;
  return `oklch(${AVATAR_LIGHTNESS} ${AVATAR_CHROMA} ${hue})`;
}
