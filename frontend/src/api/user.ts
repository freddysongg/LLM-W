import type { ApiCurrentUser } from "@/types/user";
import { fetchApi } from "./client";

export async function fetchCurrentUser(): Promise<ApiCurrentUser> {
  return fetchApi<ApiCurrentUser>({ path: "/me" });
}
