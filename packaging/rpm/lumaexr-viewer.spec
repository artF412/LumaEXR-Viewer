Name:           lumaexr-viewer
Version:        1.0
Release:        1%{?dist}
Summary:        OpenEXR HDR viewer with exposure, zoom, and JPG export

License:        Proprietary
URL:            https://github.com/artF412/LumaEXR-Viewer
Source0:        %{name}-%{version}.tar.gz

BuildArch:      x86_64

%description
LumaEXR Viewer is a desktop viewer for EXR/HDR images with exposure control,
zoom, panning, despeckle, highlight clamping, and JPG export.

This RPM installs a prebuilt Linux binary that should be created on Rocky Linux 9
with PyInstaller before packaging.

%prep
%autosetup -n %{name}-%{version}

%build
# Nothing to build here. The binary must already exist in the source tarball.

%install
install -d %{buildroot}/opt/%{name}
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_datadir}/applications
install -d %{buildroot}%{_datadir}/icons/hicolor/256x256/apps

install -m 0755 dist/LumaEXR-Viewer %{buildroot}/opt/%{name}/LumaEXR-Viewer
install -m 0755 packaging/linux/lumaexr-viewer %{buildroot}%{_bindir}/lumaexr-viewer
install -m 0644 packaging/linux/lumaexr-viewer.desktop %{buildroot}%{_datadir}/applications/lumaexr-viewer.desktop
install -m 0644 assets/app_icon.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/lumaexr-viewer.png

%files
%license
%doc README.md
%{_bindir}/lumaexr-viewer
/opt/%{name}/LumaEXR-Viewer
%{_datadir}/applications/lumaexr-viewer.desktop
%{_datadir}/icons/hicolor/256x256/apps/lumaexr-viewer.png

%changelog
* Tue Mar 18 2026 Codex <codex@example.com> - 1.0-1
- Initial RPM packaging for Rocky Linux 9
