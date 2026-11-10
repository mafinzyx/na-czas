import type { JourneyPlan, RouteOption } from '../api/types'

export function findOption(plan: JourneyPlan, id: string): RouteOption | undefined {
  return plan.options.find((option) => option.id === id)
}
