# TimeLapse Pro - License Compliance Evidence Report

Generated: `2026-07-15T22:39:43.919507+00:00`

> This is an engineering compliance assessment, not legal advice. Unknown and review items require resolution before redistribution.

## Executive Summary

- Components inventoried: **479**
- Permissive: **415**
- Obligations: **41**
- Manual review: **22**
- Unknown: **1**
- Blocked: **0**

**Overall status: REVIEW_REQUIRED**

## Runtime Tools

| Tool | Available | Observed license | Status |
|---|---:|---|---|
| ffmpeg | True | GPL-2.0-or-later | review |
| gphoto2 | False | not asserted | unknown |
| nginx | True | not asserted | inventory-only |
| ollama | True | not asserted | inventory-only |
| postgresql | True | not asserted | inventory-only |

## Components Requiring Attention

| Ecosystem | Component | Version | License | Status |
|---|---|---|---|---|
| pypi | certifi | 2026.6.17 | MPL-2.0 | obligations |
| pypi | google-crc32c | 1.8.0 | UNKNOWN | unknown |
| pypi | inflate64 | 1.0.4 | LGPL-2.1-or-later | obligations |
| pypi | multivolumefile | 0.2.3 | LGPL-2.1+ | obligations |
| pypi | paramiko | 4.0.0 | LGPL-2.1 | obligations |
| pypi | pathspec | 1.1.1 | OSI Approved :: Mozilla Public License 2.0 (MPL 2.0) | obligations |
| pypi | psycopg2-binary | 2.9.12 | LGPL with exceptions | obligations |
| pypi | py7zr | 1.1.3 | LGPL-2.1-or-later | obligations |
| pypi | pybcj | 1.0.7 | LGPL-2.1-or-later | obligations |
| pypi | pyppmd | 1.3.1 | LGPL-2.1-or-later | obligations |
| pypi | pytest-html | 4.1.1 | MPL-2.0 | obligations |
| pypi | pytest-metadata | 3.1.1 | MPL-2.0 | obligations |
| pypi | tqdm | 4.68.3 | MPL-2.0 AND MIT | obligations |
| npm | @typescript-eslint/typescript-estree/node_modules/minimatch | 10.2.5 | BlueOak-1.0.0 | review |
| npm | argparse | 2.0.1 | Python-2.0 | review |
| npm | caniuse-lite | 1.0.30001782 | CC-BY-4.0 | review |
| npm | lightningcss | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-android-arm64 | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-darwin-arm64 | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-darwin-x64 | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-freebsd-x64 | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-linux-arm-gnueabihf | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-linux-arm64-gnu | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-linux-arm64-musl | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-linux-x64-gnu | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-linux-x64-musl | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-win32-arm64-msvc | 1.32.0 | MPL-2.0 | obligations |
| npm | lightningcss-win32-x64-msvc | 1.32.0 | MPL-2.0 | obligations |
| homebrew | augeas | 1.14.1_1 | LGPL-2.1-or-later | obligations |
| homebrew | autoconf | 2.73 | GPL-3.0-or-later AND (GPL-3.0-or-later WITH Autoconf-exception-3.0) | review |
| homebrew | ca-certificates | 2026-05-14 | MPL-2.0 | obligations |
| homebrew | certifi | 2026.4.22 | MPL-2.0 | obligations |
| homebrew | fail2ban | 1.1.0_2 | GPL-2.0-or-later | review |
| homebrew | ffmpeg | 8.1.1 | GPL-3.0-or-later | review |
| homebrew | gettext | 1.0 | GPL-3.0-or-later AND LGPL-2.1-or-later | obligations |
| homebrew | gmp | 6.3.0 | LGPL-3.0-or-later OR GPL-2.0-or-later | obligations |
| homebrew | gnupg | 2.5.19 | GPL-3.0-or-later | review |
| homebrew | gnutls | 3.8.13 | LGPL-2.1-or-later AND GPL-3.0-only | obligations |
| homebrew | icu4c@78 | 78.3 | Unicode-3.0 | review |
| homebrew | krb5 | 1.22.2 | BSD-2-Clause AND BSD-2-Clause-first-lines AND BSD-3-Clause AND BSD-4-Clause AND Brian-Gladman-2-Clause AND CMU-Mach-nodoc AND FSFULLRWD AND HPND AND HPND-export2-US AND HPND-export-US AND HPND-export-US-acknowledgement AND HPND-export-US-modify AND ISC AND MIT AND MIT-CMU AND OLDAP-2.8 AND OpenVision AND (BSD-2-Clause OR GPL-2.0-or-later) | review |
| homebrew | lame | 3.100 | LGPL-2.0-or-later | obligations |
| homebrew | libassuan | 3.0.2 | LGPL-2.1-or-later AND GPL-3.0-or-later AND FSFULLR | obligations |
| homebrew | libgcrypt | 1.12.2 | LGPL-2.1-or-later AND GPL-2.0-or-later | obligations |
| homebrew | libgpg-error | 1.61 | LGPL-2.1-or-later | obligations |
| homebrew | libidn2 | 2.3.8 | (GPL-2.0-or-later OR LGPL-3.0-or-later) AND (Unicode-TOU AND Unicode-DFS-2016) AND GPL-3.0-or-later AND LGPL-2.1-or-later AND FSFAP-no-warranty-disclaimer | obligations |
| homebrew | libksba | 1.7.0 | LGPL-3.0-or-later OR GPL-2.0-or-later | obligations |
| homebrew | libtasn1 | 4.21.0 | LGPL-2.1-or-later | obligations |
| homebrew | libunistring | 1.4.2 | GPL-2.0-or-later OR LGPL-3.0-or-later | obligations |
| homebrew | libusb | 1.0.29 | LGPL-2.1-or-later | obligations |
| homebrew | m4 | 1.4.21 | GPL-3.0-or-later | review |
| homebrew | nettle | 3.10.2 | GPL-2.0-or-later OR LGPL-3.0-or-later | obligations |
| homebrew | npth | 1.8 | LGPL-2.1-or-later | obligations |
| homebrew | pinentry | 1.3.2 | GPL-2.0-or-later | review |
| homebrew | pinentry-mac | 1.3.1.1 | GPL-2.0-or-later AND GPL-3.0-or-later | review |
| homebrew | postgresql@17 | 17.10 | PostgreSQL | review |
| homebrew | python@3.12 | 3.12.13_2 | Python-2.0 | review |
| homebrew | python@3.13 | 3.13.13_1 | Python-2.0 | review |
| homebrew | python@3.14 | 3.14.4_1 | Python-2.0 | review |
| homebrew | readline | 8.3.3 | GPL-3.0-or-later | review |
| homebrew | sqlite | 3.53.1 | blessing | review |
| homebrew | x264 | r3222 | GPL-2.0-or-later | review |
| homebrew | x265 | 4.2 | GPL-2.0-or-later | review |
| homebrew | xz | 5.8.3 | 0BSD AND GPL-2.0-or-later | review |
| homebrew | zstd | 1.5.7_1 | (BSD-3-Clause OR GPL-2.0-only) AND BSD-2-Clause AND MIT | review |

## Evidence and Policy

- Python evidence comes from installed distribution metadata and hashes of installed LICENSE/COPYING/NOTICE files.
- npm evidence comes from the committed lockfile, including package integrity values.
- Runtime-tool evidence is captured from the actual executable on the machine generating this report.
- Copyleft does not automatically mean prohibited; distribution model and obligations must be reviewed.
- Codec patent/licensing questions are separate from open-source copyright licenses.
