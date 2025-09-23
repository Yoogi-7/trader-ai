import { useEffect, useState } from 'react';

export const RegistryPanel: React.FC = () => {
  const [versions, setVersions] = useState<string[]>([]);

  // Prosta lista wersji z katalogu – w realu endpoint; tutaj tylko UI + wskazówka
  useEffect(()=> {
    // placeholder UI – backend w P6 zapisuje meta do MODEL_REGISTRY_PATH; w P8 dodamy endpoint
    setVersions([]);
  }, []);

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Model Registry</h2>
        <div className="text-xs text-slate-500">Wersje zapisane w MODEL_REGISTRY_PATH</div>
      </div>
      {versions.length === 0 && <div className="text-sm text-slate-500 mt-2">Brak listingu z backendu (endpoint doda P8). Artefakty są zapisywane na dysku.</div>}
      <div className="mt-3 grid md:grid-cols-3 gap-2">
        {versions.map(v=>(
          <div key={v} className="border rounded-xl p-2 flex items-center justify-between">
            <div className="text-sm">{v}</div>
            <div className="space-x-2">
              <button className="px-2 py-1 bg-emerald-600 text-white rounded">Promote</button>
              <button className="px-2 py-1 bg-rose-600 text-white rounded">Rollback</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
