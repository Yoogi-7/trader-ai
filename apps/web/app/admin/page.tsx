"use client";
import BackfillProgress from "../components/BackfillProgress";
import TrainMetrics from "../components/TrainMetrics";
import ModelRegistry from "../components/ModelRegistry";

export default function AdminPanel(){
  return (
    <div className="max-w-7xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold">Admin — Backfill/Training/Model Registry</h1>
      <BackfillProgress/>
      <TrainMetrics/>
      <ModelRegistry/>
    </div>
  );
}
