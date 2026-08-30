import React from 'react';

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T, index: number) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  className?: string;
  width?: string;
}

interface DataTableProps<T> {
  id?: string;
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T, index: number) => string;
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
  className?: string;
}

export function DataTable<T>({
  id,
  columns,
  data,
  keyExtractor,
  onRowClick,
  emptyMessage = 'No records available.',
  className = '',
}: DataTableProps<T>) {
  return (
    <div
      id={id || 'data-table-container'}
      className={`w-full overflow-x-auto rounded-lg border border-[#222] bg-[#161616] ${className}`}
    >
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-black/30 border-b border-[#222] text-gray-400 font-bold uppercase tracking-wider text-[10px]">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                style={{ width: col.width }}
                className={`py-3.5 px-4 ${
                  col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                } ${col.className || ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#222] text-gray-200">
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="py-8 text-center text-gray-500 font-mono text-xs">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item, index) => {
              const rowKey = keyExtractor(item, index);
              return (
                <tr
                  key={rowKey}
                  id={`row-${rowKey}`}
                  onClick={() => onRowClick?.(item)}
                  className={`transition-colors ${
                    onRowClick ? 'cursor-pointer hover:bg-white/[0.03]' : 'hover:bg-white/[0.015]'
                  }`}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`py-3 px-4 ${
                        col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                      } ${col.className || ''}`}
                    >
                      {col.render ? col.render(item, index) : (item as any)[col.key] ?? '—'}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

