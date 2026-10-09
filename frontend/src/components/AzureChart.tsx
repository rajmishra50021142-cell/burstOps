import React, { useState } from 'react';
import { MetricHistoryPoint } from '../types';

interface AzureChartSeries {
  key: keyof MetricHistoryPoint;
  label: string;
  color: string;
  unit?: string;
}

interface AzureChartProps {
  title: string;
  subtitle?: string;
  data: MetricHistoryPoint[];
  series: AzureChartSeries[];
  height?: number;
  showHysteresisThresholds?: boolean;
  minY?: number;
  maxY?: number;
  timeRangeLabel?: string;
}

export const AzureChart: React.FC<AzureChartProps> = ({
  title,
  subtitle,
  data,
  series,
  height = 200,
  showHysteresisThresholds = false,
  minY = 0,
  maxY,
  timeRangeLabel = 'Last 5 minutes',
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // If data is empty, show skeleton / placeholder
  if (!data || data.length === 0) {
    return (
      <div className="azure-card p-4 rounded-sm flex flex-col justify-between" style={{ height }}>
        <div className="flex items-center justify-between">
          <span className="font-semibold text-xs text-[#323130] dark:text-white">{title}</span>
          <span className="text-[10px] text-slate-400">{timeRangeLabel}</span>
        </div>
        <div className="flex-1 flex items-center justify-center text-xs text-slate-400">
          Gathering telemetry points (polled every 2s)...
        </div>
      </div>
    );
  }

  // Calculate bounds
  let computedMaxY = maxY;
  if (computedMaxY === undefined) {
    let maxVal = 0;
    for (const point of data) {
      for (const s of series) {
        const val = Number(point[s.key]) || 0;
        if (val > maxVal) maxVal = val;
      }
    }
    computedMaxY = showHysteresisThresholds ? Math.max(100, maxVal * 1.1) : Math.max(10, maxVal * 1.25);
  }

  const padding = { top: 20, right: 55, bottom: 25, left: 40 };
  const chartWidth = 600; // viewBox width
  const chartHeight = height;

  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  const pointsCount = data.length;

  const getX = (index: number) => {
    if (pointsCount <= 1) return padding.left;
    return padding.left + (index / (pointsCount - 1)) * innerWidth;
  };

  const getY = (val: number) => {
    const clamped = Math.max(minY, Math.min(computedMaxY, val));
    const normalized = (clamped - minY) / (computedMaxY - minY || 1);
    return padding.top + innerHeight - normalized * innerHeight;
  };

  // Build SVG path strings
  const getLinePath = (seriesKey: keyof MetricHistoryPoint) => {
    return data
      .map((d, i) => {
        const val = Number(d[seriesKey]) || 0;
        const x = getX(i);
        const y = getY(val);
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(' ');
  };

  const getAreaPath = (seriesKey: keyof MetricHistoryPoint) => {
    const line = getLinePath(seriesKey);
    const lastX = getX(pointsCount - 1);
    const firstX = getX(0);
    const bottomY = getY(minY);
    return `${line} L ${lastX.toFixed(1)} ${bottomY.toFixed(1)} L ${firstX.toFixed(1)} ${bottomY.toFixed(1)} Z`;
  };

  const hoveredPoint = hoverIndex !== null && data[hoverIndex] ? data[hoverIndex] : null;

  return (
    <div className="azure-card p-4 rounded-sm space-y-2 select-none relative group">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
            {title}
            {subtitle && (
              <span className="font-normal text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                — {subtitle}
              </span>
            )}
          </h4>
        </div>

        <div className="flex items-center gap-3 text-[11px]">
          {/* Series Legends */}
          {series.map((s) => (
            <div key={s.label} className="flex items-center gap-1.5 text-[#605E5C] dark:text-[#A19F9D]">
              <span className="w-2.5 h-1 rounded-sm" style={{ backgroundColor: s.color }} />
              <span>{s.label}</span>
            </div>
          ))}
          <span className="text-[10px] text-slate-400 font-mono ml-1">{timeRangeLabel}</span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative">
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          className="w-full overflow-visible"
          style={{ height }}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = ((e.clientX - rect.left) / rect.width) * chartWidth;
            if (relX >= padding.left && relX <= chartWidth - padding.right) {
              const fraction = (relX - padding.left) / innerWidth;
              const idx = Math.round(fraction * (pointsCount - 1));
              setHoverIndex(Math.max(0, Math.min(pointsCount - 1, idx)));
            }
          }}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            {series.map((s) => (
              <linearGradient key={`grad-${s.label}`} id={`grad-${s.label}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity="0.25" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0.0" />
              </linearGradient>
            ))}
          </defs>

          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={getY(minY)}
            x2={chartWidth - padding.right}
            y2={getY(minY)}
            stroke="#EDEBE9"
            className="dark:stroke-[#292827]"
            strokeWidth="1"
          />
          <line
            x1={padding.left}
            y1={getY(computedMaxY / 2)}
            x2={chartWidth - padding.right}
            y2={getY(computedMaxY / 2)}
            stroke="#EDEBE9"
            className="dark:stroke-[#292827]"
            strokeWidth="1"
            strokeDasharray="2 2"
          />
          <line
            x1={padding.left}
            y1={getY(computedMaxY)}
            x2={chartWidth - padding.right}
            y2={getY(computedMaxY)}
            stroke="#EDEBE9"
            className="dark:stroke-[#292827]"
            strokeWidth="1"
            strokeDasharray="2 2"
          />

          {/* Y-axis Labels */}
          <text
            x={padding.left - 6}
            y={getY(computedMaxY) + 3}
            textAnchor="end"
            fontSize="9"
            className="fill-slate-400 font-mono"
          >
            {Math.round(computedMaxY)}
          </text>
          <text
            x={padding.left - 6}
            y={getY(computedMaxY / 2) + 3}
            textAnchor="end"
            fontSize="9"
            className="fill-slate-400 font-mono"
          >
            {Math.round(computedMaxY / 2)}
          </text>
          <text
            x={padding.left - 6}
            y={getY(minY) + 3}
            textAnchor="end"
            fontSize="9"
            className="fill-slate-400 font-mono"
          >
            {Math.round(minY)}
          </text>

          {/* Hysteresis Threshold Lines (80% Burst / 60% Recover) */}
          {showHysteresisThresholds && (
            <>
              {/* 80% Burst Threshold */}
              <g>
                <line
                  x1={padding.left}
                  y1={getY(80)}
                  x2={chartWidth - padding.right}
                  y2={getY(80)}
                  stroke="#D83B01"
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                />
                <text
                  x={chartWidth - padding.right + 4}
                  y={getY(80) + 3}
                  fontSize="9"
                  className="fill-amber-500 font-mono font-semibold"
                >
                  80% Burst
                </text>
              </g>

              {/* 60% Recovery Threshold */}
              <g>
                <line
                  x1={padding.left}
                  y1={getY(60)}
                  x2={chartWidth - padding.right}
                  y2={getY(60)}
                  stroke="#107C10"
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                />
                <text
                  x={chartWidth - padding.right + 4}
                  y={getY(60) + 3}
                  fontSize="9"
                  className="fill-emerald-500 font-mono font-semibold"
                >
                  60% Recv
                </text>
              </g>
            </>
          )}

          {/* Area gradients & Paths */}
          {series.map((s) => (
            <React.Fragment key={s.label}>
              <path
                d={getAreaPath(s.key)}
                fill={`url(#grad-${s.label})`}
                pointerEvents="none"
              />
              <path
                d={getLinePath(s.key)}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                pointerEvents="none"
              />
            </React.Fragment>
          ))}

          {/* Hover Crosshair */}
          {hoverIndex !== null && (
            <g pointerEvents="none">
              <line
                x1={getX(hoverIndex)}
                y1={padding.top}
                x2={getX(hoverIndex)}
                y2={padding.top + innerHeight}
                stroke="#0078D4"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              {series.map((s) => {
                const val = Number(data[hoverIndex][s.key]) || 0;
                return (
                  <circle
                    key={`dot-${s.label}`}
                    cx={getX(hoverIndex)}
                    cy={getY(val)}
                    r="3.5"
                    fill={s.color}
                    stroke="#FFFFFF"
                    strokeWidth="1.5"
                  />
                );
              })}
            </g>
          )}

          {/* X-axis start/end timestamps */}
          <text
            x={padding.left}
            y={chartHeight - 6}
            textAnchor="start"
            fontSize="9"
            className="fill-slate-400 font-mono"
          >
            {data[0]?.timeLabel || ''}
          </text>
          <text
            x={chartWidth - padding.right}
            y={chartHeight - 6}
            textAnchor="end"
            fontSize="9"
            className="fill-slate-400 font-mono"
          >
            {data[data.length - 1]?.timeLabel || ''}
          </text>
        </svg>

        {/* Floating Tooltip */}
        {hoveredPoint && hoverIndex !== null && (
          <div
            className="absolute -top-7 pointer-events-none z-20 bg-black/85 dark:bg-black/90 text-white text-[10px] px-2.5 py-1 rounded-sm shadow-md font-mono flex items-center gap-2 transform -translate-x-1/2"
            style={{
              left: `${((getX(hoverIndex) / chartWidth) * 100).toFixed(1)}%`,
            }}
          >
            <span className="text-slate-400">{hoveredPoint.timeLabel}:</span>
            {series.map((s) => (
              <span key={s.label} style={{ color: s.color }} className="font-semibold">
                {s.label}: {Number(hoveredPoint[s.key]).toFixed(1)}{s.unit || ''}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
