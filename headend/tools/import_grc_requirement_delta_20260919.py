#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"headend"))
from database import GrcEvidence,GrcItem,SessionLocal
ACTOR="chatgpt-grc-consolidation-20260919"
SRC="doc://Dokumentation/HANDOVER_LOG.md#2026-09-19"
REQS=[
("SF-033","system_functional","Krav","UI og CLI for samme operation SKAL anvende samme authoritative service/tool implementation.","Delvist / kendt gap","P0","UI/CLI findes; Edge CLI har observerede fejl og mulig divergent execution path.","UI↔CLI parity audit og konsolidering mod fælles service/tool."),
("SF-034","system_functional","Krav","Edge Servicetekniker UI og CLI SKAL bruge samme Service Operations/HAL path.","Delvist / fejl observeret","P0","Service Operations/HAL findes; CLI-fejl er observeret.","Inventarér technician operations: SAME CORE / DIVERGENT / BROKEN / MISSING."),
("SF-035","system_functional","Krav","Headend LAB UI og LAB CLI SKAL bruge samme LAB/domain operation path.","Skal verificeres","P1","LAB UI/CLI findes i den operative model.","Parity audit på Headend LAB operations."),
("SF-036","system_functional","Krav","Validering, permissions, safety interlocks, locks, timeout og cleanup SKAL være fælles for UI og CLI og må ikke duplikeres pr. interface.","Skal verificeres","P0","Fælles service-lag findes for dele af systemet.","Contract-/architecture-test for fælles enforcement."),
("SF-037","system_functional","Krav","Samme operation og input via UI og CLI SKAL give semantisk samme operation, resultat og error classification.","Mangler contract-test","P1","Ingen samlet parity evidence.","Tilføj UI↔CLI contract tests."),
("SF-038","system_functional","Krav","Service operations SKAL have machine-readable resultat og exit/status-semantik, så CLI, UI, audit og automation fortolker udfald ens.","Delvist / skal verificeres","P1","Flere operations returnerer strukturerede resultater; ikke samlet verificeret.","Standardisér operation result contract."),
("SF-039","system_functional","Krav","Audit SKAL registrere samme operation/action-id og outcome uanset om operationen initieres fra UI eller CLI.","Delvist","P1","Auditmekanismer findes; cross-interface correlation er ikke samlet verificeret.","Indfør/verificér fælles action-id og audit correlation."),
("SF-040","system_functional","Arkitektur-invariant","En service capability må kun implementeres ét authoritative sted; UI/CLI/API er adapters og må ikke være alternative implementations.","Delvist / arkitekturdrift mistænkt","P0","Fælles service-lag findes; CLI-fejl tyder på mulig divergens.","Architecture parity audit og fjern duplikerede execution paths."),
("SF-041","system_functional","Krav","Edge SKAL via Bluetooth kunne annoncere device-navn, aktuelt management-SSID og management-IPv4 som DEVICE_SSID_IP i både Wi-Fi client mode og autonom service-AP mode; navnet skal opdateres ved state/IP/SSID-skift.","Planlagt / ikke implementeret","P0","Bluetooth management og autonom AP findes; DEVICE_SSID_IP-format er nyt krav.","Implementér via fælles authoritative network-status service; test client/AP transitions og BlueZ længdegrænser."),
("SNF-037","system_nonfunctional","Krav","Interface parity / single execution path: en capability må ikke være healthy via UI og defekt via CLI på grund af divergent implementation; outcome skal bestemmes af fælles underliggende service.","Kendt gap","P0","Edge CLI har observerede fejl, mens tilsvarende UI-funktioner findes.","Parity metrics/tests og architecture enforcement."),
]
def main():
 db=SessionLocal();created=updated=0
 try:
  for rid,cat,kind,stmt,impl,pri,evidence,gap in REQS:
   item=db.query(GrcItem).filter_by(item_type="requirement",external_id=rid).first()
   attrs={"category":cat,"requirement_kind":kind,"implementation_status":impl,"current_evidence_summary":evidence,"gap_next_step":gap,"source_rationale":"Peter requirement 2026-09-19","register_date":"2026-09-19"}
   if item is None:
    item=GrcItem(item_type="requirement",external_id=rid,title=f"{rid}: {stmt}"[:300],description=stmt,status="active",priority=pri.lower(),source="import_grc_requirement_delta_20260919.py",scope={"product":"timelapse-pro","category":cat},attributes=attrs,created_by=ACTOR,updated_by=ACTOR);db.add(item);db.flush();created+=1
   else:
    item.title=f"{rid}: {stmt}"[:300];item.description=stmt;item.status="active";item.priority=pri.lower();item.scope={"product":"timelapse-pro","category":cat};item.attributes=attrs;item.updated_by=ACTOR;updated+=1
   if db.query(GrcEvidence).filter_by(item_id=item.id,uri=SRC).first() is None:
    db.add(GrcEvidence(item_id=item.id,evidence_type="source_evidence",title="Peter requirement clarification 2026-09-19",uri=SRC,collected_by=ACTOR,retention_class="grc_standard"))
  db.commit()
  ids=[r[0] for r in REQS];n=db.query(GrcItem).filter(GrcItem.item_type=="requirement",GrcItem.external_id.in_(ids)).count()
  print(f"Requirement delta: {created} created, {updated} updated; read-back {n}/{len(ids)}")
  if n!=len(ids): raise SystemExit("Read-back failed")
 except Exception:
  db.rollback();raise
 finally: db.close()
if __name__=="__main__": main()
