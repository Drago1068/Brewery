"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      router.replace("/");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="centered-panel">
      <div className="eyebrow">Private workspace</div>
      <h1>Welcome back, brewer.</h1>
      <p className="lede">Sign in to plan a recipe and run the architecture-proving Mash workflow.</p>
      <form className="card form-stack" onSubmit={submit}>
        <label>
          Username
          <input name="username" autoComplete="username" required />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {error && <div className="alert error" role="alert">{error}</div>}
        <button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </section>
  );
}

