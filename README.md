# LumaEXR Viewer

โปรแกรมนี้เป็นตัวดูไฟล์ `.exr` / `.hdr` แบบง่าย

มีแค่ 3 อย่าง:

- เปิดไฟล์ EXR
- ปรับ `Exposure` เพื่อดูภาพ HDR บนจอปกติ
- บันทึกภาพ preview ออกเป็น JPG

## Install

```powershell
pip install -r .\requirements.txt
```

สำหรับ build `.exe`:

```powershell
pip install pyinstaller
.\build_exe.bat
```

ไฟล์ที่ได้จะอยู่ที่ `dist\LumaEXR-Viewer.exe`

## Rocky 9 RPM

บน Rocky Linux 9 แนะนำให้ build บนเครื่อง Rocky 9 เอง แล้วค่อยแพ็กเป็น `.rpm`

ติดตั้ง dependency:

```bash
sudo dnf install -y python3 python3-pip python3-tkinter rpm-build
pip3 install -r requirements.txt
pip3 install pyinstaller
```

build binary + RPM:

```bash
chmod +x packaging/linux/build_rpm.sh
chmod +x packaging/linux/lumaexr-viewer
./packaging/linux/build_rpm.sh
```

ถ้าสำเร็จ ไฟล์ `.rpm` จะอยู่ใน `rpm-build/RPMS/`

## Run

```powershell
python .\luma_exr_viewer.py
```

เปิดไฟล์ตัวอย่างทันที:

```powershell
python .\luma_exr_viewer.py .\test_hdr\3L5A0661_2025-11-06_20-52-54_Sphere_hdr.exr
```

## Note

- สคริปต์ตั้งค่า `OPENCV_IO_ENABLE_OPENEXR=1` ให้อัตโนมัติ
- ใช้ `opencv-python`, `numpy`, `Pillow`, และ `tkinter`
