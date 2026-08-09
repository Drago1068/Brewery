import { FormEvent, useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type RecipeSummary = {
  id: string;
  name: string;
  style: string | null;
  current_version_id: string | null;
  status: string;
};

type RecipeDetail = RecipeSummary & {
  description: string | null;
  current_version: {
    id: string;
    version_number: number;
    status: string;
    batch_size: string;
    batch_size_unit: string;
    brewhouse_efficiency: string | null;
    boil_time_minutes: number | null;
    mash_method: string | null;
    intent: {
      overall_objective: string | null;
      desired_aroma: string | null;
      desired_flavor: string | null;
      desired_bitterness: string | null;
      desired_body: string | null;
    } | null;
    fermentables: Array<{
      ingredient_name: string;
      amount: string;
      unit: string;
      color_lovibond: string | null;
      potential_sg: string | null;
    }>;
    hops: Array<{
      ingredient_name: string;
      amount: string;
      unit: string;
      alpha_acid: string | null;
      stage: string;
      time_minutes: number | null;
    }>;
    yeasts: Array<{
      ingredient_name: string;
      expected_attenuation: string | null;
    }>;
    mash_steps: Array<{
      step_name: string;
      target_temperature_c: string;
      duration_minutes: number;
    }>;
  } | null;
  versions: Array<{
    id: string;
    version_number: number;
    status: string;
    change_summary: string | null;
  }>;
};

type Equipment = { id: string; name: string };

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? "Invalid input").join("; ");
    }
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

type Props = {
  breweryId: string;
  preferredUnits: "US" | "METRIC";
  equipment: Equipment[];
  onError: (message: string | null) => void;
};

