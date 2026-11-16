# Mendaftarkan tarik_harian.py + sinkron_vps.py + run.py + kirim_supabase.py ke Windows Task Scheduler (laptop).
# Jalankan sekali: powershell -ExecutionPolicy Bypass -File data-science\daftar_tugas_harian.ps1
# Hapus lagi:      Unregister-ScheduledTask -TaskName "KebunIbu-TarikHarian" -Confirm:$false

$dasar = $PSScriptRoot
$pythonw = Join-Path $dasar ".venv\Scripts\pythonw.exe"

# Aksi dijalankan berurutan (aksi berikutnya tetap jalan walau yang sebelumnya gagal):
# tarik dulu, salin hasil VPS (data_lake_vps\), muat hari ini ke gudang DuckDB, lalu kirim ke Supabase.
# Muat ulang aman: run.py mengganti data (sumber, tanggal) yang sama, jadi 12:00 hanya menimpa.
$aksi = @(
    New-ScheduledTaskAction -Execute $pythonw `
        -Argument ('"' + (Join-Path $dasar "tarik_harian.py") + '"') -WorkingDirectory $dasar
    New-ScheduledTaskAction -Execute $pythonw `
        -Argument ('"' + (Join-Path $dasar "sinkron_vps.py") + '"') -WorkingDirectory $dasar
    New-ScheduledTaskAction -Execute $pythonw `
        -Argument ('"' + (Join-Path $dasar "run.py") + '" --tahap transform,load') -WorkingDirectory $dasar
    # Kirim tanggal yang berubah ke Supabase (dashboard Manalagi). 12:00 biasanya mengirim 0 tanggal.
    New-ScheduledTaskAction -Execute $pythonw `
        -Argument ('"' + (Join-Path $dasar "kirim_supabase.py") + '"') -WorkingDirectory $dasar
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
    -Description "Tarik harga buah Blibli + Tokopedia, salin hasil VPS, muat ke gudang, lalu kirim dashboard Manalagi ke Supabase (tarik_harian.py, sinkron_vps.py, run.py, kirim_supabase.py)" `
    -Action $aksi -Trigger $pemicu -Settings $aturan -Force
