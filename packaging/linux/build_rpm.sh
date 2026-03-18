#!/usr/bin/env bash
set -euo pipefail

APP_NAME="lumaexr-viewer"
APP_VERSION="1.0"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_ROOT="${ROOT_DIR}/rpm-build"
PYINSTALLER_NAME="LumaEXR-Viewer"
TARBALL_NAME="${APP_NAME}-${APP_VERSION}.tar.gz"

cd "${ROOT_DIR}"

rm -rf build dist "${BUILD_ROOT}"

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onefile \
  --name "${PYINSTALLER_NAME}" \
  --icon assets/app_icon.png \
  luma_exr_viewer.py

mkdir -p "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}"
mkdir -p "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/dist"
mkdir -p "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/assets"
mkdir -p "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/packaging/linux"
mkdir -p "${BUILD_ROOT}/SPECS"

cp dist/${PYINSTALLER_NAME} "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/dist/"
cp README.md "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/"
cp assets/app_icon.png "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/assets/" 2>/dev/null || true
cp packaging/linux/lumaexr-viewer "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/packaging/linux/"
cp packaging/linux/lumaexr-viewer.desktop "${BUILD_ROOT}/SOURCES/${APP_NAME}-${APP_VERSION}/packaging/linux/"

tar -C "${BUILD_ROOT}/SOURCES" -czf "${BUILD_ROOT}/SOURCES/${TARBALL_NAME}" "${APP_NAME}-${APP_VERSION}"
cp packaging/rpm/lumaexr-viewer.spec "${BUILD_ROOT}/SPECS/"

rpmbuild \
  --define "_topdir ${BUILD_ROOT}" \
  -ba "${BUILD_ROOT}/SPECS/lumaexr-viewer.spec"

echo
echo "RPM output:"
find "${BUILD_ROOT}/RPMS" -type f -name "*.rpm"
