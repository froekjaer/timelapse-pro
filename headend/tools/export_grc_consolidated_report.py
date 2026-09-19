#!/usr/bin/env python3
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"headend"))
from database import GrcItem,SessionLocal
OUT=ROOT/"Dokumentation"/"GRC_CONSOLIDATED_REQUIREMENTS_SECURITY_READINESS.md"
CATS=[("photo_functional","Foto — Functional"),("photo_nonfunctional","Foto — Nonfunctional"),("system_functional","System — Functional"),("system_nonfunctional","System — Nonfunctional")]
def esc(v): return str(v or "").replace("|","\\|").replace("\n"," ")
def main():
 db=SessionLocal()
 try:
  reqs=db.query(GrcItem).filter_by(item_type="requirement").all();findings=db.query(GrcItem).filter(GrcItem.item_type.in_(["finding","risk"])).all();bycat=defaultdict(list)
  for r in reqs: bycat[(r.attributes or {}).get("category","uncategorized")].append(r)
  impl=Counter((r.attributes or {}).get("implementation_status","Ukendt") for r in reqs);openf=[f for f in findings if (f.status or "").lower() not in {"closed","resolved","accepted","superseded"}]
  lines=["# TimeLapse Pro — Consolidated Requirements, Cybersecurity & Readiness Report","",f"**Generated from GRC:** {datetime.now(timezone.utc).isoformat()}","","> GRC-snapshot. Kravets lifecycle-status og implementerings-/verifikationsstatus er forskellige dimensioner. active betyder gældende krav — ikke implementeret eller verificeret.","","## Executive snapshot","",f"- Requirements i GRC: **{len(reqs)}**",f"- Open findings/risks: **{len(openf)}**",f"- Critical open: **{sum(1 for f in openf if (f.priority or '').lower()=='critical')}**",f"- High open: **{sum(1 for f in openf if (f.priority or '').lower()=='high')}**","","### Implementeringsstatus",""]
  for k,v in sorted(impl.items(),key=lambda x:(-x[1],x[0])): lines.append(f"- {k}: {v}")
  for key,title in CATS:
   lines+=["",f"## {title}","","| ID | Krav | Implementeringsstatus | Evidens/status | Gap / næste skridt | Pri. |","|---|---|---|---|---|---|"]
   for r in sorted(bycat[key],key=lambda x:x.external_id or ""):
    a=r.attributes or {};lines.append(f"| {esc(r.external_id)} | {esc(r.description)} | {esc(a.get('implementation_status'))} | {esc(a.get('current_evidence_summary'))} | {esc(a.get('gap_next_step'))} | {esc(r.priority).upper()} |")
  lines+=["","## Open cybersecurity / risk findings","","| ID | Type | Finding | Status | Priority |","|---|---|---|---|---|"];rank={"critical":0,"high":1,"medium":2,"low":3}
  for f in sorted(openf,key=lambda x:(rank.get((x.priority or "").lower(),9),x.external_id or "")): lines.append(f"| {esc(f.external_id)} | {esc(f.item_type)} | {esc(f.title)} | {esc(f.status)} | {esc(f.priority).upper()} |")
  lines+=["","## Governance note","","Rapporten er et GRC-snapshot og er ikke i sig selv compliance-bevis. Implementering, runtime-verifikation, outcome-verifikation og retained evidence skal spores separat.",""];OUT.write_text("\n".join(lines),encoding="utf-8");print(OUT)
 finally: db.close()
if __name__=="__main__": main()
