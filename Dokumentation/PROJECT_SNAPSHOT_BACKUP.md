# Projektbackup og restore

## Formaal

Mac-headendens aktive projekttrae synkroniseres ikke direkte med en cloud-klient. Det gav tidligere Google Drive meget store upload-koeer og et betydeligt memory-forbrug. I stedet opretter Restic en krypteret, deduplikeret snapshot-repository paa den lokale datadisk. Den faerdige repository spejles derefter til OneDrive.

## Logisk datarod

Alle nye backupstier bruger `/data-fast`, der er et stabilt logisk navn for den aktive data-volume. Ved opstart vedligeholder `timelapse-mount-data` et sikkert symlink fra `/data-fast` til den mounted APFS-volume. Et nyt enclosure eller et nyt volume-navn kraever derfor kun opdatering af den ene mount-konfiguration, ikke af backup- eller restoreproceduren.

## Indhold

- Kilde: `/data-fast/peter-home/projects`, inklusive Git-historik, dokumentation, konfiguration og secrets, krypteret i repositoryet.
- Inkluderet: `/data-fast/backup/timelapse-artifacts`.
- Fravalgt: `node_modules`, Python-venv'er, build/cachefoldere, Downloads, Open WebUI-venv samt genopbyggelige base-images og genererede artifacts i arbejdstraeet.
- Retention: 30 daglige, 12 maanedlige og 3 aarlige snapshots.

## Drift

Scriptet `project_snapshot_backup.sh` installeres som `/usr/local/sbin/timelapse-project-snapshot-backup` og koeres via brugerens LaunchAgent kl. 01:15. Det bruger en tilfældigt genereret repository-adgangskode i macOS Keychain (`dk.froekjaer.timelapse.project-backup.restic`). OneDrive-destinationen har en markerfil, saa `rsync --delete` aldrig kan ramme en vilkaarig eksisterende folder.

### OneDrive-destination

Den spejlede, krypterede repository ligger lokalt i OneDrive File Provider-roden paa:

`/Users/peter/Library/CloudStorage/OneDrive-Personligt/Filer/Projektbackups/restic-repository`

Den lokale primære repository ligger paa:

`/data-fast/backup/project-snapshots/restic-repository`

Kun Restic-repositoryet, det signerede snapshotmanifest og restore-vejledningen synkroniseres til OneDrive. Selve den aktive projektmappe synkroniseres ikke direkte.

## Restore

1. Vis lokale snapshots: `timelapse-project-snapshot-restore --list`.
2. Vis den off-site spejlede repository: `timelapse-project-snapshot-restore --source onedrive --list`.
3. Gendan et valgt snapshot til en ny, tom folder: `timelapse-project-snapshot-restore --snapshot <id> --target /data-fast/restore-test`.
4. Verificer indholdet og Git-status i restore-mappen.
5. Den aktive projektmappe overskrives aldrig af restore-scriptet. En egentlig tilbagefoering skal ske som en kontrolleret, separat change.

## Testkrav

Efter foerste snapshot koeres mindst en restore-test til `/data-fast/restore-test`, inklusive kontrol af dokumenter, Git-commit og artefakter. Backup er ikke accepteret foer denne test er dokumenteret.

## Verificeret evidens

- 2026-08-03: Foerste snapshot `2018d0cb` oprettet lokalt med 8.049 GiB indhold og efterfoelgende `restic check --read-data-subset=1/100` uden fejl.
- 2026-08-03: Repository blev spejlet til `OneDrive-Personligt/Filer/Projektbackups/restic-repository`.
- 2026-08-03: Snapshot `2018d0cb` blev gendannet til `/data-fast/backup/project-snapshots/restore-verification-20260803`. `README.md` og `timelapse-artifacts` blev fundet; den gendannede og aktive TimeLapse Pro-arbejdskopi har begge commit `eed9e3c8c67369e1924c25a11908616220c3c753`.
- Restorekopien slettes ikke automatisk. Den er test-evidens, indtil en administrator beslutter at frigive pladsen.
