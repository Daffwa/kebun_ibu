# Mendaftarkan tarik_harian.py + run.py ke Windows Task Scheduler (laptop).
# Jalankan sekali: powershell -ExecutionPolicy Bypass -File data-science\daftar_tugas_harian.ps1
# Hapus lagi:      Unregister-ScheduledTask -TaskName "KebunIbu-TarikHarian" -Confirm:$false

$dasar = $PSScriptRoot
$pythonw = Join-Path $dasar ".venv\Scripts\pythonw.exe"

# Aksi dijalankan berurutan (aksi berikutnya tetap jalan walau yang sebelumnya gagal):
# tarik dulu, salin hasil VPS (data_lake_vps\), lalu muat hari ini ke gudang DuckDB.
# Muat ulang aman: run.py mengganti data (sumber, tanggal) yang sama, jadi 12:00 hanya menimpa.
$aksi = @(
    New-ScheduledTaskAction -Execute $pythonw `
        -Argument ('"' + (Join-Path $dasar "tarik_harian.py") + '"') -WorkingDirectory $dasar
    New-ScheduledTaskAction -Execute $pythonw `
        -Argument ('"' + (Join-Path $dasar "sinkron_vps.py") + '"') -WorkingDirectory $dasar
    New-ScheduledTaskAction -Execute $pythonw `
        -Argument ('"' + (Join-Path $dasar "run.py") + '" --tahap transform,load') -WorkingDirectory $dasar
)

# 06:00 tarikan utama; 12:00 hanya mengulang sumber yang pagi tadi gagal (yang sukses dilewati).
$pemicu = @(
    New-ScheduledTaskTrigger -Daily -At "06:00"
    New-ScheduledTaskTrigger -Daily -At "12:00"
)

$aturan = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "KebunIbu-TarikHarian" `
    -Description "Tarik harga buah Blibli + Tokopedia, salin hasil VPS, lalu muat ke gudang (tarik_harian.py, sinkron_vps.py, run.py)" `
    -Action $aksi -Trigger $pemicu -Settings $aturan -Force
