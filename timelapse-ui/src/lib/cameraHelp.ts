// Delt hjælpe- og formateringslag for kamera-parametre (LAB + CameraPage).
// Forankret i Nikon Z30 Referencevejledning (da). Formål: fototekniske
// beskrivelser, lukkertid som brøk (ikke komma), og meningsfulde ord frem
// for kameraets bagvedliggende tal/opcodes. Display-transformationer ændrer
// ALDRIG den værdi der sendes til kameraet — kun det brugeren ser.

/** "0,0250s"/"0.0250s" → "1/40"; ">=1s" → "1,3 s"; brøk ind = brøk ud. */
export function prettyShutter(raw: string): string {
  if (!raw) return raw
  const t = raw.trim()
  if (/^1\/\d+(\.\d+)?$/.test(t)) return t.replace('.', ',') // allerede brøk
  const m = /^(\d+(?:[.,]\d+)?)\s*s?$/.exec(t)
  if (!m) return raw
  const sec = parseFloat(m[1].replace(',', '.'))
  if (!isFinite(sec) || sec <= 0) return raw
  if (sec < 1) {
    const denom = Math.round(1 / sec)
    return `1/${denom}`
  }
  const s = Number.isInteger(sec) ? String(sec) : String(sec).replace('.', ',')
  return `${s} s`
}

const SECONDS_RE = /^\d+(?:[.,]\d+)?\s*s$/i

/** Pæn visningsværdi for en parameter — brøk-lukkertid, punktum i f-tal/EV,
 *  og "(ukendt værdi)" for opcodes kameraet ikke kan navngive. Display only. */
export function prettyValue(path: string, raw: string): string {
  if (raw == null) return raw
  const leaf = (path.split('/').pop() || '').toLowerCase()
  if (leaf.includes('shutterspeed')) return prettyShutter(raw)
  if (SECONDS_RE.test(raw.trim())) return prettyShutter(raw)
  if (leaf === 'f-number' || leaf === 'movief-number') return raw.replace(',', '.')
  if (leaf === 'exposurecompensation' || leaf === 'movieexposurecompensation' || leaf === 'flashexposurecompensation')
    return raw.replace(',', '.')
  if (/^unknown value/i.test(raw.trim())) return '(ukendt værdi)'
  return raw
}

/** Fri-tekst TEXT-felter der SKAL kunne redigeres (ellers er TEXT read-only). */
export const EDITABLE_TEXT = new Set<string>([
  '/main/settings/imagecomment',
  '/main/settings/artist',
  '/main/settings/copyright',
  '/main/capturesettings/wbpresetcomment1',
  '/main/capturesettings/wbpresetcomment2',
  '/main/capturesettings/wbpresetcomment3',
  '/main/capturesettings/wbpresetcomment4',
  '/main/capturesettings/wbpresetcomment6',
])

