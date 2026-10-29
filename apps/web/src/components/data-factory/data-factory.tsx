"use client";

import { useRef, useState } from "react";
import { generateHouseholds } from "@/lib/data-factory-api";
import type { GenerationConfig, HouseholdDataset } from "@/types/data-factory";
import { GenerationForm } from "./generation-form";
import { DatasetPreview } from "./dataset-preview";
import { CustomDatasetBuilder } from "./custom-dataset-builder";
import { Button } from "@/components/ui/button";

export function DataFactory() {
  const [mode, setMode] = useState("households");
  const [dataset, setDataset] = useState<HouseholdDataset | null>(null);
  const [generation, setGeneration] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  async function generate(config: GenerationConfig) {
    if (inFlight.current) return;
    
    // Validate config parameters
    if (!config || typeof config !== 'object') {
      setError("Invalid configuration object");
      return;
    }
    if (typeof config.count !== 'number' || config.count < 1 || config.count > 1000) {
      setError("Count must be between 1 and 1000");
      return;
    }
    if (typeof config.seed !== 'number' || config.seed < 0) {
      setError("Seed must be a non-negative number");
      return;
    }
    
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await generateHouseholds(config);
      if (!result || !result.data) {
        throw new Error("Invalid response from API");
      }
      setDataset(result);
      setGeneration((value) => value + 1);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Generation failed. Please try again.");
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-sm leading-6 text-slate-500">
        <p>Generate realistic synthetic datasets for development, testing, and analytics.</p>
        <p className="mt-2 text-xs">All records are synthetic, with fictional sample barangays. Income categories are illustrative testing values, not official classifications.</p>
      </div>
      <div className="flex flex-wrap gap-2" aria-label="Dataset mode">
        <Button variant={mode === "households" ? "default" : "outline"} aria-pressed={mode === "households"} onClick={() => setMode("households")}>Household Dataset</Button>
        <Button variant={mode === "custom" ? "default" : "outline"} aria-pressed={mode === "custom"} onClick={() => setMode("custom")}>Custom Dataset</Button>
      </div>
      <div hidden={mode !== "households"} className="space-y-6">
      <GenerationForm busy={busy} onGenerate={generate} />
      {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}{dataset && " The previous dataset is still shown below."}</div>}
      <DatasetPreview key={generation} dataset={dataset} busy={busy} />
      </div>
      {mode === "custom" && <CustomDatasetBuilder />}
    </div>
  );
}
