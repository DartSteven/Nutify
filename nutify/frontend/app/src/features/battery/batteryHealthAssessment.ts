/**
 * Batteryhealthassessment.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type BatteryHealthAssessment = {
  score: number
  level: 'Excellent' | 'Good' | 'Watch' | 'Critical'
  summary: string
  recommendations: string[]
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function buildBatteryHealthAssessment(
  chargePercent: number,
  runtimeMinutes: number,
  voltageValue: number,
  temperatureCelsius: number | null,
): BatteryHealthAssessment {
  const safeCharge = clamp(Number.isFinite(chargePercent) ? chargePercent : 0, 0, 100)
  const safeRuntime = clamp(Number.isFinite(runtimeMinutes) ? runtimeMinutes : 0, 0, 240)
  const safeVoltage = clamp(Number.isFinite(voltageValue) ? voltageValue : 0, 0, 64)

  const runtimeScore = clamp((safeRuntime / 180) * 100, 0, 100)
  const voltageScore = clamp((safeVoltage / 32) * 100, 0, 100)
  const temperatureScore = (() => {
    if (temperatureCelsius === null || !Number.isFinite(temperatureCelsius)) {
      return 60
    }
    if (temperatureCelsius >= 20 && temperatureCelsius <= 30) return 100
    if (temperatureCelsius >= 15 && temperatureCelsius <= 35) return 70
    if (temperatureCelsius >= 10 && temperatureCelsius <= 40) return 40
    return 20
  })()

  const score = clamp(
    Math.round(safeCharge * 0.45 + runtimeScore * 0.25 + voltageScore * 0.15 + temperatureScore * 0.15),
    0,
    100,
  )

  if (score >= 85) {
    return {
      score,
      level: 'Excellent',
      summary: 'Battery operating in an optimal range with healthy reserve.',
      recommendations: [
        'Keep current charging profile and monthly self-test cadence.',
        'Continue monitoring runtime drift against your usual load.',
      ],
    }
  }

  if (score >= 65) {
    return {
      score,
      level: 'Good',
      summary: 'Battery is stable, but periodic checks are recommended.',
      recommendations: [
        'Run a manual battery test during a low-risk time window.',
        'Watch for runtime drops or temperature spikes in peak hours.',
      ],
    }
  }

  if (score >= 45) {
    return {
      score,
      level: 'Watch',
      summary: 'Battery condition is acceptable but trending toward maintenance.',
      recommendations: [
        'Schedule a battery calibration test and verify ventilation.',
        'Prepare replacement planning if runtime keeps dropping.',
      ],
    }
  }

  return {
    score,
    level: 'Critical',
    summary: 'Battery health is degraded and requires immediate attention.',
    recommendations: [
      'Plan battery replacement as soon as possible.',
      'Reduce critical load exposure until replacement is complete.',
    ],
  }
}
