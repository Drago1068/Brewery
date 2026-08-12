"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { DraftLine, Ingredient, displayEstimate, makeDraftLine } from "@/lib/designer";

type Equipment = { id: string; name: string };
type Location = { id: string; name: string };
type Availability = { ingredient_name: string; required: string; available: string; unit: string; status: string };
type Design = { version_id: string; version_number: number; name: string; batch_size_liters: string; calculations: Record<string, string>; availability: Availability[] };

export default function RecipeDesigner() {
  const router = useRouter();
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [design, setDesign] = useState<Design>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selected = useMemo(
    () => ingredients.find((item) => item.id === ingredientId),
    [ingredientId, ingredients],
  );

  async function refresh() {
    const [profiles, catalog, stores] = await Promise.all([
      apiFetch<Equipment[]>("/equipment-profiles"),
      apiFetch<Ingredient[]>("/ingredients"),
      apiFetch<Location[]>("/inventory/locations"),
    ]);
    setEquipment(profiles); setIngredients(catalog); setLocations(stores);
  }

  useEffect(() => {
    Promise.all([
      apiFetch<Equipment[]>("/equipment-profiles"),
      apiFetch<Ingredient[]>("/ingredients"),
      apiFetch<Location[]>("/inventory/locations"),
    ])
      .then(([profiles, catalog, stores]) => {
        setEquipment(profiles);
        setIngredients(catalog);
        setLocations(stores);
      })
      .catch((reason) => {
        if (reason instanceof ApiError && reason.status === 401) router.replace("/login");
        else setError("Could not load the Recipe Designer.");
      });
  }, [router]);

  async function save(event: FormEvent<HTMLFormElement>, path: string, payload: (form: FormData) => object) {
    event.preventDefault(); setBusy(true); setError("");
    const formElement = event.currentTarget;
    const body = payload(new FormData(formElement));
    try {
      await apiFetch(path, { method: "POST", body: JSON.stringify(body) });
      formElement.reset(); await refresh();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "The operation could not be saved.");
    } finally { setBusy(false); }
  }

  async function saveRecipe(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      setDesign(await apiFetch<Design>("/recipe-designs", { method: "POST", body: JSON.stringify({
        name: form.get("name"), equipment_profile_id: form.get("equipment_profile_id"),
        batch_size_liters: form.get("batch_size_liters"), ingredients: lines,
        style_name: form.get("style_name") || null,
        target_mash_temperature_c: form.get("target_mash_temperature_c"),
        planned_mash_duration_minutes: form.get("mash_duration_minutes"),
        boil_duration_minutes: form.get("boil_duration_minutes"),
        apparent_attenuation: form.get("apparent_attenuation"),
        target_carbonation_volumes: form.get("target_carbonation_volumes"),
        process_steps: [
          { step_type: "MASH", sequence: 1, name: "Saccharification", duration_minutes: form.get("mash_duration_minutes"), temperature_c: form.get("target_mash_temperature_c") },
          { step_type: "BOIL", sequence: 2, name: "Boil", duration_minutes: form.get("boil_duration_minutes") },
        ],
      }) }));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Recipe version could not be saved.");
    } finally { setBusy(false); }
  }

  async function clone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!design) return; setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      setDesign(await apiFetch<Design>(`/recipe-designs/${design.version_id}/clone`, {
        method: "POST", body: JSON.stringify({ target_batch_liters: form.get("target_batch_liters") }),
      }));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Recipe version could not be cloned.");
    } finally { setBusy(false); }
  }

  return <div className="page-shell designer-shell">
    <section className="hero compact-hero"><div><div className="eyebrow">Phase 2 · Brewing Core</div><h1>Recipe Designer</h1><p className="lede">Build from owned equipment, canonical ingredients, and auditable stock. Every saved version preserves its deterministic calculation inputs.</p></div></section>
    {error && <div className="alert error" role="alert">{error}</div>}
    <section className="setup-grid" aria-label="Brewing core setup">
      <form className="card form-stack compact" onSubmit={(event) => save(event, "/equipment-profiles", (form) => Object.fromEntries(form.entries()))}>
        <div className="eyebrow">1 · Equipment</div><h2>Equipment profile</h2>
        <label>Name<input name="name" required placeholder="Pilot System" /></label>
        <div className="field-pair"><label>Batch liters<input name="default_batch_liters" type="number" defaultValue="20" min="0.1" step="0.1" required /></label><label>Efficiency<input name="brewhouse_efficiency" type="number" defaultValue="0.75" min="0.01" max="1" step="0.01" required /></label></div>
        <label>Boil-off L/hour<input name="boil_off_liters_per_hour" type="number" defaultValue="3" min="0" step="0.1" required /></label>
        <button className="primary" disabled={busy}>Save equipment</button>
      </form>
      <form className="card form-stack compact" onSubmit={(event) => save(event, "/ingredients", (form) => {
        const category = String(form.get("category")); const value = form.get("calculation_value");
        const attributes = category === "FERMENTABLE" ? { potential_ppg: value, color_lovibond: form.get("color") } : category === "HOP" ? { alpha_acid_percent: value } : {};
        return { name: form.get("name"), category, canonical_unit: form.get("canonical_unit"), attributes };
      })}>
        <div className="eyebrow">2 · Catalog</div><h2>Add ingredient</h2>
        <label>Name<input name="name" required placeholder="Pale Malt" /></label>
        <div className="field-pair"><label>Category<select name="category" defaultValue="FERMENTABLE"><option>FERMENTABLE</option><option>HOP</option><option>YEAST</option><option>WATER_ADDITION</option><option>ADJUNCT</option><option>FINING</option><option>NUTRIENT</option><option>MISCELLANEOUS</option></select></label><label>Canonical unit<select name="canonical_unit" defaultValue="g"><option>g</option><option>L</option><option>each</option></select></label></div>
        <div className="field-pair"><label>Potential PPG / alpha %<input name="calculation_value" type="number" defaultValue="37" step="0.1" /></label><label>Color Lovibond<input name="color" type="number" defaultValue="2" step="0.1" /></label></div>
        <button className="primary" disabled={busy}>Add ingredient</button>
      </form>
      <div className="card inventory-setup">
        <form className="form-stack compact" onSubmit={(event) => save(event, "/inventory/locations", (form) => Object.fromEntries(form.entries()))}>
          <div className="eyebrow">3 · Ledger</div><h2>Inventory</h2><label>Location name<input name="name" required placeholder="Grain Room" /></label><button className="primary" disabled={busy}>Add location</button>
        </form>
        <form className="form-stack compact divider-top" onSubmit={(event) => save(event, "/ingredient-lots", (form) => ({
          ingredient_id: form.get("ingredient_id"), lot_code: form.get("lot_code"), received_quantity: form.get("received_quantity"),
          unit: ingredients.find((item) => item.id === form.get("ingredient_id"))?.canonical_unit,
          location_id: form.get("location_id"), hop_alpha_acid_percent: form.get("hop_alpha_acid_percent") || null,
        }))}>
          <label>Ingredient<select name="ingredient_id" required defaultValue=""><option value="" disabled>Select ingredient</option>{ingredients.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <div className="field-pair"><label>Lot code<input name="lot_code" required /></label><label>Quantity<input name="received_quantity" type="number" min="0.0001" step="0.0001" required /></label></div>
          <label>Location<select name="location_id" required defaultValue=""><option value="" disabled>Select location</option>{locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Hop lot alpha % (optional)<input name="hop_alpha_acid_percent" type="number" min="0" max="100" step="0.1" /></label><button className="primary" disabled={busy}>Receive inventory</button>
        </form>
      </div>
    </section>
    <section className="card designer-card">
      <div className="section-heading"><div><div className="eyebrow">4 · Formulation</div><h2>Build recipe version</h2></div><span className="version-pill">{lines.length} lines</span></div>
      <div className="line-builder"><label>Ingredient<select aria-label="Recipe ingredient" value={ingredientId} onChange={(event) => setIngredientId(event.target.value)}><option value="">Select ingredient</option>{ingredients.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Amount<input id="line-amount" type="number" min="0.0001" step="0.0001" defaultValue="1000" /></label><button type="button" className="secondary dark" disabled={!selected} onClick={() => { const amount = (document.getElementById("line-amount") as HTMLInputElement).value; if (selected) setLines((current) => [...current, makeDraftLine(selected, amount)]); }}>Add to recipe</button></div>
      <ul className="ingredient-lines">{lines.map((line, index) => { const item = ingredients.find((ingredient) => ingredient.id === line.ingredient_id); return <li key={`${line.ingredient_id}-${index}`}><span>{item?.name}</span><strong>{line.amount} {line.unit}</strong><small>{line.use_stage}{line.timing_minutes !== undefined ? ` · ${line.timing_minutes} min` : ""}</small><button type="button" aria-label={`Remove ${item?.name}`} onClick={() => setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))}>×</button></li>; })}</ul>
      <form className="design-form" onSubmit={saveRecipe}><label>Recipe name<input name="name" required placeholder="House Pale Ale" /></label><label>Style<input name="style_name" placeholder="American Pale Ale" /></label><label>Equipment<select name="equipment_profile_id" required defaultValue=""><option value="" disabled>Select equipment</option>{equipment.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Batch liters<input name="batch_size_liters" type="number" defaultValue="20" min="0.1" step="0.1" required /></label><label>Mash °C<input name="target_mash_temperature_c" type="number" defaultValue="66.67" min="0" max="100" step="0.01" required /></label><label>Mash minutes<input name="mash_duration_minutes" type="number" defaultValue="60" min="1" max="240" required /></label><label>Boil minutes<input name="boil_duration_minutes" type="number" defaultValue="60" min="0" max="360" required /></label><label>Attenuation<input name="apparent_attenuation" type="number" defaultValue="0.75" min="0" max="1" step="0.01" required /></label><label>CO₂ volumes<input name="target_carbonation_volumes" type="number" defaultValue="2.4" min="0" max="6" step="0.1" required /></label><button className="primary" disabled={busy || lines.length === 0}>Calculate and save version</button></form>
    </section>
    {design && <section className="card calculation-summary" aria-live="polite">
      <div className="section-heading"><div><div className="eyebrow">Persisted calculation snapshot</div><h2>{design.name} · v{design.version_number}</h2></div><span className="status active">Saved</span></div>
      <div className="metric-grid"><div><span>OG</span><strong>{displayEstimate(design.calculations.og, 3)}</strong></div><div><span>FG estimate</span><strong>{displayEstimate(design.calculations.fg_estimate, 3)}</strong></div><div><span>ABV estimate</span><strong>{displayEstimate(design.calculations.abv_percent_estimate, 1)}%</strong></div><div><span>IBU estimate</span><strong>{displayEstimate(design.calculations.ibu_estimate, 1)}</strong></div><div><span>Color</span><strong>{displayEstimate(design.calculations.color_srm_estimate, 1)} SRM</strong></div><div><span>Total liquor</span><strong>{displayEstimate(design.calculations.total_liquor_liters, 1)} L</strong></div></div>
      <h3>Inventory availability</h3><div className="availability-table">{design.availability.map((line) => <div key={line.ingredient_name}><strong>{line.ingredient_name}</strong><span>{line.required} {line.unit} required</span><span>{line.available} available</span><span className={`availability ${line.status.toLowerCase()}`}>{line.status}</span></div>)}</div>
      <form className="scale-form" onSubmit={clone}><label>Scale target liters<input name="target_batch_liters" type="number" defaultValue="10" min="0.1" step="0.1" required /></label><button className="primary" disabled={busy}>Clone as scaled new version</button></form>
    </section>}
  </div>;
}
