#!/bin/bash
# Build a pinned Ubuntu 24.04 (Noble) variant of the OrangePi 4 Pro base image
# by replicating, via chroot + apt, the same jammy->noble transition already
# proven stable for months on TL-C87FF9587CA0 (which used the OS's own
# do-release-upgrade on 2026-02-27, per /var/log/dist-upgrade/20260227-1848).
#
# We use the manual apt sources-list-swap + full-upgrade method instead of
# do-release-upgrade itself, because do-release-upgrade expects a live system
# (systemd/dbus running) and is known to be unreliable inside a chroot with
# no init process. The manual method is the standard, documented way to do
# offline/image-based release upgrades and is what do-release-upgrade itself
# does under the hood at the package-manager level.
#
# Runs entirely inside a --privileged Docker container against a COPY of the
# cached base image. Never touches the original cached file or any live device.
#
# Usage (from repo root; needs the orangepi4pro base already cached — see
# headend/tools/hardware/orangepi4pro/target.yaml — and an arm64 Docker host,
# e.g. Apple Silicon, so the chroot needs no qemu-user-static emulation):
#
#   docker run --rm --privileged \
#     -v "$PWD/.base_image_cache/orangepi4pro:/img:ro" \
#     -v "$PWD/headend/tools/hardware/orangepi4pro-noble:/script:ro" \
#     -v "$PWD/.base_image_cache/orangepi4pro-noble-build:/work" \
#     ubuntu:22.04 bash -c "
#       apt-get update -qq && apt-get install -y -qq util-linux e2fsprogs kpartx parted ca-certificates
#       bash /script/build_noble_base.sh
#     "
#
# Output: /work/orangepi4pro-noble.img (~9.4G raw). Compress with
# `xz -6 -T0 -k orangepi4pro-noble.img`, sha256sum the .xz, and copy both
# into .base_image_cache/orangepi4pro-noble/ with the filenames declared in
# this directory's target.yaml before the generator can use the new base.
set -euxo pipefail

IMG_SRC=/img/orangepi4pro-image.img
WORK=/work
IMG=$WORK/orangepi4pro-noble.img
MNT=/mnt/rootfs

echo "### 1. Copy base image (never mutate the cached original) ###"
# Always start from a pristine copy of the source, never reuse a leftover
# working copy from a prior aborted attempt: a previous run can fail
# mid-dpkg-unpack (half-configured packages, mixed old/new library versions)
# without changing the working file's SIZE, so a same-size reuse check can't
# tell "pristine" apart from "broken partial upgrade" — and building further
# on top of a broken partial upgrade produces confusing, unrelated-looking
# dependency errors (this bit us once already).
mkdir -p "$WORK" "$MNT"
rm -f "$IMG"
cp "$IMG_SRC" "$IMG"
df -h "$WORK"

echo "### 1b. Grow the working image — the vendor .img's 3.4G partition is sized"
echo "### for a minimal Jammy SD-card seed image, not for holding a full"
echo "### jammy->noble transition's temp space (825 packages churned, both old"
echo "### and new copies briefly coexist on disk during dpkg unpack). On real"
echo "### hardware this never matters because nand-sata-install migrates the"
echo "### rootfs to a big NVMe before anyone dist-upgrades it — but for this"
echo "### chroot build we need the headroom up front. +6G is generous slack;"
echo "### we do NOT shrink back afterward (simpler/safer, and a slightly"
echo "### bigger flashable SD seed image is a non-issue in practice)."
truncate -s +6G "$IMG"
parted -s "$IMG" resizepart 1 100%
df -h "$WORK"

echo "### 2. Loop-attach + mount the single ext4 partition ###"
LOOPDEV=$(losetup -fP --show "$IMG")
echo "loop device: $LOOPDEV"
partprobe "$LOOPDEV" 2>&1 || true
udevadm settle 2>&1 || true
sleep 2
if [ ! -e "${LOOPDEV}p1" ]; then
  echo "partition node ${LOOPDEV}p1 missing, trying kpartx"
  kpartx -av "$LOOPDEV"
  sleep 1
  PARTDEV="/dev/mapper/$(basename "$LOOPDEV")p1"
else
  PARTDEV="${LOOPDEV}p1"
fi
echo "partition device: $PARTDEV"
e2fsck -fy "$PARTDEV" || true
resize2fs "$PARTDEV"
mount "$PARTDEV" "$MNT"
df -h "$MNT"

