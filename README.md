# LumaEXR Viewer

โปรแกรมนี้เป็นตัวดูไฟล์ `.exr` / `.hdr` แบบง่าย

มีแค่ 3 อย่าง:

- เปิดไฟล์ EXR
- ปรับ `Exposure` เพื่อดูภาพ HDR บนจอปกติ
- บันทึกภาพ preview ออกเป็น JPG

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
