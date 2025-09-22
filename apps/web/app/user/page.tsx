"use client";
import RiskSelector from "../components/RiskSelector";
import PairsPicker from "../components/PairsPicker";
import CapitalInput from "../components/CapitalInput";
import LiveSignals from "../components/LiveSignals";
import Backtester from "../components/Backtester";

export default function UserPanel(){
  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Trader AI — Panel użytkownika</h1>
      <div className="grid md:grid-cols-3 gap-4">
        <RiskSelector/>
        <PairsPicker/>
        <CapitalInput/>
      </div>
      <LiveSignals/>
      <Backtester/>
    </div>
  );
}