/** Manual-forankrede danske hjælpetekster (gphoto2-path → tekst). */
export const PARAM_HELP: Record<string, string> = {
  // ── Billedindstillinger ───────────────────────────────────────────────
  '/main/imgsettings/imagequality': 'Billedkvalitet — filformat og komprimering. JPEG Fine giver fin detalje med moderat filstørrelse; JPEG Normal/Basic sparer plads; NEF (RAW) giver mest spillerum i efterbehandling men store filer. Til timelapse er JPEG Fine en god balance.',
  '/main/imgsettings/imageformat': 'Filformat. RAW (NEF) til fuld redigeringskontrol (store filer), JPEG til komprimeret levering, RAW+JPEG til begge dele.',
  '/main/imgsettings/imagesize': 'Billedstørrelse — opløsningen på det gemte JPEG. Stor = fuld sensoropløsning; Mellem/Lille sparer lagerplads. Brug Stor til timelapse medmindre plads er knap.',
  '/main/imgsettings/iso': 'ISO-følsomhed — sensorens lysfølsomhed. Lav (100) giver reneste billede men kræver lys; høj (1600+) muliggør optagelse i svagt lys men tilføjer støj/korn. Til timelapse giver en fast, moderat ISO mest ensartede billeder.',
  '/main/imgsettings/isoauto': 'Automatisk ISO — kameraet hæver selv ISO når lyset falder, inden for en grænse. Praktisk ved skiftende lys, men en fast ISO giver mere forudsigelig eksponering fra billede til billede.',
  '/main/imgsettings/autoiso': 'Automatisk ISO-styring (samme funktion som Auto ISO — Nikon viser to felter). Hold de to felter ens.',
  '/main/imgsettings/movieiso': 'ISO for videooptagelse. Ikke relevant for stillbillede-timelapse.',
  '/main/imgsettings/whitebalance': 'Hvidbalance — farvetemperaturen kameraet gengiver som neutral. Automatisk tilpasser løbende; en fast indstilling (fx Dagslys) giver mere ensartet farve fra billede til billede, hvilket er en fordel i timelapse og ved farve-matchning på tværs af kameraer.',
  '/main/imgsettings/colorspace': 'Farverum. sRGB til skærm/web og ensartet levering; AdobeRGB har et større farveomfang til print. sRGB anbefales til timelapse.',

  // ── Eksponering / optagelse ───────────────────────────────────────────
  '/main/capturesettings/exposurecompensation': 'Eksponeringskompensation (EV) — justerer kameraets automatiske eksponering op eller ned. Negativ (−) dæmper direkte sol og reflekser; positiv (+) løfter mørke motiver. Virker i P/S/A-tilstande.',
  '/main/capturesettings/f-number': 'Blænde (f-tal) — objektivets åbning. Lavt f-tal (f/4) giver mere lys og mindre dybdeskarphed; højt f-tal (f/8–f/11) giver større dybdeskarphed. Kan kun sættes i A- eller M-tilstand.',
  '/main/capturesettings/shutterspeed': 'Lukkertid i sekunder/brøk (fx 1/125). Hurtig fryser bevægelse; langsom giver bevægelsessløring. Vises her som brøk. Kan kun sættes i S- eller M-tilstand (ellers read-only).',
  '/main/capturesettings/shutterspeed2': 'Lukkertid vist som brøk (1/40). Visningsfelt — selve indstillingen sker via eksponeringstilstand (S/M).',
  '/main/capturesettings/meteringmode': 'Lysmåling — hvordan kameraet måler scenens lys. Matrix/Multi vægter hele billedet (robust til dagslys); Centervægtet lægger vægt på midten; Spot måler et lille område. Matrix anbefales til timelapse.',
  '/main/capturesettings/exposuremetermode': 'Lysmåling — se Lysmåling. Matrix/Multi er robust default til varierende dagslys.',
  '/main/capturesettings/focusmode': 'Fokustilstand. Manuel = du styrer fokus; AF-S låser fokus når det er fundet; AF-C følger bevægelse. På Z30 er dette felt read-only over PTP — brug i stedet Live View AF-fokus til at skifte MF/AF.',
  '/main/capturesettings/liveviewaffocus': 'Fokustilstand i live view — den fokus-switch der faktisk kan sættes på Z30. Vælg Manuel fokus til drift (så kameraet ikke selv kører autofokus ved hvert billede og slider på fokusmotoren); AF-S/AF-C bruges ved fokus-test.',
  '/main/capturesettings/longexpnr': 'Støjreduktion ved lang eksponering. Ved eksponeringer på flere sekunder tager kameraet et ekstra "mørkt" referencebillede og trækker støjen fra — det fordobler omtrent optagetiden. Mest relevant til nat/lang lukkertid.',
  '/main/capturesettings/capturemode': 'Udløsertilstand — enkeltbillede, serie (burst), kontinuerlig eller selvudløser. Timelapse bruger Enkeltbillede.',
  '/main/capturesettings/imagequality_dup': '',
  '/main/capturesettings/flashmode': 'Blitztilstand. Irrelevant uden monteret blitz i felten.',
  '/main/capturesettings/flashexposurecompensation': 'Eksponeringskompensation for blitz. Irrelevant uden blitz.',
  '/main/capturesettings/focusareawrap': 'Om fokuspunktet "wrapper" rundt til modsatte kant når du flytter det forbi billedkanten.',
  '/main/capturesettings/filenrsequencing': 'Fortløbende filnummerering på tværs af mapper og kort, så filnavne ikke genbruges/kolliderer. Bør stå på Til.',
  '/main/capturesettings/microphone': 'Mikrofonfølsomhed til video. Irrelevant for stillbillede-timelapse.',
  '/main/capturesettings/shootingspeed': 'Billeder pr. sekund i kontinuerlig optagelse. Irrelevant for enkeltbillede-timelapse.',
  '/main/capturesettings/maximumcontinousrelease': 'Maks. antal billeder i én kontinuerlig serie. Irrelevant for timelapse.',
  '/main/capturesettings/burstnumber': 'Antal billeder pr. serie (burst). Irrelevant for enkeltbillede-timelapse.',
  '/main/capturesettings/liveviewsize': 'Opløsning af live view-streamen (QVGA/VGA/XGA). Påvirker preview og fokus i LAB, ikke det gemte billede.',
  '/main/capturesettings/liveviewzoomarea': 'Zoom-niveau i live view — brug til at kontrollere fokus præcist.',
  '/main/capturesettings/hdrhighdynamic': 'HDR-styrke (højt dynamisk område). Kombinerer flere eksponeringer. Flere af kameraets niveauer rapporteres uden navn på Z30. Bruges ikke i standard timelapse.',
  '/main/capturesettings/bracketing': 'Automatisk bracketing — serie af billeder med varieret eksponering/WB. Ikke brugt i standard timelapse.',
  '/main/capturesettings/bracketmode': 'Hvad bracketing varierer (eksponering/blitz/blænde).',
  '/main/capturesettings/bracketset': 'Hvilken type bracketing-serie (AE, blitz, WB, ADL).',
  '/main/capturesettings/bracketorder': 'Rækkefølgen i bracketing-serien.',
  '/main/capturesettings/aebracketingstep': 'EV-trin mellem bracketing-billeder. Nogle niveauer rapporteres uden navn på Z30.',
  '/main/capturesettings/centerweightsize': 'Størrelsen på det centervægtede måleområde. Niveauerne rapporteres uden navn på Z30.',
  '/main/capturesettings/whitebiaspresetno': 'Vælger hvilket hvidbalance-bias-forvalg (1–5) der er aktivt.',
  '/main/capturesettings/autowhitebias': 'Finjustering (bias) af auto-hvidbalance mod varm/kold. 612 er neutral. Justeres normalt via forvalg, ikke direkte.',
  '/main/capturesettings/tungstenwhitebias': 'Bias for glødelys-forvalg. 612 neutral.',
  '/main/capturesettings/flourescentwhitebias': 'Bias for lysstofrør-forvalg. 612 neutral.',
  '/main/capturesettings/daylightwhitebias': 'Bias for dagslys-forvalg. 612 neutral.',
  '/main/capturesettings/flashwhitebias': 'Bias for blitz-forvalg. 612 neutral.',
  '/main/capturesettings/cloudywhitebias': 'Bias for overskyet-forvalg. 612 neutral.',
  '/main/capturesettings/shadewhitebias': 'Bias for skygge-forvalg. 612 neutral.',
  '/main/capturesettings/naturallightautowhitebias': 'Bias for naturligt-lys-auto. 612 neutral.',
  '/main/capturesettings/wbpresetcomment1': 'Fri tekst-kommentar til hvidbalance-forvalg 1.',
  '/main/capturesettings/wbpresetcomment2': 'Fri tekst-kommentar til hvidbalance-forvalg 2.',
  '/main/capturesettings/wbpresetcomment3': 'Fri tekst-kommentar til hvidbalance-forvalg 3.',
  '/main/capturesettings/wbpresetcomment4': 'Fri tekst-kommentar til hvidbalance-forvalg 4.',
  '/main/capturesettings/wbpresetcomment6': 'Fri tekst-kommentar til hvidbalance-forvalg 6.',
  '/main/capturesettings/picturestyle': 'Picture Control — farve-/kontrastprofil. Neutral/Standard er bedst til timelapse (mest spillerum i efterbehandling); Landskab/Levende øger mætning.',

  // ── System / opsætning ────────────────────────────────────────────────
  '/main/settings/capturetarget': 'Hvor et billede lander ved optagelse: kameraets interne hukommelse eller SD-kortet. I drift bør billeder ende på kortet.',
  '/main/settings/recordingmedia': 'Optagemedie — SD-kort eller intern SDRAM. Drift skal bruge kort.',
  '/main/settings/autofocus': 'Autofokus til/fra. I vores drift holdes den fra (manuel fokus) for at skåne fokusmotoren, da kameraet slukkes mellem billeder.',
  '/main/settings/flickerreduction': 'Flimmerreduktion — modvirker ujævn eksponering/farve fra lysstofrør og lignende. 50 Hz i Europa (kviksølv/lysstof), 60 Hz hvor netfrekvensen er 60 Hz.',
  '/main/settings/imagecomment': 'Billedkommentar — fri tekst der skrives i billedets EXIF. Kan bruges til site-/kamera-id.',
  '/main/settings/imagecommentenable': 'Slår EXIF-billedkommentaren til/fra.',
  '/main/settings/artist': 'Fotograf — skrives i EXIF (Nikon: "Oplysninger om ophavsret"). Fri tekst.',
  '/main/settings/copyright': 'Ophavsret — skrives i EXIF. Fri tekst.',
  '/main/settings/thumbsize': 'Størrelse på de indbyggede miniaturer kameraet genererer.',
  '/main/settings/datetime': 'Kameraets ur. Bør synkroniseres med edgen så EXIF-tidsstempler er korrekte. Sæt via dato/tid-synk, ikke manuelt.',
  '/main/settings/reviewtime': 'Hvor længe billedet vises på skærmen efter optagelse.',

  // ── Handlinger (triggere — ikke indstillinger) ─────────────────────────
  '/main/actions/autofocusdrive': 'Udløs ét autofokus-søg. Bruges af fokus-testen i LAB — ikke en vedvarende indstilling. Normal drift kører manuel fokus.',
  '/main/actions/manualfocusdrive': 'Flyt fokusmotoren et defineret trin (negativ = nærmere, positiv = længere væk). Brug fokus-knapperne i LAB, ikke dette felt direkte.',
  '/main/actions/viewfinder': 'Tænd/sluk live view. Bruges internt før autofokus — ikke en indstilling.',

  // ── Status (read-only) ─────────────────────────────────────────────────
  '/main/status/batterylevel': 'Batteriniveau i procent (read-only).',
  '/main/status/shuttercounter': 'Antal lukkercyklusser i kameraets levetid (read-only).',
  '/main/status/availableshots': 'Estimeret antal resterende billeder på kortet (read-only).',
  '/main/status/lensname': 'Monteret objektiv (read-only).',
  '/main/status/cameramodel': 'Kameramodel (read-only).',
  '/main/status/deviceversion': 'Firmwareversion (read-only).',
}

/** Slå hjælpetekst op på fuld gphoto2-path eller på logisk nøgle (camera.iso …). */
const LOGICAL_TO_PATH: Record<string, string> = {
  'camera.iso': '/main/imgsettings/iso',
  'camera.whitebalance': '/main/imgsettings/whitebalance',
  'camera.colorspace': '/main/imgsettings/colorspace',
  'camera.shutter_speed': '/main/capturesettings/shutterspeed',
  'camera.aperture': '/main/capturesettings/f-number',
  'camera.exposurecompensation': '/main/capturesettings/exposurecompensation',
}
export function helpFor(pathOrKey: string): string | undefined {
  if (PARAM_HELP[pathOrKey]) return PARAM_HELP[pathOrKey]
  const mapped = LOGICAL_TO_PATH[pathOrKey]
  return mapped ? PARAM_HELP[mapped] : undefined
}
