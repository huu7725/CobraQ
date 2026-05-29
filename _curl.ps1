$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http
$handler = New-Object System.Net.Http.HttpClientHandler
$client = New-Object System.Net.Http.HttpClient($handler)
$client.Timeout = [TimeSpan]::FromSeconds(5)
try {
    $response = $client.GetAsync("http://127.0.0.1:8000/api/stats").Result
    $content = $response.Content.ReadAsStringAsync().Result
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Body: $content"
} catch {
    Write-Host "Error: $_"
}
