
Write-Host "1. 检查 WSL 服务..." -ForegroundColor Cyan
try {
    Write-Host "正在更新 WSL 服务..." -ForegroundColor Yellow
    wsl --update --web-download
    Write-Host "✅ WSL 服务更新成功" -ForegroundColor Green
} catch {
    Write-Host "⚠️  WSL 服务更新失败：" -ForegroundColor Yellow
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    Write-Host "继续执行其他步骤..." -ForegroundColor Yellow
}

Write-Host "2. 检查 Docker 安装状态..." -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️  Docker 未安装，请先安装 Docker Desktop" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "✅ Docker 已安装" -ForegroundColor Green
}

# ----------------------------
# 3. 下载工作台镜像
# ----------------------------
Write-Host "3. 下载工作台镜像..." -ForegroundColor Cyan
try {
    Write-Host "正在下载工作台镜像..." -ForegroundColor Yellow
    docker pull ghcr.io/openclaw/openclaw@sha256:a5a4c83b773aca85a8ba99cf155f09afa33946c0aa5cc6a9ccb6162738b5da02
    Write-Host "✅ 工作台镜像下载成功" -ForegroundColor Green
} catch {
    Write-Host "⚠️  工作台镜像下载失败：" -ForegroundColor Yellow
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    Write-Host "继续执行其他步骤..." -ForegroundColor Yellow
}


Write-Host "4. 查找本地 IP 地址..." -ForegroundColor Cyan
try {
    # 获取以太网适配器的 IPv4 地址
    # 优先选择 "以太网" 适配器的 IP 地址
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.InterfaceAlias -eq "以太网" -and 
        $_.IPAddress -notlike "169.254.*"
    }).IPAddress | Select-Object -First 1
    
    # 如果没有找到以太网适配器的 IP，再尝试获取 192.168 网段的 IP
    if (-not $localIP) {
        $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
            $_.InterfaceAlias -ne "Loopback Pseudo-Interface 1" -and 
            $_.IPAddress -notlike "169.254.*" -and
            $_.IPAddress -like "192.168.*"
        }).IPAddress | Select-Object -First 1
    }
    
    # 如果仍然没有找到，再尝试获取其他网段的 IP
    if (-not $localIP) {
        $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
            $_.InterfaceAlias -ne "Loopback Pseudo-Interface 1" -and 
            $_.IPAddress -notlike "169.254.*"
        }).IPAddress | Select-Object -First 1
    }
    
    if ($localIP) {
        Write-Host "✅ 找到本地 IP 地址：$localIP" -ForegroundColor Green
        
        # 1. 更新 .env 文件
        $envFile = "infra\compose\.env"
        if (Test-Path $envFile) {
            $envContent = Get-Content $envFile
            $envContent[0] = "CLAWLOOPS_DOMAIN=clawloops.$localIP.nip.io"
            $envContent[1] = "RUNTIME_MANAGER_DOMAIN=runtime-manager.$localIP.nip.io"
            $envContent[2] = "RUNTIME_PUBLIC_HOST=$localIP"
            Set-Content $envFile -Value $envContent
            Write-Host "✅ 已更新 .env 文件中的 IP 地址" -ForegroundColor Green
        } else {
            Write-Host "⚠️  .env 文件不存在，跳过更新" -ForegroundColor Yellow
        }
        
        # 2. 更新 Traefik 动态配置文件
        $traefikConfigFile = "infra\traefik\dynamic\middlewares.yml"
        if (Test-Path $traefikConfigFile) {
            $traefikContent = Get-Content $traefikConfigFile -Raw
            # 替换所有 IPv4 地址格式为本地 IP
            # 匹配 IPv4 地址格式 (xxx.xxx.xxx.xxx)
            $traefikContent = $traefikContent -replace '(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', $localIP
            # 替换 $localIP 变量为实际的本地 IP
            $traefikContent = $traefikContent -replace "\$localIP", $localIP
            Set-Content $traefikConfigFile -Value $traefikContent
            Write-Host "✅ 已更新 Traefik 配置文件中的 IP 地址" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Traefik 配置文件不存在，跳过更新" -ForegroundColor Yellow
        }
    } else {
        Write-Host "⚠️  未找到本地 IP 地址，使用默认配置" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ 查找本地 IP 地址失败：" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
}

# ----------------------------
# 5. 启动服务
# ----------------------------
Write-Host "5. 启动 ClawLoops 服务..." -ForegroundColor Cyan
Write-Host "正在构建和启动所有服务，这可能需要一些时间..." -ForegroundColor Yellow
try {
    docker compose --env-file infra\compose\.env -f infra\compose\docker-compose.yml up -d --build
    Write-Host "✅ 服务启动成功！" -ForegroundColor Green
} catch {
    Write-Host "❌ 启动服务失败：" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    exit 1
}

# ----------------------------
# 6. 显示服务状态
# ----------------------------
Write-Host "6. 服务状态检查..." -ForegroundColor Cyan
try {
    docker compose --env-file infra\compose\.env -f infra\compose\docker-compose.yml ps
} catch {
    Write-Host "❌ 检查服务状态失败：" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
}

# ----------------------------
# 7. 自动打开浏览器
# ----------------------------
Write-Host "7. 准备打开浏览器..." -ForegroundColor Cyan
try {
    # 读取更新后的 .env 文件，获取实际的访问地址
    $envFile = "infra\compose\.env"
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile
        $clawloopsDomain = $envContent[0].Split('=')[1]
        $accessUrl = "http://$clawloopsDomain"
        
        Write-Host "✅ 正在打开浏览器访问：$accessUrl" -ForegroundColor Green
        Start-Process $accessUrl
    } else {
        Write-Host "⚠️  .env 文件不存在，无法打开浏览器" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ 打开浏览器失败：" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
}

# ----------------------------
# 完成提示
# ----------------------------
Write-Host "===========================================" -ForegroundColor Green
Write-Host "🎉 ClawLoops 项目启动完成！" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""
if (Test-Path "infra\compose\.env") {
    $envContent = Get-Content "infra\compose\.env"
    $clawloopsDomain = $envContent[0].Split('=')[1]
    $accessUrl = "http://$clawloopsDomain"
    Write-Host "访问地址: $accessUrl" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "提示: " -ForegroundColor Yellow
Write-Host "1. 首次启动需要完成 Authentik 初始设置" -ForegroundColor Yellow
Write-Host "2. 完成设置后，需要在 .env 文件中设置 AUTHENTIK_OUTPOST_TOKEN" -ForegroundColor Yellow
Write-Host "3. 然后重新运行此脚本以启动所有服务" -ForegroundColor Yellow
Write-Host ""
