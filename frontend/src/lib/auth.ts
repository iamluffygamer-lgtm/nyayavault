"use client";

import type { User } from "@/types";

/**
 * Client-side session handling.
 *
 * KNOWN LIMITATION, stated plainly: the access token is kept in localStorage,
 * which is readable by any script running on the page, so a cross-site
 * scripting flaw would expose it. It is the pragmatic choice for a prototype
 * with a separately-hosted API, and the production fix is documented in
 * SECURITY.md — move to an httpOnly, SameSite=Strict, Secure cookie with a
 * CSRF token. Nothing else in this file pretends otherwise.
 *
 * The cached user object is a rendering convenience only. Every privileged
 * action is re-authorised by the backend against the database.
 */

const TOKEN_KEY = "nyayavault.token";
const USER_KEY = "nyayavault.user";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function getToken(): string | null {
  if (!isBrowser()) return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setSession(token: string, user: User): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
    window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* storage unavailable (private mode) — the session lives for this page only */
  }
}

export function getCachedUser(): User | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

export function isAuthenticated(): boolean {
  return Boolean(getToken());
}