export default function RecipesPanel({
  breweryId,
  preferredUnits,
  equipment,
  onError,
}: Props) {
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [detail, setDetail] = useState<RecipeDetail | null>(null);
  const [mode, setMode] = useState<"list" | "create" | "edit">("list");
  const [calc, setCalc] = useState<{
    results: Record<
      string,
      {
        status: string;
        kind: string;
        value: string | null;
        unit: string | null;
        formula_key: string;
        explanation: string;
        missing_inputs?: string[];
      }
    >;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const batchUnit = preferredUnits === "US" ? "gal" : "L";
  const maltUnit = preferredUnits === "US" ? "lb" : "kg";
  const hopUnit = preferredUnits === "US" ? "oz" : "g";

  const [form, setForm] = useState({
    name: "",
    style: "",
    description: "",
    batch_size: preferredUnits === "US" ? "5" : "19",
    equipment_profile_id: "",
    brewhouse_efficiency: "70",
    boil_time_minutes: "60",
    mash_method: "SINGLE_INFUSION",
    overall_objective: "",
    desired_aroma: "",
    desired_flavor: "",
    desired_bitterness: "",
    desired_body: "",
    fermentable_name: "",
    fermentable_amount: "",
    fermentable_potential: "1.037",
    fermentable_color: "2",
    hop_name: "",
    hop_amount: "",
    hop_alpha: "",
    hop_stage: "BOIL",
    hop_time: "60",
    yeast_name: "",
    yeast_attenuation: "75",
    mash_temp_c: "67",
    mash_duration: "60",
    change_summary: "",
  });

  async function loadList() {
    const res = await fetch(`${API_URL}/api/v1/breweries/${breweryId}/recipes`);
    if (!res.ok) throw new Error(await readError(res));
    setRecipes(await res.json());
  }

  async function loadDetail(recipeId: string) {
    const res = await fetch(`${API_URL}/api/v1/recipes/${recipeId}`);
    if (!res.ok) throw new Error(await readError(res));
    const data = (await res.json()) as RecipeDetail;
    setDetail(data);
    return data;
  }

  useEffect(() => {
    void loadList().catch((err) =>
      onError(err instanceof Error ? err.message : "Unable to load recipes"),
    );
  }, [breweryId]);

  function buildVersionPayload() {
    return {
      batch_size: form.batch_size,
      batch_size_unit: batchUnit,
      equipment_profile_id: form.equipment_profile_id || null,
      brewhouse_efficiency: form.brewhouse_efficiency || null,
      boil_time_minutes: form.boil_time_minutes ? Number(form.boil_time_minutes) : null,
      mash_method: form.mash_method,
      change_summary: form.change_summary || null,
      intent: {
        overall_objective: form.overall_objective || null,
        desired_aroma: form.desired_aroma || null,
        desired_flavor: form.desired_flavor || null,
        desired_bitterness: form.desired_bitterness || null,
        desired_body: form.desired_body || null,
      },
      fermentables: form.fermentable_name
        ? [
            {
              ingredient_name: form.fermentable_name,
              amount: form.fermentable_amount,
              unit: maltUnit,
              potential_sg: form.fermentable_potential || null,
              color_lovibond: form.fermentable_color || null,
            },
          ]
        : [],
      hops: form.hop_name
        ? [
            {
              ingredient_name: form.hop_name,
              amount: form.hop_amount,
              unit: hopUnit,
              alpha_acid: form.hop_alpha || null,
              stage: form.hop_stage,
              time_minutes: form.hop_time ? Number(form.hop_time) : null,
            },
          ]
        : [],
      yeasts: form.yeast_name
        ? [
            {
              ingredient_name: form.yeast_name,
              expected_attenuation: form.yeast_attenuation || null,
            },
          ]
        : [],
      mash_steps: [
        {
          step_name: "Saccharification",
          target_temperature_c: form.mash_temp_c,
          duration_minutes: Number(form.mash_duration),
        },
      ],
      adjuncts: [],
      water_additions: [],
      targets: [],
    };
  }

  async function createRecipe(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    onError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/breweries/${breweryId}/recipes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          style: form.style || null,
          description: form.description || null,
          version: buildVersionPayload(),
        }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const created = (await res.json()) as RecipeDetail;
      await loadList();
      setDetail(created);
      setMode("edit");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft(e: FormEvent) {
    e.preventDefault();
    if (!detail?.current_version) return;
    setBusy(true);
    onError(null);
    try {
      const version = detail.current_version;
      if (version.status === "DRAFT") {
        const res = await fetch(`${API_URL}/api/v1/recipe-versions/${version.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildVersionPayload()),
        });
        if (!res.ok) throw new Error(await readError(res));
      } else {
        const res = await fetch(`${API_URL}/api/v1/recipes/${detail.id}/versions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            change_summary: form.change_summary || "Formulation update",
            version: buildVersionPayload(),
          }),
        });
        if (!res.ok) throw new Error(await readError(res));
      }
      await loadDetail(detail.id);
      await loadList();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function runCalculate() {
    if (!detail?.current_version) return;
    setBusy(true);
    onError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/recipe-versions/${detail.current_version.id}/calculate`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await readError(res));
      setCalc(await res.json());
    } catch (err) {
      onError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setBusy(false);
    }
  }

  async function activate() {
    if (!detail?.current_version) return;
    setBusy(true);
    onError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/recipe-versions/${detail.current_version.id}/activate`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await readError(res));
      await loadDetail(detail.id);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Activate failed");
    } finally {
      setBusy(false);
    }
  }

  async function lock() {
    if (!detail?.current_version) return;
    setBusy(true);
    onError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/recipe-versions/${detail.current_version.id}/lock`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await readError(res));
      await loadDetail(detail.id);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Lock failed");
    } finally {
      setBusy(false);
    }
  }

  async function cloneRecipe() {
    if (!detail) return;
    setBusy(true);
    onError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/recipes/${detail.id}/clone`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: `${detail.name} (copy)` }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const cloned = (await res.json()) as RecipeDetail;
      await loadList();
      setDetail(cloned);
      setMode("edit");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Clone failed");
    } finally {
      setBusy(false);
    }
  }

  async function openRecipe(id: string) {
    onError(null);
    try {
      const data = await loadDetail(id);
      const v = data.current_version;
      setForm((prev) => ({
        ...prev,
        name: data.name,
        style: data.style ?? "",
        description: data.description ?? "",
        batch_size: v ? String(v.batch_size) : prev.batch_size,
        equipment_profile_id: "",
        brewhouse_efficiency: v?.brewhouse_efficiency
          ? String(v.brewhouse_efficiency)
          : prev.brewhouse_efficiency,
        boil_time_minutes: v?.boil_time_minutes != null ? String(v.boil_time_minutes) : "60",
        mash_method: v?.mash_method ?? "SINGLE_INFUSION",
        overall_objective: v?.intent?.overall_objective ?? "",
        desired_aroma: v?.intent?.desired_aroma ?? "",
        desired_flavor: v?.intent?.desired_flavor ?? "",
        desired_bitterness: v?.intent?.desired_bitterness ?? "",
        desired_body: v?.intent?.desired_body ?? "",
        fermentable_name: v?.fermentables[0]?.ingredient_name ?? "",
        fermentable_amount: v?.fermentables[0] ? String(v.fermentables[0].amount) : "",
        fermentable_potential: v?.fermentables[0]?.potential_sg
          ? String(v.fermentables[0].potential_sg)
          : "1.037",
        fermentable_color: v?.fermentables[0]?.color_lovibond
          ? String(v.fermentables[0].color_lovibond)
          : "2",
        hop_name: v?.hops[0]?.ingredient_name ?? "",
        hop_amount: v?.hops[0] ? String(v.hops[0].amount) : "",
        hop_alpha: v?.hops[0]?.alpha_acid ? String(v.hops[0].alpha_acid) : "",
        hop_stage: v?.hops[0]?.stage ?? "BOIL",
        hop_time: v?.hops[0]?.time_minutes != null ? String(v.hops[0].time_minutes) : "60",
        yeast_name: v?.yeasts[0]?.ingredient_name ?? "",
        yeast_attenuation: v?.yeasts[0]?.expected_attenuation
          ? String(v.yeasts[0].expected_attenuation)
          : "75",
        mash_temp_c: v?.mash_steps[0]
          ? String(v.mash_steps[0].target_temperature_c)
          : "67",
        mash_duration: v?.mash_steps[0] ? String(v.mash_steps[0].duration_minutes) : "60",
        change_summary: "",
      }));
      setMode("edit");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unable to open recipe");
    }
  }

  const editor = (
    <form className="form wide" onSubmit={mode === "create" ? createRecipe : saveDraft}>
      <h3 className="subhead">Overview</h3>
      <label>
        Name
        <input
          required
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          disabled={mode === "edit"}
        />
      </label>
      <label>
        Style
        <input value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} />
      </label>
      <label>
        Description
        <textarea
          rows={2}
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </label>
      <label>
        Batch size ({batchUnit})
        <input
          required
          inputMode="decimal"
          value={form.batch_size}
          onChange={(e) => setForm({ ...form, batch_size: e.target.value })}
        />
      </label>
      <label>
        Equipment profile
        <select
          value={form.equipment_profile_id}
          onChange={(e) => setForm({ ...form, equipment_profile_id: e.target.value })}
        >
          <option value="">None</option>
          {equipment.map((eq) => (
            <option key={eq.id} value={eq.id}>
              {eq.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Brewhouse efficiency (%)
        <input
          inputMode="decimal"
          value={form.brewhouse_efficiency}
          onChange={(e) => setForm({ ...form, brewhouse_efficiency: e.target.value })}
        />
      </label>

      <h3 className="subhead">Intent</h3>
      <label>
        Overall objective
        <input
          value={form.overall_objective}
          onChange={(e) => setForm({ ...form, overall_objective: e.target.value })}
        />
      </label>
      <label>
        Desired aroma
        <input
          value={form.desired_aroma}
          onChange={(e) => setForm({ ...form, desired_aroma: e.target.value })}
        />
      </label>
      <label>
        Desired flavor
        <input
          value={form.desired_flavor}
          onChange={(e) => setForm({ ...form, desired_flavor: e.target.value })}
        />
      </label>
      <label>
        Desired bitterness
        <input
          value={form.desired_bitterness}
          onChange={(e) => setForm({ ...form, desired_bitterness: e.target.value })}
        />
      </label>
      <label>
        Desired body
        <input
          value={form.desired_body}
          onChange={(e) => setForm({ ...form, desired_body: e.target.value })}
        />
      </label>

      <h3 className="subhead">Fermentables</h3>
      <label>
        Ingredient
        <input
          value={form.fermentable_name}
          onChange={(e) => setForm({ ...form, fermentable_name: e.target.value })}
        />
      </label>
      <label>
        Amount ({maltUnit})
        <input
          inputMode="decimal"
          value={form.fermentable_amount}
          onChange={(e) => setForm({ ...form, fermentable_amount: e.target.value })}
        />
      </label>
      <label>
        Potential (SG)
        <input
          inputMode="decimal"
          value={form.fermentable_potential}
          onChange={(e) => setForm({ ...form, fermentable_potential: e.target.value })}
        />
      </label>
      <label>
        Color (°L)
        <input
          inputMode="decimal"
          value={form.fermentable_color}
          onChange={(e) => setForm({ ...form, fermentable_color: e.target.value })}
        />
      </label>

      <h3 className="subhead">Hops</h3>
      <label>
        Ingredient
        <input
          value={form.hop_name}
          onChange={(e) => setForm({ ...form, hop_name: e.target.value })}
        />
      </label>
      <label>
        Amount ({hopUnit})
        <input
          inputMode="decimal"
          value={form.hop_amount}
          onChange={(e) => setForm({ ...form, hop_amount: e.target.value })}
        />
      </label>
      <label>
        Alpha acid %
        <input
          inputMode="decimal"
          value={form.hop_alpha}
          onChange={(e) => setForm({ ...form, hop_alpha: e.target.value })}
        />
      </label>
      <label>
        Stage
        <select
          value={form.hop_stage}
          onChange={(e) => setForm({ ...form, hop_stage: e.target.value })}
        >
          <option value="MASH">Mash</option>
          <option value="FIRST_WORT">First wort</option>
          <option value="BOIL">Boil</option>
          <option value="WHIRLPOOL">Whirlpool</option>
          <option value="DRY_HOP">Dry hop</option>
        </select>
      </label>
      <label>
        Time (minutes)
        <input
          inputMode="numeric"
          value={form.hop_time}
          onChange={(e) => setForm({ ...form, hop_time: e.target.value })}
        />
      </label>

      <h3 className="subhead">Yeast</h3>
      <label>
        Yeast
        <input
          value={form.yeast_name}
          onChange={(e) => setForm({ ...form, yeast_name: e.target.value })}
        />
      </label>
      <label>
        Expected attenuation (%)
        <input
          inputMode="decimal"
          value={form.yeast_attenuation}
          onChange={(e) => setForm({ ...form, yeast_attenuation: e.target.value })}
        />
      </label>

      <h3 className="subhead">Mash</h3>
      <label>
        Target temperature (°C)
        <input
          inputMode="decimal"
          value={form.mash_temp_c}
          onChange={(e) => setForm({ ...form, mash_temp_c: e.target.value })}
        />
      </label>
      <label>
        Duration (minutes)
        <input
          inputMode="numeric"
          value={form.mash_duration}
          onChange={(e) => setForm({ ...form, mash_duration: e.target.value })}
        />
      </label>

      {mode === "edit" && detail?.current_version?.status !== "DRAFT" && (
        <label>
          Change summary (new version)
          <input
            value={form.change_summary}
            onChange={(e) => setForm({ ...form, change_summary: e.target.value })}
          />
        </label>
      )}

      <div className="actions">
        <button type="submit" className="primary" disabled={busy}>
          {busy
            ? "Saving…"
            : mode === "create"
              ? "Create recipe"
              : detail?.current_version?.status === "DRAFT"
                ? "Save draft"
                : "Save as new version"}
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => {
            setMode("list");
            setDetail(null);
          }}
        >
          Back
        </button>
      </div>
    </form>
  );

  return (
    <section className="panel">
      <h2>Recipes</h2>
      {mode === "list" && (
        <>
          <p className="muted">
            Formulate the beer. Drafts can be edited; meaningful changes to active versions create
            a new RecipeVersion.
          </p>
          <div className="actions">
            <button type="button" className="primary" onClick={() => setMode("create")}>
              New recipe
            </button>
          </div>
          {recipes.length === 0 ? (
            <p className="muted">No recipes yet.</p>
          ) : (
            <ul className="list">
              {recipes.map((r) => (
                <li key={r.id}>
                  <button type="button" className="ghost linkish" onClick={() => void openRecipe(r.id)}>
                    <strong>{r.name}</strong>
                    <span>{r.style || "Unstyled"} · {r.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {mode === "create" && editor}

      {mode === "edit" && detail && (
        <>
          <p className="muted">
            Version {detail.current_version?.version_number} · {detail.current_version?.status}
            {detail.versions.length > 1
              ? ` · ${detail.versions.length} versions in history`
              : ""}
          </p>
          <div className="actions">
            <button type="button" className="primary" onClick={() => void runCalculate()} disabled={busy}>
              Calculate
            </button>
            <button type="button" className="ghost" onClick={() => void activate()} disabled={busy}>
              Activate
            </button>
            <button type="button" className="ghost" onClick={() => void lock()} disabled={busy}>
              Lock
            </button>
            <button type="button" className="ghost" onClick={() => void cloneRecipe()} disabled={busy}>
              Clone
            </button>
          </div>
          {calc && (
            <div className="calc-panel">
              <h3 className="subhead">Predictions</h3>
              <p className="muted">ESTIMATED / CALCULATED values — not measured brew-day observations.</p>
              <ul className="list">
                {Object.entries(calc.results).map(([key, result]) => (
                  <li key={key}>
                    <strong>
                      {key.replaceAll("_", " ").toUpperCase()}
                      {result.value != null ? ` — ${result.value}${result.unit ? ` ${result.unit}` : ""}` : " — NOT AVAILABLE"}
                    </strong>
                    <span>
                      {result.kind} · {result.status} · {result.formula_key}
                    </span>
                    <span className="row-meta">{result.explanation}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {editor}
          {detail.versions.length > 0 && (
            <>
              <h3 className="subhead">Version history</h3>
              <ul className="list">
                {detail.versions.map((v) => (
                  <li key={v.id}>
                    <strong>v{v.version_number}</strong>
                    <span>
                      {v.status}
                      {v.change_summary ? ` · ${v.change_summary}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
