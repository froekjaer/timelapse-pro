# TimeLapse Pro - License Compliance Evidence Report

Generated: `2026-07-15T22:39:46.993275+00:00`

> This is an engineering compliance assessment, not legal advice. Unknown and review items require resolution before redistribution.

## Executive Summary

- Components inventoried: **2187**
- Permissive: **508**
- Obligations: **708**
- Manual review: **634**
- Unknown: **337**
- Blocked: **0**

**Overall status: REVIEW_REQUIRED**

## Runtime Tools

| Tool | Available | Observed license | Status |
|---|---:|---|---|
| ffmpeg | False | not asserted | unknown |
| gphoto2 | True | GPL (version requires source evidence) | review |
| nginx | False | not asserted | unknown |
| ollama | False | not asserted | unknown |
| postgresql | False | not asserted | unknown |

## Components Requiring Attention

| Ecosystem | Component | Version | License | Status |
|---|---|---|---|---|
| pypi | certifi | 2026.2.25 | MPL-2.0 | obligations |
| pypi | paramiko | 4.0.0 | LGPL-2.1 | obligations |
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
| deb | 2to3 | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | 7zip | 23.01+dfsg-11 | LGPL-2.1+ AND public-domain AND BSD-3-clause | obligations |
| deb | acl | 2.3.2-1build1.1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | adduser | 3.137ubuntu1 | GPL-2+ | review |
| deb | adwaita-icon-theme | 46.0-1 | CC-BY-SA-3.0 or LGPL-3, and CC-BY-SA-4.0 AND CC-BY-SA-3.0-US or LGPL-3 AND GPL-unspecified AND CC-BY-SA-4.0 AND GFDL-1.2+ or CC-BY-SA-3.0-Unported or CC-BY-SA-2.0-IT, and CC-BY-3.0-US AND GPL-2 AND GPL-3+ AND CC-BY-SA-3.0-Unported AND CC-BY-3.0-US AND CC-BY-SA-3.0-US AND CC-BY-SA-2.0-IT AND GFDL-1.2+ | obligations |
| deb | alsa-utils | 1.2.9-1ubuntu5 | GPL-2 AND LGPL-2+ | obligations |
| deb | anacron | 2.3-39ubuntu2 | GPL-2+ | review |
| deb | apparmor | 4.0.1really4.0.1-0ubuntu0.24.04.7 | GPL-2+ AND BSD-3-clause or GPL-2+ AND LGPL-2.1+ AND GPL-2 AND BSD-3-clause | obligations |
| deb | apport | 2.28.1-0ubuntu3.8 | GPL-2+ | review |
| deb | apport-core-dump-handler | 2.28.1-0ubuntu3.8 | GPL-2+ | review |
| deb | apport-gtk | 2.28.1-0ubuntu3.8 | GPL-2+ | review |
| deb | appstream | 1.0.2-1build6 | GPL-2+ and LGPL-2.1+ AND LGPL-2.1+ AND GPL-2+ AND FSFAP AND SIL-1.1 | obligations |
| deb | apt | 2.8.3 | GPL-2+ AND GPL-2 AND BSD-3-clause AND Expat | review |
| deb | apt-config-icons | 1.0.2-1build6 | GPL-2+ and LGPL-2.1+ AND LGPL-2.1+ AND GPL-2+ AND FSFAP AND SIL-1.1 | obligations |
| deb | apt-transport-https | 2.8.3 | GPL-2+ AND GPL-2 AND BSD-3-clause AND Expat | review |
| deb | apt-utils | 2.8.3 | GPL-2+ AND GPL-2 AND BSD-3-clause AND Expat | review |
| deb | aptdaemon | 1.1.1+bzr982-0ubuntu44 | GPL-2+ | review |
| deb | aptdaemon-data | 1.1.1+bzr982-0ubuntu44 | GPL-2+ | review |
| deb | aptitude | 0.8.13-5ubuntu5 | GPL-2+ | review |
| deb | aptitude-common | 0.8.13-5ubuntu5 | GPL-2+ | review |
| deb | at-spi2-common | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | at-spi2-core | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | autoconf | 2.71-3 | GPL-3+ AND GPL-3+ with Autoconf exception AND permissive-short-disclaimer AND permissive-long-disclaimer AND permissive-without-disclaimer AND permissive-without-notices-or-disclaimer AND GPL-2+ with Autoconf exception AND GPL-2+ AND MIT-X-Consortium AND GPL-3+ with Texinfo exception AND GFDL-1.3+ AND no-modification AND permissive AND other | review |
| deb | automake | 1:1.16.5-1.3ubuntu1 | GPL-2+ AND GPL-3+ AND GFDL-NIV-1.3+ AND permissive | review |
| deb | autotools-dev | 20220109.1 | UNKNOWN | unknown |
| deb | avahi-autoipd | 0.8-13ubuntu6.2 | UNKNOWN | unknown |
| deb | avahi-daemon | 0.8-13ubuntu6.2 | UNKNOWN | unknown |
| deb | base-files | 13ubuntu10.4 | UNKNOWN | unknown |
| deb | base-passwd | 3.6.3build1 | GPL-2 AND public-domain | review |
| deb | bash | 5.2.21-2ubuntu4 | GPL-3+ AND GPL-3+ with Bison exception AND GPL-2+ AND GFDL-NIV-1.3 AND Latex2e AND BSD-4-clause-UC and MIT-like AND BSD-4-clause-UC AND MIT-like AND permissive | review |
| deb | bash-completion | 1:2.11-8 | GPL-2+ | review |
| deb | bc | 1.07.1-3ubuntu4 | GPL-2.0+ AND permissive AND permissive' AND GPL-2.0+ with Texinfo exception AND X11 and public-domain | review |
| deb | bind9-dnsutils | 1:9.18.39-0ubuntu0.24.04.5 | MPL-2.0 and ISC and BSD-2-clause and BSD-3-clause AND MPL-2.0 and ISC AND MPL-2.0 and CC0-1.0 AND MPL-2.0 and public-domain AND FSFAP AND ISC or MPL-2.0 AND MPL-2.0 AND ISC AND BSD-2-clause AND BSD-3-clause AND CC0-1.0 | obligations |
| deb | bind9-host | 1:9.18.39-0ubuntu0.24.04.5 | MPL-2.0 and ISC and BSD-2-clause and BSD-3-clause AND MPL-2.0 and ISC AND MPL-2.0 and CC0-1.0 AND MPL-2.0 and public-domain AND FSFAP AND ISC or MPL-2.0 AND MPL-2.0 AND ISC AND BSD-2-clause AND BSD-3-clause AND CC0-1.0 | obligations |
| deb | bind9-libs:arm64 | 1:9.18.39-0ubuntu0.24.04.5 | MPL-2.0 and ISC and BSD-2-clause and BSD-3-clause AND MPL-2.0 and ISC AND MPL-2.0 and CC0-1.0 AND MPL-2.0 and public-domain AND FSFAP AND ISC or MPL-2.0 AND MPL-2.0 AND ISC AND BSD-2-clause AND BSD-3-clause AND CC0-1.0 | obligations |
| deb | binutils | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | binutils-aarch64-linux-gnu | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | binutils-common:arm64 | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | bison | 2:3.8.2+dfsg-1build2 | GPL-3+ AND GPL-2+ | review |
| deb | blueman | 2.3.5-3build1 | GPL-3+ | review |
| deb | bluetooth | 5.72-0ubuntu5.5 | GPL-2+ AND LGPL-2.1+ AND Apache-2.0 AND BSD-2-clause | obligations |
| deb | bluez | 5.72-0ubuntu5.5 | GPL-2+ AND LGPL-2.1+ AND Apache-2.0 AND BSD-2-clause | obligations |
| deb | bluez-cups | 5.72-0ubuntu5.5 | GPL-2+ AND LGPL-2.1+ AND Apache-2.0 AND BSD-2-clause | obligations |
| deb | bluez-hcidump | 5.72-0ubuntu5.5 | GPL-2+ AND LGPL-2.1+ AND Apache-2.0 AND BSD-2-clause | obligations |
| deb | bluez-obexd | 5.72-0ubuntu5.5 | GPL-2+ AND LGPL-2.1+ AND Apache-2.0 AND BSD-2-clause | obligations |
| deb | bluez-tools | 2.0~20170911.0.7cb788c-4build2 | GPL-2+ | review |
| deb | bolt | 0.9.7-1 | LGPL-2.1+ | obligations |
| deb | bridge-utils | 1.7.1-1ubuntu2 | UNKNOWN | unknown |
| deb | brltty | 6.6-4ubuntu5 | UNKNOWN | unknown |
| deb | brltty-x11 | 6.6-4ubuntu5 | UNKNOWN | unknown |
| deb | bsdextrautils | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | bsdutils | 1:2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | btrfs-progs | 6.6.3-1.1build2 | GPL-2 AND LGPL-2.1+ AND GPL-2+ | obligations |
| deb | bubblewrap | 0.9.0-1ubuntu0.1 | LGPL-2+ AND pd-bubblewrap.jpg AND permissive-git.mk AND GPL-2+ with Autoconf exception | obligations |
| deb | build-essential | 12.10ubuntu1 | The files in this package are free software; you can redistribute them | review |
| deb | busybox-initramfs | 1:1.36.1-6ubuntu3.1 | This package is free software; you can redistribute it and/or modify | review |
| deb | bzip2 | 1.0.8-5.1build0.1 | BSD-variant AND GPL-2 | review |
| deb | ca-certificates | 20260601~24.04.1 | GPL-2+ AND MPL-2.0 | obligations |
| deb | chrony | 4.5-1ubuntu4.2 | GPL-2 AND GPL-2+ AND RSA-MD | review |
| deb | cifs-utils | 2:7.0-2ubuntu0.2 | GPL-3+ AND LGPL-3+ | obligations |
| deb | cmake | 3.28.3-1build7 | BSD-3-clause AND Apache-2.0 AND Expat AND GPL-3+ with Bison exception AND Zlib AND GPL-2+ with Bison exception AND ISC AND BSD-2-Clause AND BSD-3-Clause AND BSD-0-Clause AND BSD-4-Clause AND BSD-2-Clause or ISC AND FSFAP | review |
| deb | cmake-data | 3.28.3-1build7 | BSD-3-clause AND Apache-2.0 AND Expat AND GPL-3+ with Bison exception AND Zlib AND GPL-2+ with Bison exception AND ISC AND BSD-2-Clause AND BSD-3-Clause AND BSD-0-Clause AND BSD-4-Clause AND BSD-2-Clause or ISC AND FSFAP | review |
| deb | colord | 1.4.7-1build2 | GPL-2+ AND LGPL-2.1+ AND GFDL-NIV AND CC0-1.0 AND CC0-1.0 and NPES AND NPES | obligations |
| deb | colord-data | 1.4.7-1build2 | GPL-2+ AND LGPL-2.1+ AND GFDL-NIV AND CC0-1.0 AND CC0-1.0 and NPES AND NPES | obligations |
| deb | console-setup | 1.226ubuntu1 | UNKNOWN | unknown |
| deb | console-setup-linux | 1.226ubuntu1 | UNKNOWN | unknown |
| deb | coreutils | 9.4-3ubuntu6.2 | GPL-3+ AND GPL-3+ and BSD-4-clause-UC AND BSD-4-clause-UC AND GPL-3+ and ISC AND ISC AND FSFULLR AND GFDL-NIV-1.3 | review |
| deb | cpio | 2.15+dfsg-1ubuntu2 | GPL-3+ AND LGPL-3+ | obligations |
| deb | cpp | 4:13.2.0-7ubuntu1 | UNKNOWN | unknown |
| deb | cpp-11 | 11.5.0-1ubuntu1~24.04.1 | UNKNOWN | unknown |
| deb | cpp-13 | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | cpp-13-aarch64-linux-gnu | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | cpp-aarch64-linux-gnu | 4:13.2.0-7ubuntu1 | UNKNOWN | unknown |
| deb | cpufrequtils | 008-2build2 | GPL-2 | review |
| deb | cracklib-runtime | 2.9.6-5.1build2 | LGPL-2.1 | obligations |
| deb | cron | 3.0pl1-184ubuntu2 | Paul-Vixie's-license AND Paul-Vixie's-license and GPL-2+ and ISC AND GPL-2+ AND Artistic AND ISC | review |
| deb | cron-daemon-common | 3.0pl1-184ubuntu2 | Paul-Vixie's-license AND Paul-Vixie's-license and GPL-2+ and ISC AND GPL-2+ AND Artistic AND ISC | review |
| deb | cryptsetup | 2:2.7.0-1ubuntu4.2 | GPL-2+ with OpenSSL exception AND GPL-2+ AND GPL-3+ AND LGPL-2.1+ AND LGPL-2.1+ with OpenSSL exception AND CC0 or Apache-2.0 AND public-domain AND CC0 AND Apache-2.0 | obligations |
| deb | cryptsetup-bin | 2:2.7.0-1ubuntu4.2 | GPL-2+ with OpenSSL exception AND GPL-2+ AND GPL-3+ AND LGPL-2.1+ AND LGPL-2.1+ with OpenSSL exception AND CC0 or Apache-2.0 AND public-domain AND CC0 AND Apache-2.0 | obligations |
| deb | cups | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-bsd | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-client | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-common | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-core-drivers | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-daemon | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-filters | 2.0.0-0ubuntu4.1 | Apache-2.0-with-GPL2-LGPL2-Exception AND GPL-2+ | obligations |
| deb | cups-filters-core-drivers | 2.0.0-0ubuntu4.1 | Apache-2.0-with-GPL2-LGPL2-Exception AND GPL-2+ | obligations |
| deb | cups-ipp-utils | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-ppdc | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | cups-server-common | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | curl | 8.5.0-2ubuntu10.9 | curl AND OLDAP-2.8 AND ISC AND GPL-2+ with Autoconf-data exception AND GPL-3+ with Autoconf-data exception AND GPL-2+ with Libtool exception AND BSD-3-clause AND BSD-4-Clause-UC AND FSFULLR AND X11 AND BSD-3-Clause | review |
| deb | dash | 0.5.12-6ubuntu5 | BSD-3-Clause AND public-domain AND GPL-2+ AND BSD-3-clause | review |
| deb | dbus | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | dbus-bin | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | dbus-daemon | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | dbus-session-bus-common | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | dbus-system-bus-common | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | dbus-user-session | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | dbus-x11 | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | dconf-cli | 0.40.0-4ubuntu0.1 | LGPL-2+ AND GPL-3 | obligations |
| deb | dconf-gsettings-backend:arm64 | 0.40.0-4ubuntu0.1 | LGPL-2+ AND GPL-3 | obligations |
| deb | dconf-service | 0.40.0-4ubuntu0.1 | LGPL-2+ AND GPL-3 | obligations |
| deb | debianutils | 5.17build1 | GPL-2+ AND public-domain AND SMAIL-GPL | review |
| deb | desktop-file-utils | 0.27-2build1 | GPL-2+ | review |
| deb | device-tree-compiler | 1.7.0-2build1 | GPL-2+ AND GPL-2+ or BSD-2-clause AND LGPL-2.1+ AND BSD-2-clause | obligations |
| deb | dhcpcd-base | 1:10.0.6-1ubuntu3.2 | BSD-2 AND ISC AND Expat AND BSD-2-Clause-NETBSD AND BSD-3-Clause AND public-domain AND GPL-3+ | review |
| deb | dialog | 1.3-20240101-1 | LGPL AND GPL-3 AND public-domain | obligations |
| deb | dictionaries-common | 1.29.7 | GPL-2+ AND GPL-3+ | review |
| deb | diffutils | 1:3.10-1build1 | GPL-3+ AND FSFULLR AND GPL-3+ and FSFULLR AND LGPL-2.1+ AND GPL-3+ with autoconf exception AND GPL-3+ with texinfo exception AND LGPL-2.0+ AND GPL-2+ AND X11 AND FSFAP AND GFDL-NIV-1.3 AND LGPL-3.0+ AND LGPL-3.0+ or GPL-2+ AND public-domain | obligations |
| deb | dirmngr | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | dmsetup | 2:1.02.185-3ubuntu3.2 | GPL-2.0 AND LGPL-2.1 AND BSD-2-Clause AND GPL-2.0+ | obligations |
| deb | dmz-cursor-theme | 0.4.5ubuntu1 | UNKNOWN | unknown |
| deb | dns-root-data | 2024071801~ubuntu0.24.04.1 | ICANN-Public AND Expat | review |
| deb | dnsmasq | 2.90-2ubuntu0.3 | GPL-2 or GPL-3 AND GPL-2 AND GPL-3 | review |
| deb | dnsmasq-base | 2.90-2ubuntu0.3 | GPL-2 or GPL-3 AND GPL-2 AND GPL-3 | review |
| deb | dnsutils | 1:9.18.39-0ubuntu0.24.04.5 | MPL-2.0 and ISC and BSD-2-clause and BSD-3-clause AND MPL-2.0 and ISC AND MPL-2.0 and CC0-1.0 AND MPL-2.0 and public-domain AND FSFAP AND ISC or MPL-2.0 AND MPL-2.0 AND ISC AND BSD-2-clause AND BSD-3-clause AND CC0-1.0 | obligations |
| deb | doc-base | 0.11.2 | GPL-2+ | review |
| deb | docker-buildx-plugin | 0.34.1-1~ubuntu.24.04~noble | UNKNOWN | unknown |
| deb | docker-ce | 5:29.5.3-1~ubuntu.24.04~noble | UNKNOWN | unknown |
| deb | docker-ce-cli | 5:29.5.3-1~ubuntu.24.04~noble | UNKNOWN | unknown |
| deb | docker-ce-rootless-extras | 5:29.5.3-1~ubuntu.24.04~noble | UNKNOWN | unknown |
| deb | docker-compose-plugin | 5.1.4-1~ubuntu.24.04~noble | UNKNOWN | unknown |
| deb | dosfstools | 4.2-1.1build1 | GPL-3+ AND public-domain | review |
| deb | dpkg | 1.22.6ubuntu6.6 | GPL-2+ AND public-domain-s-s-d | review |
| deb | dpkg-dev | 1.22.6ubuntu6.6 | GPL-2+ AND public-domain-s-s-d | review |
| deb | dracut-install | 060+5-1ubuntu3.3 | GPL-2+ AND BSD-3-clause AND LGPL-2.1+ | obligations |
| deb | e2fsprogs | 1.47.0-2.4~exp1ubuntu4.1 | GPL-2 AND LGPL-2 AND BSD-3-Clause AND Apache-2 AND ISC AND GPL or MIT-US-export AND Kazlib AND Latex2e AND GPL-2+ with Texinfo exception | obligations |
| deb | eject | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | emacs-bin-common | 1:29.3+1-1ubuntu2 | GPL-3+ AND admin/unidata/copyright.html AND This originates from X11R5 (mit/util/scripts/install.sh), which was AND GPL plus Ian AND manpage license AND efaq.texi license AND efaq-w32.texi license AND LGPL-2+ AND LGPL-3+ AND GPL-2+ or LGPL-3+ AND GPL-2+ AND same as corresponding file in /etc/images AND Creative Commons Attribution-ShareAlike 3.0 License AND MPL-2.0 AND Open Document Format for Office Applications (OpenDocument) Version 1.2 AND Open Document Format for Office Applications (OpenDocument) Version 1.3 AND meese.el license AND gnulib-comp.m4 license AND pkg.m4 license AND m4 license AND sedadmin.inp license AND nt/inc/dirent.h license AND This file is free software; as a special exception the author gives AND GPL-2 AND Boost Software License - Version 1.0 - August 17th, 2003 AND PCRE LICENCE | obligations |
| deb | emacs-common | 1:29.3+1-1ubuntu2 | GPL-3+ AND admin/unidata/copyright.html AND This originates from X11R5 (mit/util/scripts/install.sh), which was AND GPL plus Ian AND manpage license AND efaq.texi license AND efaq-w32.texi license AND LGPL-2+ AND LGPL-3+ AND GPL-2+ or LGPL-3+ AND GPL-2+ AND same as corresponding file in /etc/images AND Creative Commons Attribution-ShareAlike 3.0 License AND MPL-2.0 AND Open Document Format for Office Applications (OpenDocument) Version 1.2 AND Open Document Format for Office Applications (OpenDocument) Version 1.3 AND meese.el license AND gnulib-comp.m4 license AND pkg.m4 license AND m4 license AND sedadmin.inp license AND nt/inc/dirent.h license AND This file is free software; as a special exception the author gives AND GPL-2 AND Boost Software License - Version 1.0 - August 17th, 2003 AND PCRE LICENCE | obligations |
| deb | emacs-el | 1:29.3+1-1ubuntu2 | GPL-3+ AND admin/unidata/copyright.html AND This originates from X11R5 (mit/util/scripts/install.sh), which was AND GPL plus Ian AND manpage license AND efaq.texi license AND efaq-w32.texi license AND LGPL-2+ AND LGPL-3+ AND GPL-2+ or LGPL-3+ AND GPL-2+ AND same as corresponding file in /etc/images AND Creative Commons Attribution-ShareAlike 3.0 License AND MPL-2.0 AND Open Document Format for Office Applications (OpenDocument) Version 1.2 AND Open Document Format for Office Applications (OpenDocument) Version 1.3 AND meese.el license AND gnulib-comp.m4 license AND pkg.m4 license AND m4 license AND sedadmin.inp license AND nt/inc/dirent.h license AND This file is free software; as a special exception the author gives AND GPL-2 AND Boost Software License - Version 1.0 - August 17th, 2003 AND PCRE LICENCE | obligations |
| deb | emacs-nox | 1:29.3+1-1ubuntu2 | GPL-3+ AND admin/unidata/copyright.html AND This originates from X11R5 (mit/util/scripts/install.sh), which was AND GPL plus Ian AND manpage license AND efaq.texi license AND efaq-w32.texi license AND LGPL-2+ AND LGPL-3+ AND GPL-2+ or LGPL-3+ AND GPL-2+ AND same as corresponding file in /etc/images AND Creative Commons Attribution-ShareAlike 3.0 License AND MPL-2.0 AND Open Document Format for Office Applications (OpenDocument) Version 1.2 AND Open Document Format for Office Applications (OpenDocument) Version 1.3 AND meese.el license AND gnulib-comp.m4 license AND pkg.m4 license AND m4 license AND sedadmin.inp license AND nt/inc/dirent.h license AND This file is free software; as a special exception the author gives AND GPL-2 AND Boost Software License - Version 1.0 - August 17th, 2003 AND PCRE LICENCE | obligations |
| deb | emacsen-common | 3.0.5 | UNKNOWN | unknown |
| deb | ethtool | 1:6.7-1build1 | GPL-2 AND GPL-3+ with autoconf exception | review |
| deb | evince | 46.3.1-0ubuntu1.1 | UNKNOWN | unknown |
| deb | evince-common | 46.3.1-0ubuntu1.1 | UNKNOWN | unknown |
| deb | evolution-data-server | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | evolution-data-server-common | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | evtest | 1:1.35-1 | GPL-2.0+ | review |
| deb | exo-utils | 4.18.0-1build4 | UNKNOWN | unknown |
| deb | expect | 5.45.4-3 | PD | review |
| deb | f2fs-tools | 1.16.0-1 | GPL-2 AND GPL-2 or LGPL-2 AND BSD-2-clause AND GPL-2+ AND LGPL-2 | obligations |
| deb | f3 | 8.0-2build2 | GPL-3 AND GPL-3+ AND GPL-3 or GPL-3+ | review |
| deb | fake-hwclock | 0.13 | UNKNOWN | unknown |
| deb | fbset | 2.1-33build1 | GPL-2 | review |
| deb | fcitx | 1:4.2.9.9-2build2 | GPL-2+ AND BSD-3-Clause AND DEC-BSD-LIKE AND FUJITSU-BSD-LIKE AND SUN-HP-BSD-LIKE AND LGPL-2+ AND MIT AND BSD-1-Clause | obligations |
| deb | fcitx-bin | 1:4.2.9.9-2build2 | GPL-2+ AND BSD-3-Clause AND DEC-BSD-LIKE AND FUJITSU-BSD-LIKE AND SUN-HP-BSD-LIKE AND LGPL-2+ AND MIT AND BSD-1-Clause | obligations |
| deb | fcitx-data | 1:4.2.9.9-2build2 | GPL-2+ AND BSD-3-Clause AND DEC-BSD-LIKE AND FUJITSU-BSD-LIKE AND SUN-HP-BSD-LIKE AND LGPL-2+ AND MIT AND BSD-1-Clause | obligations |
| deb | fcitx-modules | 1:4.2.9.9-2build2 | GPL-2+ AND BSD-3-Clause AND DEC-BSD-LIKE AND FUJITSU-BSD-LIKE AND SUN-HP-BSD-LIKE AND LGPL-2+ AND MIT AND BSD-1-Clause | obligations |
| deb | fdisk | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | figlet | 2.2.5-3 | BSD-3-clause AND Expat AND ISC AND Unicode AND WTFPL-2 AND GPL-2+ | review |
| deb | findutils | 4.9.0-5build1 | GFDL-NIV-1.3+ AND GPL-3+ AND FSFAP AND GPL-3+ with Autoconf-data exception AND FSFULLR AND GPL-2+ with Autoconf-data exception AND GPL-2+ AND X11 AND public-domain AND GPL with automake exception AND LGPL-2.1+ AND LGPL-2+ AND LGPL-3+ AND BSD-3-clause and/or GPL-3+ AND GPL-3+ with Bison-2.2 exception AND LGPL-3 AND ISC and/or LGPL-2.1+ AND BSD-3-clause AND ISC | obligations |
| deb | flex | 2.6.4-8.2build1 | FLEX AND GPL-3+ AND FSFAP AND GPL AND LGPL-2+ AND GPL-2+ | obligations |
| deb | fontconfig | 2.15.0-1.1ubuntu2 | UNKNOWN | unknown |
| deb | fontconfig-config | 2.15.0-1.1ubuntu2 | UNKNOWN | unknown |
| deb | fonts-arphic-ukai | 0.2.20080216.2-5 | UNKNOWN | unknown |
| deb | fonts-arphic-uming | 0.2.20080216.2-10ubuntu2 | UNKNOWN | unknown |
| deb | fonts-dejavu-core | 2.37-8 | bitstream-vera AND GPL-2+ | review |
| deb | fonts-dejavu-mono | 2.37-8 | bitstream-vera AND GPL-2+ | review |
| deb | fonts-freefont-ttf | 20211204+svn4273-2 | GPL-3+ AND GPL-3+ with Special Font Exception | review |
| deb | fonts-guru-extra | 2.0-5 | GPL-2.0+ with Font exception AND GPL-2.0+ | review |
| deb | fonts-kacst | 2.01+mry-15 | GPL-2 | review |
| deb | fonts-kacst-one | 5.0+svn11846-10 | GPL-2 | review |
| deb | fonts-khmeros-core | 5.0-9ubuntu1 | LGPL-2.1+ | obligations |
| deb | fonts-lato | 2.015-1 | OFL-1.1 AND GPL-2+ | review |
| deb | fonts-liberation | 1:2.1.5-3 | SIL-OFL-1.1 AND GPL-2+ | review |
| deb | fonts-lyx | 2.4.0~RC3-1build4 | GPL-2+ AND BSL-1.0 AND BSD-2-Mark-Modifications AND LGPL-2.1+ AND BSD-3-Clause AND CC0-1.0 AND BaKoMa AND public-domain | obligations |
| deb | fonts-mathjax | 2.7.9+dfsg-1 | Apache-2.0 AND OFL-1.1 AND GFL AND GPL-2+ or Apache-2.0 AND GPL-2+ | review |
| deb | fonts-nanum | 20200506-1 | OFL-1.1 AND GPL-3+ AND CC0-1.0 | review |
| deb | fonts-opensymbol | 4:102.12+LibO24.2.7-0ubuntu0.24.04.5 | MPL-2.0 AND Apache-2.0 AND CC0-1.0 AND GPL-2+ AND CC-BY-SA-3.0 AND GPL-3+ AND LGPL-3+ AND Expat AND MIT AND GPL-2 AND This is a subset copy of Noto Emoji font licensed under Open Font License and AND This is a subset copy of Source Han Sans font licensed under Open Font License and AND BSD-3-clause AND MPL-1.1 or GPL-2 or LGPL-2 AND other AND LGPL-3 AND BSD-2-clause AND MPL-1.1 AND LGPL-2 | obligations |
| deb | fonts-stix | 1.1.1-5 | SIL-OFL-1.1 AND GPL-2 | review |
| deb | fonts-symbola | 2.60-1.1 | Fonts are free for any use; they may be opened, edited, | review |
| deb | fonts-ubuntu | 0.869+git20240321-0ubuntu1 | Ubuntu-Font-Licence-1.0 AND GPL-3 AND CC-BY-SA-3.0 | review |
| deb | fonts-ubuntu-console | 0.869+git20240321-0ubuntu1 | Ubuntu-Font-Licence-1.0 AND GPL-3 AND CC-BY-SA-3.0 | review |
| deb | fonts-urw-base35 | 20200910-8 | AGPL-3 with Font exception AND CC-BY-4.0 AND GPL-2+ AND AGPL-3 | review |
| deb | fonts-wqy-zenhei | 0.9.45-8 | GPL-2 with Font embedding exception and M+ FONTS License AND GPL-2 with Font embedding exception AND M+ FONTS License | review |
| deb | foomatic-db-compressed-ppds | 20230202-1 | GPL-2 AND FSFUL AND Expat AND GPL-2+ AND GPL-2.0+OKI AND BSDunspecified | review |
| deb | fuse3 | 3.14.0-5build1 | GPL-2 AND LGPL-2.1 AND GPL-2+ | obligations |
| deb | fwupd | 2.0.20-1ubuntu2~24.04.1 | LGPL-2.1-or-later AND CC0-1.0 | obligations |
| deb | fwupd-signed | 1.52+1.4-1 | GPL-2.0+ AND GPL-3+ | review |
| deb | g++ | 4:13.2.0-7ubuntu1 | UNKNOWN | unknown |
| deb | g++-13 | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | g++-13-aarch64-linux-gnu | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | g++-aarch64-linux-gnu | 4:13.2.0-7ubuntu1 | UNKNOWN | unknown |
| deb | gcc | 4:13.2.0-7ubuntu1 | UNKNOWN | unknown |
| deb | gcc-11 | 11.5.0-1ubuntu1~24.04.1 | UNKNOWN | unknown |
| deb | gcc-11-base:arm64 | 11.5.0-1ubuntu1~24.04.1 | UNKNOWN | unknown |
| deb | gcc-12-base:arm64 | 12.4.0-2ubuntu1~24.04.1 | UNKNOWN | unknown |
| deb | gcc-13 | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | gcc-13-aarch64-linux-gnu | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | gcc-13-base:arm64 | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | gcc-14-base:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | gcc-aarch64-linux-gnu | 4:13.2.0-7ubuntu1 | UNKNOWN | unknown |
| deb | gcr | 3.41.2-1build3 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | gcr4 | 4.2.0-5 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | gdal-data | 3.8.4+dfsg-3ubuntu3 | Expat AND Qhull AND HPND-p-sl-sgi AND public-domain AND HPND-sl-sgi AND HPND-sl-gl-sgi AND HPND-eos AND IJG AND ITT AND Apache-2.0 AND Apache-2.0 and BSD-3-Clause AND BSD-3-Clause AND libpng AND fontconfig AND zlib AND ISC AND Expat and GPL-3+ with Bison exception AND Expat and PostgreSQL AND Expat or LGPL-2+ AND GPL-3+ with Bison exception AND HPND-3i AND Expat and Base64 AND cpl-mem-cache AND Info-ZIP AND HPND-disclaimer AND Expat and zlib AND LGPL-2+ AND Base64 AND PostgreSQL | obligations |
| deb | gdal-plugins:arm64 | 3.8.4+dfsg-3ubuntu3 | Expat AND Qhull AND HPND-p-sl-sgi AND public-domain AND HPND-sl-sgi AND HPND-sl-gl-sgi AND HPND-eos AND IJG AND ITT AND Apache-2.0 AND Apache-2.0 and BSD-3-Clause AND BSD-3-Clause AND libpng AND fontconfig AND zlib AND ISC AND Expat and GPL-3+ with Bison exception AND Expat and PostgreSQL AND Expat or LGPL-2+ AND GPL-3+ with Bison exception AND HPND-3i AND Expat and Base64 AND cpl-mem-cache AND Info-ZIP AND HPND-disclaimer AND Expat and zlib AND LGPL-2+ AND Base64 AND PostgreSQL | obligations |
| deb | gdebi | 0.9.5.7+nmu7 | GPL-2+ AND LGPL-2.1 | obligations |
| deb | gdebi-core | 0.9.5.7+nmu7 | GPL-2+ AND LGPL-2.1 | obligations |
| deb | geoclue-2.0 | 2.7.0-3ubuntu7 | GPL-2+ AND GFDL-NIV-1.1+ AND LGPL-2+ | obligations |
| deb | geocode-glib-common | 3.26.3-6build3 | LGPL-2+ AND BSD-3-clause AND ODbL-1.0 | obligations |
| deb | ghostscript | 10.02.1~dfsg1-0ubuntu7.8 | AGPL-3+ AND AGPL-3+ and FTL AND none AND BSD-3-Clause~Adobe AND LGPL-2.1 AND GPL-1+ AND AGPL-3+ with font exception AND GAP~configure AND GPL-2+ AND ZLIB AND BSD-3-Clause AND Expat~SunSoft with SunSoft exception AND Expat AND public-domain AND Apache-2.0 AND GPL-3+ with Autoconf exception AND ISC AND Expat~Ghostgum AND MIT-Open-Group AND NTP~Lucent AND NTP~WSU AND X11 AND GPL-3+ AND AGPL-3 AND Expat~SunSoft AND FTL | obligations |
| deb | gir1.2-accountsservice-1.0:arm64 | 23.13.9-2ubuntu6 | GPL-3+ AND GPL-2+ | review |
| deb | gir1.2-adw-1:arm64 | 1.5.0-1ubuntu2 | LGPL-2.1+ AND GPL-3+ AND CC0-1.0 AND CC-BY-SA-4.0 | obligations |
| deb | gir1.2-atk-1.0:arm64 | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | gir1.2-atspi-2.0:arm64 | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | gir1.2-freedesktop:arm64 | 1.80.1-1 | GPL-2+ AND LGPL-2+ AND LGPL-2 or MPL-1.1 AND LGPL-2.1+ AND BSD-2-clause AND FSFAP and FSFULLR AND Expat and GPL-2+ AND LGPL-2+ and LGPL-2.1+ and FSFULLR and CC0-1.0 AND AFL-2.0 or LGPL-2.1+ AND Unicode-DFS-2016 AND Expat AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND GPL with Autoconf exception AND AFL-2.0 AND CC0-1.0 AND FSFAP AND FSFULLR AND Kuchling-PD AND LGPL-2 AND MPL-1.1 AND Plumb-PD | obligations |
| deb | gir1.2-gck-2:arm64 | 4.2.0-5 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | gir1.2-gcr-4:arm64 | 4.2.0-5 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | gir1.2-gdesktopenums-3.0:arm64 | 46.1-0ubuntu1 | LGPL-2.1+ | obligations |
| deb | gir1.2-gdkpixbuf-2.0:arm64 | 2.42.10+dfsg-3ubuntu3.3 | LGPL-2+ and LGPL-2.1+ and CC0-1.0 AND GPL-2+ AND CC0-1.0 AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | gir1.2-gdm-1.0 | 46.2-1ubuntu1~24.04.9 | This package is free software; you can redistribute it and/or modify | review |
| deb | gir1.2-geoclue-2.0:arm64 | 2.7.0-3ubuntu7 | GPL-2+ AND GFDL-NIV-1.1+ AND LGPL-2+ | obligations |
| deb | gir1.2-girepository-2.0:arm64 | 1.80.1-1 | GPL-2+ AND LGPL-2+ AND LGPL-2 or MPL-1.1 AND LGPL-2.1+ AND BSD-2-clause AND FSFAP and FSFULLR AND Expat and GPL-2+ AND LGPL-2+ and LGPL-2.1+ and FSFULLR and CC0-1.0 AND AFL-2.0 or LGPL-2.1+ AND Unicode-DFS-2016 AND Expat AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND GPL with Autoconf exception AND AFL-2.0 AND CC0-1.0 AND FSFAP AND FSFULLR AND Kuchling-PD AND LGPL-2 AND MPL-1.1 AND Plumb-PD | obligations |
| deb | gir1.2-glib-2.0:arm64 | 2.80.0-6ubuntu3.8 | LGPL-2.1+ AND old-glib-tests AND AFL-2.0 or LGPL-2.1+ AND Janik-permissive AND LGPL-2+ AND FSFULLR AND Iconv-PD AND CC0-1.0 AND CC0-1.0 or Mingw-PD AND Janik-permissive and old-glib-tests AND Unicode-DFS-2016 AND Expat AND GPL-2+ AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND cmph AND AFL-2.0 AND Kuchling-PD AND Mingw-PD AND Plumb-PD | obligations |
| deb | gir1.2-gnomebg-4.0:arm64 | 44.0-5build2 | LGPL-2+ AND LGPL-3+ AND GPL-2+ AND Expat | obligations |
| deb | gir1.2-gnomebluetooth-3.0:arm64 | 46.0-1ubuntu1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | gir1.2-gnomedesktop-4.0:arm64 | 44.0-5build2 | LGPL-2+ AND LGPL-3+ AND GPL-2+ AND Expat | obligations |
| deb | gir1.2-graphene-1.0:arm64 | 1.10.8-3build2 | Expat | review |
| deb | gir1.2-gstreamer-1.0:arm64 | 1.24.2-1ubuntu0.1 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ AND GPL-3+ | obligations |
| deb | gir1.2-gtk-3.0:arm64 | 3.24.41-4ubuntu1.3 | LGPL-2+ and LGPL-2.1+ and Expat AND GPL-3+ AND LGPL-2+ AND CC-BY-SA-4.0 AND unencumbered AND other AND SWL AND LGPL-2+ or SWL AND X11R5-permissive AND Expat AND Apache-2.0 AND LGPL-2+ and ZPL-2.1 AND check-gdk-cairo-permissive AND LGPL-2.1+ AND ZPL-2.1 | obligations |
| deb | gir1.2-gtk-4.0:arm64 | 4.14.5+ds-0ubuntu0.10 | LGPL-2.1+ AND LGPL-2+ and LGPL-2.1+ and sun-permissive and lcs-telegraphics-permissive and X11R5-permissive and Expat and BSD-3-clause-Google and Apache-2.0 and CC0-1.0 and ZPL-2.1 AND Unicode-DFS-2016 AND GPL-3+ AND Apache-2.0 with LLVM exception AND Expat or unlicense AND CC0-1.0 AND Apache-2.0 AND BSD-3-clause-Google AND Expat AND LGPL-2+ AND lcs-telegraphics-permissive AND sun-permissive AND unlicense AND X11R5-permissive AND ZPL-2.1 | obligations |
| deb | gir1.2-gweather-4.0:arm64 | 4.4.2-1build1 | GPL-2+ AND LGPL-2.1+ AND LGPL-2+ | obligations |
| deb | gir1.2-handy-1:arm64 | 1.8.3-1build2 | LGPL-2.1+ | obligations |
| deb | gir1.2-harfbuzz-0.0:arm64 | 8.3.0-2build2 | MIT AND Unicode AND ISC AND Apache-2.0 AND OFL-1.1 AND Monotype AND CC0-1.0 AND GPL-3+ AND GPL-2+ with Font exception AND UFL-1.0 AND FSFULLR AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND LGPL-2.1+ AND GPL-2+ with LibTool exception AND Expat AND FSFUL | obligations |
| deb | gir1.2-ibus-1.0:arm64 | 1.5.29-2 | LGPL-2.1+ AND permissive-makefile-in AND ISC-Sun AND permissive-autoconf-m4 AND GPL-2.0+ with autoconf exception AND ISC-Intel AND ISC-Fujitsu AND MIT and ISC-NCR AND MIT AND ISC-NCR AND LGPL-2.0+ AND permissive-fsf-grant AND permissive AND permissive-fsf-grant-attribution AND permissive-author-grant-attribution AND GPL-3.0+ with autoconf exception | obligations |
| deb | gir1.2-javascriptcoregtk-4.1:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | gir1.2-javascriptcoregtk-6.0:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | gir1.2-mutter-14:arm64 | 46.2-1ubuntu0.24.04.15 | GPL-2+ and GPL-3+ and LGPL-2+ and LGPL-2.1+ and Expat and NTP-BSD-variant and SGI-B-2.0 AND WRF-BSD-variant AND free-of-known-restrictions AND DEC-BSD-variant and OpenGroup-BSD-variant AND DEC-BSD-variant and OpenGroup-BSD-variant and GPL-2+ AND GPL-2+ AND GPL-3+ AND LGPL-2+ AND LGPL-2.1+ AND Expat AND NTP-BSD-variant AND OpenGroup-BSD-variant AND DEC-BSD-variant AND SGI-B-2.0 | obligations |
| deb | gir1.2-nm-1.0:arm64 | 1.46.0-1ubuntu2.7 | GPL-2+ AND LGPL-2.1+ AND GFDL-NIV-1.1+ | obligations |
| deb | gir1.2-nma4-1.0:arm64 | 1.10.6-3build2 | GPL-2+ AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | gir1.2-notify-0.7:arm64 | 0.8.3-1build2 | This library is free software; you can redistribute it and/or | review |
| deb | gir1.2-packagekitglib-1.0 | 1.2.8-2ubuntu1.5 | GPL-2+ and LGPL-2.1+ AND GPL-2+ AND LGPL-2.1+ AND FSFAP | obligations |
| deb | gir1.2-pango-1.0:arm64 | 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ AND Example AND LGPL-2+ AND LGPL-2+ and TCL AND Unicode AND LGPL-2+ and ICU AND Chromium-BSD-style AND Apache-2 and Bitstream-Vera and OFL-1.1 AND Apache-2 AND Bitstream-Vera AND ICU AND LGPL-2.1+ AND TCL AND OFL-1.1 | obligations |
| deb | gir1.2-polkit-1.0 | 124-2ubuntu1.24.04.3 | LGPL-2.0+ and Expat AND Expat AND Apache-2.0 AND LGPL-2.0+ | obligations |
| deb | gir1.2-rsvg-2.0:arm64 | 2.58.0+dfsg-1build1 | LGPL-2+ AND FSFAP AND BSD-3-clause AND Expat AND Apache-2.0, and BSD-2-clause, and BSD-3-clause, and Expat, and Apache-2.0 or Expat or 0BSD, and Apache-2.0 or Boost-1.0, and Apache-2.0 or Expat, and Expat or Unlicense, and MPL-2.0, and Sun-permissive, and zlib AND CC-zero-waive-1.0-us AND OFL-1.1 AND Apache-2.0 AND MPL-2.0 AND Unlicense AND BSD-2-clause AND Sun-permissive AND Boost-1.0 AND zlib AND 0BSD | obligations |
| deb | gir1.2-snapd-2:arm64 | 1.64-0ubuntu5 | LGPL-2 or LGPL-3 AND GPL-3+ AND LGPL-2 AND LGPL-3 | obligations |
| deb | gir1.2-soup-3.0:arm64 | 3.4.4-5ubuntu0.7 | LGPL-2.1+ AND LGPL-2+ AND MPL-2.0 or RSA-Other AND Expat AND MPL-2.0 AND RSA-Other | obligations |
| deb | gir1.2-upowerglib-1.0:arm64 | 1.90.3-1 | GPL-2+ AND GFDL-1.1+ | review |
| deb | gir1.2-vte-2.91:arm64 | 0.76.0-1ubuntu0.1 | GPL-3+ and LGPL-3+ and Expat AND GPL-3+ and LGPL-3+ AND LGPL-3+ AND GPL-3+ AND Expat | obligations |
| deb | gir1.2-webkit-6.0:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | gir1.2-webkit2-4.1:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | gir1.2-wnck-3.0:arm64 | 43.0-3build4 | LGPL-2+ | obligations |
| deb | gist | 6.0.0-3 | Expat | review |
| deb | git | 1:2.43.0-1ubuntu7.3 | GPL-2 AND BSD-3-clause AND Zlib AND LGPL-2.1+ AND EDL-1.0 AND GPL-2+ AND Expat AND GPL-1+ or Artistic-1 AND ISC AND mingw-runtime AND Boost AND dlmalloc AND Apache-2.0 AND LGPL-2+ | obligations |
| deb | git-man | 1:2.43.0-1ubuntu7.3 | GPL-2 AND BSD-3-clause AND Zlib AND LGPL-2.1+ AND EDL-1.0 AND GPL-2+ AND Expat AND GPL-1+ or Artistic-1 AND ISC AND mingw-runtime AND Boost AND dlmalloc AND Apache-2.0 AND LGPL-2+ | obligations |
| deb | glib-networking:arm64 | 2.80.0-1build1 | LGPL-2+ and LGPL-2.1+ AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | glib-networking-common | 2.80.0-1build1 | LGPL-2+ and LGPL-2.1+ AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | glib-networking-services | 2.80.0-1build1 | LGPL-2+ and LGPL-2.1+ AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | gnome-bluetooth-3-common | 46.0-1ubuntu1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | gnome-desktop3-data | 44.0-5build2 | LGPL-2+ AND LGPL-3+ AND GPL-2+ AND Expat | obligations |
| deb | gnome-font-viewer | 46.0-1build1 | GPL-2+ | review |
| deb | gnome-icon-theme | 3.12.0-5 | GPL-2+ AND GPL-3+ | review |
| deb | gnome-keyring | 46.1-2ubuntu0.2 | GPL-2+ AND LGPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND BSD-3-clause and GPL-2+ or LGPL-3+ AND custom-license AND MPL-1.1 or GPL-2+ or LGPL-2.1+ AND GPL-2+ with AutoConf exception AND FSFAP AND FSFULLR AND GPL-3+ with AutoConf exception AND FSFULLR or GPL-2+ with AutoConf exception AND GPL-2+ with LibTool exception AND FSFULLR or GPL-2+ with LibTool exception AND Expat AND FSFUL AND LGPL-3+ AND MPL-1.1 | obligations |
| deb | gnome-keyring-pkcs11:arm64 | 46.1-2ubuntu0.2 | GPL-2+ AND LGPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND BSD-3-clause and GPL-2+ or LGPL-3+ AND custom-license AND MPL-1.1 or GPL-2+ or LGPL-2.1+ AND GPL-2+ with AutoConf exception AND FSFAP AND FSFULLR AND GPL-3+ with AutoConf exception AND FSFULLR or GPL-2+ with AutoConf exception AND GPL-2+ with LibTool exception AND FSFULLR or GPL-2+ with LibTool exception AND Expat AND FSFUL AND LGPL-3+ AND MPL-1.1 | obligations |
| deb | gnome-screenshot | 41.0-2build2 | GPL-2+ | review |
| deb | gnome-session-bin | 46.0-1ubuntu4 | This package is free software; you can redistribute it and/or modify | review |
| deb | gnome-session-common | 46.0-1ubuntu4 | This package is free software; you can redistribute it and/or modify | review |
| deb | gnome-settings-daemon | 46.0-1ubuntu1.24.04.1 | This package is free software; you can redistribute it and/or modify AND This package is free software; you can redistribute it and/or | review |
| deb | gnome-settings-daemon-common | 46.0-1ubuntu1.24.04.1 | This package is free software; you can redistribute it and/or modify AND This package is free software; you can redistribute it and/or | review |
| deb | gnome-shell | 46.0-0ubuntu6~24.04.14 | GPL-2+ (/usr/share/common-licenses/GPL-2) AND LGPL-2+ (/usr/share/common-licenses/LGPL-2) AND LGPL-2.1 (/usr/share/common-licenses/LGPL-2.1) | obligations |
| deb | gnome-shell-common | 46.0-0ubuntu6~24.04.14 | GPL-2+ (/usr/share/common-licenses/GPL-2) AND LGPL-2+ (/usr/share/common-licenses/LGPL-2) AND LGPL-2.1 (/usr/share/common-licenses/LGPL-2.1) | obligations |
| deb | gnome-software | 46.0-1ubuntu2 | GPL-2+ AND CC0-1.0 | review |
| deb | gnome-software-common | 46.0-1ubuntu2 | GPL-2+ AND CC0-1.0 | review |
| deb | gnome-software-plugin-snap | 46.0-1ubuntu2 | GPL-2+ AND CC0-1.0 | review |
| deb | gnome-startup-applications | 46.0-1ubuntu4 | This package is free software; you can redistribute it and/or modify | review |
| deb | gnome-system-monitor | 46.0-1build1 | GPL-2+ AND LGPL-2+ AND CC-BY-SA-4.0 | obligations |
| deb | gnome-user-docs | 46.0-1ubuntu1 | CC-BY-SA-3.0 | review |
| deb | gnome-user-docs-de | 46.0-1ubuntu1 | CC-BY-SA-3.0 | review |
| deb | gnome-user-docs-es | 46.0-1ubuntu1 | CC-BY-SA-3.0 | review |
| deb | gnome-user-docs-it | 46.0-1ubuntu1 | CC-BY-SA-3.0 | review |
| deb | gnome-user-docs-pt | 46.0-1ubuntu1 | CC-BY-SA-3.0 | review |
| deb | gnome-user-docs-ru | 46.0-1ubuntu1 | CC-BY-SA-3.0 | review |
| deb | gnome-user-docs-sl | 46.0-1ubuntu1 | CC-BY-SA-3.0 | review |
| deb | gnupg | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gnupg-l10n | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gnupg-utils | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gnupg2 | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gpg | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gpg-agent | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gpg-wks-client | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gpgconf | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gpgsm | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gpgv | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | gphoto2 | 2.5.28-2build2 | LGPL-2+ AND LGPL-2.1+ AND public_domain AND public_domain_1 AND GPL-2+ | obligations |
| deb | grep | 3.11-4build1 | GPL-3+ | review |
| deb | groff-base | 1.23.0-3build2 | UNKNOWN | unknown |
| deb | gsettings-desktop-schemas | 46.1-0ubuntu1 | LGPL-2.1+ | obligations |
| deb | gstreamer1.0-gl:arm64 | 1.24.2-1ubuntu0.4 | LGPL-2+ AND BSD (2 clause) AND MIT/X11 (BSD like) LGPL-2+ AND BSD (3 clause) AND GPL-2+ | obligations |
| deb | gstreamer1.0-packagekit | 1.2.8-2ubuntu1.5 | GPL-2+ and LGPL-2.1+ AND GPL-2+ AND LGPL-2.1+ AND FSFAP | obligations |
| deb | gstreamer1.0-pipewire:arm64 | 1.0.5-1ubuntu3.2 | Expat and LGPL-2.1+ AND Expat AND BZIP2 AND LGPL-2.1+ AND GPL-2 AND LGPL-2+ and LGPL-2.1+ and Expat AND LGPL-2+ AND FFTPACK | obligations |
| deb | gstreamer1.0-plugins-base:arm64 | 1.24.2-1ubuntu0.4 | LGPL-2+ AND BSD (2 clause) AND MIT/X11 (BSD like) LGPL-2+ AND BSD (3 clause) AND GPL-2+ | obligations |
| deb | gstreamer1.0-plugins-base-apps | 1.24.2-1ubuntu0.4 | LGPL-2+ AND BSD (2 clause) AND MIT/X11 (BSD like) LGPL-2+ AND BSD (3 clause) AND GPL-2+ | obligations |
| deb | gstreamer1.0-plugins-good:arm64 | 1.24.2-1ubuntu1.4 | LGPL-2+ AND LGPL-2.1+ AND MIT/X11 (BSD like) LGPL-2+ AND GPL-2+ AND LGPL AND LGPL-2 AND BSD (3 clause) AND BSD | obligations |
| deb | gstreamer1.0-pulseaudio:arm64 | 1.24.2-1ubuntu1.4 | LGPL-2+ AND LGPL-2.1+ AND MIT/X11 (BSD like) LGPL-2+ AND GPL-2+ AND LGPL AND LGPL-2 AND BSD (3 clause) AND BSD | obligations |
| deb | gstreamer1.0-tools | 1.24.2-1ubuntu0.1 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ AND GPL-3+ | obligations |
| deb | gstreamer1.0-x:arm64 | 1.24.2-1ubuntu0.4 | LGPL-2+ AND BSD (2 clause) AND MIT/X11 (BSD like) LGPL-2+ AND BSD (3 clause) AND GPL-2+ | obligations |
| deb | gtk-update-icon-cache | 3.24.41-4ubuntu1.3 | LGPL-2+ and LGPL-2.1+ and Expat AND GPL-3+ AND LGPL-2+ AND CC-BY-SA-4.0 AND unencumbered AND other AND SWL AND LGPL-2+ or SWL AND X11R5-permissive AND Expat AND Apache-2.0 AND LGPL-2+ and ZPL-2.1 AND check-gdk-cairo-permissive AND LGPL-2.1+ AND ZPL-2.1 | obligations |
| deb | gtk2-engines:arm64 | 1:2.20.2-5build4 | UNKNOWN | unknown |
| deb | gtk2-engines-murrine:arm64 | 0.98.2-4 | LGPL-2+ | obligations |
| deb | gtk2-engines-pixbuf:arm64 | 2.24.33-4ubuntu1.1 | tests/testnouiprint.c AND other | review |
| deb | gvfs:arm64 | 1.54.4-0ubuntu1~24.04.2 | LGPL-2+ AND GPL-3+ AND GPL-2+ | obligations |
| deb | gvfs-backends | 1.54.4-0ubuntu1~24.04.2 | LGPL-2+ AND GPL-3+ AND GPL-2+ | obligations |
| deb | gvfs-common | 1.54.4-0ubuntu1~24.04.2 | LGPL-2+ AND GPL-3+ AND GPL-2+ | obligations |
| deb | gvfs-daemons | 1.54.4-0ubuntu1~24.04.2 | LGPL-2+ AND GPL-3+ AND GPL-2+ | obligations |
| deb | gvfs-libs:arm64 | 1.54.4-0ubuntu1~24.04.2 | LGPL-2+ AND GPL-3+ AND GPL-2+ | obligations |
| deb | gzip | 1.12-1ubuntu3.1 | GPL-3+ AND GFDL-1.3+-no-invariant AND FSF-manpages | review |
| deb | haveged | 1.9.14-1ubuntu2 | GPL-3+ AND public-domain AND permissive-mconf AND permissive-nist | review |
| deb | hdparm | 9.65+ds-1build1 | hdparm AND GPL-2+ or BSD-2-clause AND GPL-2+ AND BSD-2-clause | review |
| deb | hicolor-icon-theme | 0.17-2 | GPL-2+ | review |
| deb | hostapd | 3:2.10-6~armbian22.02.3+1 | UNKNOWN | unknown |
| deb | hostname | 3.23+nmu2ubuntu2 | GPL-2 | review |
| deb | hplip | 3.23.12+dfsg0-0ubuntu5 | GPL-2+ AND BSD-2-clause AND BSD-3-clause AND Expat AND FSFUL AND public-domain AND GPL-2 | review |
| deb | hplip-data | 3.23.12+dfsg0-0ubuntu5 | GPL-2+ AND BSD-2-clause AND BSD-3-clause AND Expat AND FSFUL AND public-domain AND GPL-2 | review |
| deb | html2text | 1.3.2a-28 | GPL-2+ AND BSD-4-Clause AND GPL-1+ | review |
| deb | htop | 3.3.0-4build1 | GPL-2+ | review |
| deb | humanity-icon-theme | 0.6.16 | The Humanity Icon Theme is licensed under the GPL v2. | review |
| deb | hunspell-en-us | 1:2020.12.07-2 | UNKNOWN | unknown |
| deb | i2c-tools | 4.3-4build2 | UNKNOWN | unknown |
| deb | ibverbs-providers:arm64 | 50.0-2ubuntu0.2 | BSD-MIT or GPL-2 AND GPL-2+ AND BSD-2-clause AND CC0 AND MIT AND BSD-MIT AND GPL-2 or BSD-2-clause AND GPL-2 AND GPL-2 or BSD-3-clause AND BSD-2-clause or GPL-2 AND BSD-3-clause or GPL-2 AND CPL-1.0 or BSD-2-clause or GPL-2 AND BSD-3-clause AND CPL-1.0 | review |
| deb | idle | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | idn2 | 2.3.7-2build1.1 | GPL-3+ AND LGPL-3+ or GPL-2+ AND Unicode AND GPL-2+ AND LGPL-3+ | obligations |
| deb | ifenslave | 2.10ubuntu3 | GPL-3+ | review |
| deb | ifupdown | 0.8.41ubuntu1 | GPL-2+ | review |
| deb | indicator-common | 16.10.0+18.04.20180321.1-0ubuntu8 | GPL-3 | review |
| deb | indicator-printers | 0.1.7+17.10.20171101-0ubuntu7 | GPL-3 | review |
| deb | init | 1.66ubuntu1 | BSD-3-clause AND GPL-2+ | review |
| deb | init-system-helpers | 1.66ubuntu1 | BSD-3-clause AND GPL-2+ | review |
| deb | initramfs-tools | 0.142ubuntu25.8 | GPL v2 or any later version | review |
| deb | initramfs-tools-bin | 0.142ubuntu25.8 | GPL v2 or any later version | review |
| deb | initramfs-tools-core | 0.142ubuntu25.8 | GPL v2 or any later version | review |
| deb | inputattach | 1:1.8.1-2build1 | GPL-2+ AND public-domain | review |
| deb | install-info | 7.1-3build2 | GPL-3+ AND GPL-2+ AND GFDL-NIV-1.3+ | review |
| deb | inxi | 3.3.34-1-1 | GPL-3+ AND BSD-3-clause | review |
| deb | iotop | 0.6-42-ga14256a-0.2build1 | GPL-2+ | review |
| deb | iozone3 | 506-1 | UNKNOWN | unknown |
| deb | iperf3 | 3.16-1build2 | BSD-3-clause-iperf AND BSD-2-clause AND MIT/X11 AND BSD-3-clause-iperf+MIT/X11+BSD-3-clause AND BSD-3-clause AND NCSA AND FSF-permissive1 AND FSF-permissive2 AND GPL-2+ AND permissive AND MIT AND public-domain-1 AND GPL-3+ AND public-domain-2 AND GPL-2 | review |
| deb | iproute2 | 6.1.0-1ubuntu6.3 | GPL-2 | review |
| deb | iptables | 1.8.10-3ubuntu2 | GPL-2 AND Artistic AND GPL-2+ AND custom | review |
| deb | iputils-arping | 3:20240117-1ubuntu0.1 | BSD-3-clause AND GPL-2+ AND public-domain | review |
| deb | iputils-ping | 3:20240117-1ubuntu0.1 | BSD-3-clause AND GPL-2+ AND public-domain | review |
| deb | ir-keytable | 1.26.1-4build3 | GPL-2 AND LGPL-2.1+ AND BSD-3-clause or GPL-2+ AND GPL-2+ AND FSFULLR AND LGPL AND GPL-3+ AND BSD-3-clause or GPL-2 AND LGPL-2.1 AND BSD-2-clause AND jpeg-group AND LGPL-2+ AND BSD-3-clause AND Expat AND BSD-3-clause or LGPL-2.1 AND HPND-sell-variant | obligations |
| deb | isc-dhcp-client | 4.4.3-P1-4ubuntu2 | MPL-2.0 AND GPL-2 | obligations |
| deb | iso-codes | 4.16.0-1 | LGPL-2.1+ | obligations |
| deb | javascript-common | 11+nmu1 | GPL-2+ | review |
| deb | jq | 1.7.1-3ubuntu0.24.04.2 | MIT AND CC-BY-3.0 AND Expat AND GPL-2.0+ | review |
| deb | kbd | 2.6.4-2ubuntu2 | GPL-2+ AND GPL-any AND GPL-2-with-exceptions | review |
| deb | kerneloops | 0.12+git20140509-6ubuntu8 | UNKNOWN | unknown |
| deb | keyboard-configuration | 1.226ubuntu1 | UNKNOWN | unknown |
| deb | keyboxd | 2.4.4-2ubuntu17.4 | GPL-3+ AND permissive AND LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND Expat AND GPL-3+ or BSD-3-clause AND LGPL-3+ AND RFC-Reference AND TinySCHEME AND CC0-1.0 AND BSD-3-clause AND GPL-2+ | obligations |
| deb | keyutils | 1.6.3-3build1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | klibc-utils | 2.0.13-4ubuntu0.2 | BSD/GPL AND Note: The advertising clause in the license appearing on BSD Unix | review |
| deb | kmod | 31+20240202-2ubuntu7.2 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | krb5-locales | 1.20.1-6ubuntu2.6 | Copyright 2006 g10 Code GmbH AND Copyright 2004-2008 Apple Inc. All Rights Reserved. AND Copyright (c) 2011, PADL Software Pty Ltd. All rights reserved. | review |
| deb | language-pack-de | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-de-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-en | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-en-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-es | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-es-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-fr | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-fr-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-de | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-de-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-en | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-en-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-es | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-es-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-fr | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-fr-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-it | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-it-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-pt | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-pt-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-ru | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-ru-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-sl | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-gnome-sl-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-it | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-it-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-pt | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-pt-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-ru | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-ru-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-sl | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | language-pack-sl-base | 1:24.04+20260127 | UNKNOWN | unknown |
| deb | less | 590-2ubuntu2.1 | GPL-3+ or Less AND GPL-3+ AND Less AND GPL-3+ or Less, and X11 AND X11 AND Spencer-86 AND public-domain | review |
| deb | liba52-0.7.4:arm64 | 0.7.4-20build1 | GPL-2+ | review |
| deb | libaa1:arm64 | 1.4p5-51.1 | LGPL-2.0+ AND Custom AND Abstyles | obligations |
| deb | libaccountsservice0:arm64 | 23.13.9-2ubuntu6 | GPL-3+ AND GPL-2+ | review |
| deb | libacl1:arm64 | 2.3.2-1build1.1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libadwaita-1-0:arm64 | 1.5.0-1ubuntu2 | LGPL-2.1+ AND GPL-3+ AND CC0-1.0 AND CC-BY-SA-4.0 | obligations |
| deb | libaec0:arm64 | 1.1.2-1build1 | UNKNOWN | unknown |
| deb | libao-common | 1.2.2+20180113-1.1ubuntu4 | UNKNOWN | unknown |
| deb | libao4:arm64 | 1.2.2+20180113-1.1ubuntu4 | UNKNOWN | unknown |
| deb | libapparmor1:arm64 | 4.0.1really4.0.1-0ubuntu0.24.04.7 | GPL-2+ AND BSD-3-clause or GPL-2+ AND LGPL-2.1+ AND GPL-2 AND BSD-3-clause | obligations |
| deb | libappstream5:arm64 | 1.0.2-1build6 | GPL-2+ and LGPL-2.1+ AND LGPL-2.1+ AND GPL-2+ AND FSFAP AND SIL-1.1 | obligations |
| deb | libapt-pkg6.0t64:arm64 | 2.8.3 | GPL-2+ AND GPL-2 AND BSD-3-clause AND Expat | review |
| deb | libaribb24-0t64:arm64 | 1.0.3-2.1build2 | LGPL-3+ | obligations |
| deb | libarmadillo12 | 1:12.6.7+dfsg-1build2 | Apache AND GPL-2 | review |
| deb | libasan6:arm64 | 11.5.0-1ubuntu1~24.04.1 | UNKNOWN | unknown |
| deb | libasan8:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libasound2-data | 1.2.11-1ubuntu0.2 | LPGL-2.1+ | review |
| deb | libasound2-plugins:arm64 | 1.2.7.1-1ubuntu5 | LGPL-2.1+ | obligations |
| deb | libasound2t64:arm64 | 1.2.11-1ubuntu0.2 | LPGL-2.1+ | review |
| deb | libaspell15:arm64 | 0.60.8.1-1build1 | LGPL-2.1+ AND GFDL-1.2+ | obligations |
| deb | libass9:arm64 | 1:0.17.1-2build1 | ISC AND NTP AND Unlicense AND GPL-2+ | review |
| deb | libassuan0:arm64 | 2.5.6-1build1 | LGPL-2.1+ AND GAP~FSF AND LGPL-3+ AND GPL-2+ with libtool exception AND GPL-3+ AND GAP AND GPL-2+ | obligations |
| deb | libasyncns0:arm64 | 0.8-6build4 | LGPL-2.1+ | obligations |
| deb | libatasmart4:arm64 | 0.19-5build3 | This package is free software; you can redistribute it and/or | review |
| deb | libatk-adaptor:arm64 | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | libatk-bridge2.0-0t64:arm64 | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | libatk1.0-0t64:arm64 | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | libatkmm-1.6-1v5:arm64 | 2.28.4-1build4 | LGPL-2.1+ AND GPL-2+ AND LGPL-2+ | obligations |
| deb | libatm1t64:arm64 | 1:2.5.1-5.1build1 | UNKNOWN | unknown |
| deb | libatomic1:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libatopology2t64:arm64 | 1.2.11-1ubuntu0.2 | LPGL-2.1+ | review |
| deb | libatspi2.0-0t64:arm64 | 2.52.0-1build1 | LGPL-2+ AND LGPL-2.1+ AND AFL-2.1 or GPL-2+ AND GPL-2 AND public-domain AND AFL-2.1 AND GPL-2+ | obligations |
| deb | libattr1:arm64 | 1:2.5.2-1build1.1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libaudit-common | 1:3.1.2-2.1build1.1 | GPL-2 AND LGPL-2.1 | obligations |
| deb | libaudit1:arm64 | 1:3.1.2-2.1build1.1 | GPL-2 AND LGPL-2.1 | obligations |
| deb | libauthen-sasl-perl | 2.1700-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libavahi-client3:arm64 | 0.8-13ubuntu6.2 | UNKNOWN | unknown |
| deb | libavahi-common-data:arm64 | 0.8-13ubuntu6.2 | UNKNOWN | unknown |
| deb | libavahi-common3:arm64 | 0.8-13ubuntu6.2 | UNKNOWN | unknown |
| deb | libavahi-core7:arm64 | 0.8-13ubuntu6.2 | UNKNOWN | unknown |
| deb | libavahi-glib1:arm64 | 0.8-13ubuntu6.2 | UNKNOWN | unknown |
| deb | libavc1394-0:arm64 | 0.5.4-5build3 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libavcodec-dev:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libavcodec60:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libavdevice60:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libavfilter9:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libavformat-dev:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libavformat60:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libavutil-dev:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libavutil58:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libayatana-appindicator3-1 | 0.5.93-1build3 | LGPL-2.1 or LGPL-3 or GPL-3 AND BSD-2-clause AND GPL-3 AND LGPL-2.1 or LGPL-3 AND BSD-3-clause AND GPL-3 or LGPL-2.1 or LGPL-3 AND LGPL-2.1 AND LGPL-3 AND public-domain | obligations |
| deb | libayatana-ido3-0.4-0:arm64 | 0.10.1-1build2 | GPL-3 AND LGPL-2.1 or LGPL-3 AND GPL-3 or LGPL-2.1 or LGPL-3 AND LGPL-2+ AND BSD-2-clause AND BSD-3-clause AND GPL-3 or LGPL-3 or LGPL-2.1 AND LGPL-2.1 AND LGPL-3 | obligations |
| deb | libayatana-indicator3-7:arm64 | 0.9.4-1build1 | GPL-3 | review |
| deb | libbinutils:arm64 | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | libblkid-dev:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | libblkid1:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | libblockdev-crypto3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev-fs3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev-loop3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev-mdraid3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev-nvme3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev-part3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev-swap3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev-utils3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libblockdev3:arm64 | 3.1.1-1ubuntu0.1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libbluetooth3:arm64 | 5.72-0ubuntu5.5 | GPL-2+ AND LGPL-2.1+ AND Apache-2.0 AND BSD-2-clause | obligations |
| deb | libbluray2:arm64 | 1:1.3.4-1build1 | LGPL-2.1+ AND custom AND GPL-2+ AND BSD-3-clause AND MPL-1.0 or GPL-2+ or LGPL-2.1+ AND MPL-1.0 | obligations |
| deb | libbpf1:arm64 | 1:1.3.0-2build2 | LGPL-2.1 or BSD-2-Clause AND GPL-2.0 AND GPL-2 with Linux-syscall-note exception AND GPL-2 with Linux-syscall-note exception OR BSD-3-Clause AND GPL-2+ AND LGPL-2.1 AND BSD-2-Clause AND BSD-3-Clause | obligations |
| deb | libbrlapi0.8:arm64 | 6.6-4ubuntu5 | UNKNOWN | unknown |
| deb | libbs2b0:arm64 | 3.1.0+dfsg-7build1 | Expat AND GPL-3+ AND GPL-2+ AND MIT+FSF-public AND FSF-unlimited | review |
| deb | libbytesize-common | 2.10-1ubuntu2 | LGPL-2.1+ | obligations |
| deb | libbytesize1:arm64 | 2.10-1ubuntu2 | LGPL-2.1+ | obligations |
| deb | libbz2-1.0:arm64 | 1.0.8-5.1build0.1 | BSD-variant AND GPL-2 | review |
| deb | libc-bin | 2.39-0ubuntu8.7 | UNKNOWN | unknown |
| deb | libc-dev-bin | 2.39-0ubuntu8.7 | UNKNOWN | unknown |
| deb | libc-devtools | 2.39-0ubuntu8.7 | UNKNOWN | unknown |
| deb | libc6:arm64 | 2.39-0ubuntu8.7 | UNKNOWN | unknown |
| deb | libc6-dev:arm64 | 2.39-0ubuntu8.7 | UNKNOWN | unknown |
| deb | libcaca0:arm64 | 0.99.beta20-4ubuntu0.2 | WTFPL-2 AND ISC AND LGPL-2+ AND GPL-2+ AND GPL | obligations |
| deb | libcairo-gobject-perl | 1.005-4build3 | LGPL-2.1+ | obligations |
| deb | libcairo-gobject2:arm64 | 1.18.0-3build1 | UNKNOWN | unknown |
| deb | libcairo-perl | 1.109-4build1 | LGPL-2.1+ AND Artistic or GPL-1+ AND Artistic AND GPL-1+ | obligations |
| deb | libcairo-script-interpreter2:arm64 | 1.18.0-3build1 | UNKNOWN | unknown |
| deb | libcairo2:arm64 | 1.18.0-3build1 | UNKNOWN | unknown |
| deb | libcairomm-1.0-1v5:arm64 | 1.14.5-1build1 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libcairomm-1.16-1:arm64 | 1.18.0-1build1 | LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | libcamel-1.2-64t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libcanberra-gtk3-0t64:arm64 | 0.30-10ubuntu10 | UNKNOWN | unknown |
| deb | libcanberra0t64:arm64 | 0.30-10ubuntu10 | UNKNOWN | unknown |
| deb | libcap-ng0:arm64 | 0.8.4-2build2 | LGPL-2.1+ AND GPL-2+ AND GPL-3 | obligations |
| deb | libcap2:arm64 | 1:2.66-5ubuntu2.4 | BSD-3-clause or GPL-2 AND BSD-3-clause or GPL-2+ AND BSD-3-clause AND GPL-2 AND GPL-2+ | review |
| deb | libcap2-bin | 1:2.66-5ubuntu2.4 | BSD-3-clause or GPL-2 AND BSD-3-clause or GPL-2+ AND BSD-3-clause AND GPL-2 AND GPL-2+ | review |
| deb | libcbor0.10:arm64 | 0.10.2-1.2ubuntu2 | Expat | review |
| deb | libcc1-0:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libcddb2 | 1.3.2-7fakesync1build1 | LGPL-2+ | obligations |
| deb | libcdio-cdda2t64:arm64 | 10.2+2.0.1-1.1build2 | UNKNOWN | unknown |
| deb | libcdio-paranoia2t64:arm64 | 10.2+2.0.1-1.1build2 | UNKNOWN | unknown |
| deb | libcdio19t64:arm64 | 2.1.0-4.1ubuntu1.2 | GPL-3 AND GPL-2+ with autoconf-macro exception AND GPL-3 and GFDL-1.2 AND GFDL-1.2 | review |
| deb | libcdparanoia0:arm64 | 3.10.2+debian-14build3 | GPL-2+ AND LGPL-2.1+ | obligations |
| deb | libcfitsio10t64:arm64 | 4.3.1-1.1build2 | Permission to freely use, copy, modify, and distribute this software | review |
| deb | libchromaprint1:arm64 | 1.5.1-5 | Expat AND BSD-3-clause AND LGPL-2.1+ | obligations |
| deb | libclone-perl:arm64 | 0.46-1build3 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libcodec2-1.2:arm64 | 1.2.0-2build1 | LGPL-2.1 AND JMVBSD AND KISSFFTBSD | obligations |
| deb | libcolord2:arm64 | 1.4.7-1build2 | GPL-2+ AND LGPL-2.1+ AND GFDL-NIV AND CC0-1.0 AND CC0-1.0 and NPES AND NPES | obligations |
| deb | libcolorhug2:arm64 | 1.4.7-1build2 | GPL-2+ AND LGPL-2.1+ AND GFDL-NIV AND CC0-1.0 AND CC0-1.0 and NPES AND NPES | obligations |
| deb | libcom-err2:arm64 | 1.47.0-2.4~exp1ubuntu4.1 | GPL-2 AND LGPL-2 AND BSD-3-Clause AND Apache-2 AND ISC AND GPL or MIT-US-export AND Kazlib AND Latex2e AND GPL-2+ with Texinfo exception | obligations |
| deb | libcpufreq0 | 008-2build2 | GPL-2 | review |
| deb | libcrack2:arm64 | 2.9.6-5.1build2 | LGPL-2.1 | obligations |
| deb | libcrypt-dev:arm64 | 1:4.4.36-4build1 | UNKNOWN | unknown |
| deb | libcrypt1:arm64 | 1:4.4.36-4build1 | UNKNOWN | unknown |
| deb | libcryptsetup12:arm64 | 2:2.7.0-1ubuntu4.2 | GPL-2+ with OpenSSL exception AND GPL-2+ AND GPL-3+ AND LGPL-2.1+ AND LGPL-2.1+ with OpenSSL exception AND CC0 or Apache-2.0 AND public-domain AND CC0 AND Apache-2.0 | obligations |
| deb | libctf-nobfd0:arm64 | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | libctf0:arm64 | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | libcups2t64:arm64 | 2.4.7-1.2ubuntu7.14 | Apache-2.0-with-GPL2-LGPL2-Exception AND FSFUL AND Zlib AND Apache-2.0 AND Apache-2.0-with-GPL2-LGPL2-Exception or BSD-2-clause AND BSD-2-Clause | obligations |
| deb | libcupsfilters2-common | 2.0.0-0ubuntu7.2 | Apache-2.0-with-GPL2-LGPL2-Exception AND GPL-2+ | obligations |
| deb | libcupsfilters2t64:arm64 | 2.0.0-0ubuntu7.2 | Apache-2.0-with-GPL2-LGPL2-Exception AND GPL-2+ | obligations |
| deb | libcurl3t64-gnutls:arm64 | 8.5.0-2ubuntu10.9 | curl AND OLDAP-2.8 AND ISC AND GPL-2+ with Autoconf-data exception AND GPL-3+ with Autoconf-data exception AND GPL-2+ with Libtool exception AND BSD-3-clause AND BSD-4-Clause-UC AND FSFULLR AND X11 AND BSD-3-Clause | review |
| deb | libcurl4t64:arm64 | 8.5.0-2ubuntu10.9 | curl AND OLDAP-2.8 AND ISC AND GPL-2+ with Autoconf-data exception AND GPL-3+ with Autoconf-data exception AND GPL-2+ with Libtool exception AND BSD-3-clause AND BSD-4-Clause-UC AND FSFULLR AND X11 AND BSD-3-Clause | review |
| deb | libcwidget4:arm64 | 0.5.18-6build1 | GPL-2+ | review |
| deb | libdaemon0:arm64 | 0.14-7.1ubuntu4 | libdaemon is free software; you can redistribute it and/or modify | review |
| deb | libdata-dump-perl | 1.25-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libdatrie1:arm64 | 0.2.13-3build1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libdb5.3t64:arm64 | 5.3.28+dfsg2-7 | Sleepycat and BSD-3-clause AND Sleepycat AND BSD-3-clause AND Ms-PL AND GPL or Artistic AND X11 AND MIT-old AND TCL-like AND BSD-3-clause-fjord AND GPL-3 AND zlib AND Artistic or BSD-3-clause AND GPL | review |
| deb | libdbus-1-3:arm64 | 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat and Tcl-BSDish AND GPL-2+ AND BSD-3-clause and BSD-3-clause-generic AND autoconf-archive-permissive AND FSF-unlimited-permission AND LGPL-2.1+ AND g10-permissive AND Expat AND Tcl-BSDish AND BSD-3-clause AND BSD-3-clause-generic AND AFL-2.1 | obligations |
| deb | libdbus-glib-1-2:arm64 | 0.112-3build2 | GPL-2+ or AFL-2.1 AND GPL-2+ AND GPL-2+ or AFL-2.1 or Expat AND Expat AND AFL-2.1 | review |
| deb | libdbusmenu-glib4:arm64 | 18.10.20180917~bzr492+repack1-3.1ubuntu5 | GPL-3 AND LGPL-2.1 or LGPL-3 AND LGPL-2.1 AND LGPL-3 | obligations |
| deb | libdbusmenu-gtk3-4:arm64 | 18.10.20180917~bzr492+repack1-3.1ubuntu5 | GPL-3 AND LGPL-2.1 or LGPL-3 AND LGPL-2.1 AND LGPL-3 | obligations |
| deb | libdc1394-25:arm64 | 2.2.6-4build1 | UNKNOWN | unknown |
| deb | libdc1394-dev:arm64 | 2.2.6-4build1 | UNKNOWN | unknown |
| deb | libdca0:arm64 | 0.0.7-2build1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libdconf1:arm64 | 0.40.0-4ubuntu0.1 | LGPL-2+ AND GPL-3 | obligations |
| deb | libde265-0:arm64 | 1.0.15-1build3 | LGPL-3+ AND GPL-3+ AND BSD-4-clause AND public-domain-1 AND other-1 | obligations |
| deb | libdebconfclient0:arm64 | 0.271ubuntu3 | BSD-2-Clause AND GPL-2+ AND BSD-2-clause | review |
| deb | libdecor-0-0:arm64 | 0.2.2-1build2 | Expat AND GPL-3.0+ | review |
| deb | libdeflate-dev:arm64 | 1.19-1build1.1 | Expat | review |
| deb | libdeflate0:arm64 | 1.19-1build1.1 | Expat | review |
| deb | libdevmapper1.02.1:arm64 | 2:1.02.185-3ubuntu3.2 | GPL-2.0 AND LGPL-2.1 AND BSD-2-Clause AND GPL-2.0+ | obligations |
| deb | libdigest-sha-perl | 6.04-1build3 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libdjvulibre-text | 3.5.28-2ubuntu0.24.04.2 | UNKNOWN | unknown |
| deb | libdjvulibre21:arm64 | 3.5.28-2ubuntu0.24.04.2 | UNKNOWN | unknown |
| deb | libdotconf0:arm64 | 1.3-0.3fakesync1build3 | LGPL-2.1 AND Apache-1.1 | obligations |
| deb | libdpkg-perl | 1.22.6ubuntu6.6 | GPL-2+ AND public-domain-s-s-d | review |
| deb | libdrm-amdgpu1:arm64 | 2.4.125-1ubuntu0.1~24.04.2 | UNKNOWN | unknown |
| deb | libdrm-common | 2.4.125-1ubuntu0.1~24.04.2 | UNKNOWN | unknown |
| deb | libdrm2:arm64 | 2.4.125-1ubuntu0.1~24.04.2 | UNKNOWN | unknown |
| deb | libduktape207:arm64 | 2.7.0+tests-0ubuntu3 | expat AND unicode AND CC0 | review |
| deb | libdv4t64:arm64 | 1.0.0-17.1build1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libdvbpsi10:arm64 | 1.3.3-1build1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libdvdnav4:arm64 | 6.1.1-3build1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libdvdread8t64:arm64 | 6.1.3-1.1build1 | GPL-2+ AND LGPL-2.1+ AND GPL-2 or GPL-3 AND GPL-2 AND GPL-3 | obligations |
| deb | libdw1t64:arm64 | 0.190-1.1ubuntu0.1 | GPL-3+ AND LGPL-3+ or GPL-2+ AND BSD-2-clause AND GFDL-NIV-1.3 AND LGPL-2.1+ AND GPL-3+ with Bison exception | obligations |
| deb | libebackend-1.2-11t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libebml5:arm64 | 1.4.5-1 | LGPL-2.1 AND GPL-2+ | obligations |
| deb | libebook-1.2-21t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libebook-contacts-1.2-4t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libecal-2.0-3:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libedata-book-1.2-27t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libedata-cal-2.0-2t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libedataserver-1.2-27t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libedataserverui-1.2-4t64:arm64 | 3.52.3-0ubuntu1.2 | UNKNOWN | unknown |
| deb | libegl-mesa0:arm64 | 25.2.8-0ubuntu0.24.04.2 | MIT AND GPL-2 AND GPL-2 or MIT AND GPL-1+ AND BSD-3-google AND Khronos AND Apache-2.0 AND BSL AND MLAA AND SGI AND BSD-2-clause AND MIT OR Apache-2.0 AND (MIT OR Apache-2.0) AND Unicode-DFS-2016 AND Apache-2.0 OR MIT AND GPL AND Unicode-DFS-2016 | review |
| deb | libegl1:arm64 | 1.7.0-1build1 | MIT AND Apache-2.0 AND public-domain AND GPL-3+ AND BSD-1-clause AND GPL | review |
| deb | libeis1:arm64 | 1.2.1-1 | Expat | review |
| deb | libelf1t64:arm64 | 0.190-1.1ubuntu0.1 | GPL-3+ AND LGPL-3+ or GPL-2+ AND BSD-2-clause AND GFDL-NIV-1.3 AND LGPL-2.1+ AND GPL-3+ with Bison exception | obligations |
| deb | libenchant-2-2:arm64 | 2.3.3-2build2 | LGPL-2.1+ AND Expat AND LGPL-2.0+ AND LGPL-3.0+ AND GPL-3.0+ AND FSFAP AND GPL-2.0+ | obligations |
| deb | libencode-locale-perl | 1.05-3 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libepoxy0:arm64 | 1.5.10-1build1 | Expat | review |
| deb | liberror-perl | 0.17029-2 | Artistic or GPL-1+ AND MIT/X11 AND Artistic AND GPL-1+ | review |
| deb | libestr0:arm64 | 0.1.11-1build1 | LGPL-2.1+ | obligations |
| deb | libevdev2:arm64 | 1.13.1+dfsg-1build1 | MIT AND Apache-2.0 AND BSD-3 AND GPL-2 AND GPL-2+ | review |
| deb | libevdocument3-4t64:arm64 | 46.3.1-0ubuntu1.1 | UNKNOWN | unknown |
| deb | libevent-core-2.1-7t64:arm64 | 2.1.12-stable-9ubuntu2 | BSD-3-clause AND FSFULLR AND FSFULLR-No-Warranty AND Expat AND BSD-2-clause AND BSL AND FSFUL AND GPL-2+ AND GPL-3+ AND ISC AND curl | review |
| deb | libevent-pthreads-2.1-7t64:arm64 | 2.1.12-stable-9ubuntu2 | BSD-3-clause AND FSFULLR AND FSFULLR-No-Warranty AND Expat AND BSD-2-clause AND BSL AND FSFUL AND GPL-2+ AND GPL-3+ AND ISC AND curl | review |
| deb | libevview3-3t64:arm64 | 46.3.1-0ubuntu1.1 | UNKNOWN | unknown |
| deb | libexif-dev:arm64 | 0.6.24-1build2 | LGPL-2.1+ AND MIT AND public-domain AND LGPL-2+ AND BSD-2-Clause and LGPL-2.1+ AND GPL-2+ AND BSD-2-Clause | obligations |
| deb | libexif12:arm64 | 0.6.24-1build2 | LGPL-2.1+ AND MIT AND public-domain AND LGPL-2+ AND BSD-2-Clause and LGPL-2.1+ AND GPL-2+ AND BSD-2-Clause | obligations |
| deb | libexiv2-27:arm64 | 0.27.6-1ubuntu0.3 | GPL-2+ AND BSD-3-clause AND Expat | review |
| deb | libexo-2-0:arm64 | 4.18.0-1build4 | UNKNOWN | unknown |
| deb | libexo-common | 4.18.0-1build4 | UNKNOWN | unknown |
| deb | libext2fs2t64:arm64 | 1.47.0-2.4~exp1ubuntu4.1 | GPL-2 AND LGPL-2 AND BSD-3-Clause AND Apache-2 AND ISC AND GPL or MIT-US-export AND Kazlib AND Latex2e AND GPL-2+ with Texinfo exception | obligations |
| deb | libextutils-depends-perl | 0.8001-2 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libfaad2:arm64 | 2.11.1-1build1 | GPL-2+ AND GPL-3+ | review |
| deb | libfabric1:arm64 | 1.17.0-3build2 | BSD-2-clause or GPL-2 AND Expat AND GPL-2+ | review |
| deb | libfcitx-config4:arm64 | 1:4.2.9.9-2build2 | GPL-2+ AND BSD-3-Clause AND DEC-BSD-LIKE AND FUJITSU-BSD-LIKE AND SUN-HP-BSD-LIKE AND LGPL-2+ AND MIT AND BSD-1-Clause | obligations |
| deb | libfcitx-core0:arm64 | 1:4.2.9.9-2build2 | GPL-2+ AND BSD-3-Clause AND DEC-BSD-LIKE AND FUJITSU-BSD-LIKE AND SUN-HP-BSD-LIKE AND LGPL-2+ AND MIT AND BSD-1-Clause | obligations |
| deb | libfcitx-utils0:arm64 | 1:4.2.9.9-2build2 | GPL-2+ AND BSD-3-Clause AND DEC-BSD-LIKE AND FUJITSU-BSD-LIKE AND SUN-HP-BSD-LIKE AND LGPL-2+ AND MIT AND BSD-1-Clause | obligations |
| deb | libfdisk1:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | libfdt1:arm64 | 1.7.0-2build1 | GPL-2+ AND GPL-2+ or BSD-2-clause AND LGPL-2.1+ AND BSD-2-clause | obligations |
| deb | libffi-dev:arm64 | 3.4.6-1build1 | Expat AND X11 AND GPL-2+ AND GPL-3+ AND MPL-1.1 or GPL-2+ or LGPL-2.1+ AND public-domain AND GPL | obligations |
| deb | libffi8:arm64 | 3.4.6-1build1 | Expat AND X11 AND GPL-2+ AND GPL-3+ AND MPL-1.1 or GPL-2+ or LGPL-2.1+ AND public-domain AND GPL | obligations |
| deb | libfftw3-double3:arm64 | 3.3.10-1ubuntu3 | GPL-2+ | review |
| deb | libfftw3-single3:arm64 | 3.3.10-1ubuntu3 | GPL-2+ | review |
| deb | libfile-listing-perl | 6.16-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libflac12t64:arm64 | 1.4.3+ds-2.1ubuntu2 | GPL-2+ or LGPL-2.1+ AND GFDL-1.1+ AND GPL-2+ AND BSD-3-clause AND LGPL-2.1+ AND LGPL-2+ AND Public-domain AND ISC | obligations |
| deb | libflashrom1:arm64 | 1.3.0-2.1ubuntu2 | GPL-2+ AND GPL-2 AND PD | review |
| deb | libfont-afm-perl | 1.20-4 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libfontconfig1:arm64 | 2.15.0-1.1ubuntu2 | UNKNOWN | unknown |
| deb | libfontenc1:arm64 | 1:1.1.8-1build1 | UNKNOWN | unknown |
| deb | libfreetype6:arm64 | 2.13.2+dfsg-1ubuntu0.1 | FTL AND FTL and Expat AND BSD-3-Clause AND FSFAP AND GPL-3+ AND Expat AND GPL-2+ AND Public-Domain AND MIT-SMC AND BSL-1.0 AND MIT-Modern-Variant AND Zlib AND OpenGroup-MIT | review |
| deb | libfreexl1:arm64 | 2.0.0-1build2 | MPL-1.1 or GPL-2+ or LGPL-2.1+ AND GPL-2+ AND LGPL-2.1+ AND MPL-1.1 | obligations |
| deb | libfribidi0:arm64 | 1.0.13-3build1 | LGPL-2.1+ | obligations |
| deb | libftdi1-2:arm64 | 1.5-6build5 | * The C library "libftdi1" is distributed under the | review |
| deb | libfuse2t64:arm64 | 2.9.9-8.1build1 | GPL-2 AND LGPL-2 AND GPL-2+ | obligations |
| deb | libfuse3-3:arm64 | 3.14.0-5build1 | GPL-2 AND LGPL-2.1 AND GPL-2+ | obligations |
| deb | libfwupd2:arm64 | 1.9.34-0ubuntu1~24.04.1 | LGPL-2.1+ AND CC0-1.0 | obligations |
| deb | libfwupd3:arm64 | 2.0.20-1ubuntu2~24.04.1 | LGPL-2.1-or-later AND CC0-1.0 | obligations |
| deb | libfyba0t64:arm64 | 4.1.1-11build1 | MIT AND GPL-2.0+ | review |
| deb | libgail-common:arm64 | 2.24.33-4ubuntu1.1 | tests/testnouiprint.c AND other | review |
| deb | libgail18t64:arm64 | 2.24.33-4ubuntu1.1 | tests/testnouiprint.c AND other | review |
| deb | libgarcon-1-0:arm64 | 4.18.1-1build3 | LGPL-2+ | obligations |
| deb | libgarcon-common | 4.18.1-1build3 | LGPL-2+ | obligations |
| deb | libgarcon-gtk3-1-0:arm64 | 4.18.1-1build3 | LGPL-2+ | obligations |
| deb | libgbm1:arm64 | 25.2.8-0ubuntu0.24.04.2 | MIT AND GPL-2 AND GPL-2 or MIT AND GPL-1+ AND BSD-3-google AND Khronos AND Apache-2.0 AND BSL AND MLAA AND SGI AND BSD-2-clause AND MIT OR Apache-2.0 AND (MIT OR Apache-2.0) AND Unicode-DFS-2016 AND Apache-2.0 OR MIT AND GPL AND Unicode-DFS-2016 | review |
| deb | libgcc-11-dev:arm64 | 11.5.0-1ubuntu1~24.04.1 | UNKNOWN | unknown |
| deb | libgcc-13-dev:arm64 | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libgcc-14-dev:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libgcc-s1:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libgccjit0:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libgck-1-0:arm64 | 3.41.2-1build3 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | libgck-2-2:arm64 | 4.2.0-5 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | libgcr-4-4:arm64 | 4.2.0-5 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | libgcr-base-3-1:arm64 | 3.41.2-1build3 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | libgcr-ui-3-1:arm64 | 3.41.2-1build3 | LGPL-2.1+ AND bzip2-1.0.5 | obligations |
| deb | libgcrypt20:arm64 | 1.10.3-2ubuntu0.1 | Most of the package is licensed under the GNU Lesser General Public | review |
| deb | libgd3:arm64 | 2.3.3-9ubuntu5 | GD AND GAP~Makefile.in AND GPL-2+ with Autoconf exception AND BSD-3-clause AND GAP~configure AND MIT AND HPND AND XFIG AND WEBP AND GPL-2+ | review |
| deb | libgdal34t64:arm64 | 3.8.4+dfsg-3ubuntu3 | Expat AND Qhull AND HPND-p-sl-sgi AND public-domain AND HPND-sl-sgi AND HPND-sl-gl-sgi AND HPND-eos AND IJG AND ITT AND Apache-2.0 AND Apache-2.0 and BSD-3-Clause AND BSD-3-Clause AND libpng AND fontconfig AND zlib AND ISC AND Expat and GPL-3+ with Bison exception AND Expat and PostgreSQL AND Expat or LGPL-2+ AND GPL-3+ with Bison exception AND HPND-3i AND Expat and Base64 AND cpl-mem-cache AND Info-ZIP AND HPND-disclaimer AND Expat and zlib AND LGPL-2+ AND Base64 AND PostgreSQL | obligations |
| deb | libgdata-common | 0.18.1-6build2 | LGPL-2.1+ | obligations |
| deb | libgdata22:arm64 | 0.18.1-6build2 | LGPL-2.1+ | obligations |
| deb | libgdbm-compat4t64:arm64 | 1.23-5.1build1 | GPL-3+ AND GPL-2+ AND GFDL-NIV-1.3+ | review |
| deb | libgdbm6t64:arm64 | 1.23-5.1build1 | GPL-3+ AND GPL-2+ AND GFDL-NIV-1.3+ | review |
| deb | libgdcm-dev | 3.0.22-2.1ubuntu1 | BSD-3-clause-alike-CREATIS AND Apache-2.0 AND LGPL-2+ AND BSD-3-clause-alike-Mathieu-Malaterre AND BSD-3-clause-alike-Alexander-Chemeris AND BSD-3-clause-alike-Jan-de-Vaan AND Expat AND gdcmjpeg AND zlib/libpng AND BSD-2-clause AND BSL AND BSD-3-clause-alike-Theodore-Ts AND Zlib AND BSD-4-clause AND public-domain AND socketxx | obligations |
| deb | libgdcm3.0t64:arm64 | 3.0.22-2.1ubuntu1 | BSD-3-clause-alike-CREATIS AND Apache-2.0 AND LGPL-2+ AND BSD-3-clause-alike-Mathieu-Malaterre AND BSD-3-clause-alike-Alexander-Chemeris AND BSD-3-clause-alike-Jan-de-Vaan AND Expat AND gdcmjpeg AND zlib/libpng AND BSD-2-clause AND BSL AND BSD-3-clause-alike-Theodore-Ts AND Zlib AND BSD-4-clause AND public-domain AND socketxx | obligations |
| deb | libgdk-pixbuf-2.0-0:arm64 | 2.42.10+dfsg-3ubuntu3.3 | LGPL-2+ and LGPL-2.1+ and CC0-1.0 AND GPL-2+ AND CC0-1.0 AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | libgdk-pixbuf2.0-bin | 2.42.10+dfsg-3ubuntu3.3 | LGPL-2+ and LGPL-2.1+ and CC0-1.0 AND GPL-2+ AND CC0-1.0 AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | libgdk-pixbuf2.0-common | 2.42.10+dfsg-3ubuntu3.3 | LGPL-2+ and LGPL-2.1+ and CC0-1.0 AND GPL-2+ AND CC0-1.0 AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | libgdm1 | 46.2-1ubuntu1~24.04.9 | This package is free software; you can redistribute it and/or modify | review |
| deb | libgeoclue-2-0:arm64 | 2.7.0-3ubuntu7 | GPL-2+ AND GFDL-NIV-1.1+ AND LGPL-2+ | obligations |
| deb | libgeocode-glib-2-0:arm64 | 3.26.3-6build3 | LGPL-2+ AND BSD-3-clause AND ODbL-1.0 | obligations |
| deb | libgeos-c1t64:arm64 | 3.12.1-3build1 | LGPL-2.1+ AND Expat AND Apache-2.0 or BSL-1.0 AND zlib AND Apache-2.0 AND BSL-1.0 | obligations |
| deb | libgeos3.12.1t64:arm64 | 3.12.1-3build1 | LGPL-2.1+ AND Expat AND Apache-2.0 or BSL-1.0 AND zlib AND Apache-2.0 AND BSL-1.0 | obligations |
| deb | libgeotiff5:arm64 | 1.7.1-5build1 | attribution AND MIT AND BSD-3-Clause AND BSD-4-Clause AND HPND-sl-sgi AND GPL-2+ | review |
| deb | libgettextpo0:arm64 | 0.21-14ubuntu2 | UNKNOWN | unknown |
| deb | libgfortran5:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libgirepository-1.0-1:arm64 | 1.80.1-1 | GPL-2+ AND LGPL-2+ AND LGPL-2 or MPL-1.1 AND LGPL-2.1+ AND BSD-2-clause AND FSFAP and FSFULLR AND Expat and GPL-2+ AND LGPL-2+ and LGPL-2.1+ and FSFULLR and CC0-1.0 AND AFL-2.0 or LGPL-2.1+ AND Unicode-DFS-2016 AND Expat AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND GPL with Autoconf exception AND AFL-2.0 AND CC0-1.0 AND FSFAP AND FSFULLR AND Kuchling-PD AND LGPL-2 AND MPL-1.1 AND Plumb-PD | obligations |
| deb | libgirepository-2.0-0:arm64 | 2.80.0-6ubuntu3.8 | LGPL-2.1+ AND old-glib-tests AND AFL-2.0 or LGPL-2.1+ AND Janik-permissive AND LGPL-2+ AND FSFULLR AND Iconv-PD AND CC0-1.0 AND CC0-1.0 or Mingw-PD AND Janik-permissive and old-glib-tests AND Unicode-DFS-2016 AND Expat AND GPL-2+ AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND cmph AND AFL-2.0 AND Kuchling-PD AND Mingw-PD AND Plumb-PD | obligations |
| deb | libgjs0g:arm64 | 1.80.2-1build2 | Expat or LGPL-2.0+ AND CC0-1.0 AND Expat AND MPL-1.1 or GPL-2.0+ or LGPL-2.1+ AND MPL-2.0 AND BSD-3-clause AND LGPL-2.1+ and Expat AND LGPL-2.0+ AND LGPL-2.1+ | obligations |
| deb | libgl1:arm64 | 1.7.0-1build1 | MIT AND Apache-2.0 AND public-domain AND GPL-3+ AND BSD-1-clause AND GPL | review |
| deb | libgl1-mesa-dri:arm64 | 25.2.8-0ubuntu0.24.04.2 | MIT AND GPL-2 AND GPL-2 or MIT AND GPL-1+ AND BSD-3-google AND Khronos AND Apache-2.0 AND BSL AND MLAA AND SGI AND BSD-2-clause AND MIT OR Apache-2.0 AND (MIT OR Apache-2.0) AND Unicode-DFS-2016 AND Apache-2.0 OR MIT AND GPL AND Unicode-DFS-2016 | review |
| deb | libgl2ps1.4 | 1.4.2+dfsg1-2build1 | GPL-2+ or GL2PS-2+ | review |
| deb | libgles2:arm64 | 1.7.0-1build1 | MIT AND Apache-2.0 AND public-domain AND GPL-3+ AND BSD-1-clause AND GPL | review |
| deb | libglew2.2:arm64 | 2.2.0-4build1 | BSD-3-clause AND GPL-2+ AND Mesa AND Expat | review |
| deb | libglib-object-introspection-perl | 0.051-1build3 | LGPL-2.1+ | obligations |
| deb | libglib-perl:arm64 | 3:1.329.3-3build3 | LGPL-2.1+ | obligations |
| deb | libglib2.0-0:arm64 | 2.72.4-0ubuntu2.9 | UNKNOWN | unknown |
| deb | libglib2.0-0t64:arm64 | 2.80.0-6ubuntu3.8 | LGPL-2.1+ AND old-glib-tests AND AFL-2.0 or LGPL-2.1+ AND Janik-permissive AND LGPL-2+ AND FSFULLR AND Iconv-PD AND CC0-1.0 AND CC0-1.0 or Mingw-PD AND Janik-permissive and old-glib-tests AND Unicode-DFS-2016 AND Expat AND GPL-2+ AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND cmph AND AFL-2.0 AND Kuchling-PD AND Mingw-PD AND Plumb-PD | obligations |
| deb | libglib2.0-bin | 2.80.0-6ubuntu3.8 | LGPL-2.1+ AND old-glib-tests AND AFL-2.0 or LGPL-2.1+ AND Janik-permissive AND LGPL-2+ AND FSFULLR AND Iconv-PD AND CC0-1.0 AND CC0-1.0 or Mingw-PD AND Janik-permissive and old-glib-tests AND Unicode-DFS-2016 AND Expat AND GPL-2+ AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND cmph AND AFL-2.0 AND Kuchling-PD AND Mingw-PD AND Plumb-PD | obligations |
| deb | libglib2.0-data | 2.80.0-6ubuntu3.8 | LGPL-2.1+ AND old-glib-tests AND AFL-2.0 or LGPL-2.1+ AND Janik-permissive AND LGPL-2+ AND FSFULLR AND Iconv-PD AND CC0-1.0 AND CC0-1.0 or Mingw-PD AND Janik-permissive and old-glib-tests AND Unicode-DFS-2016 AND Expat AND GPL-2+ AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND cmph AND AFL-2.0 AND Kuchling-PD AND Mingw-PD AND Plumb-PD | obligations |
| deb | libglib2.0-dev:arm64 | 2.80.0-6ubuntu3.8 | LGPL-2.1+ AND old-glib-tests AND AFL-2.0 or LGPL-2.1+ AND Janik-permissive AND LGPL-2+ AND FSFULLR AND Iconv-PD AND CC0-1.0 AND CC0-1.0 or Mingw-PD AND Janik-permissive and old-glib-tests AND Unicode-DFS-2016 AND Expat AND GPL-2+ AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND cmph AND AFL-2.0 AND Kuchling-PD AND Mingw-PD AND Plumb-PD | obligations |
| deb | libglib2.0-dev-bin | 2.80.0-6ubuntu3.8 | LGPL-2.1+ AND old-glib-tests AND AFL-2.0 or LGPL-2.1+ AND Janik-permissive AND LGPL-2+ AND FSFULLR AND Iconv-PD AND CC0-1.0 AND CC0-1.0 or Mingw-PD AND Janik-permissive and old-glib-tests AND Unicode-DFS-2016 AND Expat AND GPL-2+ AND LGPL-3+ AND Apache-2.0 with LLVM exception AND LGPL-2.1+ and Kuchling-PD and Plumb-PD AND bzip2-1.0.6 AND CC-BY-SA-3.0 AND cmph AND AFL-2.0 AND Kuchling-PD AND Mingw-PD AND Plumb-PD | obligations |
| deb | libglibmm-2.4-1t64:arm64 | 2.66.7-1build1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libglibmm-2.68-1t64:arm64 | 2.78.1-2.2build2 | LGPL-2.1+ AND GPL-2+ AND LGPL-2+ AND GPL-3+ | obligations |
| deb | libglvnd0:arm64 | 1.7.0-1build1 | MIT AND Apache-2.0 AND public-domain AND GPL-3+ AND BSD-1-clause AND GPL | review |
| deb | libglx-mesa0:arm64 | 25.2.8-0ubuntu0.24.04.2 | MIT AND GPL-2 AND GPL-2 or MIT AND GPL-1+ AND BSD-3-google AND Khronos AND Apache-2.0 AND BSL AND MLAA AND SGI AND BSD-2-clause AND MIT OR Apache-2.0 AND (MIT OR Apache-2.0) AND Unicode-DFS-2016 AND Apache-2.0 OR MIT AND GPL AND Unicode-DFS-2016 | review |
| deb | libglx0:arm64 | 1.7.0-1build1 | MIT AND Apache-2.0 AND public-domain AND GPL-3+ AND BSD-1-clause AND GPL | review |
| deb | libgme0:arm64 | 0.6.3-7build1 | LGPL-2.1+ AND MIT | obligations |
| deb | libgmp10:arm64 | 2:6.3.0+dfsg-2ubuntu6.1 | GPL-2+ or LGPL-3+ AND GPL-3+ AND GPL-3+ with Bison exception AND GPL-2+ AND LGPL-3+ | obligations |
| deb | libgnome-autoar-0-0:arm64 | 0.4.4-2build4 | LGPL-2.1+ | obligations |
| deb | libgnome-bg-4-2t64:arm64 | 44.0-5build2 | LGPL-2+ AND LGPL-3+ AND GPL-2+ AND Expat | obligations |
| deb | libgnome-bluetooth-3.0-13:arm64 | 46.0-1ubuntu1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libgnome-desktop-3-20t64:arm64 | 44.0-5build2 | LGPL-2+ AND LGPL-3+ AND GPL-2+ AND Expat | obligations |
| deb | libgnome-desktop-4-2t64:arm64 | 44.0-5build2 | LGPL-2+ AND LGPL-3+ AND GPL-2+ AND Expat | obligations |
| deb | libgnomekbd-common | 3.28.1-1build3 | LGPL-2+ | obligations |
| deb | libgnomekbd8:arm64 | 3.28.1-1build3 | LGPL-2+ | obligations |
| deb | libgnutls30t64:arm64 | 3.8.3-1.1ubuntu3.6 | The main library is licensed under GNU Lesser AND * Redistribution and use in source and binary forms, with or without AND Public domain. AND CC0 license AND Expat AND Apache-2.0 AND LGPLv3+_or_GPLv2+ AND LGPLv2.1+ AND based on Russian standard GOST 28147-89 AND GPLv3+ AND BSD-3-Clause | obligations |
| deb | libgoa-1.0-0b:arm64 | 3.50.4-0ubuntu2 | LGPL-2.1+ | obligations |
| deb | libgoa-1.0-common | 3.50.4-0ubuntu2 | LGPL-2.1+ | obligations |
| deb | libgomp1:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libgpg-error0:arm64 | 1.47-3build2.1 | LGPL-2.1+ AND LGPL-2.1+ or BSD-3-clause AND g10-permissive AND GPL-3+ AND BSD-3-clause | obligations |
| deb | libgpgme11t64:arm64 | 1.18.0-4.1ubuntu4 | LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND GPL-3+ AND GPL-2+ AND LGPL-2+ AND LGPL-3+ | obligations |
| deb | libgphoto2-6t64:arm64 | 2.5.31-2.1ubuntu1 | LGPL-2+ AND GPL-2 AND LGPL-2.1+ AND IJG AND BSD-3-Clause AND LGPL-2+ or BSD-3-clause AND other-2 AND GPL-2+ AND GPL-3+ AND public-domain AND LGPL-3+ AND other-3 AND GPL-1 AND LGPL-1.1+ AND public-domain-1 AND MIT | obligations |
| deb | libgphoto2-dev:arm64 | 2.5.31-2.1ubuntu1 | LGPL-2+ AND GPL-2 AND LGPL-2.1+ AND IJG AND BSD-3-Clause AND LGPL-2+ or BSD-3-clause AND other-2 AND GPL-2+ AND GPL-3+ AND public-domain AND LGPL-3+ AND other-3 AND GPL-1 AND LGPL-1.1+ AND public-domain-1 AND MIT | obligations |
| deb | libgphoto2-l10n | 2.5.31-2.1ubuntu1 | LGPL-2+ AND GPL-2 AND LGPL-2.1+ AND IJG AND BSD-3-Clause AND LGPL-2+ or BSD-3-clause AND other-2 AND GPL-2+ AND GPL-3+ AND public-domain AND LGPL-3+ AND other-3 AND GPL-1 AND LGPL-1.1+ AND public-domain-1 AND MIT | obligations |
| deb | libgphoto2-port12t64:arm64 | 2.5.31-2.1ubuntu1 | LGPL-2+ AND GPL-2 AND LGPL-2.1+ AND IJG AND BSD-3-Clause AND LGPL-2+ or BSD-3-clause AND other-2 AND GPL-2+ AND GPL-3+ AND public-domain AND LGPL-3+ AND other-3 AND GPL-1 AND LGPL-1.1+ AND public-domain-1 AND MIT | obligations |
| deb | libgpm2:arm64 | 1.20.7-11 | GPL-2.0+ AND GPL-3.0+ | review |
| deb | libgprofng0:arm64 | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | libgraphene-1.0-0:arm64 | 1.10.8-3build2 | Expat | review |
| deb | libgraphite2-3:arm64 | 1.3.14-2ubuntu0.24.04.1 | LGPL-2.1+ or MPL-1.1 or GPL-2+ AND LGPL-2.1+ AND public-domain AND Artistic or GPL-1+ AND LGPL-2.1+ or GPL-2+ or MPL-1.1 AND custom-sil-open-font-license AND Artistic AND GPL-1+ AND GPL-2+ AND MPL-1.1 | obligations |
| deb | libgs-common | 10.02.1~dfsg1-0ubuntu7.8 | AGPL-3+ AND AGPL-3+ and FTL AND none AND BSD-3-Clause~Adobe AND LGPL-2.1 AND GPL-1+ AND AGPL-3+ with font exception AND GAP~configure AND GPL-2+ AND ZLIB AND BSD-3-Clause AND Expat~SunSoft with SunSoft exception AND Expat AND public-domain AND Apache-2.0 AND GPL-3+ with Autoconf exception AND ISC AND Expat~Ghostgum AND MIT-Open-Group AND NTP~Lucent AND NTP~WSU AND X11 AND GPL-3+ AND AGPL-3 AND Expat~SunSoft AND FTL | obligations |
| deb | libgs10:arm64 | 10.02.1~dfsg1-0ubuntu7.8 | AGPL-3+ AND AGPL-3+ and FTL AND none AND BSD-3-Clause~Adobe AND LGPL-2.1 AND GPL-1+ AND AGPL-3+ with font exception AND GAP~configure AND GPL-2+ AND ZLIB AND BSD-3-Clause AND Expat~SunSoft with SunSoft exception AND Expat AND public-domain AND Apache-2.0 AND GPL-3+ with Autoconf exception AND ISC AND Expat~Ghostgum AND MIT-Open-Group AND NTP~Lucent AND NTP~WSU AND X11 AND GPL-3+ AND AGPL-3 AND Expat~SunSoft AND FTL | obligations |
| deb | libgs10-common | 10.02.1~dfsg1-0ubuntu7.8 | AGPL-3+ AND AGPL-3+ and FTL AND none AND BSD-3-Clause~Adobe AND LGPL-2.1 AND GPL-1+ AND AGPL-3+ with font exception AND GAP~configure AND GPL-2+ AND ZLIB AND BSD-3-Clause AND Expat~SunSoft with SunSoft exception AND Expat AND public-domain AND Apache-2.0 AND GPL-3+ with Autoconf exception AND ISC AND Expat~Ghostgum AND MIT-Open-Group AND NTP~Lucent AND NTP~WSU AND X11 AND GPL-3+ AND AGPL-3 AND Expat~SunSoft AND FTL | obligations |
| deb | libgsettings-qt1:arm64 | 0.2-5build3 | LGPL-3 | obligations |
| deb | libgsm1:arm64 | 1.0.22-1build1 | TU-Berlin-2.0 | review |
| deb | libgspell-1-2:arm64 | 1.12.2-1build4 | LGPL-2.1+ AND CC0-1.0 | obligations |
| deb | libgspell-1-common | 1.12.2-1build4 | LGPL-2.1+ AND CC0-1.0 | obligations |
| deb | libgssapi-krb5-2:arm64 | 1.20.1-6ubuntu2.6 | Copyright 2006 g10 Code GmbH AND Copyright 2004-2008 Apple Inc. All Rights Reserved. AND Copyright (c) 2011, PADL Software Pty Ltd. All rights reserved. | review |
| deb | libgstreamer-gl1.0-0:arm64 | 1.24.2-1ubuntu0.4 | LGPL-2+ AND BSD (2 clause) AND MIT/X11 (BSD like) LGPL-2+ AND BSD (3 clause) AND GPL-2+ | obligations |
| deb | libgstreamer-plugins-base1.0-0:arm64 | 1.24.2-1ubuntu0.4 | LGPL-2+ AND BSD (2 clause) AND MIT/X11 (BSD like) LGPL-2+ AND BSD (3 clause) AND GPL-2+ | obligations |
| deb | libgstreamer-plugins-good1.0-0:arm64 | 1.24.2-1ubuntu1.4 | LGPL-2+ AND LGPL-2.1+ AND MIT/X11 (BSD like) LGPL-2+ AND GPL-2+ AND LGPL AND LGPL-2 AND BSD (3 clause) AND BSD | obligations |
| deb | libgstreamer1.0-0:arm64 | 1.24.2-1ubuntu0.1 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ AND GPL-3+ | obligations |
| deb | libgtk-3-0:arm64 | 3.24.33-1ubuntu2.2 | UNKNOWN | unknown |
| deb | libgtk-3-0t64:arm64 | 3.24.41-4ubuntu1.3 | LGPL-2+ and LGPL-2.1+ and Expat AND GPL-3+ AND LGPL-2+ AND CC-BY-SA-4.0 AND unencumbered AND other AND SWL AND LGPL-2+ or SWL AND X11R5-permissive AND Expat AND Apache-2.0 AND LGPL-2+ and ZPL-2.1 AND check-gdk-cairo-permissive AND LGPL-2.1+ AND ZPL-2.1 | obligations |
| deb | libgtk-3-bin | 3.24.41-4ubuntu1.3 | LGPL-2+ and LGPL-2.1+ and Expat AND GPL-3+ AND LGPL-2+ AND CC-BY-SA-4.0 AND unencumbered AND other AND SWL AND LGPL-2+ or SWL AND X11R5-permissive AND Expat AND Apache-2.0 AND LGPL-2+ and ZPL-2.1 AND check-gdk-cairo-permissive AND LGPL-2.1+ AND ZPL-2.1 | obligations |
| deb | libgtk-3-common | 3.24.41-4ubuntu1.3 | LGPL-2+ and LGPL-2.1+ and Expat AND GPL-3+ AND LGPL-2+ AND CC-BY-SA-4.0 AND unencumbered AND other AND SWL AND LGPL-2+ or SWL AND X11R5-permissive AND Expat AND Apache-2.0 AND LGPL-2+ and ZPL-2.1 AND check-gdk-cairo-permissive AND LGPL-2.1+ AND ZPL-2.1 | obligations |
| deb | libgtk-4-1:arm64 | 4.14.5+ds-0ubuntu0.10 | LGPL-2.1+ AND LGPL-2+ and LGPL-2.1+ and sun-permissive and lcs-telegraphics-permissive and X11R5-permissive and Expat and BSD-3-clause-Google and Apache-2.0 and CC0-1.0 and ZPL-2.1 AND Unicode-DFS-2016 AND GPL-3+ AND Apache-2.0 with LLVM exception AND Expat or unlicense AND CC0-1.0 AND Apache-2.0 AND BSD-3-clause-Google AND Expat AND LGPL-2+ AND lcs-telegraphics-permissive AND sun-permissive AND unlicense AND X11R5-permissive AND ZPL-2.1 | obligations |
| deb | libgtk-4-bin | 4.14.5+ds-0ubuntu0.10 | LGPL-2.1+ AND LGPL-2+ and LGPL-2.1+ and sun-permissive and lcs-telegraphics-permissive and X11R5-permissive and Expat and BSD-3-clause-Google and Apache-2.0 and CC0-1.0 and ZPL-2.1 AND Unicode-DFS-2016 AND GPL-3+ AND Apache-2.0 with LLVM exception AND Expat or unlicense AND CC0-1.0 AND Apache-2.0 AND BSD-3-clause-Google AND Expat AND LGPL-2+ AND lcs-telegraphics-permissive AND sun-permissive AND unlicense AND X11R5-permissive AND ZPL-2.1 | obligations |
| deb | libgtk-4-common | 4.14.5+ds-0ubuntu0.10 | LGPL-2.1+ AND LGPL-2+ and LGPL-2.1+ and sun-permissive and lcs-telegraphics-permissive and X11R5-permissive and Expat and BSD-3-clause-Google and Apache-2.0 and CC0-1.0 and ZPL-2.1 AND Unicode-DFS-2016 AND GPL-3+ AND Apache-2.0 with LLVM exception AND Expat or unlicense AND CC0-1.0 AND Apache-2.0 AND BSD-3-clause-Google AND Expat AND LGPL-2+ AND lcs-telegraphics-permissive AND sun-permissive AND unlicense AND X11R5-permissive AND ZPL-2.1 | obligations |
| deb | libgtk-4-media-gstreamer | 4.14.5+ds-0ubuntu0.10 | LGPL-2.1+ AND LGPL-2+ and LGPL-2.1+ and sun-permissive and lcs-telegraphics-permissive and X11R5-permissive and Expat and BSD-3-clause-Google and Apache-2.0 and CC0-1.0 and ZPL-2.1 AND Unicode-DFS-2016 AND GPL-3+ AND Apache-2.0 with LLVM exception AND Expat or unlicense AND CC0-1.0 AND Apache-2.0 AND BSD-3-clause-Google AND Expat AND LGPL-2+ AND lcs-telegraphics-permissive AND sun-permissive AND unlicense AND X11R5-permissive AND ZPL-2.1 | obligations |
| deb | libgtk2.0-0:arm64 | 2.24.33-2ubuntu2.1 | UNKNOWN | unknown |
| deb | libgtk2.0-0t64:arm64 | 2.24.33-4ubuntu1.1 | tests/testnouiprint.c AND other | review |
| deb | libgtk2.0-bin | 2.24.33-4ubuntu1.1 | tests/testnouiprint.c AND other | review |
| deb | libgtk2.0-common | 2.24.33-4ubuntu1.1 | tests/testnouiprint.c AND other | review |
| deb | libgtk3-perl | 0.038-3 | LGPL-2.1+ | obligations |
| deb | libgtkmm-2.4-1t64:arm64 | 1:2.24.5-5.2build2 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libgtkmm-3.0-1t64:arm64 | 3.24.9-1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libgtkmm-4.0-0:arm64 | 4.10.0-4build3 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libgtksourceview-4-0:arm64 | 4.8.4-5build4 | This library is free software; you can redistribute it and/or | review |
| deb | libgtksourceview-4-common | 4.8.4-5build4 | This library is free software; you can redistribute it and/or | review |
| deb | libgtop-2.0-11:arm64 | 2.41.3-1ubuntu0.24.04.1 | This package is free software; you can redistribute it and/or modify | review |
| deb | libgtop2-common | 2.41.3-1ubuntu0.24.04.1 | This package is free software; you can redistribute it and/or modify | review |
| deb | libgudev-1.0-0:arm64 | 1:238-5ubuntu1 | LGPL-2+ | obligations |
| deb | libgusb2:arm64 | 0.4.8-1build2 | LGPL-2.1+ AND CC0-1.0 AND GPL-2.0+ | obligations |
| deb | libgweather-4-0t64:arm64 | 4.4.2-1build1 | GPL-2+ AND LGPL-2.1+ AND LGPL-2+ | obligations |
| deb | libgweather-4-common | 4.4.2-1build1 | GPL-2+ AND LGPL-2.1+ AND LGPL-2+ | obligations |
| deb | libgxps2t64:arm64 | 0.3.2-4build3 | LGPL-2.1+ | obligations |
| deb | libhandy-1-0:arm64 | 1.8.3-1build2 | LGPL-2.1+ | obligations |
| deb | libharfbuzz-gobject0:arm64 | 8.3.0-2build2 | MIT AND Unicode AND ISC AND Apache-2.0 AND OFL-1.1 AND Monotype AND CC0-1.0 AND GPL-3+ AND GPL-2+ with Font exception AND UFL-1.0 AND FSFULLR AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND LGPL-2.1+ AND GPL-2+ with LibTool exception AND Expat AND FSFUL | obligations |
| deb | libharfbuzz-icu0:arm64 | 8.3.0-2build2 | MIT AND Unicode AND ISC AND Apache-2.0 AND OFL-1.1 AND Monotype AND CC0-1.0 AND GPL-3+ AND GPL-2+ with Font exception AND UFL-1.0 AND FSFULLR AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND LGPL-2.1+ AND GPL-2+ with LibTool exception AND Expat AND FSFUL | obligations |
| deb | libharfbuzz0b:arm64 | 8.3.0-2build2 | MIT AND Unicode AND ISC AND Apache-2.0 AND OFL-1.1 AND Monotype AND CC0-1.0 AND GPL-3+ AND GPL-2+ with Font exception AND UFL-1.0 AND FSFULLR AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND LGPL-2.1+ AND GPL-2+ with LibTool exception AND Expat AND FSFUL | obligations |
| deb | libhavege2:arm64 | 1.9.14-1ubuntu2 | GPL-3+ AND public-domain AND permissive-mconf AND permissive-nist | review |
| deb | libhdf4-0-alt:arm64 | 4.2.16-4build1 | HDF4 AND Apache-2.0 AND BSD-3-Clause AND NetCDF AND NetCDF and HDF4 AND GPL-3+ with Bison exception AND HPND-sl-gl-sgi AND GPL-2+ | review |
| deb | libhdf5-103-1t64:arm64 | 1.10.10+repack-3.1ubuntu4 | BSD-3-clause AND GPL-2+ | review |
| deb | libhdf5-hl-100t64:arm64 | 1.10.10+repack-3.1ubuntu4 | BSD-3-clause AND GPL-2+ | review |
| deb | libheif-plugin-aomdec:arm64 | 1.17.6-1ubuntu4.3 | LGPL-3+ AND GPL-3+ AND MIT AND BSD-4-clause AND BSD-3-clause AND BOOST-1.0 | obligations |
| deb | libheif-plugin-aomenc:arm64 | 1.17.6-1ubuntu4.3 | LGPL-3+ AND GPL-3+ AND MIT AND BSD-4-clause AND BSD-3-clause AND BOOST-1.0 | obligations |
| deb | libheif-plugin-libde265:arm64 | 1.17.6-1ubuntu4.3 | LGPL-3+ AND GPL-3+ AND MIT AND BSD-4-clause AND BSD-3-clause AND BOOST-1.0 | obligations |
| deb | libheif1:arm64 | 1.17.6-1ubuntu4.3 | LGPL-3+ AND GPL-3+ AND MIT AND BSD-4-clause AND BSD-3-clause AND BOOST-1.0 | obligations |
| deb | libhogweed6t64:arm64 | 3.9.1-2.2build1.1 | LGPL-3+ or GPL-2+ AND LGPL-2+ AND Expat AND GPL-2+ AND GPL-3+ with Autoconf exception AND public-domain AND GPL-2 AND GAP AND LGPL-3+ | obligations |
| deb | libhpmud0:arm64 | 3.23.12+dfsg0-0ubuntu5 | GPL-2+ AND BSD-2-clause AND BSD-3-clause AND Expat AND FSFUL AND public-domain AND GPL-2 | review |
| deb | libhtml-form-perl | 6.11-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhtml-format-perl | 2.16-2 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhtml-parser-perl:arm64 | 3.81-1build3 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhtml-tagset-perl | 3.20-6 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhtml-tree-perl | 5.07-3 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhttp-cookies-perl | 6.11-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhttp-daemon-perl | 6.16-1ubuntu0.24.04.1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhttp-date-perl | 6.06-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhttp-message-perl | 6.45-1ubuntu1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhttp-negotiate-perl | 6.01-2 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libhunspell-1.7-0:arm64 | 1.7.2+really1.7.2-10build3 | MPL 1.1/GPL 2.0/LGPL 2.1 | obligations |
| deb | libhwasan0:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libhwloc-plugins:arm64 | 2.10.0-1build1 | Redistribution and use in source and binary forms, with or without | review |
| deb | libhwloc15:arm64 | 2.10.0-1build1 | Redistribution and use in source and binary forms, with or without | review |
| deb | libhyphen0:arm64 | 2.8.8-7build3 | GPL-2+ or LGPL-2.1+ or MPL-1.1+ AND GPL-2+ AND LGPL-2.1+ AND MPL-1.1+ | obligations |
| deb | libi2c0:arm64 | 4.3-4build2 | UNKNOWN | unknown |
| deb | libibus-1.0-5:arm64 | 1.5.29-2 | LGPL-2.1+ AND permissive-makefile-in AND ISC-Sun AND permissive-autoconf-m4 AND GPL-2.0+ with autoconf exception AND ISC-Intel AND ISC-Fujitsu AND MIT and ISC-NCR AND MIT AND ISC-NCR AND LGPL-2.0+ AND permissive-fsf-grant AND permissive AND permissive-fsf-grant-attribution AND permissive-author-grant-attribution AND GPL-3.0+ with autoconf exception | obligations |
| deb | libibverbs1:arm64 | 50.0-2ubuntu0.2 | BSD-MIT or GPL-2 AND GPL-2+ AND BSD-2-clause AND CC0 AND MIT AND BSD-MIT AND GPL-2 or BSD-2-clause AND GPL-2 AND GPL-2 or BSD-3-clause AND BSD-2-clause or GPL-2 AND BSD-3-clause or GPL-2 AND CPL-1.0 or BSD-2-clause or GPL-2 AND BSD-3-clause AND CPL-1.0 | review |
| deb | libical3t64:arm64 | 3.0.17-1.1build3 | LGPL-2.1 or MPL-2.0 AND BSD-3-Clause AND GPL-1+ or Artistic-1 AND LGPL-2.1 AND MPL-2.0 AND BSD-3-clause | obligations |
| deb | libice6:arm64 | 2:1.0.10-1build3 | UNKNOWN | unknown |
| deb | libicu74:arm64 | 74.2-1ubuntu3.1 | MIT AND GPL-3 | review |
| deb | libidn12:arm64 | 1.42-1build1 | GPL-3+ AND GFDL-NIV-1.3+ AND LGPL-3+ or GPL-2+ AND LGPL-2.1+ AND GAP AND LGPL-3+ AND GPL-2+ | obligations |
| deb | libidn2-0:arm64 | 2.3.7-2build1.1 | GPL-3+ AND LGPL-3+ or GPL-2+ AND Unicode AND GPL-2+ AND LGPL-3+ | obligations |
| deb | libiec61883-0:arm64 | 1.2.0-6build1 | This library is free software; you can redistribute it and/or | review |
| deb | libieee1284-3t64:arm64 | 0.2.11-14.1build1 | UNKNOWN | unknown |
| deb | libijs-0.35:arm64 | 0.35-15.1build1 | Expat AND GPL-2+ with Autoconf exception AND GAP~configure AND GAP AND Expat~X with X exception AND GAP~Makefile.in AND GPL-2+ AND Expat~X | review |
| deb | libimage-exiftool-perl | 12.76+dfsg-1 | Artistic or GPL-1+ AND GPL-1+ AND Artistic | review |
| deb | libimagequant0:arm64 | 2.18.0-1build1 | GPL-3.0+ AND MIT AND CC0 | review |
| deb | libimath-3-1-29t64:arm64 | 3.1.9-3.1ubuntu2 | imath | review |
| deb | libimath-dev:arm64 | 3.1.9-3.1ubuntu2 | imath | review |
| deb | libimobiledevice6:arm64 | 1.3.0-8.1build3 | LGPL-2.1+ AND GPL-3+ | obligations |
| deb | libindicator3-7 | 16.10.0+18.04.20180321.1-0ubuntu8 | GPL-3 | review |
| deb | libinput-bin | 1.25.0-1ubuntu3.4 | Expat AND GPL-2 | review |
| deb | libinput10:arm64 | 1.25.0-1ubuntu3.4 | Expat AND GPL-2 | review |
| deb | libio-html-perl | 1.004-3 | Artistic or GPL-1+ AND GPL-3+ AND Artistic AND GPL-1+ | review |
| deb | libio-socket-ssl-perl | 2.085-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libip4tc2:arm64 | 1.8.10-3ubuntu2 | GPL-2 AND Artistic AND GPL-2+ AND custom | review |
| deb | libip6tc2:arm64 | 1.8.10-3ubuntu2 | GPL-2 AND Artistic AND GPL-2+ AND custom | review |
| deb | libiperf0:arm64 | 3.16-1build2 | BSD-3-clause-iperf AND BSD-2-clause AND MIT/X11 AND BSD-3-clause-iperf+MIT/X11+BSD-3-clause AND BSD-3-clause AND NCSA AND FSF-permissive1 AND FSF-permissive2 AND GPL-2+ AND permissive AND MIT AND public-domain-1 AND GPL-3+ AND public-domain-2 AND GPL-2 | review |
| deb | libitm1:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libiw30t64:arm64 | 30~pre9-16.1ubuntu2 | UNKNOWN | unknown |
| deb | libixml11t64:arm64 | 1:1.14.18-1.1ubuntu2 | BSD-3-clause-Intel AND GPL-3 AND Academia-Sinicai-XML-Now AND public-domain AND GPL-2+ with Autoconf exception AND GPL-3+ with Autoconf exception AND GPL-2+ AND MIT-like AND ISC | review |
| deb | libjack-jackd2-0:arm64 | 1.9.21~dfsg-3ubuntu3 | LGPL-2.1+ AND GPL-2+ AND GPL-2~either AND GPL-3+ AND GPL-2 AND LGPL-2+ AND GPL-2~or AND Expat AND BSD-3-clause AND public-domain~Kroon AND BSD-2-clause | obligations |
| deb | libjansson4:arm64 | 2.14-2build2 | Expat | review |
| deb | libjavascriptcoregtk-4.1-0:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | libjavascriptcoregtk-6.0-1:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | libjbig-dev:arm64 | 2.1-6.1ubuntu2 | GPL-2+ | review |
| deb | libjbig0:arm64 | 2.1-6.1ubuntu2 | GPL-2+ | review |
| deb | libjbig2dec0:arm64 | 0.20-1build3 | AGPL-3+ AND LGPL-2.1+ AND BSD-2-clause AND public-domain AND pubic-domain AND GPL-3+ | obligations |
| deb | libjcat1:arm64 | 0.2.3-1~ubuntu0.24.04.1 | LGPL-2.1+ | obligations |
| deb | libjpeg-dev:arm64 | 8c-2ubuntu11 | LGPL-2.1 | obligations |
| deb | libjpeg8:arm64 | 8c-2ubuntu11 | LGPL-2.1 | obligations |
| deb | libjpeg8-dev:arm64 | 8c-2ubuntu11 | LGPL-2.1 | obligations |
| deb | libjq1:arm64 | 1.7.1-3ubuntu0.24.04.2 | MIT AND CC-BY-3.0 AND Expat AND GPL-2.0+ | review |
| deb | libjs-jquery | 3.6.1+dfsg+~3.5.14-1 | Expat | review |
| deb | libjs-jquery-ui | 1.13.2+dfsg-1 | Expat AND CC0 AND CC-BY-SA-3.0 AND GPL-2 or Expat AND GPL-2 | review |
| deb | libjs-mathjax | 2.7.9+dfsg-1 | Apache-2.0 AND OFL-1.1 AND GFL AND GPL-2+ or Apache-2.0 AND GPL-2+ | review |
| deb | libjs-underscore | 1.13.4~dfsg+~1.11.4-3 | Expat AND BSD-3-clause AND GPL-3+ | review |
| deb | libjson-c5:arm64 | 0.17-1build1 | Expat | review |
| deb | libjson-glib-1.0-0:arm64 | 1.8.0-2build2 | LGPL-2.1+ | obligations |
| deb | libjson-glib-1.0-common | 1.8.0-2build2 | LGPL-2.1+ | obligations |
| deb | libjsoncpp25:arm64 | 1.9.5-6build1 | Expat_or_PublicDomain_or_DualExpatPD AND GPL-3+ | review |
| deb | libk5crypto3:arm64 | 1.20.1-6ubuntu2.6 | Copyright 2006 g10 Code GmbH AND Copyright 2004-2008 Apple Inc. All Rights Reserved. AND Copyright (c) 2011, PADL Software Pty Ltd. All rights reserved. | review |
| deb | libkate1:arm64 | 0.4.1-11build2 | BSD-3-Clause AND GPL-2+ | review |
| deb | libkeybinder-3.0-0:arm64 | 0.3.2-1.1build2 | GPL-2+ AND public-domain AND MIT | review |
| deb | libkeyutils1:arm64 | 1.6.3-3build1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libklibc:arm64 | 2.0.13-4ubuntu0.2 | BSD/GPL AND Note: The advertising clause in the license appearing on BSD Unix | review |
| deb | libkmlbase1t64:arm64 | 1.3.0-12build1 | BSD-3-Clause AND zlib AND GPL-3+ | review |
| deb | libkmldom1t64:arm64 | 1.3.0-12build1 | BSD-3-Clause AND zlib AND GPL-3+ | review |
| deb | libkmlengine1t64:arm64 | 1.3.0-12build1 | BSD-3-Clause AND zlib AND GPL-3+ | review |
| deb | libkmod2:arm64 | 31+20240202-2ubuntu7.2 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libkpathsea6:arm64 | 2023.20230311.66589-9build3 | TeX-Live AND GPL-2+ AND MIT AND LPPL | review |
| deb | libkrb5-3:arm64 | 1.20.1-6ubuntu2.6 | Copyright 2006 g10 Code GmbH AND Copyright 2004-2008 Apple Inc. All Rights Reserved. AND Copyright (c) 2011, PADL Software Pty Ltd. All rights reserved. | review |
| deb | libkrb5support0:arm64 | 1.20.1-6ubuntu2.6 | Copyright 2006 g10 Code GmbH AND Copyright 2004-2008 Apple Inc. All Rights Reserved. AND Copyright (c) 2011, PADL Software Pty Ltd. All rights reserved. | review |
| deb | libksba8:arm64 | 1.6.6-1build1 | FSFUL AND LGPL-2.1-or-later | obligations |
| deb | liblcms2-2:arm64 | 2.14-2ubuntu0.1 | MIT AND GPL-3 AND IJG AND GPL-2+ | review |
| deb | libldap-common | 2.6.10+dfsg-0ubuntu0.24.04.1 | OpenLDAP-2.8 AND FSF-unlimited and GPL-2+ with Autoconf exception AND GPL-3+ with Autoconf exception AND FSF-unlimited AND GPL-2+ with Libtool exception and GPL-3+ with Libtool exception and GPL-3+ AND GPL-2+ with Autoconf exception AND GPL-2+ AND OpenLDAP-2.8 and UMich and F5 AND OpenLDAP-2.8 and UMich AND OpenLDAP-2.8 and JCG and UMich AND OpenLDAP-2.8 and FSF-unlimited and GPL-2+ with Libtool exception AND FSF-unlimited and GPL-2+ with Libtool exception AND FSF-unlimited and OpenLDAP-2.8 AND MIT-XC AND NeoSoft-permissive AND BSD-3-clause AND OpenLDAP-2.8 and BSD-3-clause AND OpenLDAP-2.8 and Beerware AND public-domain AND OpenLDAP-2.8 and BSD-4-clause-California AND OpenLDAP-2.8 and BSD-3-clause-variant AND OpenLDAP-2.8 and Expat-ISC AND OpenLDAP-2.8 and Expat-UNM AND OpenLDAP-2.8 and Expat AND BSD-3-clause-California AND F5 AND GPL-2+ with Libtool exception AND GPL-3+ AND GPL-3+ with Libtool exception AND JCG AND UMich AND Beerware AND BSD-3-clause-variant AND Expat-ISC AND Expat-UNM AND Expat AND BSD-4-clause-California | review |
| deb | libldap2:arm64 | 2.6.10+dfsg-0ubuntu0.24.04.1 | OpenLDAP-2.8 AND FSF-unlimited and GPL-2+ with Autoconf exception AND GPL-3+ with Autoconf exception AND FSF-unlimited AND GPL-2+ with Libtool exception and GPL-3+ with Libtool exception and GPL-3+ AND GPL-2+ with Autoconf exception AND GPL-2+ AND OpenLDAP-2.8 and UMich and F5 AND OpenLDAP-2.8 and UMich AND OpenLDAP-2.8 and JCG and UMich AND OpenLDAP-2.8 and FSF-unlimited and GPL-2+ with Libtool exception AND FSF-unlimited and GPL-2+ with Libtool exception AND FSF-unlimited and OpenLDAP-2.8 AND MIT-XC AND NeoSoft-permissive AND BSD-3-clause AND OpenLDAP-2.8 and BSD-3-clause AND OpenLDAP-2.8 and Beerware AND public-domain AND OpenLDAP-2.8 and BSD-4-clause-California AND OpenLDAP-2.8 and BSD-3-clause-variant AND OpenLDAP-2.8 and Expat-ISC AND OpenLDAP-2.8 and Expat-UNM AND OpenLDAP-2.8 and Expat AND BSD-3-clause-California AND F5 AND GPL-2+ with Libtool exception AND GPL-3+ AND GPL-3+ with Libtool exception AND JCG AND UMich AND Beerware AND BSD-3-clause-variant AND Expat-ISC AND Expat-UNM AND Expat AND BSD-4-clause-California | review |
| deb | libldb2:arm64 | 2:2.8.0+samba4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | liblept5:arm64 | 1.82.0-3build4 | /*====================================================================* | review |
| deb | liblightdm-gobject-1-0:arm64 | 1.30.0-0ubuntu14 | GPL-3+ AND LGPL-3+ AND GPL-2+ | obligations |
| deb | liblirc-client0t64:arm64 | 0.10.2-0.8build1 | GPL-2.0+ AND MIT | review |
| deb | liblirc0t64:arm64 | 0.10.2-0.8build1 | GPL-2.0+ AND MIT | review |
| deb | liblmdb0:arm64 | 0.9.31-1build1 | OpenLDAP-2.8 | review |
| deb | liblocale-gettext-perl | 1.07-6ubuntu5 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | liblouis-data | 3.29.0-1build1 | This package is free software; you can redistribute it and/or AND This package is free software; you can redistribute it and/or modify AND This program is free software: you can redistribute it and/or modify it | review |
| deb | liblouis20:arm64 | 3.29.0-1build1 | This package is free software; you can redistribute it and/or AND This package is free software; you can redistribute it and/or modify AND This program is free software: you can redistribute it and/or modify it | review |
| deb | liblsan0:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libltdl7:arm64 | 2.4.7-7build1 | GPL-2+ AND GFDL-NIV-1.3+ | review |
| deb | liblua5.2-0:arm64 | 5.2.4-3build2 | Expat | review |
| deb | liblwp-mediatypes-perl | 6.04-2 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | liblwp-protocol-https-perl | 6.13-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | liblz4-1:arm64 | 1.9.4-1build1.1 | BSD-2-clause AND GPL-2+ AND GPL-2+ or BSD-2-clause | review |
| deb | liblzma-dev:arm64 | 5.6.1+really5.4.5-1ubuntu0.3 | Different licenses apply to different files in this package. Here AND PD AND probably-PD AND GPL-2+ AND LGPL-2.1+ AND permissive-fsf AND Autoconf AND permissive-nowarranty AND GPL-2 AND none AND config-h AND noderivs AND PD-debian | obligations |
| deb | liblzma5:arm64 | 5.6.1+really5.4.5-1ubuntu0.3 | Different licenses apply to different files in this package. Here AND PD AND probably-PD AND GPL-2+ AND LGPL-2.1+ AND permissive-fsf AND Autoconf AND permissive-nowarranty AND GPL-2 AND none AND config-h AND noderivs AND PD-debian | obligations |
| deb | liblzo2-2:arm64 | 2.10-2build4 | GPL-2+ | review |
| deb | libmad0:arm64 | 0.15.1b-10.2ubuntu1 | UNKNOWN | unknown |
| deb | libmagic1:arm64 | 1:5.41-3ubuntu0.1 | UNKNOWN | unknown |
| deb | libmailtools-perl | 2.21-2 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libmalcontent-0-0:arm64 | 0.11.1-1ubuntu1.3 | LGPL-2.1+ AND GPL-2.0+ | obligations |
| deb | libmanette-0.2-0:arm64 | 0.2.7-1build2 | LGPL-2.1+ | obligations |
| deb | libmatroska7:arm64 | 1.7.1-1build1 | LGPL-2.1 AND QPL or GPL-2 AND GPL-2+ | obligations |
| deb | libmaxminddb0:arm64 | 1.9.1-1build1 | Apache-2.0 AND CC-BY-SA-3.0 AND GPL-2+ AND BSD-2-clause and BSD-3-clause and BSD-4-clause | review |
| deb | libmbedcrypto7t64:arm64 | 2.28.8-1 | Apache-2.0 or GPL-2+ AND Apache-2.0 AND GPL-2+ | review |
| deb | libmbim-glib4:arm64 | 1.31.2-0ubuntu3.1 | GPL-2+ AND LGPL-2+ AND GFDL-NIV-1.3+ | obligations |
| deb | libmbim-proxy | 1.31.2-0ubuntu3.1 | GPL-2+ AND LGPL-2+ AND GFDL-NIV-1.3+ | obligations |
| deb | libmbim-utils | 1.31.2-0ubuntu3.1 | GPL-2+ AND LGPL-2+ AND GFDL-NIV-1.3+ | obligations |
| deb | libmm-glib0:arm64 | 1.23.4-0ubuntu2 | GPL-2.0+ AND GPL-3.0+ AND GPL-2.0 AND LGPL-2.0+ | obligations |
| deb | libmnl0:arm64 | 1.0.5-2build1 | LGPL-2.1 AND GPL-2+ | obligations |
| deb | libmount-dev:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | libmount1:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | libmousepad0:arm64 | 0.6.1-1build2 | UNKNOWN | unknown |
| deb | libmozjs-115-0t64:arm64 | 115.10.0-1 | MPL-2.0 and Apache-2.0 and BSD-2-clause and BSD-3-clause and BSD-3-clause-ARM and BSD-3-clause-ECMA and BSD-3-clause-Google and BSD-3-clause-Intel and BSD-3-clause-SwapOff and BSD-3-clause-Voidspace and BSD-3-clause-psutil and BSL-1.0 and Beerware and CC0-1.0 and Expat and ISC and LGPL-2.1 and MIT-Lucent and NTP and Python and Unlicense and Zlib AND MPL-2.0 AND Apache-2.0 AND BSD-2-clause AND BSD-3-clause AND BSD-3-clause-ARM AND BSD-3-clause-ECMA AND BSD-3-clause-Google AND BSD-3-clause-Intel AND BSD-3-clause-psutil AND BSD-3-clause-SwapOff AND BSD-3-clause-UC AND BSD-3-clause-Voidspace AND BSL-1.0 AND Beerware AND CC0-1.0 AND Expat AND GPL-2 AND GPL-2+ AND GPL-3 AND GPL-3+ AND GPL-3+ with Bison exception AND ICU-IBM AND ICU-Unicode AND ISC AND LGPL-2.1 AND MIT-Lucent AND NTP AND Python AND SunPro AND Unlicense AND Zlib AND GPL-2 or GPL-3 AND aclocal-public-domain AND nspr-public-domain AND SunPro and BSD-2-clause and MPL-2.0 AND ICU-IBM and ICU-Unicode and BSD-3-clause-Google AND Expat and GPL-3+ and GPL-2+ AND BSD-3-clause-UC or ISC AND GPL-some-version AND BSD-3-clause or GPL-2 | obligations |
| deb | libmp3lame0:arm64 | 3.100-6build1 | LGPL-2+ AND LGPL-2.1+ AND zlib/libpng AND BSD-3-clause AND GPL-1+ | obligations |
| deb | libmpc3:arm64 | 1.3.1-1build1.1 | This library is distributed under the terms of the GNU Lesser General | review |
| deb | libmpcdec6:arm64 | 2:0.1~r495-2build1 | For common/fastmath.c, | review |
| deb | libmpeg2-4:arm64 | 0.5.1-9build1 | UNKNOWN | unknown |
| deb | libmpfr6:arm64 | 4.2.1-1build1.1 | UNKNOWN | unknown |
| deb | libmpg123-0t64:arm64 | 1.32.5-1ubuntu1.1 | LGPL-2.1 | obligations |
| deb | libmsgraph-0-1:arm64 | 0.2.1-0ubuntu3 | LGPL-3+ AND GPL-3+ | obligations |
| deb | libmtdev1t64:arm64 | 1.1.6-1.1build1 | Expat | review |
| deb | libmtp-common | 1.1.21-3.1ubuntu1 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libmtp-runtime | 1.1.21-3.1ubuntu1 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libmtp9t64:arm64 | 1.1.21-3.1ubuntu1 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libmunge2:arm64 | 0.5.15-4ubuntu0.1 | GPL-3+-and-LGPL-3+ AND GPL-2+ AND ISC AND LGPL-2.1+ | obligations |
| deb | libmutter-14-0:arm64 | 46.2-1ubuntu0.24.04.15 | GPL-2+ and GPL-3+ and LGPL-2+ and LGPL-2.1+ and Expat and NTP-BSD-variant and SGI-B-2.0 AND WRF-BSD-variant AND free-of-known-restrictions AND DEC-BSD-variant and OpenGroup-BSD-variant AND DEC-BSD-variant and OpenGroup-BSD-variant and GPL-2+ AND GPL-2+ AND GPL-3+ AND LGPL-2+ AND LGPL-2.1+ AND Expat AND NTP-BSD-variant AND OpenGroup-BSD-variant AND DEC-BSD-variant AND SGI-B-2.0 | obligations |
| deb | libmysqlclient21:arm64 | 8.0.46-0ubuntu0.24.04.3 | GPL-2+ AND Artistic or GPL-2 AND GPL-2 AND BSD-3-clause AND BSD-2-clause AND LGPL AND zlib/libpng AND public-domain AND ISC AND BSD-3-clause and GPL-2 AND BSD-like AND Boost-1.0 AND Artistic | obligations |
| deb | libndp0:arm64 | 1.8-1fakesync1ubuntu0.24.04.1 | LGPL-2.1+ | obligations |
| deb | libnet-http-perl | 6.23-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libnet-smtp-ssl-perl | 1.04-2 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libnet-ssleay-perl:arm64 | 1.94-1build4 | Artistic-2.0 AND Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libnetcdf19t64:arm64 | 1:4.9.2-5ubuntu4 | BSD-3-Clause AND CC-BY-4.0 AND NetCDF AND public-domain AND GPL-3+ with Bison exception AND Zlib AND Expat AND Unicode-data AND HDF5 AND NetCDF and BSL-1.0 AND ncxml AND BSL-1.0 | review |
| deb | libnetfilter-conntrack3:arm64 | 1.0.9-6build1 | GPL-2+ | review |
| deb | libnetplan1:arm64 | 1.1.2-8ubuntu1~24.04.2 | GPL-3 | review |
| deb | libnettle8t64:arm64 | 3.9.1-2.2build1.1 | LGPL-3+ or GPL-2+ AND LGPL-2+ AND Expat AND GPL-2+ AND GPL-3+ with Autoconf exception AND public-domain AND GPL-2 AND GAP AND LGPL-3+ | obligations |
| deb | libnewt0.52:arm64 | 0.52.24-2ubuntu2 | LGPL-2 AND GPL-2+ | obligations |
| deb | libnfnetlink0:arm64 | 1.0.2-2build1 | GPL-2.0+ | review |
| deb | libnfs14:arm64 | 5.0.2-1ubuntu0.24.04.1 | LGPL-2.1+ AND BSD-3-Clause AND GPL-3+ AND BSD-2-clause | obligations |
| deb | libnftables1:arm64 | 1.0.9-1ubuntu0.1 | GPL-2 AND GPL-2+ AND CC-BY-SA-4.0 | review |
| deb | libnftnl11:arm64 | 1.2.6-2build1 | GPL-2+ AND GPL-2 | review |
| deb | libnghttp2-14:arm64 | 1.59.0-1ubuntu0.3 | Expat AND all-permissive AND GPL-3+ with autoconf exception AND MIT AND BSD-2-clause | review |
| deb | libnl-3-200:arm64 | 3.7.0-0.3build1.1 | src/nl-addr-add.c | review |
| deb | libnl-3-dev:arm64 | 3.7.0-0.3build1.1 | src/nl-addr-add.c | review |
| deb | libnl-genl-3-200:arm64 | 3.7.0-0.3build1.1 | src/nl-addr-add.c | review |
| deb | libnl-genl-3-dev:arm64 | 3.7.0-0.3build1.1 | src/nl-addr-add.c | review |
| deb | libnl-route-3-200:arm64 | 3.7.0-0.3build1.1 | src/nl-addr-add.c | review |
| deb | libnm0:arm64 | 1.46.0-1ubuntu2.7 | GPL-2+ AND LGPL-2.1+ AND GFDL-NIV-1.1+ | obligations |
| deb | libnma-common | 1.10.6-3build2 | GPL-2+ AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | libnma-gtk4-0:arm64 | 1.10.6-3build2 | GPL-2+ AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | libnma0:arm64 | 1.10.6-3build2 | GPL-2+ AND LGPL-2+ AND LGPL-2.1+ | obligations |
| deb | libnotify-bin | 0.8.3-1build2 | This library is free software; you can redistribute it and/or | review |
| deb | libnotify4:arm64 | 0.8.3-1build2 | This library is free software; you can redistribute it and/or | review |
| deb | libnpth0t64:arm64 | 1.6-3.1build1 | LGPL-2.1+ | obligations |
| deb | libnsl-dev:arm64 | 1.3.0-3build3 | LGPL-2.1+ AND LGPL-2.1 AND BSD-3-clause AND permissive-fsf AND permissive-makefile-in AND permissive-autoconf-m4-no-warranty AND GPL-3+-autoconf-exception AND permissive-configure AND GPL-2+-autoconf-exception AND MIT AND GPL-2+-libtool-exception AND permissive-autoconf-m4 | obligations |
| deb | libnsl2:arm64 | 1.3.0-3build3 | LGPL-2.1+ AND LGPL-2.1 AND BSD-3-clause AND permissive-fsf AND permissive-makefile-in AND permissive-autoconf-m4-no-warranty AND GPL-3+-autoconf-exception AND permissive-configure AND GPL-2+-autoconf-exception AND MIT AND GPL-2+-libtool-exception AND permissive-autoconf-m4 | obligations |
| deb | libnspr4:arm64 | 2:4.35-1.1build1 | MPL-2.0 | obligations |
| deb | libnss-myhostname:arm64 | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | libnss-systemd:arm64 | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | libnss3:arm64 | 2:3.98-1ubuntu0.1 | MPL-2.0 AND Zlib AND BSD-3 AND public-domain | obligations |
| deb | libntfs-3g89t64:arm64 | 1:2022.10.3-1.2ubuntu3.1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libnuma1:arm64 | 2.0.18-1ubuntu0.24.04.1 | UNKNOWN | unknown |
| deb | libnvme1t64 | 1.8-3ubuntu1 | LGPL-2.1+ AND CC0 AND MIT AND GPL-2 AND Apache-2.0 | obligations |
| deb | libodbc2:arm64 | 2.3.12-1ubuntu0.24.04.1 | LGPL-2.1+ AND GPL-2+ AND LGPL-2+ AND ppowell | obligations |
| deb | libodbcinst2:arm64 | 2.3.12-1ubuntu0.24.04.1 | LGPL-2.1+ AND GPL-2+ AND LGPL-2+ AND ppowell | obligations |
| deb | libogdi4.1:arm64 | 4.1.1+ds-3build1 | OGDI-LAS AND MIT AND MIT or LGPL-2.1+ AND public-domain AND OGDI-3I AND OGDI-QUEEN AND VPFLIB AND GPL-2+ AND LGPL-2.1+ | obligations |
| deb | libonig5:arm64 | 6.9.9-1build1 | BSD-2-clause AND GPL-2+ | review |
| deb | libopenal-data | 1:1.23.1-4build1 | LGPL-2+ AND Apache-2.0 AND Expat AND GPL-3+ AND BSD-3-clause AND GPL-2+ | obligations |
| deb | libopenal1:arm64 | 1:1.23.1-4build1 | LGPL-2+ AND Apache-2.0 AND Expat AND GPL-3+ AND BSD-3-clause AND GPL-2+ | obligations |
| deb | libopencv-calib3d-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-calib3d406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-contrib-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-contrib406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-core-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-core406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-dev | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-dnn-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-dnn406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-features2d-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-features2d406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-flann-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-flann406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-highgui-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-highgui406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-imgcodecs-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-imgcodecs406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-imgproc-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-imgproc406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-ml-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-ml406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-objdetect-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-objdetect406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-photo-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-photo406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-shape-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-shape406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-stitching-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-stitching406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-superres-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-superres406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-video-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-video406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-videoio-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-videoio406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-videostab-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-videostab406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-viz-dev:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopencv-viz406t64:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | libopengl0:arm64 | 1.7.0-1build1 | MIT AND Apache-2.0 AND public-domain AND GPL-3+ AND BSD-1-clause AND GPL | review |
| deb | libopenmpi3t64:arm64 | 4.1.6-7ubuntu2 | Redistribution and use in source and binary forms, with or without AND GNU Libltdl is free software; you can redistribute it and/or | review |
| deb | libopenmpt-modplug1:arm64 | 0.8.9.0-openmpt1-2build2 | BSD-3-clause AND GPL-2+ with Autoconf exception AND GPL-3+ with AutoConf exception AND X11 AND GPL-2+ with LibTool exception AND GPL-3+ with Autoconf Macros exception AND GNU-All-Permissive-License AND GNU-All-Permissive-License-FSF | review |
| deb | libopenmpt0t64:arm64 | 0.7.3-1.1build3 | BSD-3-clause AND GPL-2+ with Autoconf exception AND GPL-3+ with AutoConf exception AND X11 AND GPL-2+ with LibTool exception AND GPL-3+ with Autoconf Macros exception AND GNU-All-Permissive-License AND GNU-All-Permissive-License-FSF AND BSD-3-clause or BSL-1.0 AND BSL-1.0 | review |
| deb | liborc-0.4-0t64:arm64 | 1:0.4.38-1ubuntu0.1 | UNKNOWN | unknown |
| deb | libp11-kit0:arm64 | 0.25.3-4ubuntu2.1 | BSD-3-clause AND FSFULLR AND GPL-2+ with Autoconf-data exception AND GPL-3+ with Autoconf-data exception AND X11 AND ISC AND customFSFULLRWD AND Apache-2.0 AND LGPL-2.1+ AND customFSFUL AND FSFAP | obligations |
| deb | libpackagekit-glib2-18:arm64 | 1.2.8-2ubuntu1.5 | GPL-2+ and LGPL-2.1+ AND GPL-2+ AND LGPL-2.1+ AND FSFAP | obligations |
| deb | libpam-cap:arm64 | 1:2.66-5ubuntu2.4 | BSD-3-clause or GPL-2 AND BSD-3-clause or GPL-2+ AND BSD-3-clause AND GPL-2 AND GPL-2+ | review |
| deb | libpam-gnome-keyring:arm64 | 46.1-2ubuntu0.2 | GPL-2+ AND LGPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND BSD-3-clause and GPL-2+ or LGPL-3+ AND custom-license AND MPL-1.1 or GPL-2+ or LGPL-2.1+ AND GPL-2+ with AutoConf exception AND FSFAP AND FSFULLR AND GPL-3+ with AutoConf exception AND FSFULLR or GPL-2+ with AutoConf exception AND GPL-2+ with LibTool exception AND FSFULLR or GPL-2+ with LibTool exception AND Expat AND FSFUL AND LGPL-3+ AND MPL-1.1 | obligations |
| deb | libpam-modules:arm64 | 1.5.3-5ubuntu5.5 | BSD-3-clause or GPL AND GPL-2 AND GPL-2+ AND GPL-3 AND GPL-3+ with Bison exception AND BSD-tcp_wrappers AND LGPL-2+ AND public-domain AND Beerware | obligations |
| deb | libpam-modules-bin | 1.5.3-5ubuntu5.5 | BSD-3-clause or GPL AND GPL-2 AND GPL-2+ AND GPL-3 AND GPL-3+ with Bison exception AND BSD-tcp_wrappers AND LGPL-2+ AND public-domain AND Beerware | obligations |
| deb | libpam-runtime | 1.5.3-5ubuntu5.5 | BSD-3-clause or GPL AND GPL-2 AND GPL-2+ AND GPL-3 AND GPL-3+ with Bison exception AND BSD-tcp_wrappers AND LGPL-2+ AND public-domain AND Beerware | obligations |
| deb | libpam-systemd:arm64 | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | libpam0g:arm64 | 1.5.3-5ubuntu5.5 | BSD-3-clause or GPL AND GPL-2 AND GPL-2+ AND GPL-3 AND GPL-3+ with Bison exception AND BSD-tcp_wrappers AND LGPL-2+ AND public-domain AND Beerware | obligations |
| deb | libpango-1.0-0:arm64 | 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ AND Example AND LGPL-2+ AND LGPL-2+ and TCL AND Unicode AND LGPL-2+ and ICU AND Chromium-BSD-style AND Apache-2 and Bitstream-Vera and OFL-1.1 AND Apache-2 AND Bitstream-Vera AND ICU AND LGPL-2.1+ AND TCL AND OFL-1.1 | obligations |
| deb | libpangocairo-1.0-0:arm64 | 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ AND Example AND LGPL-2+ AND LGPL-2+ and TCL AND Unicode AND LGPL-2+ and ICU AND Chromium-BSD-style AND Apache-2 and Bitstream-Vera and OFL-1.1 AND Apache-2 AND Bitstream-Vera AND ICU AND LGPL-2.1+ AND TCL AND OFL-1.1 | obligations |
| deb | libpangoft2-1.0-0:arm64 | 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ AND Example AND LGPL-2+ AND LGPL-2+ and TCL AND Unicode AND LGPL-2+ and ICU AND Chromium-BSD-style AND Apache-2 and Bitstream-Vera and OFL-1.1 AND Apache-2 AND Bitstream-Vera AND ICU AND LGPL-2.1+ AND TCL AND OFL-1.1 | obligations |
| deb | libpangomm-1.4-1v5:arm64 | 2.46.4-1build3 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libpangomm-2.48-1t64:arm64 | 2.52.0-1build1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libpangoxft-1.0-0:arm64 | 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ AND Example AND LGPL-2+ AND LGPL-2+ and TCL AND Unicode AND LGPL-2+ and ICU AND Chromium-BSD-style AND Apache-2 and Bitstream-Vera and OFL-1.1 AND Apache-2 AND Bitstream-Vera AND ICU AND LGPL-2.1+ AND TCL AND OFL-1.1 | obligations |
| deb | libpaper1:arm64 | 1.1.29build1 | UNKNOWN | unknown |
| deb | libparted2t64:arm64 | 3.6-4build1 | UNKNOWN | unknown |
| deb | libpcap0.8t64:arm64 | 1.10.4-4.1ubuntu3 | UNKNOWN | unknown |
| deb | libpci3:arm64 | 1:3.10.0-2build1 | GPL-2+ | review |
| deb | libpciaccess0:arm64 | 0.17-3ubuntu0.24.04.2 | UNKNOWN | unknown |
| deb | libpcre16-3:arm64 | 2:8.39-15build1 | UNKNOWN | unknown |
| deb | libpcre3:arm64 | 2:8.39-15build1 | UNKNOWN | unknown |
| deb | libpcre3-dev:arm64 | 2:8.39-15build1 | UNKNOWN | unknown |
| deb | libpcre32-3:arm64 | 2:8.39-15build1 | UNKNOWN | unknown |
| deb | libpcrecpp0v5:arm64 | 2:8.39-15build1 | UNKNOWN | unknown |
| deb | libpcsclite1:arm64 | 2.0.3-1build1 | BSD-3-clause AND ISC AND GPL-3+ | review |
| deb | libperl5.38t64:arm64 | 5.38.2-3.2ubuntu0.3 | GPL-1+ or Artistic AND Expat AND REGCOMP, and GPL-1+ or Artistic AND GPL-3+-WITH-BISON-EXCEPTION AND Unicode AND GPL-1+ or Artistic, and Unicode AND BZIP AND ZLIB AND Artistic AND GPL-2+ or Artistic AND Expat or GPL-1+ or Artistic AND FSFAP AND BSD-3-clause-with-weird-numbering AND CC0-1.0 AND TEXT-TABS AND GPL-1+ or Artistic, and BSD-4-clause-POWERDOG AND GPL-1+ or Artistic, and BSD-3-clause-GENERIC AND BSD-3-clause AND SDBM-PUBLIC-DOMAIN AND DONT-CHANGE-THE-GPL AND GPL-1+ or Artistic or Artistic-dist AND Artistic-dist AND Artistic or GPL-1+ or Artistic-dist AND GPL-1+ or Artistic, and Expat AND LGPL-2.1 AND GPL-1+ AND GPL-2+ AND Artistic-2 AND BSD-4-clause-POWERDOG AND BSD-3-clause-GENERIC AND REGCOMP | obligations |
| deb | libpgm-5.3-0t64:arm64 | 5.3.128~dfsg-2.1build1 | LGPL-2.1 AND LGPL-2+ AND BSD-3-clause and ISC AND BSD-3-clause AND ISC | obligations |
| deb | libpipeline1:arm64 | 1.5.7-2 | GPL-2+ AND GPL-3+ | review |
| deb | libpipewire-0.3-0t64:arm64 | 1.0.5-1ubuntu3.2 | Expat and LGPL-2.1+ AND Expat AND BZIP2 AND LGPL-2.1+ AND GPL-2 AND LGPL-2+ and LGPL-2.1+ and Expat AND LGPL-2+ AND FFTPACK | obligations |
| deb | libpipewire-0.3-modules:arm64 | 1.0.5-1ubuntu3.2 | Expat and LGPL-2.1+ AND Expat AND BZIP2 AND LGPL-2.1+ AND GPL-2 AND LGPL-2+ and LGPL-2.1+ and Expat AND LGPL-2+ AND FFTPACK | obligations |
| deb | libpixman-1-0:arm64 | 0.42.2-1build1 | UNKNOWN | unknown |
| deb | libpkcs11-helper1t64:arm64 | 1.29.0-2.1build2 | BSD-3-clause or GPL-2 AND permissive AND BSD-3-clause AND GPL-2 | review |
| deb | libpkgconf3:arm64 | 1.8.1-2build1 | ISC AND BSD-4 AND BSD-2 AND X11 AND GPL-2+ | review |
| deb | libplacebo338:arm64 | 6.338.2-2build1 | LGPL-2.1+ AND CC0 AND LGPL-2.1+ or Expat AND LGPL-2.1+ and Zlib AND LGPL-2.1+ and CC0 AND Expat AND Zlib | obligations |
| deb | libplist-2.0-4:arm64 | 2.3.0-1~exp2build2 | LGPL-2.1-or-later AND Expat AND GPL-3.0-or-later | obligations |
| deb | libplymouth5:arm64 | 24.004.60-1ubuntu7.1 | GPL-2+ AND other | review |
| deb | libpmix2t64:arm64 | 5.0.1-4.1build1 | GPL-2 AND MIT | review |
| deb | libpng-dev:arm64 | 1.6.43-5ubuntu0.6 | libpng AND expat AND GPL-2+ or BSD-like-with-advertising-clause AND libpng OR Apache-2.0 OR BSD-3-clause AND Apache-2.0 AND GPL-2+ AND BSD-like-with-advertising-clause AND BSD-3-clause | review |
| deb | libpng16-16t64:arm64 | 1.6.43-5ubuntu0.6 | libpng AND expat AND GPL-2+ or BSD-like-with-advertising-clause AND libpng OR Apache-2.0 OR BSD-3-clause AND Apache-2.0 AND GPL-2+ AND BSD-like-with-advertising-clause AND BSD-3-clause | review |
| deb | libpocketsphinx3:arm64 | 0.8.0+real5prealpha+1-15ubuntu5 | BSD-2 AND BSD-3-clause AND GPL-2+ | review |
| deb | libpolkit-agent-1-0:arm64 | 124-2ubuntu1.24.04.3 | LGPL-2.0+ and Expat AND Expat AND Apache-2.0 AND LGPL-2.0+ | obligations |
| deb | libpolkit-gobject-1-0:arm64 | 124-2ubuntu1.24.04.3 | LGPL-2.0+ and Expat AND Expat AND Apache-2.0 AND LGPL-2.0+ | obligations |
| deb | libpoppler-cpp0t64:arm64 | 24.02.0-1ubuntu9.9 | GPL-2 or GPL-3 AND Apache-2.0 AND GPL-2 AND GPL-3 | review |
| deb | libpoppler-glib8t64:arm64 | 24.02.0-1ubuntu9.9 | GPL-2 or GPL-3 AND Apache-2.0 AND GPL-2 AND GPL-3 | review |
| deb | libpoppler134:arm64 | 24.02.0-1ubuntu9.9 | GPL-2 or GPL-3 AND Apache-2.0 AND GPL-2 AND GPL-3 | review |
| deb | libpopt0:arm64 | 1.19+dfsg-1build1 | expat AND GPL-2+ | review |
| deb | libportaudio2:arm64 | 19.6.0-1.2build3 | UNKNOWN | unknown |
| deb | libpostproc57:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libppd2:arm64 | 2:2.0.0-0ubuntu4.1 | Apache-2.0-with-GPL2-LGPL2-Exception AND GPL-2+ | obligations |
| deb | libppd2-common | 2:2.0.0-0ubuntu4.1 | Apache-2.0-with-GPL2-LGPL2-Exception AND GPL-2+ | obligations |
| deb | libpresage-data | 0.9.1-2.6ubuntu2 | GPL-2+ AND ZLIB AND public-domain AND Scintilla-and-Scite | review |
| deb | libpresage1v5:arm64 | 0.9.1-2.6ubuntu2 | GPL-2+ AND ZLIB AND public-domain AND Scintilla-and-Scite | review |
| deb | libproc-processtable-perl:arm64 | 0.636-1build3 | Artistic or GPL-1+ AND other AND GPL-2 AND LGPL-2.1+ AND Artistic AND GPL-1+ | obligations |
| deb | libproc2-0:arm64 | 2:4.0.4-4ubuntu3.2 | LGPL-2.1+ AND LGPL-2.0+ AND GPL-2.0+ | obligations |
| deb | libproj25:arm64 | 9.4.0-1build2 | Expat AND LRUCache11 AND Apache-2.0 AND public-domain AND GPL-3+ with Bison exception AND GPL-2+ | review |
| deb | libprotobuf-lite32t64:arm64 | 3.21.12-8.2ubuntu0.3 | BSD-3-Clause~Google AND GPLWithACException AND Apache-2.0 AND Public-Domain or Expat AND GPL-3 AND BSD-3-Clause AND Public-Domain AND Expat | review |
| deb | libprotobuf32t64:arm64 | 3.21.12-8.2ubuntu0.3 | BSD-3-Clause~Google AND GPLWithACException AND Apache-2.0 AND Public-Domain or Expat AND GPL-3 AND BSD-3-Clause AND Public-Domain AND Expat | review |
| deb | libproxy1-plugin-gsettings:arm64 | 0.5.4-4build1 | LGPL-2.1+ AND GPL-3+ AND LGPL-2.1+ or GPL-2+ or NPL-1.1 AND GPL-2+ AND MPL-1.1 AND NPL-1.1 | obligations |
| deb | libproxy1-plugin-networkmanager:arm64 | 0.5.4-4build1 | LGPL-2.1+ AND GPL-3+ AND LGPL-2.1+ or GPL-2+ or NPL-1.1 AND GPL-2+ AND MPL-1.1 AND NPL-1.1 | obligations |
| deb | libproxy1v5:arm64 | 0.5.4-4build1 | LGPL-2.1+ AND GPL-3+ AND LGPL-2.1+ or GPL-2+ or NPL-1.1 AND GPL-2+ AND MPL-1.1 AND NPL-1.1 | obligations |
| deb | libpulse-mainloop-glib0:arm64 | 1:16.1+dfsg1-2ubuntu10.1 | LGPL-2.1+ AND other AND GPL-2+ AND LGPL-2+ | obligations |
| deb | libpulse0:arm64 | 1:16.1+dfsg1-2ubuntu10.1 | LGPL-2.1+ AND other AND GPL-2+ AND LGPL-2+ | obligations |
| deb | libpython3-dev:arm64 | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | libpython3-stdlib:arm64 | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | libqalculate-data | 4.9.0-1.1build2 | GPL-2.0-or-later | review |
| deb | libqalculate22t64:arm64 | 4.9.0-1.1build2 | GPL-2.0-or-later | review |
| deb | libqhull-r8.0:arm64 | 2020.2-6build1 | Qhull AND GPL-3+ | review |
| deb | libqmi-glib5:arm64 | 1.35.2-0ubuntu2 | LGPL-2.0+ AND GPL-2+ AND GFDL-NIV-1.3+ | obligations |
| deb | libqmi-proxy | 1.35.2-0ubuntu2 | LGPL-2.0+ AND GPL-2+ AND GFDL-NIV-1.3+ | obligations |
| deb | libqmi-utils | 1.35.2-0ubuntu2 | LGPL-2.0+ AND GPL-2+ AND GFDL-NIV-1.3+ | obligations |
| deb | libqpdf29t64:arm64 | 11.9.0-1.1ubuntu0.1 | UNKNOWN | unknown |
| deb | libqrencode4:arm64 | 4.1.1-1build2 | LGPL-2.1+ AND public-domain | obligations |
| deb | libqrtr-glib0:arm64 | 1.2.2-1ubuntu4 | LGPL-2.1+ AND GFDL-1.3+ AND GPL-2+ | obligations |
| deb | libqt5core5a:arm64 | 5.15.3+dfsg-2ubuntu0.2 | UNKNOWN | unknown |
| deb | libqt5core5t64:arm64 | 5.15.13+dfsg-1ubuntu1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND GPL-3 with Qt-1.0 exception AND BSD-3-clause AND LGPL-3 or GPL-2+ AND Expat AND GPL-3 AND MPL-2.0 or GPL-2+ or LGPL-2.1+ AND W3C AND Unicode AND Hybrid-BSD AND BSD-2-clause AND Apache-2.0 AND Harfbuzz AND GPL-2+ or FTL AND ICC AND libjpeg and BSD-3-clause and Zlib AND libpng AND public-domain AND CC0-1.0 AND brg-endian AND Bitstream AND Zlib AND LGPL-2.1+ AND LGPL-3 AND GPL-2 AND GPL-2+ AND FTL AND libjpeg AND MPL-2.0 | obligations |
| deb | libqt5dbus5t64:arm64 | 5.15.13+dfsg-1ubuntu1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND GPL-3 with Qt-1.0 exception AND BSD-3-clause AND LGPL-3 or GPL-2+ AND Expat AND GPL-3 AND MPL-2.0 or GPL-2+ or LGPL-2.1+ AND W3C AND Unicode AND Hybrid-BSD AND BSD-2-clause AND Apache-2.0 AND Harfbuzz AND GPL-2+ or FTL AND ICC AND libjpeg and BSD-3-clause and Zlib AND libpng AND public-domain AND CC0-1.0 AND brg-endian AND Bitstream AND Zlib AND LGPL-2.1+ AND LGPL-3 AND GPL-2 AND GPL-2+ AND FTL AND libjpeg AND MPL-2.0 | obligations |
| deb | libqt5gui5:arm64 | 5.15.3+dfsg-2ubuntu0.2 | UNKNOWN | unknown |
| deb | libqt5gui5t64:arm64 | 5.15.13+dfsg-1ubuntu1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND GPL-3 with Qt-1.0 exception AND BSD-3-clause AND LGPL-3 or GPL-2+ AND Expat AND GPL-3 AND MPL-2.0 or GPL-2+ or LGPL-2.1+ AND W3C AND Unicode AND Hybrid-BSD AND BSD-2-clause AND Apache-2.0 AND Harfbuzz AND GPL-2+ or FTL AND ICC AND libjpeg and BSD-3-clause and Zlib AND libpng AND public-domain AND CC0-1.0 AND brg-endian AND Bitstream AND Zlib AND LGPL-2.1+ AND LGPL-3 AND GPL-2 AND GPL-2+ AND FTL AND libjpeg AND MPL-2.0 | obligations |
| deb | libqt5network5t64:arm64 | 5.15.13+dfsg-1ubuntu1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND GPL-3 with Qt-1.0 exception AND BSD-3-clause AND LGPL-3 or GPL-2+ AND Expat AND GPL-3 AND MPL-2.0 or GPL-2+ or LGPL-2.1+ AND W3C AND Unicode AND Hybrid-BSD AND BSD-2-clause AND Apache-2.0 AND Harfbuzz AND GPL-2+ or FTL AND ICC AND libjpeg and BSD-3-clause and Zlib AND libpng AND public-domain AND CC0-1.0 AND brg-endian AND Bitstream AND Zlib AND LGPL-2.1+ AND LGPL-3 AND GPL-2 AND GPL-2+ AND FTL AND libjpeg AND MPL-2.0 | obligations |
| deb | libqt5opengl5t64:arm64 | 5.15.13+dfsg-1ubuntu1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND GPL-3 with Qt-1.0 exception AND BSD-3-clause AND LGPL-3 or GPL-2+ AND Expat AND GPL-3 AND MPL-2.0 or GPL-2+ or LGPL-2.1+ AND W3C AND Unicode AND Hybrid-BSD AND BSD-2-clause AND Apache-2.0 AND Harfbuzz AND GPL-2+ or FTL AND ICC AND libjpeg and BSD-3-clause and Zlib AND libpng AND public-domain AND CC0-1.0 AND brg-endian AND Bitstream AND Zlib AND LGPL-2.1+ AND LGPL-3 AND GPL-2 AND GPL-2+ AND FTL AND libjpeg AND MPL-2.0 | obligations |
| deb | libqt5svg5:arm64 | 5.15.13-1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND BSD-3-clause AND BSD-3-clause and Expat AND LGPL-3 or GPL-2, and HPND-sell-variant AND GPL-3 with Qt-1.0 exception AND HPND-sell-variant AND GPL-2 AND LGPL-3 AND Expat | obligations |
| deb | libqt5test5t64:arm64 | 5.15.13+dfsg-1ubuntu1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND GPL-3 with Qt-1.0 exception AND BSD-3-clause AND LGPL-3 or GPL-2+ AND Expat AND GPL-3 AND MPL-2.0 or GPL-2+ or LGPL-2.1+ AND W3C AND Unicode AND Hybrid-BSD AND BSD-2-clause AND Apache-2.0 AND Harfbuzz AND GPL-2+ or FTL AND ICC AND libjpeg and BSD-3-clause and Zlib AND libpng AND public-domain AND CC0-1.0 AND brg-endian AND Bitstream AND Zlib AND LGPL-2.1+ AND LGPL-3 AND GPL-2 AND GPL-2+ AND FTL AND libjpeg AND MPL-2.0 | obligations |
| deb | libqt5widgets5t64:arm64 | 5.15.13+dfsg-1ubuntu1 | LGPL-3 or GPL-2 AND GFDL-NIV-1.3 AND GPL-3 with Qt-1.0 exception AND BSD-3-clause AND LGPL-3 or GPL-2+ AND Expat AND GPL-3 AND MPL-2.0 or GPL-2+ or LGPL-2.1+ AND W3C AND Unicode AND Hybrid-BSD AND BSD-2-clause AND Apache-2.0 AND Harfbuzz AND GPL-2+ or FTL AND ICC AND libjpeg and BSD-3-clause and Zlib AND libpng AND public-domain AND CC0-1.0 AND brg-endian AND Bitstream AND Zlib AND LGPL-2.1+ AND LGPL-3 AND GPL-2 AND GPL-2+ AND FTL AND libjpeg AND MPL-2.0 | obligations |
| deb | libqt5x11extras5:arm64 | 5.15.13-1 | LGPL-3 or GPL-2 AND GPL-3 with Qt-1.0 exception AND GFDL-NIV-1.3 AND BSD-3-clause AND GPL-2 AND LGPL-3 | obligations |
| deb | libraw1394-11:arm64 | 2.1.2-2build3 | This package is free software; you can redistribute it and/or | review |
| deb | libraw1394-dev:arm64 | 2.1.2-2build3 | This package is free software; you can redistribute it and/or | review |
| deb | librdmacm1t64:arm64 | 50.0-2ubuntu0.2 | BSD-MIT or GPL-2 AND GPL-2+ AND BSD-2-clause AND CC0 AND MIT AND BSD-MIT AND GPL-2 or BSD-2-clause AND GPL-2 AND GPL-2 or BSD-3-clause AND BSD-2-clause or GPL-2 AND BSD-3-clause or GPL-2 AND CPL-1.0 or BSD-2-clause or GPL-2 AND BSD-3-clause AND CPL-1.0 | review |
| deb | libreadline8t64:arm64 | 8.2-4build1 | GPL-3+ AND GPL-2+ AND GFDL-NIV-1.3+ AND ISC-no-attribution AND GPL-3 | review |
| deb | libreiserfscore0t64 | 1:3.6.27-7.1build1 | GPL-2 | review |
| deb | libresid-builder0c2a | 2.1.1-15ubuntu3 | UNKNOWN | unknown |
| deb | libroc0.3:arm64 | 0.3.0+dfsg-7ubuntu2 | MPL-2.0 AND CC0-1.0 | obligations |
| deb | librsvg2-2:arm64 | 2.58.0+dfsg-1build1 | LGPL-2+ AND FSFAP AND BSD-3-clause AND Expat AND Apache-2.0, and BSD-2-clause, and BSD-3-clause, and Expat, and Apache-2.0 or Expat or 0BSD, and Apache-2.0 or Boost-1.0, and Apache-2.0 or Expat, and Expat or Unlicense, and MPL-2.0, and Sun-permissive, and zlib AND CC-zero-waive-1.0-us AND OFL-1.1 AND Apache-2.0 AND MPL-2.0 AND Unlicense AND BSD-2-clause AND Sun-permissive AND Boost-1.0 AND zlib AND 0BSD | obligations |
| deb | librsvg2-common:arm64 | 2.58.0+dfsg-1build1 | LGPL-2+ AND FSFAP AND BSD-3-clause AND Expat AND Apache-2.0, and BSD-2-clause, and BSD-3-clause, and Expat, and Apache-2.0 or Expat or 0BSD, and Apache-2.0 or Boost-1.0, and Apache-2.0 or Expat, and Expat or Unlicense, and MPL-2.0, and Sun-permissive, and zlib AND CC-zero-waive-1.0-us AND OFL-1.1 AND Apache-2.0 AND MPL-2.0 AND Unlicense AND BSD-2-clause AND Sun-permissive AND Boost-1.0 AND zlib AND 0BSD | obligations |
| deb | librtmp1:arm64 | 2.4+20151223.gitfa8646d.1-2build7 | UNKNOWN | unknown |
| deb | librttopo1:arm64 | 1.1.0-3build2 | GPL-2+ | review |
| deb | librubberband2:arm64 | 3.3.0+dfsg-2build1 | GPL-2+ AND Expat AND BSD-3-clause AND Zlib AND other-1 | review |
| deb | libruby:arm64 | 1:3.2~ubuntu1 | RubyLicense | review |
| deb | libruby3.2:arm64 | 3.2.3-1ubuntu0.24.04.7 | BSD-2-clause or Ruby AND BSD-2-clause AND SIL-1.1 AND CC-BY-3.0-famfamfam AND Expat AND Expat or Ruby AND PreserveNotice AND 3C-BSD AND PublicDomain AND BSD-3-clause AND AllPermissions AND PartialGplArtisticAndRuby AND zlib/libpng AND GPL-1+ or Artistic AND CC0 AND Unicode AND Permissive AND Artistic AND GPL-1+ AND Ruby | obligations |
| deb | libsamplerate0:arm64 | 0.2.2-4build1 | BSD-2-clause AND GPL-2+ AND FSFAP AND GPL-3+ | review |
| deb | libsane-common | 1.2.1-7build4 | GPL-2+ with sane exception AND GPL-2+ AND GPL-2 AND GPL-3+ AND Artistic AND LGPL-2.1+ | obligations |
| deb | libsane-hpaio:arm64 | 3.23.12+dfsg0-0ubuntu5 | GPL-2+ AND BSD-2-clause AND BSD-3-clause AND Expat AND FSFUL AND public-domain AND GPL-2 | review |
| deb | libsane1:arm64 | 1.2.1-7build4 | GPL-2+ with sane exception AND GPL-2+ AND GPL-2 AND GPL-3+ AND Artistic AND LGPL-2.1+ | obligations |
| deb | libsasl2-2:arm64 | 2.1.28+dfsg1-5ubuntu3.1 | BSD-3-Clause-Attribution AND BSD-3-clause AND BSD-2-clause AND GPL-3+ AND GPL-3 AND BSD-4-clause-UC AND RSA-MD AND BSD-3-Clause-Attribution and IBM-as-is AND BSD-3-clause-JANET and BSD-3-Clause-Attribution AND BSD-3-clause-PADL and MIT-OpenVision AND MIT-OpenVision AND OpenLDAP AND FSFULLR and MIT-CMU AND BSD-3-Clause-Attribution and MIT-Export AND BSD-2-clause and MIT-CMU AND BSD-2.2-clause AND FSFULLR AND MIT-Export AND MIT-CMU AND BSD-3-clause-JANET AND BSD-3-clause-PADL AND IBM-as-is | review |
| deb | libsasl2-modules:arm64 | 2.1.28+dfsg1-5ubuntu3.1 | BSD-3-Clause-Attribution AND BSD-3-clause AND BSD-2-clause AND GPL-3+ AND GPL-3 AND BSD-4-clause-UC AND RSA-MD AND BSD-3-Clause-Attribution and IBM-as-is AND BSD-3-clause-JANET and BSD-3-Clause-Attribution AND BSD-3-clause-PADL and MIT-OpenVision AND MIT-OpenVision AND OpenLDAP AND FSFULLR and MIT-CMU AND BSD-3-Clause-Attribution and MIT-Export AND BSD-2-clause and MIT-CMU AND BSD-2.2-clause AND FSFULLR AND MIT-Export AND MIT-CMU AND BSD-3-clause-JANET AND BSD-3-clause-PADL AND IBM-as-is | review |
| deb | libsasl2-modules-db:arm64 | 2.1.28+dfsg1-5ubuntu3.1 | BSD-3-Clause-Attribution AND BSD-3-clause AND BSD-2-clause AND GPL-3+ AND GPL-3 AND BSD-4-clause-UC AND RSA-MD AND BSD-3-Clause-Attribution and IBM-as-is AND BSD-3-clause-JANET and BSD-3-Clause-Attribution AND BSD-3-clause-PADL and MIT-OpenVision AND MIT-OpenVision AND OpenLDAP AND FSFULLR and MIT-CMU AND BSD-3-Clause-Attribution and MIT-Export AND BSD-2-clause and MIT-CMU AND BSD-2.2-clause AND FSFULLR AND MIT-Export AND MIT-CMU AND BSD-3-clause-JANET AND BSD-3-clause-PADL AND IBM-as-is | review |
| deb | libsbc1:arm64 | 2.0-1build1 | GPL-2+ AND LGPL-2.1+ | obligations |
| deb | libsctp1:arm64 | 1.0.19+dfsg-2build1 | GPL-2.0+ AND LGPL-2.1+ AND BSD-3-clause | obligations |
| deb | libsdl2-2.0-0:arm64 | 2.30.0+dfsg-1ubuntu3.1 | zlib/libpng and zlib-libpng-like-permissive AND zlib/libpng and Expat-like and Apache-2.0 AND SGI-Free-Software-License-B AND BSD-3-clause or GPL-3 or hidapi-orig, and zlib/libpng AND SunPro AND PublicDomain_Sam_Lantinga AND PublicDomain_David_Ludwig AND BrownUn_UnCalifornia_ErikCorry AND Gareth_McCaughan AND zlib/libpng and RSA_Data_Security AND Mozilla-permissive and Expat and zlib/libpng AND Apache-2.0 AND LGPL-2.1+ AND BSD-3-clause AND PublicDomain_Edgar_Simo AND zlib/libpng AND BSD-3-clause-chromium AND Expat and MIT-open-group AND BSD-3-clause-kitware AND Expat AND Expat-like AND zlib-libpng-like-permissive AND GPL-3 AND RSA_Data_Security AND MIT-open-group AND Mozilla-permissive AND hidapi-orig | obligations |
| deb | libseccomp2:arm64 | 2.5.5-1ubuntu3.1 | LGPL-2.1 | obligations |
| deb | libsecret-1-0:arm64 | 0.21.4-1build3 | LGPL-2.1+ AND BSD-3-clause AND GPL-2+ AND Apache-2.0 | obligations |
| deb | libsecret-common | 0.21.4-1build3 | LGPL-2.1+ AND BSD-3-clause AND GPL-2+ AND Apache-2.0 | obligations |
| deb | libselinux1:arm64 | 3.5-2ubuntu2.1 | public-domain AND GPL-2 | review |
| deb | libselinux1-dev:arm64 | 3.5-2ubuntu2.1 | public-domain AND GPL-2 | review |
| deb | libsemanage-common | 3.5-1build5 | LGPL-2.1+ AND GPL-2 | obligations |
| deb | libsemanage2:arm64 | 3.5-1build5 | LGPL-2.1+ AND GPL-2 | obligations |
| deb | libsensors-config | 1:3.6.0-9build1 | UNKNOWN | unknown |
| deb | libsensors5:arm64 | 1:3.6.0-9build1 | UNKNOWN | unknown |
| deb | libsepol-dev:arm64 | 3.5-2build1 | LGPL-2.1+ AND Zlib AND GPL-2 AND GPL-2+ | obligations |
| deb | libsepol2:arm64 | 3.5-2build1 | LGPL-2.1+ AND Zlib AND GPL-2 AND GPL-2+ | obligations |
| deb | libsframe1:arm64 | 2.42-4ubuntu2.10 | UNKNOWN | unknown |
| deb | libshine3:arm64 | 3.1.1-2build1 | LGPL-2 AND GPL-2+ | obligations |
| deb | libshout3:arm64 | 2.4.6-1build2 | LGPL-2+ AND FSFULLR~Makefile.in AND FSFULLR and GPL-2+ with Libtool exception AND GPL-2+ with Autoconf exception AND GPL-3+~file with Autoconf exception AND NTP~Rushing AND FSFUL AND FSFULLR AND X11 AND GPL-3+ AND GPL-2+ AND GPL-3+~file | obligations |
| deb | libsidplay2 | 2.1.1-15ubuntu3 | UNKNOWN | unknown |
| deb | libsigc++-2.0-0v5:arm64 | 2.12.1-2 | LGPL-3.0-or-later AND permissive-axboost-1 AND Public-Domain AND LGPL-2.1-or-later AND GPL-3.0-or-later | obligations |
| deb | libsigc++-3.0-0:arm64 | 3.6.0-2 | LGPL-3.0-or-later AND permissive-axboost-1 AND Public-Domain AND LGPL-2.1-or-later AND GPL-3.0-or-later | obligations |
| deb | libsixel1:arm64 | 1.10.3-3build1 | Expat AND public-domain | review |
| deb | libslang2:arm64 | 2.3.3-3build2 | GPL-2+ | review |
| deb | libsm6:arm64 | 2:1.2.3-1build3 | UNKNOWN | unknown |
| deb | libsmartcols1:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | libsmbclient0:arm64 | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | libsnapd-glib-2-1:arm64 | 1.64-0ubuntu5 | LGPL-2 or LGPL-3 AND GPL-3+ AND LGPL-2 AND LGPL-3 | obligations |
| deb | libsndfile1:arm64 | 1.2.2-1ubuntu5.24.04.1 | LGPL-2.1+ AND gsm AND Apache-2.0 AND sun AND GPL-2+ AND LGPL-2+ AND BSD-3-clause AND BSD-3-clause and LGPL-2.1+ AND BSD-2-clause AND FSFAP AND GPL-3+ AND NTP | obligations |
| deb | libsnmp-base | 5.9.4+dfsg-1.1ubuntu3.2 | BSD-LIKE and BSD-3-clause AND BSD-3-clause AND GPL-2.0+ or Artistic-1.0 AND BSD-LIKE AND Artistic-1.0 AND GPL-2.0+ | review |
| deb | libsnmp40t64:arm64 | 5.9.4+dfsg-1.1ubuntu3.2 | BSD-LIKE and BSD-3-clause AND BSD-3-clause AND GPL-2.0+ or Artistic-1.0 AND BSD-LIKE AND Artistic-1.0 AND GPL-2.0+ | review |
| deb | libsocket++1:arm64 | 1.12.13+git20131030.5d039ba-1build1 | AS_IS AND PD | review |
| deb | libsodium23:arm64 | 1.0.18-1ubuntu0.24.04.1 | ISC AND BSD-2-clause AND public-domain AND CC0 AND MIT AND GPL-2+ | review |
| deb | libsoup-2.4-1:arm64 | 2.74.3-6ubuntu1.6 | LGPL-2.1+ AND LGPL-2+ AND Expat | obligations |
| deb | libsoup-3.0-0:arm64 | 3.4.4-5ubuntu0.7 | LGPL-2.1+ AND LGPL-2+ AND MPL-2.0 or RSA-Other AND Expat AND MPL-2.0 AND RSA-Other | obligations |
| deb | libsoup-3.0-common | 3.4.4-5ubuntu0.7 | LGPL-2.1+ AND LGPL-2+ AND MPL-2.0 or RSA-Other AND Expat AND MPL-2.0 AND RSA-Other | obligations |
| deb | libsoup2.4-common | 2.74.3-6ubuntu1.6 | LGPL-2.1+ AND LGPL-2+ AND Expat | obligations |
| deb | libsoxr0:arm64 | 0.1.3-4build3 | LGPL-2.1+ AND Spherepack AND permissive1 AND permissive2 | obligations |
| deb | libspa-0.2-modules:arm64 | 1.0.5-1ubuntu3.2 | Expat and LGPL-2.1+ AND Expat AND BZIP2 AND LGPL-2.1+ AND GPL-2 AND LGPL-2+ and LGPL-2.1+ and Expat AND LGPL-2+ AND FFTPACK | obligations |
| deb | libspatialaudio0t64:arm64 | 0.3.0+git20180730+dfsg1-2.1build1 | LGPL-2.1+ AND Expat AND BSD-3-clause | obligations |
| deb | libspatialite8t64:arm64 | 5.1.0-3build1 | MPL-1.1 or GPL-2+ or LGPL-2.1+ AND GPL-3+ AND public-domain AND GPL-2+ AND BSD-4-Clause AND LGPL-2+ AND LGPL-2.1+ AND MPL-1.1 | obligations |
| deb | libspectre1:arm64 | 0.2.12-1build2 | GPL-2+ | review |
| deb | libspeechd2:arm64 | 0.12.0~rc2-2build3 | GPL-2+ AND GFDL-NIV-1.2+ or GPL-2+ AND GFDL-NIV-1.2+ AND GPL-3+ with tex exception AND LGPL-2.1+ AND other AND GPL-2+ and public-domain AND public-domain | obligations |
| deb | libspeex1:arm64 | 1.2.1-2ubuntu2.24.04.1 | BSD-3-Clause AND GFDL-1.1-or-later AND BSD-3-Clause and custom-1 AND LGPL-2.0-or-later AND custom-1 | obligations |
| deb | libsphinxbase3t64:arm64 | 0.8+5prealpha+1-17build2 | BSD-2-clause AND BSD-3-clause-carnegie AND BSD-2-clause-beyond AND u-o-tennesee AND lucent AND BSD-3-clause AND GPL-2+ | review |
| deb | libsqlite3-0:arm64 | 3.45.1-1ubuntu2.5 | public-domain AND GPL-2+ | review |
| deb | libsrt1.5-gnutls:arm64 | 1.5.3-1build2 | MPL-2.0 AND BSD-3-clause AND Zlib AND unlicense AND LGPL-2.1+ | obligations |
| deb | libss2:arm64 | 1.47.0-2.4~exp1ubuntu4.1 | GPL-2 AND LGPL-2 AND BSD-3-Clause AND Apache-2 AND ISC AND GPL or MIT-US-export AND Kazlib AND Latex2e AND GPL-2+ with Texinfo exception | obligations |
| deb | libssh-4:arm64 | 0.10.6-2ubuntu0.4 | LGPL-2.1+~OpenSSL AND public-domain AND LGPL-2.1 AND BSD-2-clause AND BSD-3-clause AND LGPL-2.1+~OpenSSL or BSD-2-clause or BSD-3-clause | obligations |
| deb | libssh-gcrypt-4:arm64 | 0.10.6-2ubuntu0.4 | LGPL-2.1+~OpenSSL AND public-domain AND LGPL-2.1 AND BSD-2-clause AND BSD-3-clause AND LGPL-2.1+~OpenSSL or BSD-2-clause or BSD-3-clause | obligations |
| deb | libssl-dev:arm64 | 3.0.13-0ubuntu3.11 | UNKNOWN | unknown |
| deb | libssl3:arm64 | 3.0.2-0ubuntu1.21 | UNKNOWN | unknown |
| deb | libssl3t64:arm64 | 3.0.13-0ubuntu3.11 | Apache-2.0 AND Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libstartup-notification0:arm64 | 0.12-6build3 | part MIT, part LGPL, see below. | obligations |
| deb | libstdc++-13-dev:arm64 | 13.3.0-6ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libstdc++6:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libsuperlu6:arm64 | 6.0.1+dfsg1-1build1 | BSD-3-clause AND permissive AND GPL-2+ AND permissive-colamd | review |
| deb | libsvtav1enc1d1:arm64 | 1.7.0+dfsg-2build1 | BSD-3-Clause-Clear AND LGPL-2.1+ AND ISC AND Expat AND BSD-2-clause AND BSD-3-clause | obligations |
| deb | libswresample-dev:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libswresample4:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libswscale-dev:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libswscale7:arm64 | 7:6.1.1-3ubuntu5 | LGPL-2.1+ AND LGPL-2.1+ and Sundry AND GPL-2+ AND GPL-3+ AND Expat AND LGPL-2.1+ and BSD-3-clause AND public-domain AND ISC AND IJG AND LGPL-2.1+ and BSD-2-clause AND Zlib AND BSD-3-clause AND LGPL-2.1+ and Expat AND BSD-2-clause AND BSD-1-clause AND LGPL-2+ AND LGPL-2.1+ and BSL AND man-page AND BSL AND Sundry | obligations |
| deb | libsynctex2:arm64 | 2023.20230311.66589-9build3 | TeX-Live AND GPL-2+ AND MIT AND LPPL | review |
| deb | libsysfs2:arm64 | 2.1.1-6build1 | GPL-2+ AND LGPL-2.1+ | obligations |
| deb | libsystemd-shared:arm64 | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | libsystemd0:arm64 | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | libsz2:arm64 | 1.1.2-1build1 | UNKNOWN | unknown |
| deb | libtag1v5:arm64 | 1.13.1-1build1 | LGPL-2.1 or MPL-1.1 AND BSL-1.0 AND LGPL-2.1 AND BSD-2-clause AND MPL-1.1 | obligations |
| deb | libtag1v5-vanilla:arm64 | 1.13.1-1build1 | LGPL-2.1 or MPL-1.1 AND BSL-1.0 AND LGPL-2.1 AND BSD-2-clause AND MPL-1.1 | obligations |
| deb | libtalloc2:arm64 | 2.4.2-1build2 | LGPL-3.0+ AND PostgreSQL AND ISC AND BSD-3 AND GPL-3.0+ | obligations |
| deb | libtasn1-6:arm64 | 4.19.0-3ubuntu0.24.04.2 | UNKNOWN | unknown |
| deb | libtbb-dev:arm64 | 2021.11.0-2ubuntu2 | Apache-2.0 AND BSD-3-Clause AND BSD-like-bzip2 AND MIT AND GPL-1+ AND GPL-2 | review |
| deb | libtbb12:arm64 | 2021.11.0-2ubuntu2 | Apache-2.0 AND BSD-3-Clause AND BSD-like-bzip2 AND MIT AND GPL-1+ AND GPL-2 | review |
| deb | libtbbbind-2-5:arm64 | 2021.11.0-2ubuntu2 | Apache-2.0 AND BSD-3-Clause AND BSD-like-bzip2 AND MIT AND GPL-1+ AND GPL-2 | review |
| deb | libtbbmalloc2:arm64 | 2021.11.0-2ubuntu2 | Apache-2.0 AND BSD-3-Clause AND BSD-like-bzip2 AND MIT AND GPL-1+ AND GPL-2 | review |
| deb | libtcl8.6:arm64 | 8.6.14+dfsg-1build1 | UNKNOWN | unknown |
| deb | libtdb1:arm64 | 1.4.10-1build1 | LGPL-3.0+ AND GPL-3.0+ AND PostgreSQL AND ISC AND BSD-3 | obligations |
| deb | libteamdctl0:arm64 | 1.31-1build3 | LGPL-2.1+ AND GPL-2 AND BSD-3-clause or GPL-2 AND BSD-3-clause | obligations |
| deb | libtevent0t64:arm64 | 0.16.1-2build1 | LGPL-3.0+ AND GPL-3.0+ AND PostgreSQL AND ISC AND BSD-3 | obligations |
| deb | libtext-iconv-perl:arm64 | 1.7-8build3 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libthai-data | 0.1.29-2build1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libthai0:arm64 | 0.1.29-2build1 | LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libthunarx-3-0:arm64 | 4.18.8-1build3 | UNKNOWN | unknown |
| deb | libtiff-dev:arm64 | 4.5.1+git230720-4ubuntu2.5 | Hylafax | review |
| deb | libtiff6:arm64 | 4.5.1+git230720-4ubuntu2.5 | Hylafax | review |
| deb | libtiffxx6:arm64 | 4.5.1+git230720-4ubuntu2.5 | Hylafax | review |
| deb | libtimedate-perl | 2.3300-2 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libtirpc-common | 1.3.4+ds-1.1build1 | BSD-3-Clause AND GPL-2 AND __AUTO_PERMISSIVE__ AND BSD-2-Clause AND BSD-4-Clause AND LGPL-2.1+ AND PERMISSIVE | obligations |
| deb | libtirpc-dev:arm64 | 1.3.4+ds-1.1build1 | BSD-3-Clause AND GPL-2 AND __AUTO_PERMISSIVE__ AND BSD-2-Clause AND BSD-4-Clause AND LGPL-2.1+ AND PERMISSIVE | obligations |
| deb | libtirpc3t64:arm64 | 1.3.4+ds-1.1build1 | BSD-3-Clause AND GPL-2 AND __AUTO_PERMISSIVE__ AND BSD-2-Clause AND BSD-4-Clause AND LGPL-2.1+ AND PERMISSIVE | obligations |
| deb | libtk8.6:arm64 | 8.6.14-1build1 | UNKNOWN | unknown |
| deb | libtree-sitter0:arm64 | 0.20.8-2 | Expat AND Unicode | review |
| deb | libtry-tiny-perl | 0.31-2 | Expat | review |
| deb | libtsan0:arm64 | 11.5.0-1ubuntu1~24.04.1 | UNKNOWN | unknown |
| deb | libtsan2:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libtwolame0:arm64 | 0.4.0-2build3 | LGPL-2+ | obligations |
| deb | libu2f-udev | 1.1.10-3build3 | LGPL-2.1+ AND GPL-3+ | obligations |
| deb | libubsan1:arm64 | 14.2.0-4ubuntu2~24.04.1 | UNKNOWN | unknown |
| deb | libuchardet0:arm64 | 0.0.8-1build1 | MPL-1.1 or GPL-2+ or LGPL-2.1+ AND GPL-2+ AND LGPL-2.1+ AND MPL-1.1 | obligations |
| deb | libudev1:arm64 | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | libudfread0:arm64 | 1.1.2-1build1 | LGPL-2.1+ AND GPL-2+ with autoconf-macro exception | obligations |
| deb | libudisks2-0:arm64 | 2.10.1-6ubuntu1.3 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libunistring5:arm64 | 1.1-2build1.1 | LGPL-3+ or GPL-2+ AND FreeSoftware AND GPL-3+ or GFDL-NIV-1.2+ AND GPL-3+ AND GPL-2+ AND GPL-2+ with distribution exception AND GPL-2+ with distribution exception, Expat and GPL-2+ AND X11 AND LGPL-3+ AND GFDL-NIV-1.2+ | obligations |
| deb | libunwind8:arm64 | 1.6.2-3build1.1 | Expat AND GPL-2+ | review |
| deb | libupnp17t64:arm64 | 1:1.14.18-1.1ubuntu2 | BSD-3-clause-Intel AND GPL-3 AND Academia-Sinicai-XML-Now AND public-domain AND GPL-2+ with Autoconf exception AND GPL-3+ with Autoconf exception AND GPL-2+ AND MIT-like AND ISC | review |
| deb | libupower-glib3:arm64 | 1.90.3-1 | GPL-2+ AND GFDL-1.1+ | review |
| deb | liburi-perl | 5.27-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | liburiparser1:arm64 | 0.9.7+dfsg-2build1 | BSD-3-clause AND LGPL-2.1+ AND GPL-3+ | obligations |
| deb | libusb-0.1-4:arm64 | 2:0.1.12-35build1 | * libusb is covered by the LGPL: | obligations |
| deb | libusb-1.0-0:arm64 | 2:1.0.27-1 | UNKNOWN | unknown |
| deb | libusbmuxd6:arm64 | 2.0.2-4build3 | LGPL-2.1+ AND GPL-2+ AND GPL-3+ | obligations |
| deb | libutempter0:arm64 | 1.2.1-3build1 | LGPL-2.1 AND BSD-2-Clause | obligations |
| deb | libuuid-perl | 0.31-1build3 | Artistic AND Artistic or GPL-1+ AND GPL-1+ | review |
| deb | libuuid1:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | libuv1t64:arm64 | 1.48.0-1.1build1 | Expat AND ISC AND CC-BY-4.0 AND Apache-2.0 AND BSD-2-clause AND GPL3+ with autoconf exception | review |
| deb | libv4l-0t64:arm64 | 1.26.1-4build3 | GPL-2 AND LGPL-2.1+ AND BSD-3-clause or GPL-2+ AND GPL-2+ AND FSFULLR AND LGPL AND GPL-3+ AND BSD-3-clause or GPL-2 AND LGPL-2.1 AND BSD-2-clause AND jpeg-group AND LGPL-2+ AND BSD-3-clause AND Expat AND BSD-3-clause or LGPL-2.1 AND HPND-sell-variant | obligations |
| deb | libv4l2rds0t64:arm64 | 1.26.1-4build3 | GPL-2 AND LGPL-2.1+ AND BSD-3-clause or GPL-2+ AND GPL-2+ AND FSFULLR AND LGPL AND GPL-3+ AND BSD-3-clause or GPL-2 AND LGPL-2.1 AND BSD-2-clause AND jpeg-group AND LGPL-2+ AND BSD-3-clause AND Expat AND BSD-3-clause or LGPL-2.1 AND HPND-sell-variant | obligations |
| deb | libv4lconvert0t64:arm64 | 1.26.1-4build3 | GPL-2 AND LGPL-2.1+ AND BSD-3-clause or GPL-2+ AND GPL-2+ AND FSFULLR AND LGPL AND GPL-3+ AND BSD-3-clause or GPL-2 AND LGPL-2.1 AND BSD-2-clause AND jpeg-group AND LGPL-2+ AND BSD-3-clause AND Expat AND BSD-3-clause or LGPL-2.1 AND HPND-sell-variant | obligations |
| deb | libva-drm2:arm64 | 2.20.0-2ubuntu0.2 | Expat AND Expat-advertising AND other AND GPL-2+ | review |
| deb | libva-wayland2:arm64 | 2.20.0-2ubuntu0.2 | Expat AND Expat-advertising AND other AND GPL-2+ | review |
| deb | libva-x11-2:arm64 | 2.20.0-2ubuntu0.2 | Expat AND Expat-advertising AND other AND GPL-2+ | review |
| deb | libva2:arm64 | 2.20.0-2ubuntu0.2 | Expat AND Expat-advertising AND other AND GPL-2+ | review |
| deb | libvdpau1:arm64 | 1.5-2build1 | Expat AND other | review |
| deb | libvidstab1.1:arm64 | 1.1.0-2build1 | GPL-2.0+ | review |
| deb | libvisual-0.4-0:arm64 | 0.4.2-2build1 | LGPL-2.1+ AND LGPL-2+ AND GPL-2+ | obligations |
| deb | libvlc-bin:arm64 | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | libvlc5:arm64 | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | libvlccore9:arm64 | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | libvolume-key1:arm64 | 0.3.12-7build2 | GPL-2 AND MPL-1.1 or GPL-2+ or LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libvte-2.91-0:arm64 | 0.76.0-1ubuntu0.1 | GPL-3+ and LGPL-3+ and Expat AND GPL-3+ and LGPL-3+ AND LGPL-3+ AND GPL-3+ AND Expat | obligations |
| deb | libvte-2.91-common | 0.76.0-1ubuntu0.1 | GPL-3+ and LGPL-3+ and Expat AND GPL-3+ and LGPL-3+ AND LGPL-3+ AND GPL-3+ AND Expat | obligations |
| deb | libvtk9.1t64:arm64 | 9.1.0+really9.1.0+dfsg2-7.1build3 | BSD-3-clause AND BSD-2-clause AND BSL-1 AND Apache-2 AND BSD-like AND Zlib AND Expat AND GPL-2+ AND BSD-3-clause-notice AND MIT AND MIT-exception AND BSD-3-clause-notice-2 AND public-domain | review |
| deb | libwayland-client0:arm64 | 1.22.0-2.1build1 | X11 | review |
| deb | libwayland-cursor0:arm64 | 1.22.0-2.1build1 | X11 | review |
| deb | libwayland-egl1:arm64 | 1.22.0-2.1build1 | X11 | review |
| deb | libwayland-server0:arm64 | 1.22.0-2.1build1 | X11 | review |
| deb | libwbclient0:arm64 | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | libwebkit2gtk-4.1-0:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | libwebkitgtk-6.0-4:arm64 | 2.52.3-0ubuntu0.24.04.1 | BSD-2-clause AND AFL-2.0 or LGPL-2+ AND Apache-2.0 AND BSD-2-Clause-Patent AND BSD-2-clause or BSL-1.0 AND BSD-2-clause or Expat AND LGPL-2.1+ or MPL-1.1 AND BSD-3-clause-adam-barth AND BSD-3-clause-apple AND BSD-3-clause-canon AND BSD-3-clause-code-aurora AND BSD-3-clause-copyright-holder AND BSD-3-clause-ericsson AND BSD-3-clause-google AND BSD-3-clause-jochen-kalmbach AND BSD-3-clause-microsoft AND BSD-3-clause-motorola AND BSD-3-clause-opera AND BSL-1.0 AND Expat AND GPL-2+ or LGPL-2.1+ or MPL-1.1 AND BSD-4-clause-valgrind AND GPL-2+ with Bison exception AND GPL-3+ AND GPL-3+ with Bison exception AND ISC AND LGPL-2 AND LGPL-2.1+ AND LGPL-2+ AND LGPL-2+ or MPL-1.1 AND LGPL-2.1 AND MPL-2.0 AND AFL-2.0 AND GPL-2+ AND MPL-1.1 | obligations |
| deb | libwhoopsie-preferences0 | 23build3 | GPL-3 | review |
| deb | libwhoopsie0:arm64 | 0.2.77ubuntu0.1 | GPL-3 AND Apache-2.0 | review |
| deb | libwmf-0.2-7:arm64 | 0.2.13-1.1build3 | LGPL-2+ AND AGPL-3 with Font exception AND GD AND ISC AND public-domain | obligations |
| deb | libwmf-0.2-7-gtk:arm64 | 0.2.13-1.1build3 | LGPL-2+ AND AGPL-3 with Font exception AND GD AND ISC AND public-domain | obligations |
| deb | libwmf0.2-7-gtk:arm64 | 0.2.13-1.1build3 | LGPL-2+ AND AGPL-3 with Font exception AND GD AND ISC AND public-domain | obligations |
| deb | libwmflite-0.2-7:arm64 | 0.2.13-1.1build3 | LGPL-2+ AND AGPL-3 with Font exception AND GD AND ISC AND public-domain | obligations |
| deb | libwnck-3-0:arm64 | 43.0-3build4 | LGPL-2+ | obligations |
| deb | libwnck-3-common | 43.0-3build4 | LGPL-2+ | obligations |
| deb | libwoff1:arm64 | 1.0.2-2build1 | Expat | review |
| deb | libwww-perl | 6.76-1ubuntu0.1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libwww-robotrules-perl | 6.02-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libx11-6:arm64 | 2:1.8.7-1build1 | UNKNOWN | unknown |
| deb | libx11-data | 2:1.8.7-1build1 | UNKNOWN | unknown |
| deb | libx11-xcb1:arm64 | 2:1.8.7-1build1 | UNKNOWN | unknown |
| deb | libx264-164:arm64 | 2:0.164.3108+git31e19f9-1 | GPL-2+ AND ISC AND GPL-2+ with other exception AND LGPL-2.1+ AND BSD-3-clause AND public-domain AND Expat | obligations |
| deb | libx265-199:arm64 | 3.5-2build1 | GPL-2+ AND Expat AND LGPL-2.1+ AND ISC | obligations |
| deb | libxapian30:arm64 | 1.4.22-1build1 | UNKNOWN | unknown |
| deb | libxapp1:arm64 | 2.8.2-1build3 | LGPL-3 AND GPL-3 AND LGPL-2.1+ AND GPL-2+ | obligations |
| deb | libxau6:arm64 | 1:1.0.9-1build6 | UNKNOWN | unknown |
| deb | libxaw7:arm64 | 2:1.0.14-1build2 | UNKNOWN | unknown |
| deb | libxcb-damage0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-dri3-0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-glx0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-icccm4:arm64 | 0.4.1-1.1build3 | MIT/X Consortium License AND GPL-2+ | review |
| deb | libxcb-image0:arm64 | 0.4.0-2build1 | MIT/X11 AND GPL-2+ | review |
| deb | libxcb-keysyms1:arm64 | 0.4.0-1build4 | MIT/X11 AND GPL-2+ | review |
| deb | libxcb-present0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-randr0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-render-util0:arm64 | 0.3.9-1build4 | MIT/X Consortium License AND GPL-2+ | review |
| deb | libxcb-render0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-res0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-shape0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-shm0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-sync1:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-util1:arm64 | 0.4.0-1build3 | MIT AND GPL-2+ | review |
| deb | libxcb-xfixes0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-xinerama0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-xinput0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-xkb1:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb-xv0:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcb1:arm64 | 1.15-1ubuntu2 | UNKNOWN | unknown |
| deb | libxcomposite1:arm64 | 1:0.4.5-1build3 | UNKNOWN | unknown |
| deb | libxcursor1:arm64 | 1:1.2.1-1build1 | UNKNOWN | unknown |
| deb | libxdamage1:arm64 | 1:1.1.6-1build1 | UNKNOWN | unknown |
| deb | libxdmcp6:arm64 | 1:1.1.3-0ubuntu6 | UNKNOWN | unknown |
| deb | libxerces-c3.2t64:arm64 | 3.2.4+debian-1.2ubuntu2 | xerces-Apache-2.0 AND Apache-2.0 AND permissive-fsf AND GPL-2+ with Autoconf exception AND GPL-3+ with Autoconf exception AND GPL-2+ with Libtool exception AND X11-install-sh AND permissive-configure | review |
| deb | libxext6:arm64 | 2:1.3.4-1build2 | UNKNOWN | unknown |
| deb | libxfce4panel-2.0-4 | 4.18.4-1ubuntu0.1 | GPL-2+ AND LGPL-2.1+ | obligations |
| deb | libxfce4ui-2-0:arm64 | 4.18.4-1build4 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ AND GFDL-1.1+ | obligations |
| deb | libxfce4ui-common | 4.18.4-1build4 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ AND GFDL-1.1+ | obligations |
| deb | libxfce4ui-utils | 4.18.4-1build4 | LGPL-2+ AND LGPL-2.1+ AND GPL-2+ AND GFDL-1.1+ | obligations |
| deb | libxfce4util-common | 4.18.1-2build3 | LGPL-2+ AND GPL-2+ AND This package is free software; you can redistribute it and/or | obligations |
| deb | libxfce4util7:arm64 | 4.18.1-2build3 | LGPL-2+ AND GPL-2+ AND This package is free software; you can redistribute it and/or | obligations |
| deb | libxfconf-0-3:arm64 | 4.18.1-1build3 | GPL-2 AND LGPL-2+ AND GPL-2+ | obligations |
| deb | libxfixes3:arm64 | 1:6.0.0-2build1 | UNKNOWN | unknown |
| deb | libxfont2:arm64 | 1:2.0.6-1build1 | UNKNOWN | unknown |
| deb | libxft2:arm64 | 2.3.6-1build1 | UNKNOWN | unknown |
| deb | libxi6:arm64 | 2:1.8.1-1build1 | UNKNOWN | unknown |
| deb | libxinerama1:arm64 | 2:1.1.4-3build1 | UNKNOWN | unknown |
| deb | libxkbcommon-x11-0:arm64 | 1.6.0-1build1 | UNKNOWN | unknown |
| deb | libxkbcommon0:arm64 | 1.6.0-1build1 | UNKNOWN | unknown |
| deb | libxkbfile1:arm64 | 1:1.1.0-1build4 | UNKNOWN | unknown |
| deb | libxkbregistry0:arm64 | 1.6.0-1build1 | UNKNOWN | unknown |
| deb | libxklavier16:arm64 | 5.4-5build2 | The libxklavier library can be freely distributed under the terms of the | review |
| deb | libxmlb2:arm64 | 0.3.24-1~ubuntu0.24.04.1 | LGPL-2.1+ AND CC0-1.0 | obligations |
| deb | libxmu6:arm64 | 2:1.1.3-3build2 | UNKNOWN | unknown |
| deb | libxmuu1:arm64 | 2:1.1.3-3build2 | UNKNOWN | unknown |
| deb | libxnvctrl0:arm64 | 510.47.03-0ubuntu4.24.04.1 | GPL-2 AND Expat-NVIDIA AND other-MetroLink and other-XFree AND Expat-Precision AND Expat-RedHat AND other-MetroLink AND other-XFree AND Expat AND other-Metrolink | review |
| deb | libxpm4:arm64 | 1:3.5.17-1build2 | UNKNOWN | unknown |
| deb | libxpresent1:arm64 | 1.0.0-2build2 | UNKNOWN | unknown |
| deb | libxrandr2:arm64 | 2:1.5.2-2build1 | UNKNOWN | unknown |
| deb | libxrender1:arm64 | 1:0.9.10-1.1build1 | UNKNOWN | unknown |
| deb | libxres1:arm64 | 2:1.2.1-1build1 | UNKNOWN | unknown |
| deb | libxshmfence1:arm64 | 1.3-1build5 | UNKNOWN | unknown |
| deb | libxslt1.1:arm64 | 1.1.39-0exp1ubuntu0.24.04.3 | UNKNOWN | unknown |
| deb | libxss1:arm64 | 1:1.2.3-1build3 | UNKNOWN | unknown |
| deb | libxt6t64:arm64 | 1:1.2.1-1.2build1 | UNKNOWN | unknown |
| deb | libxtables12:arm64 | 1.8.10-3ubuntu2 | GPL-2 AND Artistic AND GPL-2+ AND custom | review |
| deb | libxtst6:arm64 | 2:1.2.3-1.1build1 | UNKNOWN | unknown |
| deb | libxv1:arm64 | 2:1.0.11-1.1build1 | All Rights Reserved | review |
| deb | libxvidcore4:arm64 | 2:1.3.7-1build1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | libxxf86dga1:arm64 | 2:1.1.5-1build1 | UNKNOWN | unknown |
| deb | libxxf86vm1:arm64 | 1:1.1.4-1build4 | UNKNOWN | unknown |
| deb | libxxhash0:arm64 | 0.8.2-2build1 | BSD-2-clause AND GPL-2+ AND BSD-2-clause or GPL-2+ | review |
| deb | libyaml-0-2:arm64 | 0.2.5-1build1 | Expat AND permissive | review |
| deb | libyaml-tiny-perl | 1.74-1 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | libyelp0:arm64 | 42.2-1ubuntu0.24.04.1 | GPL-2+ AND Apache-2.0 | review |
| deb | libzimg2:arm64 | 3.0.5+ds1-1build1 | WTFPL-2 AND GPL-3+ with AutoConf exception | review |
| deb | libzmq5:arm64 | 4.3.5-1build2 | MPL-2.0 AND MIT AND LGPL-2.0+ | obligations |
| deb | libzstd-dev:arm64 | 1.5.5+dfsg2-2build1.1 | BSD-3-clause or GPL-2 AND zlib AND Expat AND GPL-2 AND BSD-3-clause | review |
| deb | libzstd1:arm64 | 1.5.5+dfsg2-2build1.1 | BSD-3-clause or GPL-2 AND zlib AND Expat AND GPL-2 AND BSD-3-clause | review |
| deb | libzvbi-common | 0.2.42-2 | GPL-2+ AND BSD-2-Clause AND LGPL-2+ AND LGPL-2.1+ AND GPL-2 AND MIT AND GPL-2+ or BSD-3-Clause AND BSD-3-Clause | obligations |
| deb | libzvbi0t64:arm64 | 0.2.42-2 | GPL-2+ AND BSD-2-Clause AND LGPL-2+ AND LGPL-2.1+ AND GPL-2 AND MIT AND GPL-2+ or BSD-3-Clause AND BSD-3-Clause | obligations |
| deb | lightdm | 1.30.0-0ubuntu14 | GPL-3+ AND LGPL-3+ AND GPL-2+ | obligations |
| deb | lightdm-settings | 2.0.1-1 | GPL-3+ AND GPL-2+ | review |
| deb | linux-base | 4.5ubuntu9+24.04.2 | UNKNOWN | unknown |
| deb | linux-dtb-current-sun60iw2 | 1.0.6 | UNKNOWN | unknown |
| deb | linux-image-current-sun60iw2 | 1.0.6 | UNKNOWN | unknown |
| deb | linux-libc-dev:arm64 | 6.8.0-124.124 | UNKNOWN | unknown |
| deb | linux-u-boot-orangepi4pro-current | 1.0.6 | UNKNOWN | unknown |
| deb | lirc | 0.10.2-0.8build1 | GPL-2.0+ AND MIT | review |
| deb | lm-sensors | 1:3.6.0-9build1 | UNKNOWN | unknown |
| deb | locales | 2.39-0ubuntu8.7 | UNKNOWN | unknown |
| deb | login | 1:4.13+dfsg1-4ubuntu3.2 | BSD-3-clause AND GPL-1 AND GPL-2+ AND public-domain | review |
| deb | logrotate | 3.21.0-2build1 | GPL-2 AND GPL-3+ AND BSD-3-Clause | review |
| deb | logsave | 1.47.0-2.4~exp1ubuntu4.1 | GPL-2 AND LGPL-2 AND BSD-3-Clause AND Apache-2 AND ISC AND GPL or MIT-US-export AND Kazlib AND Latex2e AND GPL-2+ with Texinfo exception | obligations |
| deb | lsb-base | 11.6 | GPL-2 AND BSD-3-clause | review |
| deb | lsof | 4.95.0-1build3 | Purdue AND BSD-4-clause AND GPL-2+ AND LGPL-2+ AND sendmail | obligations |
| deb | lto-disabled-list | 47 | GPL-2+ | review |
| deb | lxtask | 0.1.10-2build2 | GPL-2+ | review |
| deb | m4 | 1.4.19-4build1 | UNKNOWN | unknown |
| deb | mailcap | 3.70+nmu1ubuntu1 | ad-hoc AND Bellcore | review |
| deb | make | 4.3-4.1build2 | GPL-3+ | review |
| deb | man-db | 2.12.0-4build2 | GPL-2+ AND GPL-3+ | review |
| deb | manpages | 6.7-2 | GPL-2+ AND LGPL-3.0 with LGPL-3.0-linking exception AND BSD-2-clause AND BSD-3-clause AND BSD-4-clause AND BSD-4-clause and Linux-man-pages-copyleft AND Expat AND GPL-1+ AND GPL-2 AND GPL-2+ and Linux-man-pages-copyleft AND GPL-3 AND Linux-man-pages-1-para AND Linux-man-pages-copyleft AND Linux-man-pages-copyleft-2-para AND Linux-man-pages-copyleft-var | obligations |
| deb | manpages-dev | 6.7-2 | GPL-2+ AND LGPL-3.0 with LGPL-3.0-linking exception AND BSD-2-clause AND BSD-3-clause AND BSD-4-clause AND BSD-4-clause and Linux-man-pages-copyleft AND Expat AND GPL-1+ AND GPL-2 AND GPL-2+ and Linux-man-pages-copyleft AND GPL-3 AND Linux-man-pages-1-para AND Linux-man-pages-copyleft AND Linux-man-pages-copyleft-2-para AND Linux-man-pages-copyleft-var | obligations |
| deb | mawk | 1.3.4.20240123-1build1 | GPL-2.0-only AND X11 AND CC-BY-3.0 | review |
| deb | mc | 3:4.8.30-1ubuntu0.1 | GPL-3+ AND Apache-2.0 AND BSD-3-Clause AND Expat AND GPL-2+ AND FSFULLR AND FSF-Install | review |
| deb | mc-data | 3:4.8.30-1ubuntu0.1 | GPL-3+ AND Apache-2.0 AND BSD-3-Clause AND Expat AND GPL-2+ AND FSFULLR AND FSF-Install | review |
| deb | media-types | 10.1.0 | ad-hoc | review |
| deb | mesa-libgallium:arm64 | 25.2.8-0ubuntu0.24.04.2 | MIT AND GPL-2 AND GPL-2 or MIT AND GPL-1+ AND BSD-3-google AND Khronos AND Apache-2.0 AND BSL AND MLAA AND SGI AND BSD-2-clause AND MIT OR Apache-2.0 AND (MIT OR Apache-2.0) AND Unicode-DFS-2016 AND Apache-2.0 OR MIT AND GPL AND Unicode-DFS-2016 | review |
| deb | mesa-utils | 9.0.0-2 | UNKNOWN | unknown |
| deb | mesa-utils-bin:arm64 | 9.0.0-2 | UNKNOWN | unknown |
| deb | mesa-vulkan-drivers:arm64 | 25.2.8-0ubuntu0.24.04.2 | MIT AND GPL-2 AND GPL-2 or MIT AND GPL-1+ AND BSD-3-google AND Khronos AND Apache-2.0 AND BSL AND MLAA AND SGI AND BSD-2-clause AND MIT OR Apache-2.0 AND (MIT OR Apache-2.0) AND Unicode-DFS-2016 AND Apache-2.0 OR MIT AND GPL AND Unicode-DFS-2016 | review |
| deb | mmc-utils | 0+git20220624.d7b343fd-1ubuntu1 | GPL-2 AND BSD-3-clause | review |
| deb | modemmanager | 1.23.4-0ubuntu2 | GPL-2.0+ AND GPL-3.0+ AND GPL-2.0 AND LGPL-2.0+ | obligations |
| deb | mount | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | mousepad | 0.6.1-1build2 | UNKNOWN | unknown |
| deb | mousetweaks | 3.32.0-4build2 | UNKNOWN | unknown |
| deb | mpv | 0.37.0-1ubuntu4 | LGPL-2.1+ AND ISC AND GPL-2+ AND BSD-2-clause AND BSD-3-clause AND Expat AND CC0-1.0 | obligations |
| deb | mtd-utils | 1:2.2.0-1ubuntu2 | GPL-2+ AND BSD-3-clause AND BSD-2-clause AND unrestricted AND Expat | review |
| deb | mutter-common | 46.2-1ubuntu0.24.04.15 | GPL-2+ and GPL-3+ and LGPL-2+ and LGPL-2.1+ and Expat and NTP-BSD-variant and SGI-B-2.0 AND WRF-BSD-variant AND free-of-known-restrictions AND DEC-BSD-variant and OpenGroup-BSD-variant AND DEC-BSD-variant and OpenGroup-BSD-variant and GPL-2+ AND GPL-2+ AND GPL-3+ AND LGPL-2+ AND LGPL-2.1+ AND Expat AND NTP-BSD-variant AND OpenGroup-BSD-variant AND DEC-BSD-variant AND SGI-B-2.0 | obligations |
| deb | mutter-common-bin | 46.2-1ubuntu0.24.04.15 | GPL-2+ and GPL-3+ and LGPL-2+ and LGPL-2.1+ and Expat and NTP-BSD-variant and SGI-B-2.0 AND WRF-BSD-variant AND free-of-known-restrictions AND DEC-BSD-variant and OpenGroup-BSD-variant AND DEC-BSD-variant and OpenGroup-BSD-variant and GPL-2+ AND GPL-2+ AND GPL-3+ AND LGPL-2+ AND LGPL-2.1+ AND Expat AND NTP-BSD-variant AND OpenGroup-BSD-variant AND DEC-BSD-variant AND SGI-B-2.0 | obligations |
| deb | mysql-common | 5.8+1.1.0build1 | GPL-2+ | review |
| deb | nano | 7.2-2ubuntu0.2 | GPL-3+ AND GFDL-NIV+ or GPL-3+ AND GFDL-NIV+ | review |
| deb | net-tools | 2.10-0.1ubuntu4.4 | GPL-2+ | review |
| deb | netbase | 6.4 | GPL-2 | review |
| deb | netplan-generator | 1.1.2-8ubuntu1~24.04.2 | GPL-3 | review |
| deb | netplan.io | 1.1.2-8ubuntu1~24.04.2 | GPL-3 | review |
| deb | network-manager | 1.46.0-1ubuntu2.7 | GPL-2+ AND LGPL-2.1+ AND GFDL-NIV-1.1+ | obligations |
| deb | network-manager-gnome | 1.34.0-1ubuntu3 | GPL-2+ AND LGPL-2+ | obligations |
| deb | network-manager-openvpn | 1.10.2-4ubuntu0.2 | GPL-2+ AND LGPL-2+ | obligations |
| deb | network-manager-pptp | 1.2.12-3build2 | GPL-2+ AND LGPL-2+ | obligations |
| deb | network-manager-ssh | 1.2.11-1.1build2 | GPL-2+ | review |
| deb | network-manager-vpnc | 1.2.8-7build2 | GPL-2+ AND LGPL-2+ | obligations |
| deb | networkd-dispatcher | 2.2.4-1 | GPL-3+ | review |
| deb | nftables | 1.0.9-1ubuntu0.1 | GPL-2 AND GPL-2+ AND CC-BY-SA-4.0 | review |
| deb | nocache | 1.1-1 | BSD-2-clause AND GPL-3+ or BSD-2-clause AND GPL-3+ | review |
| deb | ntfs-3g | 1:2022.10.3-1.2ubuntu3.1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | numix-gtk-theme | 2.6.7-7 | GPL-3+ | review |
| deb | numix-icon-theme | 0~20231202-1 | GPL-3+ | review |
| deb | numix-icon-theme-circle | 24.04.22-1 | GPL-3.0+ | review |
| deb | openprinting-ppds | 20230202-1 | GPL-2 AND FSFUL AND Expat AND GPL-2+ AND GPL-2.0+OKI AND BSDunspecified | review |
| deb | openssl | 3.0.13-0ubuntu3.11 | UNKNOWN | unknown |
| deb | openvpn | 2.6.19-0ubuntu0.24.04.2 | GPL-2 with OpenSSL exception AND GPL-2+ AND GPL-2 AND BSD-3 AND other AND MIT AND GPL-3+ AND BSD-2 | review |
| deb | orangepi-bsp-cli-orangepi4pro | 1.0.6 | UNKNOWN | unknown |
| deb | orangepi-bsp-desktop-orangepi4pro | 1.0.6 | UNKNOWN | unknown |
| deb | orangepi-config | 1.0.6 | UNKNOWN | unknown |
| deb | orangepi-firmware | 1.0.6 | UNKNOWN | unknown |
| deb | orangepi-jammy-desktop-xfce | 1.0.6 | UNKNOWN | unknown |
| deb | orangepi-plymouth-theme | 1.0.6 | UNKNOWN | unknown |
| deb | orangepi-zsh | 1.0.6 | UNKNOWN | unknown |
| deb | orca | 46.1-1ubuntu1 | LGPL-2.1+ | obligations |
| deb | overlayroot | 0.49~24.04.1 | GPL-3.0+ | review |
| deb | p11-kit | 0.25.3-4ubuntu2.1 | BSD-3-clause AND FSFULLR AND GPL-2+ with Autoconf-data exception AND GPL-3+ with Autoconf-data exception AND X11 AND ISC AND customFSFULLRWD AND Apache-2.0 AND LGPL-2.1+ AND customFSFUL AND FSFAP | obligations |
| deb | p11-kit-modules:arm64 | 0.25.3-4ubuntu2.1 | BSD-3-clause AND FSFULLR AND GPL-2+ with Autoconf-data exception AND GPL-3+ with Autoconf-data exception AND X11 AND ISC AND customFSFULLRWD AND Apache-2.0 AND LGPL-2.1+ AND customFSFUL AND FSFAP | obligations |
| deb | p7zip-full | 16.02+transitional.1 | GPL-2+ | review |
| deb | packagekit | 1.2.8-2ubuntu1.5 | GPL-2+ and LGPL-2.1+ AND GPL-2+ AND LGPL-2.1+ AND FSFAP | obligations |
| deb | packagekit-tools | 1.2.8-2ubuntu1.5 | GPL-2+ and LGPL-2.1+ AND GPL-2+ AND LGPL-2.1+ AND FSFAP | obligations |
| deb | parted | 3.6-4build1 | UNKNOWN | unknown |
| deb | passwd | 1:4.13+dfsg1-4ubuntu3.2 | BSD-3-clause AND GPL-1 AND GPL-2+ AND public-domain | review |
| deb | pasystray | 0.8.2-1build2 | LGPL-2.1+ | obligations |
| deb | patch | 2.7.6-7build3 | UNKNOWN | unknown |
| deb | pavucontrol | 5.0-2build3 | GPL-2+ | review |
| deb | pavucontrol-qt | 1.4.0-0ubuntu6 | GPL-2.0 AND GPL-2.0+ | review |
| deb | pavumeter | 0.9.3-4build5 | GPL-2+ | review |
| deb | pci.ids | 0.0~2024.03.31-1ubuntu0.1 | GPL-2+ or BSD-3-clause AND GPL-2+ AND BSD-3-clause | review |
| deb | pciutils | 1:3.10.0-2build1 | GPL-2+ | review |
| deb | perl | 5.38.2-3.2ubuntu0.3 | GPL-1+ or Artistic AND Expat AND REGCOMP, and GPL-1+ or Artistic AND GPL-3+-WITH-BISON-EXCEPTION AND Unicode AND GPL-1+ or Artistic, and Unicode AND BZIP AND ZLIB AND Artistic AND GPL-2+ or Artistic AND Expat or GPL-1+ or Artistic AND FSFAP AND BSD-3-clause-with-weird-numbering AND CC0-1.0 AND TEXT-TABS AND GPL-1+ or Artistic, and BSD-4-clause-POWERDOG AND GPL-1+ or Artistic, and BSD-3-clause-GENERIC AND BSD-3-clause AND SDBM-PUBLIC-DOMAIN AND DONT-CHANGE-THE-GPL AND GPL-1+ or Artistic or Artistic-dist AND Artistic-dist AND Artistic or GPL-1+ or Artistic-dist AND GPL-1+ or Artistic, and Expat AND LGPL-2.1 AND GPL-1+ AND GPL-2+ AND Artistic-2 AND BSD-4-clause-POWERDOG AND BSD-3-clause-GENERIC AND REGCOMP | obligations |
| deb | perl-base | 5.38.2-3.2ubuntu0.3 | GPL-1+ or Artistic AND Expat AND REGCOMP, and GPL-1+ or Artistic AND GPL-3+-WITH-BISON-EXCEPTION AND Unicode AND GPL-1+ or Artistic, and Unicode AND BZIP AND ZLIB AND Artistic AND GPL-2+ or Artistic AND Expat or GPL-1+ or Artistic AND FSFAP AND BSD-3-clause-with-weird-numbering AND CC0-1.0 AND TEXT-TABS AND GPL-1+ or Artistic, and BSD-4-clause-POWERDOG AND GPL-1+ or Artistic, and BSD-3-clause-GENERIC AND BSD-3-clause AND SDBM-PUBLIC-DOMAIN AND DONT-CHANGE-THE-GPL AND GPL-1+ or Artistic or Artistic-dist AND Artistic-dist AND Artistic or GPL-1+ or Artistic-dist AND GPL-1+ or Artistic, and Expat AND LGPL-2.1 AND GPL-1+ AND GPL-2+ AND Artistic-2 AND BSD-4-clause-POWERDOG AND BSD-3-clause-GENERIC AND REGCOMP | obligations |
| deb | perl-modules-5.38 | 5.38.2-3.2ubuntu0.3 | GPL-1+ or Artistic AND Expat AND REGCOMP, and GPL-1+ or Artistic AND GPL-3+-WITH-BISON-EXCEPTION AND Unicode AND GPL-1+ or Artistic, and Unicode AND BZIP AND ZLIB AND Artistic AND GPL-2+ or Artistic AND Expat or GPL-1+ or Artistic AND FSFAP AND BSD-3-clause-with-weird-numbering AND CC0-1.0 AND TEXT-TABS AND GPL-1+ or Artistic, and BSD-4-clause-POWERDOG AND GPL-1+ or Artistic, and BSD-3-clause-GENERIC AND BSD-3-clause AND SDBM-PUBLIC-DOMAIN AND DONT-CHANGE-THE-GPL AND GPL-1+ or Artistic or Artistic-dist AND Artistic-dist AND Artistic or GPL-1+ or Artistic-dist AND GPL-1+ or Artistic, and Expat AND LGPL-2.1 AND GPL-1+ AND GPL-2+ AND Artistic-2 AND BSD-4-clause-POWERDOG AND BSD-3-clause-GENERIC AND REGCOMP | obligations |
| deb | perl-openssl-defaults:arm64 | 7build3 | Artistic or GPL-1+ AND Artistic AND GPL-1+ | review |
| deb | php-cgi | 2:8.3+93ubuntu2 | Expat | review |
| deb | php-common | 2:93ubuntu2 | Expat | review |
| deb | php-intl | 2:8.3+93ubuntu2 | Expat | review |
| deb | php-json | 2:8.3+93ubuntu2 | Expat | review |
| deb | php-sqlite3 | 2:8.3+93ubuntu2 | Expat | review |
| deb | php-xml | 2:8.3+93ubuntu2 | Expat | review |
| deb | php8.3-cgi | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | php8.3-cli | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | php8.3-common | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | php8.3-intl | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | php8.3-opcache | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | php8.3-readline | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | php8.3-sqlite3 | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | php8.3-xml | 8.3.6-0ubuntu0.24.04.9 | PHP-3.01 AND BSD-TSRM AND BSD-2-clause and LGPL-3+ AND Zend-Engine-2.00 AND BSD-2-clause AND LGPL-2+ AND BSD-2-clause-libmagic AND Expat AND LGPL-2.1 AND BSD-3-clause and PHP-3.01 AND PHP-3.0 AND Apache-2.0 AND GD AND CC0 AND BSD-3-clause AND public-domain AND OpenLDAP AND BSD-4-clause AND LGPL-3+ | obligations |
| deb | pigz | 2.8-1 | This software is provided 'as-is', without any express or implied | obligations |
| deb | pinentry-curses | 1.2.1-3ubuntu5 | GPL-2+ AND GPL-2 AND X11 AND LGPL-3+ or GPL-2+ AND LGPL-3+ | obligations |
| deb | pinentry-gnome3 | 1.2.1-3ubuntu5 | GPL-2+ AND GPL-2 AND X11 AND LGPL-3+ or GPL-2+ AND LGPL-3+ | obligations |
| deb | pipewire:arm64 | 1.0.5-1ubuntu3.2 | Expat and LGPL-2.1+ AND Expat AND BZIP2 AND LGPL-2.1+ AND GPL-2 AND LGPL-2+ and LGPL-2.1+ and Expat AND LGPL-2+ AND FFTPACK | obligations |
| deb | pipewire-bin | 1.0.5-1ubuntu3.2 | Expat and LGPL-2.1+ AND Expat AND BZIP2 AND LGPL-2.1+ AND GPL-2 AND LGPL-2+ and LGPL-2.1+ and Expat AND LGPL-2+ AND FFTPACK | obligations |
| deb | pkexec | 124-2ubuntu1.24.04.3 | LGPL-2.0+ and Expat AND Expat AND Apache-2.0 AND LGPL-2.0+ | obligations |
| deb | pkg-config:arm64 | 1.8.1-2build1 | ISC AND BSD-4 AND BSD-2 AND X11 AND GPL-2+ | review |
| deb | pkgconf:arm64 | 1.8.1-2build1 | ISC AND BSD-4 AND BSD-2 AND X11 AND GPL-2+ | review |
| deb | pkgconf-bin | 1.8.1-2build1 | ISC AND BSD-4 AND BSD-2 AND X11 AND GPL-2+ | review |
| deb | plymouth | 24.004.60-1ubuntu7.1 | GPL-2+ AND other | review |
| deb | plymouth-label | 24.004.60-1ubuntu7.1 | GPL-2+ AND other | review |
| deb | plymouth-theme-spinner | 24.004.60-1ubuntu7.1 | GPL-2+ AND other | review |
| deb | plymouth-themes | 24.004.60-1ubuntu7.1 | GPL-2+ AND other | review |
| deb | policykit-1 | 124-2ubuntu1.24.04.3 | LGPL-2.0+ and Expat AND Expat AND Apache-2.0 AND LGPL-2.0+ | obligations |
| deb | policykit-desktop-privileges | 0.22 | GPL-2+ | review |
| deb | polkitd | 124-2ubuntu1.24.04.3 | LGPL-2.0+ and Expat AND Expat AND Apache-2.0 AND LGPL-2.0+ | obligations |
| deb | poppler-data | 0.4.12-1 | BSD-3-cluase AND MIT AND GPL-2 AND AGPL-3+ | review |
| deb | poppler-utils | 24.02.0-1ubuntu9.9 | GPL-2 or GPL-3 AND Apache-2.0 AND GPL-2 AND GPL-3 | review |
| deb | ppp | 2.4.9-1+1.1ubuntu4 | UNKNOWN | unknown |
| deb | pptp-linux | 1.10.0-1build4 | GPL-2.0+ | review |
| deb | printer-driver-all | 0.20210903 | WTFPL-2 | review |
| deb | printer-driver-hpcups | 3.23.12+dfsg0-0ubuntu5 | GPL-2+ AND BSD-2-clause AND BSD-3-clause AND Expat AND FSFUL AND public-domain AND GPL-2 | review |
| deb | procps | 2:4.0.4-4ubuntu3.2 | LGPL-2.1+ AND LGPL-2.0+ AND GPL-2.0+ | obligations |
| deb | profile-sync-daemon | 6.50-1 | Expat | review |
| deb | proj-data | 9.4.0-1build2 | Expat AND LRUCache11 AND Apache-2.0 AND public-domain AND GPL-3+ with Bison exception AND GPL-2+ | review |
| deb | psmisc | 23.7-1build1 | GPL-2+ | review |
| deb | publicsuffix | 20231001.0357-0.1 | MPL-2.0 AND CC0 | obligations |
| deb | pulseaudio | 1:16.1+dfsg1-2ubuntu10.1 | LGPL-2.1+ AND other AND GPL-2+ AND LGPL-2+ | obligations |
| deb | pulseaudio-module-bluetooth | 1:16.1+dfsg1-2ubuntu10.1 | LGPL-2.1+ AND other AND GPL-2+ AND LGPL-2+ | obligations |
| deb | pulseaudio-utils | 1:16.1+dfsg1-2ubuntu10.1 | LGPL-2.1+ AND other AND GPL-2+ AND LGPL-2+ | obligations |
| deb | pv | 1.8.5-2build1 | GPL-3 AND GPL-2+ | review |
| deb | python-apt-common | 2.7.7ubuntu5.2 | GPL-2+ AND Permissive | review |
| deb | python-is-python3 | 3.11.4-1 | GPL-3.0 | review |
| deb | python3 | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | python3-appdirs | 1.4.4-4 | Expat | review |
| deb | python3-apport | 2.28.1-0ubuntu3.8 | GPL-2+ | review |
| deb | python3-apt | 2.7.7ubuntu5.2 | GPL-2+ AND Permissive | review |
| deb | python3-aptdaemon | 1.1.1+bzr982-0ubuntu44 | GPL-2+ | review |
| deb | python3-aptdaemon.gtk3widgets | 1.1.1+bzr982-0ubuntu44 | GPL-2+ | review |
| deb | python3-attr | 23.2.0-2 | Expat | review |
| deb | python3-bcrypt | 3.2.2-1build1 | Apache-2.0 AND ISC AND BSD-3-Clause AND public-domain AND GPL-3+ | review |
| deb | python3-brlapi:arm64 | 6.6-4ubuntu5 | UNKNOWN | unknown |
| deb | python3-cairo | 1.25.1-2build2 | UNKNOWN | unknown |
| deb | python3-certifi | 2023.11.17-1 | MPL-2 AND GPL-2 | obligations |
| deb | python3-cffi-backend:arm64 | 1.16.0-2build1 | Expat | review |
| deb | python3-chardet | 5.2.0+dfsg-1 | LGPL-2.1+ AND non-given-in-english | obligations |
| deb | python3-colorama | 0.4.6-4 | BSD-3 AND GPL-2+ | review |
| deb | python3-cups:arm64 | 2.0.1-5build6 | GPL-2+ | review |
| deb | python3-cupshelpers | 1.5.18-1ubuntu9 | GPL-2+ | review |
| deb | python3-dbus | 1.3.2-5build3 | Expat AND GPL-2+ or AFL-2.1, and Expat AND AFL-2.1 AND GPL-2+ | review |
| deb | python3-debian | 0.1.49ubuntu2 | GPL-2+ AND GPL-3+ | review |
| deb | python3-defer | 1.0.6-2.1ubuntu1 | GPL-2+ AND MIT | review |
| deb | python3-dev | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | python3-distupgrade | 1:24.04.28 | GPL-2+ AND Expat | review |
| deb | python3-fonttools | 4.46.0-1build2 | Expat AND Apache-2.0 AND OFL-1.1 AND BSD-3-Clause-Adobe AND X11-Unicode AND GPL-2 with font exception or OFL-1.1 AND GPL-2 with font exception | review |
| deb | python3-full | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | python3-gdbm:arm64 | 3.12.3-0ubuntu1 | The following text includes the Python license and licenses and | review |
| deb | python3-gi | 3.48.2-1 | LGPL-2.1+ AND Expat | obligations |
| deb | python3-gi-cairo | 3.48.2-1 | LGPL-2.1+ AND Expat | obligations |
| deb | python3-gpg | 1.18.0-4.1ubuntu4 | LGPL-2.1+ AND LGPL-3+ or GPL-2+ AND GPL-3+ AND GPL-2+ AND LGPL-2+ AND LGPL-3+ | obligations |
| deb | python3-httplib2 | 0.20.4-3 | Expat AND MPL-1.1 or GPL-2+ or LGPL-2.1+ AND BSD-3 AND GPL-3+ AND GPL-2+ AND LGPL-2.1+ AND MPL-1.1 | obligations |
| deb | python3-jwt | 2.7.0-1ubuntu0.1 | Expat | review |
| deb | python3-launchpadlib | 1.11.0-6 | LGPL-3.0 AND LGPL-3.0+ | obligations |
| deb | python3-lazr.restfulclient | 0.14.6-1 | LGPL-3.0 AND LGPL-3.0+ | obligations |
| deb | python3-lazr.uri | 1.0.6-3 | LGPL-3.0 | obligations |
| deb | python3-ldb | 2:2.8.0+samba4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | python3-lib2to3 | 3.12.3-0ubuntu1 | The following text includes the Python license and licenses and | review |
| deb | python3-louis | 3.29.0-1build1 | This package is free software; you can redistribute it and/or AND This package is free software; you can redistribute it and/or modify AND This program is free software: you can redistribute it and/or modify it | review |
| deb | python3-lxml:arm64 | 5.2.1-1 | Copyright (c) 2004 Infrae. All rights reserved. AND GPL2 or later | review |
| deb | python3-lz4 | 4.0.2+dfsg-1build4 | BSD-3-clause AND GPL-2+ or BSD-3-clause AND GPL-2+ | review |
| deb | python3-markdown-it | 3.0.0-2 | expat | review |
| deb | python3-mdurl | 0.1.2-1 | expat | review |
| deb | python3-minimal | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | python3-netplan | 1.1.2-8ubuntu1~24.04.2 | GPL-3 | review |
| deb | python3-opencv:arm64 | 4.6.0+dfsg-13.1ubuntu1 | Apache-2.0 AND BSD-3-Clause AND BSD-3-Clause AND Expat AND BSD-2-Clause AND Apache-2.0 AND GPL-2.0+ AND STEREO_CALIB_PERMISSIVE AND BSD-3-clause AND ISC | review |
| deb | python3-paramiko | 2.12.0-2ubuntu4.1 | LGPL-2.1 | obligations |
| deb | python3-pil:arm64 | 10.2.0-1ubuntu1.2 | UNKNOWN | unknown |
| deb | python3-pil.imagetk:arm64 | 10.2.0-1ubuntu1.2 | UNKNOWN | unknown |
| deb | python3-pip | 24.0+dfsg-1ubuntu1.3 | Expat AND Apache-2.0 AND MPL-2 AND LGPL-2.1+ AND BSD-3 AND Python AND Apache-2.0 OR BSD-2 AND ISC AND BSD-2 | obligations |
| deb | python3-pip-whl | 24.0+dfsg-1ubuntu1.3 | Expat AND Apache-2.0 AND MPL-2 AND LGPL-2.1+ AND BSD-3 AND Python AND Apache-2.0 OR BSD-2 AND ISC AND BSD-2 | obligations |
| deb | python3-problem-report | 2.28.1-0ubuntu3.8 | GPL-2+ | review |
| deb | python3-samba | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | python3-serial | 3.5-2 | UNKNOWN | unknown |
| deb | python3-six | 1.16.0-4 | Expat | review |
| deb | python3-software-properties | 0.99.49.4 | GPL-2+ AND LGPL-3 AND GPL-3 | obligations |
| deb | python3-speechd | 0.12.0~rc2-2build3 | GPL-2+ AND GFDL-NIV-1.2+ or GPL-2+ AND GFDL-NIV-1.2+ AND GPL-3+ with tex exception AND LGPL-2.1+ AND other AND GPL-2+ and public-domain AND public-domain | obligations |
| deb | python3-sympy | 1.12-7 | BSD-3-clause AND GPL-2+ | review |
| deb | python3-talloc:arm64 | 2.4.2-1build2 | LGPL-3.0+ AND PostgreSQL AND ISC AND BSD-3 AND GPL-3.0+ | obligations |
| deb | python3-tdb | 1.4.10-1build1 | LGPL-3.0+ AND GPL-3.0+ AND PostgreSQL AND ISC AND BSD-3 | obligations |
| deb | python3-tk:arm64 | 3.12.3-0ubuntu1 | The following text includes the Python license and licenses and | review |
| deb | python3-tz | 2024.1-2 | Expat | review |
| deb | python3-update-manager | 1:24.04.12 | UNKNOWN | unknown |
| deb | python3-urllib3 | 2.0.7-1ubuntu0.7 | Expat | review |
| deb | python3-venv | 3.12.3-0ubuntu2.1 | UNKNOWN | unknown |
| deb | python3-wadllib | 1.3.6-5 | LGPL-3.0 | obligations |
| deb | python3-wheel | 0.42.0-2 | Expat AND Apache-2.0 or BSD-2-Clause AND GPL-3 AND Apache-2.0 AND BSD-2-Clause | review |
| deb | python3-xapp | 2.4.1-1 | LGPL-2+ | obligations |
| deb | python3-xdg | 0.28-2 | LGPL-2 | obligations |
| deb | python3-xkit | 0.5.0ubuntu6 | UNKNOWN | unknown |
| deb | python3-zipp | 1.0.0-6ubuntu0.1 | Expat | review |
| deb | qalc | 4.9.0-1.1build2 | GPL-2.0-or-later | review |
| deb | qalculate-gtk | 4.9.0-1build3 | GPL-2.0-or-later | review |
| deb | qrencode | 4.1.1-1build2 | LGPL-2.1+ AND public-domain | obligations |
| deb | rake | 13.0.6-3 | Expat | review |
| deb | readline-common | 8.2-4build1 | GPL-3+ AND GPL-2+ AND GFDL-NIV-1.3+ AND ISC-no-attribution AND GPL-3 | review |
| deb | redshift | 1.12-4.2ubuntu4 | GPL-3+ AND FSFAP AND GPL-2+ | review |
| deb | resolvconf | 1.84ubuntu1 | UNKNOWN | unknown |
| deb | rfkill | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | rpcsvc-proto | 1.4.2-0ubuntu7 | BSD-3-clause AND permissive-fsf AND permissive-makefile-in AND permissive-autoconf-m4-no-warranty AND GPL-3+-autoconf-exception AND permissive-configure AND GPL-2+-autoconf-exception AND MIT AND permissive-autoconf-m4 | review |
| deb | rsync | 3.2.7-1ubuntu1.5 | UNKNOWN | unknown |
| deb | rsyslog | 8.2312.0-3ubuntu9.2 | GPL-3.0+ and Apache-2.0 AND LGPL-3.0+ and Apache-2.0 AND BSD-3-clause AND GPL-3.0+ AND Apache-2.0 AND LGPL-3.0+ | obligations |
| deb | ruby | 1:3.2~ubuntu1 | RubyLicense | review |
| deb | ruby-json:arm64 | 2.6.3+dfsg-1build4 | Ruby or GPL-2 AND GPL-2 AND Ruby | review |
| deb | ruby-net-telnet | 0.2.0-1 | Ruby | review |
| deb | ruby-rubygems | 3.4.20-1 | Expat or Custom AND Expat AND Custom | review |
| deb | ruby-xmlrpc | 0.3.2-2 | Ruby | review |
| deb | ruby3.2 | 3.2.3-1ubuntu0.24.04.7 | BSD-2-clause or Ruby AND BSD-2-clause AND SIL-1.1 AND CC-BY-3.0-famfamfam AND Expat AND Expat or Ruby AND PreserveNotice AND 3C-BSD AND PublicDomain AND BSD-3-clause AND AllPermissions AND PartialGplArtisticAndRuby AND zlib/libpng AND GPL-1+ or Artistic AND CC0 AND Unicode AND Permissive AND Artistic AND GPL-1+ AND Ruby | obligations |
| deb | rubygems-integration | 1.18 | Expat | review |
| deb | samba-common | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | samba-common-bin | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | samba-dsdb-modules:arm64 | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | samba-libs:arm64 | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | sbsigntool | 0.9.4-3.1ubuntu7 | GPL-3+ with OpenSSL exception AND GPL-3+ AND LGPL-2+ AND CC0 AND LGPL-3+ AND LGPL-2.1+ AND MIT | obligations |
| deb | screen | 4.9.1-1ubuntu1 | GPL-3+ | review |
| deb | secureboot-db | 1.9build1 | GPL-3+ | review |
| deb | sed | 4.9-2ubuntu0.24.04.1 | GPL-3+ AND X11 AND GFDL-NIV-1.3+ AND GPL-3+ and ISC AND ISC AND BSD-4-clause-UC AND BSL-1 AND pcre | review |
| deb | sensible-utils | 0.0.22 | GPL-2+ AND All-permissive AND configure AND installsh AND BSD-2-clause | review |
| deb | session-migration | 0.3.9build1 | LGPL-3+ | obligations |
| deb | sgml-base | 1.31 | GPL-2+ | review |
| deb | shared-mime-info | 2.4-4 | This package is free software; you can redistribute it and/or modify | review |
| deb | slick-greeter | 2.0.1-1build3 | GPL-3 AND GPL-2+ AND CC-BY-3.0 | review |
| deb | slirp4netns | 1.2.1-1build2 | GPL-2+ AND GPL-2 AND LGPL-2.1 AND Expat or MIT AND MIT AND Expat | obligations |
| deb | smartmontools | 7.4-2build1 | GPL-2+ AND GPL-2 AND LGPL-2.1+ AND Expat-like AND BSD-2-Clause AND BSD-2-Clause and GPL-2+ | obligations |
| deb | smbclient | 2:4.19.5+dfsg-4ubuntu9.6 | GPL-3.0+ AND BSD-3 AND MS-ADSL AND GPL-3 AND LGPL-3.0+ AND PostgreSQL AND ISC | obligations |
| deb | snapd | 2.75.2+ubuntu24.04 | GPL-3 | review |
| deb | software-properties-common | 0.99.49.4 | GPL-2+ AND LGPL-3 AND GPL-3 | obligations |
| deb | software-properties-gtk | 0.99.49.4 | GPL-2+ AND LGPL-3 AND GPL-3 | obligations |
| deb | sound-theme-freedesktop | 0.8-2ubuntu1 | CC-BY-SA-3.0 AND GPL-2+ AND CC-BY-3.0 AND GPL-2 | review |
| deb | speech-dispatcher | 0.12.0~rc2-2build3 | GPL-2+ AND GFDL-NIV-1.2+ or GPL-2+ AND GFDL-NIV-1.2+ AND GPL-3+ with tex exception AND LGPL-2.1+ AND other AND GPL-2+ and public-domain AND public-domain | obligations |
| deb | speech-dispatcher-audio-plugins:arm64 | 0.12.0~rc2-2build3 | GPL-2+ AND GFDL-NIV-1.2+ or GPL-2+ AND GFDL-NIV-1.2+ AND GPL-3+ with tex exception AND LGPL-2.1+ AND other AND GPL-2+ and public-domain AND public-domain | obligations |
| deb | spice-vdagent | 0.22.1-4build3 | GPL-3+ | review |
| deb | sqlite3 | 3.45.1-1ubuntu2.5 | public-domain AND GPL-2+ | review |
| deb | squashfs-tools | 1:4.6.1-1build1 | GPL-2+ | review |
| deb | ssh-import-id | 5.11-0ubuntu2.24.04.1 | GPL-3 | review |
| deb | sshpass | 1.09-1 | GPL-2+ | review |
| deb | strace | 6.8-0ubuntu2 | UNKNOWN | unknown |
| deb | stress | 1.0.7-1 | GPL-2+ AND BSD-3-Clause AND special | review |
| deb | sudo | 1.9.15p5-3ubuntu5.24.04.2 | ISC AND other AND public-domain AND BSD-3-Clause AND BSD-2-Clause AND Zlib AND GPL-2+ | review |
| deb | sunxi-tools | 1.4.2+git20221128.530adf-3 | Expat AND GPL-2+ AND GPL-2 AND public-domain | review |
| deb | sysfsutils | 2.1.1-6build1 | GPL-2+ AND LGPL-2.1+ | obligations |
| deb | sysstat | 12.6.1-2 | GPL-2+ | review |
| deb | system-config-printer | 1.5.18-1ubuntu9 | GPL-2+ | review |
| deb | system-config-printer-common | 1.5.18-1ubuntu9 | GPL-2+ | review |
| deb | systemd | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | systemd-dev | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | systemd-hwe-hwdb | 255.1.7 | GPL-2.0+ | review |
| deb | systemd-resolved | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | systemd-sysv | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | sysvinit-utils | 3.08-6ubuntu3 | GPL-2.0+ AND LGPL-2.1+ AND GPL-3.0 AND GPL-2.0 | obligations |
| deb | tar | 1.35+dfsg-3build1 | GPL-3+ AND GPL-3+ with Bison exception AND LGPL-2.1+ AND LGPL-3+ AND GPL-2+ | obligations |
| deb | tcl | 8.6.14build1 | UNKNOWN | unknown |
| deb | tcl-expect:arm64 | 5.45.4-3 | PD | review |
| deb | tcl8.6 | 8.6.14+dfsg-1build1 | UNKNOWN | unknown |
| deb | terminator | 2.1.3-1 | GPL-2.0 | review |
| deb | thunar | 4.18.8-1build3 | UNKNOWN | unknown |
| deb | thunar-data | 4.18.8-1build3 | UNKNOWN | unknown |
| deb | thunar-volman | 4.18.0-1build2 | GPL-2+ | review |
| deb | toilet | 0.3-1.4build1 | UNKNOWN | unknown |
| deb | toilet-fonts | 0.3-1.4build1 | UNKNOWN | unknown |
| deb | tree | 2.1.1-2ubuntu3.24.04.2 | GPL-2+ AND LGPL-2.1+ | obligations |
| deb | tzdata | 2026a-0ubuntu0.24.04.1 | public-domain AND ICU | review |
| deb | tzdata-legacy | 2026a-0ubuntu0.24.04.1 | public-domain AND ICU | review |
| deb | u-boot-tools | 2025.10-0ubuntu0.24.04.2 | GPL-2.0+ AND GPL-2.0 AND GPL-2.0 OR BSD-2-Clause AND GPL-2.0+ OR MIT AND BSD-3-Clause AND GPL-2.0 OR MIT AND Apache-2.0 OR GPL-2.0+ AND GPL-2.0+ OR BSD-3-Clause AND GPL-2.0+ OR X11 AND GPL-2.0+ OR BSD-2-Clause AND GPL-2.0 OR X11 AND MIT AND GPL-2.0 OR BSD-3-Clause AND Intel AND BSD-2-Clause AND ISC AND BSD-2-Clause-Patent AND LGPL-2.1+ AND Apache-2.0 AND GPL-2.0+ or X11 AND GPL-2.0 WITH Linux-syscall-note EXCEPTION AND GPL-2.0+ or MIT AND CC0-1.0 AND GPL-2.0 or MIT AND BEER-WARE AND eCos-2.0 AND MIT OR BSD-3-Clause AND LGPL-2.1 AND GPL-2.0 or BSD-2-Clause AND BSD-3-Clause OR GPL-2.0+ AND LGPL-2.0+ AND MIT or Unlicense AND Unicode-DFS-2016 AND BSD-3-Clause AND GPL-2.0 AND bzip2-1.0.6 AND GPL-2.0 OR Apache-2.0 AND CC-BY-SA-4.0 AND GPL-2.0+ AND bzip2-1.0.6 AND GPL-2.0 OR IBM-pibs AND GPL-2.0+ and MIT AND BSD-Chromium AND BSD-Facebook AND BSD-lwip AND Permissive-lwip AND X11 AND lwip-long AND lwip-short AND DCO AND BSD-Broadcom AND BSD-chromium AND BSD-HP AND GPL-2.0 WITH Linux-syscall-note exception AND bzlib-BSD-4 AND ecos-2.0 AND IBM-pibs AND Public-Domain AND Unlicense | obligations |
| deb | ubuntu-advantage-desktop-daemon | 1.11ubuntu0.1 | GPL-3.0 | review |
| deb | ubuntu-docs | 24.04.2 | GPL-3+ AND CC-BY-SA-3.0 | review |
| deb | ubuntu-drivers-common | 1:0.9.7.6ubuntu3.7 | GPL-2+ AND BSD-2-clause | review |
| deb | ubuntu-keyring | 2023.11.28.1 | UNKNOWN | unknown |
| deb | ubuntu-mono | 24.04-0ubuntu1 | CC-BY-SA-3.0 AND GPL-3 | review |
| deb | ubuntu-pro-client | 37.2ubuntu~24.04 | GPL-3.0 | review |
| deb | ubuntu-pro-client-l10n | 37.2ubuntu~24.04 | GPL-3.0 | review |
| deb | ubuntu-release-upgrader-core | 1:24.04.28 | GPL-2+ AND Expat | review |
| deb | ubuntu-release-upgrader-gtk | 1:24.04.28 | GPL-2+ AND Expat | review |
| deb | ubuntu-wallpapers | 24.04.2 | CC-BY-SA-3.0 AND CC-BY-SA-2.0 AND CC-BY-2.0 AND CC0 AND CC-BY-SA-4.0 AND Unsplash AND CC-BY-3.0 | review |
| deb | ubuntu-wallpapers-noble | 24.04.2 | CC-BY-SA-3.0 AND CC-BY-SA-2.0 AND CC-BY-2.0 AND CC0 AND CC-BY-SA-4.0 AND Unsplash AND CC-BY-3.0 | review |
| deb | ucf | 3.0043+nmu1 | GPL-2 | review |
| deb | udev | 255.4-1ubuntu8.16 | LGPL-2.1+ AND CC0-1.0 AND GPL-2 with Linux-syscall-note exception AND Expat AND public-domain AND GPL-2+ | obligations |
| deb | udisks2 | 2.10.1-6ubuntu1.3 | GPL-2+ AND LGPL-2+ | obligations |
| deb | unattended-upgrades | 2.9.1+nmu4ubuntu1 | GPL-2+ | review |
| deb | unicode-data | 15.1.0-1 | UNKNOWN | unknown |
| deb | unixodbc-common | 2.3.12-1ubuntu0.24.04.1 | LGPL-2.1+ AND GPL-2+ AND LGPL-2+ AND ppowell | obligations |
| deb | unzip | 6.0-28ubuntu4.1 | UNKNOWN | unknown |
| deb | update-inetd | 4.53 | GPL-2+ | review |
| deb | update-manager | 1:24.04.12 | UNKNOWN | unknown |
| deb | update-manager-core | 1:24.04.12 | UNKNOWN | unknown |
| deb | update-notifier | 3.192.68.2 | UNKNOWN | unknown |
| deb | update-notifier-common | 3.192.68.2 | UNKNOWN | unknown |
| deb | upower | 1.90.3-1 | GPL-2+ AND GFDL-1.1+ | review |
| deb | usb-modeswitch | 2.6.1-3ubuntu3 | GPL-2+ AND BSD-2-clause | review |
| deb | usb-modeswitch-data | 20191128-6 | This package is free software; you can redistribute it and/or modify | review |
| deb | usbmuxd | 1.1.1-5~exp3ubuntu2.1 | GPL-2+ AND LGPL-2.1+ AND GPL-3+ AND LGPL-2+ | obligations |
| deb | usbutils | 1:017-3build1 | This program is free software; you can redistribute it and/or modify | review |
| deb | util-linux | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | uuid-dev:arm64 | 2.39.3-9ubuntu6.5 | GPL-2+ AND GPL-2 AND GPL-3+ AND public-domain AND BSD-4-clause AND MIT AND BSD-3-clause AND BSLA AND LGPL-2+ AND LGPL-2.1+ AND LGPL AND LGPL-3+ | obligations |
| deb | v4l-utils | 1.26.1-4build3 | GPL-2 AND LGPL-2.1+ AND BSD-3-clause or GPL-2+ AND GPL-2+ AND FSFULLR AND LGPL AND GPL-3+ AND BSD-3-clause or GPL-2 AND LGPL-2.1 AND BSD-2-clause AND jpeg-group AND LGPL-2+ AND BSD-3-clause AND Expat AND BSD-3-clause or LGPL-2.1 AND HPND-sell-variant | obligations |
| deb | viewnior | 1.8-3build2 | GPL-3+ AND CC0-1.0 AND GPL-2+ | review |
| deb | vim | 2:9.1.0016-1ubuntu7.15 | Vim AND OPL-1+ AND BSD-3-clause AND Expat AND BSD-2-clause AND Apache or Expat AND GPL-1+ or Artistic-1 AND Vim-Regexp AND UC AND public-domain AND Expat or GPL-2 AND X11 AND Compaq AND GPL-2+ AND Expat or Vim AND XPM AND LGPL-2.1+ AND EDL-1 AND Apache AND GPL-3+ AND GPL-2 AND GPL-1+ AND Artistic-1 | obligations |
| deb | vim-common | 2:9.1.0016-1ubuntu7.15 | Vim AND OPL-1+ AND BSD-3-clause AND Expat AND BSD-2-clause AND Apache or Expat AND GPL-1+ or Artistic-1 AND Vim-Regexp AND UC AND public-domain AND Expat or GPL-2 AND X11 AND Compaq AND GPL-2+ AND Expat or Vim AND XPM AND LGPL-2.1+ AND EDL-1 AND Apache AND GPL-3+ AND GPL-2 AND GPL-1+ AND Artistic-1 | obligations |
| deb | vim-runtime | 2:9.1.0016-1ubuntu7.15 | Vim AND OPL-1+ AND BSD-3-clause AND Expat AND BSD-2-clause AND Apache or Expat AND GPL-1+ or Artistic-1 AND Vim-Regexp AND UC AND public-domain AND Expat or GPL-2 AND X11 AND Compaq AND GPL-2+ AND Expat or Vim AND XPM AND LGPL-2.1+ AND EDL-1 AND Apache AND GPL-3+ AND GPL-2 AND GPL-1+ AND Artistic-1 | obligations |
| deb | vlan | 2.0.5ubuntu5 | GPL-2+ | review |
| deb | vlc | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | vlc-bin | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | vlc-data | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | vlc-plugin-base:arm64 | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | vlc-plugin-qt:arm64 | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | vlc-plugin-video-output:arm64 | 3.0.20-3build6 | GPL-2+ AND LGPL-2.1+ AND BSD-3-clause AND Expat or GPL-2 AND FSFULLR AND Expat AND LGPL-2+ AND GPL-2+ with AutoConf exception AND GPL-3+ with AutoConf exception AND FSFAP AND BSD-2-clause AND BSD-3-clause or GPL-2+ AND WTFPL AND GPL-2 AND Expat or GPL-2+ AND GPL-3+ with Bison exception AND BSD-3-clause and LGPL-2.1 AND ISC AND BSD-2-clause or LGPL-2.1+ AND LGPL-2.1 AND CC0 or GPL-2+ AND CC0 | obligations |
| deb | vpnc | 0.5.3+git20220927-1build2 | GPL-2+ AND BSD-2-clause | review |
| deb | vpnc-scripts | 0.1~git20220510-1 | GPL-2+ | review |
| deb | wamerican | 2020.12.07-2 | UNKNOWN | unknown |
| deb | watchdog | 5.16-1 | UNKNOWN | unknown |
| deb | wbrazilian | 3.0~beta4-25 | GPL-2 AND GPL-3+ | review |
| deb | wbritish | 2020.12.07-2 | UNKNOWN | unknown |
| deb | wfrench | 1.2.7-2 | GPL-2+ | review |
| deb | wget | 1.21.4-1ubuntu4.1 | UNKNOWN | unknown |
| deb | whiptail | 0.52.24-2ubuntu2 | LGPL-2 AND GPL-2+ | obligations |
| deb | whoopsie-preferences | 23build3 | GPL-3 | review |
| deb | wireless-tools | 30~pre9-16.1ubuntu2 | UNKNOWN | unknown |
| deb | wiringpi | 2.58 | UNKNOWN | unknown |
| deb | witalian | 1.10 | GPL-3+ | review |
| deb | wpasupplicant | 2:2.10-21ubuntu0.4 | BSD-3-clause AND BSD-3-clause or GPL-2 AND ISC AND public-domain AND GPL-2 | review |
| deb | wportuguese | 20220621-1 | GPL-2+ or LGPL-2.1+ or MPL-1.1 AND GPL-3+ AND GPL-2+ AND LGPL-2.1+ AND MPL-1.1 | obligations |
| deb | wspanish | 1.0.30 | UNKNOWN | unknown |
| deb | wswiss | 20161207-12 | GPL-2+ AND LGPL-2.1 AND BSD-4-clause and GPL-2+ AND BSD-4-clause | obligations |
| deb | x11-apps | 7.7+11build3 | UNKNOWN | unknown |
| deb | x11-common | 1:7.7+23ubuntu3 | UNKNOWN | unknown |
| deb | x11-utils | 7.7+6build2 | UNKNOWN | unknown |
| deb | x11-xkb-utils | 7.7+8build2 | UNKNOWN | unknown |
| deb | x11-xserver-utils | 7.7+10build2 | UNKNOWN | unknown |
| deb | xapp | 2.2.8-1 | UNKNOWN | unknown |
| deb | xapps-common | 2.8.2-1build3 | LGPL-3 AND GPL-3 AND LGPL-2.1+ AND GPL-2+ | obligations |
| deb | xarchiver | 1:0.5.4.22-1build2 | GPL-2+ AND LGPL-2+ AND LGPL-3+ | obligations |
| deb | xauth | 1:1.1.2-1build1 | UNKNOWN | unknown |
| deb | xbacklight | 1.2.1-1build2 | UNKNOWN | unknown |
| deb | xcursor-themes | 1.0.6-0ubuntu1 | UNKNOWN | unknown |
| deb | xdg-dbus-proxy | 0.1.5-1ubuntu0.2 | LGPL-2.1+ AND LGPL-2+ | obligations |
| deb | xdg-user-dirs | 0.18-1build1 | For everything except xdg-user-dir-lookup.c: | review |
| deb | xdg-user-dirs-gtk | 0.11-1build2 | This package is free software; you can redistribute it and/or | review |
| deb | xdg-utils | 1.1.3-4.1ubuntu3 | Expat | review |
| deb | xfce4 | 4.18 | UNKNOWN | unknown |
| deb | xfce4-appfinder | 4.18.0-1build2 | GPL-2+ | review |
| deb | xfce4-helpers | 4.18.4-0ubuntu3 | GPL-2+ AND LGPL-2+ | obligations |
| deb | xfce4-notifyd | 0.9.4-1 | GPL-2+ | review |
| deb | xfce4-panel | 4.18.4-1ubuntu0.1 | GPL-2+ AND LGPL-2.1+ | obligations |
| deb | xfce4-power-manager | 4.18.3-2build3 | You are free to distribute this software under the terms of | review |
| deb | xfce4-power-manager-data | 4.18.3-2build3 | You are free to distribute this software under the terms of | review |
| deb | xfce4-pulseaudio-plugin:arm64 | 0.4.8-1build2 | GPL-2.0+ | review |
| deb | xfce4-screenshooter | 1.10.5-1build1 | UNKNOWN | unknown |
| deb | xfce4-session | 4.18.3-1build2 | GPL AND GPL-2 AND GPL-2+ AND LGPL-2+ AND MIT/X11 (BSD like) GPL AND You are free to distribute this software under the terms of | obligations |
| deb | xfce4-settings | 4.18.4-0ubuntu3 | GPL-2+ AND LGPL-2+ | obligations |
| deb | xfce4-terminal | 1.1.3-1build1 | GPL-2+ AND LGPL-2+ | obligations |
| deb | xfconf | 4.18.1-1build3 | GPL-2 AND LGPL-2+ AND GPL-2+ | obligations |
| deb | xfdesktop4 | 4.18.1-1build3 | GPL-2+ | review |
| deb | xfdesktop4-data | 4.18.1-1build3 | GPL-2+ | review |
| deb | xfonts-100dpi | 1:1.0.5 | UNKNOWN | unknown |
| deb | xfonts-75dpi | 1:1.0.5 | UNKNOWN | unknown |
| deb | xfonts-base | 1:1.0.5+nmu1 | UNKNOWN | unknown |
| deb | xfonts-encodings | 1:1.0.5-0ubuntu2 | UNKNOWN | unknown |
| deb | xfonts-scalable | 1:1.0.3-1.3 | UNKNOWN | unknown |
| deb | xfonts-utils | 1:7.7+6build3 | UNKNOWN | unknown |
| deb | xfwm4 | 4.18.0-1build3 | GPL AND LGPL AND GPL-2+ | obligations |
| deb | xkb-data | 2.41-2ubuntu1.1 | UNKNOWN | unknown |
| deb | xml-core | 0.19 | GPL-2+ | review |
| deb | xorg-docs-core | 1:1.7.1-1.2 | UNKNOWN | unknown |
| deb | xscreensaver | 6.08+dfsg1-1ubuntu3 | Other_1 AND Other_1b AND Other_1c AND Other_2 AND Other_3 AND Other_4 AND Other_5 AND X11 AND Other_6 AND Other_7 AND GPL-2+ AND Other_8 AND Other_9 AND MIT AND public-domain | review |
| deb | xscreensaver-data | 6.08+dfsg1-1ubuntu3 | Other_1 AND Other_1b AND Other_1c AND Other_2 AND Other_3 AND Other_4 AND Other_5 AND X11 AND Other_6 AND Other_7 AND GPL-2+ AND Other_8 AND Other_9 AND MIT AND public-domain | review |
| deb | xserver-common | 2:21.1.12-1ubuntu1.6 | UNKNOWN | unknown |
| deb | xserver-xorg | 1:7.7+23ubuntu3 | UNKNOWN | unknown |
| deb | xserver-xorg-core | 2:21.1.12-1ubuntu1.6 | UNKNOWN | unknown |
| deb | xserver-xorg-input-all | 1:7.7+23ubuntu3 | UNKNOWN | unknown |
| deb | xserver-xorg-video-fbdev | 1:0.5.0-2build2 | UNKNOWN | unknown |
| deb | xxd | 2:9.1.0016-1ubuntu7.15 | Vim AND OPL-1+ AND BSD-3-clause AND Expat AND BSD-2-clause AND Apache or Expat AND GPL-1+ or Artistic-1 AND Vim-Regexp AND UC AND public-domain AND Expat or GPL-2 AND X11 AND Compaq AND GPL-2+ AND Expat or Vim AND XPM AND LGPL-2.1+ AND EDL-1 AND Apache AND GPL-3+ AND GPL-2 AND GPL-1+ AND Artistic-1 | obligations |
| deb | xz-utils | 5.6.1+really5.4.5-1ubuntu0.3 | Different licenses apply to different files in this package. Here AND PD AND probably-PD AND GPL-2+ AND LGPL-2.1+ AND permissive-fsf AND Autoconf AND permissive-nowarranty AND GPL-2 AND none AND config-h AND noderivs AND PD-debian | obligations |
| deb | yelp | 42.2-1ubuntu0.24.04.1 | GPL-2+ AND Apache-2.0 | review |
| deb | yelp-xsl | 42.1-2ubuntu0.24.04.1 | LGPL-2+ AND GPL-2+ AND BSD-3-clause | obligations |
| deb | zip | 3.0-13ubuntu0.2 | UNKNOWN | unknown |
| deb | zsh | 5.9-6ubuntu2 | Zsh AND Expat AND BSD-3 AND GPL-2+ AND GPL-2 AND Artistic or GPL-1+ or Zsh AND PWS-Zsh-FAQ AND GPL-1+ AND Artistic | review |
| deb | zsh-common | 5.9-6ubuntu2 | Zsh AND Expat AND BSD-3 AND GPL-2+ AND GPL-2 AND Artistic or GPL-1+ or Zsh AND PWS-Zsh-FAQ AND GPL-1+ AND Artistic | review |
| deb | zstd | 1.5.5+dfsg2-2build1.1 | BSD-3-clause or GPL-2 AND zlib AND Expat AND GPL-2 AND BSD-3-clause | review |

## Evidence and Policy

- Python evidence comes from installed distribution metadata and hashes of installed LICENSE/COPYING/NOTICE files.
- npm evidence comes from the committed lockfile, including package integrity values.
- Runtime-tool evidence is captured from the actual executable on the machine generating this report.
- Copyleft does not automatically mean prohibited; distribution model and obligations must be reviewed.
- Codec patent/licensing questions are separate from open-source copyright licenses.
