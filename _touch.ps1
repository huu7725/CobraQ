# Trigger WatchFiles reload by touching router.py
$file = "d:\CobraQ\backend\app\api\router.py"
(Get-Item $file).LastWriteTime = (Get-Date)
Write-Host "Touched router.py"
