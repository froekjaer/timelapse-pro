// Dansk visningsnavn for AI-tags — kundevendt UI viser danske navne i stedet
// for de rå engelske kanoniske tag-nøgler (som stadig er hvad der lagres og
// bruges til søgning/filtrering bag kulissen).
//
// Henter ÉN gang pr. session og cacher i hukommelsen — oversættelser ændrer sig
// kun når en admin godkender/retter et tag i Tag Review, hvilket er sjældent
// nok at en simpel "fetch ved første brug"-cache er fin.
import { useEffect, useState } from 'react'
import { getApiUrl } from '../api/client'

type TagLabels = Record<string, string>

let cache: TagLabels | null = null
let inflight: Promise<TagLabels> | null = null

async function fetchTagLabels(): Promise<TagLabels> {
  if (cache) return cache
  if (!inflight) {
    inflight = fetch(`${getApiUrl()}/api/ai/vocabulary/translations`, { credentials: 'include' })
      .then(r => (r.ok ? r.json() : {}))
      .then((data: TagLabels) => {
        cache = data
        return data
      })
      .catch(() => ({} as TagLabels))
  }
  return inflight
}

/** Hook der returnerer den aktuelle tag→dansk-navn map. Trigger en fetch ved
 * første brug i app'en, derefter genbruges cachen overalt. */
export function useTagLabels(): TagLabels {
  const [labels, setLabels] = useState<TagLabels>(cache ?? {})

  useEffect(() => {
    if (cache) {
      setLabels(cache)
      return
    }
    fetchTagLabels().then(setLabels)
  }, [])

  return labels
}

/** Slå et enkelt tag op — falder tilbage til engelsk med underscores erstattet
 * af mellemrum, hvis der ikke (endnu) findes en dansk oversættelse. */
export function tagLabel(tag: string, labels: TagLabels): string {
  return labels[tag] ?? tag.replace(/_/g, ' ')
}

/** Nulstil cachen — kald fx hvis en admin lige har rettet en oversættelse og
 * vil se ændringen uden en fuld sideopdatering. */
export function invalidateTagLabelsCache(): void {
  cache = null
  inflight = null
}
