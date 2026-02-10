# PyPI Authentication Test Script - Mimics K6 behavior
# Usage: .\test-pypi-auth.ps1 -Url "https://artifactory.example.com/artifactory/api/pypi/pypi-remote/simple/joblib/" -Username "myuser" -Password "your-password"

param(
    [Parameter(Mandatory=$true)]
    [string]$Url,
    
    [Parameter(Mandatory=$false)]
    [string]$Username = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Password = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Token = "",
    
    [switch]$Verbose
)

function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "PyPI Authentication Test - K6 Compatible" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Prepare headers matching K6 getPypiAuthHeaders() function
$headers = @{
    'User-Agent' = 'pip/23.0 CPython/3.11.0'
    'Accept' = '*/*'
}

# Encode credentials (matching K6 encoding.b64encode behavior)
if ($Token -ne "") {
    Write-Host "Authentication: Token-based (Basic auth with __token__:TOKEN)" -ForegroundColor Yellow
    $credString = "__token__:$Token"
    $credBytes = [System.Text.Encoding]::UTF8.GetBytes($credString)
    $credB64 = [System.Convert]::ToBase64String($credBytes)
    $headers['Authorization'] = "Basic $credB64"
    
    if ($Verbose) {
        Write-Host "  Credential string: __token__:<TOKEN>" -ForegroundColor Gray
        Write-Host "  Base64: $credB64" -ForegroundColor Gray
    }
}
elseif ($Username -ne "" -and $Password -ne "") {
    Write-Host "Authentication: Username/Password (Basic auth)" -ForegroundColor Yellow
    $credString = "${Username}:${Password}"
    $credBytes = [System.Text.Encoding]::UTF8.GetBytes($credString)
    $credB64 = [System.Convert]::ToBase64String($credBytes)
    $headers['Authorization'] = "Basic $credB64"
    
    if ($Verbose) {
        Write-Host "  Credential string: ${Username}:<PASSWORD>" -ForegroundColor Gray
        Write-Host "  Base64: $credB64" -ForegroundColor Gray
    }
}
else {
    Write-Host "WARNING: No authentication provided. Use -Username/-Password or -Token" -ForegroundColor Red
}

Write-Host ""
Write-Host "Request Details:" -ForegroundColor Green
Write-Host "  URL: $Url" -ForegroundColor White
Write-Host ""
Write-Host "  Headers:" -ForegroundColor White
foreach ($key in $headers.Keys) {
    if ($key -eq 'Authorization') {
        Write-Host "    $key: Basic <base64_credentials>" -ForegroundColor White
    }
    else {
        Write-Host "    ${key}: $($headers[$key])" -ForegroundColor White
    }
}
Write-Host ""

# Make the request
try {
    Write-Host "Sending request..." -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri $Url -Headers $headers -Method GET -UseBasicParsing -ErrorAction Stop
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host "SUCCESS - Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Response Headers:" -ForegroundColor Green
    foreach ($key in $response.Headers.Keys) {
        Write-Host "  ${key}: $($response.Headers[$key])" -ForegroundColor White
    }
    
    Write-Host ""
    Write-Host "Response Body (first 500 chars):" -ForegroundColor Green
    $body = $response.Content
    if ($body.Length -gt 500) {
        Write-Host $body.Substring(0, 500) -ForegroundColor White
        Write-Host "..." -ForegroundColor Gray
    }
    else {
        Write-Host $body -ForegroundColor White
    }
    
    Write-Host ""
    Write-Host "✓ Authentication successful!" -ForegroundColor Green
    exit 0
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Red
    Write-Host "FAILED - Status: $statusCode" -ForegroundColor Red
    Write-Host "=" * 80 -ForegroundColor Red
    Write-Host ""
    
    if ($statusCode -eq 401) {
        Write-Host "❌ 401 UNAUTHORIZED - Authentication failed" -ForegroundColor Red
        Write-Host ""
        Write-Host "Possible issues:" -ForegroundColor Yellow
        Write-Host "  1. Wrong username or password" -ForegroundColor White
        Write-Host "  2. Credentials not properly base64 encoded" -ForegroundColor White
        Write-Host "  3. Server expects different header format" -ForegroundColor White
        Write-Host "  4. Token format incorrect (should be __token__:TOKEN)" -ForegroundColor White
        Write-Host ""
        Write-Host "Try comparing with working curl command:" -ForegroundColor Yellow
        Write-Host "  curl -v -u `"${Username}:${Password}`" `"$Url`"" -ForegroundColor Cyan
    }
    elseif ($statusCode -eq 404) {
        Write-Host "✓ Authentication worked! (404 = Package not found)" -ForegroundColor Green
        Write-Host ""
        Write-Host "The 404 status means:" -ForegroundColor Yellow
        Write-Host "  - Your credentials are CORRECT" -ForegroundColor White
        Write-Host "  - The server authenticated you successfully" -ForegroundColor White
        Write-Host "  - The package/path just doesn't exist" -ForegroundColor White
        exit 0
    }
    elseif ($statusCode -eq 403) {
        Write-Host "✓ Authentication worked, but access denied" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "The 403 status means:" -ForegroundColor Yellow
        Write-Host "  - Your credentials are valid" -ForegroundColor White
        Write-Host "  - But you don't have permission to access this resource" -ForegroundColor White
    }
    else {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    # Try to get response body from error
    if ($_.Exception.Response) {
        try {
            $responseStream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($responseStream)
            $responseBody = $reader.ReadToEnd()
            
            Write-Host ""
            Write-Host "Response Body:" -ForegroundColor Yellow
            Write-Host $responseBody -ForegroundColor White
        }
        catch {
            # Ignore
        }
    }
    
    Write-Host ""
    exit 1
}
