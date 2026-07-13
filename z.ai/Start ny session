Vi starter lige på en ny session. Allerførst vil jeg gerne bede dig læse 00_START_HER.md`, `GO_LIVE_CHECKLIST_v10.md og  læse og løbende   
  opdatere HANDOVER_LOG.md ved alle                                                                                                          
    aktiviteter, opdateringer og ændringer, samt opdatere relevante dokumenter som user/admin guide og risk                                  
    assessment mv. Vi sluttede med følgende i sidste session. Håber du kan samle op på det, og gøre det færdigt, du var i gang med, og       
  derefter gå videre, please?
  
  
  
  
  
  
  ⏺ Nu opdaterer jeg Gemini Batch sektionen (Vertex AI / Cloud Storage):
     
⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/SystemAdminPage.tsx)
  ⎿  Added 4 lines, removed 2 lines
      820        {/* Gemini Batch (Vertex AI / GCS) — kun relevant ved service-account auth */}
      821        <Section title="Gemini Batch — Vertex AI / Cloud Storage" icon={<Database className="w-4 h-4" />}
      822          description="Kun nødvendigt hvis I bruger Vertex AI (service account) til Gemini. AI Studio (API-nøgle) bruger Files API i stedet og kræver ikke 
           dette."> 
      823 -        <Field label="GCS bucket" description="Navn uden 'gs://', fx 'timelapse-ai-batch'. Bruges til at uploade billeder og hente resultater under batch
          --jobs.">                                                                                                                                                 
      823 +        <Field label="GCS bucket" description="Navn uden 'gs://', fx 'timelapse-ai-batch'. Bruges til at uploade billeder og hente resultater under batch
          +-jobs."                                                                                                                                                  
      824 +          tooltip="Google Cloud Storage bucket navn til Gemini batch processing. Skal oprettes manuelt og have appropriate IAM permissions. Navn uden gs:
          +// prefix (fx timelapse-ai-batch). Service account skal have Storage Object Admin.">                                                                     
      825            <Txt value={settings.gemini_gcs_bucket ?? ''} onChange={v => setSettings(s => ({...s, gemini_gcs_bucket: v}))} mono />
      826          </Field>
      826 -        <Field label="Bucket-region" description="SKAL matche jeres Vertex AI-region (fx 'europe-west1') — ellers stoppes batch-jobs for at undgå databeh
          -andling uden for EU (GDPR).">                                                                                                                            
      827 +        <Field label="Bucket-region" description="SKAL matche jeres Vertex AI-region (fx 'europe-west1') — ellers stoppes batch-jobs for at undgå databeh
          +andling uden for EU (GDPR)."                                                                                                                             
      828 +          tooltip="GCS bucket region SKAL matche Vertex AI region for at undgå data crossing region boundaries (GDPR). Fx europe-west1 for EU data. Forke
          +rt region kan stoppe batch-jobs for compliance. Service account og bucket skal være i samme region.">                                                    
      829            <Txt value={settings.gemini_gcs_bucket_region ?? ''} onChange={v => setSettings(s => ({...s, gemini_gcs_bucket_region: v}))} mono />
      830          </Field>
      831          <p className="text-xs text-amber-600 mt-1">

  Thought for 3s (ctrl+o to expand)

⏺ Nu opdaterer jeg BT PAN TOTP sektionen (global rotation):
     
⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/SystemAdminPage.tsx)
  ⎿  Added 4 lines, removed 2 lines
      843        {/* BT PAN TOTP — globalt lag (laveste prioritet, lige over fabriksstandard) */}
      844        <Section title="BT PAN TOTP — global rotation" icon={<Database className="w-4 h-4" />}
      845          description="Gælder ALLE enheder uden mere specifikt kunde/site/kamera-override. Brug ved kompromitteret secret.">
      846 -        <Field label="Global secret (Base32)" description="Tom = brug fabriksstandard JBSWY3DPEHPK3PXP">                                                 
      846 +        <Field label="Global secret (Base32)" description="Tom = brug fabriksstandard JBSWY3DPEHPK3PXP"                                                  
      847 +          tooltip="Global BT PAN TOTP secret i Base32 format. Gælder alle enheder uden specifikke overrides. Tom bruger fabriksstandard (JBSWY3DPEHPK3PXP
          + = HELLO WORLD). Bruges til technician authentication via QR codes. KUN roter ved kompromittering.">                                                     
      848            <Txt value={settings.bt_totp_secret ?? ''} onChange={v => setSettings(s => ({...s, bt_totp_secret: v}))} mono />
      849          </Field>
      849 -        <Field label="Global SID" description="Label vist på edge login-side og i CMDB">                                                                 
      850 +        <Field label="Global SID" description="Label vist på edge login-side og i CMDB"                                                                  
      851 +          tooltip="Global System Identifier vist på edge login-side og i CMDB. Identificerer hvilket TOTP system der bruges. Fx 'TimeLapse PRO Production
          +' eller 'Site A'. Hjælper teknikere med at vælge rigtige credentials ved onsite login.">                                                                 
      852            <Txt value={settings.bt_totp_sid ?? ''} onChange={v => setSettings(s => ({...s, bt_totp_sid: v}))} mono />
      853          </Field>
      854          <p className="text-xs text-amber-600 mt-1">

  Thought for 3s (ctrl+o to expand)

⏺ Nu opdaterer jeg SSH Tunnel sektionen:
     
⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/SystemAdminPage.tsx)
  ⎿  Added 16 lines, removed 8 lines
      894        <Section title="SSH Tunnel" icon={<Terminal className="w-4 h-4" />}
      895          description="Reverse SSH tunnel til remote adgang — edge initierer forbindelsen">
      896          <Field label="Aktiver tunnel"
      897 -          description="Edge åbner tunnel til headend ved næste config-poll">                                                                             
      897 +          description="Edge åbner tunnel til headend ved næste config-poll"                                                                              
      898 +          tooltip="Aktiver reverse SSH tunnel fra edge til headend for remote adgang. Edge initierer forbindelsen (firewall friendly). Tunnel oprettes ve
          +d næste config poll. Kræver gyldig endpoint og nøglefil.">                                                                                               
      899            <Toggle value={tunnelEnabled} onChange={setTunnelEnabled} />
      900          </Field>
      901          <Field label="Primær endpoint"
      901 -          description="Bruger og host som edge forbinder til (user@host:port)">                                                                          
      902 +          description="Bruger og host som edge forbinder til (user@host:port)"                                                                           
      903 +          tooltip="SSH endpoint som edge forbinder til i formatet user@host:port. Edge authenticerer med key_file. Headend skal have tilsvarende public k
          +ey i authorized_keys. Forkerte credentials giver connection timeout.">                                                                                   
      904            <Txt value={tunnelPrimary} onChange={setTunnelPrimary} mono placeholder="user@headend.example:22" />
      905          </Field>
      906          <Field label="Remote port"
      905 -          description="Port der åbnes på headend — unik pr. device">                                                                                     
      907 +          description="Port der åbnes på headend — unik pr. device"                                                                                      
      908 +          tooltip="Port på headend der åbnes for tunnel ind til edge SSH. Skal være unik pr. device for at undgå konflikter. Fx 2201, 2202, osv. Skal vær
          +e åben i headend firewall. Forkert port kan forårsage port conflict.">                                                                                   
      909            <Num value={tunnelRemotePort} onChange={setTunnelRemotePort} placeholder="2201" />
      910          </Field>
      911          <Field label="Lokal port på Edge"
      909 -          description="Port på Edge som tunnelen videresender til">                                                                                      
      912 +          description="Port på Edge som tunnelen videresender til"                                                                                       
      913 +          tooltip="SSH port på edge enhed som tunnelen videresender til. Typisk 22 for standard SSH. Skal matche SSH daemon config på edge. Forkert port 
          +kan give tunnel til non-existent service.">                                                                                                              
      914            <Num value={tunnelLocalPort} onChange={setTunnelLocalPort} placeholder="22" />
      915          </Field>
      916          <Field label="Nøglefil (edge)"
      913 -          description="Sti til SSH privat nøgle på edge-enheden">                                                                                        
      917 +          description="Sti til SSH privat nøgle på edge-enheden"                                                                                         
      918 +          tooltip="Sti til SSH privat nøgle på edge enhed til tunnel authentication. Fx /root/.ssh/tunnel_key. Nøglen skal være tilgængelig på edge og ma
          +tching public key skal være på headend. Forkert sti kan forhindre tunnel oprettelse.">                                                                   
      919            <Txt value={tunnelKeyFile} onChange={setTunnelKeyFile} mono placeholder="/path/to/tunnel_key" />
      920          </Field>
      921          <Field label="Auto-start ved API-tab"
      917 -          description="Start tunnel automatisk hvis headend API er utilgængeligt">                                                                       
      922 +          description="Start tunnel automatisk hvis headend API er utilgængeligt"                                                                        
      923 +          tooltip="Start SSH tunnel automatisk hvis headend API er utilgængelig i N sekunder. Bruges til remote recovery ved netværks problemer. Aktivere
          +t som fallback mekanisme. Kræver at enabled er true.">                                                                                                   
      924            <Toggle value={tunnelAutoOnApiLoss} onChange={setTunnelAutoOnApiLoss} />
      925          </Field>
      926          <Field label="Auto-start tærskel" unit="sekunder"
      921 -          description="Hvor længe API skal være utilgængelig før tunnel startes">                                                                        
      927 +          description="Hvor længe API skal være utilgængelig før tunnel startes"                                                                         
      928 +          tooltip="Sekunder headend API skal være utilgængelig før tunnel auto-startes. For lav værdi kan give unødvendige tunnels ved midlertidige netvæ
          +rks glitches. Høj værdi kan forsinke recovery. Typisk 300-600 sekunder.">                                                                                
      929            <Num value={tunnelAutoOnApiLossThresholdS} onChange={setTunnelAutoOnApiLossThresholdS} placeholder="300" />
      930          </Field>
      931          <Field label="Forbyd tunnel"
      925 -          description="Denne enhed må aldrig oprette SSH tunnel (tilsidesætter enabled)">                                                                
      932 +          description="Denne enhed må aldrig oprette SSH tunnel (tilsidesætter enabled)"                                                                 
      933 +          tooltip="Forbyd SSH tunnel for denne enhed uanset enabled setting. Bruges til sites med sikkerhedspolitik der forbyder remote adgang. Tilsidesæ
          +tter både enabled og auto_on_api_loss.">                                                                                                                 
      934            <Toggle value={tunnelDeny} onChange={setTunnelDeny} />
      935          </Field>
      936          <div className="flex justify-end mt-3">

  Thought for 3s (ctrl+o to expand)