cleanup() {
  set +e
  echo "### cleanup ###"
  umount "$MNT/dev/pts" 2>/dev/null
  umount "$MNT/dev" 2>/dev/null
  umount "$MNT/proc" 2>/dev/null
  umount "$MNT/sys" 2>/dev/null
  umount "$MNT" 2>/dev/null
  kpartx -d "$LOOPDEV" 2>/dev/null
  losetup -d "$LOOPDEV" 2>/dev/null
}
trap cleanup EXIT

echo "### 3. Verify starting state ###"
cat "$MNT/etc/os-release" | head -3
grep -h "" "$MNT"/etc/apt/sources.list.d/*.sources 2>/dev/null | head -5 || cat "$MNT/etc/apt/sources.list" | head -10

echo "### 4. Hold the vendor kernel/u-boot/dtb packages so the upgrade cannot touch them ###"
chroot "$MNT" bash -c "dpkg -l | grep -E 'linux-image-current-sun60iw2|linux-dtb-current-sun60iw2|linux-u-boot-orangepi4pro-current'"
chroot "$MNT" apt-mark hold linux-image-current-sun60iw2 linux-dtb-current-sun60iw2 linux-u-boot-orangepi4pro-current
chroot "$MNT" apt-mark showhold

echo "### 5. Bind mounts + resolv.conf + block service (re)starts inside chroot ###"
mount --bind /dev "$MNT/dev"
mount --bind /dev/pts "$MNT/dev/pts"
mount -t proc proc "$MNT/proc"
mount -t sysfs sysfs "$MNT/sys"
cp -L /etc/resolv.conf "$MNT/etc/resolv.conf"
cat > "$MNT/usr/sbin/policy-rc.d" <<'EOF'
#!/bin/sh
exit 101
EOF
chmod +x "$MNT/usr/sbin/policy-rc.d"

export DEBIAN_FRONTEND=noninteractive

echo "### 6. jammy -> noble sources swap ###"
if [ -d "$MNT/etc/apt/sources.list.d" ] && ls "$MNT"/etc/apt/sources.list.d/*.sources >/dev/null 2>&1; then
  sed -i 's/jammy/noble/g' "$MNT"/etc/apt/sources.list.d/*.sources
fi
if [ -f "$MNT/etc/apt/sources.list" ]; then
  sed -i 's/jammy/noble/g' "$MNT/etc/apt/sources.list"
fi
{ grep -rh "^URIs\|^deb " "$MNT"/etc/apt/sources.list.d/*.sources "$MNT/etc/apt/sources.list" 2>/dev/null || true; } | head -10

echo "### 7. apt-get update against noble ###"
chroot "$MNT" apt-get update

echo "### 8. full-upgrade (this is the actual jammy->noble package transition) ###"
# --force-confdef/--force-confold: keep OrangePi's vendor-modified conffiles
# (journald.conf etc.) over the incoming Debian-maintainer defaults, same
# choice a human would make by pressing Enter at the interactive prompt
# ("default action is to keep your current version") — DEBIAN_FRONTEND alone
# does not suppress these conffile prompts, only package debconf prompts.
chroot "$MNT" apt-get -y --allow-downgrades --allow-remove-essential --allow-change-held-packages \
  -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
  full-upgrade || {
  echo "!!! full-upgrade failed, dumping dpkg status for diagnosis !!!"
  chroot "$MNT" dpkg --audit || true
  exit 1
}

echo "### 9. cleanup obsolete packages ###"
chroot "$MNT" apt-get -y autoremove --purge
chroot "$MNT" apt-get clean

echo "### 10. sanity checks ###"
cat "$MNT/etc/os-release"
chroot "$MNT" bash -c "dpkg -l | grep -E 'linux-image-current-sun60iw2|linux-dtb-current-sun60iw2|linux-u-boot-orangepi4pro-current'"
chroot "$MNT" ldd --version | head -1
chroot "$MNT" dpkg --audit && echo "dpkg --audit: clean" || echo "dpkg --audit: ISSUES FOUND (see above)"
chroot "$MNT" apt-get check && echo "apt-get check: clean"
rm -f "$MNT/usr/sbin/policy-rc.d"

echo "### DONE — see cleanup trap for unmount ###"
