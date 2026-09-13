# Evidensbilag KIMI-03 — frossen branchmåling 2026-09-13

**Tilknytning:** Bilag til `KIMI_REVIEW_PAKKE_GOVERNANCE_2026-09-13.md`, fund KIMI-03.
**Måletidspunkt (UTC):** 2026-09-13T08:25:46Z (frys af `git fetch origin --prune` umiddelbart før).
**Base-SHA (origin/main):** `13a0d3b3af67a36adf9115d0911aaf2a687bca15` (reviewbasen for PR #231).
**Population:** 124 remote refs inkl. `origin/main` og ét HEAD-alias (se nedenfor); 123 klassificerede linjer.

## Metode (reproducerbar)

1. `git fetch origin --prune` (frys af remote-tilstand).
2. `git for-each-ref --format='%(refname:short) %(objectname)' refs/remotes/origin | grep -v 'origin/HEAD' | sort` → frossen branchliste med head-SHA'er (sektion 1 nedenfor).
3. `origin/main` udelades fra klassificeringen.
4. Pr. branch: `git merge-base --is-ancestor <head> origin/main` → ancestry-merged?
5. Hvis ikke: `git cherry origin/main <head>`; antal `+`-linjer = patches uden patch-ækvivalent i main. 0 `+`-linjer = patch-absorberet; >0 = rest-patches (antal i parentes).
6. Råt klassifikationsoutput: sektion 2 nedenfor (uændret maskinelt output).

**Begrænsninger (uændret fra KIMI-03):** `git cherry` er patch-screening, ikke semantisk bevis. Squash-merges kan efterlade falske rest-patches; indhold reappliceret ad anden vej genkendes ikke. Ingen slettebeslutning må træffes alene på dette grundlag.

## Kendte datakvalitetsnoter

- Den frosne liste indeholder én linje `origin 13a0d3b3…` (HEAD-alias/symref-artefakt fra for-each-ref, samme SHA som main). Den er klassificeret ANCESTRY-MERGED og udgør ikke en selvstændig branch. Den reelle branch-population ekskl. main og alias er 122: 13 ancestry-merged + 109 ikke-merged (51 patch-absorberede + 58 med rest-patches). 51+58=109 ✓.
- Tallene adskiller sig fra min tidligere sweep samme formiddag (127/112/57/56), fordi populationen ændrede sig under den måling (mine 7 branch-sletninger + nye branches fra andre sessioner). Denne måling er taget mod ét fryst tidspunkt og er internt konsistent.

## Sektion 1 — frossen branchliste (refname, head-SHA)

```text
origin 13a0d3b3af67a36adf9115d0911aaf2a687bca15
origin/agent/architecture-governance-v1 dac4cabf03935ebe7df888a74f28099edada856f
origin/agent/codex-edge-conformance-workorder 4e85615d59e1470920023badcd5173f45f64da26
origin/agent/core-design-principles 320281b698c8a0114e2389f3b3f778f2c806573d
origin/agent/edge-reference-architecture-v1 0bbb5a80982ad69127e2d043db83468a9eaa1c07
origin/agent/headend-generator-verification 7e1df21ae2f6b6e766e7c51f373f244096f3b966
origin/assessment/2026-07-3p-review 4766eefa1b629c80a66e8ebad1a3b7787aaf8734
origin/claude/claude-md-docs-mr71ia 230f7c9a0d70f46cb43b19773e05593457b6d37c
origin/claude/globalconfig-parallel-load bed3cf14ce5952843f6688ab331f81f666811db8
origin/claude/pakke-hygiejne-adr 989bcd224074f94d7453fd095477d13597ba7c2f
origin/codex/capture-assignment-metadata f269c012eb87022218b99ba81531c9340bb5b5f2
origin/codex/edge-post-restart-health-handshake 4c0cfba268da35af3b213a1a628ffb5d40cfdfa3
origin/codex/edge-runtime-convergence-docs e6f0c249ff30593f680b637b744269a5a71600c2
origin/codex/edge-terminal-renderer 35ad6cc5d47654c243faec3f0c928e7711237188
origin/codex/edge2-ssh-host-identity-unblocker eb9f2cfdf9b4bd836ff3bb481546d80cc6e7860c
origin/codex/fix-capture-time-and-edge2-evidence eaa0289267f67edd734a7aa28ea18380d4afd0e8
origin/codex/navigation-diagnostics-20260910 05ab2a6c1033d14ed0fc454584bbaf0e2b04eb2a
origin/codex/os-catalog-refresh 918282a2920551c8f0f31041cdb6b9ceeaef8eff
origin/codex/package-governance-review-pack 1e9d53bccd5c322434b4afa952d6133de5722581
origin/codex/reconcile-package-governance 69d8d691a0b219507aad4d96acfeb57f2a578210
origin/codex/security-closure-f001 540daea40138081bbdf0dfdb4de24deee6db8212
origin/codex/security-closure-f005 7de91fad136ac81f3712ce14344d585d31b9905c
origin/codex/ssh-tunnel-ux-convergence 3c58ee769d1074900b9d2425c36de9f88be73453
origin/codex/update-flow-visibility-2026-09-01 ef953420f25331ae9fe4c44069f56115aa133e6f
origin/codex/web-performance 0242d6ac90057d135ce005164584a3c7553fce49
origin/codex/wp4-edge-image-provisioning-clean 0885aded6fb6e5f421dcec58fc925c3ce9866ed3
origin/docs-help-menu fdf0cd9c7ec723deebb597f8c4cb67f9fc04be44
origin/docs-manual-update-process-guide 017de8c48b7116a896aa5d251153f14a50908515
origin/docs/claude-review-2026-08-15 df02e405cb9ae4971320ce6d868c05ba4afd598b
origin/docs/claude-update-flow-review-2026-08-16 49ce292db2a76ce21cbab8d75eaad76777a7f616
origin/docs/handover-2026-08-16-update-lifecycle 99e3f939721346e44a24cb44974f3e96635d30e9
origin/docs/handover-admin-settings-extraction 314ad2b9be3090afc2c127fec305c058ac953361
origin/docs/handover-ai-batch-extraction 45d26723e080abbb99150222fb385b2189c7b68e
origin/docs/handover-auth-extraction 628a9b8b36955629369485cb48e0b04872e3ab22
origin/docs/handover-breakglass-chown 9656a10dca88b32e173b9cca234fe0462766ac6c
origin/docs/handover-breakglass-drop-script-relay 33e2de7cad233e4ddf3b1a800eb811c31427c3d9
origin/docs/handover-breakglass-rechown fc0985a8f514a247b27b1b21db9dc5799cc021e5
origin/docs/handover-cameras-extraction 5803b42d6d8bc638bcb038bfa4b20c48505b68d9
origin/docs/handover-checkout-no-rotate 4988d2d581a0cb31473b754a7bd2557ca9d5cab0
origin/docs/handover-edge-disk-image-extraction 7044687b81271b6a3fbef664926db7e58212ab19
origin/docs/handover-etc-sandbox-fix 3cbd576e7fbae8a2de5b6b43d93a3c12297a868b
origin/docs/handover-navdiag 78aeea61341b338204cb3825150e9aab062e1902
origin/docs/handover-tooltips-2026-08-26 6d4fc098dc6dfcaf3d817376e7c9cb8a1817fb25
origin/docs/headend-modularization-status 4066d685c920d0248f2eebcc241faed8a844789e
origin/docs/kimi-grc-afventer-2026-08-19 8f4ef2bb7d2a22f7c6ea0bf0275248c523b80c9f
origin/docs/kimi-grc-opdateret-2026-08-23 e4c769c494ba7f156bbdea9168e9798d5fbe6efa
origin/docs/kimi-handover-2026-08-20 af2f7d6ec3d6dbe92166e89a5976fbcc646c89f2
origin/docs/kimi-handover-2026-08-23 9aa9d0e97a8c0c3a83388db8136584ec0adb9547
origin/docs/kimi-handover-2026-08-23b 7f982662293ea3febc7cd0b035707851b4c5e50d
origin/docs/kimi-handover-2026-08-23c 569a0246c383c02745d2cf138ee86947028b142c
origin/docs/kimi-menu-guides-2026-08-20 b8a49cc6a7d9bc157d00ea9104543840f289569a
origin/docs/kimi-review-2026-08-15 aac5128c7301e42ee87b89b6e5f5bc192642843b
origin/docs/master-review-closure-2026-08-15 af7166d28d41e82bef4b2d25e2559833fbf5726c
origin/docs/reviews-2026-08-15 df02e405cb9ae4971320ce6d868c05ba4afd598b
origin/docs/update-flow-review-2026-08-16 43c0741d664035f40311b265970e418ae1cb4427
origin/feat/edge-safe-uploaded-file-cleanup-2026-08-20 2333a580bac389a98c2d508384e902005f0afdd9
origin/feat/ui-help-tooltips-2026-08-24 43d084f970234c3b3a40f73a1c4b690aae00add5
origin/feature-camera-hardware-cmdb c0ce52cc44ef1857fb1ed8fe6842c20d44eaeb76
origin/feature-cmdb-version-visibility 055f635ffac12f7ecbd1372ba6823b04c97bbd55
origin/feature-edge-comm-capture-sessions 2898170c10e96d35219d7c79d374b076efa37d2f
origin/feature-edge-comm-clear-list 281068ede13c36e07100c93c74cde80928243489
origin/feature-python-dependency-updates 5843ac97948aa95b9c5fe5dea93d19eeac02ff20
origin/feature-redaction-image-preview 125d4284a2278909b6d88762f5809c8ce09e6589
origin/feature-update-governance-hardening 41245d51095be34816233c385c3df49dd75566f8
origin/feature/device-identity-dropdowns-2026-08-16 235286fc13f473aa8670fcc68bc96413e64e756a
origin/feature/exposure-ramping-2026-08-16 1abe27073b1524c9dcc2a3aa89448d8fd683754f
origin/feature/framework-v1-contracts 934d7380dc396f4160d71d84a620395f357b69bd
origin/feature/legacy-backlog-qa-backfill-2026-08-16 ed152630c60e418e98b3a10d7c30859879da3a30
origin/feature/legacy-backlog-sweep-2026-08-16 619931c563520303acdfb2754eed058f5329fdde
origin/feature/tpa-00-commissioner-auth d266eb1721d4dca9fd66e8a815dc3962ec362844
origin/fix-edge-venv-packages-reporting 7c8fb93a3f8218bcff6fdb0a4381a046782dedff
origin/fix-ordered-offline-apt-install 49055da60739025cfa7439eb042d936b897c859e
origin/fix-os-bundle-plan-packages 277a552c0f681a00f6cd99059e9ad37063204add
origin/fix-os-catalog-refresh-automation 4a4129db6668ffa947fb9af07ae7ca3f32a9a8c4
origin/fix-resolution-reason-reblock-gap 829b3f7e6134008ce302ccc5d9aec7520d73e4b1
origin/fix-totp-policy-poll-gating 885ffd763e78d2b56c94019242c9ab7da57b38a1
origin/fix/bootstrap-cli-permission-error-2026-08-16 07ed1b30a089648a56c7b3f512f1d924ba892e78
origin/fix/breakglass-checkout-no-auto-rotate 774bcad58ce7a6915d936cfb6b2ff6fdafb56888
origin/fix/breakglass-drop-script-pty-relay e2ee126cb95b085eb4de8b9391e9e4fa752de36f
origin/fix/breakglass-events-file-rechown 922644c45c46b0371205c5169d3b8a122a6f5d1e
origin/fix/breakglass-log-dir-ownership 3b28bbd040c7720ddb6b0ccefdaf4a9c378f46ca
origin/fix/edge-headend-health-url 540807f6e3cdb4519f3c011b6046f0d26daf84e4
origin/fix/edge-post-restart-health-rollback a289393da37b6876a907de0e9291543c6bc863c0
origin/fix/grant-full-etc-sandbox-access c85bf8ebbaa9f1dc1d0aa28101fcf6be2d7bc4d3
origin/fix/headend-client-retry-health 75747120488e1124ef2d8a548cdff1fa1ec848e7
origin/fix/missing-resolve-session-policy-import b294bf0212ca88d27753a26b2b3b4e0940d0bfbb
origin/fix/sftp-upload-attempt-ledger c1f9f5f354ae48c1fe916a6df08e6d8b0c374791
origin/fix/ssh-host-trust-legacy-migration 6e5e8fe03a4e78cd4a1503a85a19a77ac2b7b675
origin/fix/ssh-terminal-visible-button 32bcf56e1e43367bcae593c5d84faf6c5fb4d215
origin/fix/ssh-tunnel-stderr-drain 037f6f137d23140dd933ba8c716ab09023a4aa40
origin/fix/trust-deploy-secret-migration 88e77a0408f9fef4add3e1d820bec166c532226b
origin/fix/update-authority-isolation 07606d8b95c4e1472114fa4e1c69fa201a21c1f4
origin/fix/update-rollback-idempotency 0093c2a7327a921057efc7627ee4831bd19d6d6c
origin/investigate-camera-image-delay a8f64bbfa2e9efb6159e96c7ce4d374b83cc941a
origin/kimi/pakke-hygiejne-sweep-20260913 49ec2765e101170a4a6d97f35ce8021de57ef533
origin/main 13a0d3b3af67a36adf9115d0911aaf2a687bca15
origin/ops/recover-macmini-deploy-checkout-2026-08-16 dad0879ab199726eb909fb9737df1c5616198a35
origin/refactor/extract-admin-settings 1a0cbb9297000bc3c1cc370d42da84f551e29259
origin/refactor/extract-ai-ops-batch c819dafeb4a82b4c80165201656bbe1bca4e1320
origin/refactor/extract-auth-module eff83832cbac84f53d5bc145b870eaaf7bac8b50
origin/refactor/extract-cameras b767e4c9a71e025f3a1035c1edda5478121613dd
origin/refactor/extract-edge-provisioning 1f51362c28fdde9cc858b77b0bb9ac90eec0e850
origin/security/close-os-update-governance-bypass 5ca63d077272ab78a9d71e7df6b9615df8fe3339
origin/security/closure-assign-site-tenant-rbac b3ccde3f0438f16b5a11b5c9ddb5874aa844d970
origin/security/closure-e2e-test-hardening 76ea03d975d2d74601b71108f9a8d72fb37e3aec
origin/security/closure-e2e-test-hardening-current cf83cd06f9c257db711c00387b88adcc07e6fd79
origin/security/closure-edge-ssh-private-key-ownership 51d1690ddd393ab5ad32dd3610db26573d2273d1
origin/security/closure-headend-deploy-integrity 0b1415128411b490c21a1b5e527cd851a591f244
origin/security/closure-headend-deploy-integrity-current c4ec3548dac8bfd4f4895f9b9aa0ce4e219e3d63
origin/security/closure-headend-deploy-integrity-final 34e63ada55d519113384a7ae91d19cd654e9b992
origin/security/closure-mainpy-p0-f001 4c4aa28f8c557be4c5a55e16c26b1f5f0141df0d
origin/security/closure-os-builder-f002 342854b969e40659f6659000fb970b66516f9a69
origin/security/closure-real-artifact-signature-verification d384d1d67619f8433d928f05bc98ae96426061d4
origin/security/closure-sftp-host-trust 307b4c48e3afbb0d1be827d6b072de09ef7ac290
origin/security/closure-technician-auth-xss d5e5f2db4b2d3efd628208371520d510dd1ef219
origin/security/closure-test-target-isolation 40e0dda7e086d560f666e1ee03925859fcd709b7
origin/security/closure-test-target-isolation-current 0b616709f9ba9d1048cad83255920d0886d7428e
origin/security/closure-trust-grant-evidence 112ed8c087dc2112cc14e9100db72ba17144f62a
origin/security/closure-unused-passlib 2a3447c0f22bbd47058a5e66f579772d9a3e8bbf
origin/security/closure-update-authority-h123 16bd9641e75360ed1c7eeae0541aaecc61e7e4e2
origin/security/closure-update-authority-h123-ci 5e1272c4ab7899ade129e63ad9b513dd9d3994eb
origin/security/closure-update-type-trust-gate 356959a5e6664d8fc66d8c6f6a59caa71f98232b
origin/security/closure-zai-critical-redaction ca44af0b343d476580659cebc9a22535f536a0b9
origin/security/os-update-governance-closure 33ecac26373acc3e736ff78dc9ff5fcfd4dc9d33
```

## Sektion 2 — råt klassifikationsoutput (refname, head-SHA, status)

`ANCESTRY-MERGED` = head er ancestor af main. `NOTMERGED-ABSORBED` = ikke ancestor, men 0 unikke patches ifølge `git cherry`. `NOTMERGED-REST(n)` = n patches uden patch-ækvivalent i main (screening — kræver per-branch ADR-003-vurdering).

```text
origin 13a0d3b3af67a36adf9115d0911aaf2a687bca15 ANCESTRY-MERGED
origin/agent/architecture-governance-v1 dac4cabf03935ebe7df888a74f28099edada856f NOTMERGED-REST(3)
origin/agent/codex-edge-conformance-workorder 4e85615d59e1470920023badcd5173f45f64da26 NOTMERGED-REST(1)
origin/agent/core-design-principles 320281b698c8a0114e2389f3b3f778f2c806573d NOTMERGED-REST(1)
origin/agent/edge-reference-architecture-v1 0bbb5a80982ad69127e2d043db83468a9eaa1c07 NOTMERGED-REST(2)
origin/agent/headend-generator-verification 7e1df21ae2f6b6e766e7c51f373f244096f3b966 NOTMERGED-REST(1)
origin/assessment/2026-07-3p-review 4766eefa1b629c80a66e8ebad1a3b7787aaf8734 NOTMERGED-REST(2)
origin/claude/claude-md-docs-mr71ia 230f7c9a0d70f46cb43b19773e05593457b6d37c NOTMERGED-REST(1)
origin/claude/globalconfig-parallel-load bed3cf14ce5952843f6688ab331f81f666811db8 NOTMERGED-REST(1)
origin/claude/pakke-hygiejne-adr 989bcd224074f94d7453fd095477d13597ba7c2f NOTMERGED-REST(1)
origin/codex/capture-assignment-metadata f269c012eb87022218b99ba81531c9340bb5b5f2 NOTMERGED-ABSORBED
origin/codex/edge-post-restart-health-handshake 4c0cfba268da35af3b213a1a628ffb5d40cfdfa3 NOTMERGED-REST(1)
origin/codex/edge-runtime-convergence-docs e6f0c249ff30593f680b637b744269a5a71600c2 NOTMERGED-REST(1)
origin/codex/edge-terminal-renderer 35ad6cc5d47654c243faec3f0c928e7711237188 NOTMERGED-REST(48)
origin/codex/edge2-ssh-host-identity-unblocker eb9f2cfdf9b4bd836ff3bb481546d80cc6e7860c NOTMERGED-REST(1)
origin/codex/fix-capture-time-and-edge2-evidence eaa0289267f67edd734a7aa28ea18380d4afd0e8 NOTMERGED-REST(1)
origin/codex/navigation-diagnostics-20260910 05ab2a6c1033d14ed0fc454584bbaf0e2b04eb2a NOTMERGED-ABSORBED
origin/codex/os-catalog-refresh 918282a2920551c8f0f31041cdb6b9ceeaef8eff NOTMERGED-REST(17)
origin/codex/package-governance-review-pack 1e9d53bccd5c322434b4afa952d6133de5722581 NOTMERGED-REST(1)
origin/codex/reconcile-package-governance 69d8d691a0b219507aad4d96acfeb57f2a578210 NOTMERGED-ABSORBED
origin/codex/security-closure-f001 540daea40138081bbdf0dfdb4de24deee6db8212 NOTMERGED-REST(1)
origin/codex/security-closure-f005 7de91fad136ac81f3712ce14344d585d31b9905c NOTMERGED-REST(1)
origin/codex/ssh-tunnel-ux-convergence 3c58ee769d1074900b9d2425c36de9f88be73453 ANCESTRY-MERGED
origin/codex/update-flow-visibility-2026-09-01 ef953420f25331ae9fe4c44069f56115aa133e6f NOTMERGED-REST(2)
origin/codex/web-performance 0242d6ac90057d135ce005164584a3c7553fce49 NOTMERGED-ABSORBED
origin/codex/wp4-edge-image-provisioning-clean 0885aded6fb6e5f421dcec58fc925c3ce9866ed3 NOTMERGED-REST(2)
origin/docs-help-menu fdf0cd9c7ec723deebb597f8c4cb67f9fc04be44 NOTMERGED-REST(4)
origin/docs-manual-update-process-guide 017de8c48b7116a896aa5d251153f14a50908515 NOTMERGED-ABSORBED
origin/docs/claude-review-2026-08-15 df02e405cb9ae4971320ce6d868c05ba4afd598b ANCESTRY-MERGED
origin/docs/claude-update-flow-review-2026-08-16 49ce292db2a76ce21cbab8d75eaad76777a7f616 ANCESTRY-MERGED
origin/docs/handover-2026-08-16-update-lifecycle 99e3f939721346e44a24cb44974f3e96635d30e9 NOTMERGED-REST(3)
origin/docs/handover-admin-settings-extraction 314ad2b9be3090afc2c127fec305c058ac953361 NOTMERGED-ABSORBED
origin/docs/handover-ai-batch-extraction 45d26723e080abbb99150222fb385b2189c7b68e NOTMERGED-ABSORBED
origin/docs/handover-auth-extraction 628a9b8b36955629369485cb48e0b04872e3ab22 NOTMERGED-ABSORBED
origin/docs/handover-breakglass-chown 9656a10dca88b32e173b9cca234fe0462766ac6c NOTMERGED-ABSORBED
origin/docs/handover-breakglass-drop-script-relay 33e2de7cad233e4ddf3b1a800eb811c31427c3d9 NOTMERGED-ABSORBED
origin/docs/handover-breakglass-rechown fc0985a8f514a247b27b1b21db9dc5799cc021e5 NOTMERGED-ABSORBED
origin/docs/handover-cameras-extraction 5803b42d6d8bc638bcb038bfa4b20c48505b68d9 NOTMERGED-ABSORBED
origin/docs/handover-checkout-no-rotate 4988d2d581a0cb31473b754a7bd2557ca9d5cab0 NOTMERGED-ABSORBED
origin/docs/handover-edge-disk-image-extraction 7044687b81271b6a3fbef664926db7e58212ab19 NOTMERGED-ABSORBED
origin/docs/handover-etc-sandbox-fix 3cbd576e7fbae8a2de5b6b43d93a3c12297a868b NOTMERGED-ABSORBED
origin/docs/handover-navdiag 78aeea61341b338204cb3825150e9aab062e1902 NOTMERGED-ABSORBED
origin/docs/handover-tooltips-2026-08-26 6d4fc098dc6dfcaf3d817376e7c9cb8a1817fb25 NOTMERGED-ABSORBED
origin/docs/headend-modularization-status 4066d685c920d0248f2eebcc241faed8a844789e NOTMERGED-ABSORBED
origin/docs/kimi-grc-afventer-2026-08-19 8f4ef2bb7d2a22f7c6ea0bf0275248c523b80c9f NOTMERGED-ABSORBED
origin/docs/kimi-grc-opdateret-2026-08-23 e4c769c494ba7f156bbdea9168e9798d5fbe6efa NOTMERGED-ABSORBED
origin/docs/kimi-handover-2026-08-20 af2f7d6ec3d6dbe92166e89a5976fbcc646c89f2 NOTMERGED-REST(3)
origin/docs/kimi-handover-2026-08-23 9aa9d0e97a8c0c3a83388db8136584ec0adb9547 NOTMERGED-ABSORBED
origin/docs/kimi-handover-2026-08-23b 7f982662293ea3febc7cd0b035707851b4c5e50d NOTMERGED-ABSORBED
origin/docs/kimi-handover-2026-08-23c 569a0246c383c02745d2cf138ee86947028b142c NOTMERGED-ABSORBED
origin/docs/kimi-menu-guides-2026-08-20 b8a49cc6a7d9bc157d00ea9104543840f289569a NOTMERGED-REST(1)
origin/docs/kimi-review-2026-08-15 aac5128c7301e42ee87b89b6e5f5bc192642843b NOTMERGED-ABSORBED
origin/docs/master-review-closure-2026-08-15 af7166d28d41e82bef4b2d25e2559833fbf5726c NOTMERGED-REST(1)
origin/docs/reviews-2026-08-15 df02e405cb9ae4971320ce6d868c05ba4afd598b ANCESTRY-MERGED
origin/docs/update-flow-review-2026-08-16 43c0741d664035f40311b265970e418ae1cb4427 NOTMERGED-ABSORBED
origin/feat/edge-safe-uploaded-file-cleanup-2026-08-20 2333a580bac389a98c2d508384e902005f0afdd9 NOTMERGED-REST(1)
origin/feat/ui-help-tooltips-2026-08-24 43d084f970234c3b3a40f73a1c4b690aae00add5 NOTMERGED-ABSORBED
origin/feature-camera-hardware-cmdb c0ce52cc44ef1857fb1ed8fe6842c20d44eaeb76 NOTMERGED-REST(2)
origin/feature-cmdb-version-visibility 055f635ffac12f7ecbd1372ba6823b04c97bbd55 NOTMERGED-ABSORBED
origin/feature-edge-comm-capture-sessions 2898170c10e96d35219d7c79d374b076efa37d2f NOTMERGED-REST(2)
origin/feature-edge-comm-clear-list 281068ede13c36e07100c93c74cde80928243489 NOTMERGED-ABSORBED
origin/feature-python-dependency-updates 5843ac97948aa95b9c5fe5dea93d19eeac02ff20 NOTMERGED-ABSORBED
origin/feature-redaction-image-preview 125d4284a2278909b6d88762f5809c8ce09e6589 NOTMERGED-ABSORBED
origin/feature-update-governance-hardening 41245d51095be34816233c385c3df49dd75566f8 NOTMERGED-ABSORBED
origin/feature/device-identity-dropdowns-2026-08-16 235286fc13f473aa8670fcc68bc96413e64e756a ANCESTRY-MERGED
origin/feature/exposure-ramping-2026-08-16 1abe27073b1524c9dcc2a3aa89448d8fd683754f ANCESTRY-MERGED
origin/feature/framework-v1-contracts 934d7380dc396f4160d71d84a620395f357b69bd NOTMERGED-REST(3)
origin/feature/legacy-backlog-qa-backfill-2026-08-16 ed152630c60e418e98b3a10d7c30859879da3a30 ANCESTRY-MERGED
origin/feature/legacy-backlog-sweep-2026-08-16 619931c563520303acdfb2754eed058f5329fdde ANCESTRY-MERGED
origin/feature/tpa-00-commissioner-auth d266eb1721d4dca9fd66e8a815dc3962ec362844 NOTMERGED-REST(4)
origin/fix-edge-venv-packages-reporting 7c8fb93a3f8218bcff6fdb0a4381a046782dedff NOTMERGED-ABSORBED
origin/fix-ordered-offline-apt-install 49055da60739025cfa7439eb042d936b897c859e NOTMERGED-REST(2)
origin/fix-os-bundle-plan-packages 277a552c0f681a00f6cd99059e9ad37063204add NOTMERGED-ABSORBED
origin/fix-os-catalog-refresh-automation 4a4129db6668ffa947fb9af07ae7ca3f32a9a8c4 NOTMERGED-ABSORBED
origin/fix-resolution-reason-reblock-gap 829b3f7e6134008ce302ccc5d9aec7520d73e4b1 NOTMERGED-ABSORBED
origin/fix-totp-policy-poll-gating 885ffd763e78d2b56c94019242c9ab7da57b38a1 NOTMERGED-REST(2)
origin/fix/bootstrap-cli-permission-error-2026-08-16 07ed1b30a089648a56c7b3f512f1d924ba892e78 ANCESTRY-MERGED
origin/fix/breakglass-checkout-no-auto-rotate 774bcad58ce7a6915d936cfb6b2ff6fdafb56888 NOTMERGED-ABSORBED
origin/fix/breakglass-drop-script-pty-relay e2ee126cb95b085eb4de8b9391e9e4fa752de36f NOTMERGED-ABSORBED
origin/fix/breakglass-events-file-rechown 922644c45c46b0371205c5169d3b8a122a6f5d1e NOTMERGED-ABSORBED
origin/fix/breakglass-log-dir-ownership 3b28bbd040c7720ddb6b0ccefdaf4a9c378f46ca NOTMERGED-ABSORBED
origin/fix/edge-headend-health-url 540807f6e3cdb4519f3c011b6046f0d26daf84e4 ANCESTRY-MERGED
origin/fix/edge-post-restart-health-rollback a289393da37b6876a907de0e9291543c6bc863c0 NOTMERGED-REST(11)
origin/fix/grant-full-etc-sandbox-access c85bf8ebbaa9f1dc1d0aa28101fcf6be2d7bc4d3 NOTMERGED-ABSORBED
origin/fix/headend-client-retry-health 75747120488e1124ef2d8a548cdff1fa1ec848e7 NOTMERGED-REST(4)
origin/fix/missing-resolve-session-policy-import b294bf0212ca88d27753a26b2b3b4e0940d0bfbb NOTMERGED-ABSORBED
origin/fix/sftp-upload-attempt-ledger c1f9f5f354ae48c1fe916a6df08e6d8b0c374791 NOTMERGED-REST(3)
origin/fix/ssh-host-trust-legacy-migration 6e5e8fe03a4e78cd4a1503a85a19a77ac2b7b675 ANCESTRY-MERGED
origin/fix/ssh-terminal-visible-button 32bcf56e1e43367bcae593c5d84faf6c5fb4d215 ANCESTRY-MERGED
origin/fix/ssh-tunnel-stderr-drain 037f6f137d23140dd933ba8c716ab09023a4aa40 NOTMERGED-REST(2)
origin/fix/trust-deploy-secret-migration 88e77a0408f9fef4add3e1d820bec166c532226b NOTMERGED-REST(3)
origin/fix/update-authority-isolation 07606d8b95c4e1472114fa4e1c69fa201a21c1f4 NOTMERGED-REST(7)
origin/fix/update-rollback-idempotency 0093c2a7327a921057efc7627ee4831bd19d6d6c NOTMERGED-REST(5)
origin/investigate-camera-image-delay a8f64bbfa2e9efb6159e96c7ce4d374b83cc941a NOTMERGED-ABSORBED
origin/kimi/pakke-hygiejne-sweep-20260913 49ec2765e101170a4a6d97f35ce8021de57ef533 NOTMERGED-REST(2)
origin/ops/recover-macmini-deploy-checkout-2026-08-16 dad0879ab199726eb909fb9737df1c5616198a35 NOTMERGED-REST(3)
origin/refactor/extract-admin-settings 1a0cbb9297000bc3c1cc370d42da84f551e29259 NOTMERGED-ABSORBED
origin/refactor/extract-ai-ops-batch c819dafeb4a82b4c80165201656bbe1bca4e1320 NOTMERGED-ABSORBED
origin/refactor/extract-auth-module eff83832cbac84f53d5bc145b870eaaf7bac8b50 NOTMERGED-ABSORBED
origin/refactor/extract-cameras b767e4c9a71e025f3a1035c1edda5478121613dd NOTMERGED-ABSORBED
origin/refactor/extract-edge-provisioning 1f51362c28fdde9cc858b77b0bb9ac90eec0e850 NOTMERGED-ABSORBED
origin/security/close-os-update-governance-bypass 5ca63d077272ab78a9d71e7df6b9615df8fe3339 NOTMERGED-REST(2)
origin/security/closure-assign-site-tenant-rbac b3ccde3f0438f16b5a11b5c9ddb5874aa844d970 NOTMERGED-REST(9)
origin/security/closure-e2e-test-hardening 76ea03d975d2d74601b71108f9a8d72fb37e3aec NOTMERGED-ABSORBED
origin/security/closure-e2e-test-hardening-current cf83cd06f9c257db711c00387b88adcc07e6fd79 NOTMERGED-ABSORBED
origin/security/closure-edge-ssh-private-key-ownership 51d1690ddd393ab5ad32dd3610db26573d2273d1 NOTMERGED-REST(20)
origin/security/closure-headend-deploy-integrity 0b1415128411b490c21a1b5e527cd851a591f244 NOTMERGED-REST(2)
origin/security/closure-headend-deploy-integrity-current c4ec3548dac8bfd4f4895f9b9aa0ce4e219e3d63 NOTMERGED-REST(2)
origin/security/closure-headend-deploy-integrity-final 34e63ada55d519113384a7ae91d19cd654e9b992 NOTMERGED-REST(2)
origin/security/closure-mainpy-p0-f001 4c4aa28f8c557be4c5a55e16c26b1f5f0141df0d NOTMERGED-REST(10)
origin/security/closure-os-builder-f002 342854b969e40659f6659000fb970b66516f9a69 NOTMERGED-REST(17)
origin/security/closure-real-artifact-signature-verification d384d1d67619f8433d928f05bc98ae96426061d4 NOTMERGED-REST(5)
origin/security/closure-sftp-host-trust 307b4c48e3afbb0d1be827d6b072de09ef7ac290 NOTMERGED-ABSORBED
origin/security/closure-technician-auth-xss d5e5f2db4b2d3efd628208371520d510dd1ef219 NOTMERGED-REST(10)
origin/security/closure-test-target-isolation 40e0dda7e086d560f666e1ee03925859fcd709b7 NOTMERGED-REST(3)
origin/security/closure-test-target-isolation-current 0b616709f9ba9d1048cad83255920d0886d7428e NOTMERGED-REST(2)
origin/security/closure-trust-grant-evidence 112ed8c087dc2112cc14e9100db72ba17144f62a NOTMERGED-REST(5)
origin/security/closure-unused-passlib 2a3447c0f22bbd47058a5e66f579772d9a3e8bbf NOTMERGED-ABSORBED
origin/security/closure-update-authority-h123 16bd9641e75360ed1c7eeae0541aaecc61e7e4e2 NOTMERGED-REST(7)
origin/security/closure-update-authority-h123-ci 5e1272c4ab7899ade129e63ad9b513dd9d3994eb NOTMERGED-REST(13)
origin/security/closure-update-type-trust-gate 356959a5e6664d8fc66d8c6f6a59caa71f98232b NOTMERGED-REST(2)
origin/security/closure-zai-critical-redaction ca44af0b343d476580659cebc9a22535f536a0b9 NOTMERGED-REST(2)
origin/security/os-update-governance-closure 33ecac26373acc3e736ff78dc9ff5fcfd4dc9d33 ANCESTRY-MERGED
```
