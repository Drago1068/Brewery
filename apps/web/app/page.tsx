"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";

type Recipe = {
  id: string;
  name: string;
  version_id: string;
  version_number: number;
  target_mash_temperature: string;
  target_mash_ph: string;
  target_mash_gravity: string;
  planned_mash_duration_minutes: number;
};

export default function Dashboard() {
  const router = useRouter();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [activeId, setActiveId] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<Recipe[]>("/recipes"), apiFetch<{ id: string } | null>("/brew-sessions/active")])
      .then(([items, active]) => {
        setRecipes(items);
        setActiveId(active?.id);
      })
      .catch((reason) => {
        if (reason instanceof ApiError && reason.status === 401) router.replace("/login");
        else setError("Could not load the brewing workspace.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function createRecipe(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    try {
      const recipe = await apiFetch<Recipe>("/recipes", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setRecipes((current) => [recipe, ...current]);
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Recipe could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function startBrew(recipe: Recipe) {
    setBusy(true);
    setError("");
    try {
      const session = await apiFetch<{ id: string }>("/brew-sessions", {
        method: "POST",
        body: JSON.stringify({ recipe_version_id: recipe.version_id }),
      });
      await apiFetch(`/brew-sessions/${session.id}/start`, { method: "POST" });
      router.push(`/brew/${session.id}`);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Brew session could not start.");
      setBusy(false);
    }
  }

  if (loading) return <div className="loading" aria-live="polite">Loading your brewery…</div>;

  return (
    <div className="page-shell">
      <section className="hero">
        <div>
          <div className="eyebrow">Measured process · Better beer</div>
          <h1>Plan once. Brew with confidence.</h1>
          <p className="lede">Version the plan, capture the Mash, and keep every observation auditable.</p>
        </div>
        <div className="hero-stat"><strong>{recipes.length}</strong><span>recipe{recipes.length === 1 ? "" : "s"}</span></div>
      </section>

      {error && <div className="alert error" role="alert">{error}</div>}
      {activeId && (
        <section id="active-brew" className="active-banner">
          <div><span className="pulse" /> Active brew session ready to resume</div>
          <button className="secondary" onClick={() => router.push(`/brew/${activeId}`)}>Resume brew</button>
        </section>
      )}

      <div className="dashboard-grid">
        <section>
          <div className="section-heading"><div><div className="eyebrow">Recipe lineage</div><h2>Your recipes</h2></div></div>
          <div className="recipe-grid">
            {recipes.length === 0 && <div className="empty card">Create the first recipe version to begin.</div>}
            {recipes.map((recipe) => (
              <article className="card recipe-card" key={recipe.id}>
                <div className="version-pill">v{recipe.version_number}</div>
                <h3>{recipe.name}</h3>
                <dl>
                  <div><dt>Mash</dt><dd>{recipe.target_mash_temperature}°F</dd></div>
                  <div><dt>pH</dt><dd>{recipe.target_mash_ph}</dd></div>
                  <div><dt>Gravity</dt><dd>{recipe.target_mash_gravity}</dd></div>
                  <div><dt>Time</dt><dd>{recipe.planned_mash_duration_minutes} min</dd></div>
                </dl>
                <button className="primary" disabled={busy || Boolean(activeId)} onClick={() => startBrew(recipe)}>
                  {activeId ? "Finish active brew first" : "Start brew session"}
                </button>
              </article>
            ))}
          </div>
        </section>

        <aside className="card create-card">
          <div className="eyebrow">New versioned plan</div>
          <h2>Create recipe</h2>
          <form className="form-stack compact" onSubmit={createRecipe}>
            <label>Recipe name<input name="name" required maxLength={160} placeholder="House Pale Ale" /></label>
            <div className="field-pair">
              <label>Mash target (°F)<input name="target_mash_temperature" type="number" defaultValue="152" min="100" max="180" step="0.01" required /></label>
              <label>Duration (min)<input name="planned_mash_duration_minutes" type="number" defaultValue="60" min="1" max="240" required /></label>
            </div>
            <div className="field-pair">
              <label>Target pH<input name="target_mash_ph" type="number" defaultValue="5.30" min="0" max="14" step="0.01" required /></label>
              <label>pH tolerance<input name="mash_ph_tolerance" type="number" defaultValue="0.05" min="0" max="2" step="0.01" required /></label>
            </div>
            <div className="field-pair">
              <label>Target gravity<input name="target_mash_gravity" type="number" defaultValue="1.050" min="1" max="1.2" step="0.001" required /></label>
              <label>SG tolerance<input name="mash_gravity_tolerance" type="number" defaultValue="0.003" min="0" max="0.1" step="0.001" required /></label>
            </div>
            <button className="primary" disabled={busy}>{busy ? "Saving…" : "Create recipe v1"}</button>
          </form>
        </aside>
      </div>
    </div>
  );
}

