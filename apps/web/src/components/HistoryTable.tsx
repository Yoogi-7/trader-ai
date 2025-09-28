import { useMemo } from 'react';
import { ColumnDef, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';

type Signal = {
  id: string; symbol: string; tf_base: string; ts: number; dir: string; entry: number;
  tp?: number[]; sl: number; lev: number; risk: string; margin_mode: string; expected_net_pct: number; status: string;
  ai_summary?: string | null;
  confidence_rating?: number | null;
  market_regime?: string | null;
  sentiment_rating?: number | null;
};

export const HistoryTable: React.FC<{ rows: Signal[] }> = ({ rows }) => {
  const cols = useMemo<ColumnDef<Signal>[]>(() => [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Symbol', accessorKey: 'symbol' },
    { header: 'TF', accessorKey: 'tf_base' },
    { header: 'Dir', accessorKey: 'dir' },
    { header: 'Entry', accessorKey: 'entry' },
    { header: 'SL', accessorKey: 'sl' },
    { header: 'Lev', accessorKey: 'lev' },
    { header: 'Risk', accessorKey: 'risk' },
    { header: 'Net %', accessorKey: 'expected_net_pct',
      cell: info => (info.getValue<number>()*100).toFixed(2) + '%' },
    { header: 'Rating', accessorKey: 'confidence_rating',
      cell: info => {
        const value = info.getValue<number | null | undefined>();
        return value != null ? `${value}/100` : '—';
      } },
    { header: 'Regime', accessorKey: 'market_regime',
      cell: info => info.getValue<string | null | undefined>() || '—' },
    { header: 'Sentiment', accessorKey: 'sentiment_rating',
      cell: info => {
        const value = info.getValue<number | null | undefined>();
        return value != null ? `${value}/100` : '—';
      } },
    { header: 'Status', accessorKey: 'status' },
    { header: 'Opis AI', accessorKey: 'ai_summary', cell: info => info.getValue<string | null>() || '—' },
  ], []);
  const table = useReactTable({ data: rows, columns: cols, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100">
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id}>
              {hg.headers.map(h => (
                <th key={h.id} className="text-left p-2">{flexRender(h.column.columnDef.header, h.getContext())}</th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(r => (
            <tr key={r.id} className="border-b">
              {r.getVisibleCells().map(c => (
                <td key={c.id} className="p-2">{flexRender(c.column.columnDef.cell, c.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
