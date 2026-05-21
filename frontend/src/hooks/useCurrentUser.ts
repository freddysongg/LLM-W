import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { fetchCurrentUser } from "@/api/user";
import { deriveAvatarColor, deriveInitials, type CurrentUser } from "@/lib/current-user";

const CURRENT_USER_KEY = ["me"] as const;
const CURRENT_USER_STALE_TIME_MS = 60 * 60 * 1000;

export function useCurrentUser(): UseQueryResult<CurrentUser, Error> {
  return useQuery<CurrentUser, Error>({
    queryKey: CURRENT_USER_KEY,
    queryFn: async (): Promise<CurrentUser> => {
      const raw = await fetchCurrentUser();
      return {
        id: raw.id,
        name: raw.name,
        email: raw.email,
        initials: deriveInitials({ name: raw.name }),
        avatarColor: deriveAvatarColor({ id: raw.id }),
      };
    },
    staleTime: CURRENT_USER_STALE_TIME_MS,
  });
}
