/**
 * Batterycharts.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type BatteryPoint = {
  timestamp: number
  value: number
}

export type BatteryHistoryPayload = {
  charge: BatteryPoint[]
  runtime: BatteryPoint[]
  voltage: BatteryPoint[]
  temperature: BatteryPoint[]
}

function toDate(value: number | string): Date | null {
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) {
    return null
  }

  const date = new Date(parsed)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  return date
}

function formatTime(value: number | string, timezone: string): string {
  const date = toDate(value)
  if (!date) {
    return String(value)
  }

  try {
    return date.toLocaleTimeString(undefined, {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  }
}

function formatDateTime(value: number | string, timezone: string): string {
  const date = toDate(value)
  if (!date) {
    return String(value)
  }

  try {
    return date.toLocaleString(undefined, {
      timeZone: timezone,
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  }
}

export function buildBatteryCombinedSeries(history: BatteryHistoryPayload) {
  return [
    {
      name: 'Battery Level',
      data: history.charge.map((point) => ({ x: point.timestamp, y: point.value })),
      color: '#2E93fA',
      type: 'line',
    },
    {
      name: 'Runtime',
      data: history.runtime.map((point) => ({ x: point.timestamp, y: point.value / 60 })),
      color: '#66DA26',
      type: 'line',
    },
    {
      name: 'Voltage',
      data: history.voltage.map((point) => ({ x: point.timestamp, y: point.value })),
      color: '#FF9800',
      type: 'line',
    },
  ]
}

export function buildBatteryCombinedOptions(timezone: string) {
  return {
    chart: {
      type: 'line',
      height: 450,
      animations: {
        enabled: true,
        easing: 'linear',
        dynamicAnimation: {
          speed: 1000,
        },
      },
      toolbar: {
        show: true,
      },
      noData: {
        text: 'Loading data...',
        align: 'center',
        verticalAlign: 'middle',
        style: {
          fontSize: '16px',
        },
      },
    },
    stroke: {
      curve: 'smooth',
      width: [2, 2, 2],
    },
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false,
        rotate: 0,
        formatter: (value: string) => formatTime(value, timezone),
      },
    },
    tooltip: {
      x: {
        formatter: (value: number) => formatTime(value, timezone),
      },
      y: {
        formatter: (value: number) => Number(value).toFixed(2),
      },
    },
    yaxis: [
      {
        title: {
          text: 'Battery Level (%)',
          style: { color: '#2E93fA' },
        },
        min: 0,
        max: 100,
        tickAmount: 5,
        decimalsInFloat: 0,
        labels: {
          formatter: (value: number) => String(Math.round(value)),
          style: { colors: '#2E93fA' },
        },
      },
      {
        opposite: true,
        title: {
          text: 'Runtime (min)',
          style: { color: '#66DA26' },
        },
        labels: {
          formatter: (value: number) => String(Math.round(value)),
          style: { colors: '#66DA26' },
        },
      },
      {
        opposite: true,
        title: {
          text: 'Voltage (V)',
          style: { color: '#FF9800' },
        },
        min: 0,
        tickAmount: 5,
        labels: {
          formatter: (value: number) => String(Math.round(value)),
          style: { colors: '#FF9800' },
        },
      },
    ],
    legend: {
      horizontalAlign: 'center',
    },
  }
}

export function buildBatteryTemperatureSeries(history: BatteryHistoryPayload) {
  return [
    {
      name: 'Temperature',
      data: history.temperature.map((point) => ({ x: point.timestamp, y: point.value })),
    },
  ]
}

export function buildBatteryTemperatureOptions(timezone: string) {
  return {
    chart: {
      type: 'line',
      height: 350,
      animations: { enabled: true },
    },
    stroke: {
      curve: 'smooth',
      width: 2,
    },
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false,
        rotate: 0,
        formatter: (value: string) => formatTime(value, timezone),
      },
    },
    yaxis: {
      title: { text: 'Temperature (°C)' },
      decimalsInFloat: 1,
      min: 15,
      max: 30,
    },
    tooltip: {
      shared: true,
      x: {
        formatter: (value: number) => formatDateTime(value, timezone),
      },
    },
  }
}

export const BATTERY_HEALTH_OPTIONS = {
  chart: {
    type: 'radialBar',
    height: 350,
    foreColor: 'var(--text-primary, #e6edf7)',
  },
  plotOptions: {
    radialBar: {
      startAngle: -135,
      endAngle: 135,
      hollow: {
        margin: 15,
        size: '70%',
      },
      track: {
        background: '#e7e7e7',
        strokeWidth: '97%',
        margin: 5,
      },
      dataLabels: {
        name: {
          show: true,
          fontSize: '16px',
          color: 'var(--text-secondary, #b8c1d7)',
          offsetY: -10,
        },
        value: {
          show: true,
          fontSize: '30px',
          offsetY: 5,
          formatter: (value: number) => `${Number(value).toFixed(2)}%`,
        },
      },
    },
  },
  fill: {
    type: 'gradient',
    gradient: {
      shade: 'dark',
      type: 'horizontal',
      shadeIntensity: 0.5,
      gradientToColors: ['#ABE5A1'],
      inverseColors: true,
      opacityFrom: 1,
      opacityTo: 1,
      stops: [0, 100],
    },
  },
  stroke: {
    lineCap: 'round',
  },
  labels: ['Battery Health'],
}
