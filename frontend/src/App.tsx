import { FormEvent, useEffect, useMemo, useState } from "react";
import RecipesPanel from "./RecipesPanel";
import BrewDayPanel from "./brewDay/BrewDayPanel";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type PreferredUnits = "US" | "METRIC";
type VolumeUnit = "gal" | "L";
type View = "home" | "brewery" | "equipment" | "inventory" | "recipes" | "brewday";

type Brewery = {
  id: string;
  name: string;
  preferred_units: PreferredUnits;
  timezone: string;
  default_batch_size: string;
  default_batch_size_unit: VolumeUnit;
  default_brewhouse_efficiency: string;
};

type EquipmentSystemType =
  | "BIAB"
  | "ELECTRIC_ALL_IN_ONE"
  | "COOLER_MASH_TUN"
  | "TRADITIONAL_3_VESSEL"
  | "EXTRACT"
  | "PARTIAL_MASH"
  | "CUSTOM";

type Equipment = {
  id: string;
  name: string;
  system_type: EquipmentSystemType;
  target_batch_size: string;
  kettle_capacity: string;
  kettle_capacity_unit: VolumeUnit;
  mash_capacity: string | null;
  active: boolean;
};

type IngredientCategory =
  | "FERMENTABLE"
  | "HOP"
  | "YEAST"
  | "ADJUNCT"
  | "WATER_ADDITION"
  | "FINING"
  | "OTHER";

type InventoryRow = {
  ingredient_id: string;
  name: string;
  category: IngredientCategory;
  manufacturer: string | null;
  unit: string;
  quantity_available: string;
  freshness: string;
  storage_locations: string[];
  lot_count: number;
};

type Lot = {
  id: string;
  ingredient_id: string;
  quantity_on_hand: string;
  quantity_reserved: string;
  unit: string;
  storage_location: string | null;
};

const SYSTEM_TYPES: { value: EquipmentSystemType; label: string }[] = [
  { value: "BIAB", label: "BIAB" },
  { value: "ELECTRIC_ALL_IN_ONE", label: "Electric All-in-One" },
  { value: "COOLER_MASH_TUN", label: "Cooler Mash Tun" },
  { value: "TRADITIONAL_3_VESSEL", label: "Traditional 3-Vessel" },
  { value: "EXTRACT", label: "Extract" },
  { value: "PARTIAL_MASH", label: "Partial Mash" },
  { value: "CUSTOM", label: "Custom" },
];

const MASH_TYPES = new Set<EquipmentSystemType>([
  "BIAB",
  "ELECTRIC_ALL_IN_ONE",
  "COOLER_MASH_TUN",
  "TRADITIONAL_3_VESSEL",
  "PARTIAL_MASH",
  "CUSTOM",
]);

const CATEGORIES: { value: IngredientCategory; label: string }[] = [
  { value: "FERMENTABLE", label: "Fermentable" },
  { value: "HOP", label: "Hop" },
  { value: "YEAST", label: "Yeast" },
  { value: "ADJUNCT", label: "Adjunct" },
  { value: "WATER_ADDITION", label: "Water addition" },
  { value: "FINING", label: "Fining" },
  { value: "OTHER", label: "Other" },
];

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

function defaultUnitFor(category: IngredientCategory, preferred: PreferredUnits): string {
  if (category === "HOP") return preferred === "US" ? "oz" : "g";
  if (category === "YEAST") return "each";
  if (category === "WATER_ADDITION") return "g";
  return preferred === "US" ? "lb" : "kg";
}