⏺ SystemAdminPage er nu færdig med tooltips! Lad mig teste UI build og derefter gå videre til næste side:
     
⏺ Bash(cd /Users/peter/projects/timelapse-pro/timelapse-ui && npm run build 2>&1 | tail -20)
  ⎿  > tsc -b && vite build
     
     (node:11341) [DEP0205] DeprecationWarning: `module.register()` is deprecated. Use `module.registerHooks()` instead.
     … +19 lines (ctrl+o to expand)

  Thought for 4s (ctrl+o to expand)
  
⏺ ✅ UI bygger succesfuldt! SystemAdminPage er færdig. Nu opdaterer jeg task status og fortsætter med AIPage:
  
  Thought for 3s (ctrl+o to expand)
  
⏺ Nu læser jeg AIPage for at tilføje tooltips til alle parametre:
  
  Thought for 4s, read 1 file (ctrl+o to expand)

⏺ Nu opdaterer jeg AIPage edit modal med tooltips på alle labels:
  
⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/AIPage.tsx)
  ⎿  Added 12 lines, removed 6 lines
      556  
      557              {/* Strategi */}
      558              <div className="space-y-2">
      559 -              <label className="text-xs text-slate-400 font-medium uppercase tracking-wider">Strategi</label>                                            
      559 +              <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Vælg AI strategi: Technical_only (kun OpenCV kvalitet
          +skontrol, ingen tags), Local_only (kun Ollama, offline), Local_then_cloud (Ollama først, Gemini ved usikkerhed), Cloud_only (kun Gemini Flash, bedste kva
          +litet). Cloud kræver API nøgle.">Strategi</label>                                                                                                        
      560                <div className="grid grid-cols-2 gap-2">
      561                  {(Object.keys(STRATEGY_META) as Strategy[]).map(s => (
      562                    <button
     ...
      567                          ? 'border-violet-500 bg-violet-950/50'
      568                          : 'border-white/8 bg-gray-800 hover:border-white/20'
      569                      }`}
      570 +                    title={STRATEGY_META[s].desc}                                                                                                        
      571                    >
      572                      <div className="mt-0.5"><StrategyBadge strategy={s} /></div>
      573                      <p className="text-xs text-slate-400 mt-0.5">{STRATEGY_META[s].desc}</p>
     ...
      579              {/* Lokal model */}
      580              {(editing.strategy === 'local_only' || editing.strategy === 'local_then_cloud') && (
      581                <div className="space-y-1.5">
      581 -                <label className="text-xs text-slate-400 font-medium uppercase tracking-wider">Lokal model</label>                                       
      582 +                <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Lokal vision model til tag analyse. qwen2.5vl:7b (a
          +nbefalet - balance mellem hastighed og kvalitet), llama3.2-vision:11b (tung men meget præcis), llava-phi3:latest (hurtig men mindre præcis). Modellen ska
          +l være pulled på Ollama server.">Lokal model</label>                                                                                                     
      583                  <select
      584                    value={editing.local_model}
      585                    onChange={e => setEditing({ ...editing, local_model: e.target.value })}
      586                    className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
      587 +                  title="Lokal vision model til tag analyse. qwen2.5vl:7b (anbefalet - balance mellem hastighed og kvalitet), llama3.2-vision:11b (tung m
          +en meget præcis), llava-phi3:latest (hurtig men mindre præcis). Modellen skal være pulled på Ollama server."                                             
      588                  >
      589                    <option value="qwen2.5vl:7b">qwen2.5vl:7b (anbefalet)</option>
      590                    <option value="llama3.2-vision:11b">llama3.2-vision:11b (tung)</option>
     ...
      597              {editing.strategy === 'local_then_cloud' && (
      598                <div className="grid grid-cols-2 gap-3">
      599                  <div className="space-y-1.5">
      598 -                  <label className="text-xs text-slate-400 font-medium uppercase tracking-wider">                                                        
      600 +                  <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Confidence tærskel for eskalering til Gemini. Hvi
          +s lokal model confidence er under denne værdi (fx 0.70), sendes billedet til Gemini for bedre analyse. Højere værdi = mere cloud usage. Lavere værdi = fl
          +ere locale resultater. Typisk 0.60-0.80.">                                                                                                               
      601                      Eskalér hvis confidence &lt;
      602                    </label>
      603                    <input
     ...
      605                      value={editing.escalation_threshold}
      606                      onChange={e => setEditing({ ...editing, escalation_threshold: parseFloat(e.target.value) })}
      607                      className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
      608 +                    title="Confidence tærskel (0.5-1.0). Hvis lokal model er usikker, eskaler til Gemini. Højere = mere cloud usage. Typisk 0.60-0.80."  
      609                    />
      610                  </div>
      611                  <div className="space-y-1.5">
      609 -                  <label className="text-xs text-slate-400 font-medium uppercase tracking-wider">                                                        
      612 +                  <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Maksimalt antal nye/ukendte tags før eskalering t
          +il Gemini. Hvis lokal model finder mere end N tags der ikke er i vocab, sendes til Gemini for at udvide vokabulariet. Højere værdi = mere lokal autonomy.
          + Typisk 3-10 nye tags.">                                                                                                                                 
      613                      Eskalér hvis &gt; N nye tags
      614                    </label>
      615                    <input
     ...
      617                      value={editing.escalation_new_tags}
      618                      onChange={e => setEditing({ ...editing, escalation_new_tags: parseInt(e.target.value) })}
      619                      className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
      620 +                    title="Maksimalt antal nye tags før eskalering (1-20). Højt tal = mere lokal autonomy. Typisk 3-10."                                 
      621                    />
      622                  </div>
      623                </div>
     ...
      625  
      626              {/* Vocab limit */}
      627              <div className="space-y-1.5">
      624 -              <label className="text-xs text-slate-400 font-medium uppercase tracking-wider">                                                            
      628 +              <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Maksimalt antal tags i AI prompt for at begrænse toke
          +n forbrug og øge hastighed. Færre tags = hurtigere analyse. 372 = fulde vokabular (alle tags). Typisk 100-300 for balance mellem hastighed og dækning."> 
      629                  Max tags i prompt (performance)
      630                </label>
      631                <input
     ...
      633                  value={editing.tag_vocabulary_limit}
      634                  onChange={e => setEditing({ ...editing, tag_vocabulary_limit: parseInt(e.target.value) })}
      635                  className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
      636 +                title="Max tags i prompt (20-372). Færre = hurtigere analyse. 372 = alle tags. Typisk 100-300."                                          
      637                />
      638                <p className="text-xs text-slate-500">Færre = hurtigere. 372 = alle tags</p>
      639              </div>
      640  
      641              {/* Enabled */}
      642              <div className="flex items-center justify-between">
      638 -              <span className="text-sm text-slate-300">AI aktiveret for denne kunde</span>                                                               
      643 +              <span className="text-sm text-slate-300" title="Aktiver AI tag analyse for denne kunde. Når deaktiveret, springes AI analyse over og captur
          +es markeres manuelt eller uden tags. Kan bruges til at pause AI eller kunder der ikke ønsker automatisk tagning.">AI aktiveret for denne kunde</span>    
      644                <button
      645                  onClick={() => setEditing({ ...editing, enabled: !editing.enabled })}
      646                  className={`w-11 h-6 rounded-full transition-colors ${editing.enabled ? 'bg-violet-600' : 'bg-gray-700'}`}
      647 +                title="Klik for at toggle AI aktivering for denne kunde"                                                                                 
      648                >
      649                  <div className={`w-4 h-4 rounded-full bg-white mx-auto transition-transform ${editing.enabled ? 'translate-x-2.5' : '-translate-x-2.5'}`}
            />
      650                </button>

  Thought for 3s (ctrl+o to expand)

⏺ AIPage er færdig! Tester UI build:
     
⏺ Bash(npm run build 2>&1 | tail -10)
  ⎿  dist/assets/index-UgJfhHRQ.js   1,417.31 kB │ gzip: 366.56 kB
     
     [INEFFECTIVE_DYNAMIC_IMPORT] Warning: src/api/client.ts is dynamically imported by src/pages/DevicePage.tsx, src/pages/LabPage.tsx, src/pages/LoginPage.tsx, src/
     … +9 lines (ctrl+o to expand)

  Thought for 4s (ctrl+o to expand)

⏺ ✅ AIPage færdig! Opdaterer task status:
     
  Thought for 3s (ctrl+o to expand)

⏺ Nu scanner jeg CameraPage og DevicePage for parametre:
     
  Thought for 9s, read 2 files (ctrl+o to expand)

⏺ CameraPage og DevicePage begge har konfigurationsparametre! CameraPage har allerede descriptions - jeg skal blot tilføje tooltips. Lad mig starte:

⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/CameraPage.tsx)
  ⎿  Error editing file

  Thought for 6s (ctrl+o to expand)

⏺ Lad mig læse specifikke sektion for at finde den præcise tekst:
     
  Thought for 5s, read 1 file (ctrl+o to expand)

⏺ Først skal jeg opdatere ParamRow interface til at inkludere tooltip felt:

⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/CameraPage.tsx)
  ⎿  Added 1 line
      70    unit?: string
      71    placeholder?: string
      72    description?: string
      73 +  tooltip?: string                                                                                                                                        
      74  }
      75   
      76  interface DriftDimension {

  Thought for 5s (ctrl+o to expand)

⏺ Nu opdaterer jeg CAMERA_PARAMS array med tooltips. Lad mig gøre det i sektioner:
     
⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/CameraPage.tsx)
  ⎿  Added 2 lines, removed 2 lines
      107  
      108  const CAMERA_PARAMS: ParamRow[] = [
      109    // Optagelse
      110 -  { key: 'schedule.interval_minutes', label: 'Optagelsesinterval', section: 'Optagelse', type: 'number', unit: 'min', placeholder: '60', description: 'Mi
          -nutter mellem hvert billede' },                                                                                                                          
      111 -  { key: 'schedule.capture_mode',     label: 'Tilstand', section: 'Optagelse', type: 'select', options: ['interval', 'fixed_times'], description: 'Interv
          -al = hvert N min, Fixed = faste tidspunkter' },                                                                                                          
      110 +  { key: 'schedule.interval_minutes', label: 'Optagelsesinterval', section: 'Optagelse', type: 'number', unit: 'min', placeholder: '60', description: 'Mi
          +nutter mellem hvert billede', tooltip: 'Minutter mellem captures. 60 = et billede i minuttet, 10 = hvert 10. minut. Kortere interval = flere billeder men
          + mere disk/usage. Typisk 10-120 minutter.' },                                                                                                            
      111 +  { key: 'schedule.capture_mode',     label: 'Tilstand', section: 'Optagelse', type: 'select', options: ['interval', 'fixed_times'], description: 'Interv
          +al = hvert N min, Fixed = faste tidspunkter', tooltip: 'Interval tager billeder med fast mellemrum. Fixed tager billeder på specifikke tidspunkter (fx 08
          +:00, 12:00, 16:00). Koordineres på tværs af kameraer på samme site.' },                                                                                  
      112    // Kamera
      113    { key: 'camera.iso',               label: 'ISO', section: 'Kamera', type: 'select', options: ['Auto', '100', '200', '400', '800', '1600', '3200', '6400
           '], description: 'Lysfølsomhed — Auto anbefales til varierende lys' },
      114    { key: 'camera.shutter_speed',     label: 'Lukkerhastiged', section: 'Kamera', type: 'select', options: ['Auto', '1/4000', '1/2000', '1/1000', '1/500',
            '1/250', '1/125', '1/60', '1/30', '1/15', '1/8', '1/4', '1/2', '1'], description: 'Eksponeringstid i sekunder' },

  Thought for 5s (ctrl+o to expand)

⏺ Fortsætter med at opdatere CAMERA_PARAMS array i batches. Nu Kamera sektionen:
     
⏺ Update(~/projects/timelapse-pro/timelapse-ui/src/pages/CameraPage.tsx)
  ⎿  Added 5 lines, removed 5 lines
      110    { key: 'schedule.interval_minutes', label: 'Optagelsesinterval', section: 'Optagelse', type: 'number', unit: 'min', placeholder: '60', description: 'Mi
           nutter mellem hvert billede', tooltip: 'Minutter mellem captures. 60 = et billede i minuttet, 10 = hvert 10. minut. Kortere interval = flere billeder men
            mere disk/usage. Typisk 10-120 minutter.' },
      111    { key: 'schedule.capture_mode',     label: 'Tilstand', section: 'Optagelse', type: 'select', options: ['interval', 'fixed_times'], description: 'Interv
           al = hvert N min, Fixed = faste tidspunkter', tooltip: 'Interval tager billeder med fast mellemrum. Fixed tager billeder på specifikke tidspunkter (fx 08
           :00, 12:00, 16:00). Koordineres på tværs af kameraer på samme site.' },
      112    // Kamera
      113 -  { key: 'camera.iso',               label: 'ISO', section: 'Kamera', type: 'select', options: ['Auto', '100', '200', '400', '800', '1600', '3200', '6400
          -'], description: 'Lysfølsomhed — Auto anbefales til varierende lys' },                                                                                   
      114 -  { key: 'camera.shutter_speed',     label: 'Lukkerhastiged', section: 'Kamera', type: 'select', options: ['Auto', '1/4000', '1/2000', '1/1000', '1/500',
          - '1/250', '1/125', '1/60', '1/30', '1/15', '1/8', '1/4', '1/2', '1'], description: 'Eksponeringstid i sekunder' },                                       
      115 -  { key: 'camera.aperture',          label: 'Blænde', section: 'Kamera', type: 'select', options: ['Auto', '3.5', '4', '4.5', '5', '5.6', '6.3', '7.1', '
          -8', '9', '10', '11', '13', '14', '16', '18', '20', '22'], description: 'f-tal — højere = skarpere baggrund' },                                           
      116 -  { key: 'camera.exposurecompensation', label: 'Eksponeringskompensation', section: 'Kamera', type: 'select', options: ['-2.0', '-1.7', '-1.3', '-1.0', '
          --0.7', '-0.3', '0', '+0.3', '+0.7', '+1.0', '+1.3', '+1.7', '+2.0'], description: 'EV justering. Negativ dæmper direkte sol/refleks, positiv hjælper mørk
          -e billeder' },                                                                                                                                           
      117 -  { key: 'camera.whitebalance',      label: 'Hvidbalance', section: 'Kamera', type: 'select', options: ['Auto', 'Daylight', 'Cloudy', 'Tungsten', 'Fluore
          -scent', 'Flash'], description: 'Auto anbefales til varierende vejr' },                                                                                   
      113 +  { key: 'camera.iso',               label: 'ISO', section: 'Kamera', type: 'select', options: ['Auto', '100', '200', '400', '800', '1600', '3200', '6400
          +'], description: 'Lysfølsomhed — Auto anbefales til varierende lys', tooltip: 'ISO lysfølsomhed. Lav ISO (100-200) = mindre støj men kræver mere lys. Høj
          + ISO (1600+) = kan bruges i mørke men med mere støj. Auto anbefales til varierende vejr.' },                                                             
      114 +  { key: 'camera.shutter_speed',     label: 'Lukkerhastiged', section: 'Kamera', type: 'select', options: ['Auto', '1/4000', '1/2000', '1/1000', '1/500',
          + '1/250', '1/125', '1/60', '1/30', '1/15', '1/8', '1/4', '1/2', '1'], description: 'Eksponeringstid i sekunder', tooltip: 'Eksponeringstid. Hurtig (1/100
          +0+) fryser bevægelse men kræver meget lys. Langsom (1/15) kan give motion blur i mørke. Auto anbefales til timelapse.' },                                
      115 +  { key: 'camera.aperture',          label: 'Blænde', section: 'Kamera', type: 'select', options: ['Auto', '3.5', '4', '4.5', '5', '5.6', '6.3', '7.1', '
          +8', '9', '10', '11', '13', '14', '16', '18', '20', '22'], description: 'f-tal — højere = skarpere baggrund', tooltip: 'Blændeåbning (f-tal). Lav f-tal (3
          +.5-5.6) = sløret baggrund (bokeh). Høj f-tal (11-22) = skarpe forgrund og baggrund. Påvirker også hvor meget lys der kommer ind.' },                     
      116 +  { key: 'camera.exposurecompensation', label: 'Eksponeringskompensation', section: 'Kamera', type: 'select', options: ['-2.0', '-1.7', '-1.3', '-1.0', '
          +-0.7', '-0.3', '0', '+0.3', '+0.7', '+1.0', '+1.3', '+1.7', '+2.0'], description: 'EV justering. Negativ dæmper direkte sol/refleks, positiv hjælper mørk
          +e billeder', tooltip: 'EV (exposure value) kompensation. Negativ (-1 til -2) dæmper direkte sol og refleks. Positiv (+0.3 til +1) hjælper mørke scener. A
          +utogen values for perioder med ekstremt lys.' },                                                                                                         
      117 +  { key: 'camera.whitebalance',      label: 'Hvidbalance', section: 'Kamera', type: 'select', options: ['Auto', 'Daylight', 'Cloudy', 'Tungsten', 'Fluore
          +scent', 'Flash'], description: 'Auto anbefales til varierende vejr', tooltip: 'Hvidbalance indstilling. Auto tilpasser sig vejr og lysforhold. Daylight t
          +il solrige dage. Cloudy til overskyet vejr. Bruges til at undgå orange/blue farvestik.' },                                                               
      118    { key: 'camera.serial_number',     label: 'Kamera serienummer', section: 'Hardware', type: 'text', placeholder: 'fx d12b869bf88a4b719094a801bdaa41c7',
           description: 'gphoto2 serienummer — bruges til stabil USB port identificering ved multi-kamera' },
      119    { key: 'camera.power_mode',        label: 'Strømstyring', section: 'Hardware', type: 'select', options: ['relay', 'usb_powered'], description: 'relay =
            agenten tænder/slukker via GPIO; usb_powered = kameraet har konstant strøm og går selv i standby' },
      120    { key: 'camera.relay_gpio_pin',    label: 'Relay GPIO (kamera)', section: 'Hardware', type: 'number', placeholder: '356', description: 'GPIO pin til ka
           mera relay' },

⏺ API Error: The model has reached its context window limit.

✻ Crunched for 5m 3s
     
  11 tasks (2 done, 2 in progress, 7 open)
  ◼ Add tooltips to CameraPage parameters › blocked by #16
  ◼ Add tooltips to DevicePage parameters › blocked by #16
  ◻ Add tooltips to all UI pages
  ◻ Add tooltips to Site/Customer pages
  ◻ Add tooltips to Admin pages (Users/Keys/Notifications)
   … +4 pending, 2 completed