export default function App() {
  const [view, setView] = useState<View>("home");
  const [brewSessionId, setBrewSessionId] = useState<string | null>(
    () => localStorage.getItem("brewingos.e2a6.activeBrewSessionId"),
  );
  const [brewery, setBrewery] = useState<Brewery | null>(null);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [inventoryMode, setInventoryMode] = useState<"list" | "add" | "action">("list");
  const [actionKind, setActionKind] = useState<"ADJUST" | "USE" | "DISCARD">("USE");
  const [selectedIngredientId, setSelectedIngredientId] = useState<string | null>(null);
  const [lots, setLots] = useState<Lot[]>([]);

  const [breweryForm, setBreweryForm] = useState({
    name: "",
    preferred_units: "US" as PreferredUnits,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    default_batch_size: "5",
    default_brewhouse_efficiency: "70",
  });

  const volumeUnit: VolumeUnit = breweryForm.preferred_units === "US" ? "gal" : "L";

  const [equipmentForm, setEquipmentForm] = useState({
    name: "",
    system_type: "BIAB" as EquipmentSystemType,
    target_batch_size: "5",
    kettle_capacity: "10",
    mash_capacity: "10",
    boil_off_rate: "",
    boil_off_rate_unit: "gal/hr",
    trub_loss: "",
    fermenter_loss: "",
    typical_brewhouse_efficiency: "",
    notes: "",
  });

  const [addForm, setAddForm] = useState({
    category: "HOP" as IngredientCategory,
    name: "",
    manufacturer: "",
    quantity: "",
    storage_location: "",
    alpha: "",
    fermentable_type: "BASE_MALT",
    color: "",
    potential: "",
    hop_type: "PELLET",
    yeast_type: "ALE",
    strain: "",
    attenuation_min: "",
    attenuation_max: "",
  });

  const [actionForm, setActionForm] = useState({
    lot_id: "",
    quantity: "",
    reason: "",
  });

  const needsMash = useMemo(
    () => MASH_TYPES.has(equipmentForm.system_type),
    [equipmentForm.system_type],
  );

  async function loadInventory(breweryId: string) {
    const invRes = await fetch(`${API_URL}/api/v1/breweries/${breweryId}/inventory`);
    if (!invRes.ok) throw new Error(await readError(invRes));
    setInventory(await invRes.json());
  }

  async function load() {
    setError(null);
    try {
      const breweryRes = await fetch(`${API_URL}/api/v1/brewery`);
      if (!breweryRes.ok) throw new Error(await readError(breweryRes));
      const breweryData = (await breweryRes.json()) as Brewery | null;
      setBrewery(breweryData);
      if (breweryData) {
        setBreweryForm({
          name: breweryData.name,
          preferred_units: breweryData.preferred_units,
          timezone: breweryData.timezone,
          default_batch_size: String(breweryData.default_batch_size),
          default_brewhouse_efficiency: String(breweryData.default_brewhouse_efficiency),
        });
        const eqRes = await fetch(
          `${API_URL}/api/v1/breweries/${breweryData.id}/equipment`,
        );
        if (!eqRes.ok) throw new Error(await readError(eqRes));
        setEquipment(await eqRes.json());
        await loadInventory(breweryData.id);
      } else {
        setEquipment([]);
        setInventory([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach API");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function saveBrewery(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const payload = {
      name: breweryForm.name,
      preferred_units: breweryForm.preferred_units,
      timezone: breweryForm.timezone,
      default_batch_size: breweryForm.default_batch_size,
      default_batch_size_unit: volumeUnit,
      default_brewhouse_efficiency: breweryForm.default_brewhouse_efficiency,
    };
    try {
      const res = await fetch(
        brewery ? `${API_URL}/api/v1/brewery/${brewery.id}` : `${API_URL}/api/v1/brewery`,
        {
          method: brewery ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (!res.ok) throw new Error(await readError(res));
      const saved = (await res.json()) as Brewery;
      setBrewery(saved);
      setView("equipment");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveEquipment(e: FormEvent) {
    e.preventDefault();
    if (!brewery) return;
    setBusy(true);
    setError(null);
    const unit = brewery.preferred_units === "US" ? "gal" : "L";
    const payload: Record<string, unknown> = {
      name: equipmentForm.name,
      system_type: equipmentForm.system_type,
      target_batch_size: equipmentForm.target_batch_size,
      target_batch_size_unit: unit,
      kettle_capacity: equipmentForm.kettle_capacity,
      kettle_capacity_unit: unit,
      active: true,
    };
    if (needsMash && equipmentForm.mash_capacity) {
      payload.mash_capacity = equipmentForm.mash_capacity;
      payload.mash_capacity_unit = unit;
    }
    if (showAdvanced) {
      if (equipmentForm.boil_off_rate) {
        payload.boil_off_rate = equipmentForm.boil_off_rate;
        payload.boil_off_rate_unit = equipmentForm.boil_off_rate_unit || `${unit}/hr`;
      }
      if (equipmentForm.trub_loss) {
        payload.trub_loss = equipmentForm.trub_loss;
        payload.trub_loss_unit = unit;
      }
      if (equipmentForm.fermenter_loss) {
        payload.fermenter_loss = equipmentForm.fermenter_loss;
        payload.fermenter_loss_unit = unit;
      }
      if (equipmentForm.typical_brewhouse_efficiency) {
        payload.typical_brewhouse_efficiency = equipmentForm.typical_brewhouse_efficiency;
      }
      if (equipmentForm.notes.trim()) payload.notes = equipmentForm.notes.trim();
    }
    try {
      const res = await fetch(`${API_URL}/api/v1/breweries/${brewery.id}/equipment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await readError(res));
      await load();
      setEquipmentForm((prev) => ({ ...prev, name: "" }));
      setView("home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function addInventory(e: FormEvent) {
    e.preventDefault();
    if (!brewery) return;
    setBusy(true);
    setError(null);
    const unit = defaultUnitFor(addForm.category, brewery.preferred_units);
    const createBody: Record<string, unknown> = {
      category: addForm.category,
      name: addForm.name,
      manufacturer: addForm.manufacturer || null,
      default_unit: unit,
    };
    if (addForm.category === "FERMENTABLE") {
      createBody.fermentable_profile = {
        fermentable_type: addForm.fermentable_type,
        color_lovibond: addForm.color || null,
        potential_sg: addForm.potential || null,
      };
    }
    if (addForm.category === "HOP") {
      createBody.hop_profile = {
        hop_type: addForm.hop_type,
        default_alpha_acid: addForm.alpha || null,
      };
    }
    if (addForm.category === "YEAST") {
      createBody.yeast_profile = {
        yeast_type: addForm.yeast_type,
        strain: addForm.strain || null,
        attenuation_min: addForm.attenuation_min || null,
        attenuation_max: addForm.attenuation_max || null,
      };
    }
    try {
      const createRes = await fetch(
        `${API_URL}/api/v1/breweries/${brewery.id}/ingredients`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(createBody),
        },
      );
      if (!createRes.ok) throw new Error(await readError(createRes));
      const ingredient = await createRes.json();
      const receiveRes = await fetch(
        `${API_URL}/api/v1/breweries/${brewery.id}/inventory/receive`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ingredient_id: ingredient.id,
            quantity: addForm.quantity,
            unit,
            storage_location: addForm.storage_location || null,
            actual_alpha_acid: addForm.category === "HOP" && addForm.alpha ? addForm.alpha : null,
            reason: "Initial receipt",
          }),
        },
      );
      if (!receiveRes.ok) throw new Error(await readError(receiveRes));
      await loadInventory(brewery.id);
      setInventoryMode("list");
      setAddForm((prev) => ({ ...prev, name: "", quantity: "", storage_location: "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setBusy(false);
    }
  }

  async function openAction(kind: "ADJUST" | "USE" | "DISCARD", ingredientId: string) {
    if (!brewery) return;
    setError(null);
    setActionKind(kind);
    setSelectedIngredientId(ingredientId);
    setActionForm({ lot_id: "", quantity: "", reason: kind === "USE" ? "Used in brew prep" : "" });
    try {
      const res = await fetch(
        `${API_URL}/api/v1/breweries/${brewery.id}/ingredients/${ingredientId}/lots`,
      );
      if (!res.ok) throw new Error(await readError(res));
      const lotRows = (await res.json()) as Lot[];
      setLots(lotRows);
      if (lotRows[0]) setActionForm((prev) => ({ ...prev, lot_id: lotRows[0].id }));
      setInventoryMode("action");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load lots");
    }
  }

  async function submitAction(e: FormEvent) {
    e.preventDefault();
    if (!brewery) return;
    setBusy(true);
    setError(null);
    const endpoints = {
      ADJUST: "/api/v1/inventory/adjust",
      USE: "/api/v1/inventory/use",
      DISCARD: "/api/v1/inventory/discard",
    } as const;
    const body =
      actionKind === "ADJUST"
        ? {
            lot_id: actionForm.lot_id,
            quantity: actionForm.quantity,
            reason: actionForm.reason,
          }
        : actionKind === "DISCARD"
          ? {
              lot_id: actionForm.lot_id,
              quantity: actionForm.quantity,
              reason: actionForm.reason,
            }
          : {
              lot_id: actionForm.lot_id,
              quantity: actionForm.quantity,
              reason: actionForm.reason || null,
            };
    try {
      const res = await fetch(`${API_URL}${endpoints[actionKind]}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await readError(res));
      await loadInventory(brewery.id);
      setInventoryMode("list");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <header className="brand">
        <p className="eyebrow">Epic 1 · Increment 7</p>
        <h1>BrewingOS</h1>
        <p className="lede">
          Design → predict → explain → ready to brew. Epic 1 foundation complete for review.
        </p>
      </header>

      <nav className="nav" aria-label="Primary">
        <button type="button" className={view === "home" ? "active" : ""} onClick={() => setView("home")}>
          Home
        </button>
        <button type="button" className={view === "brewery" ? "active" : ""} onClick={() => setView("brewery")}>
          Brewery
        </button>
        <button
          type="button"
          className={view === "equipment" ? "active" : ""}
          onClick={() => setView("equipment")}
          disabled={!brewery}
        >
          Equipment
        </button>
        <button
          type="button"
          className={view === "inventory" ? "active" : ""}
          onClick={() => {
            setInventoryMode("list");
            setView("inventory");
          }}
          disabled={!brewery}
        >
          Inventory
        </button>
        <button
          type="button"
          className={view === "recipes" ? "active" : ""}
          onClick={() => setView("recipes")}
          disabled={!brewery}
        >
          Recipes
        </button>
        <button
          type="button"
          className={view === "brewday" ? "active" : ""}
          onClick={() => setView("brewday")}
          disabled={!brewery}
        >
          Brew Day
        </button>
      </nav>

      {error && <div className="alert">{error}</div>}

      {view === "home" && (
        <section className="panel">
          {!brewery ? (
            <>
              <h2>Get started</h2>
              <p className="muted">Set up your brewery name, units, and default batch size.</p>
              <button type="button" className="primary" onClick={() => setView("brewery")}>
                Set up brewery
              </button>
            </>
          ) : (
            <>
              <h2>{brewery.name}</h2>
              <dl className="facts">
                <div>
                  <dt>Units</dt>
                  <dd>{brewery.preferred_units}</dd>
                </div>
                <div>
                  <dt>Batch size</dt>
                  <dd>
                    {brewery.default_batch_size} {brewery.default_batch_size_unit}
                  </dd>
                </div>
                <div>
                  <dt>Efficiency</dt>
                  <dd>{brewery.default_brewhouse_efficiency}%</dd>
                </div>
                <div>
                  <dt>Inventory items</dt>
                  <dd>{inventory.length}</dd>
                </div>
              </dl>
              <h3 className="subhead">Equipment profiles</h3>
              {equipment.length === 0 ? (
                <p className="muted">No equipment yet.</p>
              ) : (
                <ul className="list">
                  {equipment.map((item) => (
                    <li key={item.id}>
                      <strong>{item.name}</strong>
                      <span>
                        {item.system_type.replaceAll("_", " ")} · kettle {item.kettle_capacity}{" "}
                        {item.kettle_capacity_unit}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="actions">
                <button type="button" className="primary" onClick={() => setView("recipes")}>
                  Open recipes
                </button>
                <button type="button" className="ghost" onClick={() => setView("inventory")}>
                  Open inventory
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {view === "brewery" && (
        <section className="panel">
          <h2>{brewery ? "Edit brewery" : "Brewery setup"}</h2>
          <form className="form" onSubmit={saveBrewery}>
            <label>
              Brewery name
              <input
                required
                value={breweryForm.name}
                onChange={(e) => setBreweryForm({ ...breweryForm, name: e.target.value })}
              />
            </label>
            <label>
              Preferred units
              <select
                value={breweryForm.preferred_units}
                onChange={(e) =>
                  setBreweryForm({
                    ...breweryForm,
                    preferred_units: e.target.value as PreferredUnits,
                    default_batch_size:
                      e.target.value === "US"
                        ? "5"
                        : breweryForm.default_batch_size === "5"
                          ? "19"
                          : breweryForm.default_batch_size,
                  })
                }
              >
                <option value="US">US</option>
                <option value="METRIC">Metric</option>
              </select>
            </label>
            <label>
              Typical batch size ({volumeUnit})
              <input
                required
                inputMode="decimal"
                value={breweryForm.default_batch_size}
                onChange={(e) =>
                  setBreweryForm({ ...breweryForm, default_batch_size: e.target.value })
                }
              />
            </label>
            <label>
              Timezone
              <input
                required
                value={breweryForm.timezone}
                onChange={(e) => setBreweryForm({ ...breweryForm, timezone: e.target.value })}
              />
            </label>
            <label>
              Default brewhouse efficiency (%)
              <input
                required
                inputMode="decimal"
                value={breweryForm.default_brewhouse_efficiency}
                onChange={(e) =>
                  setBreweryForm({
                    ...breweryForm,
                    default_brewhouse_efficiency: e.target.value,
                  })
                }
              />
            </label>
            <div className="actions">
              <button type="submit" className="primary" disabled={busy}>
                {busy ? "Saving…" : "Save & continue"}
              </button>
              <button type="button" className="ghost" onClick={() => setView("home")}>
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {view === "equipment" && brewery && (
        <section className="panel">
          <h2>Equipment profile</h2>
          <p className="muted">
            Start with the basics. Open advanced fields only if you track losses and boil-off.
          </p>
          <form className="form" onSubmit={saveEquipment}>
            <label>
              Profile name
              <input
                required
                value={equipmentForm.name}
                onChange={(e) => setEquipmentForm({ ...equipmentForm, name: e.target.value })}
              />
            </label>
            <label>
              System type
              <select
                value={equipmentForm.system_type}
                onChange={(e) =>
                  setEquipmentForm({
                    ...equipmentForm,
                    system_type: e.target.value as EquipmentSystemType,
                  })
                }
              >
                {SYSTEM_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Target batch size ({volumeUnit})
              <input
                required
                inputMode="decimal"
                value={equipmentForm.target_batch_size}
                onChange={(e) =>
                  setEquipmentForm({ ...equipmentForm, target_batch_size: e.target.value })
                }
              />
            </label>
            <label>
              Kettle capacity ({volumeUnit})
              <input
                required
                inputMode="decimal"
                value={equipmentForm.kettle_capacity}
                onChange={(e) =>
                  setEquipmentForm({ ...equipmentForm, kettle_capacity: e.target.value })
                }
              />
            </label>
            {needsMash && (
              <label>
                Mash capacity ({volumeUnit})
                <input
                  inputMode="decimal"
                  value={equipmentForm.mash_capacity}
                  onChange={(e) =>
                    setEquipmentForm({ ...equipmentForm, mash_capacity: e.target.value })
                  }
                />
              </label>
            )}
            <button
              type="button"
              className="ghost disclosure"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? "Hide advanced" : "Show advanced performance & losses"}
            </button>
            {showAdvanced && (
              <div className="advanced">
                <label>
                  Boil-off rate
                  <input
                    inputMode="decimal"
                    value={equipmentForm.boil_off_rate}
                    onChange={(e) =>
                      setEquipmentForm({ ...equipmentForm, boil_off_rate: e.target.value })
                    }
                  />
                </label>
                <label>
                  Trub loss ({volumeUnit})
                  <input
                    inputMode="decimal"
                    value={equipmentForm.trub_loss}
                    onChange={(e) =>
                      setEquipmentForm({ ...equipmentForm, trub_loss: e.target.value })
                    }
                  />
                </label>
                <label>
                  Fermenter loss ({volumeUnit})
                  <input
                    inputMode="decimal"
                    value={equipmentForm.fermenter_loss}
                    onChange={(e) =>
                      setEquipmentForm({ ...equipmentForm, fermenter_loss: e.target.value })
                    }
                  />
                </label>
                <label>
                  Typical brewhouse efficiency (%)
                  <input
                    inputMode="decimal"
                    value={equipmentForm.typical_brewhouse_efficiency}
                    onChange={(e) =>
                      setEquipmentForm({
                        ...equipmentForm,
                        typical_brewhouse_efficiency: e.target.value,
                      })
                    }
                  />
                </label>
              </div>
            )}
            <div className="actions">
              <button type="submit" className="primary" disabled={busy}>
                {busy ? "Saving…" : "Save equipment"}
              </button>
              <button type="button" className="ghost" onClick={() => setView("home")}>
                Done
              </button>
            </div>
          </form>
        </section>
      )}

      {view === "inventory" && brewery && (
        <section className="panel">
          <h2>Inventory</h2>
          {inventoryMode === "list" && (
            <>
              <p className="muted">What you have on hand. Lot details stay optional until you need them.</p>
              <div className="actions">
                <button type="button" className="primary" onClick={() => setInventoryMode("add")}>
                  Add
                </button>
              </div>
              {inventory.length === 0 ? (
                <p className="muted">No inventory yet. Add your first ingredient lot.</p>
              ) : (
                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>Ingredient</th>
                        <th>Available</th>
                        <th>Freshness</th>
                        <th>Location</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {inventory.map((row) => (
                        <tr key={row.ingredient_id}>
                          <td>
                            <strong>{row.name}</strong>
                            <span className="row-meta">
                              {row.category.replaceAll("_", " ").toLowerCase()}
                              {row.manufacturer ? ` · ${row.manufacturer}` : ""}
                            </span>
                          </td>
                          <td>
                            {row.quantity_available} {row.unit}
                          </td>
                          <td>{row.freshness}</td>
                          <td>{row.storage_locations.join(", ") || "—"}</td>
                          <td className="row-actions">
                            <button type="button" className="ghost" onClick={() => void openAction("ADJUST", row.ingredient_id)}>
                              Adjust
                            </button>
                            <button type="button" className="ghost" onClick={() => void openAction("USE", row.ingredient_id)}>
                              Use
                            </button>
                            <button type="button" className="ghost" onClick={() => void openAction("DISCARD", row.ingredient_id)}>
                              Discard
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {inventoryMode === "add" && (
            <>
              <p className="muted">Create an ingredient and receive stock in one step.</p>
              <form className="form" onSubmit={addInventory}>
                <label>
                  Category
                  <select
                    value={addForm.category}
                    onChange={(e) =>
                      setAddForm({ ...addForm, category: e.target.value as IngredientCategory })
                    }
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Name
                  <input
                    required
                    value={addForm.name}
                    onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                  />
                </label>
                <label>
                  Manufacturer
                  <input
                    value={addForm.manufacturer}
                    onChange={(e) => setAddForm({ ...addForm, manufacturer: e.target.value })}
                  />
                </label>
                <label>
                  Quantity ({defaultUnitFor(addForm.category, brewery.preferred_units)})
                  <input
                    required
                    inputMode="decimal"
                    value={addForm.quantity}
                    onChange={(e) => setAddForm({ ...addForm, quantity: e.target.value })}
                  />
                </label>
                <label>
                  Storage location
                  <input
                    value={addForm.storage_location}
                    onChange={(e) => setAddForm({ ...addForm, storage_location: e.target.value })}
                  />
                </label>
                {addForm.category === "FERMENTABLE" && (
                  <>
                    <label>
                      Fermentable type
                      <select
                        value={addForm.fermentable_type}
                        onChange={(e) =>
                          setAddForm({ ...addForm, fermentable_type: e.target.value })
                        }
                      >
                        <option value="BASE_MALT">Base malt</option>
                        <option value="SPECIALTY_MALT">Specialty malt</option>
                        <option value="EXTRACT">Extract</option>
                        <option value="SUGAR">Sugar</option>
                        <option value="ADJUNCT_GRAIN">Adjunct grain</option>
                        <option value="OTHER">Other</option>
                      </select>
                    </label>
                    <label>
                      Color (°L)
                      <input
                        inputMode="decimal"
                        value={addForm.color}
                        onChange={(e) => setAddForm({ ...addForm, color: e.target.value })}
                      />
                    </label>
                    <label>
                      Potential (SG)
                      <input
                        inputMode="decimal"
                        value={addForm.potential}
                        onChange={(e) => setAddForm({ ...addForm, potential: e.target.value })}
                      />
                    </label>
                  </>
                )}
                {addForm.category === "HOP" && (
                  <label>
                    Alpha acid % (lot)
                    <input
                      inputMode="decimal"
                      value={addForm.alpha}
                      onChange={(e) => setAddForm({ ...addForm, alpha: e.target.value })}
                    />
                  </label>
                )}
                {addForm.category === "YEAST" && (
                  <>
                    <label>
                      Strain
                      <input
                        value={addForm.strain}
                        onChange={(e) => setAddForm({ ...addForm, strain: e.target.value })}
                      />
                    </label>
                    <label>
                      Attenuation min %
                      <input
                        inputMode="decimal"
                        value={addForm.attenuation_min}
                        onChange={(e) =>
                          setAddForm({ ...addForm, attenuation_min: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      Attenuation max %
                      <input
                        inputMode="decimal"
                        value={addForm.attenuation_max}
                        onChange={(e) =>
                          setAddForm({ ...addForm, attenuation_max: e.target.value })
                        }
                      />
                    </label>
                  </>
                )}
                <div className="actions">
                  <button type="submit" className="primary" disabled={busy}>
                    {busy ? "Saving…" : "Add to inventory"}
                  </button>
                  <button type="button" className="ghost" onClick={() => setInventoryMode("list")}>
                    Cancel
                  </button>
                </div>
              </form>
            </>
          )}

          {inventoryMode === "action" && selectedIngredientId && (
            <>
              <p className="muted">
                {actionKind === "ADJUST" && "Adjustment quantity is signed (+ add / − remove)."}
                {actionKind === "USE" && "Use reduces available stock via a consumption transaction."}
                {actionKind === "DISCARD" && "Discard records waste — history is preserved."}
              </p>
              <form className="form" onSubmit={submitAction}>
                <label>
                  Lot
                  <select
                    required
                    value={actionForm.lot_id}
                    onChange={(e) => setActionForm({ ...actionForm, lot_id: e.target.value })}
                  >
                    {lots.map((lot) => (
                      <option key={lot.id} value={lot.id}>
                        {lot.quantity_on_hand} {lot.unit} on hand
                        {lot.storage_location ? ` · ${lot.storage_location}` : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Quantity
                  <input
                    required
                    inputMode="decimal"
                    value={actionForm.quantity}
                    onChange={(e) => setActionForm({ ...actionForm, quantity: e.target.value })}
                  />
                </label>
                <label>
                  Reason
                  <input
                    required={actionKind !== "USE"}
                    value={actionForm.reason}
                    onChange={(e) => setActionForm({ ...actionForm, reason: e.target.value })}
                  />
                </label>
                <div className="actions">
                  <button type="submit" className="primary" disabled={busy}>
                    {busy ? "Saving…" : "Confirm"}
                  </button>
                  <button type="button" className="ghost" onClick={() => setInventoryMode("list")}>
                    Cancel
                  </button>
                </div>
              </form>
            </>
          )}
        </section>
      )}

      {view === "recipes" && brewery && (
        <RecipesPanel
          breweryId={brewery.id}
          preferredUnits={brewery.preferred_units}
          equipment={equipment.map((e) => ({ id: e.id, name: e.name }))}
          onError={setError}
          onBrewSessionReady={(sessionId) => {
            setBrewSessionId(sessionId);
            setView("brewday");
          }}
        />
      )}

      {view === "brewday" && brewery && (
        <BrewDayPanel
          breweryId={brewery.id}
          initialSessionId={brewSessionId}
          onError={setError}
        />
      )}
    </div>
  );
}
